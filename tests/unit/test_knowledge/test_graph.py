"""Tests for knowledge graph manager."""

from __future__ import annotations

import tempfile
from pathlib import Path

from codereviewmate.core.knowledge.graph import KnowledgeGraphManager
from codereviewmate.core.models.knowledge import EdgeType, KnowledgeEdge, KnowledgeNode, NodeType


class TestKnowledgeGraphManager:
    def test_add_node(self):
        g = KnowledgeGraphManager()
        node = g.add_node(
            label="Use is None instead of == None",
            node_type=NodeType.STANDARD,
            description="None is a singleton — use identity check",
            tags=["python", "style"],
        )
        assert node.label == "Use is None instead of == None"
        assert node.type == NodeType.STANDARD
        assert g.node_count == 1

    def test_add_duplicate_node_returns_existing(self):
        g = KnowledgeGraphManager()
        n1 = g.add_node("Test Node", NodeType.CONCEPT)
        n2 = g.add_node("test node", NodeType.CONCEPT)  # case-insensitive
        assert n1.id == n2.id
        assert g.node_count == 1

    def test_add_edge(self):
        g = KnowledgeGraphManager()
        n1 = g.add_node("Node A", NodeType.PATTERN)
        n2 = g.add_node("Node B", NodeType.PATTERN)
        edge = g.add_edge(n1.id, n2.id, EdgeType.RELATES_TO, "related")
        assert edge is not None
        assert edge.source_id == n1.id
        assert g.edge_count == 1

    def test_add_edge_missing_node(self):
        g = KnowledgeGraphManager()
        edge = g.add_edge("missing1", "missing2", EdgeType.RELATES_TO)
        assert edge is None

    def test_add_edge_no_duplicate(self):
        g = KnowledgeGraphManager()
        n1 = g.add_node("A", NodeType.CONCEPT)
        n2 = g.add_node("B", NodeType.CONCEPT)
        e1 = g.add_edge(n1.id, n2.id, EdgeType.RELATES_TO, "first")
        e2 = g.add_edge(n1.id, n2.id, EdgeType.RELATES_TO, "second")
        assert e1 == e2
        assert g.edge_count == 1

    def test_get_node(self):
        g = KnowledgeGraphManager()
        node = g.add_node("Test", NodeType.CONCEPT)
        found = g.get_node(node.id)
        assert found is not None
        assert found.label == "Test"
        assert g.get_node("nonexistent") is None

    def test_remove_node(self):
        g = KnowledgeGraphManager()
        n1 = g.add_node("A", NodeType.CONCEPT)
        n2 = g.add_node("B", NodeType.CONCEPT)
        g.add_edge(n1.id, n2.id, EdgeType.RELATES_TO)

        g.remove_node(n1.id)
        assert g.node_count == 1
        assert g.edge_count == 0  # edges to removed node are cleaned up

    def test_find_by_type(self):
        g = KnowledgeGraphManager()
        g.add_node("S1", NodeType.STANDARD)
        g.add_node("S2", NodeType.STANDARD)
        g.add_node("AP1", NodeType.ANTI_PATTERN)

        standards = g.find_by_type(NodeType.STANDARD)
        assert len(standards) == 2

        anti = g.find_by_type(NodeType.ANTI_PATTERN)
        assert len(anti) == 1

    def test_find_by_tag(self):
        g = KnowledgeGraphManager()
        g.add_node("Node1", NodeType.CONCEPT, tags=["python", "security"])
        g.add_node("Node2", NodeType.CONCEPT, tags=["javascript", "react"])
        g.add_node("Node3", NodeType.CONCEPT, tags=["python", "logging"])

        py_nodes = g.find_by_tag("python")
        assert len(py_nodes) == 2

    def test_search(self):
        g = KnowledgeGraphManager()
        g.add_node("Use parameterized SQL queries", NodeType.STANDARD, "Always parameterize", tags=["security", "sql"])
        g.add_node("Avoid console.log", NodeType.STANDARD, "Use proper logging", tags=["javascript"])
        g.add_node("SQL injection prevention", NodeType.ANTI_PATTERN, "Never build SQL with strings", tags=["security"])

        results = g.search("sql")
        assert len(results) >= 2
        # "SQL" in label should rank higher
        assert "sql" in results[0].label.lower()

    def test_get_related(self):
        g = KnowledgeGraphManager()
        center = g.add_node("Center", NodeType.CONCEPT)
        a = g.add_node("A", NodeType.CONCEPT)
        b = g.add_node("B", NodeType.CONCEPT)
        c = g.add_node("C", NodeType.CONCEPT)

        g.add_edge(center.id, a.id, EdgeType.RELATES_TO)
        g.add_edge(center.id, b.id, EdgeType.RELATES_TO)
        g.add_edge(a.id, c.id, EdgeType.RELATES_TO)  # depth 2

        related = g.get_related(center.id, depth=1)
        assert len(related) == 2

        related_deep = g.get_related(center.id, depth=2)
        assert len(related_deep) == 3

    def test_get_neighbors(self):
        g = KnowledgeGraphManager()
        n1 = g.add_node("N1", NodeType.CONCEPT)
        n2 = g.add_node("N2", NodeType.CONCEPT)
        g.add_edge(n1.id, n2.id, EdgeType.RELATES_TO, "link")

        neighbors = g.get_neighbors(n1.id)
        assert len(neighbors) == 1
        assert neighbors[0][0].id == n2.id
        assert neighbors[0][1].type == EdgeType.RELATES_TO

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "graph.json")
            g1 = KnowledgeGraphManager(storage_path=path)
            g1.add_node("Persist Test", NodeType.CONCEPT, "test desc")
            g1.save()

            g2 = KnowledgeGraphManager(storage_path=path)
            g2.load()
            assert g2.node_count == 1
            assert g2.nodes[0].label == "Persist Test"

    def test_merge(self):
        g = KnowledgeGraphManager()
        g.add_node("Existing", NodeType.CONCEPT, "old desc", tags=["tag1"])

        new_node = KnowledgeNode(
            id="existing",
            label="Existing",
            type=NodeType.CONCEPT,
            description="new desc",
            tags=["tag2"],
        )
        new_edge = KnowledgeEdge(
            source_id="existing",
            target_id="existing",
            type=EdgeType.RELATES_TO,
        )

        added = g.merge([new_node], [new_edge])
        assert added == 0  # merged, not added
        assert g.nodes[0].description == "new desc"
        assert "tag2" in g.nodes[0].tags

    def test_subgraph_filter(self):
        g = KnowledgeGraphManager()
        s = g.add_node("Standard1", NodeType.STANDARD, tags=["py"])
        ap = g.add_node("Anti1", NodeType.ANTI_PATTERN, tags=["py"])

        sub = g.get_subgraph(node_types=[NodeType.STANDARD])
        assert len(sub.nodes) == 1
        assert sub.nodes[0].type == NodeType.STANDARD

    def test_make_id(self):
        assert KnowledgeGraphManager._make_id("Use is None") == "use_is_none"
        assert KnowledgeGraphManager._make_id("  Spaces  ") == "spaces"
        assert KnowledgeGraphManager._make_id("!!!") == "node"
