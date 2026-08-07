"""L9 (execution primitives) + L6 (dispatch) in one small module: every
side-effecting tool call goes through `execute_tool`, which is the only
place that (a) checks the manifest, (b) computes and checks the idempotency
key, and (c) writes to `tool_calls`. Agents never call an adapter directly.

Idempotency: `idempotency_key = sha256(case_id + tool_name + canonical_args)`
(docs/architecture.md §L9). Calling the same action twice for the same case
returns the first call's stored result instead of executing again — this is
what makes double-clicking "Approve" safe.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.common.errors import IdempotencyError
from services.mocks.casemgmt import CaseMgmtAdapter
from services.mocks.crm import CRMAdapter
from services.mocks.payments import PaymentsAdapter
from services.tools.manifests.registry import get_manifest


def _idempotency_key(case_id: str, tool_name: str, args: dict[str, Any]) -> str:
    canonical = json.dumps(args, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(f"{case_id}:{tool_name}:{canonical}".encode("utf-8")).hexdigest()


def _handler(tool_name: str, db: Session, args: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    crm, payments, casemgmt = CRMAdapter(db), PaymentsAdapter(db), CaseMgmtAdapter(db)

    if tool_name == "lookup_status":
        customer = crm.get_customer(args["customer_ref"])
        txns = payments.list_transactions(args["customer_ref"], limit=args.get("limit", 5))
        return {"ok": True, "customer": customer, "recent_transactions": txns}
    if tool_name == "send_templated_reply":
        return {"ok": True, "ticket_id": args.get("ticket_id"), "reply_sent": not dry_run, "template": args.get("template")}
    if tool_name == "tag_ticket":
        return {"ok": True, "ticket_id": args.get("ticket_id"), "tag": args.get("tag")}
    if tool_name == "summarize_issue":
        return {"ok": True, "case_id": args.get("case_id"), "summary": args.get("summary")}
    if tool_name == "update_contact_details":
        result = crm.update_contact_details(args["customer_ref"], args.get("email"), args.get("phone"))
        return {"ok": True, "customer": result}
    if tool_name == "create_internal_task":
        return casemgmt.create_internal_task(args["title"], args.get("description", ""), args.get("category", "general"), dry_run=dry_run)

    if tool_name == "retry_payment":
        return payments.retry_payment(args["txn_id"], dry_run=dry_run)
    if tool_name == "issue_refund":
        return payments.issue_refund(args["txn_id"], float(args["amount_inr"]), dry_run=dry_run)
    if tool_name == "waive_fee":
        return {"ok": True, "customer_ref": args["customer_ref"], "waived_amount_inr": args["amount_inr"], "dry_run": dry_run}

    if tool_name in ("place_fraud_hold", "lift_fraud_hold"):
        status = "OPEN" if tool_name == "place_fraud_hold" else "CLOSED_BENIGN"
        return casemgmt.close_fraud_case(args["fraud_case_id"], status, dry_run=dry_run) if tool_name == "lift_fraud_hold" \
            else {"ok": True, "fraud_case_id": args["fraud_case_id"], "hold_placed": not dry_run, "dry_run": dry_run}
    if tool_name == "close_fraud_case_benign":
        return casemgmt.close_fraud_case(args["fraud_case_id"], "CLOSED_BENIGN", dry_run=dry_run)

    if tool_name == "unblock_card":
        return {"ok": True, "customer_ref": args["customer_ref"], "card_unblocked": not dry_run, "dry_run": dry_run}
    if tool_name in ("freeze_account", "unfreeze_account"):
        return {"ok": True, "customer_ref": args["customer_ref"], "frozen": tool_name == "freeze_account" and not dry_run, "dry_run": dry_run}

    raise ValueError(f"no handler registered for tool '{tool_name}'")


def execute_tool(
    db: Session, *, case_id: str, tool_name: str, args: dict[str, Any], dry_run: bool = True,
) -> dict[str, Any]:
    manifest = get_manifest(tool_name)
    if manifest is None:
        raise ValueError(f"unknown tool '{tool_name}' — not in the manifest registry")

    if dry_run and not manifest.dry_run_supported:
        raise ValueError(f"tool '{tool_name}' does not support dry_run")

    # Idempotency only applies to real executions. A dry-run is a projection
    # for the approval card, not a completed action, so it never touches
    # tool_calls — otherwise its idempotency_key (same case+tool+args) would
    # collide with the real execution that follows once a human approves.
    idempotency_key = _idempotency_key(case_id, tool_name, args) if (manifest.requires_idempotency and not dry_run) else None

    if idempotency_key:
        existing = db.execute(
            text("SELECT result, status FROM tool_calls WHERE idempotency_key = :key"), {"key": idempotency_key}
        ).mappings().first()
        if existing:
            result = json.loads(existing["result"]) if isinstance(existing["result"], str) else existing["result"]
            result["idempotent_replay"] = True
            return result

    result = _handler(tool_name, db, args, dry_run=dry_run)

    if idempotency_key:
        try:
            db.execute(
                text("""INSERT INTO tool_calls (case_id, tool_name, idempotency_key, args, dry_run, status, result, created_at)
                    VALUES (:case_id, :tool_name, :key, :args, :dry_run, :status, :result, :created_at)"""),
                {
                    "case_id": case_id, "tool_name": tool_name, "key": idempotency_key,
                    "args": json.dumps(args, default=str), "dry_run": dry_run,
                    "status": "DRY_RUN" if dry_run else ("SUCCESS" if result.get("ok") else "FAILED"),
                    "result": json.dumps(result, default=str), "created_at": datetime.now(timezone.utc),
                },
            )
        except Exception as exc:  # unique constraint race — another call won
            raise IdempotencyError(f"idempotency key collision for {tool_name} on case {case_id}") from exc

    return result
