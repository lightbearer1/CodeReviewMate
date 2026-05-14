"""GitHub platform adapter."""

from __future__ import annotations

import logging
import os
from typing import Optional

from codereviewmate.integrations.git.base import GitPlatform, PRFile, PRInfo, ReviewComment

logger = logging.getLogger(__name__)


class GitHubPlatform(GitPlatform):
    """GitHub API integration via PyGithub or gh CLI fallback."""

    def __init__(
        self,
        repo: str = "",
        token: Optional[str] = None,
        repo_path: str = ".",
    ):
        self._repo_path = repo_path
        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._repo = repo or self._infer_repo()
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from github import Github
                from github.exceptions import GithubException

                self._client = Github(self._token) if self._token else Github()
            except ImportError:
                logger.debug("PyGithub not installed, using gh CLI fallback")
                self._client = False
        return self._client

    def get_pr(self, pr_id: str) -> PRInfo:
        client = self._get_client()
        if client:
            return self._get_pr_via_sdk(client, pr_id)
        return self._get_pr_via_cli(pr_id)

    def _get_pr_via_sdk(self, client, pr_id: str) -> PRInfo:
        from github import Github

        repo = client.get_repo(self._repo)
        pr = repo.get_pull(int(pr_id))
        return PRInfo(
            id=str(pr.number),
            title=pr.title,
            description=pr.body or "",
            author=pr.user.login if pr.user else "",
            source_branch=pr.head.ref,
            target_branch=pr.base.ref,
            url=pr.html_url,
            labels=[label.name for label in pr.labels],
        )

    def _get_pr_via_cli(self, pr_id: str) -> PRInfo:
        import json
        import subprocess

        result = subprocess.run(
            ["gh", "pr", "view", pr_id, "--json", "number,title,body,author,headRefName,baseRefName,url,labels"],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gh pr view failed: {result.stderr}")

        data = json.loads(result.stdout)
        return PRInfo(
            id=str(data.get("number", pr_id)),
            title=data.get("title", ""),
            description=data.get("body", ""),
            author=data.get("author", {}).get("login", ""),
            source_branch=data.get("headRefName", ""),
            target_branch=data.get("baseRefName", ""),
            url=data.get("url", ""),
            labels=[l["name"] for l in data.get("labels", [])],
        )

    def get_pr_diff(self, pr_id: str) -> str:
        import subprocess

        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_id)],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Try GitHub API fallback
            return self._get_pr_diff_via_api(pr_id)
        return result.stdout

    def _get_pr_diff_via_api(self, pr_id: str) -> str:
        import subprocess

        result = subprocess.run(
            ["gh", "api", f"repos/{self._repo}/pulls/{pr_id}", "-H", "Accept: application/vnd.github.v3.diff"],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to fetch PR diff: {result.stderr}")
        return result.stdout

    def get_pr_files(self, pr_id: str) -> list[PRFile]:
        client = self._get_client()
        if client:
            return self._get_pr_files_via_sdk(client, pr_id)
        return self._get_pr_files_via_cli(pr_id)

    def _get_pr_files_via_sdk(self, client, pr_id: str) -> list[PRFile]:
        repo = client.get_repo(self._repo)
        pr = repo.get_pull(int(pr_id))
        files: list[PRFile] = []
        for f in pr.get_files():
            files.append(PRFile(
                path=f.filename,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                diff=f.patch or "",
            ))
        return files

    def _get_pr_files_via_cli(self, pr_id: str) -> list[PRFile]:
        import json
        import subprocess

        result = subprocess.run(
            ["gh", "pr", "view", str(pr_id), "--json", "files"],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gh pr view files failed: {result.stderr}")

        data = json.loads(result.stdout)
        files: list[PRFile] = []
        for f in data.get("files", []):
            files.append(PRFile(
                path=f.get("path", ""),
                status=f.get("status", "modified"),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
            ))
        return files

    def post_review(self, pr_id: str, comments: list[ReviewComment], summary: str = "") -> None:
        client = self._get_client()
        if client:
            self._post_review_via_sdk(client, pr_id, comments, summary)
        else:
            self._post_review_via_cli(pr_id, comments, summary)

    def _post_review_via_sdk(self, client, pr_id: str, comments: list[ReviewComment], summary: str) -> None:
        repo = client.get_repo(self._repo)
        pr = repo.get_pull(int(pr_id))
        if summary:
            pr.create_issue_comment(summary)
        for c in comments:
            pr.create_review_comment(body=c.body, commit_id=pr.head.sha, path=c.file_path, position=c.line or 1)

    def _post_review_via_cli(self, pr_id: str, comments: list[ReviewComment], summary: str) -> None:
        import subprocess

        if summary:
            subprocess.run(
                ["gh", "pr", "comment", str(pr_id), "--body", summary],
                cwd=self._repo_path,
                check=True,
            )
        for c in comments:
            body = f"**{c.severity.upper()}** — {c.file_path}:{c.line}\n{c.body}"
            subprocess.run(
                ["gh", "pr", "comment", str(pr_id), "--body", body],
                cwd=self._repo_path,
                check=True,
            )

    def get_repo_url(self) -> str:
        return f"https://github.com/{self._repo}"

    def get_default_branch(self) -> str:
        client = self._get_client()
        if client:
            repo = client.get_repo(self._repo)
            return repo.default_branch
        # Fallback via gh CLI
        import subprocess
        import json

        result = subprocess.run(
            ["gh", "repo", "view", self._repo, "--json", "defaultBranchRef"],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("defaultBranchRef", {}).get("name", "main")
        return "main"

    def _infer_repo(self) -> str:
        """Infer owner/repo from git remote."""
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
            if "github.com" in url:
                parts = url.rstrip("/").split("github.com/")[-1]
                return parts.removesuffix(".git")
        except subprocess.CalledProcessError:
            pass

        raise ValueError("Cannot determine GitHub repo. Set GITHUB_REPOSITORY env var or pass repo explicitly.")
