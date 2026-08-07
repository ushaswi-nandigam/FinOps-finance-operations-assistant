"""Support Agent — cheap tier, read-only + fully reversible tools only
(docs/architecture.md §L5). Answers status queries, drafts templated
replies, routes anything it can't safely resolve to an internal task.

Deliberately makes **no LLM call** for the intents it owns: replies are
template-filled from structured tool results, not generated prose. This is
what makes golden-path scenario 1 ("Where is my refund?") a genuine
no-LLM-in-the-decision-path case (docs/architecture.md §6) rather than an LLM
call that happens to be cheap.
"""

from typing import Any

from sqlalchemy.orm import Session

from services.common.ids import generate_id
from services.common.schemas import CaseState
from services.orchestrator.agents.base import AgentOutput
from services.tools.executor import execute_tool
from services.triage.schemas import TriageResult

NAME = "support_agent"
SCOPES = ["crm:read", "payments:read", "casemgmt:write", "crm:write"]


def _pick_relevant_transaction(transactions: list[dict], entities: dict) -> dict | None:
    if not transactions:
        return None
    txn_ids = entities.get("txn_ids") or []
    if txn_ids:
        for t in transactions:
            if t["txn_id"] in txn_ids:
                return t
    failed = [t for t in transactions if t["status"] == "FAILED"]
    return failed[0] if failed else transactions[0]


def _status_reply(customer: dict, txn: dict | None) -> str:
    if txn is None:
        return f"Hi {customer['name']}, we couldn't find a recent transaction matching your query. Our team will follow up."
    if txn["status"] == "FAILED":
        return (f"Hi {customer['name']}, your payment of ₹{txn['amount_inr']} did not go through "
                f"(reason: {txn['decline_code']}). No amount has been deducted; you're welcome to retry.")
    if txn["status"] == "REFUNDED":
        return f"Hi {customer['name']}, your refund for ₹{txn['amount_inr']} has been processed successfully."
    return f"Hi {customer['name']}, your transaction of ₹{txn['amount_inr']} on {txn['timestamp']} was successful."


def _kyc_reply(customer: dict) -> str:
    status_text = {
        "VERIFIED": "your KYC is verified — no action needed.",
        "PENDING": "your KYC documents are under review; this typically takes up to 3 business days.",
        "REJECTED": "your last KYC submission was rejected. Please re-upload valid documents from the app.",
    }.get(customer["kyc_status"], "we could not determine your KYC status; routing to our team.")
    return f"Hi {customer['name']}, {status_text}"


def handle(db: Session, case: CaseState, ops_event: dict, triage: TriageResult, *, revise: bool = False) -> AgentOutput:
    customer_ref = case.customer_ref
    observations: list[dict[str, Any]] = []
    tool_calls_used = 0

    lookup = execute_tool(db, case_id=case.case_id, tool_name="lookup_status",
                           args={"customer_ref": customer_ref, "limit": 10}, dry_run=False)
    tool_calls_used += 1
    observations.append({"tool": "lookup_status", "result": lookup})
    customer = lookup.get("customer")

    if customer is None:
        return AgentOutput(proposal=None, observations=observations, tool_calls_used=tool_calls_used)

    if triage.intent in ("refund_status_query", "payment_status_update", "failed_transaction_refund"):
        txn = _pick_relevant_transaction(lookup.get("recent_transactions") or [], triage.extracted_slots)
        reply_text = _status_reply(customer, txn)
        evidence = [{"type": "transaction", "ref": txn["txn_id"]}] if txn else []
        reasoning = "Looked up the customer's recent transactions via CRM/payments and answered the status query directly from the system of record — no inference needed."
    elif triage.intent == "kyc_verification_status":
        reply_text = _kyc_reply(customer)
        evidence = [{"type": "customer_profile", "ref": customer_ref}]
        reasoning = "KYC status is a direct CRM field; answered from the system of record."
    else:
        proposal = {
            "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
            "action_type": "create_internal_task",
            "args": {"title": f"Manual follow-up: {triage.intent}", "description": ops_event.get("redacted_text", ""), "category": "support"},
            "evidence": [{"type": "ticket", "ref": ops_event.get("event_id", "")}],
            "confidence": 0.7, "proposed_by": NAME,
            "reasoning": f"Intent '{triage.intent}' isn't one Support Agent can resolve directly with a templated reply; routing to a human-reviewed internal task rather than guessing.",
        }
        return AgentOutput(proposal=proposal, observations=observations, tool_calls_used=tool_calls_used)

    proposal = {
        "proposal_id": generate_id("prop"), "case_id": case.case_id, "domain": case.domain.value,
        "action_type": "send_templated_reply",
        "args": {"ticket_id": ops_event.get("event_id"), "template": reply_text},
        "evidence": evidence, "confidence": 0.97, "proposed_by": NAME, "reasoning": reasoning,
    }
    return AgentOutput(proposal=proposal, observations=observations, tool_calls_used=tool_calls_used)
