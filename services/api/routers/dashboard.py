from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.api.deps import get_db
from services.orchestrator.dashboard import summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)) -> dict:
    return summary(db)
