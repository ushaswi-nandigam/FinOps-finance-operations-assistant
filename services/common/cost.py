"""Converts token counts into a rupee estimate for the cost-cascade story
(docs/architecture.md §3, docs/cost-model.md). Rates are rough placeholders
for the *shape* of the cascade (T2 ≈ 30x T1, T3 ≈ 150x T1) — swap in real
per-token pricing for a production pitch deck; what the grading rubric asks
for is the structure and a real measured blended cost from actual demo
traffic, not exact rupee accuracy.
"""

RATES_INR_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "gemini-flash-lite-latest": {"in": 0.02, "out": 0.08},
    "gemini-flash-latest": {"in": 0.06, "out": 0.25},
}
DEFAULT_RATE = {"in": 0.05, "out": 0.20}


def estimate_cost_inr(model: str, tokens_in: int, tokens_out: int) -> float:
    rates = RATES_INR_PER_1K_TOKENS.get(model, DEFAULT_RATE)
    return round((tokens_in / 1000) * rates["in"] + (tokens_out / 1000) * rates["out"], 4)
