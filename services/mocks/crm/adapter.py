"""mock-crm — customer profile, tier, KYC status, contact history.

A typed adapter class rather than a standalone MCP server/microservice
(architecture.md §L6 explicitly allows this "time is short" option). Every
domain agent talks to enterprise systems only through adapters like this one
— never directly to the database — so swapping in a real CRM later only
touches this file.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class CRMAdapter:
    def __init__(self, db: Session):
        self.db = db

    def get_customer(self, customer_ref: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM customers WHERE customer_ref = :ref"), {"ref": customer_ref}
        ).mappings().first()
        return dict(row) if row else None

    def list_tickets(self, customer_ref: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text("SELECT * FROM tickets WHERE customer_ref = :ref ORDER BY created_at DESC LIMIT :limit"),
            {"ref": customer_ref, "limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM tickets WHERE ticket_id = :id"), {"id": ticket_id}
        ).mappings().first()
        return dict(row) if row else None

    def list_transcripts(self, customer_ref: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text("SELECT * FROM transcripts WHERE customer_ref = :ref ORDER BY created_at DESC"),
            {"ref": customer_ref},
        ).mappings().all()
        return [dict(r) for r in rows]

    def update_contact_details(self, customer_ref: str, email: str | None, phone: str | None) -> dict[str, Any]:
        """T0 action — read-mutation of low-risk contact fields only."""
        fields, params = [], {"ref": customer_ref}
        if email:
            fields.append("email = :email")
            params["email"] = email
        if phone:
            fields.append("phone = :phone")
            params["phone"] = phone
        if fields:
            self.db.execute(text(f"UPDATE customers SET {', '.join(fields)} WHERE customer_ref = :ref"), params)
        return self.get_customer(customer_ref) or {}
