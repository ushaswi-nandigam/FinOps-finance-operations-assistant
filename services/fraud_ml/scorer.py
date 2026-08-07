"""Inference-time fraud scoring: LightGBM risk score + SHAP attributions for
a single transaction (docs/architecture.md §L5's Fraud Agent detail — "the
decision is a classical model; the LLM writes the explanation"). Reproducible
and sub-millisecond; no LLM call anywhere in this module.
"""

import pickle
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import shap
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.fraud_ml.features import FEATURE_NAMES, build_feature_row

MODEL_DIR = Path(__file__).resolve().parent

_model: Any = None
_explainer: Any = None


def _ensure_loaded() -> tuple[Any, Any]:
    global _model, _explainer
    if _model is None:
        model_path = MODEL_DIR / "model.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"Fraud model missing at {model_path}. Run 'python -m services.fraud_ml.train' first.")
        with open(model_path, "rb") as f:
            _model = pickle.load(f)
        _explainer = shap.TreeExplainer(_model)
    return _model, _explainer


def _customer_stats(db: Session, customer_ref: str, exclude_txn_id: str | None) -> tuple[float, float]:
    row = db.execute(
        text("SELECT AVG(amount_inr) AS mean_amt, STDDEV(amount_inr) AS std_amt FROM transactions "
             "WHERE customer_ref = :ref AND txn_id != :exclude"),
        {"ref": customer_ref, "exclude": exclude_txn_id or ""},
    ).mappings().first()
    mean_amt = float(row["mean_amt"]) if row and row["mean_amt"] is not None else 0.0
    std_amt = float(row["std_amt"]) if row and row["std_amt"] is not None else 0.0
    return mean_amt, std_amt


def _velocity_24h(db: Session, customer_ref: str, timestamp, exclude_txn_id: str | None) -> int:
    row = db.execute(
        text("""SELECT COUNT(*) AS c FROM transactions WHERE customer_ref = :ref AND txn_id != :exclude
                AND timestamp >= :window_start AND timestamp < :ts"""),
        {"ref": customer_ref, "exclude": exclude_txn_id or "", "window_start": timestamp - timedelta(hours=24), "ts": timestamp},
    ).mappings().first()
    return int(row["c"]) if row else 0


def _device_shared_count(db: Session, device_id: str, customer_ref: str) -> int:
    row = db.execute(
        text("SELECT COUNT(DISTINCT customer_ref) AS c FROM transactions WHERE device_id = :dev"),
        {"dev": device_id},
    ).mappings().first()
    distinct_customers = int(row["c"]) if row else 1
    return max(0, distinct_customers - 1)


def score_transaction(db: Session, txn: dict[str, Any]) -> dict[str, Any]:
    """Returns {"risk_score": float, "shap_contributions": {feature: value},
    "top_reasons": [(feature, value), ...]} for one transaction row (as
    returned by services.mocks.payments.PaymentsAdapter)."""
    model, explainer = _ensure_loaded()

    mean_amt, std_amt = _customer_stats(db, txn["customer_ref"], txn.get("txn_id"))
    velocity = _velocity_24h(db, txn["customer_ref"], txn["timestamp"], txn.get("txn_id"))
    device_shared = _device_shared_count(db, txn["device_id"], txn["customer_ref"])

    row = build_feature_row(
        amount_inr=float(txn["amount_inr"]), hour_of_day=txn["timestamp"].hour,
        is_failed=(txn["status"] == "FAILED"), merchant_category=txn["merchant_category"],
        customer_mean_amount=mean_amt, customer_std_amount=std_amt,
        velocity_24h=velocity, device_shared_count=device_shared,
    )
    row_df = pd.DataFrame([row], columns=FEATURE_NAMES)

    risk_score = float(model.predict_proba(row_df)[0][1])
    # SHAP values here are in log-odds space (contribution to the positive
    # class's margin, not the 0-1 probability) — standard for a TreeExplainer
    # on a binary classifier, and exactly what "why did the score move" needs:
    # relative ranking of feature contributions, not an absolute probability delta.
    contributions = explainer(row_df).values[0]

    shap_map = dict(zip(FEATURE_NAMES, [float(v) for v in contributions]))
    top_reasons = sorted(shap_map.items(), key=lambda kv: abs(kv[1]), reverse=True)[:4]

    return {
        "risk_score": risk_score, "shap_contributions": shap_map, "top_reasons": top_reasons,
        "features": dict(zip(FEATURE_NAMES, row)),
    }
