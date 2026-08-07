from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.api.deps import get_db
from services.audit.export import export_case
from services.audit.ledger import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/export")
def audit_export(case_id: str, db: Session = Depends(get_db)) -> dict:
    payload = export_case(db, case_id)
    if payload["decision_count"] == 0:
        raise HTTPException(404, f"no decision records for case_id={case_id}")
    return payload


@router.get("/verify")
def audit_verify(db: Session = Depends(get_db)) -> dict:
    return verify_chain(db)
