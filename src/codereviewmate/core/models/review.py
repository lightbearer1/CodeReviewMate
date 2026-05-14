"""Domain models for code review."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(str, Enum):
    STYLE = "style"
    NAMING = "naming"
    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"
    ARCHITECTURE = "architecture"
    MAINTAINABILITY = "maintainability"
    DOCUMENTATION = "documentation"


class ReviewPhase(str, Enum):
    PRE_COMMIT = "pre_commit"
    DEEP = "deep"


class Issue(BaseModel):
    """A single issue found during review."""

    severity: Severity
    category: IssueCategory
    title: str
    description: str
    file_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    suggestion: Optional[str] = None
    rule_id: Optional[str] = None
    auto_fixable: bool = False


class Patch(BaseModel):
    """A generated fix patch for an issue."""

    issue_id: str
    file_path: str
    original_lines: str
    fixed_lines: str
    unified_diff: str


class PreCommitResult(BaseModel):
    """Result of a pre-commit fast check."""

    passed: bool
    issues: list[Issue] = Field(default_factory=list)
    patches: list[Patch] = Field(default_factory=list)
    duration_ms: float = 0.0
    checks_run: int = 0


class ContextBundle(BaseModel):
    """Context gathered from RAG for deep review."""

    relevant_docs: list[dict] = Field(default_factory=list)
    relevant_reviews: list[dict] = Field(default_factory=list)
    relevant_standards: list[dict] = Field(default_factory=list)
    architecture_constraints: list[str] = Field(default_factory=list)


class DeepReviewResult(BaseModel):
    """Result of a deep LLM-powered review."""

    passed: bool
    issues: list[Issue] = Field(default_factory=list)
    summary: str = ""
    architecture_compliance: Optional[dict] = None
    token_usage: Optional[dict] = None
    duration_ms: float = 0.0


class ReviewReport(BaseModel):
    """Full review report combining pre-commit and deep results."""

    pre_commit: Optional[PreCommitResult] = None
    deep: Optional[DeepReviewResult] = None
    context: Optional[ContextBundle] = None
    total_duration_ms: float = 0.0

    @property
    def all_issues(self) -> list[Issue]:
        issues: list[Issue] = []
        if self.pre_commit:
            issues.extend(self.pre_commit.issues)
        if self.deep:
            issues.extend(self.deep.issues)
        return issues

    @property
    def passed(self) -> bool:
        pre_ok = self.pre_commit.passed if self.pre_commit else True
        deep_ok = self.deep.passed if self.deep else True
        return pre_ok and deep_ok

    def _count_by_severity(self) -> dict[Severity, int]:
        counts: dict[Severity, int] = {}
        for issue in self.all_issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts
