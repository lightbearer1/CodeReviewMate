"""Pre-commit review engine — fast checks before code is committed."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

from codereviewmate.core.config.manager import get_config
from codereviewmate.core.models.review import Issue, Patch, PreCommitResult
from codereviewmate.core.review.analyzers.complexity import ComplexityAnalyzer
from codereviewmate.core.review.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer
from codereviewmate.core.review.auto_fix import PatchGenerator
from codereviewmate.core.review.rules.base import Rule, RuleEngine
from codereviewmate.core.review.rules.bug_pattern import create_bug_rules
from codereviewmate.core.review.rules.security import create_security_rules
from codereviewmate.core.review.rules.style import create_style_rules

logger = logging.getLogger(__name__)


class PreCommitEngine:
    """Orchestrates fast pre-commit checks: rules + complexity + auto-fix."""

    def __init__(self, rules: Optional[list[Rule]] = None):
        self._rule_engine = RuleEngine(rules=rules or self._default_rules())
        self._complexity = ComplexityAnalyzer()
        self._tree_sitter = TreeSitterAnalyzer()
        self._patch_generator = PatchGenerator()
        self._config = get_config()

    @staticmethod
    def _default_rules() -> list[Rule]:
        """Assemble all default rules."""
        rules: list[Rule] = []
        rules.extend(create_style_rules())
        rules.extend(create_security_rules())
        rules.extend(create_bug_rules())
        return rules

    def check_file(self, file_path: str) -> list[Issue]:
        """Run all checks on a single file."""
        if not self._should_check(file_path):
            return []

        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            logger.debug("Cannot read file: %s", file_path)
            return []

        issues: list[Issue] = []

        # 1. Rule-based checks
        rule_issues = self._rule_engine.check_file(file_path, content)
        issues.extend(rule_issues)

        # 2. Complexity checks
        try:
            metrics = self._complexity.analyze_file(file_path, content)
            for func_metrics in metrics.functions:
                if func_metrics.cyclomatic_complexity > self._complexity.COMPLEXITY_THRESHOLDS[
                    "cyclomatic_complexity"
                ]:
                    issues.append(
                        Issue(
                            severity="medium",
                            category="maintainability",
                            title=f"函数 {func_metrics.name} 圈复杂度过高",
                            description=(
                                f"圈复杂度: {func_metrics.cyclomatic_complexity} "
                                f"(建议 ≤ {self._complexity.COMPLEXITY_THRESHOLDS['cyclomatic_complexity']})"
                            ),
                            file_path=file_path,
                            suggestion="考虑拆分函数或提取子方法以降低复杂度",
                            rule_id="complexity-too-high",
                        )
                    )
                if func_metrics.nesting_depth > self._complexity.COMPLEXITY_THRESHOLDS[
                    "nesting_depth"
                ]:
                    issues.append(
                        Issue(
                            severity="low",
                            category="maintainability",
                            title=f"函数 {func_metrics.name} 嵌套层级过深",
                            description=(
                                f"嵌套深度: {func_metrics.nesting_depth} "
                                f"(建议 ≤ {self._complexity.COMPLEXITY_THRESHOLDS['nesting_depth']})"
                            ),
                            file_path=file_path,
                            suggestion="考虑使用早返回(early return)模式减少嵌套",
                            rule_id="nesting-too-deep",
                        )
                    )
        except Exception:
            logger.debug("Complexity analysis failed for %s", file_path, exc_info=True)

        return issues

    def check_diff(self, repo_path: str = ".", staged_only: bool = True) -> PreCommitResult:
        """Run pre-commit checks on the git diff."""
        start = time.monotonic()
        issues: list[Issue] = []
        checks_run = 0

        changed_files = self._get_changed_files(repo_path, staged_only)
        if not changed_files:
            logger.info("No files to check")
            return PreCommitResult(passed=True, duration_ms=0)

        file_contents: dict[str, str] = {}

        for file_path in changed_files:
            if not self._should_check(file_path):
                continue

            checks_run += 1
            try:
                full_path = os.path.join(repo_path, file_path)
                content = Path(full_path).read_text(encoding="utf-8")
                file_contents[file_path] = content

                file_issues = self.check_file(full_path)
                issues.extend(file_issues)

            except Exception:
                logger.debug("Error checking %s", file_path, exc_info=True)

        # Generate auto-fix patches
        patches = self._patch_generator.generate_all(
            [i for i in issues if i.auto_fixable], file_contents
        )

        passed = len([i for i in issues if i.severity in ("critical", "high")]) == 0
        duration_ms = (time.monotonic() - start) * 1000

        if issues:
            severity_counts = {}
            for issue in issues:
                severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            logger.info(
                "Pre-commit found %d issues: %s (%.0fms)",
                len(issues),
                severity_counts,
                duration_ms,
            )

        return PreCommitResult(
            passed=passed,
            issues=issues,
            patches=patches,
            duration_ms=duration_ms,
            checks_run=checks_run,
        )

    def _should_check(self, file_path: str) -> bool:
        """Determine if a file should be checked."""
        ext = Path(file_path).suffix.lower()
        if ext not in self._config.review.supported_extensions:
            return False

        for pattern in self._config.review.ignore_patterns:
            if Path(file_path).match(pattern):
                return False

        return True

    @staticmethod
    def _get_changed_files(repo_path: str, staged_only: bool = True) -> list[str]:
        """Get list of changed files from git."""
        import subprocess

        try:
            args = ["git", "diff", "--name-only"]
            if staged_only:
                args.append("--cached")
            result = subprocess.run(
                args,
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # Try without --cached for non-git contexts
                args = ["git", "diff", "--name-only", "HEAD"]
                result = subprocess.run(args, cwd=repo_path, capture_output=True, text=True)
            if result.returncode != 0:
                # Fallback: list all tracked files
                args = ["git", "ls-files"]
                result = subprocess.run(args, cwd=repo_path, capture_output=True, text=True)

            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except FileNotFoundError:
            logger.debug("git not available, cannot get changed files")
            return []
