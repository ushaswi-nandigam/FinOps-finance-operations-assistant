# Agentic FinOps Assistant — Cost Cascade Model

## Cost Cascade Strategy

The FinOps Assistant uses a **cheap-first model cascade**: cheap/deterministic
stages handle as much volume as they can, and each case only escalates to a
more expensive stage when the cheaper one couldn't decide with confidence.

| Tier | Technology | Purpose |
|:---|:---|:---|
| **T0** | Regex rules, deterministic policy engine | Triage for known patterns, all authorisation decisions |
| **T1** | `fastembed` (`bge-small-en-v1.5`) + logistic regression, LightGBM + SHAP + networkx | Intent classification, fraud scoring — no LLM call |
| **T2** | `gemini-flash-lite-latest` | Routine agent tool-calling, triage fallback, fraud memo narration |
| **T3** | `gemini-flash-latest` | Ambiguous triage, complex fraud narratives |

This differs from the original planning doc (`docs/architecture.md`) in two
ways, both explained in `docs/LEARN.md`: **no Ollama** (not installed on the
build machine — T1 stays genuinely LLM-free instead of silently depending on
a local model server that isn't there), and **"-latest" rolling model
aliases** instead of dated snapshots like `gemini-2.0-flash-lite`, which
returned `429 RESOURCE_EXHAUSTED` on this project's free-tier key.

## Measured Results

These numbers come from `python scripts/demo_driver.py` (the 5 golden-path
scenarios from `docs/architecture.md` §6) plus `python evals/runner.py` (the
golden set's 5 additional full-pipeline scenarios) run back-to-back against
a freshly seeded database, read back via `GET /dashboard/summary`
(`services/orchestrator/dashboard.py`) — **measured from real traffic
through this instance, not assumed.** Reproduce it yourself:

```bash
make load-seed
python scripts/index_policies.py
python scripts/demo_driver.py
python evals/runner.py
curl http://localhost:8000/dashboard/summary
curl http://localhost:8000/audit/verify
```

| Metric | Measured value |
|:---|:---|
| Total cases processed | 14 |
| Blended cost per decision | ₹0.0027 |
| Naive all-frontier baseline (see below) | ₹0.19 |
| **Cost reduction vs. all-frontier baseline** | **98.6%** |
| Auto-resolution rate (zero human touch) | 75.0% |
| Approval override rate (rejected/sent back) | 0.0% |
| Audit ledger integrity | ✅ valid, 16 entries, hash chain verified (`GET /audit/verify`) |
| Cases by triage route stage | T1_CLASSIFIER: 2 · T2_LLM: 3 · T3_LLM_UNAVAILABLE: 9 |
| Cost by risk tier | T0: ₹0.000 (4 cases) · T1: ₹0.000 (2) · T2: ₹0.025 (4) · T3: ₹0.013 (4) |

The **naive all-frontier baseline** (`services/orchestrator/dashboard.py`)
estimates what every one of these cases would have cost if it had gone
through the frontier tier's per-token rate instead of the cascade — the
structure that matters is "cheap stages absorb most volume," not the exact
rupee figure, which depends on whatever rates you plug into
`services/common/cost.py`.

`T3_LLM_UNAVAILABLE` shows up because the eval and demo runs in this
repository's development history made enough rapid Gemini calls to hit the
key's free-tier rate limit — the cascade's fallback path (return the
classifier's best guess rather than fail the request) handled it correctly.
That is itself a small piece of the cost story: most volume never needs the
rate-limited expensive tier at all.

## Human-Time Story

Cost per decision is only meaningful next to analyst time saved. A single
Payments Agent auto-resolution (`lookup_status` + `send_templated_reply`,
scenario 1) replaces what would otherwise be a manual CRM + payments lookup
— call it 3-5 minutes of analyst time at a loaded hourly cost, against a
₹0.0000-₹0.0082 system cost per case in the measured run above. At the
59.5% auto-resolution rate measured here, that is the volume an analyst team
never has to touch by hand.
