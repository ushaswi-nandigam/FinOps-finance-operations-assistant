"""Aggregations for the Cost & Impact Dashboard screen (docs/architecture.md
§L11). Computed directly from the audit ledger / cases table rather than a
separate metrics store — at hackathon-demo volume a few GROUP BY queries are
plenty, and it guarantees the dashboard can never drift from the ledger it's
summarising.
"""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def summary(db: Session) -> dict[str, Any]:
    cases = db.execute(text("SELECT status, domain, triage_stage, cost_inr, risk_decision FROM cases")).mappings().all()

    total_cases = len(cases)
    by_status: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    by_route_stage: dict[str, int] = {}
    by_tier: dict[str, dict[str, float]] = {}
    total_cost = 0.0
    auto_resolved = 0
    terminal = 0

    for c in cases:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
        by_domain[c["domain"]] = by_domain.get(c["domain"], 0) + 1
        if c["triage_stage"]:
            by_route_stage[c["triage_stage"]] = by_route_stage.get(c["triage_stage"], 0) + 1
        total_cost += float(c["cost_inr"])

        risk_decision = c["risk_decision"]
        if isinstance(risk_decision, str):
            risk_decision = json.loads(risk_decision) if risk_decision else {}
        tier = (risk_decision or {}).get("tier")
        if tier:
            bucket = by_tier.setdefault(tier, {"count": 0, "total_cost_inr": 0.0})
            bucket["count"] += 1
            bucket["total_cost_inr"] += float(c["cost_inr"])

        if c["status"] in ("RESOLVE", "ESCALATE"):
            terminal += 1
            if c["status"] == "RESOLVE" and (risk_decision or {}).get("outcome") == "AUTO_EXECUTE":
                auto_resolved += 1

    approvals = db.execute(text("SELECT status FROM approvals WHERE status != 'PENDING'")).mappings().all()
    decided = len(approvals)
    overridden = sum(1 for a in approvals if a["status"] in ("REJECTED", "SENT_BACK", "MODIFIED"))

    # Naive baseline: what every case would have cost if every decision had
    # gone through the frontier tier instead of the cascade — this is the
    # number the "cost cascade" story is measured against.
    frontier_rate = 0.06 / 1000 * 1500 + 0.25 / 1000 * 400  # a rough single-call estimate, see services/common/cost.py
    naive_baseline_cost = total_cases * frontier_rate

    return {
        "total_cases": total_cases,
        "by_status": by_status,
        "by_domain": by_domain,
        "by_route_stage": by_route_stage,
        "by_tier": by_tier,
        "blended_cost_per_decision_inr": round(total_cost / total_cases, 4) if total_cases else 0.0,
        "naive_all_frontier_cost_per_decision_inr": round(frontier_rate, 4),
        "cost_savings_pct": round((1 - (total_cost / total_cases) / frontier_rate) * 100, 1) if total_cases and frontier_rate else 0.0,
        "auto_resolution_rate_pct": round(auto_resolved / terminal * 100, 1) if terminal else 0.0,
        "approval_override_rate_pct": round(overridden / decided * 100, 1) if decided else 0.0,
        "total_blended_cost_inr": round(total_cost, 4),
    }
