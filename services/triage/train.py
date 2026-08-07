"""
Layer 3 Triage Classifier Trainer
Trains a Logistic Regression / LinearSVC classifier over ticket text embeddings produced by fastembed (bge-small-en-v1.5).
Saves model artifacts to services/triage/model.pkl and label_encoder.pkl.
"""

import json
import pickle
from pathlib import Path
from fastembed import TextEmbedding
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

MODEL_DIR = Path(__file__).resolve().parent
DATA_PATH = MODEL_DIR.parent.parent / "data" / "generated" / "tickets.json"


def train_triage_model():
    print("Loading synthetic tickets dataset for triage training...")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Seed data missing at {DATA_PATH}. Run 'python scripts/seed.py' first!")

    with open(DATA_PATH) as f:
        tickets = json.load(f)

    texts = [t["text"] for t in tickets]
    labels = [t["intent"] for t in tickets]

    print(f"Dataset size: {len(texts)} tickets across {len(set(labels))} intents.")

    print("Generating embeddings using fastembed (bge-small-en-v1.5)...")
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    embeddings = list(embedding_model.embed(texts))

    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(labels)
    X = embeddings

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("Training Logistic Regression classifier...")
    clf = LogisticRegression(max_iter=1000, C=1.0)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    f1 = f1_score(y_test, y_pred, average="weighted")
    print(f"[OK] Triage Classifier Training Complete! Weighted F1-score: {f1:.4f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred, target_names=label_encoder.classes_))

    # Save artifacts
    with open(MODEL_DIR / "model.pkl", "wb") as f:
        pickle.dump(clf, f)

    with open(MODEL_DIR / "label_encoder.pkl", "wb") as f:
        pickle.dump(label_encoder, f)

    print(f"Saved artifacts to {MODEL_DIR / 'model.pkl'} and {MODEL_DIR / 'label_encoder.pkl'}")


if __name__ == "__main__":
    train_triage_model()
