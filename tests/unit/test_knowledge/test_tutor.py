"""Tests for intelligent tutor engine."""

from __future__ import annotations

from unittest import mock

import pytest

from codereviewmate.core.knowledge.graph import KnowledgeGraphManager
from codereviewmate.core.knowledge.tutor import TutorEngine
from codereviewmate.core.models.knowledge import NodeType


class TestTutorEngine:
    @pytest.fixture
    def mock_rag(self):
        m = mock.AsyncMock()
        from codereviewmate.core.models.document import ContextBundle
        m.query_context.return_value = ContextBundle()
        return m

    @pytest.fixture
    def graph(self):
        g = KnowledgeGraphManager()
        g.add_node(
            "Use parameterized SQL queries",
            NodeType.STANDARD,
            "Always use parameterized queries to prevent SQL injection",
            tags=["security", "sql", "database"],
        )
        g.add_node(
            "SQL injection via f-strings",
            NodeType.ANTI_PATTERN,
            "Building SQL with f-strings enables injection attacks",
            tags=["security", "sql"],
        )
        g.add_node(
            "Repository pattern",
            NodeType.PATTERN,
            "Encapsulate data access in repository classes",
            tags=["architecture", "database"],
        )
        return g

    def test_synthesize_from_graph(self, graph, mock_rag):
        tutor = TutorEngine(graph=graph)

        answer = tutor._synthesize_from_graph(
            question="How to write SQL queries safely?",
            graph_nodes=graph.search("sql"),
            standards=graph.find_by_type(NodeType.STANDARD),
            anti_patterns=graph.find_by_type(NodeType.ANTI_PATTERN),
        )

        assert "SQL" in answer or "parameterized" in answer.lower()
        assert "##" in answer

    def test_synthesize_empty_graph(self, mock_rag):
        graph = KnowledgeGraphManager()
        tutor = TutorEngine(graph=graph)

        answer = tutor._synthesize_from_graph(
            question="How do I do X?",
            graph_nodes=[],
            standards=[],
            anti_patterns=[],
        )

        assert "未找到" in answer

    def test_suggest_readings(self, graph, mock_rag):
        tutor = TutorEngine(graph=graph)
        nodes = graph.search("sql")
        readings = tutor._suggest_readings(nodes, "How to prevent SQL injection?")
        assert len(readings) > 0

    @pytest.mark.asyncio
    async def test_ask_without_llm(self, graph, mock_rag):
        tutor = TutorEngine(graph=graph)
        tutor._rag = mock_rag

        response = await tutor.ask(
            question="How to write secure database queries?",
            use_llm=False,
        )

        assert response.question == "How to write secure database queries?"
        assert len(response.answer) > 0
        assert len(response.related_nodes) > 0

    @pytest.mark.asyncio
    async def test_ask_empty_graph(self, mock_rag):
        graph = KnowledgeGraphManager()
        tutor = TutorEngine(graph=graph)
        tutor._rag = mock_rag

        response = await tutor.ask(
            question="What patterns should I follow?",
            use_llm=False,
        )

        assert len(response.answer) > 0
        assert response.suggested_readings is not None
