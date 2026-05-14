"""Deep review engine — LLM-powered architecture compliance and semantic analysis."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from jinja2 import Environment, PackageLoader, select_autoescape

from codereviewmate.core.config.manager import get_config
from codereviewmate.core.context.engine import get_rag_engine
from codereviewmate.core.llm.base import LLMProvider
from codereviewmate.core.llm.factory import create_llm_provider
from codereviewmate.core.models.review import (
    ContextBundle,
    DeepReviewResult,
    Issue,
    IssueCategory,
    Severity,
)
from codereviewmate.integrations.git.base import GitPlatform
from codereviewmate.integrations.git.factory import GitPlatformType, create_git_platform

logger = logging.getLogger(__name__)

_SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
}


class DeepReviewEngine:
    """Orchestrates deep, LLM-powered code review with architecture compliance check.

    Uses RAG context + PR diff + team architecture constraints to produce
    a comprehensive review with architecture compliance scoring.
    """

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        platform: Optional[GitPlatform] = None,
    ):
        self._config = get_config()
        self._llm = llm
        self._platform = platform
        self._rag = get_rag_engine()
        try:
            self._jinja = Environment(
                loader=PackageLoader("codereviewmate.core.llm", "prompts"),
                autoescape=select_autoescape(),
            )
        except Exception:
            self._jinja = Environment(
                loader=PackageLoader("codereviewmate.core.llm", "prompts"),
            )

    async def review_pr(
        self,
        pr_id: str,
        platform_type: GitPlatformType = GitPlatformType.LOCAL,
        repo_path: str = ".",
    ) -> DeepReviewResult:
        """Run a deep review on a pull request."""
        start = time.monotonic()

        platform = self._platform or create_git_platform(
            platform=platform_type, repo_path=repo_path
        )

        pr_info = platform.get_pr(pr_id)
        diff_text = platform.get_pr_diff(pr_id)

        return await self._review_diff(
            diff_text=diff_text,
            pr_title=pr_info.title,
            pr_description=pr_info.description,
            duration_start=start,
        )

    async def review_diff(
        self,
        diff_text: str,
        repo_path: str = ".",
        pr_title: str = "",
        pr_description: str = "",
    ) -> DeepReviewResult:
        """Run a deep review on a raw diff string."""
        start = time.monotonic()
        return await self._review_diff(
            diff_text=diff_text,
            pr_title=pr_title,
            pr_description=pr_description,
            duration_start=start,
        )

    async def review_local(
        self,
        repo_path: str = ".",
        base_ref: str = "HEAD~1",
        target_ref: str = "HEAD",
    ) -> DeepReviewResult:
        """Run a deep review on local git changes."""
        start = time.monotonic()

        platform = self._platform or create_git_platform(
            platform=GitPlatformType.LOCAL, repo_path=repo_path
        )
        diff_text = platform.get_diff(base_ref=base_ref, target_ref=target_ref)

        return await self._review_diff(
            diff_text=diff_text,
            duration_start=start,
        )

    async def _review_diff(
        self,
        diff_text: str,
        pr_title: str = "",
        pr_description: str = "",
        duration_start: float = 0.0,
    ) -> DeepReviewResult:
        """Internal: run the LLM architecture compliance check on a diff."""
        if not diff_text.strip():
            return DeepReviewResult(
                passed=True,
                issues=[],
                summary="No changes to review.",
                duration_ms=0.0,
            )

        # 1. Assemble RAG context
        query = self._build_context_query(diff_text, pr_title, pr_description)
        context = await self._rag.query_context(query)

        # 2. Build prompt
        prompt = self._render_prompt(diff_text, context, pr_title, pr_description)

        # 3. Call LLM
        llm = self._llm or create_llm_provider()
        messages = llm.format_messages(
            system_prompt="You are an expert code reviewer and architect. Output ONLY valid JSON.",
            user_message=prompt,
        )

        try:
            response = await llm.chat(messages, temperature=0.1, max_tokens=4096)
            result_data = self._parse_response(response.content)
        except Exception as e:
            logger.error("LLM deep review failed: %s", e)
            return DeepReviewResult(
                passed=True,
                issues=[],
                summary=f"Deep review skipped — LLM error: {e}",
                duration_ms=(time.monotonic() - duration_start) * 1000,
                token_usage=None,
            )

        # 4. Convert to DeepReviewResult
        issues = self._convert_issues(result_data.get("violations", []))
        passed = result_data.get("compliant", True) and len(issues) == 0
        arch_score = result_data.get("architecture_score")

        summary_parts = []
        if result_data.get("recommendations"):
            summary_parts.append("## Recommendations")
            for r in result_data["recommendations"]:
                summary_parts.append(f"- {r}")
        if arch_score is not None:
            summary_parts.insert(0, f"Architecture Score: {arch_score}/100")

        duration_ms = (time.monotonic() - duration_start) * 1000

        return DeepReviewResult(
            passed=passed,
            issues=issues,
            summary="\n".join(summary_parts) if summary_parts else result_data.get("summary", ""),
            architecture_compliance={
                "score": arch_score,
                "compliant": result_data.get("compliant", passed),
                "recommendations": result_data.get("recommendations", []),
            },
            token_usage=response.usage if hasattr(response, "usage") else None,
            duration_ms=duration_ms,
        )

    def _render_prompt(
        self,
        diff_text: str,
        context: ContextBundle,
        pr_title: str = "",
        pr_description: str = "",
    ) -> str:
        """Render the deep review Jinja2 template."""
        template = self._jinja.get_template("deep_arch.j2")

        constraints = context.architecture_constraints or self._default_constraints()

        return template.render(
            team_name=self._config.team_name,
            architecture_constraints=constraints,
            relevant_docs=context.relevant_docs,
            relevant_reviews=context.relevant_reviews,
            relevant_standards=context.relevant_standards,
            pr_title=pr_title,
            pr_description=pr_description,
            diff=diff_text,
        )

    def _build_context_query(
        self,
        diff_text: str,
        pr_title: str = "",
        pr_description: str = "",
    ) -> str:
        """Build a query string for RAG context retrieval."""
        parts = []
        if pr_title:
            parts.append(pr_title)
        if pr_description:
            parts.append(pr_description[:200])
        # Extract key identifiers from diff for better retrieval
        parts.append(diff_text[:500])
        return " ".join(parts)

    @staticmethod
    def _parse_response(content: str) -> dict:
        """Parse the LLM JSON response, handling markdown code fences."""
        content = content.strip()

        if content.startswith("```"):
            lines = content.split("\n")
            end = next((i for i, line in enumerate(lines[1:], 1) if line.startswith("```")), len(lines))
            content = "\n".join(lines[1:end])

        return json.loads(content)

    @staticmethod
    def _convert_issues(violations: list[dict]) -> list[Issue]:
        """Convert LLM violation dicts to Issue models."""
        issues: list[Issue] = []
        for v in violations:
            try:
                if "constraint" not in v or "description" not in v:
                    logger.debug("Skipping violation without required fields: %s", v)
                    continue
                issues.append(Issue(
                    severity=_SEVERITY_MAP.get(
                        v.get("severity", "medium").lower(), Severity.MEDIUM
                    ),
                    category=IssueCategory.ARCHITECTURE,
                    title=v["constraint"],
                    description=v["description"],
                    file_path=v.get("file_path", ""),
                    suggestion=v.get("fix_suggestion"),
                    rule_id="deep-arch-compliance",
                ))
            except Exception as e:
                logger.debug("Skipping malformed violation: %s", e)
        return issues

    @staticmethod
    def _default_constraints() -> list[str]:
        """Fallback architecture constraints when no context is available."""
        return [
            "New modules must follow the project's directory structure conventions",
            "Database access must go through repository/DAO layer, not directly from UI or CLI",
            "Dependencies must flow from less stable to more stable layers",
            "Public interfaces must be versioned (API endpoints, CLI commands)",
            "New external dependencies must be justified in PR description",
            "Error handling must propagate properly — no bare except or silent failures",
            "Configuration must be externalized — no hardcoded values in logic",
        ]
