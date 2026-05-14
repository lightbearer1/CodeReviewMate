"""Knowledge engine — orchestrates extraction, storage, and querying."""

from __future__ import annotations

import logging
from typing import Optional

from codereviewmate.core.config.manager import get_config
from codereviewmate.core.knowledge.extractor import KnowledgeExtractor
from codereviewmate.core.knowledge.graph import KnowledgeGraphManager
from codereviewmate.core.llm.base import LLMProvider
from codereviewmate.core.models.knowledge import (
    KnowledgeExtraction,
    KnowledgeNode,
    NodeType,
)
from codereviewmate.core.models.review import Issue, ReviewReport

logger = logging.getLogger(__name__)


class KnowledgeEngine:
    """Main orchestrator for knowledge accumulation.

    Subscribes to review events and automatically extracts knowledge
    from completed reviews into the knowledge graph.
    """

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        storage_path: Optional[str] = None,
    ):
        self._config = get_config()
        self._graph = KnowledgeGraphManager(
            storage_path=storage_path or self._config.knowledge.graph_storage_path
        )
        self._extractor = KnowledgeExtractor(llm=llm)

    @property
    def graph(self) -> KnowledgeGraphManager:
        return self._graph

    def load(self) -> KnowledgeGraphManager:
        """Load the existing knowledge graph from disk."""
        self._graph.load()
        return self._graph

    def save(self) -> None:
        """Persist the knowledge graph to disk."""
        self._graph.save()

    async def process_review(self, report: ReviewReport) -> KnowledgeExtraction:
        """Extract knowledge from a completed review and merge into the graph."""
        if not self._config.knowledge.auto_extract_enabled:
            return KnowledgeExtraction(summary="Auto-extraction disabled")

        issues = report.all_issues
        if not issues:
            return KnowledgeExtraction(summary="No issues to extract knowledge from")

        # Phase 1: Rule-based extraction (always runs, fast)
        extraction = self._extractor.extract_from_issues(
            issues, existing_nodes=self._graph.nodes
        )

        # Phase 2: LLM-based extraction for novel patterns (if LLM available)
        if self._extractor._llm and self._should_use_llm(issues):
            try:
                llm_extraction = await self._extractor.extract_with_llm(
                    issues=issues,
                    team_name=self._config.team_name,
                    existing_nodes=self._graph.nodes,
                )
                # Merge LLM results with rule-based results
                extraction.new_nodes.extend(llm_extraction.new_nodes)
                extraction.new_edges.extend(llm_extraction.new_edges)
                if llm_extraction.summary:
                    extraction.summary += " | LLM: " + llm_extraction.summary
            except Exception as e:
                logger.warning("LLM extraction failed, using rule-based only: %s", e)

        # Merge into graph
        if extraction.new_nodes or extraction.new_edges:
            added = self._graph.merge(extraction.new_nodes, extraction.new_edges)
            extraction.updated_nodes = extraction.new_nodes[:added]
            if self._config.knowledge.auto_extract_enabled:
                self._graph.save()

        logger.info("Knowledge extracted: %d new nodes, %d new edges", len(extraction.new_nodes), len(extraction.new_edges))
        return extraction

    def query(self, query: str, limit: int = 20) -> list[KnowledgeNode]:
        """Search the knowledge graph."""
        return self._graph.search(query, limit)

    def get_stats(self) -> dict:
        """Get knowledge graph statistics."""
        by_type: dict[str, int] = {}
        for n in self._graph.nodes:
            by_type[n.type.value] = by_type.get(n.type.value, 0) + 1

        return {
            "total_nodes": self._graph.node_count,
            "total_edges": self._graph.edge_count,
            "by_type": by_type,
            "top_tags": self._top_tags(10),
        }

    def get_standards(self, limit: int = 50) -> list[KnowledgeNode]:
        """Get all coding standards and rules."""
        return self._graph.find_by_type(NodeType.STANDARD, limit=limit)

    def get_anti_patterns(self, limit: int = 50) -> list[KnowledgeNode]:
        """Get all known anti-patterns."""
        return self._graph.find_by_type(NodeType.ANTI_PATTERN, limit=limit)

    def _top_tags(self, n: int = 10) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for node in self._graph.nodes:
            for tag in node.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]

    @staticmethod
    def _should_use_llm(issues: list[Issue]) -> bool:
        """Decide whether to invoke LLM for extraction. Skip if all issues are known rule IDs."""
        unknown = sum(1 for i in issues if i.rule_id not in KnowledgeExtractor.RULE_KNOWLEDGE_MAP if i.rule_id)
        return unknown > 0 or len(issues) > 5
