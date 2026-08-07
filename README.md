<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/LangGraph-0.4-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" alt="LangGraph"/>
<img src="https://img.shields.io/badge/Supabase-2-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase"/>  <img src="https://img.shields.io/badge/Redis-Streams-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis"/>
  <img src="https://img.shields.io/badge/License-Proprietary-lightgrey?style=for-the-badge" alt="License"/>
</p>

<h1 align="center">🏦 Agentic FinOps Assistant</h1>

<p align="center">
  <strong>An AI-powered, multi-agent system for autonomous financial operations — built with deterministic safety guardrails, human-in-the-loop oversight, and full auditability.</strong>
</p>

<p align="center">
  <em>AI Build 2026 · Agentic Financial Ops Track</em>
</p>

---

## 📋 Problem Statement

Financial operations teams in India's digital payments ecosystem face an overwhelming volume of support tickets, payment failures, fraud alerts, disputes, and internal ops requests — often exceeding **thousands per day**. Human analysts spend the majority of their time on repetitive, low-complexity tasks, leaving high-value investigations under-resourced and SLA timers ticking.

### The Core Challenge

> Build an **intelligent, agentic assistant** that can autonomously resolve routine financial operations tasks while maintaining the **trust, safety, and regulatory compliance** that the financial sector demands.

Specifically, the system must:

| Requirement | Description |
|:---|:---|
| **Autonomous Resolution** | Handle 55–70% of incoming cases (status queries, simple refunds, payment retries) without human intervention |
| **Human-in-the-Loop** | Route high-risk, high-value, or ambiguous cases for human approval with a 20-second decision card |
| **Auditability** | Produce a tamper-evident, hash-chained audit trail with plain-language explanations for every decision — including escalations |
| **Privacy & Compliance** | Ensure PII (Aadhaar, PAN, UPI VPA, card numbers) never enters an LLM prompt — aligned with **DPDP Act 2023** and **RBI data-localisation** guidelines |
| **Cost Efficiency** | Demonstrate a measured cost cascade — classical models and rules handle ~80% of work at near-zero cost, with frontier LLMs reserved for the ~5% that truly need them |
| **Explainability** | Every action carries a `reason_plain` generated once and reused everywhere — console, Slack, customer email, auditor export |

---

## 🏗️ Architecture Overview

The system follows a **14-layer architecture** governed by one design thesis:

> *"The LLM proposes. A deterministic policy engine disposes. A human approves anything irreversible. Everything is written to an append-only ledger with a plain-language reason."*

```
 L1   Ingress           → tickets, chat, payments, disputes, internal ops
 L2   Normalise & PII   → canonical OpsEvent + PII tokenisation (Presidio)
 L3   Triage Cascade    → rules → classifier → small LLM → frontier (cheap-first)
 L4   Orchestrator      → LangGraph state machine (Plan → Act → Observe → Verify)
 L5   Specialist Agents → Support · Payments · Fraud · Internal Ops · Verifier
 L6   Tool / MCP Layer  → typed tool registry with risk tiers & idempotency
 L7   Policy Engine     → deterministic YAML rules — NO LLM (the safety spine)
 L8   Human-in-the-Loop → approval console with maker-checker enforcement
 L9   Execution         → saga pattern + dry-run + compensating transactions
 L10  Audit Ledger      → hash-chained, append-only, with cost tracking
 L11  Ops Console       → Next.js dashboard — queue, traces, approvals, cost
 L12  Feedback Loop     → human judgements become training labels
 L13  Security          → RBAC, prompt-injection defence, DPDP/RBI compliance
 L14  Observability     → OpenTelemetry + Langfuse tracing
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|:---|:---|
| **API & Validation** | Python 3.12 · FastAPI · Pydantic v2 |
| **Agent Orchestration** | LangGraph · LangChain |
| **Database** | PostgreSQL 16 + pgvector |
| **Queue / Cache** | Redis Streams |
| **Background Workers** | Celery · arq |
| **Local Models** | Ollama / vLLM |
| **Embeddings** | `bge-small-en-v1.5` (33M params, CPU) |
| **Classical ML** | scikit-learn · LightGBM · XGBoost · SHAP · NetworkX · OR-Tools |
| **PII Detection** | Microsoft Presidio + custom Indian recognisers |
| **LLM Tracing** | Langfuse (self-hosted) · OpenTelemetry |
| **Frontend** | Next.js 14 · Tailwind · shadcn/ui · Recharts |
| **Packaging** | Docker Compose (`make up`) |

---

## 📁 Project Structure

```
finops-agent/
├── requirements.txt                # Python dependencies
├── docs/
│   └── architecture.md             # Full 14-layer architecture specification
├── services/
│   ├── api/                        # FastAPI: ingress, cases, approvals, audit
│   ├── orchestrator/
│   │   ├── agents/                 # support.py · payments.py · fraud.py · ops.py
│   │   │                           # policy.py · verifier.py
│   │   └── prompts/                # Versioned .md prompts, one per agent
│   ├── policy_engine/
│   │   └── rules/                  # Deterministic YAML policy rules
│   ├── tools/                      # MCP servers + tool registry + manifests
│   ├── triage/                     # Rules, classifier, training script
│   ├── fraud_ml/                   # Feature eng, LightGBM, SHAP, NetworkX
│   ├── privacy/                    # Presidio recognisers, tokeniser, PII vault
│   ├── audit/                      # Hash chain, DecisionRecord, export
│   └── mocks/                      # mock-crm · mock-payments · mock-casemgmt
├── web/                            # Next.js ops console
├── evals/                          # Golden eval set, runner, metrics report
└── scripts/                        # seed.py · train_triage.py · demo_driver.py
```

---

## ✅ Current Progress

| Phase | Status | Details |
|:---|:---:|:---|
| Architecture specification | ✅ Complete | Full 14-layer reference architecture documented |
| Project scaffolding | ✅ Complete | Directory structure matching the repository layout |
| Dependency management | 🔄 In Progress | `requirements.txt` created; resolving version constraints |
| Mock services | ⬜ Not Started | mock-crm, mock-payments, mock-casemgmt |
| L1–L2: Ingress & PII | ⬜ Not Started | FastAPI routes, OpsEvent schema, Presidio pipeline |
| L7: Policy engine | ⬜ Not Started | YAML rules DSL, deterministic authoriser |
| L10: Audit ledger | ⬜ Not Started | Hash-chained append-only log |
| L3: Triage cascade | ⬜ Not Started | Rules → classifier → LLM router |
| L4–L5: Orchestrator & agents | ⬜ Not Started | LangGraph state machine, specialist agents |
| L11: Ops console | ⬜ Not Started | Next.js dashboard |
| Seed data generation | ⬜ Not Started | 300 customers, 8K transactions, 400 tickets |
| Golden path demos | ⬜ Not Started | 5 end-to-end scenarios |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 16
- Redis
- Node.js 20+ (for the console)
- Docker & Docker Compose (recommended)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd finops-agent

# Install Python dependencies
pip install -r requirements.txt

# (Coming soon) Start all services
make up
```

---

## 📄 Documentation

- [Architecture Specification](docs/architecture.md) — Full build-ready spec covering all 14 layers

---

## 🎯 Key Differentiators

1. **The policy engine is not an LLM** — financial decisions are structurally impossible to make without passing through a deterministic, unit-testable rules engine
2. **Measured cost cascade** — classical solvers and small models handle ~95% of work; frontier LLMs are reserved for genuine ambiguity
3. **Fraud decided by classical ML, explained by LLM** — XGBoost scores the risk, SHAP explains it, the LLM only narrates
4. **Self-correction on display** — the Verifier Agent catches and corrects mistakes before they reach a human
5. **Prompt injection defence** — untrusted customer text can never directly cause a financial action

---

<p align="center">
  <sub>Built for AI Build 2026 · Agentic Financial Ops Track</sub>
</p>
