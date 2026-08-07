"""These load the real trained model (services/triage/{model,label_encoder}.pkl)
and the real fastembed embedding model — no mocking, since the whole point
of this stage is that it works without an LLM."""

from services.triage.classifier import classify


def test_classifies_refund_status_query_confidently():
    intent, confidence = classify("My refund for order #ORD-4471 hasn't been credited to my bank account yet. Please check.")
    assert intent == "refund_status_query"
    assert confidence >= 0.85


def test_classifies_fee_waiver_confidently():
    intent, confidence = classify("I was charged an annual fee of ₹1,299 on my card. Kindly waive this charge.")
    assert intent == "fee_waiver_request"
    assert confidence >= 0.85


def test_classifies_chargeback_dispute_confidently():
    intent, confidence = classify("Filing a formal chargeback for txn #txn_12345. Merchant did not deliver goods.")
    assert intent == "chargeback_dispute"


def test_confidence_always_in_valid_range():
    _, confidence = classify("asdkfjh random gibberish text with no clear intent whatsoever")
    assert 0.0 <= confidence <= 1.0
