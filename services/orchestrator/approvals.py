"""L8 — Human-in-the-Loop. Creates the approval slot(s) a case's
`RiskDecision` calls for (1 for NEEDS_APPROVAL, 2 for DUAL_APPROVAL) and
records a human's decision against one.

Maker != checker (docs/architecture.md §L8) is enforced by the database, not
application logic: `UNIQUE(proposal_id, approver_id)` on the `approvals`
table makes it physically impossible for the same approver_id to end up
recorded on two slots of the same proposal — see `decide_approval` below,
where that constraint violation is caught and turned into a clear rejection
rather than a 500.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.common.errors import FinOpsException
from services.common.ids import generate_id
from services.common.schemas import RiskDecision

SLA_HOURS = 24


class ApprovalError(FinOpsException):
    pass


def create_approval_requests(db: Session, *, case_id: str, proposal_id: str, decision: RiskDecision) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=SLA_HOURS)
    rows = []
    for slot in range(1, decision.required_approvers + 1):
        approval_id = generate_id("appr")
        db.execute(
            text("""INSERT INTO approvals (approval_id, case_id, proposal_id, slot_no, status, sla_deadline, created_at)
                    VALUES (:approval_id, :case_id, :proposal_id, :slot_no, 'PENDING', :sla_deadline, :created_at)"""),
            {"approval_id": approval_id, "case_id": case_id, "proposal_id": proposal_id, "slot_no": slot,
             "sla_deadline": deadline, "created_at": now},
        )
        rows.append({"approval_id": approval_id, "case_id": case_id, "proposal_id": proposal_id, "slot_no": slot, "status": "PENDING"})
    return rows


def get_approval(db: Session, approval_id: str) -> dict[str, Any] | None:
    row = db.execute(text("SELECT * FROM approvals WHERE approval_id = :id"), {"id": approval_id}).mappings().first()
    return dict(row) if row else None


def list_approvals_for_proposal(db: Session, proposal_id: str) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT * FROM approvals WHERE proposal_id = :pid ORDER BY slot_no"), {"pid": proposal_id}).mappings().all()
    return [dict(r) for r in rows]


def list_pending(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.execute(
        text("SELECT * FROM approvals WHERE status = 'PENDING' ORDER BY sla_deadline ASC LIMIT :limit"), {"limit": limit}
    ).mappings().all()
    return [dict(r) for r in rows]


Decision = Literal["approve", "reject", "send_back"]


def decide_approval(db: Session, *, approval_id: str, approver_id: str, decision: Decision, reason: str) -> dict[str, Any]:
    approval = get_approval(db, approval_id)
    if approval is None:
        raise ApprovalError(f"approval {approval_id} not found")
    if approval["status"] != "PENDING":
        raise ApprovalError(f"approval {approval_id} is already {approval['status']}")

    status_map = {"approve": "APPROVED", "reject": "REJECTED", "send_back": "SENT_BACK"}
    new_status = status_map[decision]
    now = datetime.now(timezone.utc)

    try:
        db.execute(
            text("""UPDATE approvals SET status = :status, approver_id = :approver_id,
                    decision_reason = :reason, decided_at = :decided_at WHERE approval_id = :id"""),
            {"status": new_status, "approver_id": approver_id, "reason": reason, "decided_at": now, "id": approval_id},
        )
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApprovalError(
            f"approver '{approver_id}' has already decided on proposal {approval['proposal_id']} — "
            "the maker cannot also be the checker for the same proposal."
        ) from exc

    siblings = list_approvals_for_proposal(db, approval["proposal_id"])
    all_approved = all(s["status"] == "APPROVED" for s in siblings)
    any_rejected = any(s["status"] in ("REJECTED", "SENT_BACK") for s in siblings)

    return {
        "approval_id": approval_id, "case_id": approval["case_id"], "proposal_id": approval["proposal_id"],
        "status": new_status, "all_required_approved": all_approved, "any_rejected": any_rejected,
    }


def decide_and_resume(
    db: Session, *, approval_id: str, approver_id: str, decision: Decision, reason: str,
    modified_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The single entrypoint every caller should use — `decide_approval`
    alone only updates the approval row; it does *not* execute the
    underlying action once every required slot is in, or escalate the case
    on rejection. That resumption logic used to live only in the API router
    (services/api/routers/approvals.py), which meant any other caller of
    `decide_approval` (this function's own reason for existing:
    scripts/demo_driver.py originally called `decide_approval` directly and
    silently left every approved case stuck in APPROVAL_PENDING, since
    nothing ever told the orchestrator the approval had completed) got an
    incomplete operation. Consolidating it here makes that impossible to
    forget again.
    """
    from services.orchestrator import resume

    outcome = decide_approval(db, approval_id=approval_id, approver_id=approver_id, decision=decision, reason=reason)

    if decision == "approve" and outcome["all_required_approved"]:
        approver_ids = [s["approver_id"] for s in list_approvals_for_proposal(db, outcome["proposal_id"])]
        resume.execute_after_approval(db, case_id=outcome["case_id"], proposal_id=outcome["proposal_id"],
                                       approver_ids=approver_ids, modified_args=modified_args)
    elif decision in ("reject", "send_back"):
        resume.reject_case(db, case_id=outcome["case_id"], proposal_id=outcome["proposal_id"],
                            approver_id=approver_id, reason=reason or f"{decision} with no reason given")

    return outcome
