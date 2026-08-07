"""L1 — Ingress. One endpoint per channel; each only validates the envelope
and stores — it never interprets content (architecture.md §L1: "must not
interpret content"). Interpretation starts at L3 (triage), which a later
build step wires up as a background task from here.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.api.deps import get_db
from services.api.schemas import (
    DisputeIngressRequest,
    IngressResponse,
    InternalOpsIngressRequest,
    PaymentEventIngressRequest,
    TicketIngressRequest,
    TranscriptIngressRequest,
)
from services.common.ids import event_id as new_event_id
from services.common.ids import trace_id as new_trace_id
from services.privacy.redactor import redact

router = APIRouter(prefix="/ingress", tags=["ingress"])


def _store_raw_event(db: Session, eid: str, source: str, payload: dict) -> None:
    db.execute(
        text("INSERT INTO raw_events (event_id, source, payload, received_at) VALUES (:id, :source, :payload, :received_at)"),
        {"id": eid, "source": source, "payload": json.dumps(payload, default=str), "received_at": datetime.now(timezone.utc)},
    )


def _store_ops_event(
    db: Session, eid: str, source: str, customer_ref: str, channel: str,
    redacted_text: str, entities: dict, tid: str,
) -> None:
    db.execute(
        text("""INSERT INTO ops_events
            (event_id, source, received_at, customer_ref, channel, redacted_text, entities, attachments, trace_id, processed_l2)
            VALUES (:id, :source, :received_at, :customer_ref, :channel, :redacted_text, :entities, :attachments, :trace_id, TRUE)"""),
        {
            "id": eid, "source": source, "received_at": datetime.now(timezone.utc),
            "customer_ref": customer_ref, "channel": channel, "redacted_text": redacted_text,
            "entities": json.dumps(entities), "attachments": json.dumps([]), "trace_id": tid,
        },
    )


@router.post("/ticket", response_model=IngressResponse)
def ingress_ticket(req: TicketIngressRequest, db: Session = Depends(get_db)) -> IngressResponse:
    if req.ticket_id:
        row = db.execute(text("SELECT * FROM tickets WHERE ticket_id = :id"), {"id": req.ticket_id}).mappings().first()
        if not row:
            raise HTTPException(404, f"ticket {req.ticket_id} not found")
        customer_ref, raw_text = row["customer_ref"], row["text"]
    elif req.customer_ref and req.text:
        customer_ref, raw_text = req.customer_ref, req.text
    else:
        raise HTTPException(422, "either ticket_id or (customer_ref and text) is required")

    eid, tid = new_event_id(), new_trace_id()
    _store_raw_event(db, eid, "support_ticket", req.model_dump())
    redacted_text, entities = redact(db, raw_text, eid)
    _store_ops_event(db, eid, "support_ticket", customer_ref, "chat", redacted_text, entities, tid)

    return IngressResponse(event_id=eid, trace_id=tid, customer_ref=customer_ref, source="support_ticket",
                            redacted_text=redacted_text, entities=entities)


@router.post("/transcript", response_model=IngressResponse)
def ingress_transcript(req: TranscriptIngressRequest, db: Session = Depends(get_db)) -> IngressResponse:
    if req.transcript_id:
        row = db.execute(text("SELECT * FROM transcripts WHERE transcript_id = :id"), {"id": req.transcript_id}).mappings().first()
        if not row:
            raise HTTPException(404, f"transcript {req.transcript_id} not found")
        customer_ref, channel = row["customer_ref"], row["channel"]
        turns = json.loads(row["turns"]) if isinstance(row["turns"], str) else row["turns"]
    elif req.customer_ref and req.turns:
        customer_ref, channel, turns = req.customer_ref, req.channel or "chat", req.turns
    else:
        raise HTTPException(422, "either transcript_id or (customer_ref and turns) is required")

    raw_text = "\n".join(f"{t.get('speaker', '?')}: {t.get('text', '')}" for t in turns)
    eid, tid = new_event_id(), new_trace_id()
    _store_raw_event(db, eid, "transcript", req.model_dump())
    redacted_text, entities = redact(db, raw_text, eid)
    _store_ops_event(db, eid, "transcript", customer_ref, channel, redacted_text, entities, tid)

    return IngressResponse(event_id=eid, trace_id=tid, customer_ref=customer_ref, source="transcript",
                            redacted_text=redacted_text, entities=entities)


@router.post("/payment_event", response_model=IngressResponse)
def ingress_payment_event(req: PaymentEventIngressRequest, db: Session = Depends(get_db)) -> IngressResponse:
    row = db.execute(text("SELECT * FROM transactions WHERE txn_id = :id"), {"id": req.txn_id}).mappings().first()
    if not row:
        raise HTTPException(404, f"transaction {req.txn_id} not found")

    raw_text = (f"Payment event for txn {row['txn_id']}: status={row['status']}, "
                f"decline_code={row['decline_code']}, amount=₹{row['amount_inr']}")
    eid, tid = new_event_id(), new_trace_id()
    _store_raw_event(db, eid, "payment_event", req.model_dump())
    redacted_text, entities = redact(db, raw_text, eid)
    _store_ops_event(db, eid, "payment_event", row["customer_ref"], "webhook", redacted_text, entities, tid)

    return IngressResponse(event_id=eid, trace_id=tid, customer_ref=row["customer_ref"], source="payment_event",
                            redacted_text=redacted_text, entities=entities)


@router.post("/dispute", response_model=IngressResponse)
def ingress_dispute(req: DisputeIngressRequest, db: Session = Depends(get_db)) -> IngressResponse:
    row = db.execute(text("SELECT * FROM disputes WHERE dispute_id = :id"), {"id": req.dispute_id}).mappings().first()
    if not row:
        raise HTTPException(404, f"dispute {req.dispute_id} not found")

    raw_text = f"Dispute {row['dispute_id']} on txn {row['txn_id']}: reason={row['reason']}, amount=₹{row['amount_inr']}"
    eid, tid = new_event_id(), new_trace_id()
    _store_raw_event(db, eid, "dispute", req.model_dump())
    redacted_text, entities = redact(db, raw_text, eid)
    _store_ops_event(db, eid, "dispute", row["customer_ref"], "batch_poll", redacted_text, entities, tid)

    return IngressResponse(event_id=eid, trace_id=tid, customer_ref=row["customer_ref"], source="dispute",
                            redacted_text=redacted_text, entities=entities)


@router.post("/internal_ops", response_model=IngressResponse)
def ingress_internal_ops(req: InternalOpsIngressRequest, db: Session = Depends(get_db)) -> IngressResponse:
    raw_text = f"{req.title}: {req.description}"
    eid, tid = new_event_id(), new_trace_id()
    _store_raw_event(db, eid, "internal_ops", req.model_dump())
    redacted_text, entities = redact(db, raw_text, eid)
    _store_ops_event(db, eid, "internal_ops", req.customer_ref, "form", redacted_text, entities, tid)

    return IngressResponse(event_id=eid, trace_id=tid, customer_ref=req.customer_ref, source="internal_ops",
                            redacted_text=redacted_text, entities=entities)
