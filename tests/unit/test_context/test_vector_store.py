"""Tests for ChromaDB vector store wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from codereviewmate.core.context.vector_store import VectorStore
from codereviewmate.core.models.document import Chunk


@pytest.fixture
def vector_store(tmp_path: Path):
    """Create a temporary vector store."""
    store = VectorStore(persist_path=tmp_path / "chromadb")
    yield store
    # Cleanup
    try:
        store.delete_collection()
    except Exception:
        pass


class TestVectorStore:
    def test_add_and_count(self, vector_store: VectorStore):
        """Adding chunks should increase the count."""
        assert vector_store.count() == 0

        chunks = [
            Chunk(id="c1", document_id="doc1", content="Hello world", chunk_index=0),
            Chunk(id="c2", document_id="doc1", content="Second chunk", chunk_index=1),
        ]
        embeddings = [[0.1] * 128, [0.2] * 128]

        vector_store.add_chunks(chunks, embeddings)
        assert vector_store.count() == 2

    def test_search_by_similarity(self, vector_store: VectorStore):
        """Search should return scored chunks."""
        chunks = [
            Chunk(
                id="c1",
                document_id="doc1",
                content="Python is a programming language",
                chunk_index=0,
                metadata={"title": "Python Guide"},
            ),
            Chunk(
                id="c2",
                document_id="doc2",
                content="JavaScript is used for web development",
                chunk_index=0,
                metadata={"title": "JS Guide"},
            ),
        ]
        # Simple 3D embeddings for testing
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

        vector_store.add_chunks(chunks, embeddings)

        # Query close to first embedding
        results = vector_store.search([0.9, 0.1, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0].chunk.id == "c1"  # Should be closer
        assert results[0].score > 0

    def test_delete_by_document(self, vector_store: VectorStore):
        """Deleting by document ID should remove all its chunks."""
        chunks = [
            Chunk(id="c1", document_id="doc1", content="A", chunk_index=0),
            Chunk(id="c2", document_id="doc1", content="B", chunk_index=1),
            Chunk(id="c3", document_id="doc2", content="C", chunk_index=0),
        ]
        embeddings = [[0.1] * 128, [0.2] * 128, [0.3] * 128]
        vector_store.add_chunks(chunks, embeddings)

        deleted = vector_store.delete_by_document("doc1")
        assert deleted == 2
        assert vector_store.count() == 1

    def test_list_documents(self, vector_store: VectorStore):
        """Should list unique document IDs."""
        chunks = [
            Chunk(id="c1", document_id="doc-a", content="A", chunk_index=0),
            Chunk(id="c2", document_id="doc-b", content="B", chunk_index=0),
            Chunk(id="c3", document_id="doc-a", content="A2", chunk_index=1),
        ]
        embeddings = [[0.1] * 64, [0.2] * 64, [0.3] * 64]
        vector_store.add_chunks(chunks, embeddings)

        docs = vector_store.list_documents()
        assert sorted(docs) == ["doc-a", "doc-b"]

    def test_delete_nonexistent_document(self, vector_store: VectorStore):
        """Deleting a nonexistent document should return 0."""
        assert vector_store.delete_by_document("nonexistent") == 0

    def test_empty_search(self, vector_store: VectorStore):
        """Search on empty store should return empty list."""
        results = vector_store.search([1.0] * 128)
        assert results == []
