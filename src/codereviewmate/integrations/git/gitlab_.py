"""GitLab platform adapter."""

from __future__ import annotations

import logging
import os
from typing import Optional

from codereviewmate.integrations.git.base import GitPlatform, PRFile, PRInfo, ReviewComment

logger = logging.getLogger(__name__)


class GitLabPlatform(GitPlatform):
    """GitLab API integration via python-gitlab or glab CLI fallback."""

    def __init__(
        self,
        project: str = "",
        token: Optional[str] = None,
        url: str = "https://gitlab.com",
        repo_path: str = ".",
    ):
        self._repo_path = repo_path
        self._token = token or os.environ.get("GITLAB_TOKEN")
        self._url = url
        self._project = project or self._infer_project()
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import gitlab

                self._client = gitlab.Gitlab(self._url, private_token=self._token)
            except ImportError:
                logger.debug("python-gitlab not installed, using glab CLI fallback")
                self._client = False
        return self._client

    def get_pr(self, pr_id: str) -> PRInfo:
        return self._get_mr_via_cli(pr_id)

    def get_pr_diff(self, pr_id: str) -> str:
        import subprocess

        result = subprocess.run(
            ["glab", "mr", "diff", pr_id],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"glab mr diff failed: {result.stderr}")
        return result.stdout

    def get_pr_files(self, pr_id: str) -> list[PRFile]:
        import json
        import subprocess

        result = subprocess.run(
            ["glab", "api", f"projects/{self._project}/merge_requests/{pr_id}/changes"],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"glab api changes failed: {result.stderr}")

        data = json.loads(result.stdout)
        files: list[PRFile] = []
        for change in data.get("changes", []):
            files.append(PRFile(
                path=change.get("new_path", change.get("old_path", "")),
                status=self._map_status(change),
                additions=int(change.get("additions", 0)),
                deletions=int(change.get("deletions", 0)),
                diff=change.get("diff", ""),
            ))
        return files

    def post_review(self, pr_id: str, comments: list[ReviewComment], summary: str = "") -> None:
        import subprocess

        if summary:
            subprocess.run(
                ["glab", "mr", "note", pr_id, "--message", summary],
                cwd=self._repo_path,
                check=True,
            )
        for c in comments:
            body = f"**{c.severity.upper()}** — {c.file_path}:{c.line}\n{c.body}"
            subprocess.run(
                ["glab", "mr", "note", pr_id, "--message", body],
                cwd=self._repo_path,
                check=True,
            )

    def get_repo_url(self) -> str:
        return f"{self._url}/{self._project}"

    def get_default_branch(self) -> str:
        try:
            import subprocess
            result = subprocess.run(
                ["glab", "api", f"projects/{self._project}"],
                cwd=self._repo_path, capture_output=True, text=True,
            )
            if result.returncode == 0:
                import json
                return json.loads(result.stdout).get("default_branch", "main")
        except Exception:
            pass
        return "main"

    def _get_mr_via_cli(self, mr_id: str) -> PRInfo:
        import json
        import subprocess

        result = subprocess.run(
            ["glab", "mr", "view", mr_id, "--output", "json"],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"glab mr view failed: {result.stderr}")

        data = json.loads(result.stdout)
        return PRInfo(
            id=str(data.get("iid", mr_id)),
            title=data.get("title", ""),
            description=data.get("description", ""),
            author=data.get("author", {}).get("username", ""),
            source_branch=data.get("source_branch", ""),
            target_branch=data.get("target_branch", ""),
            url=data.get("web_url", ""),
            labels=data.get("labels", []),
        )

    @staticmethod
    def _map_status(change: dict) -> str:
        if change.get("new_file"):
            return "added"
        if change.get("deleted_file"):
            return "removed"
        if change.get("renamed_file"):
            return "renamed"
        return "modified"

    def _infer_project(self) -> str:
        import subprocess

        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            url = result.stdout.strip()
            parts = url.rstrip("/").split(":/")[-1].removesuffix(".git")
            return parts
        except subprocess.CalledProcessError:
            pass

        raise ValueError("Cannot determine GitLab project. Set GITLAB_PROJECT env var or pass project explicitly.")
