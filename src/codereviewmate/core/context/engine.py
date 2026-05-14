"""RAG Engine — orchestrates document ingestion, retrieval, and context assembly."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from codereviewmate.core.config.manager import get_config
from codereviewmate.core.context.ingestion import DocumentIngestor
from codereviewmate.core.context.reranker import get_reranker
from codereviewmate.core.context.retriever import HybridRetriever
from codereviewmate.core.context.vector_store import get_vector_store
from codereviewmate.core.models.document import ContextBundle, DocumentType, ScoredChunk

logger = logging.getLogger(__name__)


class RAGEngine:
    """Orchestrates the full RAG pipeline: ingest → retrieve → rerank → assemble context."""

    def __init__(self):
        self._ingestor = DocumentIngestor()
        self._retriever = HybridRetriever()
        self._reranker = get_reranker()
        self._store = get_vector_store()
        self._config = get_config()

    async def ingest_document(self, file_path: str | Path, doc_type: str = "other") -> int:
        """Ingest a single document file into the knowledge base."""
        path = Path(file_path)
        dt = DocumentType(doc_type) if doc_type else DocumentType.OTHER
        return await self._ingestor.ingest_file(path, dt)

    async def ingest_text(
        self,
        title: str,
        content: str,
        doc_type: str = "other",
        source: str = "",
    ) -> int:
        """Ingest raw text into the knowledge base."""
        dt = DocumentType(doc_type) if doc_type else DocumentType.OTHER
        return await self._ingestor.ingest_text(title, content, dt, source)

    async def ingest_directory(
        self,
        dir_path: str | Path,
        doc_type: str = "architecture",
        glob_pattern: str = "*.md",
    ) -> dict[str, int]:
        """Ingest all matching files from a directory."""
        path = Path(dir_path)
        dt = DocumentType(doc_type) if doc_type else DocumentType.ARCHITECTURE
        return await self._ingestor.ingest_directory(path, dt, glob_pattern)

    async def query_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        doc_types: Optional[list[str]] = None,
    ) -> ContextBundle:
        """Retrieve relevant context for a review query or tutoring question."""
        k = top_k or self._config.rag.top_k_retrieval

        chunks = await self._retriever.retrieve(query, top_k=k)

        if self._config.rag.rerank_enabled:
            chunks = self._reranker.rerank(query, chunks)

        # Filter by document type if specified
        if doc_types:
            chunks = [c for c in chunks if c.chunk.metadata.get("type") in doc_types]

        # Assemble context bundle
        relevant_docs: list[dict] = []
        relevant_standards: list[dict] = []
        architecture_constraints: list[str] = []

        for sc in chunks[:k]:
            doc_info = {
                "title": sc.chunk.metadata.get("title", "Unknown"),
                "type": sc.chunk.metadata.get("type", ""),
                "content": sc.chunk.content,
                "score": sc.score,
                "source": sc.chunk.metadata.get("source", ""),
            }

            chunk_type = sc.chunk.metadata.get("type", "")
            if chunk_type in ("architecture",):
                relevant_docs.append(doc_info)
                if sc.chunk.content:
                    architecture_constraints.append(sc.chunk.content[:200])
            elif chunk_type in ("coding_standard", "standard"):
                relevant_standards.append(doc_info)
            else:
                relevant_docs.append(doc_info)

        logger.info(
            "Context assembled: %d docs, %d standards, %d constraints",
            len(relevant_docs),
            len(relevant_standards),
            len(architecture_constraints),
        )

        return ContextBundle(
            relevant_docs=relevant_docs,
            relevant_standards=relevant_standards,
            architecture_constraints=architecture_constraints,
        )

    async def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[ScoredChunk]:
        """Raw search without context assembly (for debugging / exploration)."""
        chunks = await self._retriever.retrieve(query, top_k=top_k)
        if self._config.rag.rerank_enabled:
            chunks = self._reranker.rerank(query, chunks)
        return chunks[:top_k]

    def stats(self) -> dict:
        """Return statistics about the knowledge base."""
        return {
            "total_chunks": self._store.count(),
            "documents": self._store.list_documents(),
        }

    def reset(self) -> None:
        """Clear all data from the vector store."""
        self._store.delete_collection()
        logger.info("RAG engine reset — all data cleared")


_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    """Get the global RAG engine singleton."""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
