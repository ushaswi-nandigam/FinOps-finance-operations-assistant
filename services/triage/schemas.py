from typing import Any

from pydantic import BaseModel, Field

from services.common.enums import Domain


class TriageResult(BaseModel):
    intent: str
    domain: Domain
    confidence: float = Field(ge=0.0, le=1.0)
    urgency: str = "medium"
    extracted_slots: dict[str, Any] = Field(default_factory=dict)
    route_stage: str  # T0_RULES | T1_CLASSIFIER | T2_LLM | T3_LLM
