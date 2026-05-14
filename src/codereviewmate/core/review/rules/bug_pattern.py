"""Common bug pattern detection rules."""

from __future__ import annotations

import re

from codereviewmate.core.models.review import IssueCategory, Severity
from codereviewmate.core.review.rules.base import Rule, RuleMatch


def create_bug_rules() -> list[Rule]:
    """Create the default set of bug pattern rules."""
    return [
        Rule(
            id="bare-except",
            category=IssueCategory.BUG,
            severity=Severity.MEDIUM,
            description="使用了裸 except（会捕获 KeyboardInterrupt 等系统异常）",
            pattern=r"except\s*:",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="使用 except Exception 替代裸 except，避免捕获系统级异常",
        ),
        Rule(
            id="mutable-default-arg",
            category=IssueCategory.BUG,
            severity=Severity.HIGH,
            description="可变对象作为函数默认参数（会导致意外的状态共享）",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="使用 None 作为默认值，在函数内部初始化可变对象",
            check_fn=_check_mutable_default,
        ),
        Rule(
            id="is-comparison-literal",
            category=IssueCategory.BUG,
            severity=Severity.LOW,
            description="使用 'is' 比较字面量（应该用 '=='）",
            pattern=r"\bis\s+(True|False|None|['\"][^'\"]*['\"]|\d+)\b",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="比较值时使用 '==' 而非 'is'（除 None 外）",
            check_fn=_check_is_comparison,
        ),
        Rule(
            id="assignment-in-condition",
            category=IssueCategory.BUG,
            severity=Severity.MEDIUM,
            description="在条件语句中使用赋值（可能是笔误，应该是 ==）",
            pattern=r"if\s+\w+\s*=\s*[^=]",
            file_patterns=["*.py", "*.js", "*.ts"],
            auto_fixable=False,
            suggestion_template="条件判断中使用了赋值 =，是否本意是比较 ==？",
        ),
        Rule(
            id="undefined-variable",
            category=IssueCategory.BUG,
            severity=Severity.HIGH,
            description="可能未定义的变量（在 try 块外使用 try 内定义的变量）",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="在 try 块外初始化变量，或确保异常时变量也有值",
            check_fn=_check_potential_undefined,
        ),
        Rule(
            id="equality-none",
            category=IssueCategory.BUG,
            severity=Severity.LOW,
            description="使用 == 与 None 比较（应使用 'is None'）",
            pattern=r"==\s*None\b",
            file_patterns=["*.py"],
            auto_fixable=True,
            suggestion_template="使用 'is None' 替代 '== None'",
        ),
        Rule(
            id="not-in-loop-collection-modification",
            category=IssueCategory.BUG,
            severity=Severity.HIGH,
            description="在迭代过程中修改集合（.remove/.pop 在 for 循环内）",
            pattern=r"for\s+\w+\s+in\s+\w+:.*\.(remove|pop)\s*\(",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="在迭代集合时修改其内容会导致意外行为，应迭代副本或收集待删除项",
        ),
        Rule(
            id="float-equality",
            category=IssueCategory.BUG,
            severity=Severity.MEDIUM,
            description="浮点数直接比较相等（可能有精度问题）",
            pattern=r"==|!=",
            file_patterns=["*.py", "*.js", "*.ts", "*.go", "*.java"],
            auto_fixable=False,
            suggestion_template="避免浮点数直接相等比较，使用误差范围或 math.isclose()",
            check_fn=_check_float_comparison,
        ),
        Rule(
            id="variable-shadowing",
            category=IssueCategory.BUG,
            severity=Severity.LOW,
            description="内层作用域变量名覆盖了外层变量（变量遮蔽）",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="避免内层变量名覆盖外层同名变量，可能导致逻辑错误",
            check_fn=_check_variable_shadowing,
        ),
    ]


def _check_mutable_default(file_path: str, content: str) -> list[RuleMatch]:
    """Check for mutable default arguments."""
    matches: list[RuleMatch] = []
    pattern = re.compile(r"def\s+\w+\([^)]*(\w+)\s*=\s*(\[\]|\{\}|set\(\)|dict\(\))")
    for i, line in enumerate(content.splitlines(), 1):
        match = pattern.search(line)
        if match:
            matches.append(
                RuleMatch(
                    line_number=i,
                    line_content=line.strip(),
                    matched_text=match.group(2),
                    suggestion=f"参数 '{match.group(1)}' 的默认值 {match.group(2)} 是可变对象，建议使用 None",
                )
            )
    return matches


def _check_is_comparison(file_path: str, content: str) -> list[RuleMatch]:
    """Only flag 'is' with non-None literals."""
    matches: list[RuleMatch] = []
    pattern = re.compile(r"\bis\s+(True|False|['\"][^'\"]*['\"]|\d+)\b")
    for i, line in enumerate(content.splitlines(), 1):
        if pattern.search(line):
            matches.append(
                RuleMatch(
                    line_number=i,
                    line_content=line.strip(),
                    matched_text=pattern.search(line).group(0),
                    suggestion="与字面量比较应使用 '==' 而非 'is'",
                )
            )
    return matches


def _check_potential_undefined(file_path: str, content: str) -> list[RuleMatch]:
    """Simple check for variables used after try blocks."""
    matches: list[RuleMatch] = []
    lines = content.splitlines()
    in_try = False
    try_assigned_vars: set[str] = set()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("try:"):
            in_try = True
            try_assigned_vars = set()
        elif in_try and stripped.startswith("except"):
            in_try = False
        elif in_try:
            assign_match = re.match(r"(\w+)\s*=", stripped)
            if assign_match:
                try_assigned_vars.add(assign_match.group(1))
        elif not in_try and try_assigned_vars:
            for var in try_assigned_vars:
                if var in stripped and "=" not in stripped.split("=")[0] if "=" in stripped else True:
                    pass  # Too many false positives to act on, skip

    return matches


def _check_float_comparison(file_path: str, content: str) -> list[RuleMatch]:
    """Check for float equality comparisons."""
    matches: list[RuleMatch] = []
    float_pattern = re.compile(r"(\d+\.\d+)\s*(==|!=)\s*(\d+\.\d+)")
    for i, line in enumerate(content.splitlines(), 1):
        if float_pattern.search(line):
            matches.append(
                RuleMatch(
                    line_number=i,
                    line_content=line.strip(),
                    matched_text=float_pattern.search(line).group(0),
                    suggestion="浮点数直接比较可能因精度问题产生意外结果，使用 abs(a-b) < epsilon",
                )
            )
    return matches


def _check_variable_shadowing(file_path: str, content: str) -> list[RuleMatch]:
    """Simple variable shadowing detection for Python files."""
    matches: list[RuleMatch] = []
    lines = content.splitlines()
    outer_vars: dict[str, int] = {}

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Track variable assignments at module/class level
        assign_match = re.match(r"^(\w+)\s*=\s*\S", stripped)
        if assign_match:
            var_name = assign_match.group(1)
            if var_name not in ("__name__", "__all__", "__version__"):
                outer_vars[var_name] = i

        # Check function parameter shadowing
        func_match = re.match(r"\s*def\s+\w+\(([^)]*)\)", stripped)
        if func_match:
            params = re.findall(r"(\w+)\s*[=:,)]", func_match.group(1))
            for param in params:
                if param in outer_vars:
                    matches.append(
                        RuleMatch(
                            line_number=i,
                            line_content=stripped,
                            matched_text=param,
                            suggestion=f"参数 '{param}' 覆盖了第 {outer_vars[param]} 行定义的变量",
                        )
                    )

    return matches
