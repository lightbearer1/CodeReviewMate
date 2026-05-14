"""Abstract Git platform interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PRInfo:
    """Pull request information."""

    id: str
    title: str
    description: str = ""
    author: str = ""
    source_branch: str = ""
    target_branch: str = ""
    url: str = ""
    labels: list[str] = field(default_factory=list)


@dataclass
class PRFile:
    """A file changed in a PR."""

    path: str
    status: str  # added, modified, removed, renamed
    additions: int = 0
    deletions: int = 0
    diff: str = ""


@dataclass
class ReviewComment:
    """A review comment to post on a PR."""

    file_path: str
    line: Optional[int] = None
    body: str = ""
    severity: str = "info"


class GitPlatform(ABC):
    """Abstract interface for Git platform operations."""

    @abstractmethod
    def get_pr(self, pr_id: str) -> PRInfo:
        """Fetch PR information."""
        ...

    @abstractmethod
    def get_pr_diff(self, pr_id: str) -> str:
        """Get the full diff of a PR."""
        ...

    @abstractmethod
    def get_pr_files(self, pr_id: str) -> list[PRFile]:
        """Get list of changed files in a PR."""
        ...

    @abstractmethod
    def post_review(self, pr_id: str, comments: list[ReviewComment], summary: str = "") -> None:
        """Post review comments to a PR."""
        ...

    @abstractmethod
    def get_repo_url(self) -> str:
        """Get the repository URL."""
        ...

    @abstractmethod
    def get_default_branch(self) -> str:
        """Get the default branch name."""
        ...

    def create_pr(
        self,
        title: str,
        head: str,
        base: str = "",
        body: str = "",
    ) -> PRInfo:
        """Create a pull request. Optional — may not be implemented."""
        raise NotImplementedError("Creating PRs is not supported for this platform")
