"""Feature engineering shared between training (services/fraud_ml/train.py,
vectorised over the whole seeded dataset) and inference
(services/fraud_ml/scorer.py, one transaction at a time via MySQL queries).
Both paths must produce features in the exact same order — `FEATURE_NAMES`
is the single source of truth for that order.

Features (docs/architecture.md §L5's fraud-agent spec):
  amount z-score vs the customer's own history, velocity in the last 24h,
  a device-sharing signal (this synthetic dataset's actual fraud-ring
  pattern is devices shared across accounts, not per-transaction noise),
  merchant category, hour of day, and whether the transaction failed.
"""

MERCHANT_CATEGORIES = ["ECOM", "TRAVEL", "UTILITIES", "FOOD", "ENTERTAINMENT", "FINANCE"]

FEATURE_NAMES = [
    "amount_inr", "hour_of_day", "is_failed", "amount_zscore",
    "velocity_24h", "device_shared_count",
] + [f"mcat_{c}" for c in MERCHANT_CATEGORIES]


def _one_hot_merchant(category: str) -> list[int]:
    return [1 if category == c else 0 for c in MERCHANT_CATEGORIES]


def build_feature_row(
    *, amount_inr: float, hour_of_day: int, is_failed: bool, merchant_category: str,
    customer_mean_amount: float, customer_std_amount: float, velocity_24h: int, device_shared_count: int,
) -> list[float]:
    amount_zscore = 0.0
    if customer_std_amount > 0:
        amount_zscore = (amount_inr - customer_mean_amount) / customer_std_amount

    return [
        float(amount_inr), float(hour_of_day), float(is_failed), float(amount_zscore),
        float(velocity_24h), float(device_shared_count),
    ] + [float(v) for v in _one_hot_merchant(merchant_category)]
