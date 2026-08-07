from datetime import datetime, timezone

from sqlalchemy import text

from services.common.ids import generate_id
from services.fraud_ml.linkage import linked_customers


def _insert_txn(db, *, customer_ref, device_id, ip="10.0.0.1"):
    txn_id = generate_id("txn")
    db.execute(
        text("""INSERT INTO transactions (txn_id, customer_ref, amount_inr, currency, merchant_category, status,
                decline_code, is_fraud_labeled, device_id, ip_address, timestamp)
                VALUES (:txn_id, :customer_ref, 100, 'INR', 'ECOM', 'SUCCESS', 'NONE', FALSE, :device_id, :ip, :ts)"""),
        {"txn_id": txn_id, "customer_ref": customer_ref, "device_id": device_id, "ip": ip,
         "ts": datetime.now(timezone.utc)},
    )
    db.flush()


def test_finds_customers_sharing_a_device(db):
    customers = db.execute(text("SELECT customer_ref FROM customers LIMIT 4")).mappings().all()
    refs = [c["customer_ref"] for c in customers]
    shared_device = "dev_linkage_test1"

    for ref in refs:
        _insert_txn(db, customer_ref=ref, device_id=shared_device, ip=f"10.0.0.{refs.index(ref)}")

    linked = linked_customers(db, refs[0])
    for other in refs[1:]:
        assert other in linked


def test_customer_with_unique_device_has_no_linkage(db):
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1 OFFSET 50")).mappings().first()
    _insert_txn(db, customer_ref=row["customer_ref"], device_id="dev_completely_unique_xyz", ip="203.0.113.1")
    linked = linked_customers(db, row["customer_ref"])
    assert linked == []


def test_unknown_customer_returns_empty(db):
    assert linked_customers(db, "cus_tok_does_not_exist_at_all") == []
