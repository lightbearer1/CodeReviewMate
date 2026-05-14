"""Auto-fix patch generation for fixable issues."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from codereviewmate.core.models.review import Issue, Patch


class PatchGenerator:
    """Generates unified diff patches for auto-fixable issues."""

    @staticmethod
    def generate(file_path: str, issue: Issue, original_content: str) -> Patch | None:
        """Generate a fix patch for a single issue."""
        if not issue.auto_fixable:
            return None

        fixer_map = {
            "no-debug-print": _fix_debug_print,
            "no-console-log": _fix_console_log,
            "no-trailing-whitespace": _fix_trailing_whitespace,
            "equality-none": _fix_equality_none,
        }

        fixer = fixer_map.get(issue.rule_id or "")
        if fixer is None:
            return None

        fixed_content = fixer(original_content, issue)
        if fixed_content == original_content:
            return None

        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            fixed_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )

        return Patch(
            issue_id=issue.rule_id or "",
            file_path=file_path,
            original_lines=original_content[issue.line_start - 1 : issue.line_start]
            if issue.line_start
            else "",
            fixed_lines="",
            unified_diff="".join(diff),
        )

    def generate_all(
        self, issues: list[Issue], file_contents: dict[str, str]
    ) -> list[Patch]:
        """Generate patches for all fixable issues."""
        patches: list[Patch] = []
        for issue in issues:
            content = file_contents.get(issue.file_path, "")
            if not content:
                continue
            patch = self.generate(issue.file_path, issue, content)
            if patch:
                patches.append(patch)
        return patches


class PatchApplier:
    """Applies generated patches to files."""

    @staticmethod
    def apply(patch: Patch, repo_path: str = ".") -> bool:
        """Apply a single patch to the filesystem."""
        import subprocess
        import tempfile

        patch_file = Path(tempfile.mktemp(suffix=".patch"))
        try:
            patch_file.write_text(patch.unified_diff, encoding="utf-8")
            base = Path(repo_path)
            result = subprocess.run(
                ["git", "apply", str(patch_file)],
                cwd=str(base),
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False
        finally:
            if patch_file.exists():
                patch_file.unlink()

    @staticmethod
    def apply_all(patches: list[Patch], repo_path: str = ".") -> dict[str, bool]:
        """Apply multiple patches and return results."""
        results: dict[str, bool] = {}
        for patch in patches:
            results[patch.file_path] = PatchApplier.apply(patch, repo_path)
        return results


def _fix_debug_print(content: str, issue: Issue) -> str:
    """Remove or comment out debug print statements."""
    lines = content.splitlines()
    if issue.line_start and 0 < issue.line_start <= len(lines):
        i = issue.line_start - 1
        # Replace print with comment
        lines[i] = re.sub(r"(\s*)print\s*\(", r"\1# print(", lines[i])
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


def _fix_console_log(content: str, issue: Issue) -> str:
    """Remove or comment out console.log statements."""
    lines = content.splitlines()
    if issue.line_start and 0 < issue.line_start <= len(lines):
        i = issue.line_start - 1
        lines[i] = re.sub(r"(\s*)console\.(log|debug|info|warn)\s*\(", r"\1// console.\2(", lines[i])
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


def _fix_trailing_whitespace(content: str, issue: Issue) -> str:
    """Remove trailing whitespace."""
    lines = content.splitlines()
    if issue.line_start and 0 < issue.line_start <= len(lines):
        i = issue.line_start - 1
        lines[i] = lines[i].rstrip()
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


def _fix_equality_none(content: str, issue: Issue) -> str:
    """Replace == None with is None."""
    lines = content.splitlines()
    if issue.line_start and 0 < issue.line_start <= len(lines):
        i = issue.line_start - 1
        lines[i] = lines[i].replace("== None", "is None").replace("!= None", "is not None")
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")
