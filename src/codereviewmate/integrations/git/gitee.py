"""Gitee (码云) platform adapter."""

from __future__ import annotations

import logging
import os
from typing import Optional

from codereviewmate.integrations.git.base import GitPlatform, PRFile, PRInfo, ReviewComment

logger = logging.getLogger(__name__)


class GiteePlatform(GitPlatform):
    """Gitee API integration using Gitee OpenAPI.

    Uses the Gitee API: https://gitee.com/api/v5
    Requires a personal access token with PR scope.
    """

    API_BASE = "https://gitee.com/api/v5"

    def __init__(
        self,
        repo: str = "",
        token: Optional[str] = None,
        repo_path: str = ".",
    ):
        self._repo_path = repo_path
        self._token = token or os.environ.get("GITEE_TOKEN")
        self._repo = repo or self._infer_repo()
        self._session = None

    def _get_session(self):
        if self._session is None:
            import httpx
            self._session = httpx.Client(
                base_url=self.API_BASE,
                headers={"Authorization": f"token {self._token}"} if self._token else {},
                timeout=30,
            )
        return self._session

    def get_pr(self, pr_id: str) -> PRInfo:
        session = self._get_session()
        resp = session.get(f"/repos/{self._repo}/pulls/{pr_id}")
        resp.raise_for_status()
        data = resp.json()
        return PRInfo(
            id=str(data["number"]),
            title=data["title"],
            description=data.get("body", ""),
            author=data.get("user", {}).get("login", ""),
            source_branch=data.get("head", {}).get("ref", ""),
            target_branch=data.get("base", {}).get("ref", ""),
            url=data.get("html_url", ""),
            labels=[l["name"] for l in data.get("labels", [])],
        )

    def get_pr_diff(self, pr_id: str) -> str:
        session = self._get_session()
        resp = session.get(
            f"/repos/{self._repo}/pulls/{pr_id}/files",
            params={"access_token": self._token},
        )
        resp.raise_for_status()
        files = resp.json()
        diffs: list[str] = []
        for f in files:
            diffs.append(f"--- a/{f.get('filename')}\n+++ b/{f.get('filename')}")
            diffs.append(f.get("patch", ""))
        return "\n".join(diffs)

    def get_pr_files(self, pr_id: str) -> list[PRFile]:
        session = self._get_session()
        resp = session.get(f"/repos/{self._repo}/pulls/{pr_id}/files")
        resp.raise_for_status()
        data = resp.json()
        files: list[PRFile] = []
        for f in data:
            files.append(PRFile(
                path=f.get("filename", ""),
                status=f.get("status", "modified"),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                diff=f.get("patch", ""),
            ))
        return files

    def post_review(self, pr_id: str, comments: list[ReviewComment], summary: str = "") -> None:
        session = self._get_session()
        pr_info = self.get_pr(pr_id)

        if summary:
            session.post(
                f"/repos/{self._repo}/pulls/{pr_id}/comments",
                json={"body": summary},
            )

        for c in comments:
            body = f"**{c.severity.upper()}** — {c.file_path}:{c.line}\n{c.body}"
            session.post(
                f"/repos/{self._repo}/pulls/{pr_id}/comments",
                json={
                    "body": body,
                    "path": c.file_path,
                    "position": c.line or 1,
                },
            )

    def get_repo_url(self) -> str:
        return f"https://gitee.com/{self._repo}"

    def get_default_branch(self) -> str:
        return "master"

    def _infer_repo(self) -> str:
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
            if "gitee.com" in url:
                parts = url.rstrip("/").split("gitee.com")[-1].lstrip(":/").removesuffix(".git")
                return parts
        except subprocess.CalledProcessError:
            pass

        raise ValueError("Cannot determine Gitee repo. Set GITEE_REPO env var or pass repo explicitly.")
