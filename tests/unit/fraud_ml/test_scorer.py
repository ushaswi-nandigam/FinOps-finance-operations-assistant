from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from services.common.ids import generate_id
from services.fraud_ml.scorer import score_transaction


def _insert_txn(db, *, customer_ref, device_id, amount, ts, status="SUCCESS", merchant="ECOM"):
    txn_id = generate_id("txn")
    db.execute(
        text("""INSERT INTO transactions (txn_id, customer_ref, amount_inr, currency, merchant_category, status,
                decline_code, is_fraud_labeled, device_id, ip_address, timestamp)
                VALUES (:txn_id, :customer_ref, :amount, 'INR', :merchant, :status, 'NONE', FALSE, :device_id, '10.0.0.1', :ts)"""),
        {"txn_id": txn_id, "customer_ref": customer_ref, "amount": amount, "merchant": merchant,
         "status": status, "device_id": device_id, "ts": ts},
    )
    db.flush()
    return txn_id


def _get_txn(db, txn_id):
    return dict(db.execute(text("SELECT * FROM transactions WHERE txn_id = :id"), {"id": txn_id}).mappings().first())


def test_risk_score_in_valid_range(db):
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    txn_id = _insert_txn(db, customer_ref=row["customer_ref"], device_id="dev_scorer_test1", amount=1500,
                          ts=datetime.now(timezone.utc))
    result = score_transaction(db, _get_txn(db, txn_id))
    assert 0.0 <= result["risk_score"] <= 1.0
    assert len(result["top_reasons"]) > 0


def test_high_amount_zscore_and_shared_device_scores_higher_than_normal_txn(db):
    customers = db.execute(text("SELECT customer_ref FROM customers LIMIT 5")).mappings().all()
    target_customer = customers[0]["customer_ref"]
    now = datetime.now(timezone.utc)

    # Establish a normal spending history for the target customer.
    for i in range(5):
        _insert_txn(db, customer_ref=target_customer, device_id="dev_normal_history",
                    amount=500 + i * 10, ts=now - timedelta(days=i + 1))

    # A shared "ring" device used by several other customers too.
    ring_device = "dev_ring_scorer_test"
    for c in customers[1:]:
        _insert_txn(db, customer_ref=c["customer_ref"], device_id=ring_device, amount=400, ts=now - timedelta(hours=2))

    normal_txn_id = _insert_txn(db, customer_ref=target_customer, device_id="dev_normal_history", amount=510, ts=now)
    risky_txn_id = _insert_txn(db, customer_ref=target_customer, device_id=ring_device, amount=45000, ts=now)

    normal_result = score_transaction(db, _get_txn(db, normal_txn_id))
    risky_result = score_transaction(db, _get_txn(db, risky_txn_id))

    assert risky_result["risk_score"] > normal_result["risk_score"]
    assert risky_result["features"]["device_shared_count"] >= 4
    top_reason_features = [f for f, _ in risky_result["top_reasons"]]
    assert "amount_zscore" in top_reason_features or "device_shared_count" in top_reason_features


def test_shap_contributions_sum_relates_to_all_features(db):
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    txn_id = _insert_txn(db, customer_ref=row["customer_ref"], device_id="dev_scorer_test2", amount=800,
                          ts=datetime.now(timezone.utc))
    result = score_transaction(db, _get_txn(db, txn_id))
    assert set(result["shap_contributions"].keys()) == set(result["features"].keys())
