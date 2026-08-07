from sqlalchemy import text

from services.common.enums import Domain
from services.common.schemas import CaseState
from services.orchestrator.agents import support
from services.triage.schemas import TriageResult


def _case_for(customer_ref: str) -> CaseState:
    return CaseState(case_id="case_test1", event_id="evt_test1", domain=Domain.SUPPORT, customer_ref=customer_ref)


def test_refund_status_query_answers_from_system_of_record_no_llm(db):
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    customer_ref = row["customer_ref"]
    case = _case_for(customer_ref)
    triage = TriageResult(intent="refund_status_query", domain=Domain.SUPPORT, confidence=0.97,
                           route_stage="T1_CLASSIFIER", extracted_slots={})

    output = support.handle(db, case, {"event_id": "evt_test1", "redacted_text": "where is my refund"}, triage)

    assert output.proposal is not None
    assert output.proposal["action_type"] == "send_templated_reply"
    assert output.proposal["proposed_by"] == "support_agent"
    assert output.tokens_in == 0 and output.tokens_out == 0 and output.cost_inr == 0.0  # no LLM call
    assert output.tool_calls_used == 1


def test_unknown_customer_returns_none_proposal(db):
    case = _case_for("cus_tok_does_not_exist")
    triage = TriageResult(intent="refund_status_query", domain=Domain.SUPPORT, confidence=0.9, route_stage="T1_CLASSIFIER")
    output = support.handle(db, case, {"event_id": "evt_x", "redacted_text": "x"}, triage)
    assert output.proposal is None


def test_kyc_query_answers_from_crm_field(db):
    row = db.execute(text("SELECT customer_ref FROM customers WHERE kyc_status = 'PENDING' LIMIT 1")).mappings().first()
    case = _case_for(row["customer_ref"])
    triage = TriageResult(intent="kyc_verification_status", domain=Domain.SUPPORT, confidence=0.9, route_stage="T1_CLASSIFIER")
    output = support.handle(db, case, {"event_id": "evt_kyc", "redacted_text": "kyc status?"}, triage)
    assert "under review" in output.proposal["args"]["template"]


def test_unhandled_intent_routes_to_internal_task(db):
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    case = _case_for(row["customer_ref"])
    triage = TriageResult(intent="limit_enhancement_request", domain=Domain.SUPPORT, confidence=0.9, route_stage="T1_CLASSIFIER")
    output = support.handle(db, case, {"event_id": "evt_y", "redacted_text": "please raise my limit"}, triage)
    assert output.proposal["action_type"] == "create_internal_task"
