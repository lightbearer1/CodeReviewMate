"""Tests for rule engine and individual rule checkers."""

from __future__ import annotations

import pytest

from codereviewmate.core.models.review import IssueCategory, Severity
from codereviewmate.core.review.rules.base import Rule, RuleEngine, RuleMatch
from codereviewmate.core.review.rules.bug_pattern import create_bug_rules
from codereviewmate.core.review.rules.security import create_security_rules
from codereviewmate.core.review.rules.style import create_style_rules


class TestRuleEngine:
    def test_rule_matches_file_pattern(self):
        rule = Rule(
            id="test",
            category=IssueCategory.STYLE,
            severity=Severity.LOW,
            description="test",
            file_patterns=["*.py"],
        )
        assert rule.matches_file("src/app.py") is True
        assert rule.matches_file("src/app.js") is False

    def test_rule_excludes_generated(self):
        rule = Rule(
            id="test",
            category=IssueCategory.STYLE,
            severity=Severity.LOW,
            description="test",
        )
        # Generated files should be excluded by default
        assert rule.matches_file("bundle.min.js") is False
        assert rule.matches_file("src/app.py") is True

    def test_rule_regex_match(self):
        rule = Rule(
            id="no-print",
            category=IssueCategory.STYLE,
            severity=Severity.LOW,
            description="Debug print",
            pattern=r"print\(",
        )
        match = rule.check("test.py", "", "print('hello')", 1)
        assert match is not None
        assert "print" in match.matched_text

        # No match on non-print line
        match = rule.check("test.py", "", "x = 1", 2)
        assert match is None

    def test_rule_to_issue(self):
        rule = Rule(
            id="test-rule",
            category=IssueCategory.SECURITY,
            severity=Severity.HIGH,
            description="Test issue",
        )
        match = RuleMatch(
            line_number=10,
            line_content="bad code",
            matched_text="bad",
            suggestion="fix it",
        )
        issue = rule.to_issue("file.py", match)
        assert issue.severity == Severity.HIGH
        assert issue.rule_id == "test-rule"
        assert issue.line_start == 10
        assert issue.file_path == "file.py"

    def test_engine_runs_rules(self):
        engine = RuleEngine(
            rules=[
                Rule(
                    id="r1",
                    category=IssueCategory.STYLE,
                    severity=Severity.LOW,
                    description="Print",
                    pattern=r"print\(",
                    file_patterns=["*.py"],
                )
            ]
        )
        content = "print('hello')\nx = 1\nprint('world')\n"
        issues = engine.check_file("test.py", content)
        assert len(issues) == 2

    def test_engine_skips_non_matching_files(self):
        engine = RuleEngine(
            rules=[
                Rule(
                    id="r1",
                    category=IssueCategory.STYLE,
                    severity=Severity.LOW,
                    description="Print",
                    pattern=r"print\(",
                    file_patterns=["*.py"],
                )
            ]
        )
        issues = engine.check_file("test.js", "print('hello')")
        assert len(issues) == 0


class TestStyleRules:
    def test_detect_print_debug(self):
        rules = create_style_rules()
        engine = RuleEngine(rules)

        issues = engine.check_file("test.py", "print('debug')\nx = 1\n")
        print_issues = [i for i in issues if i.rule_id == "no-debug-print"]
        assert len(print_issues) == 1
        assert print_issues[0].auto_fixable is True

    def test_detect_console_log(self):
        rules = create_style_rules()
        engine = RuleEngine(rules)

        issues = engine.check_file("test.js", "console.log('hey')\n")
        console_issues = [i for i in issues if i.rule_id == "no-console-log"]
        assert len(console_issues) == 1

    def test_naming_convention_python(self):
        rules = create_style_rules()
        engine = RuleEngine(rules)

        # PascalCase class is fine
        issues = engine.check_file("test.py", "class UserManager:\n    pass\n")
        class_issues = [i for i in issues if i.rule_id == "class-naming-convention"]
        assert len(class_issues) == 0

        # lowercase class should flag
        issues = engine.check_file("test.py", "class user_manager:\n    pass\n")
        class_issues = [i for i in issues if i.rule_id == "class-naming-convention"]
        assert len(class_issues) == 1

    def test_trailing_whitespace(self):
        rules = create_style_rules()
        engine = RuleEngine(rules)

        issues = engine.check_file("test.py", "x = 1   \n")
        ws_issues = [i for i in issues if i.rule_id == "no-trailing-whitespace"]
        assert len(ws_issues) == 1

    def test_line_too_long(self):
        rules = create_style_rules()
        engine = RuleEngine(rules)

        long_line = "x = '" + "a" * 130 + "'"
        issues = engine.check_file("test.py", long_line)
        length_issues = [i for i in issues if i.rule_id == "line-too-long"]
        assert len(length_issues) == 1


class TestSecurityRules:
    def test_detect_hardcoded_password(self):
        rules = create_security_rules()
        engine = RuleEngine(rules)

        content = 'password = "supersecret123"\n'
        issues = engine.check_file("config.py", content)
        secret_issues = [i for i in issues if i.rule_id == "no-hardcoded-secrets"]
        assert len(secret_issues) >= 1
        assert secret_issues[0].severity == Severity.CRITICAL

    def test_detect_sql_injection_fstring(self):
        rules = create_security_rules()
        engine = RuleEngine(rules)

        content = 'cursor.execute(f"SELECT * FROM users WHERE id={uid}")\n'
        issues = engine.check_file("db.py", content)
        sql_issues = [i for i in issues if i.rule_id == "sql-injection-fstring"]
        assert len(sql_issues) >= 1

    def test_detect_eval_usage(self):
        rules = create_security_rules()
        engine = RuleEngine(rules)

        issues = engine.check_file("test.py", "eval(user_input)\n")
        eval_issues = [i for i in issues if i.rule_id == "eval-usage"]
        assert len(eval_issues) == 1

    def test_detect_shell_injection(self):
        rules = create_security_rules()
        engine = RuleEngine(rules)

        issues = engine.check_file("test.py", "subprocess.run(cmd, shell=True)\n")
        shell_issues = [i for i in issues if i.rule_id == "shell-injection"]
        assert len(shell_issues) == 1

    def test_clean_code_passes(self):
        rules = create_security_rules()
        engine = RuleEngine(rules)

        issues = engine.check_file(
            "test.py",
            "import os\n"
            "password = os.environ.get('DB_PASSWORD')\n"
            "cursor.execute('SELECT * FROM users WHERE id=%s', (uid,))\n",
        )
        high_severity = [i for i in issues if i.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(high_severity) == 0


class TestBugPatternRules:
    def test_detect_bare_except(self):
        rules = create_bug_rules()
        engine = RuleEngine(rules)

        content = "try:\n    x = 1\nexcept:\n    pass\n"
        issues = engine.check_file("test.py", content)
        except_issues = [i for i in issues if i.rule_id == "bare-except"]
        assert len(except_issues) == 1

    def test_detect_mutable_default_arg(self):
        rules = create_bug_rules()
        engine = RuleEngine(rules)

        content = "def foo(items=[]):\n    pass\n"
        issues = engine.check_file("test.py", content)
        mutable_issues = [i for i in issues if i.rule_id == "mutable-default-arg"]
        assert len(mutable_issues) == 1

    def test_equality_none(self):
        rules = create_bug_rules()
        engine = RuleEngine(rules)

        issues = engine.check_file("test.py", "if x == None:\n    pass\n")
        none_issues = [i for i in issues if i.rule_id == "equality-none"]
        assert len(none_issues) == 1

    def test_float_comparison(self):
        rules = create_bug_rules()
        engine = RuleEngine(rules)

        issues = engine.check_file("test.py", "if 0.1 + 0.2 == 0.3:\n    pass\n")
        float_issues = [i for i in issues if i.rule_id == "float-equality"]
        assert len(float_issues) == 1
