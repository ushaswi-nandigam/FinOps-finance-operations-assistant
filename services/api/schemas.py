"""Request/response models for the FastAPI ingress + case + approval routers.
Kept separate from services/common/schemas (the internal data contracts) —
these are the wire format."""

from pydantic import BaseModel, Field


class TicketIngressRequest(BaseModel):
    ticket_id: str | None = None
    customer_ref: str | None = None
    text: str | None = None


class TranscriptIngressRequest(BaseModel):
    transcript_id: str | None = None
    customer_ref: str | None = None
    channel: str | None = None
    turns: list[dict] | None = None


class PaymentEventIngressRequest(BaseModel):
    txn_id: str


class DisputeIngressRequest(BaseModel):
    dispute_id: str


class InternalOpsIngressRequest(BaseModel):
    customer_ref: str = Field(default="cus_tok_internal")
    title: str
    description: str
    category: str = "general"


class IngressResponse(BaseModel):
    event_id: str
    trace_id: str
    customer_ref: str
    source: str
    redacted_text: str
    entities: dict
