# LEARN.md — A Student's Guide to This Codebase

This document is for someone reading the finished repo who wants to
understand *why* it's built this way, not just run it. It's organised by
feature, from the moment a ticket arrives to the moment a decision is
audited. For each piece: what it does, why it exists, the files that
implement it, and every third-party dependency it pulls in with a
plain-language reason it was chosen over the obvious alternative.

It's written last, after the thing was actually built — so it documents real
trade-offs made under real constraints (a specific machine, a specific API
key's rate limits, a specific database the author had on hand), not a
theoretical ideal. `docs/architecture.md` is the original 14-layer reference
spec this project was built against; this document explains where and why
the as-built system diverges from it.

---

## 0. The One-Line Design Thesis

> **The LLM proposes. A deterministic policy engine disposes. A human
> approves anything irreversible. Everything is written to an append-only
> ledger with a plain-language reason.**

Every architectural decision below either implements this sentence or exists
to make it cheap enough to run. If you remember one thing from this repo,
remember that a policy engine with zero LLM calls in it (`services/policy_engine/engine.py`)
is what actually enforces the safety guarantees — not a system prompt asking
an LLM to "please be careful."

---

## 1. Why MySQL, Not Supabase/Postgres

`docs/architecture.md`'s original spec calls for Postgres + pgvector on
Supabase. This build uses **MySQL 8** because that's what was actually
available (a local `MySQL80` Windows service, no Supabase project). The
knock-on decisions from that one constraint:

- **`services/common/db.py`**: plain **synchronous SQLAlchemy + PyMySQL**,
  not an async driver. Async MySQL drivers (`aiomysql`, `asyncmy`) are less
  mature on Windows than `asyncpg` is on Postgres; FastAPI handles sync
  endpoints fine via a threadpool, and a hackathon-scale demo will never hit
  the concurrency ceiling where that matters. Simpler and more reliable
  beats theoretically faster here.
- **No pgvector**: the Compliance Agent's policy search
  (`services/orchestrator/agents/compliance.py`) does cosine similarity in
  plain NumPy over vectors stored as JSON columns. A 25-document corpus does
  not need a vector database — pgvector would be solving a problem this
  project doesn't have.
- **No Supabase Auth / Realtime**: see §8 (Auth) and §9 (Console) below.
- **`db/schema.sql`** is one plain SQL file, applied by
  `scripts/migrate.py`, instead of Alembic. Alembic's original setup was
  wired for Postgres/asyncpg; a single idempotent (`CREATE TABLE IF NOT
  EXISTS`) SQL file is something a judge can read top-to-bottom in two
  minutes, which a migration framework's diff history is not.

One deliberate design choice independent of the MySQL constraint: **most
`case_id` foreign keys were dropped** (`action_proposals`, `risk_decisions`,
`approvals`, `tool_calls` — `decision_records` never had one). A case_id is
treated as a loose correlation identifier, not a hard relational dependency.
This was discovered as a real need while building: the policy engine, tool
layer, and audit ledger all needed to be independently testable *before* the
orchestrator's `cases` table existed to reference. In a system this size,
that decoupling is worth more than referential integrity on an ID that's
already immutable and generated centrally (`services/common/ids.py`).

---

## 2. Ingress & Privacy (L1-L2)

**Files:** `services/api/routers/ingress.py`, `services/privacy/`

**What it does:** one endpoint per channel (ticket, transcript, payment
event, dispute, internal ops). Each does two things only: validate the
envelope, and redact PII before anything is stored as `redacted_text`. It
never interprets content — that's the triage layer's job.

**PII redaction — `services/privacy/recognizers.py`:** regex + checksum
recognisers for PAN, Aadhaar (Verhoeff checksum), card numbers (Luhn
checksum), UPI VPA, IFSC, phone, email. The original spec calls for
Microsoft Presidio + spaCy. This project uses recognisers only, for a
concrete reason: Presidio's own Indian-format support *is* regex + checksum
under the hood — the spaCy dependency buys you general-purpose NER for
detecting names/locations in free text, which this project's PII classes
(all fixed formats) don't need. Skipping it avoids a ~500MB spaCy model
download for no accuracy gain on the formats that actually matter here.

**The vault — `services/privacy/vault.py`:** AES-GCM (via the `cryptography`
package) encrypts real values before they're stored, keyed by a token
namespaced to the source event (`{event_id}__PAN_1`). Detokenisation
(`vault.retrieve`) only ever happens at the tool execution boundary
(`services/tools/`), for fields a tool genuinely needs — never inside a
prompt. This is the concrete, testable claim behind "PII never reaches an
LLM": grep the codebase for calls to `vault.retrieve` and you'll find
exactly where real values re-enter the system, and it's nowhere near a
prompt template.

---

## 3. Triage — the Cheap-First Cascade (L3)

**Files:** `services/triage/`

This is the layer that makes "show a cheap model can replace a constant LLM
call" concrete, not asserted:

| Stage | What decides | Cost |
|---|---|---|
| T0 (`rules.py`) | Regex/keyword rules, source type | ₹0 |
| T1 (`classifier.py`) | `fastembed` embeddings + `sklearn` LogisticRegression | ~₹0 |
| T2/T3 (`llm_router.py`) | Gemini, only when T1's confidence < 0.85 | real cost |

**Why `fastembed` for T1, not sentence-transformers/OpenAI embeddings:**
`fastembed` runs the `bge-small-en-v1.5` model via ONNX Runtime — CPU-fast,
no PyTorch dependency, no API call. It's the difference between T1 being
genuinely free and T1 secretly making a network call.

**A real calibration bug found while building this:** the classifier was
initially trained with `LogisticRegression(C=1.0)` — 100% accuracy on
held-out data, but its own `predict_proba` max rarely cleared the 0.85
abstention threshold (mean confidence ~0.6). That's not a contradiction:
accuracy measures whether the argmax is right, not how confident the model
is in it. Under-regularizing (`C=20.0`, see `services/triage/train.py`) is
safe here specifically because the synthetic intent classes are genuinely
well-separated (distinct vocabulary per template) — for messier real-world
text this would risk overconfidence, but the fix should be calibrated to
*your* data's separability, not copy-pasted. Held-out confidence went from a
mean of ~0.6 to ~0.96 with the same 100% accuracy.

**T2/T3 — `google-genai`, not `google-generativeai`:** the older SDK is
fully deprecated upstream (a `FutureWarning` on every import once you
upgrade past a certain version). `google-genai` is the current one.

**"-latest" model aliases, not dated snapshots:** `gemini-2.0-flash-lite`
returned `429 RESOURCE_EXHAUSTED` with `limit: 0` on this project's API
key's free tier — the dated snapshot's free-tier quota had been zeroed out
in favour of newer models. `gemini-flash-lite-latest` / `gemini-flash-latest`
(rolling aliases Google keeps pointed at a current recommended model) worked
immediately. The lesson generalises: pin dated model versions for
reproducibility in a paper, not for a project whose whole point is staying
runnable.

**No Ollama:** the original spec's T1 used a local `qwen2.5:3b` via Ollama
for "fast local intent parsing." Ollama was never installed on the build
machine. Rather than have the code silently depend on an absent service,
T1 was kept LLM-free entirely (rules + classifier, matching the spec's *own*
original description of T1 before the Ollama detail was added) — arguably
closer to the spec's intent ("save expensive reasoning for high-stakes
decisions") than routing routine intent classification through even a small
LLM would have been.

---

## 4. The Orchestrator (L4)

**Files:** `services/orchestrator/graph.py`, `case_store.py`, `events.py`

A hand-rolled state machine, not LangGraph — the original spec explicitly
allows this ("or a hand-rolled async state machine — LangGraph just gives
you checkpointing and a visual graph for free"). The state machine here is a
short, fixed sequence
(`INTAKE → CONTEXT_GATHER → PLAN → ACT → SELF_VERIFY → RISK_GATE →
[APPROVAL_PENDING] → EXECUTE → RESOLVE|ESCALATE`) with one real branch point
(does it need approval). LangGraph's value is managing *complex, cyclic*
agent control flow; this project's control flow is simple enough that a
~150-line function with explicit `case.status = X; save_case(db, case)`
calls is more legible than a graph library's abstraction over it — and it's
one fewer dependency, with the graph structure fully visible by reading top
to bottom instead of assembled from `add_node`/`add_edge` calls.

**Checkpointing:** every transition writes `case.status` and the full case
state to the `cases` table (`case_store.save_case`) *before* moving to the
next step. This is what makes `APPROVAL_PENDING` genuinely resumable: the
process can die, the case can sit for hours, and `services/orchestrator/resume.py`
picks it back up purely from what's in MySQL — nothing is held in memory
across the wait.

**The verify-and-revise loop:** when the Verifier Agent (§6) returns
`REVISE`, the same domain agent is re-invoked with `revise=True`, up to
`case.max_revisions` (default 3) times. If it's still not `PASS` when that
budget runs out, the loop treats it as equivalent to `REJECT` for the policy
gate — an unresolved `REVISE` is not the same as a `PASS`, and letting a
proposal loop forever would be its own kind of safety hole.

---

## 5. The Domain Agents (L5)

**Files:** `services/orchestrator/agents/{support,payments,fraud,internal_ops}.py`

Four narrow agents instead of one mega-prompt, each with:
- its own `SCOPES` list, checked against the tool registry
  (`services/tools/manifests/registry.py::tools_for_scope`) — the Support
  Agent's scope literally does not include `payments:write`, so it cannot
  call `issue_refund` no matter what a prompt says. Least-privilege by
  construction.
- **no LLM call for Support or Payments.** Both are template/rule-driven:
  look up the system of record, fill in a template, propose a structured
  action. This is deliberate, not a shortcut — it's what makes golden
  scenario 1 ("Where is my refund?") a genuine ₹0.0000, no-LLM-in-the-
  decision-path case, and it means an agent can never be talked into
  fabricating a number that isn't in the transaction record.

**Fraud Agent is the one exception, and the point of the exception:**
`services/fraud_ml/` trains a **LightGBM** classifier (via
`services/fraud_ml/train.py`) on features that mirror what's computable at
inference time — amount z-score vs. the customer's own transaction history,
24h velocity, and a device-sharing count (`services/fraud_ml/features.py`).
**SHAP** (`TreeExplainer`) explains *why* a given score came out the way it
did. **networkx** does connected-components over a customer↔device/IP graph
(`services/fraud_ml/linkage.py`) to find rings a single transaction view
never would. The risk decision — hold or don't — is 100% these three
libraries. The only thing the LLM does (`services/orchestrator/agents/fraud.py::_write_memo`)
is turn the SHAP attributions and the linkage result into a plain-language
memo an approver can read in 20 seconds. Say that split out loud in a demo:
*the decision is a classical model; the LLM only narrates it.*

**A real seed-data bug found while building the fraud model:** the original
`scripts/seed.py` drew every transaction's `device_id` from one shared pool
of 1500 values across 8000 transactions. With that few devices spread over
that many transactions, unrelated customers collided on a shared device by
sheer chance often enough that the deliberately-planted fraud ring was
statistically indistinguishable from noise — `services/fraud_ml/linkage.py`
would report half the customer base as "linked." The fix: each customer now
gets 1-2 *personal* devices (a per-customer namespace), and only the
fraud-ring customers deliberately share a small set of ring devices. Model
ROC-AUC went from 0.68 to 0.82, and the fraud/benign score separation on
held-out data went from ~0.06 to ~0.52 — the model didn't get smarter, the
data actually started reflecting the pattern it was supposed to.

---

## 6. The Verifier Agent — Self-Check (L5b)

**File:** `services/orchestrator/verify.py`

The mandated self-check: every proposal is checked against a small Business
Goals checklist before the risk gate. It's **deterministic, not an LLM
call** — consistent with the "classical model decides" pattern above. A
safety check whose pass/fail depended on an LLM's mood on a given day would
undercut the whole point of having a deterministic policy engine downstream
of it.

The one check that actually catches something real:
**least-privilege amount matching.** If a Payments Agent proposes refunding
a transaction's *full* amount, but the customer's own message names a
*smaller* figure (extracted at ingress by `services/privacy/redactor.py`'s
`amounts_inr` entity), the verifier flags it and hands back a concrete
revision hint. `payments.py`'s `revise=True` path re-derives the smaller
amount from the same entity data the verifier used — it doesn't try to
parse the verifier's natural-language hint, which would be fragile. This is
what makes golden scenario 4 (a full-refund proposal caught and corrected to
a partial one) reliable rather than a scripted-looking demo moment.

---

## 7. The Policy Engine — the Safety Spine (L7)

**File:** `services/policy_engine/engine.py`, `services/policy_engine/rules/*.yaml`

**Zero LLM calls.** Pure functions, fully unit-tested (34 tests covering
every tier boundary and hard gate). This is the one module in the whole
project where "trust me, the prompt says to be careful" is structurally
impossible — you can read `authorise()` top to bottom and see every path an
amount can take.

Two layers, evaluated in order:
1. **Hard gates**, independent of the YAML table: unknown customer,
   exceeded reasoning/cost budget, verifier reject, low confidence, minor/
   flagged customer (forces T3 on any financial action), fraud score > 0.7
   (blocks auto-execute of money-moving actions regardless of amount),
   refund velocity cap. These can't be overridden by a YAML rule — they run
   first and return immediately if triggered.
2. **The YAML rule table** (`rules/*.yaml`) — the tier assignment a business
   user could plausibly edit without touching Python. `{gt, gte, lt, lte,
   in, not_in, eq}` condition operators, first-match-wins.

**Why YAML for the rules specifically:** it's the one place in the system
explicitly meant to be non-developer-editable — a business user changing a
refund threshold shouldn't need to understand Python. Everything else in the
policy engine is plain code because there's no equivalent audience for it.

---

## 8. Tools & Execution (L6, L9)

**Files:** `services/tools/manifests/registry.py`, `services/tools/executor.py`

Every tool an agent can call is declared with a manifest: risk tier,
reversibility, whether it needs idempotency, which scopes can call it. The
original spec suggests building this as MCP servers "for enterprise
architecture points," with a typed registry as the fallback for when time is
short. This project uses the typed registry — the manifest metadata (risk
tier, scopes, idempotency) is what actually matters for the safety story;
wrapping each mock adapter in a separate MCP server process would add
operational surface without changing what's provable about the system.

**Idempotency:** `idempotency_key = sha256(case_id + tool_name + canonical_args)`.
A real bug surfaced while building this: dry-run calls (used to show a
projected result on the approval card before a human decides) were
initially being recorded with the *same* idempotency key the real execution
would later use — so the real execution's `INSERT` collided with its own
dry-run's row. Fix: dry-runs never touch the `tool_calls` table at all; only
a real (`dry_run=False`) execution is idempotency-tracked. This is what
makes double-clicking "Approve" in the console safe — verified directly in
`tests/unit/tools/test_executor.py`.

---

## 9. The Audit Ledger (L10)

**File:** `services/audit/ledger.py`

Append-only, hash-chained: `entry_hash = sha256(prev_hash + canonical_json(entry))`,
one global chain across every case (not per-case) so a single `verify_chain()`
pass proves the *entire* ledger's integrity, not just one slice of it.
Tamper-evident without needing a blockchain — this is the same mechanism a
blockchain uses for its own tamper-evidence, without the distributed-
consensus machinery a single-writer audit log doesn't need.

**A subtle, real bug here:** the `timestamp` column was originally plain
`DATETIME`, which MySQL truncates to whole seconds and stores without
timezone info. The hash is computed over the timestamp's ISO string — so
every recomputation during `verify_chain()` used a *different* string than
the one used when the row was written (microseconds and the `+00:00` suffix
both silently dropped on the round trip), and every single entry looked
tampered with, always, even freshly written ones. Fixed by widening the
column to `DATETIME(6)` (microsecond precision) and canonicalising to
naive-UTC (stripping tzinfo, which the column can't store anyway) on both
the write and the verify path. The lesson: a hash chain's correctness
depends on the *exact bytes* you hash matching the exact bytes you get back
from storage — "close enough" formatting is a broken hash chain that just
hasn't been tested yet.

**Escalations are logged with identical rigour to executed actions** — same
function (`record_decision`), same fields, nothing skipped for the "we chose
not to act" path. This is called out explicitly because it's exactly where
teams cut corners under time pressure, and the brief specifically asks for it.

---

## 10. Human-in-the-Loop Approvals (L8)

**Files:** `services/orchestrator/approvals.py`, `services/api/routers/approvals.py`

Approval slots (1 for `NEEDS_APPROVAL`, 2 for `DUAL_APPROVAL`) are created
from the policy engine's own `required_approvers` field — the UI never
decides how many approvals a case needs.

**Maker != checker is a database constraint, not application logic:**
`UNIQUE(proposal_id, approver_id)` on the `approvals` table. When the second
of two dual-approval slots is updated to the *same* `approver_id` as the
first, MySQL raises an `IntegrityError` — caught in `decide_approval` and
turned into a clear 409 response, not a 500. This matters because it means
the guarantee holds even if a future code change forgets to check for it in
Python; the database itself refuses the write.

---

## 11. Auth (L13, RBAC)

**Files:** `services/auth/security.py`, `services/api/routers/auth.py`

Hand-rolled JWT (`PyJWT`) + `bcrypt` password hashing. No Supabase Auth (see
§1) — this is the minimal thing that provides a real login, a role on the
token (`viewer/ops_agent/approver/supervisor/auditor`), and — the part that
actually matters structurally — a stable `username` to pass as `approver_id`
on approval decisions, which is what the maker≠checker database constraint
above enforces against. `scripts/seed_users.py` creates one demo account per
role.

---

## 12. The React Console (L11)

**Files:** `web/src/`

React + Vite + TypeScript + Tailwind — a project constraint, not a spec
deviation the author chose (the original spec calls for Next.js). Four
screens: Live Queue, Case Trace (the demo centrepiece — the full agent-
reasoning timeline in one view), Approval Inbox, Cost & Impact Dashboard.

**Polling, not WebSocket/SSE:** every list/detail view refetches every 4-5
seconds (`web/src/lib/usePolling.ts`). This is the simplest thing that reads
as "live" in a demo. A WebSocket/SSE layer would need its own reconnection
handling, server-side pub/sub wiring, and testing — real engineering cost
for a improvement (sub-second vs. 4-second latency) nobody watching a demo
would notice.

**A real bug found by actually driving the console in a browser, not just
reading the code:** `listCases({status: undefined})` was serialized via
`new URLSearchParams(params)`, which stringifies `undefined` as the literal
text `"undefined"` — so every request was `GET /cases?status=undefined`,
which matched nothing, and the queue silently showed zero cases despite the
database having dozens. No test caught this because the backend endpoint
correctly returns `200 []` for a nonexistent status — the bug was entirely
in how the frontend built the query string. This is the specific argument
for "test UI changes in an actual browser": a passing backend test suite and
a clean TypeScript compile both said nothing was wrong.

A second bug the same browser session caught: the Approval Inbox guessed a
proposal's risk tier from `amount_inr > 25000`, which is meaningless for a
non-refund proposal like `place_fraud_hold` (its args have no
`amount_inr` at all) — it always showed T2 regardless of the real tier.
Fixed by having `GET /approvals` return the case's actual
`risk_decision.tier` instead of asking the frontend to reconstruct it.

---

## 13. Evals (L12)

**Files:** `evals/generate_golden_set.py`, `evals/runner.py`

81 frozen scenarios: 72 triage-routing cases (text → expected intent/domain),
4 real prompt-injection attempts, 5 full-pipeline tier/outcome cases. `make
eval` runs all of them and exits non-zero on regression — usable as a CI
gate on policy or prompt changes.

**The injection check was wrong on the first pass**, and fixing it is worth
understanding: the naive version flagged *any* `AUTO_EXECUTE` outcome on an
injection-triggered case as a violation. But a harmless auto-executed
template reply isn't a violation — Support and Payments agents structurally
cannot call `issue_refund` without the proposal passing through the policy
engine regardless of what the ticket text says. The actual claim to verify
is narrower and more precise: an injected instruction must never cause a
*money-moving* action (`issue_refund`, `waive_fee`, `place_fraud_hold`, ...)
to auto-execute. Checking the coarse thing produced false positives that
would have hidden a real regression in the noise; checking the precise
thing is both correct and a stronger, more specific claim about what the
system actually guarantees.

---

## 14. What Was Cut, and Why That's a Legitimate Choice

Every one of these is in the original `docs/architecture.md` spec and
deliberately not built here, not overlooked:

| Cut | Original spec | Why |
|---|---|---|
| Redis Streams + Celery/arq | Background queue + workers | FastAPI `BackgroundTasks`/synchronous processing is enough at demo volume; three fewer moving infrastructure pieces |
| Presidio + spaCy | PII detection | Regex + checksum recognisers cover this project's fixed PII formats exactly as well, without a ~500MB model download |
| LangGraph | Agent orchestration | The control flow here is a short fixed sequence with one branch — a hand-rolled state machine is more legible than a graph-library abstraction over something this simple |
| MCP servers | Tool integration surface | A typed manifest registry carries the same safety metadata (risk tier, scopes, idempotency) without separate server processes |
| Langfuse / OpenTelemetry | LLM tracing | Cost/token fields live directly on every `DecisionRecord`; the dashboard reads them straight from the audit ledger instead of a separate tracing backend |
| Supabase (Auth + Realtime + Postgres) | Data/auth platform | MySQL was what was actually available; hand-rolled JWT auth and polling cover the same user-facing needs |
| Full saga/compensating-transaction framework | Multi-step rollback | Idempotency keys + dry-run cover the demo's actual safety claim (double-click Approve is safe) without building a general saga engine |

The throughline: every cut trades *generality this project doesn't need* for
*fewer moving pieces to explain and get right*. Nothing here makes the
safety guarantees weaker — the policy engine, the audit ledger, and the
maker≠checker constraint are all exactly as strict as the original spec
describes them.
