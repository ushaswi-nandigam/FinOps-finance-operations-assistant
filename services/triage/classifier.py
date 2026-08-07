"""L3 Stage 1 — `bge-small-en-v1.5` embeddings + logistic regression
(docs/architecture.md §L3). ~45% of volume, ~₹0.0002/case. No LLM call at
this stage — trained by services/triage/train.py against the seeded tickets.

Both the embedding model and the trained classifier are loaded lazily and
cached at module scope: loading fastembed's ONNX model takes real time, and
every ingress request going through this stage would otherwise pay that cost
again.
"""

import pickle
from pathlib import Path
from typing import Any

MODEL_DIR = Path(__file__).resolve().parent

_embedding_model: Any = None
_classifier: Any = None
_label_encoder: Any = None


def _ensure_loaded() -> tuple[Any, Any, Any]:
    global _embedding_model, _classifier, _label_encoder
    if _classifier is None or _label_encoder is None:
        model_path, encoder_path = MODEL_DIR / "model.pkl", MODEL_DIR / "label_encoder.pkl"
        if not model_path.exists() or not encoder_path.exists():
            raise FileNotFoundError(
                f"Triage classifier artifacts missing at {MODEL_DIR}. Run 'python services/triage/train.py' first."
            )
        with open(model_path, "rb") as f:
            _classifier = pickle.load(f)
        with open(encoder_path, "rb") as f:
            _label_encoder = pickle.load(f)
    if _embedding_model is None:
        from fastembed import TextEmbedding

        _embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embedding_model, _classifier, _label_encoder


def classify(text: str) -> tuple[str, float]:
    """Returns (intent, confidence) — confidence is the classifier's own
    max class probability, which is what the cascade compares against the
    0.85 abstention threshold."""
    embedding_model, clf, label_encoder = _ensure_loaded()
    embedding = list(embedding_model.embed([text]))[0]
    probs = clf.predict_proba([embedding])[0]
    idx = int(probs.argmax())
    intent = label_encoder.inverse_transform([idx])[0]
    return str(intent), float(probs[idx])
