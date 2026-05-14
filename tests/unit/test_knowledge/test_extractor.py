"""Tests for knowledge extractor."""

from __future__ import annotations

import pytest

from codereviewmate.core.knowledge.extractor import KnowledgeExtractor, RULE_KNOWLEDGE_MAP
from codereviewmate.core.models.knowledge import NodeType
from codereviewmate.core.models.review import Issue, IssueCategory, Severity


class TestKnowledgeExtractor:
    def test_rule_mapping_coverage(self):
        """Verify that common rules have knowledge mappings."""
        expected_rules = [
            "no-hardcoded-secrets", "no-debug-print", "sql-injection-fstring",
            "eval-usage", "bare-except", "mutable-default-arg", "equality-none",
        ]
        for rule_id in expected_rules:
            assert rule_id in RULE_KNOWLEDGE_MAP, f"Missing mapping for {rule_id}"

    def test_extract_from_known_issues(self):
        extractor = KnowledgeExtractor()
        issues = [
            Issue(
                severity=Severity.CRITICAL,
                category=IssueCategory.SECURITY,
                title="Hardcoded password",
                description="Found password",
                file_path="config.py",
                rule_id="no-hardcoded-secrets",
            ),
            Issue(
                severity=Severity.LOW,
                category=IssueCategory.STYLE,
                title="Debug print",
                description="print() found",
                file_path="app.py",
                rule_id="no-debug-print",
            ),
        ]

        extraction = extractor.extract_from_issues(issues)
        assert len(extraction.new_nodes) == 2
        labels = [n.label for n in extraction.new_nodes]
        assert "Never hardcode secrets in source code" in labels
        assert "Use logging instead of print()" in labels
        # No edges — these two rule nodes don't share tags

    def test_extract_skips_unknown_rule_ids(self):
        extractor = KnowledgeExtractor()
        issues = [
            Issue(
                severity=Severity.MEDIUM,
                category=IssueCategory.ARCHITECTURE,
                title="Custom issue",
                description="Custom",
                file_path="x.py",
                rule_id="nonexistent-custom-rule",
            ),
        ]
        extraction = extractor.extract_from_issues(issues)
        assert len(extraction.new_nodes) == 0

    def test_extract_deduplication(self):
        extractor = KnowledgeExtractor()
        issues = [
            Issue(severity=Severity.CRITICAL, category=IssueCategory.SECURITY, title="S1", description="d", file_path="a.py", rule_id="no-hardcoded-secrets"),
            Issue(severity=Severity.CRITICAL, category=IssueCategory.SECURITY, title="S2", description="d", file_path="b.py", rule_id="no-hardcoded-secrets"),
        ]
        extraction = extractor.extract_from_issues(issues)
        assert len(extraction.new_nodes) == 1  # deduplicated

    def test_extract_empty_issues(self):
        extractor = KnowledgeExtractor()
        extraction = extractor.extract_from_issues([])
        assert len(extraction.new_nodes) == 0
        assert "0 knowledge nodes" in extraction.summary

    def test_extract_with_existing_nodes(self):
        extractor = KnowledgeExtractor()
        from codereviewmate.core.knowledge.graph import KnowledgeGraphManager

        g = KnowledgeGraphManager()
        existing = g.add_node(
            "Use environment variables for configuration",
            NodeType.STANDARD,
            tags=["security", "configuration"],
        )

        issues = [
            Issue(severity=Severity.CRITICAL, category=IssueCategory.SECURITY, title="S1", description="d", file_path="a.py", rule_id="no-hardcoded-secrets"),
        ]
        extraction = extractor.extract_from_issues(issues, existing_nodes=[existing])
        assert len(extraction.new_nodes) == 1
        # Should create edges from new node to existing node due to tag overlap
        assert len(extraction.new_edges) >= 1

    def test_make_id(self):
        assert KnowledgeExtractor._make_id("Never hardcode secrets") == "never_hardcode_secrets"
        assert KnowledgeExtractor._make_id("Use 'is None'!") == "use_is_none"

    def test_all_mapped_rules_have_valid_types(self):
        for rule_id, mapping in RULE_KNOWLEDGE_MAP.items():
            assert mapping["type"] in [t.value for t in NodeType], f"Invalid type for {rule_id}: {mapping['type']}"
