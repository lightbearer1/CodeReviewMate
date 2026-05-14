"""Document ingestion pipeline — loading, chunking, and storing documents."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from codereviewmate.core.config.manager import get_config
from codereviewmate.core.context.embedder import get_embedder
from codereviewmate.core.context.vector_store import get_vector_store
from codereviewmate.core.models.document import Chunk, Document, DocumentType

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Splits documents into overlapping chunks for embedding."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, document: Document) -> list[Chunk]:
        """Split a document into overlapping text chunks."""
        text = document.content
        paragraphs = self._split_paragraphs(text)
        chunks: list[Chunk] = []
        current_chunk: list[str] = []
        current_length = 0

        for para in paragraphs:
            para_len = self._estimate_tokens(para)

            if current_length + para_len > self.chunk_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(self._make_chunk(document, chunk_text, len(chunks)))
                # Keep overlap from the end
                overlap_text = self._extract_overlap(current_chunk, self.chunk_overlap)
                current_chunk = [overlap_text] if overlap_text else []
                current_length = self._estimate_tokens(overlap_text) if overlap_text else 0

            current_chunk.append(para)
            current_length += para_len

        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(self._make_chunk(document, chunk_text, len(chunks)))

        if not chunks:
            chunks.append(self._make_chunk(document, document.content, 0))

        return chunks

    def _make_chunk(self, document: Document, content: str, index: int) -> Chunk:
        return Chunk(
            id=str(uuid.uuid4()),
            document_id=document.id or str(uuid.uuid4()),
            content=content,
            chunk_index=index,
            metadata={
                "title": document.title,
                "type": document.type.value,
                "source": document.source,
                "tags": ",".join(document.tags),
                **document.metadata,
            },
        )

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """Split text into paragraph-level blocks."""
        # Split on double newlines, markdown headers, or long single newlines
        blocks = re.split(r"\n\s*\n|(?=\n#+\s)", text)
        return [b.strip() for b in blocks if b.strip()]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token count estimation (~4 chars per token for CJK, ~4 for Latin)."""
        # Simple heuristic: ~4 characters per token
        return max(1, len(text) // 4)

    @staticmethod
    def _extract_overlap(paragraphs: list[str], overlap_tokens: int) -> str:
        """Extract overlap text from the end of existing paragraphs."""
        overlap_chars = overlap_tokens * 4
        combined = "\n\n".join(paragraphs)
        if len(combined) <= overlap_chars:
            return combined
        return combined[-overlap_chars:]


class DocumentIngestor:
    """Orchestrates document loading, chunking, embedding, and storage."""

    def __init__(self):
        config = get_config()
        self._chunker = DocumentChunker(
            chunk_size=config.rag.chunk_size,
            chunk_overlap=config.rag.chunk_overlap,
        )
        self._embedder = get_embedder()
        self._store = get_vector_store()
        self._config = config

    async def ingest(self, document: Document) -> int:
        """Ingest a single document: chunk, embed, store. Returns chunk count."""
        if not document.id:
            document.id = str(uuid.uuid4())

        logger.info("Ingesting document: %s (%s)", document.title, document.type.value)

        chunks = self._chunker.chunk(document)
        if not chunks:
            logger.warning("No chunks generated for document %s", document.title)
            return 0

        texts = [chunk.content for chunk in chunks]
        embeddings = await self._embedder.embed_async(texts, self._config.embedding.batch_size)

        self._store.add_chunks(chunks, embeddings)
        logger.info("Ingested %s: %d chunks", document.title, len(chunks))
        return len(chunks)

    async def ingest_file(
        self,
        file_path: Path,
        doc_type: DocumentType = DocumentType.OTHER,
        tags: Optional[list[str]] = None,
    ) -> int:
        """Ingest a file from disk."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        document = Document(
            title=file_path.stem,
            content=content,
            type=doc_type,
            source=str(file_path),
            tags=tags or [],
        )
        return await self.ingest(document)

    async def ingest_directory(
        self,
        dir_path: Path,
        doc_type: DocumentType = DocumentType.OTHER,
        glob_pattern: str = "*.md",
    ) -> dict[str, int]:
        """Ingest all matching files in a directory."""
        results: dict[str, int] = {}
        for file_path in sorted(dir_path.glob(glob_pattern)):
            try:
                count = await self.ingest_file(file_path, doc_type)
                results[str(file_path)] = count
            except Exception as e:
                logger.error("Failed to ingest %s: %s", file_path, e)
                results[str(file_path)] = -1
        return results

    async def ingest_text(
        self,
        title: str,
        content: str,
        doc_type: DocumentType = DocumentType.OTHER,
        source: str = "",
        tags: Optional[list[str]] = None,
    ) -> int:
        """Ingest text content directly."""
        document = Document(
            title=title,
            content=content,
            type=doc_type,
            source=source,
            tags=tags or [],
        )
        return await self.ingest(document)
