"""Tests for standards query engine."""

from __future__ import annotations

from codereviewmate.core.knowledge.graph import KnowledgeGraphManager
from codereviewmate.core.knowledge.standards import StandardsQuery
from codereviewmate.core.models.knowledge import NodeType


class TestStandardsQuery:
    def setup_method(self):
        self.graph = KnowledgeGraphManager()
        self.graph.add_node(
            "Use parameterized queries",
            NodeType.STANDARD,
            "Always parameterize SQL",
            tags=["security", "sql"],
        )
        self.graph.add_node(
            "Never hardcode secrets",
            NodeType.STANDARD,
            "Use env vars",
            tags=["security", "configuration"],
        )
        self.graph.add_node(
            "SQL injection via f-strings",
            NodeType.ANTI_PATTERN,
            "Bad SQL practice",
            tags=["security", "sql"],
        )
        self.graph.add_node(
            "Repository pattern for DB access",
            NodeType.PATTERN,
            "Use repository pattern",
            tags=["architecture", "database"],
        )
        self.query = StandardsQuery(self.graph)

    def test_search_by_topic(self):
        results = self.query.search("sql")
        assert len(results) >= 1
        # Only standards/rules returned
        assert all(n.type in (NodeType.STANDARD, NodeType.RULE) for n in results)

    def test_get_all_standards(self):
        standards = self.query.get_all_standards()
        assert len(standards) == 2

    def test_get_patterns(self):
        patterns = self.query.get_patterns()
        assert len(patterns) == 1
        assert patterns[0].label == "Repository pattern for DB access"

    def test_get_anti_patterns(self):
        aps = self.query.get_anti_patterns()
        assert len(aps) == 1
        assert aps[0].label == "SQL injection via f-strings"

    def test_get_by_tag(self):
        results = self.query.get_by_tag("security")
        assert len(results) == 3

        results = self.query.get_by_tag("sql")
        assert len(results) == 2

    def test_summarize_topic(self):
        summary = self.query.summarize_topic("security")
        assert summary["found"] >= 2
        assert len(summary["standards"]) >= 1
        assert len(summary["anti_patterns_to_avoid"]) >= 1
