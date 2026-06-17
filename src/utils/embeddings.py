"""Text embedding utility using all-MiniLM-L6-v2.

Provides a module-level singleton for the SentenceTransformer model and a
cosine_similarity helper for comparing embedding vectors.
"""
from __future__ import annotations

from typing import List
from typing import Optional

import numpy as np

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_model: Optional[object] = None


def _get_model():
    """Lazy-load the SentenceTransformer model as a module-level singleton."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model_name = settings.EMBEDDING_MODEL
            logger.info("Loading embedding model", extra={"model": model_name})
            _model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded")
        except Exception as exc:
            logger.error("Failed to load embedding model", extra={"error": str(exc)})
            raise
    return _model


def embed(text: str) -> List[float]:
    """Return a normalised embedding vector for *text*."""
    if not text or not text.strip():
        return []

    try:
        model = _get_model()
        vector = model.encode(text, normalize_embeddings=True)  # type: ignore[attr-defined]
        return vector.tolist()
    except Exception as exc:
        logger.warning("Embedding failed", extra={"error": str(exc)})
        return []


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Return normalised embedding vectors for a list of texts."""
    if not texts:
        return []

    try:
        model = _get_model()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)  # type: ignore[attr-defined]
        return [v.tolist() for v in vectors]
    except Exception as exc:
        logger.warning("Batch embedding failed", extra={"error": str(exc)})
        return [[] for _ in texts]


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Return the cosine similarity between two embedding vectors in [0, 1].

    Returns 0.0 if either vector is empty or all-zero.
    """
    if not vec_a or not vec_b:
        return 0.0

    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))
