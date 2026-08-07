from sqlalchemy import text

from services.common.enums import CaseStatus, Outcome
from services.orchestrator.case_store import load_case
from services.orchestrator.graph import process_event
from services.privacy.redactor import redact
from services.common.ids import event_id as new_event_id, trace_id as new_trace_id
import json
from datetime import datetime, timezone


def _make_ops_event(db, *, source: str, customer_ref: str, channel: str, raw_text: str) -> str:
    eid, tid = new_event_id(), new_trace_id()
    redacted_text, entities = redact(db, raw_text, eid)
    db.execute(
        text("""INSERT INTO ops_events
            (event_id, source, received_at, customer_ref, channel, redacted_text, entities, attachments, trace_id, processed_l2)
            VALUES (:id, :source, :received_at, :customer_ref, :channel, :redacted_text, :entities, :attachments, :trace_id, TRUE)"""),
        {"id": eid, "source": source, "received_at": datetime.now(timezone.utc), "customer_ref": customer_ref,
         "channel": channel, "redacted_text": redacted_text, "entities": json.dumps(entities), "attachments": "[]",
         "trace_id": tid},
    )
    return eid


def test_scenario1_refund_status_query_fully_autonomous(db):
    """Golden path scenario 1 (architecture.md §6): a status query resolves
    end to end with zero human involvement and zero LLM calls in the
    decision path."""
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    customer_ref = row["customer_ref"]

    event_id = _make_ops_event(db, source="support_ticket", customer_ref=customer_ref, channel="chat",
                                raw_text="My refund for order #ORD-4471 hasn't come through yet, please check.")
    db.flush()

    case = process_event(db, event_id)
    db.flush()

    assert case.status == CaseStatus.RESOLVE
    assert case.risk_decision["outcome"] == Outcome.AUTO_EXECUTE.value
    assert case.tool_calls_used >= 1
    assert case.cost.inr == 0.0  # no LLM in the decision path

    persisted = load_case(db, case.case_id)
    assert persisted["status"] == "RESOLVE"

    decisions = db.execute(text("SELECT * FROM decision_records WHERE case_id = :id"), {"id": case.case_id}).mappings().all()
    assert len(decisions) == 1
    assert decisions[0]["outcome"] == "AUTO_EXECUTE"
    assert decisions[0]["reason_plain"] != ""


def test_unknown_domain_agent_escalates_cleanly(db):
    """Domain.COMPLIANCE has no triage rule that routes to it (the
    Compliance Agent is a citation service other agents/the console call
    directly, not a case-owning domain agent — see
    services/orchestrator/agents/compliance.py) and so is never wired into
    AGENT_HANDLERS. advance_case must escalate cleanly for any domain
    that isn't, rather than crash — exercised directly here since no
    ingress path can produce a COMPLIANCE-domain case to route through
    process_event()."""
    from services.common.enums import Domain
    from services.orchestrator.case_store import create_case, save_case
    from services.orchestrator.graph import advance_case
    from services.triage.schemas import TriageResult

    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    case = create_case(db, event_id="evt_compliance_test", domain=Domain.COMPLIANCE, customer_ref=row["customer_ref"])
    save_case(db, case)
    triage_result = TriageResult(intent="other", domain=Domain.COMPLIANCE, confidence=1.0, route_stage="T0_RULES")

    case = advance_case(db, case, {"event_id": "evt_compliance_test", "redacted_text": "x"}, triage_result)
    db.flush()

    assert case.status == CaseStatus.ESCALATE
    assert "no agent" in (case.error or "").lower() or "compliance" in (case.error or "").lower()

    decisions = db.execute(text("SELECT * FROM decision_records WHERE case_id = :id"), {"id": case.case_id}).mappings().all()
    assert len(decisions) == 1
    assert decisions[0]["outcome"] == "ESCALATE"
