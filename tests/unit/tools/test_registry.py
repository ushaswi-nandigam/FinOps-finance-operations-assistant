from services.common.enums import RiskTier
from services.tools.manifests.registry import TOOLS, get_manifest, tools_for_scope


def test_issue_refund_registered_with_correct_defaults():
    m = get_manifest("issue_refund")
    assert m is not None
    assert m.system == "payments"
    assert m.reversible is False
    assert m.requires_idempotency is True
    assert m.dry_run_supported is True


def test_unknown_tool_returns_none():
    assert get_manifest("delete_everything") is None


def test_support_agent_scope_excludes_issue_refund():
    """Least-privilege by construction: a Support Agent scoped only to
    crm/casemgmt reads and replies literally cannot see issue_refund."""
    support_tools = tools_for_scope("crm:read", "payments:read", "casemgmt:write")
    names = {t.name for t in support_tools}
    assert "issue_refund" not in names
    assert "lookup_status" in names
    assert "send_templated_reply" in names


def test_payments_agent_scope_includes_refund_and_retry():
    payments_tools = tools_for_scope("payments:read", "payments:write")
    names = {t.name for t in payments_tools}
    assert "issue_refund" in names
    assert "retry_payment" in names
    assert "waive_fee" in names


def test_every_tool_has_a_risk_tier():
    for manifest in TOOLS.values():
        assert isinstance(manifest.risk_tier, RiskTier)
