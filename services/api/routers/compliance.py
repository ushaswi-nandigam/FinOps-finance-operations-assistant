from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.api.deps import get_db
from services.orchestrator.agents.compliance import search

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/search")
def search_policies(q: str, top_k: int = 3, db: Session = Depends(get_db)) -> list[dict]:
    return search(db, q, top_k=top_k)
