"""
Layer 5 Fraud ML Model Trainer
Trains a LightGBM risk classifier on synthetic transactions.
Features: amount_inr, hour_of_day, merchant_category_code, velocity_1h, new_device_flag.
Outputs: model.pkl in services/fraud_ml/
"""

import json
import pickle
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

MODEL_DIR = Path(__file__).resolve().parent
DATA_PATH = MODEL_DIR.parent.parent / "data" / "generated" / "transactions.json"


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature engineering pipeline for transaction fraud detection."""
    features = pd.DataFrame()
    features["amount_inr"] = df["amount_inr"]

    # Convert timestamp
    timestamps = pd.to_datetime(df["timestamp"])
    features["hour_of_day"] = timestamps.dt.hour

    # Merchant Category One-Hot Encoding
    merchant_dummies = pd.get_dummies(df["merchant_category"], prefix="mcat")
    features = pd.concat([features, merchant_dummies], axis=1)

    # Simulated velocity & device risk features
    features["is_failed"] = (df["status"] == "FAILED").astype(int)
    features["velocity_24h"] = np.random.poisson(lam=2.5, size=len(df))
    features["is_new_device"] = np.random.binomial(n=1, p=0.15, size=len(df))

    return features


def train_fraud_model():
    print("Loading transaction dataset for Fraud ML model training...")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Seed data missing at {DATA_PATH}. Run 'python scripts/seed.py' first!")

    with open(DATA_PATH) as f:
        txns = json.load(f)

    df = pd.DataFrame(txns)
    X = extract_features(df)
    y = df["is_fraud_labeled"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("Training LightGBM Fraud Classifier...")
    model = lgb.LGBMClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=5,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train, y_train)

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba > 0.5).astype(int)

    auc = roc_auc_score(y_test, y_pred_proba)
    print(f"[OK] Fraud ML Training Complete! ROC-AUC Score: {auc:.4f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred))

    # Save model artifact
    with open(MODEL_DIR / "model.pkl", "wb") as f:
        pickle.dump(model, f)

    print(f"Saved fraud model artifact to {MODEL_DIR / 'model.pkl'}")


if __name__ == "__main__":
    train_fraud_model()
