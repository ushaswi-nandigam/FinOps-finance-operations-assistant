"""L5b — the mandated self-check (docs/architecture.md §L5b), placeholder
version. Every proposal passes through here before the risk gate, but this
first cut always returns PASS — it exists so the state machine's SELF_VERIFY
step and the DecisionRecord.verifier field are wired end-to-end from the
start. A later build step (Step 10 in the project plan) replaces this with
an LLM-based check against the Business Goals checklist that can actually
return REVISE/REJECT; nothing else in the orchestrator needs to change when
it does, since the call site only depends on this function's shape.
"""

from typing import Any


def verify(proposal: dict[str, Any] | None) -> dict[str, Any]:
    if proposal is None:
        return {"verdict": "PASS", "confidence": 1.0, "goal_conformance": {}, "revision_hint": None}
    return {
        "verdict": "PASS",
        "confidence": 1.0,
        "goal_conformance": {"placeholder": {"pass": True, "why": "Verifier Agent not yet wired — see services/orchestrator/verify.py"}},
        "revision_hint": None,
    }
