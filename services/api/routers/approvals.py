from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.api.deps import get_db
from services.orchestrator import approvals as approvals_service
from services.orchestrator import resume
from services.orchestrator.case_store import load_case

router = APIRouter(prefix="/approvals", tags=["approvals"])


class DecideRequest(BaseModel):
    approver_id: str
    decision: str  # approve | reject | send_back
    reason: str = ""
    modified_args: dict | None = None


@router.get("")
def pending(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    rows = approvals_service.list_pending(db, limit=limit)
    enriched = []
    for row in rows:
        case = load_case(db, row["case_id"])
        proposal = next((p for p in (case["proposals"] if case else []) if p["proposal_id"] == row["proposal_id"]), None)
        tier = (case or {}).get("risk_decision", {}).get("tier")
        enriched.append({**row, "proposal": proposal, "case_domain": case["domain"] if case else None, "tier": tier})
    return enriched


@router.post("/{approval_id}/decide")
def decide(approval_id: str, req: DecideRequest, db: Session = Depends(get_db)) -> dict:
    if req.decision not in ("approve", "reject", "send_back"):
        raise HTTPException(422, "decision must be one of: approve, reject, send_back")

    try:
        outcome = approvals_service.decide_approval(
            db, approval_id=approval_id, approver_id=req.approver_id, decision=req.decision, reason=req.reason,
        )
    except approvals_service.ApprovalError as exc:
        raise HTTPException(409, str(exc)) from exc

    if req.decision == "approve" and outcome["all_required_approved"]:
        siblings = approvals_service.list_approvals_for_proposal(db, outcome["proposal_id"])
        approver_ids = [s["approver_id"] for s in siblings]
        resume.execute_after_approval(
            db, case_id=outcome["case_id"], proposal_id=outcome["proposal_id"],
            approver_ids=approver_ids, modified_args=req.modified_args,
        )
    elif req.decision in ("reject", "send_back"):
        resume.reject_case(db, case_id=outcome["case_id"], proposal_id=outcome["proposal_id"],
                            approver_id=req.approver_id, reason=req.reason or f"{req.decision} with no reason given")

    db.flush()
    return {**outcome, "case": load_case(db, outcome["case_id"])}
