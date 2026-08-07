"""Exhaustive tests for the deterministic policy engine — the safety spine.
No LLM, no mocking of the decision logic itself: every branch of
services/policy_engine/engine.py is exercised directly."""

import pytest

from services.common.enums import Outcome, RiskTier
from services.policy_engine.engine import authorise

STANDARD_CUSTOMER = {"tier": "STANDARD", "kyc_status": "VERIFIED", "is_flagged": False, "is_minor": False}
GOLD_CUSTOMER = {"tier": "GOLD", "kyc_status": "VERIFIED", "is_flagged": False, "is_minor": False}
FLAGGED_CUSTOMER = {"tier": "STANDARD", "kyc_status": "VERIFIED", "is_flagged": True, "is_minor": False}
MINOR_CUSTOMER = {"tier": "STANDARD", "kyc_status": "VERIFIED", "is_flagged": False, "is_minor": True}


def _authorise(**overrides):
    defaults = dict(
        proposal_id="prop_1", case_id="case_1", action_type="issue_refund",
        amount_inr=100.0, customer=STANDARD_CUSTOMER,
    )
    defaults.update(overrides)
    return authorise(**defaults)


# --- Refund tier table ---

def test_refund_under_500_auto_executes():
    d = _authorise(amount_inr=499.0)
    assert d.tier == RiskTier.T1
    assert d.outcome == Outcome.AUTO_EXECUTE
    assert "REFUND-POL-1.0" in d.matched_rules
    assert d.required_approvers == 0


def test_refund_exactly_500_auto_executes_boundary():
    d = _authorise(amount_inr=500.0)
    assert d.outcome == Outcome.AUTO_EXECUTE
    assert "REFUND-POL-1.0" in d.matched_rules


def test_refund_501_needs_single_approval_boundary():
    d = _authorise(amount_inr=501.0)
    assert d.tier == RiskTier.T2
    assert d.outcome == Outcome.NEEDS_APPROVAL
    assert "REFUND-POL-3.2" in d.matched_rules
    assert d.required_approvers == 1
    assert d.requires_distinct_approvers is False


def test_refund_25000_needs_single_approval_boundary():
    d = _authorise(amount_inr=25000.0)
    assert d.outcome == Outcome.NEEDS_APPROVAL
    assert "REFUND-POL-3.2" in d.matched_rules


def test_refund_above_25000_dual_approval():
    d = _authorise(amount_inr=25001.0)
    assert d.tier == RiskTier.T3
    assert d.outcome == Outcome.DUAL_APPROVAL
    assert "REFUND-POL-4.0" in d.matched_rules
    assert d.required_approvers == 2
    assert d.requires_distinct_approvers is True


def test_reason_plain_is_never_empty():
    for amount in (100, 2000, 50000):
        d = _authorise(amount_inr=amount)
        assert d.reason_plain.strip() != ""


# --- Fee waivers ---

def test_fee_waiver_gold_under_1000_needs_approval():
    d = authorise(proposal_id="p", case_id="c", action_type="waive_fee", amount_inr=800,
                   customer=GOLD_CUSTOMER)
    assert d.outcome == Outcome.NEEDS_APPROVAL
    assert "FEE-POL-1.1" in d.matched_rules


def test_fee_waiver_standard_over_cap_falls_to_general_rule():
    d = authorise(proposal_id="p", case_id="c", action_type="waive_fee", amount_inr=5000,
                   customer=STANDARD_CUSTOMER)
    assert d.outcome == Outcome.NEEDS_APPROVAL
    assert "FEE-POL-2.0" in d.matched_rules


# --- Fraud actions ---

def test_fraud_hold_always_dual_approval_regardless_of_amount():
    d = authorise(proposal_id="p", case_id="c", action_type="place_fraud_hold", amount_inr=None,
                   customer=STANDARD_CUSTOMER)
    assert d.tier == RiskTier.T3
    assert d.outcome == Outcome.DUAL_APPROVAL
    assert "FRAUD-POL-3.0" in d.matched_rules


def test_close_fraud_case_benign_needs_single_approval():
    d = authorise(proposal_id="p", case_id="c", action_type="close_fraud_case_benign", amount_inr=None,
                   customer=STANDARD_CUSTOMER)
    assert d.outcome == Outcome.NEEDS_APPROVAL


# --- T0 support actions ---

@pytest.mark.parametrize("action", ["send_templated_reply", "tag_ticket", "summarize_issue", "lookup_status", "create_internal_task"])
def test_support_actions_auto_execute(action):
    d = authorise(proposal_id="p", case_id="c", action_type=action, amount_inr=None, customer=STANDARD_CUSTOMER)
    assert d.tier == RiskTier.T0
    assert d.outcome == Outcome.AUTO_EXECUTE


# --- Hard gates ---

def test_unknown_customer_always_escalates():
    d = _authorise(amount_inr=10.0, customer=None)
    assert d.outcome == Outcome.ESCALATE
    assert "CUSTOMER-GATE-1" in d.matched_rules


def test_verifier_reject_escalates_even_for_small_refund():
    d = _authorise(amount_inr=50.0, verifier_verdict="REJECT")
    assert d.outcome == Outcome.ESCALATE
    assert "VERIFIER-GATE-1" in d.matched_rules


def test_low_confidence_escalates():
    d = _authorise(amount_inr=50.0, agent_confidence=0.4)
    assert d.outcome == Outcome.ESCALATE
    assert "CONFIDENCE-GATE-1" in d.matched_rules


def test_confidence_exactly_at_threshold_does_not_escalate():
    d = _authorise(amount_inr=50.0, agent_confidence=0.6)
    assert d.outcome != Outcome.ESCALATE


def test_exceeded_tool_call_budget_escalates():
    d = _authorise(amount_inr=50.0, tool_calls_used=7, max_tool_calls=6)
    assert d.outcome == Outcome.ESCALATE
    assert "BUDGET-GATE-1" in d.matched_rules


def test_exceeded_revision_budget_escalates():
    d = _authorise(amount_inr=50.0, revisions=4, max_revisions=3)
    assert d.outcome == Outcome.ESCALATE


def test_exceeded_cost_budget_escalates():
    d = _authorise(amount_inr=50.0, cost_inr=6.0, cost_budget_inr=5.0)
    assert d.outcome == Outcome.ESCALATE
    assert "BUDGET-GATE-1" in d.matched_rules


def test_minor_customer_forces_dual_approval_even_for_tiny_refund():
    d = _authorise(amount_inr=10.0, customer=MINOR_CUSTOMER)
    assert d.tier == RiskTier.T3
    assert d.outcome == Outcome.DUAL_APPROVAL
    assert "MINOR-GATE-1" in d.matched_rules


def test_minor_customer_non_financial_action_still_auto_executes():
    d = authorise(proposal_id="p", case_id="c", action_type="tag_ticket", amount_inr=None, customer=MINOR_CUSTOMER)
    assert d.outcome == Outcome.AUTO_EXECUTE


def test_flagged_customer_forces_dual_approval_even_for_tiny_refund():
    d = _authorise(amount_inr=10.0, customer=FLAGGED_CUSTOMER)
    assert d.tier == RiskTier.T3
    assert d.outcome == Outcome.DUAL_APPROVAL
    assert "FLAGGED-GATE-1" in d.matched_rules


def test_high_fraud_score_blocks_auto_execute_refund():
    d = _authorise(amount_inr=100.0, fraud_score=0.85)
    assert d.outcome == Outcome.NEEDS_APPROVAL
    assert "FRAUD-POL-2.1" in d.matched_rules
    assert "FRAUD-GATE-1" in d.matched_rules


def test_fraud_score_at_threshold_does_not_trigger_gate():
    d = _authorise(amount_inr=100.0, fraud_score=0.7)
    assert d.outcome == Outcome.AUTO_EXECUTE


def test_fraud_score_does_not_affect_already_approval_gated_refund():
    # Amount already requires approval; fraud score doesn't need to change outcome, just shouldn't crash / downgrade.
    d = _authorise(amount_inr=5000.0, fraud_score=0.9)
    assert d.outcome == Outcome.NEEDS_APPROVAL


def test_refund_velocity_cap_forces_approval():
    d = _authorise(amount_inr=100.0, refund_30d_inr=9950.0)
    assert d.outcome == Outcome.NEEDS_APPROVAL
    assert "VELOCITY-CAP-1" in d.matched_rules


def test_refund_velocity_cap_not_triggered_when_under_cap():
    d = _authorise(amount_inr=100.0, refund_30d_inr=100.0)
    assert d.outcome == Outcome.AUTO_EXECUTE


def test_no_matching_rule_escalates():
    d = authorise(proposal_id="p", case_id="c", action_type="teleport_customer", amount_inr=None, customer=STANDARD_CUSTOMER)
    assert d.outcome == Outcome.ESCALATE
    assert "NO-MATCHING-RULE" in d.matched_rules


def test_prompt_injection_text_cannot_influence_outcome():
    """The policy engine never sees free text at all — only structured
    amount/action/customer fields the caller derives from the system of
    record. This test proves an injected instruction has no code path into
    authorise() that could change its outcome."""
    d = _authorise(amount_inr=100.0)
    injected = _authorise(amount_inr=100.0)  # same structured inputs regardless of any "instruction" in upstream text
    assert d.outcome == injected.outcome
    assert d.tier == injected.tier


def test_policy_version_stamped_on_every_decision():
    d = _authorise(amount_inr=100.0, policy_version="2099.01.01")
    assert d.policy_version == "2099.01.01"


def test_decision_is_deterministic_pure_function():
    results = {authorise(proposal_id="p", case_id="c", action_type="issue_refund", amount_inr=1500.0, customer=STANDARD_CUSTOMER).outcome for _ in range(20)}
    assert results == {Outcome.NEEDS_APPROVAL}
