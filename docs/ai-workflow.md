# Agentic FinOps Assistant — AI Workflow Specification

## Overview

The AI Workflow implements a **Plan → Act → Observe → Verify** execution loop using LangGraph, governed by deterministic policy guardrails.

```mermaid
flowchart TD
    A[Ingress: tickets, transcripts, payment webhooks] --> B[Normalise + PII Tokenise]
    B --> C{Triage Cascade}
    C -->|rule match| D[Orchestrator]
    C -->|classifier conf > 0.85| D
    C -->|uncertain| C2[LLM Router] --> D
    D --> E[Support Agent]
    D --> F[Payments Agent]
    D --> G[Fraud Agent]
    D --> H[Internal Ops Agent]
    E & F & G & H --> I[Tool / MCP Layer]
    I --> J[Action Proposal]
    J --> K[Verifier Agent - self check]
    K --> L{Risk & Policy Engine}
    L -->|Tier 0-1| M[Auto Execute]
    L -->|Tier 2| N[Human Approval]
    L -->|Tier 3| O[Dual Approval maker-checker]
    L -->|out of policy| P[Escalate with reason]
    N --> M
    O --> M
    M --> Q[Audit Ledger + Cost Record]
    P --> Q
    Q --> R[Ops Console]
    R --> S[Feedback: approvals become training labels]
    S --> C
```

## Agent Roles & Tiers

1. **Support Agent (T1/T2)**: Handles customer queries, context retrieval, drafting replies.
2. **Payments Agent (T2)**: Reconciles failed transactions, proposes retries or refunds.
3. **Fraud Agent (Classical ML + LLM Narrative)**: LightGBM scores risk features (amount z-score, velocity, geo-ip), NetworkX computes linked graph entities, LLM writes plain-language SHAP memo.
4. **Compliance Advisor Agent (T2)**: RAG search over policy docs (25 clauses) to provide compliance citations.
5. **Verifier Agent (T2/T3)**: Automated self-check evaluating business goals and policy conformance before policy engine gate.

## Execution Bounds & Safety Rules

- **Max tool calls**: 6 per case.
- **Max reasoning revisions**: 3 per case.
- **Budget cap**: max ₹5.00 LLM cost per case.
- **Abstention threshold**: Escalation to human analyst when confidence < 0.85.
