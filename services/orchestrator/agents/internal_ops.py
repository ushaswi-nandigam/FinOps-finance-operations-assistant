"""Internal Ops Agent — cheap tier (docs/architecture.md §L5). Routes
internal requests (limit enhancements, onboarding, access requests, ...) to
the workflow catalogue and prepares an approval packet. Every action it can
take is `create_internal_task` (T0, always auto-execute per SUPPORT-POL-1.0)
— it hands off to a human queue rather than deciding anything itself, which
is the right amount of autonomy for requests this open-ended.
"""

from typing import Any

from sqlalchemy.orm import Session

from services.common.ids import generate_id
from services.common.schemas import CaseState
from services.mocks.casemgmt import CaseMgmtAdapter
from services.orchestrator.agents.base import AgentOutput
from services.triage.schemas import TriageResult

NAME = "internal_ops_agent"
SCOPES = ["casemgmt:write", "casemgmt:read"]

INTENT_CATEGORY = {
    "internal_ops_request": "general",
    "limit_enhancement_request": "access_request",
}


def handle(db: Session, case: CaseState, ops_event: dict, triage: TriageResult, *, revise: bool = False) -> AgentOutput:
    observations: list[dict[str, Any]] = []
    category = INTENT_CATEGORY.get(triage.intent, "general")

    catalogue = CaseMgmtAdapter(db).list_workflows(category=category if category != "general" else None, limit=5)
    observations.append({"tool": "list_workflows", "result": catalogue})

    matched = catalogue[0]["title"] if catalogue else None
    reasoning = (f"Matched to the '{category}' workflow catalogue (closest existing workflow: {matched}); "
                 f"creating a tracked task rather than acting directly — internal ops requests need a named owner.") \
        if matched else "No matching catalogue entry found; creating a general tracked task for manual triage."

    proposal = {
        "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
        "action_type": "create_internal_task",
        "args": {"title": f"{triage.intent.replace('_', ' ').title()}", "description": ops_event.get("redacted_text", ""), "category": category},
        "evidence": [{"type": "ticket", "ref": ops_event.get("event_id", "")}],
        "confidence": 0.9, "proposed_by": NAME, "reasoning": reasoning,
    }
    return AgentOutput(proposal=proposal, observations=observations, tool_calls_used=1)
