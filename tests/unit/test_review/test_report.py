"""Tests for review report generation."""

from __future__ import annotations

from codereviewmate.core.models.review import (
    ContextBundle,
    DeepReviewResult,
    Issue,
    IssueCategory,
    PreCommitResult,
    ReviewReport,
    Severity,
)
from codereviewmate.core.review.report import ReportGenerator


class TestReportGenerator:
    def test_generate_empty(self):
        gen = ReportGenerator()
        report = gen.generate()
        assert report.pre_commit is None
        assert report.deep is None
        assert report.passed is True
        assert len(report.all_issues) == 0

    def test_generate_with_pre_commit_only(self):
        gen = ReportGenerator()
        pc = PreCommitResult(
            passed=True,
            issues=[
                Issue(
                    severity=Severity.LOW,
                    category=IssueCategory.STYLE,
                    title="Debug print",
                    description="print() found",
                    file_path="test.py",
                    rule_id="no-debug-print",
                )
            ],
            checks_run=1,
        )
        report = gen.generate(pre_commit=pc)
        assert report.passed is True
        assert len(report.all_issues) == 1

    def test_generate_with_deep_only(self):
        gen = ReportGenerator()
        deep = DeepReviewResult(
            passed=False,
            issues=[
                Issue(
                    severity=Severity.HIGH,
                    category=IssueCategory.ARCHITECTURE,
                    title="Layering violation",
                    description="Bad layering",
                    file_path="src/api.py",
                    rule_id="deep-arch-compliance",
                )
            ],
            architecture_compliance={"score": 65, "compliant": False},
        )
        report = gen.generate(deep=deep)
        assert report.passed is False
        assert "Layering" in report.all_issues[0].title

    def test_generate_combined(self):
        gen = ReportGenerator()
        pc = PreCommitResult(passed=True, issues=[], checks_run=3)
        deep = DeepReviewResult(
            passed=True,
            issues=[],
            architecture_compliance={"score": 92, "compliant": True},
        )
        report = gen.generate(pre_commit=pc, deep=deep)
        assert report.passed is True
        assert report.pre_commit.checks_run == 3

    def test_format_markdown(self):
        report = ReviewReport(
            pre_commit=PreCommitResult(passed=True, issues=[], checks_run=2),
            deep=DeepReviewResult(
                passed=True,
                issues=[],
                architecture_compliance={"score": 88, "compliant": True},
            ),
        )
        md = ReportGenerator.format_markdown(report)
        assert "# Code Review Report" in md
        assert "PASSED" in md
        assert "Architecture Score: 88/100" in md

    def test_format_markdown_with_issues(self):
        report = ReviewReport(
            pre_commit=PreCommitResult(
                passed=False,
                issues=[
                    Issue(
                        severity=Severity.CRITICAL,
                        category=IssueCategory.SECURITY,
                        title="Hardcoded password",
                        description="Found password",
                        file_path="config.py",
                        line_start=5,
                        suggestion="Use env var",
                        rule_id="no-hardcoded-secrets",
                    )
                ],
                checks_run=1,
            ),
        )
        md = ReportGenerator.format_markdown(report)
        assert "FAILED" in md
        assert "Hardcoded password" in md
        assert "no-hardcoded-secrets" in md

    def test_format_text(self):
        report = ReviewReport(
            pre_commit=PreCommitResult(passed=True, issues=[], checks_run=1),
            deep=DeepReviewResult(
                passed=True, issues=[],
                architecture_compliance={"score": 90, "compliant": True},
            ),
        )
        text = ReportGenerator.format_text(report)
        assert "PASSED" in text
        assert "90" in text

    def test_format_text_failed(self):
        report = ReviewReport(
            pre_commit=PreCommitResult(
                passed=False,
                issues=[
                    Issue(
                        severity=Severity.HIGH,
                        category=IssueCategory.BUG,
                        title="Bug found",
                        description="Potential bug",
                        file_path="src/app.py",
                        line_start=42,
                    )
                ],
                checks_run=1,
            ),
        )
        text = ReportGenerator.format_text(report)
        assert "FAILED" in text
        assert "[HIGH]" in text

    def test_count_by_severity(self):
        report = ReviewReport(
            pre_commit=PreCommitResult(
                passed=False,
                issues=[
                    Issue(severity=Severity.CRITICAL, category=IssueCategory.SECURITY, title="S1", description="d", file_path="a.py"),
                    Issue(severity=Severity.CRITICAL, category=IssueCategory.SECURITY, title="S2", description="d", file_path="b.py"),
                    Issue(severity=Severity.LOW, category=IssueCategory.STYLE, title="S3", description="d", file_path="c.py"),
                ],
                checks_run=1,
            ),
        )
        counts = report._count_by_severity()
        assert counts[Severity.CRITICAL] == 2
        assert counts[Severity.LOW] == 1
