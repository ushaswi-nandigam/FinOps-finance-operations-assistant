"""Fraud Agent — the classical-model-first showcase (docs/architecture.md
§L5). The risk decision is entirely LightGBM + SHAP + networkx; the LLM's
only job is turning that model's own output into a plain-language memo.
Say that explicitly wherever this agent's output is displayed — it's the
single strongest "not everything needs an LLM" argument in the project.
"""

from typing import Any

from sqlalchemy.orm import Session

from services.common.cost import estimate_cost_inr
from services.common.config import settings
from services.common.ids import generate_id
from services.common.llm import generate_text
from services.common.schemas import CaseState
from services.fraud_ml.linkage import linked_customers
from services.fraud_ml.scorer import score_transaction
from services.orchestrator.agents.base import AgentOutput
from services.tools.executor import execute_tool
from services.triage.schemas import TriageResult

NAME = "fraud_agent"
SCOPES = ["crm:read", "payments:read", "casemgmt:write", "payments:write"]

HOLD_THRESHOLD = 0.7
REVIEW_THRESHOLD = 0.4


def _memo_prompt(txn: dict, risk_score: float, top_reasons: list[tuple[str, float]], linked: list[str]) -> str:
    reasons_text = "; ".join(f"{name}={value:+.2f}" for name, value in top_reasons)
    linked_text = f"{len(linked)} other account(s): {', '.join(linked[:5])}" if linked else "none"
    return f"""Write a short (3-4 sentence) plain-language fraud investigation memo for an ops analyst.

Facts (already decided by a classical model — you are only narrating them, not deciding anything):
- Transaction: ₹{txn['amount_inr']} at a {txn['merchant_category']} merchant, status={txn['status']}.
- LightGBM risk score: {risk_score:.2f} (threshold for a hold is {HOLD_THRESHOLD}).
- Top SHAP feature contributions (log-odds, positive pushes risk up): {reasons_text}.
- Linked accounts found via device/IP graph traversal: {linked_text}.

Write the memo in plain English a non-technical approver can act on in 20 seconds. \
Do not invent facts not given above. Do not use markdown formatting."""


def _write_memo(txn: dict, risk_score: float, top_reasons: list[tuple[str, float]], linked: list[str]) -> tuple[str, int, int, float]:
    try:
        text, tokens_in, tokens_out = generate_text(settings.MODEL_TIER_MID, _memo_prompt(txn, risk_score, top_reasons, linked))
        return text, tokens_in, tokens_out, estimate_cost_inr(settings.MODEL_TIER_MID, tokens_in, tokens_out)
    except Exception:
        # Template fallback keeps the case moving even if the LLM call fails
        # — the risk decision itself never depended on this call succeeding.
        reasons_text = ", ".join(f"{name} ({value:+.2f})" for name, value in top_reasons)
        linked_text = f"{len(linked)} linked account(s)" if linked else "no linked accounts"
        fallback = (f"Risk score {risk_score:.2f}. Top contributing factors: {reasons_text}. "
                    f"{linked_text} found via device/IP graph. (LLM memo unavailable; template summary shown.)")
        return fallback, 0, 0, 0.0


def handle(db: Session, case: CaseState, ops_event: dict, triage: TriageResult, *, revise: bool = False) -> AgentOutput:
    observations: list[dict[str, Any]] = []

    lookup = execute_tool(db, case_id=case.case_id, tool_name="lookup_status",
                           args={"customer_ref": case.customer_ref, "limit": 5}, dry_run=False)
    observations.append({"tool": "lookup_status", "result": lookup})
    customer = lookup.get("customer")
    if customer is None:
        return AgentOutput(proposal=None, observations=observations, tool_calls_used=1)

    transactions = lookup.get("recent_transactions") or []
    if not transactions:
        return AgentOutput(proposal=None, observations=observations, tool_calls_used=1)
    txn = transactions[0]

    from services.mocks.payments import PaymentsAdapter

    full_txn = PaymentsAdapter(db).get_transaction(txn["txn_id"]) or txn
    scoring = score_transaction(db, full_txn)
    linked = linked_customers(db, case.customer_ref)
    observations.append({"tool": "fraud_ml.score", "result": {"risk_score": scoring["risk_score"], "top_reasons": scoring["top_reasons"]}})
    observations.append({"tool": "fraud_ml.linkage", "result": {"linked_customers": linked}})

    memo, tokens_in, tokens_out, cost_inr = _write_memo(full_txn, scoring["risk_score"], scoring["top_reasons"], linked)
    observations.append({"tool": "llm.investigation_memo", "result": {"memo": memo}})

    evidence = [
        {"type": "transaction", "ref": full_txn["txn_id"]},
        {"type": "fraud_ml_score", "ref": f"{scoring['risk_score']:.2f}"},
    ] + [{"type": "linked_customer", "ref": c} for c in linked[:5]]

    risk_score = scoring["risk_score"]
    if risk_score > HOLD_THRESHOLD:
        proposal = {
            "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
            "action_type": "place_fraud_hold",
            "args": {"customer_ref": case.customer_ref, "fraud_case_id": generate_id("frd"), "fraud_score": risk_score},
            "evidence": evidence, "confidence": 0.9, "proposed_by": NAME,
            "reasoning": memo,
        }
    elif risk_score >= REVIEW_THRESHOLD:
        proposal = {
            "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
            "action_type": "create_internal_task",
            "args": {"title": f"Fraud review (score {risk_score:.2f})", "description": memo, "category": "fraud"},
            "evidence": evidence, "confidence": 0.8, "proposed_by": NAME,
            "reasoning": f"Risk score {risk_score:.2f} is in the manual-review band ({REVIEW_THRESHOLD}-{HOLD_THRESHOLD}); routing to a human analyst rather than auto-closing.",
        }
    else:
        proposal = {
            "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
            "action_type": "close_fraud_case_benign",
            "args": {"fraud_case_id": generate_id("frd"), "fraud_score": risk_score},
            "evidence": evidence, "confidence": 0.85, "proposed_by": NAME,
            "reasoning": f"Risk score {risk_score:.2f} is below the review threshold ({REVIEW_THRESHOLD}); {memo}",
        }

    return AgentOutput(proposal=proposal, observations=observations, tool_calls_used=1,
                        tokens_in=tokens_in, tokens_out=tokens_out, cost_inr=cost_inr)
