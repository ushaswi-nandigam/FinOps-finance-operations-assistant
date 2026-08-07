"""T2/T3 are mocked here for deterministic, fast unit tests (no network
dependency). tests/integration/test_triage_llm_live.py exercises the real
Gemini call separately."""

from unittest.mock import patch

from services.common.enums import Domain
from services.triage.cascade import triage
from services.triage.schemas import TriageResult


def test_t0_short_circuits_before_classifier():
    with patch("services.triage.cascade.classify") as mock_classify:
        result = triage("internal_ops", "Onboard MerchantX", {})
        mock_classify.assert_not_called()
    assert result.route_stage == "T0_RULES"


def test_t1_classifier_resolves_confident_ticket():
    result = triage("support_ticket", "My refund for order #ORD-4471 hasn't been credited to my bank account yet.", {})
    assert result.route_stage == "T1_CLASSIFIER"
    assert result.intent == "refund_status_query"
    assert result.domain == Domain.SUPPORT


def test_low_confidence_falls_through_to_llm_stage():
    fake_result = TriageResult(intent="fee_waiver_request", domain=Domain.PAYMENTS, confidence=0.9,
                                urgency="medium", extracted_slots={}, route_stage="T2_LLM")
    with patch("services.triage.cascade.classify", return_value=("other", 0.2)):
        with patch("services.triage.cascade.route_with_llm", return_value=fake_result) as mock_llm:
            result = triage("support_ticket", "some ambiguous garbled text zzz", {})
    mock_llm.assert_called_once()
    assert result.route_stage == "T2_LLM"
    assert result.confidence == 0.9


def test_llm_stage_failure_falls_back_to_classifier_guess_not_exception():
    with patch("services.triage.cascade.classify", return_value=("refund_status_query", 0.3)):
        with patch("services.triage.cascade.route_with_llm", side_effect=RuntimeError("network down")):
            result = triage("support_ticket", "ambiguous text", {})
    assert result.route_stage == "T3_LLM_UNAVAILABLE"
    assert result.intent == "refund_status_query"
    assert result.confidence == 0.3


def test_entities_merged_into_extracted_slots_on_t1():
    result = triage("support_ticket", "My refund for order #ORD-4471 hasn't been credited to my bank account yet.",
                     {"order_ids": ["ORD-4471"]})
    assert result.extracted_slots.get("order_ids") == ["ORD-4471"]
