from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.api.deps import get_db
from services.orchestrator.case_store import list_cases, load_case
from services.orchestrator.graph import process_event

router = APIRouter(prefix="/cases", tags=["cases"])


class ProcessEventRequest(BaseModel):
    event_id: str


@router.post("/process")
def process(req: ProcessEventRequest, db: Session = Depends(get_db)) -> dict:
    try:
        case = process_event(db, req.event_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    db.flush()
    return load_case(db, case.case_id)


@router.get("")
def list_all(status: str | None = None, domain: str | None = None, limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    return list_cases(db, status=status, domain=domain, limit=limit)


@router.get("/{case_id}")
def get_one(case_id: str, db: Session = Depends(get_db)) -> dict:
    case = load_case(db, case_id)
    if case is None:
        raise HTTPException(404, f"case {case_id} not found")
    return case
