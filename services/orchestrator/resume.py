"""Resumes a case after it has sat in APPROVAL_PENDING — potentially for
hours, across process restarts, since everything needed to resume was
checkpointed to MySQL rather than held in memory (docs/architecture.md §L4).
"""

from services.audit.ledger import record_decision
from services.common.config import settings
from services.common.enums import CaseStatus, Outcome
from services.common.schemas import ActorRecord, CostRecord
from services.orchestrator.case_store import case_state_from_row, load_case, save_case
from services.tools.executor import execute_tool


def _find_proposal(case_row: dict, proposal_id: str) -> dict:
    for p in case_row["proposals"]:
        if p["proposal_id"] == proposal_id:
            return p
    raise ValueError(f"proposal {proposal_id} not found on case {case_row['case_id']}")


def execute_after_approval(db, *, case_id: str, proposal_id: str, approver_ids: list[str], modified_args: dict | None = None):
    case_row = load_case(db, case_id)
    if case_row is None:
        raise ValueError(f"case {case_id} not found")
    proposal = _find_proposal(case_row, proposal_id)
    args = {**proposal["args"], **(modified_args or {})}

    case = case_state_from_row(case_row)
    case.status = CaseStatus.EXECUTE
    save_case(db, case)

    result = execute_tool(db, case_id=case_id, tool_name=proposal["action_type"], args=args, dry_run=False)
    case.observations.append({"tool": proposal["action_type"], "result": result, "human_approved_by": approver_ids})
    case.status = CaseStatus.RESOLVE
    save_case(db, case)

    approvers_note = " and ".join(approver_ids)
    modification_note = " (with human-modified arguments)" if modified_args else ""
    record_decision(
        db, case_id=case_id, actor=ActorRecord(type="human", name=approvers_note),
        action={"type": proposal["action_type"], "args": args}, outcome=Outcome.AUTO_EXECUTE.value,
        reason_plain=f"Executed after human approval by {approvers_note}{modification_note}.",
        evidence=proposal.get("evidence", []), matched_rules=["HUMAN-APPROVED"],
        cost=CostRecord(stage="human_approval"), policy_version=settings.POLICY_VERSION,
    )
    return case


def reject_case(db, *, case_id: str, proposal_id: str, approver_id: str, reason: str):
    case_row = load_case(db, case_id)
    if case_row is None:
        raise ValueError(f"case {case_id} not found")
    case = case_state_from_row(case_row)
    case.status = CaseStatus.ESCALATE
    case.error = f"Approval rejected by {approver_id}: {reason}"
    save_case(db, case)

    record_decision(
        db, case_id=case_id, actor=ActorRecord(type="human", name=approver_id),
        action={"type": "reject_proposal", "proposal_id": proposal_id}, outcome=Outcome.DENY.value,
        reason_plain=case.error, matched_rules=["HUMAN-REJECTED"], policy_version=settings.POLICY_VERSION,
    )
    return case
