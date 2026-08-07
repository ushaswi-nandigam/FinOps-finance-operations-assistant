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
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    event_id = _make_ops_event(db, source="internal_ops", customer_ref=row["customer_ref"], channel="form",
                                raw_text="Onboard new merchant MerchantX")
    db.flush()

    case = process_event(db, event_id)
    db.flush()

    # Domain resolves to INTERNAL_OPS via T0 rule, but no Internal Ops Agent
    # is wired up yet (a later build step) — must escalate, not crash.
    assert case.status == CaseStatus.ESCALATE
    assert "no agent" in (case.error or "").lower() or "internal_ops" in (case.error or "").lower()

    decisions = db.execute(text("SELECT * FROM decision_records WHERE case_id = :id"), {"id": case.case_id}).mappings().all()
    assert len(decisions) == 1
    assert decisions[0]["outcome"] == "ESCALATE"
