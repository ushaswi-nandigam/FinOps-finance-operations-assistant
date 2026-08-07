"""L7 — Risk & Policy Engine. The heart of the system (docs/architecture.md
§L7): takes a proposal and returns an authorisation decision. Contains
**zero LLM calls** — pure, deterministic, unit-testable, versioned. This is
what makes the guardrails structurally true rather than merely prompted for:
untrusted ticket/transcript text can produce a *proposal*, never an action —
only this module, reading from the system of record, can authorise one.

Two layers of rule, evaluated in order:
  1. Hard gates — independent of the YAML rules, cannot be overridden by them
     (unknown customer, exceeded budget, verifier reject, low confidence,
     minor/flagged customer, high fraud score, refund velocity cap).
  2. The YAML rule table (services/policy_engine/rules/*.yaml) — the
     per-action tier assignment a business user could plausibly edit.
"""

from pathlib import Path
from typing import Any

import yaml

from services.common.config import settings
from services.common.enums import Outcome, RiskTier
from services.common.schemas import RiskDecision

RULES_DIR = Path(__file__).resolve().parent / "rules"

TIER_APPROVERS: dict[RiskTier, int] = {RiskTier.T0: 0, RiskTier.T1: 0, RiskTier.T2: 1, RiskTier.T3: 2}
OUTCOME_FOR_TIER: dict[RiskTier, Outcome] = {
    RiskTier.T0: Outcome.AUTO_EXECUTE, RiskTier.T1: Outcome.AUTO_EXECUTE,
    RiskTier.T2: Outcome.NEEDS_APPROVAL, RiskTier.T3: Outcome.DUAL_APPROVAL,
}

# Actions that move or waive money, and are therefore subject to the fraud
# score gate and the refund velocity cap.
MONEY_MOVING_ACTIONS = {"issue_refund", "waive_fee"}

# Actions with no financial exposure — exempt from the minor/flagged hard
# gates, which exist specifically to protect money-moving/account actions.
NON_FINANCIAL_ACTIONS = {
    "send_templated_reply", "tag_ticket", "summarize_issue", "lookup_status",
    "create_internal_task", "update_contact_details",
}

VELOCITY_CAP_INR = 10_000.0
FRAUD_SCORE_HOLD_THRESHOLD = 0.7
LOW_CONFIDENCE_THRESHOLD = 0.6

_rules_cache: list[dict[str, Any]] | None = None


def _load_rules() -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for path in sorted(RULES_DIR.glob("*.yaml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        rules.extend(loaded)
    return rules


def get_rules(*, reload: bool = False) -> list[dict[str, Any]]:
    global _rules_cache
    if _rules_cache is None or reload:
        _rules_cache = _load_rules()
    return _rules_cache


def _condition_matches(value: Any, condition: Any) -> bool:
    if not isinstance(condition, dict):
        return value == condition
    for op, target in condition.items():
        if op == "gt" and not (value is not None and value > target):
            return False
        if op == "gte" and not (value is not None and value >= target):
            return False
        if op == "lt" and not (value is not None and value < target):
            return False
        if op == "lte" and not (value is not None and value <= target):
            return False
        if op == "in" and value not in target:
            return False
        if op == "not_in" and value in target:
            return False
        if op == "eq" and value != target:
            return False
    return True


def _rule_matches(rule: dict[str, Any], context: dict[str, Any]) -> bool:
    for field, condition in rule.get("when", {}).items():
        if field not in context or not _condition_matches(context[field], condition):
            return False
    return True


def _decision(
    *, proposal_id: str, case_id: str, tier: RiskTier, outcome: Outcome,
    matched_rules: list[str], reason_plain: str, policy_version: str,
) -> RiskDecision:
    return RiskDecision(
        proposal_id=proposal_id, case_id=case_id, tier=tier, outcome=outcome,
        matched_rules=matched_rules, reason_plain=reason_plain, policy_version=policy_version,
        required_approvers=TIER_APPROVERS[tier], requires_distinct_approvers=(tier == RiskTier.T3),
    )


def authorise(
    *,
    proposal_id: str,
    case_id: str,
    action_type: str,
    amount_inr: float | None = None,
    customer: dict[str, Any] | None,
    fraud_score: float = 0.0,
    refund_30d_inr: float = 0.0,
    agent_confidence: float = 1.0,
    verifier_verdict: str = "PASS",
    tool_calls_used: int = 0,
    max_tool_calls: int = 6,
    revisions: int = 0,
    max_revisions: int = 3,
    cost_inr: float = 0.0,
    cost_budget_inr: float = 5.0,
    policy_version: str | None = None,
) -> RiskDecision:
    """Pure function: same inputs always produce the same decision. Nothing
    in this function reads an LLM output as authority — amounts and
    identities are whatever the caller passed in from the system of record."""
    pv = policy_version or settings.POLICY_VERSION

    def escalate(rule_id: str, reason: str) -> RiskDecision:
        return _decision(
            proposal_id=proposal_id, case_id=case_id, tier=RiskTier.T3, outcome=Outcome.ESCALATE,
            matched_rules=[rule_id], reason_plain=reason, policy_version=pv,
        )

    # --- Hard gates (cannot be overridden by the YAML rule table) ---
    if customer is None:
        return escalate("CUSTOMER-GATE-1", "The event could not be matched to a known customer, so no action can be authorised. Escalating for manual lookup.")

    if verifier_verdict == "REJECT":
        return escalate("VERIFIER-GATE-1", "The Verifier Agent rejected this proposal, so it cannot proceed automatically. Escalating for human review.")

    if agent_confidence < LOW_CONFIDENCE_THRESHOLD:
        return escalate("CONFIDENCE-GATE-1", f"Agent confidence ({agent_confidence:.2f}) is below the {LOW_CONFIDENCE_THRESHOLD} threshold, so this is escalated rather than auto-executed or approved.")

    if tool_calls_used > max_tool_calls or revisions > max_revisions:
        return escalate("BUDGET-GATE-1", "This case exceeded its reasoning budget (tool calls or plan revisions), so it is escalated rather than continued.")

    if cost_inr > cost_budget_inr:
        return escalate("BUDGET-GATE-1", f"This case's LLM cost (₹{cost_inr:.2f}) exceeded its budget (₹{cost_budget_inr:.2f}), so it is escalated rather than continued.")

    # --- Baseline tier from the YAML rule table ---
    context = {
        "action": action_type,
        "amount_inr": amount_inr,
        "customer_tier": customer.get("tier"),
        "kyc_status": customer.get("kyc_status"),
    }
    matched_rule: dict[str, Any] | None = None
    for rule in get_rules():
        if _rule_matches(rule, context):
            matched_rule = rule
            break

    if matched_rule is None:
        return escalate("NO-MATCHING-RULE", f"No policy rule matches action '{action_type}' with the given context, so this is escalated as out-of-policy.")

    tier = RiskTier(matched_rule["tier"])
    outcome = Outcome(matched_rule["then"])
    matched_rules = [matched_rule["id"]]
    reason_plain = matched_rule["reason"]

    # --- Minor / flagged customer: force T3 for any financial action ---
    if action_type not in NON_FINANCIAL_ACTIONS and customer.get("is_minor"):
        tier, outcome = RiskTier.T3, Outcome.DUAL_APPROVAL
        matched_rules.append("MINOR-GATE-1")
        reason_plain = "This customer's account is flagged as belonging to a minor, so every financial action requires dual approval, regardless of the base policy tier."

    elif action_type not in NON_FINANCIAL_ACTIONS and customer.get("is_flagged"):
        tier, outcome = RiskTier.T3, Outcome.DUAL_APPROVAL
        matched_rules.append("FLAGGED-GATE-1")
        reason_plain = "This customer is flagged for investigation, so every financial action requires dual approval, regardless of the base policy tier."

    # --- Fraud score gate: no auto-execute of money-moving actions above threshold ---
    if action_type in MONEY_MOVING_ACTIONS and fraud_score > FRAUD_SCORE_HOLD_THRESHOLD and outcome == Outcome.AUTO_EXECUTE:
        tier, outcome = RiskTier.T2, Outcome.NEEDS_APPROVAL
        matched_rules += ["FRAUD-POL-2.1", "FRAUD-GATE-1"]
        reason_plain = f"This transaction's fraud risk score ({fraud_score:.2f}) exceeds {FRAUD_SCORE_HOLD_THRESHOLD}, so no money-moving action may auto-execute regardless of amount; routed for single ops approval."

    # --- Refund velocity cap ---
    if action_type == "issue_refund" and outcome == Outcome.AUTO_EXECUTE:
        projected_30d_total = refund_30d_inr + (amount_inr or 0.0)
        if projected_30d_total > VELOCITY_CAP_INR:
            tier, outcome = RiskTier.T2, Outcome.NEEDS_APPROVAL
            matched_rules += ["REFUND-POL-5.0", "VELOCITY-CAP-1"]
            reason_plain = (f"Auto-executing this refund would bring this customer's 30-day auto-refund total to "
                             f"₹{projected_30d_total:,.2f}, above the ₹{VELOCITY_CAP_INR:,.0f} velocity cap; routed for single ops approval.")

    return _decision(
        proposal_id=proposal_id, case_id=case_id, tier=tier, outcome=outcome,
        matched_rules=matched_rules, reason_plain=reason_plain, policy_version=pv,
    )
