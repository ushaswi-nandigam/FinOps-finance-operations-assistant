"""mock-payments — transactions, refunds, retries, disputes.

Every side-effecting method takes `dry_run`: when True it returns the
projected result without mutating anything, which is what the approval card
(architecture.md §L8) shows a human before they decide, and what the
execution layer (§L9) calls once before committing.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class PaymentsAdapter:
    def __init__(self, db: Session):
        self.db = db

    def get_transaction(self, txn_id: str) -> dict[str, Any] | None:
        row = self.db.execute(text("SELECT * FROM transactions WHERE txn_id = :id"), {"id": txn_id}).mappings().first()
        return dict(row) if row else None

    def list_transactions(self, customer_ref: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text("SELECT * FROM transactions WHERE customer_ref = :ref ORDER BY timestamp DESC LIMIT :limit"),
            {"ref": customer_ref, "limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    def refund_history_30d(self, customer_ref: str) -> float:
        """Sum of amounts on transactions refunded for this customer in the
        last 30 days — feeds the policy engine's velocity cap (REFUND-POL-5.0)."""
        row = self.db.execute(
            text("""SELECT COALESCE(SUM(amount_inr), 0) AS total FROM transactions
                    WHERE customer_ref = :ref AND status IN ('REFUNDED','PARTIALLY_REFUNDED')
                    AND timestamp >= :since"""),
            {"ref": customer_ref, "since": datetime.now(timezone.utc) - timedelta(days=30)},
        ).mappings().first()
        return float(row["total"]) if row else 0.0

    def get_dispute(self, dispute_id: str) -> dict[str, Any] | None:
        row = self.db.execute(text("SELECT * FROM disputes WHERE dispute_id = :id"), {"id": dispute_id}).mappings().first()
        return dict(row) if row else None

    def list_disputes(self, customer_ref: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text("SELECT * FROM disputes WHERE customer_ref = :ref ORDER BY created_at DESC"), {"ref": customer_ref}
        ).mappings().all()
        return [dict(r) for r in rows]

    def issue_refund(self, txn_id: str, amount_inr: float, *, dry_run: bool = True) -> dict[str, Any]:
        txn = self.get_transaction(txn_id)
        if not txn:
            return {"ok": False, "error": "transaction_not_found"}

        projected_status = "REFUNDED" if amount_inr >= float(txn["amount_inr"]) else "PARTIALLY_REFUNDED"
        result = {
            "ok": True,
            "txn_id": txn_id,
            "refunded_amount_inr": amount_inr,
            "projected_status": projected_status,
            "dry_run": dry_run,
        }
        if not dry_run:
            self.db.execute(
                text("UPDATE transactions SET status = :status WHERE txn_id = :id"),
                {"status": projected_status, "id": txn_id},
            )
        return result

    def retry_payment(self, txn_id: str, *, dry_run: bool = True) -> dict[str, Any]:
        txn = self.get_transaction(txn_id)
        if not txn:
            return {"ok": False, "error": "transaction_not_found"}
        # Deterministic-ish simulation: retries succeed unless the original
        # decline was a hard decline (card expired / bank declined).
        will_succeed = txn["decline_code"] not in ("CARD_EXPIRED", "BANK_DECLINED")
        result = {
            "ok": True,
            "txn_id": txn_id,
            "projected_status": "SUCCESS" if will_succeed else "FAILED",
            "dry_run": dry_run,
        }
        if not dry_run and will_succeed:
            self.db.execute(text("UPDATE transactions SET status = 'SUCCESS' WHERE txn_id = :id"), {"id": txn_id})
        return result
