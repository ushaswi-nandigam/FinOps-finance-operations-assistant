"""Every tool an agent can call is declared here with a manifest
(docs/architecture.md §L6). This is the single source of truth for what an
agent is *allowed* to touch — the Support Agent's toolset literally does not
include `issue_refund` (least-privilege by construction, not by convention).

`risk_tier` here is the tool's *typical* tier, useful for the console and for
a business user skimming this file — it is never itself the authorisation.
The actual tier for a given call always comes from
`services.policy_engine.engine.authorise()`, which re-derives it from the
real amount/customer/fraud-score at call time.
"""

from services.common.enums import RiskTier
from services.common.schemas import ToolManifest

TOOLS: dict[str, ToolManifest] = {
    m.name: m
    for m in [
        # --- Support Agent toolset (read-only + fully reversible) ---
        ToolManifest(name="lookup_status", system="crm", description="Look up a customer, ticket, or transaction status.",
                      risk_tier=RiskTier.T0, reversible=True, requires_idempotency=False, dry_run_supported=False,
                      scopes=["crm:read", "payments:read"]),
        ToolManifest(name="send_templated_reply", system="casemgmt", description="Send a pre-approved templated reply on a ticket.",
                      risk_tier=RiskTier.T0, reversible=True, requires_idempotency=True, dry_run_supported=False,
                      scopes=["casemgmt:write"]),
        ToolManifest(name="tag_ticket", system="casemgmt", description="Apply a classification tag to a ticket.",
                      risk_tier=RiskTier.T0, reversible=True, requires_idempotency=False, dry_run_supported=False,
                      scopes=["casemgmt:write"]),
        ToolManifest(name="summarize_issue", system="casemgmt", description="Write a summary of the customer's issue onto the case.",
                      risk_tier=RiskTier.T0, reversible=True, requires_idempotency=False, dry_run_supported=False,
                      scopes=["casemgmt:write"]),
        ToolManifest(name="update_contact_details", system="crm", description="Update a customer's email or phone.",
                      risk_tier=RiskTier.T0, reversible=True, requires_idempotency=True, dry_run_supported=False,
                      pii_fields=["email", "phone"], scopes=["crm:write"]),
        ToolManifest(name="create_internal_task", system="casemgmt", description="Create an internal ops workflow task.",
                      risk_tier=RiskTier.T0, reversible=True, requires_idempotency=True, dry_run_supported=False,
                      scopes=["casemgmt:write"]),

        # --- Payments Agent toolset ---
        ToolManifest(name="retry_payment", system="payments", description="Retry a failed payment at the gateway.",
                      risk_tier=RiskTier.T1, reversible=True, requires_idempotency=True, dry_run_supported=True,
                      scopes=["payments:write"]),
        ToolManifest(name="issue_refund", system="payments", description="Issue a refund for a transaction.",
                      risk_tier=RiskTier.T2, reversible=False, requires_idempotency=True, dry_run_supported=True,
                      pii_fields=["customer_ref"], scopes=["payments:write"]),
        ToolManifest(name="waive_fee", system="payments", description="Waive a fee charged to a customer.",
                      risk_tier=RiskTier.T2, reversible=False, requires_idempotency=True, dry_run_supported=True,
                      scopes=["payments:write"]),

        # --- Fraud Agent toolset ---
        ToolManifest(name="place_fraud_hold", system="casemgmt", description="Place a fraud hold on an account.",
                      risk_tier=RiskTier.T3, reversible=True, requires_idempotency=True, dry_run_supported=True,
                      scopes=["casemgmt:write", "payments:write"]),
        ToolManifest(name="lift_fraud_hold", system="casemgmt", description="Lift a fraud hold on an account.",
                      risk_tier=RiskTier.T3, reversible=True, requires_idempotency=True, dry_run_supported=True,
                      scopes=["casemgmt:write", "payments:write"]),
        ToolManifest(name="close_fraud_case_benign", system="casemgmt", description="Close a fraud case as benign.",
                      risk_tier=RiskTier.T2, reversible=True, requires_idempotency=True, dry_run_supported=True,
                      scopes=["casemgmt:write"]),

        # --- Account actions ---
        ToolManifest(name="unblock_card", system="payments", description="Unblock a card after a routine PIN-retry lock.",
                      risk_tier=RiskTier.T1, reversible=True, requires_idempotency=True, dry_run_supported=True,
                      scopes=["payments:write"]),
        ToolManifest(name="freeze_account", system="payments", description="Freeze a customer's account.",
                      risk_tier=RiskTier.T3, reversible=True, requires_idempotency=True, dry_run_supported=True,
                      scopes=["payments:write"]),
        ToolManifest(name="unfreeze_account", system="payments", description="Unfreeze a customer's account.",
                      risk_tier=RiskTier.T3, reversible=True, requires_idempotency=True, dry_run_supported=True,
                      scopes=["payments:write"]),
    ]
}


def get_manifest(tool_name: str) -> ToolManifest | None:
    return TOOLS.get(tool_name)


def tools_for_scope(*scopes: str) -> list[ToolManifest]:
    """The least-privilege check an agent's toolset is built from: only
    tools whose every declared scope is in the agent's allowed scope set."""
    allowed = set(scopes)
    return [m for m in TOOLS.values() if set(m.scopes) <= allowed]
