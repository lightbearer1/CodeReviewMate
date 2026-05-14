"""Knowledge graph manager using NetworkX."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import networkx as nx

from codereviewmate.core.models.knowledge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)

logger = logging.getLogger(__name__)


class KnowledgeGraphManager:
    """Manages the team knowledge graph with persistence and query capabilities."""

    def __init__(self, storage_path: Optional[str] = None):
        self._graph = nx.MultiDiGraph()
        self._model = KnowledgeGraph()
        self._storage_path = storage_path

    @property
    def nodes(self) -> list[KnowledgeNode]:
        return self._model.nodes

    @property
    def edges(self) -> list[KnowledgeEdge]:
        return self._model.edges

    @property
    def node_count(self) -> int:
        return len(self._model.nodes)

    @property
    def edge_count(self) -> int:
        return len(self._model.edges)

    # ---- Node operations ----

    def add_node(
        self,
        label: str,
        node_type: NodeType | str,
        description: str = "",
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
        source_review_ids: Optional[list[str]] = None,
        source_doc_ids: Optional[list[str]] = None,
    ) -> KnowledgeNode:
        """Add a new node or return an existing one with the same label."""
        node_type = NodeType(node_type) if isinstance(node_type, str) else node_type
        existing = self.find_by_label(label)
        if existing:
            return existing

        node_id = self._make_id(label)
        node = KnowledgeNode(
            id=node_id,
            label=label,
            type=node_type,
            description=description,
            tags=tags or [],
            metadata=metadata or {},
            source_review_ids=source_review_ids or [],
            source_doc_ids=source_doc_ids or [],
        )
        self._model.nodes.append(node)
        self._graph.add_node(node_id, **node.model_dump())
        logger.debug("Added node: %s (%s)", label, node_type.value)
        return node

    def update_node(self, node_id: str, **kwargs) -> Optional[KnowledgeNode]:
        """Update an existing node's fields."""
        node = self.get_node(node_id)
        if not node:
            return None

        for key, value in kwargs.items():
            if hasattr(node, key):
                setattr(node, key, value)

        node.updated_at = datetime.now(timezone.utc)
        self._graph.nodes[node_id].update(node.model_dump())
        return node

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its connected edges."""
        node = self.get_node(node_id)
        if not node:
            return False

        self._model.nodes = [n for n in self._model.nodes if n.id != node_id]
        self._model.edges = [
            e for e in self._model.edges
            if e.source_id != node_id and e.target_id != node_id
        ]
        self._graph.remove_node(node_id)
        return True

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        for n in self._model.nodes:
            if n.id == node_id:
                return n
        return None

    def find_by_label(self, label: str) -> Optional[KnowledgeNode]:
        for n in self._model.nodes:
            if n.label.lower() == label.lower():
                return n
        return None

    def find_by_type(self, node_type: NodeType | str, limit: int = 50) -> list[KnowledgeNode]:
        node_type = NodeType(node_type) if isinstance(node_type, str) else node_type
        return [n for n in self._model.nodes if n.type == node_type][:limit]

    def find_by_tag(self, tag: str, limit: int = 50) -> list[KnowledgeNode]:
        return [n for n in self._model.nodes if tag in n.tags][:limit]

    def search(self, query: str, limit: int = 20) -> list[KnowledgeNode]:
        """Simple keyword search across node labels and descriptions."""
        q = query.lower()
        terms = set(q.split())
        results: list[KnowledgeNode] = []
        for n in self._model.nodes:
            score = 0
            label_lower = n.label.lower()
            desc_lower = n.description.lower()
            for term in terms:
                if term in label_lower:
                    score += 3
                if term in desc_lower:
                    score += 1
                if any(term in tag.lower() for tag in n.tags):
                    score += 2
            # Also check full-phrase match
            if q in label_lower:
                score += 5
            if score > 0:
                results.append((score, n))
        results.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in results[:limit]]

    # ---- Edge operations ----

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType | str,
        description: str = "",
        weight: float = 1.0,
    ) -> Optional[KnowledgeEdge]:
        """Add an edge between two existing nodes."""
        edge_type = EdgeType(edge_type) if isinstance(edge_type, str) else edge_type

        if not self.get_node(source_id) or not self.get_node(target_id):
            logger.debug("Edge skipped — missing node: %s → %s", source_id, target_id)
            return None

        # Avoid exact duplicate edges
        for e in self._model.edges:
            if e.source_id == source_id and e.target_id == target_id and e.type == edge_type:
                return e

        edge = KnowledgeEdge(
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
            description=description,
            weight=weight,
        )
        self._model.edges.append(edge)
        self._graph.add_edge(source_id, target_id, key=edge_type.value, **edge.model_dump())
        return edge

    def remove_edge(self, source_id: str, target_id: str) -> bool:
        before = len(self._model.edges)
        self._model.edges = [
            e for e in self._model.edges
            if not (e.source_id == source_id and e.target_id == target_id)
        ]
        if self._graph.has_edge(source_id, target_id):
            self._graph.remove_edge(source_id, target_id)
        return len(self._model.edges) < before

    # ---- Graph traversal ----

    def get_related(self, node_id: str, depth: int = 2) -> list[KnowledgeNode]:
        """Find nodes related to the given node up to depth."""
        return self._model.find_related(node_id, depth)

    def get_neighbors(self, node_id: str) -> list[tuple[KnowledgeNode, KnowledgeEdge]]:
        """Get immediate neighbors with connecting edges."""
        results: list[tuple[KnowledgeNode, KnowledgeEdge]] = []
        for edge in self._model.edges:
            if edge.source_id == node_id:
                target = self.get_node(edge.target_id)
                if target:
                    results.append((target, edge))
            elif edge.target_id == node_id:
                source = self.get_node(edge.source_id)
                if source:
                    results.append((source, edge))
        return results

    def get_subgraph(
        self, node_types: Optional[list[NodeType]] = None, tags: Optional[list[str]] = None
    ) -> KnowledgeGraph:
        """Extract a subgraph filtered by node type and/or tags."""
        filtered_nodes = self._model.nodes
        if node_types:
            filtered_nodes = [n for n in filtered_nodes if n.type in node_types]
        if tags:
            filtered_nodes = [n for n in filtered_nodes if any(t in n.tags for t in tags)]

        node_ids = {n.id for n in filtered_nodes}
        filtered_edges = [
            e for e in self._model.edges
            if e.source_id in node_ids and e.target_id in node_ids
        ]

        subgraph = KnowledgeGraph(nodes=filtered_nodes, edges=filtered_edges)
        subgraph.version = self._model.version
        return subgraph

    # ---- Persistence ----

    def save(self, path: Optional[str] = None) -> None:
        """Save the knowledge graph to JSON."""
        target = Path(path or self._storage_path or ".codereviewmate/knowledge_graph.json")
        target.parent.mkdir(parents=True, exist_ok=True)

        self._model.version += 1
        data = self._model.model_dump(mode="json")
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Knowledge graph saved: %d nodes, %d edges → %s", len(self._model.nodes), len(self._model.edges), target)

    def load(self, path: Optional[str] = None) -> KnowledgeGraph:
        """Load the knowledge graph from JSON."""
        target = Path(path or self._storage_path or ".codereviewmate/knowledge_graph.json")
        if not target.exists():
            logger.info("No existing knowledge graph at %s, starting fresh", target)
            return self._model

        data = json.loads(target.read_text(encoding="utf-8"))
        self._model = KnowledgeGraph(**data)
        self._rebuild_networkx()
        logger.info("Knowledge graph loaded: %d nodes, %d edges", len(self._model.nodes), len(self._model.edges))
        return self._model

    def save_graphml(self, path: str) -> None:
        """Export graph to GraphML format."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        nx.write_graphml(self._graph, str(target))
        logger.info("GraphML exported to %s", target)

    def _rebuild_networkx(self) -> None:
        """Rebuild NetworkX graph from model data."""
        self._graph = nx.MultiDiGraph()
        for node in self._model.nodes:
            self._graph.add_node(node.id, **node.model_dump())
        for edge in self._model.edges:
            self._graph.add_edge(edge.source_id, edge.target_id, key=edge.type.value, **edge.model_dump())

    # ---- Bulk operations ----

    def merge(self, nodes: list[KnowledgeNode], edges: list[KnowledgeEdge]) -> int:
        """Merge extracted knowledge into the graph. Returns count of new nodes."""
        added = 0
        for node in nodes:
            existing = self.find_by_label(node.label)
            if existing:
                existing.tags = list(set(existing.tags + node.tags))
                existing.description = node.description or existing.description
                existing.updated_at = datetime.now(timezone.utc)
            else:
                self._model.nodes.append(node)
                self._graph.add_node(node.id, **node.model_dump())
                added += 1

        for edge in edges:
            self.add_edge(edge.source_id, edge.target_id, edge.type, edge.description, edge.weight)

        if added:
            self._model.version += 1
        return added

    @staticmethod
    def _make_id(label: str) -> str:
        """Generate a node ID from a label."""
        import re
        node_id = label.lower().strip()
        node_id = re.sub(r'[^\w]+', '_', node_id)
        return node_id.strip('_') or 'node'
