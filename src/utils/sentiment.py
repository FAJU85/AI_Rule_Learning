"""Sentiment analysis utility using a DistilBERT-based model.

Returns scores in the range [-1, 1]:
  -1 = very negative
   0 = neutral
  +1 = very positive
"""

from __future__ import annotations

from src.utils.logger import get_logger

logger = get_logger(__name__)

_pipeline: object | None = None
_MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"


def _get_pipeline():
    """Lazy-load the sentiment pipeline as a module-level singleton."""
    global _pipeline
    if _pipeline is None:
        try:
            from transformers import pipeline  # type: ignore

            logger.info("Loading sentiment model", extra={"model": _MODEL_NAME})
            _pipeline = pipeline(
                "sentiment-analysis",
                model=_MODEL_NAME,
                truncation=True,
                max_length=512,
            )
            logger.info("Sentiment model loaded")
        except Exception as exc:
            logger.error("Failed to load sentiment model", extra={"error": str(exc)})
            raise
    return _pipeline


def analyze(text: str) -> float:
    """Return a sentiment score in [-1, 1] for *text*.

    Positive label → positive score, Negative label → negative score.
    The raw confidence [0, 1] from the model is mapped to [-1, 1].
    """
    if not text or not text.strip():
        return 0.0

    try:
        pipe = _get_pipeline()
        result = pipe(text[:512])[0]  # type: ignore[index]
        label: str = result["label"].upper()
        score: float = float(result["score"])

        # Map POSITIVE → [0, 1], NEGATIVE → [-1, 0]
        if label == "POSITIVE":
            return score
        else:
            return -score
    except Exception as exc:
        logger.warning("Sentiment analysis failed", extra={"error": str(exc)})
        return 0.0


def sentiment_delta(before: float, after: float) -> float:
    """Return the change in sentiment (after - before), clamped to [-2, 2]."""
    return max(-2.0, min(2.0, after - before))
