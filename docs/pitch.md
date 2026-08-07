# Agentic Financial Operations Assistant — Pitch

## The Problem

Financial operations teams handle customer support, payments, fraud
investigations, and internal process requests — each usually living in a
different system, each needing someone to look up context, decide the right
action, and carry it out by hand. That manual orchestration across systems
slows down routine work and eats time that should go to the cases that
genuinely need human judgement.

## The Solution

An AI agent system that autonomously handles the routine slice of this work
— and is structurally incapable of doing anything risky without a human:

> **The LLM proposes. A deterministic policy engine disposes. A human
> approves anything irreversible. Everything is written to an append-only,
> hash-chained ledger with a plain-language reason.**

Four specialist agents (Support, Payments, Fraud, Internal Ops) plus a
Compliance citation service and a self-check Verifier, each with a narrow
toolset — the Support Agent literally cannot call `issue_refund`, by
construction, not by prompt instruction. A deterministic policy engine (zero
LLM calls, 100% unit-tested) is the only thing that can authorise a
money-moving action, and it re-derives amounts and identities from the
system of record — never from what an LLM extracted from customer text. That
is also the strongest defence against prompt injection: untrusted text can
produce a *proposal*, never an action.

## Value

- **75.0% of cases auto-resolved** with zero human touch, in the measured
  demo run (`docs/cost-model.md`) — capacity released back to analysts for
  the cases that need judgement, not headcount removed.
- **98.6% cost reduction** vs. routing every decision through a frontier
  LLM, from a cheap-first cascade: regex rules and classical ML (LightGBM,
  logistic regression) handle triage and fraud scoring for ₹0; an LLM is
  only reached when those abstain.
- **Zero over-automation** in the golden evaluation set
  (`evals/runner.py`) — the metric that actually matters in finance is not
  "how much did we automate" but "did we ever auto-execute something that
  should have needed a human," and that number is 0, verified, not assumed.
- **Full auditability**: every action *and every decision to escalate
  instead of act* is logged with the same rigour, hash-chained so tampering
  is detectable, exportable as a signed auditor pack in one click.

## Cost per Transaction

₹0.0027 blended cost per decision, measured from real traffic through the
demo instance (`docs/cost-model.md`) — not a projection. At any realistic
transaction volume, this is a rounding error next to the analyst-minutes it
replaces for the auto-resolved slice.

## What's Next

- **Real enterprise integration**: the mock CRM/Payments/CaseMgmt adapters
  (`services/mocks/`) are built behind typed interfaces specifically so a
  real system integration is a swap-the-adapter change, not a rewrite.
- **Richer dispute/chargeback handling**: Payments Agent currently routes
  chargeback disputes and subscription/cashback issues to a human rather
  than proposing an action, because the mock data model doesn't yet carry
  full dispute-lifecycle context — a natural next domain agent capability.
- **A real observability stack** (OpenTelemetry + Langfuse, as
  `docs/architecture.md`'s original spec calls for) once this moves past a
  single-instance demo — the cost/decision fields are already on every
  `DecisionRecord`, so wiring a trace exporter is additive, not a redesign.
- **Nightly retraining loop**: every human approve/reject/modify is already
  a labelled example (`approvals` table); the L12 feedback loop that turns
  those into a retrained triage classifier is scoped but not built in this
  pass.
