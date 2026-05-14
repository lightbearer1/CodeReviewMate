"""Base rule engine and rule definitions for pre-commit checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from codereviewmate.core.models.review import Issue, IssueCategory, Severity


@dataclass
class RuleMatch:
    """A match found by a rule with exact position."""

    line_number: int
    line_content: str
    matched_text: str
    suggestion: str = ""


@dataclass
class Rule:
    """A single check rule."""

    id: str
    category: IssueCategory
    severity: Severity
    description: str
    pattern: Optional[str] = None
    file_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=lambda: ["*.min.js", "*.generated.*"])
    auto_fixable: bool = False
    suggestion_template: str = ""
    check_fn: Optional[Callable[[str, str], list[RuleMatch]]] = None

    def matches_file(self, file_path: str) -> bool:
        """Check if the rule applies to this file."""
        # Check exclusions first
        for excl in self.exclude_patterns:
            if Path(file_path).match(excl):
                return False
        # Check file patterns
        if not self.file_patterns:
            return True
        for pat in self.file_patterns:
            if Path(file_path).match(pat):
                return True
        return False

    def check(self, file_path: str, content: str, line: str, line_num: int) -> Optional[RuleMatch]:
        """Check a single line against this rule."""
        # First try the custom check function
        if self.check_fn:
            matches = self.check_fn(file_path, content)
            for m in matches:
                if m.line_number == line_num:
                    return m
            return None

        # Then try regex pattern matching
        if self.pattern:
            match = re.search(self.pattern, line)
            if match:
                suggestion = self.suggestion_template.format(
                    matched=match.group(0),
                    line_num=line_num,
                )
                return RuleMatch(
                    line_number=line_num,
                    line_content=line.strip(),
                    matched_text=match.group(0),
                    suggestion=suggestion,
                )

        return None

    def to_issue(self, file_path: str, match: RuleMatch) -> Issue:
        """Convert a rule match to a formal Issue."""
        return Issue(
            severity=self.severity,
            category=self.category,
            title=f"[{self.id}] {self.description}",
            description=f"在行 {match.line_number} 发现: `{match.matched_text}`\n{match.line_content}",
            file_path=file_path,
            line_start=match.line_number,
            suggestion=match.suggestion or self.suggestion_template,
            rule_id=self.id,
            auto_fixable=self.auto_fixable,
        )


class RuleEngine:
    """Executes configurable rules against code files."""

    def __init__(self, rules: Optional[list[Rule]] = None):
        self._rules: list[Rule] = rules or []

    def add_rule(self, rule: Rule) -> None:
        """Register a rule."""
        self._rules.append(rule)

    def add_rules(self, rules: list[Rule]) -> None:
        """Register multiple rules."""
        self._rules.extend(rules)

    def get_rules(self) -> list[Rule]:
        """Get all registered rules."""
        return list(self._rules)

    def check_file(self, file_path: str, content: str) -> list[Issue]:
        """Run all applicable rules against a file."""
        issues: list[Issue] = []
        lines = content.splitlines()

        for rule in self._rules:
            if not rule.matches_file(file_path):
                continue

            for i, line in enumerate(lines, 1):
                match = rule.check(file_path, content, line, i)
                if match:
                    issues.append(rule.to_issue(file_path, match))

        return issues

    def check_diff(self, file_path: str, diff_content: str) -> list[Issue]:
        """Run rules against a diff (only added lines)."""
        issues: list[Issue] = []
        added_lines: list[tuple[int, str]] = []

        for line in diff_content.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append((len(added_lines), line[1:]))

        full_content = "\n".join(line for _, line in added_lines)

        for rule in self._rules:
            if not rule.matches_file(file_path):
                continue

            for i, text in added_lines:
                match = rule.check(file_path, full_content, text, i + 1)
                if match:
                    issues.append(rule.to_issue(file_path, match))

        return issues
