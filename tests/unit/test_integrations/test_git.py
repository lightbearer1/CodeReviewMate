"""Tests for Git platform adapters."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from codereviewmate.integrations.git.base import PRFile, PRInfo, ReviewComment
from codereviewmate.integrations.git.factory import (
    GitPlatformType,
    create_git_platform,
    detect_platform,
)
from codereviewmate.integrations.git.local import LocalGitPlatform


class TestPRInfo:
    def test_pr_info_defaults(self):
        pr = PRInfo(id="1", title="Test PR")
        assert pr.id == "1"
        assert pr.title == "Test PR"
        assert pr.description == ""
        assert pr.labels == []

    def test_pr_info_full(self):
        pr = PRInfo(
            id="42",
            title="Fix login bug",
            description="Fixes #123",
            author="dev1",
            source_branch="fix/login",
            target_branch="main",
            labels=["bug", "urgent"],
        )
        assert pr.author == "dev1"
        assert pr.labels == ["bug", "urgent"]


class TestPRFile:
    def test_pr_file_defaults(self):
        f = PRFile(path="src/app.py", status="modified")
        assert f.path == "src/app.py"
        assert f.additions == 0
        assert f.deletions == 0

    def test_pr_file_with_stats(self):
        f = PRFile(path="src/app.py", status="modified", additions=10, deletions=5, diff="@@ -1,3 +1,4 @@")
        assert f.additions == 10
        assert f.deletions == 5
        assert "@@" in f.diff


class TestReviewComment:
    def test_review_comment(self):
        c = ReviewComment(file_path="src/app.py", line=10, body="Use is None instead of == None", severity="medium")
        assert c.severity == "medium"
        assert c.line == 10


class TestLocalGitPlatform:
    def test_init_resolves_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_result = subprocess.run(
                ["git", "init", tmpdir],
                capture_output=True, text=True,
            )
            assert init_result.returncode == 0

            platform = LocalGitPlatform(repo_path=tmpdir)
            normalized_tmp = Path(tmpdir).resolve()
            normalized_repo = Path(platform._repo_path).resolve()
            assert normalized_tmp == normalized_repo

    def test_get_branch_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", tmpdir], capture_output=True, text=True)
            # Create initial commit so HEAD exists
            (Path(tmpdir) / "README.md").write_text("# Test\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True, text=True)
            subprocess.run(
                ["git", "checkout", "-b", "main"],
                cwd=tmpdir, capture_output=True, text=True,
            )

            platform = LocalGitPlatform(repo_path=tmpdir)
            assert platform.get_branch_name() == "main"

    def test_get_diff_returns_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", tmpdir], capture_output=True, text=True)

            # Create and commit a file
            readme = Path(tmpdir) / "README.md"
            readme.write_text("# Test\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True, text=True)

            # Modify it
            readme.write_text("# Test\n\nExtra line\n", encoding="utf-8")

            platform = LocalGitPlatform(repo_path=tmpdir)
            diff = platform.get_unstaged_diff()
            assert "Extra line" in diff

    def test_get_changed_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", tmpdir], capture_output=True, text=True)

            (Path(tmpdir) / "a.py").write_text("x=1\n", encoding="utf-8")
            (Path(tmpdir) / "b.py").write_text("y=2\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True, text=True)

            # Modify a file
            (Path(tmpdir) / "a.py").write_text("x=1\n; y=2\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True, text=True)

            platform = LocalGitPlatform(repo_path=tmpdir)
            files = platform.get_changed_files(staged_only=True)
            assert "a.py" in files

    def test_get_default_branch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", tmpdir], capture_output=True, text=True)
            # Create initial commit so HEAD exists
            (Path(tmpdir) / "README.md").write_text("# Test\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True, text=True)
            subprocess.run(
                ["git", "checkout", "-b", "main"],
                cwd=tmpdir, capture_output=True, text=True,
            )

            platform = LocalGitPlatform(repo_path=tmpdir)
            branch = platform.get_default_branch()
            assert branch in ("main", "master")

    def test_not_implemented_methods(self):
        platform = LocalGitPlatform(repo_path=".")
        with pytest.raises(NotImplementedError):
            platform.get_pr("1")
        with pytest.raises(NotImplementedError):
            platform.get_pr_diff("1")
        with pytest.raises(NotImplementedError):
            platform.get_pr_files("1")


class TestGitPlatformFactory:
    def test_create_local(self):
        p = create_git_platform(GitPlatformType.LOCAL, repo_path=".")
        assert isinstance(p, LocalGitPlatform)

    def test_detect_platform_local(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", tmpdir], capture_output=True, text=True)
            result = detect_platform(repo_path=tmpdir)
            assert result == GitPlatformType.LOCAL
