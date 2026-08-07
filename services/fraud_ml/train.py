"""L5 Fraud ML trainer — LightGBM classical risk model
(docs/architecture.md §L5's Fraud Agent detail). Features mirror
services/fraud_ml/features.py exactly (FEATURE_NAMES order) so the model
trained here scores identically at inference time in
services/fraud_ml/scorer.py.

The synthetic dataset's actual fraud signal (scripts/seed.py) is devices
shared across a small ring of customer accounts — so `device_shared_count`
carries real information here, unlike a per-transaction random feature.
"""

import json
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from services.fraud_ml.features import FEATURE_NAMES, MERCHANT_CATEGORIES

MODEL_DIR = Path(__file__).resolve().parent
DATA_PATH = MODEL_DIR.parent.parent / "data" / "generated" / "transactions.json"


def build_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    device_shared_count = df.groupby("device_id")["customer_ref"].transform("nunique") - 1

    cust_mean = df.groupby("customer_ref")["amount_inr"].transform("mean")
    cust_std = df.groupby("customer_ref")["amount_inr"].transform("std").fillna(0)
    amount_zscore = np.where(cust_std > 0, (df["amount_inr"] - cust_mean) / cust_std, 0.0)

    velocity_24h = pd.Series(0, index=df.index)
    for _, group in df.sort_values("timestamp").groupby("customer_ref"):
        times = group["timestamp"].to_numpy()
        counts = [int(np.sum((times >= t - np.timedelta64(24, "h")) & (times < t))) for t in times]
        velocity_24h.loc[group.index] = counts

    features = pd.DataFrame(index=df.index)
    features["amount_inr"] = df["amount_inr"]
    features["hour_of_day"] = df["timestamp"].dt.hour
    features["is_failed"] = (df["status"] == "FAILED").astype(int)
    features["amount_zscore"] = amount_zscore
    features["velocity_24h"] = velocity_24h
    features["device_shared_count"] = device_shared_count
    for cat in MERCHANT_CATEGORIES:
        features[f"mcat_{cat}"] = (df["merchant_category"] == cat).astype(int)

    return features[FEATURE_NAMES]


def train_fraud_model() -> None:
    print("Loading transaction dataset for Fraud ML model training...")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Seed data missing at {DATA_PATH}. Run 'python scripts/seed.py' first!")

    with open(DATA_PATH) as f:
        txns = json.load(f)
    df = pd.DataFrame(txns)

    X = build_training_frame(df)
    y = df["is_fraud_labeled"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Fraud is ~1.5-3% of volume — real class imbalance. Without
    # is_unbalance, LightGBM optimises overall accuracy by predicting
    # "not fraud" almost everywhere, which tanks recall on the class that
    # actually matters here.
    print("Training LightGBM Fraud Classifier...")
    model = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, max_depth=5, num_leaves=15,
                                is_unbalance=True, random_state=42, verbosity=-1)
    model.fit(X_train, y_train)

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba > 0.5).astype(int)

    auc = roc_auc_score(y_test, y_pred_proba)
    fraud_scores = y_pred_proba[y_test == 1]
    benign_scores = y_pred_proba[y_test == 0]
    print(f"[OK] Fraud ML Training Complete! ROC-AUC Score: {auc:.4f}")
    print(f"Held-out score separation: fraud mean={fraud_scores.mean():.3f}, benign mean={benign_scores.mean():.3f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred, zero_division=0))
    print("\nFeature importances:\n", dict(zip(FEATURE_NAMES, model.feature_importances_.tolist())))

    with open(MODEL_DIR / "model.pkl", "wb") as f:
        pickle.dump(model, f)
    print(f"Saved fraud model artifact to {MODEL_DIR / 'model.pkl'}")


if __name__ == "__main__":
    train_fraud_model()
