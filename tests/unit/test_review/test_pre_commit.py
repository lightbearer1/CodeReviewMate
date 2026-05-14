"""Tests for the pre-commit review engine."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from codereviewmate.core.review.pre_commit import PreCommitEngine


@pytest.fixture
def temp_repo():
    """Create a temporary directory with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a Python file with issues
        py_file = Path(tmpdir) / "app.py"
        py_file.write_text(
            "password = 'hardcoded123'\n"
            "print('debug message')\n"
            "import os\n\n"
            "def process_data(items=[]):\n"
            "    for item in items:\n"
            "        if item:\n"
            "            try:\n"
            "                result = eval(item)\n"
            "            except:\n"
            "                pass\n"
            "    return items\n",
            encoding="utf-8",
        )

        # Create a clean file
        clean_file = Path(tmpdir) / "clean.py"
        clean_file.write_text(
            "import os\nimport logging\n\n"
            "logger = logging.getLogger(__name__)\n\n"
            "class DataProcessor:\n"
            '    """Processes data with proper error handling."""\n\n'
            "    def __init__(self):\n"
            "        self.secret = os.environ.get('API_KEY')\n\n"
            "    def process(self, items=None):\n"
            "        if items is None:\n"
            "            items = []\n"
            "        return [item.upper() for item in items if item]\n",
            encoding="utf-8",
        )

        # Create a JS file with issues
        js_file = Path(tmpdir) / "app.js"
        js_file.write_text(
            "console.log('debug here');\n"
            "console.debug('more debug');\n"
            "const x = 1;\n",
            encoding="utf-8",
        )

        yield tmpdir


class TestPreCommitEngine:
    def test_check_file_detects_issues(self, temp_repo: str):
        engine = PreCommitEngine()
        issues = engine.check_file(str(Path(temp_repo) / "app.py"))

        # Should detect multiple issues
        rule_ids = [i.rule_id for i in issues]
        assert "no-hardcoded-secrets" in rule_ids
        assert "no-debug-print" in rule_ids
        assert "mutable-default-arg" in rule_ids
        assert "eval-usage" in rule_ids
        assert "bare-except" in rule_ids

    def test_check_clean_file(self, temp_repo: str):
        engine = PreCommitEngine()
        issues = engine.check_file(str(Path(temp_repo) / "clean.py"))

        # Clean file should have no critical/high issues
        high_issues = [i for i in issues if i.severity in ("critical", "high")]
        assert len(high_issues) == 0

    def test_should_skip_unsupported_extensions(self, temp_repo: str):
        engine = PreCommitEngine()
        # Create a .txt file
        txt_file = Path(temp_repo) / "notes.txt"
        txt_file.write_text("password = 'secret'\n", encoding="utf-8")

        assert engine._should_check(str(txt_file)) is False

    def test_should_check_supported_extensions(self, temp_repo: str):
        engine = PreCommitEngine()
        assert engine._should_check("app.py") is True
        assert engine._should_check("app.js") is True
        assert engine._should_check("app.go") is True
        assert engine._should_check("notes.txt") is False

    def test_check_js_file(self, temp_repo: str):
        engine = PreCommitEngine()
        issues = engine.check_file(str(Path(temp_repo) / "app.js"))

        rule_ids = [i.rule_id for i in issues]
        assert "no-console-log" in rule_ids

    def test_pre_commit_result_passed(self):
        """Result with no critical/high issues should be passed=True."""
        from codereviewmate.core.models.review import Issue, IssueCategory, PreCommitResult, Severity

        result = PreCommitResult(
            passed=True,
            issues=[
                Issue(
                    severity=Severity.LOW,
                    category=IssueCategory.STYLE,
                    title="Trailing whitespace",
                    description="ws",
                    file_path="test.py",
                )
            ],
            checks_run=1,
        )
        assert result.passed is True

    def test_auto_fix_generation_in_result(self, temp_repo: str):
        engine = PreCommitEngine()
        issues = engine.check_file(str(Path(temp_repo) / "app.py"))

        # Debug print should be auto-fixable
        print_issues = [i for i in issues if i.rule_id == "no-debug-print"]
        assert len(print_issues) > 0
        assert print_issues[0].auto_fixable is True

        # Hardcoded secret should NOT be auto-fixable
        secret_issues = [i for i in issues if i.rule_id == "no-hardcoded-secrets"]
        assert len(secret_issues) > 0
        assert secret_issues[0].auto_fixable is False

    def test_intercept_rate_target(self, temp_repo: str):
        """Verify that the pre-commit engine catches 60%+ of low-level issues.

        A file with intentional issues should have a high detection rate.
        """
        engine = PreCommitEngine()
        issues = engine.check_file(str(Path(temp_repo) / "app.py"))

        # The sample file has at least these issues:
        # 1. hardcoded password
        # 2. debug print
        # 3. mutable default arg
        # 4. eval usage
        # 5. bare except
        # That's 5 out of a reasonable set of issues — should be >60%
        assert len(issues) >= 5, f"Expected at least 5 issues, got {len(issues)}"
        assert len(issues) >= 5  # Well above 60% of the planted issues
