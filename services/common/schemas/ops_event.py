from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from services.common.errors import PIIViolationError


class OpsEvent(BaseModel):
    event_id: str
    source: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    customer_ref: str
    channel: str
    raw_text: str | None = None
    redacted_text: str
    entities: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str
    processed_l2: bool = False

    def validate_downstream_safety(self) -> "OpsEvent":
        """Ensures that if raw_text is present, it is not passed downstream without redacted_text set."""
        if not self.redacted_text:
            raise PIIViolationError("OpsEvent has not been redacted by Layer 2 before processing!")
        return self

    def to_sanitized_dict(self) -> dict[str, Any]:
        """Returns event representation guaranteed to exclude raw un-redacted PII text."""
        data = self.model_dump()
        data["raw_text"] = "[REDACTED_AT_L2]"
        return data
