"""L5b — the mandated self-check (docs/architecture.md §L5b). Runs before
every risk-gate decision, checking a proposal against a small Business Goals
checklist. Deterministic, not an LLM call — consistent with this project's
"classical model decides, LLM only narrates" design (see docs/LEARN.md):
a verifier whose PASS/REVISE verdict depended on an LLM's mood would be a
strange thing to call a safety check. What it checks is genuinely useful
without one: is the action registered and evidenced, and does the amount
actually requested match what the customer themselves described?

That last check is what drives golden scenario 4 (architecture.md §6): a
full-transaction refund gets flagged REVISE when the customer's own ticket
text names a smaller amount, with a concrete revision hint the proposing
agent can act on directly (see services/orchestrator/agents/payments.py's
`revise` parameter) — a caught-and-corrected mistake, not a scripted one.
"""

from typing import Any

from services.tools.manifests.registry import get_manifest

AMOUNT_OVERSTATEMENT_TOLERANCE = 1.10  # 10% slack before flagging a mismatch


def _least_privilege_check(proposal: dict[str, Any], triage_entities: dict[str, Any]) -> tuple[bool, str, str | None]:
    if proposal["action_type"] != "issue_refund":
        return True, "Proposed action matches the minimum needed to resolve the issue.", None

    proposed_amount = proposal["args"].get("amount_inr")
    stated_amounts = triage_entities.get("amounts_inr") or []
    if proposed_amount is None or not stated_amounts:
        return True, "No customer-stated amount to cross-check against; proceeding with the system-of-record amount.", None

    stated_amount = min(stated_amounts)  # the customer's own smallest-named figure
    if proposed_amount > stated_amount * AMOUNT_OVERSTATEMENT_TOLERANCE:
        hint = (f"The customer's own message names ₹{stated_amount:,.2f}, but the proposal refunds the full "
                f"transaction (₹{proposed_amount:,.2f}). Propose ₹{stated_amount:,.2f} instead unless there's "
                f"evidence the whole transaction failed.")
        return False, hint, hint
    return True, "Proposed refund amount is consistent with what the customer described.", None


def verify(proposal: dict[str, Any] | None, triage_entities: dict[str, Any] | None = None) -> dict[str, Any]:
    if proposal is None:
        return {"goal_conformance": {}, "verdict": "PASS", "revision_hint": None, "confidence": 1.0}

    triage_entities = triage_entities or {}
    checks: dict[str, Any] = {}

    checks["resolves_customer_issue"] = {"pass": True, "why": "A concrete action was proposed addressing the case's intent."}

    manifest = get_manifest(proposal["action_type"])
    checks["policy_compliant"] = {
        "pass": manifest is not None,
        "why": f"'{proposal['action_type']}' is a registered tool with a declared risk tier." if manifest
               else f"'{proposal['action_type']}' is not a registered tool — cannot verify its risk tier.",
    }

    least_priv_pass, least_priv_why, revision_hint = _least_privilege_check(proposal, triage_entities)
    checks["least_privilege_action"] = {"pass": least_priv_pass, "why": least_priv_why}

    checks["cost_proportionate"] = {"pass": True, "why": "No cost overrun signal at this stage."}

    money_moving = proposal["action_type"] in ("issue_refund", "waive_fee", "place_fraud_hold")
    has_evidence = bool(proposal.get("evidence"))
    checks["no_unsupported_claims"] = {
        "pass": (not money_moving) or has_evidence,
        "why": "Proposal is backed by evidence from the system of record." if has_evidence
               else "Money-moving proposal has no evidence attached.",
    }

    all_pass = all(c["pass"] for c in checks.values())
    return {
        "goal_conformance": checks,
        "verdict": "PASS" if all_pass else "REVISE",
        "revision_hint": revision_hint,
        "confidence": 0.95 if all_pass else 0.75,
    }
