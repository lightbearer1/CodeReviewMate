"""Review report generation — merges pre-commit and deep review results."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from codereviewmate.core.models.review import (
    ContextBundle,
    DeepReviewResult,
    Issue,
    PreCommitResult,
    ReviewReport,
    Severity,
)


class ReportGenerator:
    """Generates comprehensive review reports in multiple formats."""

    def __init__(self):
        self._start_time = time.monotonic()

    def generate(
        self,
        pre_commit: Optional[PreCommitResult] = None,
        deep: Optional[DeepReviewResult] = None,
        context: Optional[ContextBundle] = None,
    ) -> ReviewReport:
        """Combine pre-commit and deep review results into a unified report."""
        duration = (time.monotonic() - self._start_time) * 1000
        return ReviewReport(
            pre_commit=pre_commit,
            deep=deep,
            context=context,
            total_duration_ms=duration,
        )

    @staticmethod
    def format_markdown(report: ReviewReport) -> str:
        """Render the report as Markdown."""
        sections: list[str] = []

        sections.append(f"# Code Review Report")
        sections.append(f"**Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        sections.append("")

        # Overall status
        status = "PASSED" if report.passed else "FAILED"
        icon = ":white_check_mark:" if report.passed else ":x:"
        sections.append(f"## Status: {icon} {status}")
        sections.append(f"Duration: {report.total_duration_ms:.0f}ms")
        sections.append(f"Total issues: {len(report.all_issues)}")
        sections.append("")

        # Issue summary table
        by_severity = report._count_by_severity()
        if by_severity:
            sections.append("## Issues by Severity")
            sections.append("| Severity | Count |")
            sections.append("|----------|-------|")
            for sev, count in sorted(by_severity.items()):
                sections.append(f"| {sev.value} | {count} |")
            sections.append("")

        # Pre-commit results
        if report.pre_commit:
            sections.append(ReportGenerator._format_pre_commit(report.pre_commit))

        # Deep review results
        if report.deep:
            sections.append(ReportGenerator._format_deep(report.deep))

        # All issues detail
        if report.all_issues:
            sections.append("## All Issues")
            for issue in report.all_issues:
                sections.append(ReportGenerator._format_issue(issue))
                sections.append("")

        return "\n".join(sections)

    @staticmethod
    def format_html(report: ReviewReport) -> str:
        """Render the report as HTML."""
        md = ReportGenerator.format_markdown(report)
        try:
            import markdown
            return markdown.markdown(md, extensions=["tables", "fenced_code"])
        except ImportError:
            return f"<pre>{md}</pre>"

    @staticmethod
    def format_text(report: ReviewReport) -> str:
        """Render the report as plain text (for CLI output)."""
        lines: list[str] = []
        status = "PASSED" if report.passed else "FAILED"
        lines.append(f"Code Review Report — {status}")
        lines.append(f"Duration: {report.total_duration_ms:.0f}ms | Issues: {len(report.all_issues)}")
        lines.append("-" * 60)

        if report.pre_commit:
            pc = report.pre_commit
            lines.append(f"[Pre-commit] {pc.checks_run} files, {len(pc.issues)} issues, {pc.duration_ms:.0f}ms")

        if report.deep:
            d = report.deep
            score = d.architecture_compliance.get("score", "N/A") if d.architecture_compliance else "N/A"
            lines.append(f"[Deep Review] Score: {score}/100, {len(d.issues)} violations, {d.duration_ms:.0f}ms")

        if report.all_issues:
            lines.append("")
            for issue in report.all_issues:
                loc = f"L{issue.line_start}" if issue.line_start else ""
                lines.append(f"  [{issue.severity.value.upper()}] {issue.title} — {issue.file_path}:{loc}")

        return "\n".join(lines)

    @staticmethod
    def _format_pre_commit(result: PreCommitResult) -> str:
        lines: list[str] = []
        lines.append("## Pre-commit Check")
        lines.append(f"- Files checked: {result.checks_run}")
        lines.append(f"- Issues found: {len(result.issues)}")
        lines.append(f"- Patches generated: {len(result.patches)}")
        lines.append(f"- Duration: {result.duration_ms:.0f}ms")
        lines.append(f"- Result: {'PASSED' if result.passed else 'FAILED'}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_deep(result: DeepReviewResult) -> str:
        lines: list[str] = []
        lines.append("## Deep Architecture Review")
        if result.architecture_compliance:
            arch = result.architecture_compliance
            lines.append(f"- Architecture Score: {arch.get('score', 'N/A')}/100")
            lines.append(f"- Compliant: {arch.get('compliant', 'N/A')}")
            recs = arch.get("recommendations", [])
            if recs:
                lines.append("- Recommendations:")
                for r in recs:
                    lines.append(f"  - {r}")
        lines.append(f"- Duration: {result.duration_ms:.0f}ms")
        if result.token_usage:
            lines.append(f"- Token usage: {result.token_usage}")
        if result.summary:
            lines.append("")
            lines.append(result.summary)
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_issue(issue: Issue) -> str:
        parts: list[str] = []
        parts.append(f"### [{issue.severity.value.upper()}] [{issue.category.value}] {issue.title}")
        parts.append(f"- **File**: `{issue.file_path}`")
        if issue.line_start:
            parts.append(f"- **Line**: {issue.line_start}" + (f"–{issue.line_end}" if issue.line_end else ""))
        parts.append(f"- **Description**: {issue.description}")
        if issue.suggestion:
            parts.append(f"- **Suggestion**: {issue.suggestion}")
        if issue.rule_id:
            parts.append(f"- **Rule**: `{issue.rule_id}`")
        return "\n".join(parts)
