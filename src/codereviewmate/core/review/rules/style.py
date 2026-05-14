"""Style and naming convention rules."""

from __future__ import annotations

import re

from codereviewmate.core.models.review import IssueCategory, Severity
from codereviewmate.core.review.rules.base import Rule, RuleMatch


def create_style_rules() -> list[Rule]:
    """Create the default set of style/naming rules."""
    return [
        Rule(
            id="no-debug-print",
            category=IssueCategory.STYLE,
            severity=Severity.LOW,
            description="代码中残留的 debug print() 语句",
            pattern=r"\bprint\s*\(",
            file_patterns=["*.py"],
            auto_fixable=True,
            suggestion_template="建议移除调试用的 print() 或改用 logging 模块",
        ),
        Rule(
            id="no-console-log",
            category=IssueCategory.STYLE,
            severity=Severity.LOW,
            description="代码中残留的 console.log() 调试语句",
            pattern=r"console\.(log|debug|info|warn)\s*\(",
            file_patterns=["*.js", "*.ts", "*.tsx"],
            auto_fixable=True,
            suggestion_template="建议移除调试用的 console.{matched} 或使用统一的日志模块",
        ),
        Rule(
            id="no-trailing-whitespace",
            category=IssueCategory.STYLE,
            severity=Severity.INFO,
            description="行尾有多余空白字符",
            pattern=r"[ \t]+$",
            auto_fixable=True,
            suggestion_template="移除行尾空白字符",
        ),
        Rule(
            id="no-multiple-blank-lines",
            category=IssueCategory.STYLE,
            severity=Severity.INFO,
            description="连续的空行不应超过 2 行",
            pattern=r"^$",
            auto_fixable=False,
            suggestion_template="减少连续空行",
            check_fn=_check_consecutive_blanks,
        ),
        Rule(
            id="line-too-long",
            category=IssueCategory.STYLE,
            severity=Severity.INFO,
            description="单行代码超过 120 字符",
            auto_fixable=False,
            suggestion_template="建议将长行拆分为多行",
            check_fn=_check_line_length,
        ),
        Rule(
            id="no-todo-without-ticket",
            category=IssueCategory.MAINTAINABILITY,
            severity=Severity.LOW,
            description="TODO 注释未关联 Issue/工单编号",
            pattern=r"#\s*TODO(?!.*\(?(#\d+|ISSUE-\d+|PROJ-\d+)\)?)",
            file_patterns=["*.py", "*.js", "*.ts", "*.go", "*.java"],
            auto_fixable=False,
            suggestion_template="建议在 TODO 后添加工单编号，如 TODO(#123)",
        ),
        Rule(
            id="class-naming-convention",
            category=IssueCategory.NAMING,
            severity=Severity.LOW,
            description="类名应遵循 PascalCase 命名规范",
            file_patterns=["*.py", "*.js", "*.ts"],
            auto_fixable=False,
            suggestion_template="类名应使用 PascalCase",
            check_fn=_check_class_naming,
        ),
        Rule(
            id="function-naming-convention",
            category=IssueCategory.NAMING,
            severity=Severity.LOW,
            description="函数名应遵循 snake_case 命名规范",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="Python 函数名应使用 snake_case",
            check_fn=_check_function_naming_python,
        ),
    ]


def _check_consecutive_blanks(file_path: str, content: str) -> list[RuleMatch]:
    """Check for more than 2 consecutive blank lines."""
    matches: list[RuleMatch] = []
    lines = content.splitlines()
    consecutive = 0
    for i, line in enumerate(lines, 1):
        if line.strip() == "":
            consecutive += 1
            if consecutive > 2:
                matches.append(
                    RuleMatch(
                        line_number=i,
                        line_content="(空行)",
                        matched_text="连续空行",
                        suggestion=f"第 {i} 行：连续 {consecutive} 个空行，建议最多保留 2 行",
                    )
                )
        else:
            consecutive = 0
    return matches


def _check_line_length(file_path: str, content: str) -> list[RuleMatch]:
    """Check for lines exceeding 120 characters."""
    matches: list[RuleMatch] = []
    max_len = 120
    for i, line in enumerate(content.splitlines(), 1):
        if len(line) > max_len and not line.strip().startswith(("#", "//", "import", "from")):
            matches.append(
                RuleMatch(
                    line_number=i,
                    line_content=line[:80] + "...",
                    matched_text=f"行长度 {len(line)}",
                    suggestion=f"当前 {len(line)} 字符，建议不超过 {max_len} 字符",
                )
            )
    return matches


def _check_class_naming(file_path: str, content: str) -> list[RuleMatch]:
    """Check PascalCase for class names."""
    matches: list[RuleMatch] = []
    # Match class definitions
    class_pattern = re.compile(r"^\s*class\s+(\w+)", re.MULTILINE)
    for match_obj in class_pattern.finditer(content):
        name = match_obj.group(1)
        line_num = content[: match_obj.start()].count("\n") + 1
        if not name[0].isupper():
            matches.append(
                RuleMatch(
                    line_number=line_num,
                    line_content=match_obj.group(0).strip(),
                    matched_text=name,
                    suggestion=f"类名 '{name}' 应使用 PascalCase（首字母大写）",
                )
            )
    return matches


def _check_function_naming_python(file_path: str, content: str) -> list[RuleMatch]:
    """Check snake_case for Python function names."""
    matches: list[RuleMatch] = []
    # Match def statements, skip __dunder__ methods
    func_pattern = re.compile(r"^\s*def\s+(\w+)", re.MULTILINE)
    for match_obj in func_pattern.finditer(content):
        name = match_obj.group(1)
        if name.startswith("__") and name.endswith("__"):
            continue  # Skip dunder methods
        if name.startswith("_"):
            name = name[1:]  # Skip leading underscore for private methods
        line_num = content[: match_obj.start()].count("\n") + 1
        if "_" not in name and not name.islower():
            matches.append(
                RuleMatch(
                    line_number=line_num,
                    line_content=match_obj.group(0).strip(),
                    matched_text=name,
                    suggestion=f"函数名 '{name}' 应使用 snake_case",
                )
            )
    return matches
