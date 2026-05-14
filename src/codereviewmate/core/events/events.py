"""Event type definitions for the event bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from codereviewmate.core.models.review import ReviewReport


class EventType(str, Enum):
    # Document ingestion events
    DOCUMENT_INGESTED = "document.ingested"
    DOCUMENT_INGESTION_FAILED = "document.ingestion_failed"

    # Review events
    PRE_COMMIT_COMPLETED = "review.pre_commit_completed"
    DEEP_REVIEW_COMPLETED = "review.deep_review_completed"
    REVIEW_COMPLETED = "review.completed"
    REVIEW_FAILED = "review.failed"

    # Knowledge events
    KNOWLEDGE_EXTRACTED = "knowledge.extracted"
    KNOWLEDGE_NODE_ADDED = "knowledge.node_added"
    KNOWLEDGE_EDGE_ADDED = "knowledge.edge_added"
    KNOWLEDGE_GRAPH_UPDATED = "knowledge.graph_updated"

    # Config events
    CONFIG_LOADED = "config.loaded"
    CONFIG_UPDATED = "config.updated"


@dataclass
class Event:
    """A generic event in the system."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReviewCompletedEvent(Event):
    """Emitted when a full review completes."""

    def __init__(self, report: ReviewReport, repo_path: str = "", **kwargs):
        super().__init__(
            type=EventType.REVIEW_COMPLETED,
            data={"report": report, "repo_path": repo_path, **kwargs},
        )


@dataclass
class KnowledgeExtractedEvent(Event):
    """Emitted when knowledge is extracted from a review."""

    def __init__(self, extraction_result: Any, review_id: str = "", **kwargs):
        super().__init__(
            type=EventType.KNOWLEDGE_EXTRACTED,
            data={"extraction": extraction_result, "review_id": review_id, **kwargs},
        )
