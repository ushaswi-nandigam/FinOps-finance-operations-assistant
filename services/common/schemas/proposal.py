from typing import Any
from pydantic import BaseModel, Field
from services.common.enums import Domain


class EvidenceRef(BaseModel):
    type: str  # transaction, policy, transcript, customer_profile
    ref: str  # txn_123, REFUND-POL-3.2, etc.


class ActionProposal(BaseModel):
    proposal_id: str
    case_id: str
    domain: Domain
    action_type: str  # e.g., issue_refund, retry_payment, waive_fee, place_fraud_hold
    args: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    proposed_by: str  # agent name e.g., payments_agent
    reasoning: str
