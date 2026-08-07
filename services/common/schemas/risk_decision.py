from pydantic import BaseModel, Field
from services.common.enums import Outcome, RiskTier


class RiskDecision(BaseModel):
    proposal_id: str
    case_id: str
    tier: RiskTier
    outcome: Outcome
    matched_rules: list[str] = Field(default_factory=list)
    reason_plain: str
    policy_version: str = "2026.08.01"
    required_approvers: int = Field(default=0)
    requires_distinct_approvers: bool = False
