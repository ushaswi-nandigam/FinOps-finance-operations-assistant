from services.common.enums import Domain
from services.triage.rules import apply_rules


def test_internal_ops_source_always_t0():
    r = apply_rules("internal_ops", "Onboard new merchant MerchantX", {})
    assert r is not None
    assert r.domain == Domain.INTERNAL_OPS
    assert r.route_stage == "T0_RULES"
    assert r.confidence == 1.0


def test_payment_event_with_decline_code_t0():
    r = apply_rules("payment_event", "Payment event for txn txn_1: status=FAILED, decline_code=CARD_EXPIRED, amount=₹100", {})
    assert r is not None
    assert r.intent == "failed_transaction_refund"
    assert r.domain == Domain.PAYMENTS
    assert r.route_stage == "T0_RULES"


def test_payment_event_without_decline_code_falls_to_generic_t0():
    r = apply_rules("payment_event", "Payment event for txn txn_1: status=SUCCESS, decline_code=NONE, amount=₹100", {})
    assert r is not None
    assert r.intent == "payment_status_update"


def test_dispute_source_always_t0_high_urgency():
    r = apply_rules("dispute", "Dispute dsp_1 on txn txn_1: reason=GOODS_NOT_RECEIVED, amount=₹500", {})
    assert r is not None
    assert r.urgency == "high"


def test_account_freeze_detected_by_keyword():
    r = apply_rules("support_ticket", "My account was frozen unexpectedly. Please review and unblock my wallet.", {})
    assert r is not None
    assert r.intent == "account_freeze_appeal"
    assert r.domain == Domain.FRAUD


def test_card_unblock_not_misrouted_as_freeze():
    """'unblock' alone must not trigger the account-freeze rule — this
    ticket is a routine card unblock, not a fraud hold appeal."""
    r = apply_rules("support_ticket", "My debit card ending in 4321 was blocked due to wrong PIN. Please unblock it.", {})
    assert r is None  # falls through to the classifier, not misrouted here


def test_kyc_keyword_detected():
    r = apply_rules("support_ticket", "What is the status of my KYC re-verification?", {})
    assert r is not None
    assert r.intent == "kyc_verification_status"


def test_no_rule_matches_returns_none():
    r = apply_rules("support_ticket", "I would like to update my mailing address please.", {})
    assert r is None
