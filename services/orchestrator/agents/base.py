"""Shared shape every domain agent (Support/Payments/Fraud/InternalOps)
returns, so the orchestrator's state machine (services/orchestrator/graph.py)
never needs to know which agent it just called."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.orm import Session

from services.common.schemas import CaseState
from services.triage.schemas import TriageResult


@dataclass
class AgentOutput:
    proposal: dict[str, Any] | None  # None means "resolved with no action to authorise" (rare — usually there's at least a reply)
    observations: list[dict[str, Any]] = field(default_factory=list)
    tool_calls_used: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_inr: float = 0.0


class DomainAgent(Protocol):
    name: str
    scopes: list[str]

    def handle(self, db: Session, case: CaseState, ops_event: dict, triage: TriageResult) -> AgentOutput: ...
