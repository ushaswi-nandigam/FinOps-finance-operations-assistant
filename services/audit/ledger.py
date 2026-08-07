"""L10 — Audit, Explainability & Cost Ledger.

Append-only, hash-chained: `entry_hash = sha256(prev_hash + canonical_json(entry))`.
Tamper-evident without a blockchain (docs/architecture.md §L10). The chain is
global (every decision across every case links to the previous one, in
insertion order) so a single verification pass proves the *entire* ledger is
intact, not just one case's slice of it.

Two things this module is deliberately strict about, because the brief singles
them out:
  - Escalations are written with identical rigour to executed actions (same
    function, same hash chain — there is no separate, lesser code path).
  - `reason_plain` is generated once by the caller and stored verbatim here;
    this module never regenerates or rewrites it, so the audited explanation
    can never drift from whatever text a human or export later reads.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.common.ids import generate_id
from services.common.schemas import ActorRecord, CostRecord, DecisionRecord

GENESIS_HASH = "0" * 64


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))


def _latest_entry_hash(db: Session) -> str:
    row = db.execute(text("SELECT entry_hash FROM decision_records ORDER BY seq DESC LIMIT 1")).mappings().first()
    return row["entry_hash"] if row else GENESIS_HASH


def _next_case_seq(db: Session, case_id: str) -> int:
    row = db.execute(
        text("SELECT COALESCE(MAX(case_seq), 0) AS m FROM decision_records WHERE case_id = :case_id"),
        {"case_id": case_id},
    ).mappings().first()
    return (row["m"] or 0) + 1


def record_decision(
    db: Session,
    *,
    case_id: str,
    actor: ActorRecord,
    action: dict[str, Any],
    outcome: str,
    reason_plain: str,
    evidence: list[dict[str, Any]] | None = None,
    matched_rules: list[str] | None = None,
    verifier: dict[str, Any] | None = None,
    cost: CostRecord | None = None,
    policy_version: str,
) -> DecisionRecord:
    """The single write path for every decision AND every escalation. There
    is no separate, lighter-weight path for "we chose not to act" — that is
    exactly what the brief requires and exactly where teams cut corners."""
    decision_id = generate_id("dec")
    case_seq = _next_case_seq(db, case_id)
    timestamp = datetime.now(timezone.utc)
    cost = cost or CostRecord(stage="none")
    evidence = evidence or []
    matched_rules = matched_rules or []
    verifier = verifier or {}

    prev_hash = _latest_entry_hash(db)
    # MySQL DATETIME(6) round-trips microseconds but not tzinfo, so the hash
    # is computed over the naive-UTC isoformat — the same string both when
    # writing here and when recomputing in verify_chain from a freshly
    # queried row.
    hashable_entry = {
        "decision_id": decision_id, "case_id": case_id, "case_seq": case_seq,
        "timestamp": timestamp.replace(tzinfo=None).isoformat(), "actor": actor.model_dump(),
        "action": action, "outcome": outcome, "reason_plain": reason_plain,
        "evidence": evidence, "matched_rules": matched_rules, "verifier": verifier,
        "cost": cost.model_dump(), "policy_version": policy_version, "prev_hash": prev_hash,
    }
    entry_hash = hashlib.sha256((prev_hash + _canonical_json(hashable_entry)).encode("utf-8")).hexdigest()

    db.execute(
        text("""INSERT INTO decision_records
            (decision_id, case_id, case_seq, timestamp, actor_type, actor_name, actor_model, actor_version,
             action, outcome, reason_plain, evidence, matched_rules, verifier,
             cost_stage, cost_tokens_in, cost_tokens_out, cost_inr, policy_version, prev_hash, entry_hash)
            VALUES (:decision_id, :case_id, :case_seq, :timestamp, :actor_type, :actor_name, :actor_model, :actor_version,
                    :action, :outcome, :reason_plain, :evidence, :matched_rules, :verifier,
                    :cost_stage, :cost_tokens_in, :cost_tokens_out, :cost_inr, :policy_version, :prev_hash, :entry_hash)"""),
        {
            "decision_id": decision_id, "case_id": case_id, "case_seq": case_seq, "timestamp": timestamp,
            "actor_type": actor.type, "actor_name": actor.name, "actor_model": actor.model, "actor_version": actor.version,
            "action": json.dumps(action, default=str), "outcome": outcome, "reason_plain": reason_plain,
            "evidence": json.dumps(evidence, default=str), "matched_rules": json.dumps(matched_rules),
            "verifier": json.dumps(verifier, default=str), "cost_stage": cost.stage,
            "cost_tokens_in": cost.tokens_in, "cost_tokens_out": cost.tokens_out, "cost_inr": cost.inr,
            "policy_version": policy_version, "prev_hash": prev_hash, "entry_hash": entry_hash,
        },
    )

    return DecisionRecord(
        decision_id=decision_id, case_id=case_id, seq=case_seq, timestamp=timestamp, actor=actor,
        action=action, outcome=outcome, reason_plain=reason_plain, evidence=evidence,
        matched_rules=matched_rules, verifier=verifier, cost=cost, policy_version=policy_version,
        prev_hash=prev_hash, entry_hash=entry_hash,
    )


def get_case_decisions(db: Session, case_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        text("SELECT * FROM decision_records WHERE case_id = :case_id ORDER BY case_seq ASC"), {"case_id": case_id}
    ).mappings().all()
    return [dict(r) for r in rows]


def verify_chain(db: Session) -> dict[str, Any]:
    """Recomputes every entry_hash in insertion order and confirms it matches
    both the stored value and the next row's prev_hash. O(n) over the whole
    ledger — fine at hackathon-demo volume, and exactly what an auditor
    would want to be able to run."""
    rows = db.execute(text("SELECT * FROM decision_records ORDER BY seq ASC")).mappings().all()
    expected_prev = GENESIS_HASH
    for row in rows:
        d = dict(row)
        if d["prev_hash"] != expected_prev:
            return {"valid": False, "broken_at_seq": d["seq"], "reason": "prev_hash does not match previous entry_hash"}
        hashable_entry = {
            "decision_id": d["decision_id"], "case_id": d["case_id"], "case_seq": d["case_seq"],
            "timestamp": d["timestamp"].isoformat() if hasattr(d["timestamp"], "isoformat") else d["timestamp"],
            "actor": {"type": d["actor_type"], "name": d["actor_name"], "model": d["actor_model"], "version": d["actor_version"]},
            "action": json.loads(d["action"]) if isinstance(d["action"], str) else d["action"],
            "outcome": d["outcome"], "reason_plain": d["reason_plain"],
            "evidence": json.loads(d["evidence"]) if isinstance(d["evidence"], str) else d["evidence"],
            "matched_rules": json.loads(d["matched_rules"]) if isinstance(d["matched_rules"], str) else d["matched_rules"],
            "verifier": json.loads(d["verifier"]) if isinstance(d["verifier"], str) else d["verifier"],
            "cost": {"stage": d["cost_stage"], "tokens_in": d["cost_tokens_in"], "tokens_out": d["cost_tokens_out"], "inr": float(d["cost_inr"])},
            "policy_version": d["policy_version"], "prev_hash": d["prev_hash"],
        }
        recomputed = hashlib.sha256((d["prev_hash"] + _canonical_json(hashable_entry)).encode("utf-8")).hexdigest()
        if recomputed != d["entry_hash"]:
            return {"valid": False, "broken_at_seq": d["seq"], "reason": "entry_hash does not match recomputed hash — record may have been tampered with"}
        expected_prev = d["entry_hash"]
    return {"valid": True, "entries_checked": len(rows)}
