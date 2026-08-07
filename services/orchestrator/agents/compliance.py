"""Compliance Agent — read-only, no write tools (docs/architecture.md §L5).
Answers "is this allowed, and under which clause?" with citations, over the
25 numbered policy clauses (services/policy_engine/rules and data/generated/
policies.json are the enforcement + reference copy; this is the searchable
one). Cosine similarity over `fastembed` vectors in a NumPy array — a
25-document corpus doesn't need a vector database (see docs/LEARN.md), so
there's no pgvector/Postgres dependency here despite the "RAG" label.
"""

import json
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

_EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_embedding_model: Any = None


def _get_embedding_model() -> Any:
    global _embedding_model
    if _embedding_model is None:
        from fastembed import TextEmbedding

        _embedding_model = TextEmbedding(model_name=_EMBEDDING_MODEL_NAME)
    return _embedding_model


def index_policies(db: Session) -> int:
    """One-time (re-runnable) indexing job: embeds every policy clause and
    stores the vector in policy_embeddings. Safe to re-run after policies
    change — upserts by policy_id."""
    rows = db.execute(text("SELECT id, title, content FROM policies")).mappings().all()
    model = _get_embedding_model()
    texts = [f"{r['title']}. {r['content']}" for r in rows]
    vectors = list(model.embed(texts))

    for row, vector in zip(rows, vectors):
        db.execute(
            text("""INSERT INTO policy_embeddings (policy_id, embedding, model_name) VALUES (:pid, :emb, :model)
                    ON DUPLICATE KEY UPDATE embedding = :emb, model_name = :model"""),
            {"pid": row["id"], "emb": json.dumps([float(v) for v in vector]), "model": _EMBEDDING_MODEL_NAME},
        )
    return len(rows)


def search(db: Session, query: str, *, top_k: int = 3) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""SELECT p.id, p.title, p.content, p.category, e.embedding FROM policies p
                JOIN policy_embeddings e ON e.policy_id = p.id"""),
    ).mappings().all()
    if not rows:
        return []

    model = _get_embedding_model()
    query_vec = np.array(list(model.embed([query]))[0])
    query_norm = np.linalg.norm(query_vec) or 1.0

    scored = []
    for row in rows:
        doc_vec = np.array(json.loads(row["embedding"]) if isinstance(row["embedding"], str) else row["embedding"])
        doc_norm = np.linalg.norm(doc_vec) or 1.0
        similarity = float(np.dot(query_vec, doc_vec) / (query_norm * doc_norm))
        scored.append({"policy_id": row["id"], "title": row["title"], "content": row["content"],
                        "category": row["category"], "score": similarity})

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:top_k]
