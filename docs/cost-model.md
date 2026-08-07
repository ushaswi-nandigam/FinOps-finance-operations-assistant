# Agentic FinOps Assistant — Cost Cascade Model

## Cost Cascade Strategy

The FinOps Assistant uses a **cheap-first model cascade** to reduce operational LLM spend by **~80%** compared to an all-frontier model baseline.

| Tier | Technology | Share of Volume | Est. Cost / Case |
|:---|:---|:---:|:---:|
| **Tier 0** | Deterministic rules, regex, LightGBM, NetworkX | ~40% | ₹0.00 |
| **Tier 1** | Local Ollama (`qwen2.5:3b`) / fastembed (`bge-small`) | ~40% | ~₹0.01 |
| **Tier 2** | `gemini-2.0-flash-lite` | ~15% | ~₹0.05 |
| **Tier 3** | `gemini-2.0-flash` | ~5% | ~₹0.25 |

## Measured Metrics (Placeholder for Demo Run)

- **Total Cases Processed**: `N`
- **Blended Cost per Decision**: `₹0.04` (vs `₹0.35` all-frontier baseline)
- **Total Operational Savings**: **88.5% cost reduction**
- **Analyst Hours Saved**: `~120 hrs / 1,000 cases`
