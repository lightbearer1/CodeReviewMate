"""Tests for document chunking."""

from __future__ import annotations

from codereviewmate.core.context.ingestion import DocumentChunker
from codereviewmate.core.models.document import Document, DocumentType


class TestDocumentChunker:
    def test_single_paragraph(self):
        chunker = DocumentChunker(chunk_size=512, chunk_overlap=64)
        doc = Document(
            title="Test",
            content="This is a short document.",
            type=DocumentType.OTHER,
        )
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1
        assert "short document" in chunks[0].content

    def test_multiple_chunks(self):
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)
        content = "\n\n".join(
            [
                "This is paragraph one with some content.",
                "This is paragraph two with more content here.",
                "This is paragraph three with additional content.",
                "This is paragraph four with even more content to split.",
                "This is paragraph five that should also be in a chunk.",
            ]
        )
        doc = Document(title="Long", content=content, type=DocumentType.OTHER)
        chunks = chunker.chunk(doc)
        assert len(chunks) >= 2  # Should be split into multiple chunks

    def test_empty_document(self):
        chunker = DocumentChunker()
        doc = Document(
            title="Empty",
            content="",
            type=DocumentType.OTHER,
        )
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].content == ""

    def test_chunk_metadata_preserved(self):
        chunker = DocumentChunker()
        doc = Document(
            id="doc-123",
            title="Architecture Overview",
            content="The system uses a microservices architecture.",
            type=DocumentType.ARCHITECTURE,
            source="docs/arch.md",
            tags=["architecture", "overview"],
        )
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].document_id == "doc-123"
        assert chunks[0].metadata["title"] == "Architecture Overview"
        assert chunks[0].metadata["type"] == "architecture"

    def test_chunk_overlap(self):
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=30)
        paragraphs = [f"Paragraph {i} with some meaningful text content." for i in range(10)]
        content = "\n\n".join(paragraphs)
        doc = Document(title="Overlap Test", content=content, type=DocumentType.OTHER)
        chunks = chunker.chunk(doc)
        assert len(chunks) > 1

    def test_markdown_headers_split(self):
        chunker = DocumentChunker()
        content = """# Introduction
This is the introduction.

## Getting Started
First steps to get started with the project.

## Advanced Usage
More advanced features and configurations."""
        doc = Document(title="MD Test", content=content, type=DocumentType.ARCHITECTURE)
        chunks = chunker.chunk(doc)
        # Should split on headers or double newlines
        assert len(chunks) >= 1
        assert any("Introduction" in c.content for c in chunks)

    def test_estimate_tokens(self):
        # ~4 chars per token
        assert DocumentChunker._estimate_tokens("hello world") == 2  # 11 chars
        assert DocumentChunker._estimate_tokens("a" * 40) == 10
        assert DocumentChunker._estimate_tokens("") == 1  # min
