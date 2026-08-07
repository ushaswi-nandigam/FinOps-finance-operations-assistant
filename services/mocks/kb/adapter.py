"""mock-kb — policy clauses + SOPs. Read-only; the Compliance Agent's only
tool. Vector search lives in services/orchestrator/agents/compliance.py
(cosine similarity over services/triage's fastembed vectors) since a 25-clause
corpus doesn't need a vector database — see docs/LEARN.md.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class KBAdapter:
    def __init__(self, db: Session):
        self.db = db

    def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        row = self.db.execute(text("SELECT * FROM policies WHERE id = :id"), {"id": policy_id}).mappings().first()
        return dict(row) if row else None

    def list_policies(self, category: str | None = None) -> list[dict[str, Any]]:
        if category:
            rows = self.db.execute(text("SELECT * FROM policies WHERE category = :cat"), {"cat": category}).mappings().all()
        else:
            rows = self.db.execute(text("SELECT * FROM policies")).mappings().all()
        return [dict(r) for r in rows]

    def list_sops(self, category: str | None = None) -> list[dict[str, Any]]:
        if category:
            rows = self.db.execute(text("SELECT * FROM sops WHERE category = :cat"), {"cat": category}).mappings().all()
        else:
            rows = self.db.execute(text("SELECT * FROM sops")).mappings().all()
        return [dict(r) for r in rows]
