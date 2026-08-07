"""`/audit/export` — the "auditor mode" moment: every decision and escalation
for a case, plus proof the chain segment hasn't been tampered with, signed so
the export itself can't be silently edited after the fact."""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from services.audit.ledger import get_case_decisions, verify_chain
from services.common.config import settings


def _sign(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hmac.new(settings.AUDIT_SIGNING_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def export_case(db: Session, case_id: str) -> dict[str, Any]:
    decisions = get_case_decisions(db, case_id)
    chain_report = verify_chain(db)

    for d in decisions:
        for field in ("action", "evidence", "matched_rules", "verifier"):
            if isinstance(d.get(field), str):
                d[field] = json.loads(d[field])
        if hasattr(d.get("timestamp"), "isoformat"):
            d["timestamp"] = d["timestamp"].isoformat()
        d["cost"] = {
            "stage": d.pop("cost_stage"), "tokens_in": d.pop("cost_tokens_in"),
            "tokens_out": d.pop("cost_tokens_out"), "inr": float(d.pop("cost_inr")),
        }

    payload = {
        "case_id": case_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "decision_count": len(decisions),
        "decisions": decisions,
        "ledger_integrity": chain_report,
    }
    payload["signature"] = _sign(payload)
    return payload


def verify_export_signature(payload: dict[str, Any]) -> bool:
    claimed = payload.get("signature")
    unsigned = {k: v for k, v in payload.items() if k != "signature"}
    return claimed == _sign(unsigned)
