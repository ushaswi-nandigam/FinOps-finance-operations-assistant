from datetime import datetime, timezone

from sqlalchemy import text

from services.common.enums import RiskTier, Outcome
from services.common.ids import generate_id
from services.common.schemas import RiskDecision
from services.orchestrator import approvals


def _insert_case(db, case_id: str) -> None:
    db.execute(
        text("""INSERT INTO cases (case_id, event_id, domain, status, customer_ref, plan, observations, proposals,
                verifier_report, risk_decision, created_at, updated_at)
                VALUES (:cid, 'evt_x', 'payments', 'APPROVAL_PENDING', 'cus_tok_1000', '[]', '[]', '[]', '{}', '{}', :now, :now)"""),
        {"cid": case_id, "now": datetime.now(timezone.utc)},
    )


def test_single_approval_flow(db):
    case_id, proposal_id = generate_id("case"), generate_id("prop")
    _insert_case(db, case_id)
    decision = RiskDecision(proposal_id=proposal_id, case_id=case_id, tier=RiskTier.T2, outcome=Outcome.NEEDS_APPROVAL,
                             reason_plain="test", required_approvers=1, requires_distinct_approvers=False)
    rows = approvals.create_approval_requests(db, case_id=case_id, proposal_id=proposal_id, decision=decision)
    assert len(rows) == 1

    outcome = approvals.decide_approval(db, approval_id=rows[0]["approval_id"], approver_id="alice",
                                         decision="approve", reason="looks right")
    assert outcome["all_required_approved"] is True
    assert outcome["any_rejected"] is False


def test_dual_approval_requires_both_slots(db):
    case_id, proposal_id = generate_id("case"), generate_id("prop")
    _insert_case(db, case_id)
    decision = RiskDecision(proposal_id=proposal_id, case_id=case_id, tier=RiskTier.T3, outcome=Outcome.DUAL_APPROVAL,
                             reason_plain="test", required_approvers=2, requires_distinct_approvers=True)
    rows = approvals.create_approval_requests(db, case_id=case_id, proposal_id=proposal_id, decision=decision)
    assert len(rows) == 2

    first = approvals.decide_approval(db, approval_id=rows[0]["approval_id"], approver_id="alice", decision="approve", reason="ok")
    assert first["all_required_approved"] is False  # slot 2 still pending

    second = approvals.decide_approval(db, approval_id=rows[1]["approval_id"], approver_id="bob", decision="approve", reason="ok")
    assert second["all_required_approved"] is True


def test_maker_cannot_be_checker_same_approver_both_slots(db):
    case_id, proposal_id = generate_id("case"), generate_id("prop")
    _insert_case(db, case_id)
    decision = RiskDecision(proposal_id=proposal_id, case_id=case_id, tier=RiskTier.T3, outcome=Outcome.DUAL_APPROVAL,
                             reason_plain="test", required_approvers=2, requires_distinct_approvers=True)
    rows = approvals.create_approval_requests(db, case_id=case_id, proposal_id=proposal_id, decision=decision)

    approvals.decide_approval(db, approval_id=rows[0]["approval_id"], approver_id="alice", decision="approve", reason="ok")

    import pytest
    with pytest.raises(approvals.ApprovalError, match="maker cannot also be the checker"):
        approvals.decide_approval(db, approval_id=rows[1]["approval_id"], approver_id="alice", decision="approve", reason="ok")


def test_rejection_flagged_any_rejected(db):
    case_id, proposal_id = generate_id("case"), generate_id("prop")
    _insert_case(db, case_id)
    decision = RiskDecision(proposal_id=proposal_id, case_id=case_id, tier=RiskTier.T2, outcome=Outcome.NEEDS_APPROVAL,
                             reason_plain="test", required_approvers=1)
    rows = approvals.create_approval_requests(db, case_id=case_id, proposal_id=proposal_id, decision=decision)

    outcome = approvals.decide_approval(db, approval_id=rows[0]["approval_id"], approver_id="alice",
                                         decision="reject", reason="not justified")
    assert outcome["any_rejected"] is True
    assert outcome["status"] == "REJECTED"


def test_deciding_already_decided_approval_raises(db):
    case_id, proposal_id = generate_id("case"), generate_id("prop")
    _insert_case(db, case_id)
    decision = RiskDecision(proposal_id=proposal_id, case_id=case_id, tier=RiskTier.T2, outcome=Outcome.NEEDS_APPROVAL,
                             reason_plain="test", required_approvers=1)
    rows = approvals.create_approval_requests(db, case_id=case_id, proposal_id=proposal_id, decision=decision)
    approvals.decide_approval(db, approval_id=rows[0]["approval_id"], approver_id="alice", decision="approve", reason="ok")

    import pytest
    with pytest.raises(approvals.ApprovalError, match="already"):
        approvals.decide_approval(db, approval_id=rows[0]["approval_id"], approver_id="bob", decision="approve", reason="ok")
