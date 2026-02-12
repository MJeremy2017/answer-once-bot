"""Embedding model: same model for indexing and querying."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

_model: Any = None


def get_model():
    """Lazy-load sentence-transformers model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded embedding model all-MiniLM-L6-v2")
        except Exception as e:
            logger.exception("Failed to load embedding model: %s", e)
            raise
    return _model


def embed(text: str) -> list[float]:
    """Return embedding vector for text. Same model for index and query."""
    if not text or not text.strip():
        return get_model().encode(" ", normalize_embeddings=True).tolist()
    return get_model().encode(text.strip(), normalize_embeddings=True).tolist()
