from datetime import datetime, timezone

from sqlalchemy import text

from services.common.enums import Domain
from services.common.ids import generate_id
from services.common.schemas import CaseState
from services.orchestrator.agents import payments
from services.triage.schemas import TriageResult


def _case_for(customer_ref: str) -> CaseState:
    return CaseState(case_id="case_pay_test", event_id="evt_pay_test", domain=Domain.PAYMENTS, customer_ref=customer_ref)


def _insert_failed_txn(db, customer_ref: str, amount: float) -> str:
    """Inserted with 'now' as the timestamp so it's deterministically the
    customer's most recent transaction — lookup_status only returns the top
    10, and picking an existing seeded row risks it falling outside that
    window for a customer with many transactions."""
    txn_id = generate_id("txn")
    db.execute(
        text("""INSERT INTO transactions (txn_id, customer_ref, amount_inr, currency, merchant_category, status,
                decline_code, is_fraud_labeled, device_id, ip_address, timestamp)
                VALUES (:txn_id, :customer_ref, :amount, 'INR', 'ECOM', 'FAILED', 'GATEWAY_TIMEOUT', FALSE,
                        'dev_test', '127.0.0.1', :ts)"""),
        {"txn_id": txn_id, "customer_ref": customer_ref, "amount": amount, "ts": datetime.now(timezone.utc)},
    )
    db.flush()
    return txn_id


def test_failed_transaction_proposes_full_refund(db):
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    txn_id = _insert_failed_txn(db, row["customer_ref"], 2499.0)
    case = _case_for(row["customer_ref"])
    triage = TriageResult(intent="failed_transaction_refund", domain=Domain.PAYMENTS, confidence=0.95,
                           route_stage="T1_CLASSIFIER", extracted_slots={"txn_ids": [txn_id]})

    output = payments.handle(db, case, {"event_id": "evt_x", "redacted_text": "payment failed"}, triage)

    assert output.proposal["action_type"] == "issue_refund"
    assert output.proposal["args"]["txn_id"] == txn_id
    assert output.proposal["args"]["amount_inr"] == 2499.0
    assert output.tokens_in == 0 and output.cost_inr == 0.0  # no LLM


def test_fee_waiver_request_proposes_waive_fee(db):
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    case = _case_for(row["customer_ref"])
    triage = TriageResult(intent="fee_waiver_request", domain=Domain.PAYMENTS, confidence=0.9,
                           route_stage="T1_CLASSIFIER", extracted_slots={"amounts_inr": [800.0]})
    output = payments.handle(db, case, {"event_id": "evt_y", "redacted_text": "waive my fee"}, triage)
    assert output.proposal["action_type"] == "waive_fee"
    assert output.proposal["args"]["amount_inr"] == 800.0


def test_unresolvable_intent_routes_to_internal_task(db):
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    case = _case_for(row["customer_ref"])
    triage = TriageResult(intent="cashback_not_credited", domain=Domain.PAYMENTS, confidence=0.9, route_stage="T1_CLASSIFIER")
    output = payments.handle(db, case, {"event_id": "evt_z", "redacted_text": "where is my cashback"}, triage)
    assert output.proposal["action_type"] == "create_internal_task"


def test_unknown_customer_returns_none(db):
    case = _case_for("cus_tok_does_not_exist")
    triage = TriageResult(intent="fee_waiver_request", domain=Domain.PAYMENTS, confidence=0.9, route_stage="T1_CLASSIFIER")
    output = payments.handle(db, case, {"event_id": "evt_w", "redacted_text": "x"}, triage)
    assert output.proposal is None
