"""Team standards query engine."""

from __future__ import annotations

from typing import Optional

from codereviewmate.core.knowledge.graph import KnowledgeGraphManager
from codereviewmate.core.models.knowledge import KnowledgeNode, NodeType


class StandardsQuery:
    """Query team coding standards, patterns, and rules."""

    def __init__(self, graph: KnowledgeGraphManager):
        self._graph = graph

    def search(self, topic: str, limit: int = 10) -> list[KnowledgeNode]:
        """Search standards by topic keyword."""
        results = self._graph.search(topic, limit=limit)
        return [n for n in results if n.type in (NodeType.STANDARD, NodeType.RULE)]

    def get_all_standards(self) -> list[KnowledgeNode]:
        """Get all coding standards."""
        return self._graph.find_by_type(NodeType.STANDARD)

    def get_patterns(self) -> list[KnowledgeNode]:
        """Get recommended design patterns."""
        return self._graph.find_by_type(NodeType.PATTERN)

    def get_anti_patterns(self) -> list[KnowledgeNode]:
        """Get anti-patterns to avoid."""
        return self._graph.find_by_type(NodeType.ANTI_PATTERN)

    def get_by_tag(self, tag: str) -> list[KnowledgeNode]:
        """Get standards by tag (e.g., 'security', 'python', 'style')."""
        return self._graph.find_by_tag(tag)

    def get_related(self, node_id: str, depth: int = 2) -> list[KnowledgeNode]:
        """Get nodes related to a specific standard."""
        return self._graph.get_related(node_id, depth)

    def summarize_topic(self, topic: str) -> dict:
        """Summarize what the team knows about a topic."""
        # Search all node types from the graph directly
        nodes = self._graph.search(topic, limit=20)

        standards = [n for n in nodes if n.type == NodeType.STANDARD]
        patterns = [n for n in nodes if n.type == NodeType.PATTERN]
        anti_patterns = [n for n in nodes if n.type == NodeType.ANTI_PATTERN]
        examples = [n for n in nodes if n.type == NodeType.EXAMPLE]

        return {
            "topic": topic,
            "found": len(nodes),
            "standards": [n.label for n in standards],
            "recommended_patterns": [n.label for n in patterns],
            "anti_patterns_to_avoid": [n.label for n in anti_patterns],
            "examples": [n.label for n in examples],
        }
