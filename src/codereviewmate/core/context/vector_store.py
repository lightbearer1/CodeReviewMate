"""ChromaDB vector store wrapper for document storage and retrieval."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from codereviewmate.core.models.document import Chunk, Document, DocumentType, ScoredChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """Wrapper around ChromaDB for document chunk storage and semantic search."""

    DEFAULT_COLLECTION = "codereviewmate_docs"

    def __init__(self, persist_path: Optional[Path] = None):
        persist_dir = str(persist_path or Path.cwd() / ".codereviewmate" / "chromadb")
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.DEFAULT_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("VectorStore initialized at %s", persist_dir)

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Add chunks with their embeddings to the store."""
        if not chunks:
            return

        ids = [chunk.id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [
            {
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                **chunk.metadata,
            }
            for chunk in chunks
        ]

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info("Added %d chunks to vector store", len(chunks))

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: Optional[dict] = None,
    ) -> list[ScoredChunk]:
        """Semantic search for chunks closest to the query embedding."""
        where_filter = None
        if filter_metadata:
            where_filter = filter_metadata

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        scored_chunks: list[ScoredChunk] = []
        if not results["ids"] or not results["ids"][0]:
            return scored_chunks

        for i, chunk_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
            score = 1.0 - distance  # cosine distance to similarity

            chunk = Chunk(
                id=chunk_id,
                document_id=metadata.get("document_id", ""),
                content=results["documents"][0][i] if results["documents"] else "",
                chunk_index=metadata.get("chunk_index", 0),
                metadata=metadata,
            )
            scored_chunks.append(ScoredChunk(chunk=chunk, score=score))

        return scored_chunks

    def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks belonging to a document. Returns count of deleted chunks."""
        existing = self._collection.get(
            where={"document_id": document_id},
            include=["metadatas"],
        )
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])
            logger.info("Deleted %d chunks for document %s", len(existing["ids"]), document_id)
            return len(existing["ids"])
        return 0

    def delete_collection(self) -> None:
        """Delete the entire collection."""
        self._client.delete_collection(self.DEFAULT_COLLECTION)
        self._collection = self._client.get_or_create_collection(
            name=self.DEFAULT_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Collection reset")

    def count(self) -> int:
        """Return the number of chunks in the store."""
        return self._collection.count()

    def list_documents(self) -> list[str]:
        """Return unique document IDs in the store."""
        results = self._collection.get(include=["metadatas"])
        doc_ids: set[str] = set()
        if results["metadatas"]:
            for m in results["metadatas"]:
                if "document_id" in m:
                    doc_ids.add(m["document_id"])
        return sorted(doc_ids)


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the global vector store singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
