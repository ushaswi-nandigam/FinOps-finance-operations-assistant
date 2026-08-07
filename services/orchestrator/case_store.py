"""Persists `CaseState` to the `cases` table after every state transition
(docs/architecture.md §L4: "Checkpoint state to Postgres after every node" —
a case awaiting approval may sit for hours, so the process must be able to
die and resume from here, not from an in-memory object)."""

import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.common.enums import CaseStatus, Domain
from services.common.ids import generate_id
from services.common.schemas import CaseState


def create_case(db: Session, *, event_id: str, domain: Domain, customer_ref: str) -> CaseState:
    case = CaseState(case_id=generate_id("case"), event_id=event_id, domain=domain, customer_ref=customer_ref)
    now = datetime.now(timezone.utc)
    db.execute(
        text("""INSERT INTO cases
            (case_id, event_id, domain, status, customer_ref, plan, observations, proposals,
             verifier_report, risk_decision, cost_tokens_in, cost_tokens_out, cost_inr, cost_budget_inr,
             tool_calls_used, max_tool_calls, revisions, max_revisions, triage_stage, error, created_at, updated_at)
            VALUES (:case_id, :event_id, :domain, :status, :customer_ref, :plan, :observations, :proposals,
                    :verifier_report, :risk_decision, :cost_tokens_in, :cost_tokens_out, :cost_inr, :cost_budget_inr,
                    :tool_calls_used, :max_tool_calls, :revisions, :max_revisions, :triage_stage, :error, :created_at, :updated_at)"""),
        {**_case_fields(case), "triage_stage": None, "created_at": now, "updated_at": now},
    )
    return case


def save_case(db: Session, case: CaseState, *, triage_stage: str | None = None) -> None:
    """Call after every state transition. `triage_stage` is only written
    when given (it's decided once, early, and every later save call should
    leave it alone)."""
    fields = _case_fields(case)
    set_clauses = ", ".join(f"{col} = :{col}" for col in fields if col != "case_id")
    if triage_stage is not None:
        set_clauses += ", triage_stage = :triage_stage"
        fields["triage_stage"] = triage_stage
    fields["updated_at"] = datetime.now(timezone.utc)
    set_clauses += ", updated_at = :updated_at"

    db.execute(text(f"UPDATE cases SET {set_clauses} WHERE case_id = :case_id"), fields)


def _case_fields(case: CaseState) -> dict:
    return {
        "case_id": case.case_id, "event_id": case.event_id, "domain": case.domain.value,
        "status": case.status.value, "customer_ref": case.customer_ref,
        "plan": json.dumps(case.plan), "observations": json.dumps(case.observations, default=str),
        "proposals": json.dumps(case.proposals, default=str), "verifier_report": json.dumps(case.verifier_report, default=str),
        "risk_decision": json.dumps(case.risk_decision, default=str), "cost_tokens_in": case.cost.tokens_in,
        "cost_tokens_out": case.cost.tokens_out, "cost_inr": case.cost.inr, "cost_budget_inr": case.cost_budget_inr,
        "tool_calls_used": case.tool_calls_used, "max_tool_calls": case.max_tool_calls,
        "revisions": case.revisions, "max_revisions": case.max_revisions, "error": case.error,
    }


def load_case(db: Session, case_id: str) -> dict | None:
    row = db.execute(text("SELECT * FROM cases WHERE case_id = :id"), {"id": case_id}).mappings().first()
    return _row_to_dict(row) if row else None


def list_cases(db: Session, *, status: str | None = None, domain: str | None = None, limit: int = 50) -> list[dict]:
    clauses, params = [], {"limit": limit}
    if status:
        clauses.append("status = :status")
        params["status"] = status
    if domain:
        clauses.append("domain = :domain")
        params["domain"] = domain
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"SELECT * FROM cases {where} ORDER BY created_at DESC LIMIT :limit"), params).mappings().all()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row) -> dict:
    d = dict(row)
    for field in ("plan", "observations", "proposals", "verifier_report", "risk_decision"):
        if isinstance(d.get(field), str):
            d[field] = json.loads(d[field])
    for field in ("created_at", "updated_at"):
        if hasattr(d.get(field), "isoformat"):
            d[field] = d[field].isoformat()
    return d


def case_state_from_row(row: dict) -> CaseState:
    return CaseState(
        case_id=row["case_id"], event_id=row["event_id"], domain=Domain(row["domain"]),
        status=CaseStatus(row["status"]), plan=row["plan"], observations=row["observations"],
        proposals=row["proposals"], verifier_report=row["verifier_report"], risk_decision=row["risk_decision"],
        cost={"tokens_in": row["cost_tokens_in"], "tokens_out": row["cost_tokens_out"], "inr": float(row["cost_inr"])},
        cost_budget_inr=float(row["cost_budget_inr"]), tool_calls_used=row["tool_calls_used"],
        max_tool_calls=row["max_tool_calls"], revisions=row["revisions"], max_revisions=row["max_revisions"],
        customer_ref=row["customer_ref"], error=row["error"],
    )
