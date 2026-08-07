"""mock-casemgmt — fraud cases, investigation notes, internal ops workflows.

Distinct from services/orchestrator's `cases` table (an agent case/state
machine row): this is the enterprise "case management system" the Fraud and
Internal Ops agents read from and write to, exactly as they would a real one.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class CaseMgmtAdapter:
    def __init__(self, db: Session):
        self.db = db

    def get_fraud_case_by_txn(self, txn_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM fraud_cases WHERE txn_id = :id ORDER BY created_at DESC LIMIT 1"), {"id": txn_id}
        ).mappings().first()
        return dict(row) if row else None

    def list_fraud_cases(self, customer_ref: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text("SELECT * FROM fraud_cases WHERE customer_ref = :ref ORDER BY created_at DESC"), {"ref": customer_ref}
        ).mappings().all()
        return [dict(r) for r in rows]

    def close_fraud_case(self, fraud_case_id: str, status: str, *, dry_run: bool = True) -> dict[str, Any]:
        result = {"ok": True, "fraud_case_id": fraud_case_id, "projected_status": status, "dry_run": dry_run}
        if not dry_run:
            self.db.execute(
                text("UPDATE fraud_cases SET status = :status WHERE fraud_case_id = :id"),
                {"status": status, "id": fraud_case_id},
            )
        return result

    def list_workflows(self, category: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if category:
            rows = self.db.execute(
                text("SELECT * FROM internal_ops_workflows WHERE category = :cat ORDER BY created_at DESC LIMIT :limit"),
                {"cat": category, "limit": limit},
            ).mappings().all()
        else:
            rows = self.db.execute(
                text("SELECT * FROM internal_ops_workflows ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}
            ).mappings().all()
        return [dict(r) for r in rows]

    def create_internal_task(self, title: str, description: str, category: str, *, dry_run: bool = True) -> dict[str, Any]:
        from services.common.ids import generate_id

        workflow_id = generate_id("wf")
        result = {"ok": True, "workflow_id": workflow_id, "title": title, "dry_run": dry_run}
        if not dry_run:
            from datetime import datetime, timezone

            self.db.execute(
                text("""INSERT INTO internal_ops_workflows
                    (workflow_id, title, description, category, approval_required, status, created_at)
                    VALUES (:workflow_id, :title, :description, :category, FALSE, 'OPEN', :created_at)"""),
                {
                    "workflow_id": workflow_id, "title": title, "description": description,
                    "category": category, "created_at": datetime.now(timezone.utc),
                },
            )
        return result
