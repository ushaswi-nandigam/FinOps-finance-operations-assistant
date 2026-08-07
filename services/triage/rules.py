"""L3 Stage 0 — deterministic rules. ~35% of volume, ₹0 cost
(docs/architecture.md §L3). Whatever this stage can decide with certainty
never reaches a model at all."""

import re

from services.common.enums import Domain
from services.triage.schemas import TriageResult

# Intent -> domain routing, shared with the T1 classifier stage.
INTENT_DOMAIN: dict[str, Domain] = {
    "refund_status_query": Domain.SUPPORT,
    "failed_transaction_refund": Domain.PAYMENTS,
    "fee_waiver_request": Domain.PAYMENTS,
    "unrecognised_charge": Domain.FRAUD,
    "kyc_verification_status": Domain.SUPPORT,
    "account_freeze_appeal": Domain.FRAUD,
    "card_unblock_request": Domain.PAYMENTS,
    "chargeback_dispute": Domain.PAYMENTS,
    "disputed_subscription_renewal": Domain.PAYMENTS,
    "cashback_not_credited": Domain.PAYMENTS,
    "limit_enhancement_request": Domain.INTERNAL_OPS,
    "update_contact_details": Domain.SUPPORT,
}

HIGH_URGENCY_INTENTS = {"account_freeze_appeal", "chargeback_dispute", "unrecognised_charge"}

_KYC_RE = re.compile(r"\bKYC\b", re.IGNORECASE)
# Deliberately does NOT match "unblock" — "please unblock my card" is
# card_unblock_request (payments), not an account freeze appeal (fraud);
# only "account" + "frozen/freeze" together should short-circuit here.
_FREEZE_RE = re.compile(r"\baccount\b.{0,30}\b(froze|frozen|freeze)\b", re.IGNORECASE)
_DECLINE_CODES = {"INSUFFICIENT_FUNDS", "CARD_EXPIRED", "GATEWAY_TIMEOUT", "BANK_DECLINED"}


def urgency_for(intent: str, entities: dict) -> str:
    if intent in HIGH_URGENCY_INTENTS:
        return "high"
    amounts = entities.get("amounts_inr") or []
    if amounts and max(amounts) > 10_000:
        return "high"
    return "medium"


def apply_rules(source: str, redacted_text: str, entities: dict) -> TriageResult | None:
    """Returns a TriageResult for cases stage 0 can decide outright, or None
    to fall through to the classifier."""
    if source == "internal_ops":
        return TriageResult(intent="internal_ops_request", domain=Domain.INTERNAL_OPS, confidence=1.0,
                             urgency="medium", extracted_slots=entities, route_stage="T0_RULES")

    if source == "payment_event":
        text = redacted_text.upper()
        for code in _DECLINE_CODES:
            if code in text:
                return TriageResult(intent="failed_transaction_refund", domain=Domain.PAYMENTS, confidence=1.0,
                                     urgency="medium", extracted_slots={**entities, "decline_code": code},
                                     route_stage="T0_RULES")
        return TriageResult(intent="payment_status_update", domain=Domain.PAYMENTS, confidence=1.0,
                             urgency="low", extracted_slots=entities, route_stage="T0_RULES")

    if source == "dispute":
        return TriageResult(intent="chargeback_dispute", domain=Domain.PAYMENTS, confidence=1.0,
                             urgency="high", extracted_slots=entities, route_stage="T0_RULES")

    if _FREEZE_RE.search(redacted_text):
        return TriageResult(intent="account_freeze_appeal", domain=Domain.FRAUD, confidence=0.95,
                             urgency="high", extracted_slots=entities, route_stage="T0_RULES")

    if _KYC_RE.search(redacted_text):
        return TriageResult(intent="kyc_verification_status", domain=Domain.SUPPORT, confidence=0.9,
                             urgency="medium", extracted_slots=entities, route_stage="T0_RULES")

    return None
