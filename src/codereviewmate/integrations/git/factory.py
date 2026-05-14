"""Git platform factory — creates the appropriate platform adapter."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from codereviewmate.integrations.git.base import GitPlatform
from codereviewmate.integrations.git.github_ import GitHubPlatform
from codereviewmate.integrations.git.gitlab_ import GitLabPlatform
from codereviewmate.integrations.git.gitee import GiteePlatform
from codereviewmate.integrations.git.local import LocalGitPlatform

logger = logging.getLogger(__name__)


class GitPlatformType(str, Enum):
    LOCAL = "local"
    GITHUB = "github"
    GITLAB = "gitlab"
    GITEE = "gitee"


def create_git_platform(
    platform: GitPlatformType = GitPlatformType.LOCAL,
    repo: str = "",
    token: Optional[str] = None,
    repo_path: str = ".",
) -> GitPlatform:
    """Create a Git platform adapter."""
    logger.info("Creating git platform: %s", platform.value)

    if platform == GitPlatformType.LOCAL:
        return LocalGitPlatform(repo_path=repo_path)

    if platform == GitPlatformType.GITHUB:
        return GitHubPlatform(repo=repo, token=token, repo_path=repo_path)

    if platform == GitPlatformType.GITLAB:
        return GitLabPlatform(project=repo, token=token, repo_path=repo_path)

    if platform == GitPlatformType.GITEE:
        return GiteePlatform(repo=repo, token=token, repo_path=repo_path)

    raise ValueError(f"Unknown git platform: {platform}")


def detect_platform(repo_path: str = ".") -> GitPlatformType:
    """Auto-detect the git platform from remote URL."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        url = result.stdout.strip().lower()
        if "github.com" in url:
            return GitPlatformType.GITHUB
        if "gitlab" in url:
            return GitPlatformType.GITLAB
        if "gitee.com" in url:
            return GitPlatformType.GITEE
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return GitPlatformType.LOCAL
