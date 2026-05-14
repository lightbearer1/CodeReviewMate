"""Cross-encoder reranker for improving retrieval precision."""

from __future__ import annotations

import logging
from typing import Optional

from codereviewmate.core.config.manager import get_config
from codereviewmate.core.models.document import ScoredChunk

logger = logging.getLogger(__name__)


class Reranker:
    """Re-ranks retrieved chunks using a cross-encoder for better relevance.

    Falls back gracefully when cross-encoder models are not available.
    Uses a lightweight model (ms-marco-MiniLM) for speed.
    """

    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or self.DEFAULT_MODEL
        self._model = None
        self._available = False
        self._init_model()

    def _init_model(self) -> None:
        try:
            from sentence_transformers import CrossEncoder

            logger.info("Loading cross-encoder: %s", self._model_name)
            self._model = CrossEncoder(self._model_name)
            self._available = True
        except Exception:
            logger.warning(
                "Cross-encoder %s not available. Reranking disabled.",
                self._model_name,
                exc_info=True,
            )
            self._available = False

    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        """Re-rank chunks by cross-encoder relevance scores."""
        if not chunks or not self._available or self._model is None:
            return chunks

        pairs = [(query, chunk.chunk.content) for chunk in chunks]
        try:
            scores = self._model.predict(pairs, show_progress_bar=False)
            for chunk, score in zip(chunks, scores):
                chunk.score = float(score)
            chunks.sort(key=lambda c: c.score, reverse=True)
            logger.debug("Reranked %d chunks", len(chunks))
        except Exception:
            logger.warning("Reranking failed, returning original order", exc_info=True)

        return chunks


_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    """Get the global reranker singleton."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker
