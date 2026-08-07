"""Golden path scenario 2 (architecture.md §6): failed payment -> Payments
Agent proposes a refund -> policy engine requires approval -> a human
approves -> executed -> audit trail complete. Also covers the T3 dual
approval variant and a rejection, end to end through the HTTP API.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text

from services.api.main import app
from services.common.db import session_scope
from services.common.ids import generate_id

client = TestClient(app)


def _insert_failed_txn(db, customer_ref: str, amount: float) -> str:
    txn_id = generate_id("txn")
    db.execute(
        text("""INSERT INTO transactions (txn_id, customer_ref, amount_inr, currency, merchant_category, status,
                decline_code, is_fraud_labeled, device_id, ip_address, timestamp)
                VALUES (:txn_id, :customer_ref, :amount, 'INR', 'ECOM', 'FAILED', 'GATEWAY_TIMEOUT', FALSE,
                        'dev_test', '127.0.0.1', :ts)"""),
        {"txn_id": txn_id, "customer_ref": customer_ref, "amount": amount, "ts": datetime.now(timezone.utc)},
    )
    return txn_id


def test_scenario2_single_approval_end_to_end():
    with session_scope() as db:
        row = db.execute(text("SELECT customer_ref FROM customers WHERE is_flagged = FALSE AND is_minor = FALSE LIMIT 1")).mappings().first()
        customer_ref = row["customer_ref"]
        txn_id = _insert_failed_txn(db, customer_ref, 2499.0)

    ingress_resp = client.post("/ingress/ticket", json={
        "customer_ref": customer_ref,
        "text": f"Charged ₹2499 for order but payment failed at gateway (txn #{txn_id}). Need full refund.",
    })
    assert ingress_resp.status_code == 200
    event_id = ingress_resp.json()["event_id"]

    process_resp = client.post("/cases/process", json={"event_id": event_id})
    assert process_resp.status_code == 200
    case = process_resp.json()
    assert case["status"] == "APPROVAL_PENDING"
    assert case["risk_decision"]["outcome"] == "NEEDS_APPROVAL"
    assert case["risk_decision"]["tier"] == "T2"

    pending_resp = client.get("/approvals")
    assert pending_resp.status_code == 200
    approval = next(a for a in pending_resp.json() if a["case_id"] == case["case_id"])
    assert approval["proposal"]["action_type"] == "issue_refund"

    decide_resp = client.post(f"/approvals/{approval['approval_id']}/decide", json={
        "approver_id": "ops_alice", "decision": "approve", "reason": "matches policy, approving",
    })
    assert decide_resp.status_code == 200
    body = decide_resp.json()
    assert body["all_required_approved"] is True
    assert body["case"]["status"] == "RESOLVE"

    with session_scope() as db:
        txn = db.execute(text("SELECT status FROM transactions WHERE txn_id = :id"), {"id": txn_id}).mappings().first()
        assert txn["status"] == "REFUNDED"

        decisions = db.execute(text("SELECT outcome, reason_plain FROM decision_records WHERE case_id = :id ORDER BY case_seq"),
                                {"id": case["case_id"]}).mappings().all()
        outcomes = [d["outcome"] for d in decisions]
        assert outcomes == ["NEEDS_APPROVAL", "AUTO_EXECUTE"]


def test_scenario2_dual_approval_large_refund_needs_two_distinct_approvers():
    with session_scope() as db:
        row = db.execute(text("SELECT customer_ref FROM customers WHERE is_flagged = FALSE AND is_minor = FALSE LIMIT 1 OFFSET 1")).mappings().first()
        customer_ref = row["customer_ref"]
        txn_id = _insert_failed_txn(db, customer_ref, 40000.0)

    ingress_resp = client.post("/ingress/ticket", json={
        "customer_ref": customer_ref,
        "text": f"Charged ₹40000 for order but payment failed at gateway (txn #{txn_id}). Need full refund.",
    })
    event_id = ingress_resp.json()["event_id"]
    case = client.post("/cases/process", json={"event_id": event_id}).json()
    assert case["risk_decision"]["tier"] == "T3"
    assert case["risk_decision"]["outcome"] == "DUAL_APPROVAL"

    approvals_list = client.get("/approvals").json()
    slots = [a for a in approvals_list if a["case_id"] == case["case_id"]]
    assert len(slots) == 2

    # Same approver on both slots must be rejected (maker cannot be checker).
    r1 = client.post(f"/approvals/{slots[0]['approval_id']}/decide",
                      json={"approver_id": "ops_alice", "decision": "approve", "reason": "ok"})
    assert r1.status_code == 200
    r2_same = client.post(f"/approvals/{slots[1]['approval_id']}/decide",
                           json={"approver_id": "ops_alice", "decision": "approve", "reason": "ok"})
    assert r2_same.status_code == 409

    r2 = client.post(f"/approvals/{slots[1]['approval_id']}/decide",
                      json={"approver_id": "ops_bob", "decision": "approve", "reason": "confirmed with alice"})
    assert r2.status_code == 200
    assert r2.json()["case"]["status"] == "RESOLVE"

    with session_scope() as db:
        txn = db.execute(text("SELECT status FROM transactions WHERE txn_id = :id"), {"id": txn_id}).mappings().first()
        assert txn["status"] == "REFUNDED"


def test_scenario2_rejection_escalates_case_not_execute():
    with session_scope() as db:
        row = db.execute(text("SELECT customer_ref FROM customers WHERE is_flagged = FALSE AND is_minor = FALSE LIMIT 1 OFFSET 2")).mappings().first()
        customer_ref = row["customer_ref"]
        txn_id = _insert_failed_txn(db, customer_ref, 3000.0)

    ingress_resp = client.post("/ingress/ticket", json={
        "customer_ref": customer_ref,
        "text": f"Charged ₹3000 for order but payment failed at gateway (txn #{txn_id}). Need full refund.",
    })
    event_id = ingress_resp.json()["event_id"]
    case = client.post("/cases/process", json={"event_id": event_id}).json()
    approval = next(a for a in client.get("/approvals").json() if a["case_id"] == case["case_id"])

    decide_resp = client.post(f"/approvals/{approval['approval_id']}/decide", json={
        "approver_id": "ops_alice", "decision": "reject", "reason": "duplicate refund request already processed",
    })
    assert decide_resp.status_code == 200
    assert decide_resp.json()["case"]["status"] == "ESCALATE"

    with session_scope() as db:
        txn = db.execute(text("SELECT status FROM transactions WHERE txn_id = :id"), {"id": txn_id}).mappings().first()
        assert txn["status"] == "FAILED"  # never executed
