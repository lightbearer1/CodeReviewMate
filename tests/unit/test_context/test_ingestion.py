"""Integration tests for document ingestion pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from codereviewmate.core.context.ingestion import DocumentIngestor
from codereviewmate.core.models.document import Document, DocumentType


@pytest.fixture
def mock_embedder():
    """Mock embedder that returns dummy embeddings."""
    mock = MagicMock()
    mock.embed_async = AsyncMock(
        return_value=[[0.1] * 128, [0.2] * 128, [0.3] * 128]
    )
    mock.dimension = 128
    return mock


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    return MagicMock()


class TestDocumentIngestor:
    @patch("codereviewmate.core.context.ingestion.get_vector_store")
    @patch("codereviewmate.core.context.ingestion.get_embedder")
    @patch("codereviewmate.core.context.ingestion.get_config")
    async def test_ingest_document(self, mock_config, mock_get_embedder, mock_get_store):
        """Full ingestion flow should chunk, embed, and store."""
        from codereviewmate.core.models.config import (
            EmbeddingConfig,
            KnowledgeConfig,
            RAGConfig,
            ReviewConfig,
            TeamConfig,
        )

        mock_config.return_value = TeamConfig(
            rag=RAGConfig(chunk_size=512, chunk_overlap=64),
            embedding=EmbeddingConfig(batch_size=32),
            knowledge=KnowledgeConfig(),
            review=ReviewConfig(),
        )

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        mock_embed = MagicMock()
        mock_embed.embed_async = AsyncMock(return_value=[[0.1] * 1024])
        mock_embed.dimension = 1024
        mock_get_embedder.return_value = mock_embed

        ingestor = DocumentIngestor()
        doc = Document(
            title="Test Architecture",
            content="The project follows Domain-Driven Design.\n\n"
                     "Services are organized by bounded context.\n\n"
                     "Each service owns its own data store.",
            type=DocumentType.ARCHITECTURE,
            source="docs/architecture.md",
        )

        count = await ingestor.ingest(doc)
        assert count > 0
        mock_store.add_chunks.assert_called_once()

    @patch("codereviewmate.core.context.ingestion.get_vector_store")
    @patch("codereviewmate.core.context.ingestion.get_embedder")
    @patch("codereviewmate.core.context.ingestion.get_config")
    async def test_ingest_file_not_found(self, mock_config, mock_get_embedder, mock_get_store):
        """Ingesting a nonexistent file should raise FileNotFoundError."""
        ingestor = DocumentIngestor()
        with pytest.raises(FileNotFoundError):
            await ingestor.ingest_file(Path("/nonexistent/file.md"))

    @patch("codereviewmate.core.context.ingestion.get_vector_store")
    @patch("codereviewmate.core.context.ingestion.get_embedder")
    @patch("codereviewmate.core.context.ingestion.get_config")
    async def test_ingest_file(self, mock_config, mock_get_embedder, mock_get_store, tmp_path: Path):
        """Ingesting a real file should work."""
        from codereviewmate.core.models.config import (
            EmbeddingConfig,
            KnowledgeConfig,
            RAGConfig,
            ReviewConfig,
            TeamConfig,
        )

        mock_config.return_value = TeamConfig(
            rag=RAGConfig(chunk_size=512, chunk_overlap=64),
            embedding=EmbeddingConfig(batch_size=32),
            knowledge=KnowledgeConfig(),
            review=ReviewConfig(),
        )

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        mock_embed = MagicMock()
        mock_embed.embed_async = AsyncMock(return_value=[[0.1] * 1024])
        mock_embed.dimension = 1024
        mock_get_embedder.return_value = mock_embed

        # Create a real temp file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Architecture\n\nThe system uses microservices.", encoding="utf-8")

        ingestor = DocumentIngestor()
        count = await ingestor.ingest_file(md_file, DocumentType.ARCHITECTURE)
        assert count > 0
