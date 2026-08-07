from typing import Any
from pydantic import BaseModel, Field
from services.common.enums import CaseStatus, Domain


class CostSummary(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0
    inr: float = 0.0


class CaseState(BaseModel):
    case_id: str
    event_id: str
    domain: Domain
    status: CaseStatus = CaseStatus.INTAKE
    plan: list[str] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    proposals: list[dict[str, Any]] = Field(default_factory=list)
    verifier_report: dict[str, Any] = Field(default_factory=dict)
    risk_decision: dict[str, Any] = Field(default_factory=dict)
    cost: CostSummary = Field(default_factory=CostSummary)
    cost_budget_inr: float = 5.0
    tool_calls_used: int = 0
    max_tool_calls: int = 6
    revisions: int = 0
    max_revisions: int = 3
    customer_ref: str = ""
    error: str | None = None
