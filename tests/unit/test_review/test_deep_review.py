"""Tests for deep review engine."""

from __future__ import annotations

import json
from unittest import mock

import pytest

from codereviewmate.core.llm.base import ChatMessage, ChatResponse
from codereviewmate.core.models.review import IssueCategory, Severity
from codereviewmate.core.review.deep_review import DeepReviewEngine


class TestDeepReviewEngine:
    def test_parse_response_handles_json_directly(self):
        content = '{"compliant": true, "violations": [], "architecture_score": 95, "recommendations": ["Keep it up"]}'
        result = DeepReviewEngine._parse_response(content)
        assert result["compliant"] is True
        assert result["architecture_score"] == 95
        assert len(result["recommendations"]) == 1

    def test_parse_response_handles_markdown_fence(self):
        content = '```json\n{"compliant": false, "violations": [], "architecture_score": 60}\n```'
        result = DeepReviewEngine._parse_response(content)
        assert result["compliant"] is False
        assert result["architecture_score"] == 60

    def test_parse_response_handles_fence_no_lang(self):
        content = '```\n{"compliant": true, "violations": []}\n```'
        result = DeepReviewEngine._parse_response(content)
        assert result["compliant"] is True

    def test_convert_issues(self):
        violations = [
            {
                "constraint": "Layering violation",
                "file_path": "src/api/handler.py",
                "severity": "high",
                "description": "Handler accessing DB directly",
                "fix_suggestion": "Use repository pattern",
            },
            {
                "constraint": "Missing error handling",
                "file_path": "src/utils/parse.py",
                "severity": "medium",
                "description": "No try-except around JSON parsing",
                "fix_suggestion": "Add try-except with logging",
            },
        ]
        issues = DeepReviewEngine._convert_issues(violations)
        assert len(issues) == 2
        assert issues[0].severity == Severity.HIGH
        assert issues[0].category == IssueCategory.ARCHITECTURE
        assert issues[0].rule_id == "deep-arch-compliance"
        assert issues[0].file_path == "src/api/handler.py"
        assert issues[1].severity == Severity.MEDIUM

    def test_convert_issues_skips_malformed(self):
        violations = [
            {"not_a_real_violation": True},
            {"constraint": "Good one", "file_path": "f.py", "severity": "low", "description": "desc"},
        ]
        issues = DeepReviewEngine._convert_issues(violations)
        assert len(issues) == 1

    def test_default_constraints(self):
        constraints = DeepReviewEngine._default_constraints()
        assert len(constraints) >= 5
        assert any("repository" in c.lower() for c in constraints)

    def test_build_context_query(self):
        diff = "diff --git a/app.py b/app.py\n+password = 'secret'\n"
        query = DeepReviewEngine._build_context_query(
            DeepReviewEngine, diff_text=diff, pr_title="Fix auth", pr_description="Updates login"
        )
        assert "Fix auth" in query
        assert "Updates login" in query


class TestDeepReviewEngineMocked:
    """Tests with mocked LLM provider."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM that returns a valid architecture review JSON."""
        m = mock.MagicMock()

        async def mock_chat(messages, temperature=0.2, max_tokens=4096, **kwargs):
            return ChatResponse(
                content=json.dumps({
                    "compliant": False,
                    "violations": [
                        {
                            "constraint": "DB access from CLI",
                            "file_path": "src/cli/db_tool.py",
                            "severity": "high",
                            "description": "CLI tool directly opens DB connection",
                            "fix_suggestion": "Move DB logic to repository layer",
                        }
                    ],
                    "architecture_score": 72,
                    "recommendations": ["Extract DB access into a repository module"],
                }),
                model="claude-test",
                usage={"input_tokens": 500, "output_tokens": 150},
            )

        m.chat = mock_chat
        m.format_messages.return_value = [
            ChatMessage(role="system", content="You are..."),
            ChatMessage(role="user", content="Review this diff..."),
        ]
        return m

    @pytest.fixture
    def mock_rag(self):
        """Create a mock RAG engine that returns empty context."""
        m = mock.AsyncMock()
        from codereviewmate.core.models.document import ContextBundle
        m.query_context.return_value = ContextBundle()
        return m

    @pytest.mark.asyncio
    async def test_review_diff_with_mock_llm(self, mock_llm, mock_rag):
        engine = DeepReviewEngine(llm=mock_llm)
        engine._rag = mock_rag

        diff = (
            "diff --git a/src/cli/db_tool.py b/src/cli/db_tool.py\n"
            "+import sqlite3\n"
            "+conn = sqlite3.connect('app.db')\n"
            "+conn.execute('SELECT * FROM users')\n"
        )

        result = await engine.review_diff(diff_text=diff)
        assert isinstance(result.passed, bool)
        assert len(result.issues) == 1
        assert result.issues[0].severity == Severity.HIGH
        assert result.architecture_compliance is not None
        assert result.architecture_compliance["score"] == 72
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_review_diff_empty(self, mock_llm, mock_rag):
        engine = DeepReviewEngine(llm=mock_llm)
        engine._rag = mock_rag

        result = await engine.review_diff(diff_text="")
        assert result.passed is True
        assert len(result.issues) == 0
        assert result.duration_ms == 0.0

    @pytest.mark.asyncio
    async def test_review_diff_handles_llm_error(self, mock_llm, mock_rag):
        # Replace chat with a mock that raises
        mock_llm.chat = mock.AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        engine = DeepReviewEngine(llm=mock_llm)
        engine._rag = mock_rag

        result = await engine.review_diff(diff_text="+x = 1\n")
        # Should gracefully degrade — pass with no issues
        assert result.passed is True
        assert "LLM error" in result.summary
