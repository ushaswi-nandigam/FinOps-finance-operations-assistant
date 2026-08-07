"""L3 — the cheap-first triage cascade (docs/architecture.md §L3). This is
the module that makes the "show a cheap model/classical solver can replace
constant LLM calls" principle concrete: an LLM is only ever reached for the
slice of volume the two free/near-free stages couldn't decide.

    T0 rules (₹0)  ->  T1 classifier (~₹0, no LLM)  ->  T2 gemini-2.0-flash-lite  ->  T3 gemini-2.0-flash

`route_stage` on the result is what the cost dashboard groups by — it is the
whole cost story for the project.
"""

from services.common.config import settings
from services.common.enums import Domain
from services.triage.classifier import classify
from services.triage.llm_router import route_with_llm
from services.triage.rules import INTENT_DOMAIN, apply_rules, urgency_for
from services.triage.schemas import TriageResult

CONFIDENCE_THRESHOLD = 0.85  # calibrated abstention threshold, docs/ai-workflow.md


def triage(source: str, redacted_text: str, entities: dict) -> TriageResult:
    rule_result = apply_rules(source, redacted_text, entities)
    if rule_result is not None:
        return rule_result

    intent, confidence = classify(redacted_text)
    domain = INTENT_DOMAIN.get(intent, Domain.SUPPORT)
    if confidence >= CONFIDENCE_THRESHOLD:
        return TriageResult(intent=intent, domain=domain, confidence=confidence,
                             urgency=urgency_for(intent, entities), extracted_slots=entities,
                             route_stage="T1_CLASSIFIER")

    for stage_name, model_name in (("T2_LLM", settings.MODEL_TIER_MID), ("T3_LLM", settings.MODEL_TIER_FRONTIER)):
        try:
            result = route_with_llm(redacted_text, model_name=model_name, hint_intent=intent, hint_confidence=confidence)
        except Exception:
            continue
        result.route_stage = stage_name
        result.extracted_slots = {**entities, **result.extracted_slots}
        if result.confidence >= CONFIDENCE_THRESHOLD or stage_name == "T3_LLM":
            return result

    # Every stage abstained or errored — hand back the classifier's best
    # guess with low confidence rather than raising, so the caller (the
    # orchestrator's policy gate) can escalate on low confidence instead of
    # the request failing outright.
    return TriageResult(intent=intent, domain=domain, confidence=confidence, urgency="high",
                         extracted_slots=entities, route_stage="T3_LLM_UNAVAILABLE")
