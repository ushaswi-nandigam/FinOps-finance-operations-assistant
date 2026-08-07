import pytest
from services.common.enums import Domain, Outcome, RiskTier
from services.common.errors import PIIViolationError
from services.common.schemas import (
    ActionProposal,
    CaseState,
    DecisionRecord,
    OpsEvent,
    RiskDecision,
    ToolManifest,
)


def test_ops_event_pii_validation():
    event = OpsEvent(
        event_id="evt_01",
        source="support_ticket",
        customer_ref="cus_tok_9f2a",
        channel="chat",
        raw_text="My card 4111222233334444 failed",
        redacted_text="My card [CARD_1] failed",
        trace_id="trc_01",
        processed_l2=True,
    )
    # Valid downstream check
    assert event.validate_downstream_safety().redacted_text == "My card [CARD_1] failed"

    # Sanitized dict check prevents raw text leak
    sanitized = event.to_sanitized_dict()
    assert sanitized["raw_text"] == "[REDACTED_AT_L2]"


def test_ops_event_missing_redaction_raises():
    event = OpsEvent(
        event_id="evt_02",
        source="support_ticket",
        customer_ref="cus_tok_9f2a",
        channel="chat",
        raw_text="Raw unredacted text",
        redacted_text="",
        trace_id="trc_02",
    )
    with pytest.raises(PIIViolationError):
        event.validate_downstream_safety()


def test_proposal_schema():
    prop = ActionProposal(
        proposal_id="prop_01",
        case_id="case_01",
        domain=Domain.PAYMENTS,
        action_type="issue_refund",
        args={"amount_inr": 1500},
        confidence=0.95,
        proposed_by="payments_agent",
        reasoning="Customer double charged due to network timeout",
    )
    assert prop.domain == Domain.PAYMENTS
    assert prop.args["amount_inr"] == 1500


def test_risk_decision_schema():
    decision = RiskDecision(
        proposal_id="prop_01",
        case_id="case_01",
        tier=RiskTier.T2,
        outcome=Outcome.NEEDS_APPROVAL,
        matched_rules=["REFUND-POL-3.2"],
        reason_plain="Refund between ₹500 and ₹25,000 requires single ops approval.",
        required_approvers=1,
    )
    assert decision.tier == RiskTier.T2
    assert decision.outcome == Outcome.NEEDS_APPROVAL


def test_case_state_json_serializable():
    state = CaseState(
        case_id="case_100",
        event_id="evt_100",
        domain=Domain.FRAUD,
        customer_ref="cus_tok_123",
    )
    serialized = state.model_dump_json()
    deserialized = CaseState.model_validate_json(serialized)
    assert deserialized.case_id == "case_100"
    assert deserialized.domain == Domain.FRAUD


def test_tool_manifest():
    tool = ToolManifest(
        name="issue_refund",
        system="payments",
        description="Issue financial refund",
        risk_tier=RiskTier.T2,
        reversible=False,
        requires_idempotency=True,
    )
    assert tool.name == "issue_refund"
    assert tool.risk_tier == RiskTier.T2
