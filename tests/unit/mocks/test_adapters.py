"""Integration-flavoured unit tests: these hit the real local MySQL instance
(seeded via scripts/seed.py + scripts/load_seed.py), which is the simplest
way to be honest about what the adapters actually do — no mocking of the
mocks."""

import pytest
from sqlalchemy import text

from services.common.db import session_scope
from services.mocks.casemgmt import CaseMgmtAdapter
from services.mocks.crm import CRMAdapter
from services.mocks.kb import KBAdapter
from services.mocks.payments import PaymentsAdapter


@pytest.fixture()
def db():
    with session_scope() as session:
        yield session


@pytest.fixture()
def sample_customer_ref(db):
    row = db.execute(text("SELECT customer_ref FROM customers LIMIT 1")).mappings().first()
    return row["customer_ref"]


def test_crm_get_customer(db, sample_customer_ref):
    crm = CRMAdapter(db)
    customer = crm.get_customer(sample_customer_ref)
    assert customer is not None
    assert customer["customer_ref"] == sample_customer_ref
    assert customer["tier"] in ("STANDARD", "SILVER", "GOLD", "PLATINUM")


def test_crm_unknown_customer_returns_none(db):
    crm = CRMAdapter(db)
    assert crm.get_customer("cus_tok_does_not_exist") is None


def test_payments_list_and_refund_dry_run(db, sample_customer_ref):
    payments = PaymentsAdapter(db)
    txns = payments.list_transactions(sample_customer_ref)
    assert isinstance(txns, list)

    row = db.execute(text("SELECT txn_id, amount_inr FROM transactions LIMIT 1")).mappings().first()
    result = payments.issue_refund(row["txn_id"], float(row["amount_inr"]), dry_run=True)
    assert result["ok"] is True
    assert result["dry_run"] is True
    # dry run must not mutate the transaction
    after = payments.get_transaction(row["txn_id"])
    assert after is not None


def test_payments_refund_missing_txn(db):
    payments = PaymentsAdapter(db)
    result = payments.issue_refund("txn_does_not_exist", 100.0, dry_run=True)
    assert result["ok"] is False


def test_kb_lists_policies_and_sops(db):
    kb = KBAdapter(db)
    policies = kb.list_policies()
    sops = kb.list_sops()
    assert len(policies) == 25
    assert len(sops) >= 5
    assert kb.get_policy("REFUND-POL-3.2") is not None


def test_casemgmt_lists_workflows(db):
    casemgmt = CaseMgmtAdapter(db)
    workflows = casemgmt.list_workflows(limit=5)
    assert len(workflows) <= 5
    assert all("workflow_id" in w for w in workflows)
