"""L4 — the orchestrator: a hand-rolled async-free state machine, not
LangGraph (docs/architecture.md §L4 explicitly allows this lighter option).
Owns the case lifecycle:

    INTAKE -> CONTEXT_GATHER -> PLAN -> ACT -> SELF_VERIFY -> RISK_GATE
            -> [APPROVAL_PENDING] -> EXECUTE -> RESOLVE | ESCALATE

Every transition is checkpointed to MySQL (case_store.save_case) before the
next one runs, and every terminal decision — including escalations — is
written to the audit ledger with the same rigour. `APPROVAL_PENDING` is the
one state genuinely designed to be resumed later, potentially hours after
this function returns; resumption is `resume_after_approval()` in
services/orchestrator/resume.py (added when the approvals API lands).
"""

from sqlalchemy.orm import Session

from services.audit.ledger import record_decision
from services.common.config import settings
from services.common.enums import CaseStatus, Domain, Outcome
from services.common.schemas import ActorRecord, CaseState, CostRecord
from services.mocks.crm import CRMAdapter
from services.mocks.payments import PaymentsAdapter
from services.orchestrator.agents import payments, support
from services.orchestrator.approvals import create_approval_requests
from services.orchestrator.case_store import create_case, save_case
from services.orchestrator.events import get_ops_event
from services.orchestrator.verify import verify
from services.policy_engine.engine import authorise
from services.tools.executor import execute_tool
from services.triage.cascade import triage
from services.triage.schemas import TriageResult

# Extended in later build steps as Fraud/InternalOps agents land.
AGENT_HANDLERS = {Domain.SUPPORT: support.handle, Domain.PAYMENTS: payments.handle}
AGENT_NAMES = {Domain.SUPPORT: support.NAME, Domain.PAYMENTS: payments.NAME}

MONEY_MOVING_ACTIONS = {"issue_refund", "waive_fee"}


def process_event(db: Session, event_id: str) -> CaseState:
    """The single entrypoint: triage an ingested event, open a case, and run
    it as far as the state machine can go without a human."""
    ops_event = get_ops_event(db, event_id)
    if ops_event is None:
        raise ValueError(f"no ops_event with event_id={event_id}")

    triage_result = triage(ops_event["source"], ops_event["redacted_text"], ops_event["entities"])

    case = create_case(db, event_id=event_id, domain=triage_result.domain, customer_ref=ops_event["customer_ref"])
    save_case(db, case, triage_stage=triage_result.route_stage)

    return advance_case(db, case, ops_event, triage_result)


def advance_case(db: Session, case: CaseState, ops_event: dict, triage_result: TriageResult) -> CaseState:
    agent_handle = AGENT_HANDLERS.get(case.domain)
    agent_name = AGENT_NAMES.get(case.domain, "unassigned")

    if agent_handle is None:
        return _escalate(db, case, agent_name=agent_name,
                          reason=f"No agent is wired up for domain '{case.domain.value}' yet.")

    case.status = CaseStatus.CONTEXT_GATHER
    save_case(db, case)

    output = agent_handle(db, case, ops_event, triage_result)
    case.observations.extend(output.observations)
    case.tool_calls_used += output.tool_calls_used
    case.cost.tokens_in += output.tokens_in
    case.cost.tokens_out += output.tokens_out
    case.cost.inr += output.cost_inr

    case.status = CaseStatus.PLAN
    case.plan = [output.proposal["action_type"]] if output.proposal else []
    save_case(db, case)

    case.status = CaseStatus.ACT
    if output.proposal:
        case.proposals.append(output.proposal)
    save_case(db, case)

    if output.proposal is None:
        return _escalate(db, case, agent_name=agent_name,
                          reason="The agent could not gather enough context to propose an action (e.g. unknown customer).")

    proposal = output.proposal

    case.status = CaseStatus.SELF_VERIFY
    verifier_report = verify(proposal)
    case.verifier_report = verifier_report
    save_case(db, case)

    case.status = CaseStatus.RISK_GATE
    save_case(db, case)

    customer = CRMAdapter(db).get_customer(case.customer_ref)
    # fraud_score defaults to 0.0 until the Fraud ML model lands (build step
    # 9); the gate itself already exists and is exercised by
    # tests/unit/policy_engine — this is where a real score will plug in for
    # every money-moving proposal, regardless of which agent made it.
    fraud_score = 0.0
    refund_30d_inr = 0.0
    if proposal["action_type"] in MONEY_MOVING_ACTIONS:
        refund_30d_inr = PaymentsAdapter(db).refund_history_30d(case.customer_ref)

    decision = authorise(
        proposal_id=proposal["proposal_id"], case_id=case.case_id, action_type=proposal["action_type"],
        amount_inr=proposal["args"].get("amount_inr"), customer=customer,
        fraud_score=fraud_score, refund_30d_inr=refund_30d_inr,
        agent_confidence=proposal["confidence"], verifier_verdict=verifier_report["verdict"],
        tool_calls_used=case.tool_calls_used, max_tool_calls=case.max_tool_calls,
        revisions=case.revisions, max_revisions=case.max_revisions,
        cost_inr=case.cost.inr, cost_budget_inr=case.cost_budget_inr,
        policy_version=settings.POLICY_VERSION,
    )
    case.risk_decision = decision.model_dump()
    save_case(db, case)

    record_decision(
        db, case_id=case.case_id,
        actor=ActorRecord(type="agent", name=proposal["proposed_by"], model=None, version="v0.1"),
        action={"type": proposal["action_type"], "args": proposal["args"]},
        outcome=decision.outcome.value, reason_plain=decision.reason_plain,
        evidence=proposal["evidence"], matched_rules=decision.matched_rules, verifier=verifier_report,
        cost=CostRecord(stage=case.status.value, tokens_in=output.tokens_in, tokens_out=output.tokens_out, inr=output.cost_inr),
        policy_version=decision.policy_version,
    )

    if decision.outcome == Outcome.AUTO_EXECUTE:
        case.status = CaseStatus.EXECUTE
        save_case(db, case)
        result = execute_tool(db, case_id=case.case_id, tool_name=proposal["action_type"], args=proposal["args"], dry_run=False)
        case.observations.append({"tool": proposal["action_type"], "result": result})
        case.status = CaseStatus.RESOLVE
        save_case(db, case)
    elif decision.outcome in (Outcome.NEEDS_APPROVAL, Outcome.DUAL_APPROVAL):
        case.status = CaseStatus.APPROVAL_PENDING
        save_case(db, case)
        create_approval_requests(db, case_id=case.case_id, proposal_id=proposal["proposal_id"], decision=decision)
    else:  # ESCALATE / DENY
        case.status = CaseStatus.ESCALATE
        save_case(db, case)

    return case


def _escalate(db: Session, case: CaseState, *, agent_name: str, reason: str) -> CaseState:
    case.status = CaseStatus.ESCALATE
    case.error = reason
    save_case(db, case)
    record_decision(
        db, case_id=case.case_id, actor=ActorRecord(type="system", name=agent_name),
        action={"type": "none"}, outcome=Outcome.ESCALATE.value, reason_plain=reason,
        policy_version=settings.POLICY_VERSION,
    )
    return case
