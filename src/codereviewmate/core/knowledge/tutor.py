"""Intelligent tutoring engine — answers team member questions using accumulated knowledge."""

from __future__ import annotations

import logging
from typing import Optional

from jinja2 import Environment, PackageLoader

from codereviewmate.core.config.manager import get_config
from codereviewmate.core.context.engine import get_rag_engine
from codereviewmate.core.knowledge.graph import KnowledgeGraphManager
from codereviewmate.core.knowledge.standards import StandardsQuery
from codereviewmate.core.llm.base import LLMProvider
from codereviewmate.core.llm.factory import create_llm_provider
from codereviewmate.core.models.knowledge import (
    KnowledgeNode,
    NodeType,
    TutorResponse,
)

logger = logging.getLogger(__name__)


class TutorEngine:
    """Answers new team member questions using RAG + knowledge graph + LLM.

    Integrates three knowledge sources:
    1. Vectorized architecture docs (RAG)
    2. Knowledge graph nodes (standards, patterns, anti-patterns)
    3. LLM synthesis to produce practical, example-driven answers
    """

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        graph: Optional[KnowledgeGraphManager] = None,
    ):
        self._config = get_config()
        self._llm = llm
        self._graph = graph or KnowledgeGraphManager(
            storage_path=self._config.knowledge.graph_storage_path
        )
        self._rag = get_rag_engine()
        self._standards = StandardsQuery(self._graph)

        try:
            self._jinja = Environment(
                loader=PackageLoader("codereviewmate.core.llm", "prompts"),
            )
        except Exception:
            self._jinja = None

    async def ask(
        self,
        question: str,
        context: str = "",
        use_llm: bool = True,
    ) -> TutorResponse:
        """Answer a tutoring question."""
        # 1. Search knowledge graph
        graph_nodes = self._graph.search(question, limit=5)

        # 2. RAG retrieval for architecture docs
        rag_query = f"{question} {context}"
        ctx_bundle = await self._rag.query_context(rag_query, top_k=3)

        # 3. Get relevant standards
        standards = self._standards.search(question, limit=5)
        anti_patterns = self._graph.find_by_type(NodeType.ANTI_PATTERN, limit=10)

        # Filter anti-patterns relevant to the question
        question_terms = set(question.lower().split())
        relevant_anti_patterns = [
            ap for ap in anti_patterns
            if any(tag in question_terms for tag in ap.tags)
            or any(term in ap.description.lower() for term in question_terms)
        ][:3]

        sources: list[dict] = []

        # Assemble sources
        for doc in ctx_bundle.relevant_docs:
            sources.append({
                "title": doc.get("title", "Document"),
                "type": "architecture_doc",
                "snippet": (doc.get("content", "") or "")[:200],
            })

        for node in graph_nodes:
            sources.append({
                "title": node.label,
                "type": f"knowledge_{node.type.value}",
                "snippet": node.description[:200],
            })

        # 4. LLM synthesis (or graph-only if no LLM)
        if use_llm and self._llm:
            answer = await self._synthesize_with_llm(
                question, context, graph_nodes, standards, relevant_anti_patterns, ctx_bundle
            )
        else:
            answer = self._synthesize_from_graph(
                question, graph_nodes, standards, relevant_anti_patterns
            )

        return TutorResponse(
            question=question,
            answer=answer,
            sources=sources,
            related_nodes=graph_nodes,
            suggested_readings=self._suggest_readings(graph_nodes, question),
        )

    async def _synthesize_with_llm(
        self,
        question: str,
        context: str,
        graph_nodes: list[KnowledgeNode],
        standards: list[KnowledgeNode],
        anti_patterns: list[KnowledgeNode],
        ctx_bundle,
    ) -> str:
        """Use LLM to synthesize a comprehensive answer."""
        if not self._jinja:
            return self._synthesize_from_graph(question, graph_nodes, standards, anti_patterns)

        template = self._jinja.get_template("tutor.j2")
        prompt = template.render(
            team_name=self._config.team_name,
            question=question + (f"\nContext: {context}" if context else ""),
            architecture_docs=[
                {"summary": d.get("content", "")[:500]}
                for d in (ctx_bundle.relevant_docs + ctx_bundle.relevant_standards)
            ],
            knowledge_nodes=[
                {"label": n.label, "type": n.type.value, "description": n.description}
                for n in graph_nodes
            ],
            standards=[n.description for n in standards],
            examples=[
                {"context": n.label, "lesson": n.description}
                for n in graph_nodes if n.type == NodeType.EXAMPLE
            ],
        )

        messages = self._llm.format_messages(
            system_prompt="You are a helpful coding mentor. Answer based on the team's documented patterns.",
            user_message=prompt,
        )

        try:
            response = await self._llm.chat(messages, temperature=0.3, max_tokens=2048)
            return response.content.strip()
        except Exception as e:
            logger.warning("LLM tutor failed: %s, falling back to graph", e)
            return self._synthesize_from_graph(question, graph_nodes, standards, anti_patterns)

    def _synthesize_from_graph(
        self,
        question: str,
        graph_nodes: list[KnowledgeNode],
        standards: list[KnowledgeNode],
        anti_patterns: list[KnowledgeNode],
    ) -> str:
        """Build an answer from graph nodes alone (no LLM)."""
        parts: list[str] = []

        if standards:
            parts.append("## 团队标准")
            for s in standards[:3]:
                parts.append(f"- **{s.label}**: {s.description}")

        if graph_nodes:
            parts.append("## 相关知识")
            for n in graph_nodes[:5]:
                parts.append(f"- **{n.label}** ({n.type.value}): {n.description}")

        if anti_patterns:
            parts.append("## 需要避免的反模式")
            for ap in anti_patterns[:3]:
                parts.append(f"- **{ap.label}**: {ap.description}")

        if not parts:
            return f"关于「{question}」，目前在团队知识库中尚未找到直接相关的模式或标准。建议查阅架构文档或与团队讨论。\n\n可以从 `codereviewmate ingest directory docs/ --type architecture` 开始摄入团队文档。"

        return "\n\n".join(parts)

    @staticmethod
    def _suggest_readings(nodes: list[KnowledgeNode], question: str) -> list[str]:
        """Suggest further reading topics."""
        suggestions: list[str] = []
        seen: set[str] = set()

        for node in nodes:
            for tag in node.tags:
                if tag not in seen and tag not in question.lower():
                    suggestions.append(f"Explore patterns related to '{tag}'")
                    seen.add(tag)

        if not suggestions:
            suggestions.append("Review the team architecture documents")
            suggestions.append("Check recent PR reviews for similar patterns")

        return suggestions[:5]
