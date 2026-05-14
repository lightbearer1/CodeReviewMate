"""Hybrid retriever combining semantic search and keyword matching."""

from __future__ import annotations

import logging
from typing import Optional

from codereviewmate.core.config.manager import get_config
from codereviewmate.core.context.embedder import get_embedder
from codereviewmate.core.context.vector_store import get_vector_store
from codereviewmate.core.models.document import ScoredChunk

logger = logging.getLogger(__name__)


class KeywordRetriever:
    """Simple BM25-like keyword search over chunk text."""

    @staticmethod
    def search(query: str, chunks_text: list[tuple[str, str]], top_k: int = 5) -> list[tuple[str, float]]:
        """Score chunks by keyword overlap with the query.

        Args:
            query: The search query.
            chunks_text: List of (chunk_id, content) tuples.
            top_k: Number of results to return.

        Returns:
            List of (chunk_id, score) sorted by score descending.
        """
        query_terms = set(query.lower().split())
        if not query_terms:
            return []

        scores: list[tuple[str, float]] = []
        for chunk_id, content in chunks_text:
            content_lower = content.lower()
            # Simple TF overlap score
            score = sum(1 for term in query_terms if term in content_lower)
            if score > 0:
                # Normalize by content length to avoid bias toward long chunks
                score = score / max(1, len(content_lower.split()) ** 0.5)
                scores.append((chunk_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class HybridRetriever:
    """Combines semantic (vector) and keyword retrieval with configurable weighting."""

    def __init__(self, alpha: Optional[float] = None):
        config = get_config()
        self._alpha = alpha if alpha is not None else config.rag.hybrid_search_alpha
        self._top_k = config.rag.top_k_retrieval
        self._embedder = get_embedder()
        self._store = get_vector_store()
        self._keyword = KeywordRetriever()

    async def retrieve(self, query: str, top_k: Optional[int] = None) -> list[ScoredChunk]:
        """Hybrid search: alpha * vector + (1-alpha) * keyword."""
        k = top_k or self._top_k
        query_embedding = (await self._embedder.embed_async([query]))[0]

        # Fetch extra from vector search for fusion
        vector_results = self._store.search(query_embedding, top_k=max(k * 3, 10))
        logger.debug("Vector search returned %d results", len(vector_results))

        # Keyword search over all known chunks
        all_chunks = self._get_all_chunks_text()
        keyword_results = self._keyword.search(query, all_chunks, top_k=max(k * 3, 10))
        logger.debug("Keyword search returned %d results", len(keyword_results))

        # Reciprocal rank fusion
        fused = self._fuse(vector_results, keyword_results, k)
        return fused

    def retrieve_sync(self, query: str, top_k: Optional[int] = None) -> list[ScoredChunk]:
        """Synchronous version for non-async contexts."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.retrieve(query, top_k))
        else:
            import concurrent.futures

            future = asyncio.run_coroutine_threadsafe(self.retrieve(query, top_k), loop)
            return future.result()

    def _fuse(
        self,
        vector_results: list[ScoredChunk],
        keyword_results: list[tuple[str, float]],
        top_k: int,
    ) -> list[ScoredChunk]:
        """Reciprocal rank fusion of vector and keyword results."""
        # Build keyword result lookup
        kw_scores: dict[str, float] = {}
        for rank, (chunk_id, score) in enumerate(keyword_results):
            kw_scores[chunk_id] = 1.0 / (rank + 60)  # RRF formula

        # Build fused scores
        fused_scores: dict[str, tuple[ScoredChunk, float]] = {}
        for rank, sc in enumerate(vector_results):
            rrf_vector = 1.0 / (rank + 60)
            rrf_kw = kw_scores.get(sc.chunk.id, 0.0)
            fused = self._alpha * rrf_vector + (1 - self._alpha) * rrf_kw
            fused_scores[sc.chunk.id] = (sc, fused)

        # Include keyword-only results that weren't in vector results
        for rank, (chunk_id, kw_score) in enumerate(keyword_results):
            if chunk_id not in fused_scores:
                rrf_kw = 1.0 / (rank + 60)
                fused = (1 - self._alpha) * rrf_kw
                # Build a minimal ScoredChunk
                sc = ScoredChunk(
                    chunk=self._make_minimal_chunk(chunk_id),
                    score=kw_score,
                )
                fused_scores[chunk_id] = (sc, fused)

        # Sort and return top_k
        sorted_items = sorted(fused_scores.values(), key=lambda x: x[1], reverse=True)
        return [item[0] for item in sorted_items[:top_k]]

    def _get_all_chunks_text(self) -> list[tuple[str, str]]:
        """Get all chunk IDs and text from the vector store for keyword search.

        This is a trade-off: for very large collections, use a separate inverted index.
        For team-scale (thousands of chunks), fetching all is fine.
        """
        try:
            results = self._store._collection.get(include=["documents"])
            ids = results["ids"] or []
            docs = results["documents"] or []
            return list(zip(ids, docs))
        except Exception:
            logger.warning("Failed to fetch all chunks for keyword search", exc_info=True)
            return []

    @staticmethod
    def _make_minimal_chunk(chunk_id: str) -> "codereviewmate.core.models.document.Chunk":  # noqa: F821
        from codereviewmate.core.models.document import Chunk

        return Chunk(id=chunk_id, document_id="", content="", chunk_index=0)
