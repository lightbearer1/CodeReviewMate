"""Cyclomatic complexity and code metric analysis using tree-sitter AST."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codereviewmate.core.review.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer


@dataclass
class ComplexityMetrics:
    """Complexity metrics for a function or file."""

    name: str
    cyclomatic_complexity: int = 1
    lines_of_code: int = 0
    nesting_depth: int = 0
    parameter_count: int = 0
    cognitive_complexity: int = 0


@dataclass
class FileMetrics:
    """Aggregate metrics for a file."""

    file_path: str
    total_lines: int = 0
    functions: list[ComplexityMetrics] = field(default_factory=list)
    max_complexity: int = 0
    max_nesting: int = 0
    avg_complexity: float = 0.0


class ComplexityAnalyzer:
    """Computes code complexity metrics using tree-sitter AST."""

    COMPLEXITY_THRESHOLDS = {
        "cyclomatic_complexity": 10,  # warn above 10
        "nesting_depth": 4,
        "parameter_count": 5,
        "function_lines": 50,
    }

    # Node types that increase cyclomatic complexity
    BRANCH_NODES = {
        "if_statement",
        "elif_clause",
        "else_clause",
        "for_statement",
        "while_statement",
        "case_clause",
        "switch_statement",
        "match_case",
        "catch_clause",
        "&&",
        "||",
        "conditional_expression",
        "ternary_expression",
    }

    # Node types that increase nesting depth
    NESTING_NODES = {
        "if_statement",
        "for_statement",
        "while_statement",
        "switch_statement",
        "try_statement",
        "match_statement",
        "block",
        "class_body",
        "function_body",
    }

    def __init__(self):
        self._analyzer = TreeSitterAnalyzer()

    def analyze_file(self, file_path: str, source: str) -> FileMetrics:
        """Analyze complexity for an entire file."""
        lines = source.splitlines()
        funcs = self._analyzer.extract_functions(file_path, source)

        metrics_list: list[ComplexityMetrics] = []
        for func in funcs:
            # Extract function source
            func_source_lines = lines[func["line_start"] - 1 : func["line_end"]]
            func_source = "\n".join(func_source_lines)

            metrics = self._analyze_function(func["name"], func_source, func.get("params", []))
            metrics_list.append(metrics)

        max_cc = max((m.cyclomatic_complexity for m in metrics_list), default=0)
        max_nest = max((m.nesting_depth for m in metrics_list), default=0)
        avg_cc = (
            sum(m.cyclomatic_complexity for m in metrics_list) / len(metrics_list)
            if metrics_list
            else 0.0
        )

        return FileMetrics(
            file_path=file_path,
            total_lines=len(lines),
            functions=metrics_list,
            max_complexity=max_cc,
            max_nesting=max_nest,
            avg_complexity=avg_cc,
        )

    def _analyze_function(
        self, name: str, source: str, params: list[str]
    ) -> ComplexityMetrics:
        """Compute metrics for a single function."""
        cc = 1  # Base complexity is 1
        nesting = 0
        current_nesting = 0

        try:
            parsed = self._analyzer.parse_file("_.py", source)
            if parsed:
                _, root, _, _ = parsed
                cc += self._count_branches(root)
                nesting = self._max_nesting(root, 0)
        except Exception:
            # Fallback to regex-based counting
            cc += self._regex_count_branches(source)
            nesting = self._regex_count_nesting(source)

        func_lines = len(source.splitlines())

        return ComplexityMetrics(
            name=name,
            cyclomatic_complexity=cc,
            lines_of_code=func_lines,
            nesting_depth=nesting,
            parameter_count=len(params),
            cognitive_complexity=cc + nesting * 2,  # Simple estimation
        )

    def _count_branches(self, node) -> int:
        """Count branching nodes in the AST."""
        count = 0
        if node.type in self.BRANCH_NODES:
            count += 1
        for child in node.children:
            count += self._count_branches(child)
        return count

    def _max_nesting(self, node, current_depth: int) -> int:
        """Find maximum nesting depth in the AST."""
        max_depth = current_depth
        if node.type in self.NESTING_NODES:
            max_depth = current_depth + 1
            for child in node.children:
                child_depth = self._max_nesting(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)
            return max_depth
        for child in node.children:
            child_depth = self._max_nesting(child, current_depth)
            max_depth = max(max_depth, child_depth)
        return max_depth

    @staticmethod
    def _regex_count_branches(source: str) -> int:
        """Fallback: count branching keywords."""
        import re

        branch_keywords = [
            r"\bif\b",
            r"\belif\b",
            r"\belse\b",
            r"\bfor\b",
            r"\bwhile\b",
            r"\bcase\b",
            r"\bcatch\b",
            r"\?\s*:",
        ]
        count = 0
        for pattern in branch_keywords:
            count += len(re.findall(pattern, source))
        return count

    @staticmethod
    def _regex_count_nesting(source: str) -> int:
        """Fallback: estimate nesting from indentation."""
        max_indent = 0
        for line in source.splitlines():
            stripped = line.lstrip()
            if stripped and not stripped.startswith(("#", "//", "/*", "*")):
                indent = len(line) - len(stripped)
                max_indent = max(max_indent, indent)
        return max_indent // 4
