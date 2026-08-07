"""Loads data/generated/*.json (produced by scripts/seed.py) into MySQL.

Idempotent: wipes and reloads the reference tables every run, in FK-safe
order. Never touches runtime tables (cases, decision_records, approvals,
tool_calls, ops_events, ...) — those are demo state, not seed data.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.common.db import session_scope  # noqa: E402
from sqlalchemy import text  # noqa: E402

DATA_DIR = ROOT / "data" / "generated"

DELETE_ORDER = [
    "policy_embeddings", "disputes", "fraud_cases", "tickets", "transcripts",
    "transactions", "sops", "internal_ops_workflows", "policies", "customers",
]


def _load(name: str) -> list[dict]:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main() -> None:
    customers = _load("customers.json")
    transactions = _load("transactions.json")
    tickets = _load("tickets.json")
    transcripts = _load("transcripts.json")
    disputes = _load("disputes.json")
    fraud_cases = _load("fraud_cases.json")
    policies = _load("policies.json")
    sops = _load("sops.json")
    workflows = _load("internal_ops_workflows.json")

    with session_scope() as db:
        for table in DELETE_ORDER:
            db.execute(text(f"DELETE FROM {table}"))

        db.execute(
            text("""INSERT INTO customers
                (customer_ref, name, email, phone, tier, tenure_months, kyc_status, is_flagged, is_minor, created_at)
                VALUES (:customer_ref, :name, :email, :phone, :tier, :tenure_months, :kyc_status, :is_flagged, :is_minor, :created_at)"""),
            [{**c, "created_at": _dt(c["created_at"])} for c in customers],
        )

        db.execute(
            text("""INSERT INTO transactions
                (txn_id, customer_ref, amount_inr, currency, merchant_category, status, decline_code,
                 is_fraud_labeled, device_id, ip_address, timestamp)
                VALUES (:txn_id, :customer_ref, :amount_inr, :currency, :merchant_category, :status, :decline_code,
                        :is_fraud_labeled, :device_id, :ip_address, :timestamp)"""),
            [{**t, "timestamp": _dt(t["timestamp"])} for t in transactions],
        )

        db.execute(
            text("""INSERT INTO tickets (ticket_id, customer_ref, intent, text, created_at)
                VALUES (:ticket_id, :customer_ref, :intent, :text, :created_at)"""),
            [{**t, "created_at": _dt(t["created_at"])} for t in tickets],
        )

        db.execute(
            text("""INSERT INTO transcripts
                (transcript_id, customer_ref, channel, turns, contains_pii, contains_injection, created_at)
                VALUES (:transcript_id, :customer_ref, :channel, :turns, :contains_pii, :contains_injection, :created_at)"""),
            [{**t, "turns": json.dumps(t["turns"]), "created_at": _dt(t["created_at"])} for t in transcripts],
        )

        db.execute(
            text("""INSERT INTO disputes (dispute_id, customer_ref, txn_id, reason, amount_inr, lifecycle_stage, created_at)
                VALUES (:dispute_id, :customer_ref, :txn_id, :reason, :amount_inr, :lifecycle_stage, :created_at)"""),
            [{**d, "created_at": _dt(d["created_at"])} for d in disputes],
        )

        db.execute(
            text("""INSERT INTO fraud_cases
                (fraud_case_id, customer_ref, txn_id, status, risk_score, linked_accounts, investigator_notes, created_at)
                VALUES (:fraud_case_id, :customer_ref, :txn_id, :status, :risk_score, :linked_accounts, :investigator_notes, :created_at)"""),
            [{**f, "linked_accounts": json.dumps(f["linked_accounts"]), "created_at": _dt(f["created_at"])} for f in fraud_cases],
        )

        db.execute(
            text("INSERT INTO policies (id, title, content, category) VALUES (:id, :title, :content, :category)"),
            policies,
        )

        db.execute(
            text("INSERT INTO sops (id, title, content, category) VALUES (:id, :title, :content, :category)"),
            sops,
        )

        db.execute(
            text("""INSERT INTO internal_ops_workflows
                (workflow_id, title, description, category, approval_required, status, created_at)
                VALUES (:workflow_id, :title, :description, :category, :approval_required, :status, :created_at)"""),
            [{**w, "created_at": _dt(w["created_at"])} for w in workflows],
        )

    print(f"[OK] Loaded {len(customers)} customers, {len(transactions)} transactions, "
          f"{len(tickets)} tickets, {len(transcripts)} transcripts, {len(disputes)} disputes, "
          f"{len(fraud_cases)} fraud cases, {len(policies)} policies, {len(sops)} SOPs, "
          f"{len(workflows)} workflows into MySQL.")


if __name__ == "__main__":
    main()
