"""Tests for domain models."""

from __future__ import annotations

from codereviewmate.core.models.knowledge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)
from codereviewmate.core.models.review import (
    Issue,
    IssueCategory,
    Patch,
    PreCommitResult,
    ReviewReport,
    Severity,
)


class TestReviewModels:
    def test_issue_creation(self):
        issue = Issue(
            severity=Severity.HIGH,
            category=IssueCategory.SECURITY,
            title="Hardcoded secret",
            description="Found hardcoded password",
            file_path="src/app.py",
            line_start=15,
            auto_fixable=True,
        )
        assert issue.severity == Severity.HIGH
        assert issue.auto_fixable is True

    def test_review_report_aggregation(self):
        pre_commit = PreCommitResult(
            passed=False,
            issues=[
                Issue(
                    severity=Severity.LOW,
                    category=IssueCategory.STYLE,
                    title="Style issue",
                    description="Missing docstring",
                    file_path="a.py",
                )
            ],
        )
        report = ReviewReport(pre_commit=pre_commit)
        assert report.passed is False
        assert len(report.all_issues) == 1

    def test_patch_generation(self):
        patch = Patch(
            issue_id="issue-1",
            file_path="src/app.py",
            original_lines="password = 'secret'\n",
            fixed_lines="# TODO: use env var\n",
            unified_diff="@@ -1 +1 @@\n-password = 'secret'\n+# TODO: use env var\n",
        )
        assert "secret" in patch.original_lines


class TestKnowledgeModels:
    def test_node_creation(self):
        node = KnowledgeNode(
            id="node-1",
            label="Repository Pattern",
            type=NodeType.PATTERN,
            description="Use repository pattern for data access",
            tags=["architecture", "data-access"],
        )
        assert node.type == NodeType.PATTERN
        assert len(node.tags) == 2

    def test_graph_find_related(self):
        nodes = [
            KnowledgeNode(id="a", label="Pattern A", type=NodeType.PATTERN, description="..."),
            KnowledgeNode(id="b", label="Concept B", type=NodeType.CONCEPT, description="..."),
            KnowledgeNode(id="c", label="Rule C", type=NodeType.STANDARD, description="..."),
        ]
        edges = [
            KnowledgeEdge(source_id="a", target_id="b", type=EdgeType.REFINES),
            KnowledgeEdge(source_id="b", target_id="c", type=EdgeType.RELATES_TO),
        ]
        graph = KnowledgeGraph(nodes=nodes, edges=edges)

        related = graph.find_related("a", depth=2)
        related_ids = [n.id for n in related]
        assert "b" in related_ids
        assert "c" in related_ids

    def test_graph_empty(self):
        graph = KnowledgeGraph()
        assert graph.version == 1
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
