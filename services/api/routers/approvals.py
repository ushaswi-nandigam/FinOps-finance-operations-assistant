from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.api.deps import get_db
from services.orchestrator import approvals as approvals_service
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
        outcome = approvals_service.decide_and_resume(
            db, approval_id=approval_id, approver_id=req.approver_id, decision=req.decision,
            reason=req.reason, modified_args=req.modified_args,
        )
    except approvals_service.ApprovalError as exc:
        raise HTTPException(409, str(exc)) from exc

    db.flush()
    return {**outcome, "case": load_case(db, outcome["case_id"])}
