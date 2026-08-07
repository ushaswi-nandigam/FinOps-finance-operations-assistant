from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from services.common.enums import Outcome


class CostRecord(BaseModel):
    stage: str
    tokens_in: int = 0
    tokens_out: int = 0
    inr: float = 0.0


class ActorRecord(BaseModel):
    type: str  # agent, human, system
    name: str
    model: str | None = None
    version: str | None = None


class DecisionRecord(BaseModel):
    decision_id: str
    case_id: str
    seq: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: ActorRecord
    action: dict[str, Any]
    outcome: Outcome
    reason_plain: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    verifier: dict[str, Any] = Field(default_factory=dict)
    cost: CostRecord = Field(default_factory=CostRecord)
    policy_version: str = "2026.08.01"
    prev_hash: str = ""
    entry_hash: str = ""
