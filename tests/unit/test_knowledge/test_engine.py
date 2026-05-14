"""Tests for knowledge engine."""

from __future__ import annotations

from unittest import mock

import pytest

from codereviewmate.core.knowledge.engine import KnowledgeEngine
from codereviewmate.core.models.review import (
    Issue,
    IssueCategory,
    PreCommitResult,
    ReviewReport,
    Severity,
)


class TestKnowledgeEngine:
    def test_init_with_temp_storage(self, tmp_path):
        storage = str(tmp_path / "graph.json")
        engine = KnowledgeEngine(storage_path=storage)
        assert engine.graph.node_count == 0

    def test_load_empty(self, tmp_path):
        storage = str(tmp_path / "nonexistent.json")
        engine = KnowledgeEngine(storage_path=storage)
        engine.load()  # Should not raise
        assert engine.graph.node_count == 0

    def test_save_and_load(self, tmp_path):
        storage = str(tmp_path / "kg.json")
        engine = KnowledgeEngine(storage_path=storage)
        engine.graph.add_node("Test Node", "concept", "A test concept")
        engine.save()

        engine2 = KnowledgeEngine(storage_path=storage)
        engine2.load()
        assert engine2.graph.node_count == 1

    @pytest.mark.asyncio
    async def test_process_review_extracts_knowledge(self, tmp_path):
        storage = str(tmp_path / "kg.json")
        engine = KnowledgeEngine(storage_path=storage)

        report = ReviewReport(
            pre_commit=PreCommitResult(
                passed=False,
                issues=[
                    Issue(
                        severity=Severity.CRITICAL,
                        category=IssueCategory.SECURITY,
                        title="Hardcoded password",
                        description="Found password in config.py",
                        file_path="config.py",
                        rule_id="no-hardcoded-secrets",
                    ),
                    Issue(
                        severity=Severity.LOW,
                        category=IssueCategory.STYLE,
                        title="Debug print",
                        description="print() at line 5",
                        file_path="app.py",
                        rule_id="no-debug-print",
                    ),
                ],
                checks_run=2,
            ),
        )

        extraction = await engine.process_review(report)
        assert len(extraction.new_nodes) >= 1
        assert engine.graph.node_count >= 1

    @pytest.mark.asyncio
    async def test_process_review_empty(self, tmp_path):
        storage = str(tmp_path / "kg.json")
        engine = KnowledgeEngine(storage_path=storage)

        report = ReviewReport(
            pre_commit=PreCommitResult(passed=True, issues=[], checks_run=1),
        )

        extraction = await engine.process_review(report)
        assert len(extraction.new_nodes) == 0

    def test_query(self, tmp_path):
        storage = str(tmp_path / "kg.json")
        engine = KnowledgeEngine(storage_path=storage)
        engine.load()

        engine.graph.add_node(
            "SQL injection prevention",
            "standard",
            "Always use parameterized queries",
            tags=["security", "sql"],
        )
        engine.graph.add_node(
            "Use logging instead of print",
            "standard",
            "Proper logging with levels",
            tags=["logging", "python"],
        )

        results = engine.query("sql")
        assert len(results) >= 1
        assert "sql" in results[0].label.lower()

    def test_get_stats(self, tmp_path):
        storage = str(tmp_path / "kg.json")
        engine = KnowledgeEngine(storage_path=storage)
        engine.load()

        engine.graph.add_node("S1", "standard", tags=["python", "security"])
        engine.graph.add_node("AP1", "anti_pattern", tags=["security"])

        stats = engine.get_stats()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 0
        assert "standard" in stats["by_type"]
        assert stats["by_type"]["standard"] == 1

    def test_get_standards(self, tmp_path):
        storage = str(tmp_path / "kg.json")
        engine = KnowledgeEngine(storage_path=storage)
        engine.graph.add_node("S1", "standard")
        engine.graph.add_node("AP1", "anti_pattern")
        engine.graph.add_node("P1", "pattern")

        standards = engine.get_standards()
        assert len(standards) == 1
        assert standards[0].label == "S1"

    def test_get_anti_patterns(self, tmp_path):
        storage = str(tmp_path / "kg.json")
        engine = KnowledgeEngine(storage_path=storage)
        engine.graph.add_node("AP1", "anti_pattern")
        engine.graph.add_node("AP2", "anti_pattern")
        engine.graph.add_node("P1", "pattern")

        aps = engine.get_anti_patterns()
        assert len(aps) == 2
