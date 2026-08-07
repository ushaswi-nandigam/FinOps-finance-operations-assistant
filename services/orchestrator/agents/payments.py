"""Payments Agent — cheap-to-mid tier (docs/architecture.md §L5). Diagnoses
failed payments and proposes retries/refunds/fee waivers from the system of
record. Like Support Agent, the proposals here are template/rule-driven, not
LLM-drafted — the interesting reasoning in this project's money-moving path
lives in the policy engine, not in prose generation. (Fraud Agent, step 9,
is where an LLM actually earns its keep — narrating a classical model's
output.)
"""

from typing import Any

from sqlalchemy.orm import Session

from services.common.ids import generate_id
from services.common.schemas import CaseState
from services.orchestrator.agents.base import AgentOutput
from services.tools.executor import execute_tool
from services.triage.schemas import TriageResult

NAME = "payments_agent"
SCOPES = ["crm:read", "payments:read", "payments:write", "casemgmt:write"]

FALLBACK_INTENTS = {"chargeback_dispute", "disputed_subscription_renewal", "cashback_not_credited"}


def _first_amount(entities: dict) -> float | None:
    amounts = entities.get("amounts_inr") or []
    return float(amounts[0]) if amounts else None


def handle(db: Session, case: CaseState, ops_event: dict, triage: TriageResult) -> AgentOutput:
    observations: list[dict[str, Any]] = []

    lookup = execute_tool(db, case_id=case.case_id, tool_name="lookup_status",
                           args={"customer_ref": case.customer_ref, "limit": 10}, dry_run=False)
    observations.append({"tool": "lookup_status", "result": lookup})
    customer = lookup.get("customer")
    if customer is None:
        return AgentOutput(proposal=None, observations=observations, tool_calls_used=1)

    transactions = lookup.get("recent_transactions") or []
    entities = triage.extracted_slots

    if triage.intent in ("failed_transaction_refund", "payment_status_update"):
        txn_ids = entities.get("txn_ids") or []
        failed = [t for t in transactions if t["status"] == "FAILED"]
        txn = next((t for t in failed if t["txn_id"] in txn_ids), None) or (failed[0] if failed else None)

        if txn is None:
            proposal = _reply_proposal(case, ops_event,
                                        f"Hi {customer['name']}, we couldn't find a failed transaction matching your query. Routing to our team.",
                                        reasoning="No matching failed transaction found in the system of record; safer to route than guess.")
            return AgentOutput(proposal=proposal, observations=observations, tool_calls_used=1)

        proposal = {
            "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
            "action_type": "issue_refund",
            "args": {"txn_id": txn["txn_id"], "amount_inr": float(txn["amount_inr"]), "customer_ref": case.customer_ref},
            "evidence": [{"type": "transaction", "ref": txn["txn_id"]}],
            "confidence": 0.95, "proposed_by": NAME,
            "reasoning": (f"Transaction {txn['txn_id']} was charged (₹{txn['amount_inr']}) but failed at the gateway "
                          f"(decline_code={txn['decline_code']}) and was never fulfilled — a full refund matches "
                          f"REFUND-POL-2.0."),
        }
        return AgentOutput(proposal=proposal, observations=observations, tool_calls_used=1)

    if triage.intent == "fee_waiver_request":
        amount = _first_amount(entities) or 500.0
        proposal = {
            "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
            "action_type": "waive_fee",
            "args": {"customer_ref": case.customer_ref, "amount_inr": amount},
            "evidence": [{"type": "customer_profile", "ref": case.customer_ref}],
            "confidence": 0.85, "proposed_by": NAME,
            "reasoning": f"Customer requested a fee waiver of ₹{amount}; proposing per the fee waiver policy for their tier.",
        }
        return AgentOutput(proposal=proposal, observations=observations, tool_calls_used=1)

    if triage.intent == "card_unblock_request":
        proposal = {
            "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
            "action_type": "unblock_card", "args": {"customer_ref": case.customer_ref},
            "evidence": [{"type": "customer_profile", "ref": case.customer_ref}],
            "confidence": 0.9, "proposed_by": NAME,
            "reasoning": "Routine PIN-retry card block; unblocking is low-risk and reversible.",
        }
        return AgentOutput(proposal=proposal, observations=observations, tool_calls_used=1)

    # chargeback_dispute / disputed_subscription_renewal / cashback_not_credited
    # and anything else: these need dispute-lifecycle or promo-ledger context
    # this MVP's mocks don't fully model, so route to a human rather than
    # guess at a monetary action.
    proposal = {
        "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
        "action_type": "create_internal_task",
        "args": {"title": f"Manual review: {triage.intent}", "description": ops_event.get("redacted_text", ""), "category": "payments"},
        "evidence": [{"type": "ticket", "ref": ops_event.get("event_id", "")}],
        "confidence": 0.7, "proposed_by": NAME,
        "reasoning": f"Intent '{triage.intent}' needs dispute/ledger context this agent doesn't have reliable access to yet; routing to a human rather than proposing a monetary action on incomplete information.",
    }
    return AgentOutput(proposal=proposal, observations=observations, tool_calls_used=1)


def _reply_proposal(case: CaseState, ops_event: dict, text: str, *, reasoning: str) -> dict:
    return {
        "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
        "action_type": "send_templated_reply", "args": {"ticket_id": ops_event.get("event_id"), "template": text},
        "evidence": [], "confidence": 0.8, "proposed_by": NAME, "reasoning": reasoning,
    }
