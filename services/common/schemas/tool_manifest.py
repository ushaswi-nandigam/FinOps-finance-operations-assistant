from typing import Any
from pydantic import BaseModel, Field
from services.common.enums import RiskTier


class ToolManifest(BaseModel):
    name: str
    system: str  # payments, crm, casemgmt, kb
    description: str
    risk_tier: RiskTier
    reversible: bool = False
    requires_idempotency: bool = True
    pii_fields: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    dry_run_supported: bool = True
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
