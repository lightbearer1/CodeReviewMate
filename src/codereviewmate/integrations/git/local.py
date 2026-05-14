"""Local git repository adapter using GitPython."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from codereviewmate.integrations.git.base import GitPlatform, PRFile, PRInfo, ReviewComment

logger = logging.getLogger(__name__)


class LocalGitPlatform(GitPlatform):
    """Interact with a local git repository via subprocess."""

    def __init__(self, repo_path: str = "."):
        self._repo_path = str(Path(repo_path).resolve())

    def get_pr(self, pr_id: str) -> PRInfo:
        raise NotImplementedError("Local git has no PR concept — use a platform adapter")

    def get_pr_diff(self, pr_id: str) -> str:
        raise NotImplementedError("Local git has no PR concept")

    def get_pr_files(self, pr_id: str) -> list[PRFile]:
        raise NotImplementedError("Local git has no PR concept")

    def get_diff(self, base_ref: str = "HEAD~1", target_ref: str = "HEAD") -> str:
        """Get diff between two refs."""
        return self._run_git(["diff", f"{base_ref}..{target_ref}"])

    def get_staged_diff(self) -> str:
        """Get currently staged diff."""
        return self._run_git(["diff", "--cached"])

    def get_unstaged_diff(self) -> str:
        """Get unstaged changes."""
        return self._run_git(["diff"])

    def get_changed_files(
        self,
        base_ref: str = "HEAD~1",
        target_ref: str = "HEAD",
        staged_only: bool = False,
    ) -> list[str]:
        """Get list of changed files between refs."""
        if staged_only:
            files = self._run_git(["diff", "--name-only", "--cached"])
        else:
            files = self._run_git(["diff", "--name-only", f"{base_ref}..{target_ref}"])
        return [f for f in files.split("\n") if f.strip()]

    def get_recent_commits(self, count: int = 10) -> list[dict]:
        """Get recent commit metadata."""
        output = self._run_git(
            ["log", f"-{count}", "--format=%H|%an|%ae|%aI|%s"]
        )
        commits: list[dict] = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "subject": parts[4],
                })
        return commits

    def get_file_content(self, file_path: str, ref: str = "HEAD") -> Optional[str]:
        """Get content of a file at a specific ref."""
        try:
            return self._run_git(["show", f"{ref}:{file_path}"])
        except RuntimeError:
            return None

    def get_branch_name(self) -> str:
        """Get current branch name."""
        name = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return name.strip()

    def get_repo_url(self) -> str:
        try:
            return self._run_git(["config", "--get", "remote.origin.url"]).strip()
        except RuntimeError:
            return ""

    def get_default_branch(self) -> str:
        try:
            raw = self._run_git(["symbolic-ref", "refs/remotes/origin/HEAD"])
            return raw.strip().split("/")[-1]
        except RuntimeError:
            raw = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
            return raw.strip()

    def post_review(self, pr_id: str, comments: list[ReviewComment], summary: str = "") -> None:
        raise NotImplementedError("Local git cannot post reviews")

    def _run_git(self, args: list[str]) -> str:
        """Run a git command and return stdout, raising on error."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.debug("git %s failed: %s", " ".join(args), e.stderr)
            raise RuntimeError(f"git {' '.join(args)} failed: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError("git not found on this system") from None
