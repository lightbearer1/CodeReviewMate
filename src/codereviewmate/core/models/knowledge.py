"""Domain models for knowledge graph."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    CONCEPT = "concept"
    PATTERN = "pattern"
    ANTI_PATTERN = "anti_pattern"
    STANDARD = "standard"
    RULE = "rule"
    EXAMPLE = "example"
    BEST_PRACTICE = "best_practice"


class EdgeType(str, Enum):
    RELATES_TO = "relates_to"
    CONTRADICTS = "contradicts"
    REFINES = "refines"
    EXAMPLE_OF = "example_of"
    DEPENDS_ON = "depends_on"
    SUPERSEDES = "supersedes"


class KnowledgeNode(BaseModel):
    """A node in the knowledge graph."""

    id: str
    label: str
    type: NodeType
    description: str
    source_review_ids: list[str] = Field(default_factory=list)
    source_doc_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeEdge(BaseModel):
    """An edge connecting two knowledge nodes."""

    source_id: str
    target_id: str
    type: EdgeType
    description: str = ""
    weight: float = 1.0
    metadata: dict = Field(default_factory=dict)


class KnowledgeGraph(BaseModel):
    """A knowledge graph containing nodes and edges."""

    nodes: list[KnowledgeNode] = Field(default_factory=list)
    edges: list[KnowledgeEdge] = Field(default_factory=list)
    version: int = 1

    def find_related(self, node_id: str, depth: int = 2) -> list[KnowledgeNode]:
        """Find related nodes up to given depth."""
        visited: set[str] = {node_id}
        frontier = {node_id}
        related: list[KnowledgeNode] = []
        node_map = {n.id: n for n in self.nodes}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for edge in self.edges:
                if edge.source_id in frontier and edge.target_id not in visited:
                    next_frontier.add(edge.target_id)
                elif edge.target_id in frontier and edge.source_id not in visited:
                    next_frontier.add(edge.source_id)
            for nid in next_frontier:
                if nid in node_map:
                    related.append(node_map[nid])
            visited |= next_frontier
            frontier = next_frontier
            if not frontier:
                break

        return related


class KnowledgeExtraction(BaseModel):
    """Result of extracting knowledge from a review."""

    new_nodes: list[KnowledgeNode] = Field(default_factory=list)
    new_edges: list[KnowledgeEdge] = Field(default_factory=list)
    updated_nodes: list[KnowledgeNode] = Field(default_factory=list)
    summary: str = ""


class TutorResponse(BaseModel):
    """Response to a tutoring query."""

    question: str
    answer: str
    sources: list[dict] = Field(default_factory=list)
    related_nodes: list[KnowledgeNode] = Field(default_factory=list)
    suggested_readings: list[str] = Field(default_factory=list)
