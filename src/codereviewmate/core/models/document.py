"""Domain models for document ingestion and retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    ARCHITECTURE = "architecture"
    CODING_STANDARD = "coding_standard"
    PR_DISCUSSION = "pr_discussion"
    REVIEW_HISTORY = "review_history"
    API_DOC = "api_doc"
    ONBOARDING = "onboarding"
    OTHER = "other"


class Document(BaseModel):
    """A document to be ingested."""

    id: Optional[str] = None
    title: str
    content: str
    type: DocumentType = DocumentType.OTHER
    source: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Chunk(BaseModel):
    """A chunk of a document after splitting."""

    id: str
    document_id: str
    content: str
    chunk_index: int
    metadata: dict = Field(default_factory=dict)
    embedding: Optional[list[float]] = None


class ScoredChunk(BaseModel):
    """A chunk with a relevance score."""

    chunk: Chunk
    score: float
    source_document_title: str = ""


class ContextBundle(BaseModel):
    """Bundle of context for review/tutoring."""

    relevant_docs: list[dict] = Field(default_factory=list)
    relevant_reviews: list[dict] = Field(default_factory=list)
    relevant_standards: list[dict] = Field(default_factory=list)
    architecture_constraints: list[str] = Field(default_factory=list)
