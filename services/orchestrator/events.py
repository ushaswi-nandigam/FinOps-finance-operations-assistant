import json

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_ops_event(db: Session, event_id: str) -> dict | None:
    row = db.execute(text("SELECT * FROM ops_events WHERE event_id = :id"), {"id": event_id}).mappings().first()
    if not row:
        return None
    d = dict(row)
    for field in ("entities", "attachments"):
        if isinstance(d.get(field), str):
            d[field] = json.loads(d[field])
    return d
