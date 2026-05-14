"""Knowledge graph visualization using pyvis."""

from __future__ import annotations

import logging
from pathlib import Path

from codereviewmate.core.knowledge.graph import KnowledgeGraphManager
from codereviewmate.core.models.knowledge import EdgeType, NodeType

logger = logging.getLogger(__name__)

NODE_COLORS: dict[NodeType, str] = {
    NodeType.CONCEPT: "#667eea",         # Indigo
    NodeType.PATTERN: "#48bb78",         # Green
    NodeType.ANTI_PATTERN: "#fc8181",    # Red
    NodeType.STANDARD: "#4299e1",        # Blue
    NodeType.RULE: "#ed8936",            # Orange
    NodeType.EXAMPLE: "#9f7aea",         # Purple
    NodeType.BEST_PRACTICE: "#38b2ac",   # Teal
}

EDGE_COLORS: dict[EdgeType, str] = {
    EdgeType.RELATES_TO: "#a0aec0",      # Gray
    EdgeType.CONTRADICTS: "#fc8181",     # Red
    EdgeType.REFINES: "#48bb78",         # Green
    EdgeType.EXAMPLE_OF: "#9f7aea",      # Purple
    EdgeType.DEPENDS_ON: "#4299e1",      # Blue
    EdgeType.SUPERSEDES: "#ed8936",      # Orange
}


def generate_html(
    graph_manager: KnowledgeGraphManager,
    output_path: str = "knowledge_graph.html",
    title: str = "Team Knowledge Graph",
    height: str = "700px",
    width: str = "100%",
    physics_enabled: bool = True,
) -> str:
    """Generate an interactive HTML visualization of the knowledge graph.

    Returns the absolute path to the generated file.
    """
    try:
        from pyvis.network import Network
    except ImportError:
        raise ImportError("pyvis is required for visualization. Install with: pip install pyvis")

    net = Network(height=height, width=width, directed=True, notebook=False)
    net.set_options(f"""
    {{
        "nodes": {{
            "font": {{"size": 14, "face": "sans-serif"}},
            "borderWidth": 2
        }},
        "edges": {{
            "arrows": {{"to": {{"enabled": true, "scaleFactor": 0.5}}}},
            "smooth": {{"type": "curvedCW"}},
            "font": {{"size": 10}}
        }},
        "physics": {{
            "enabled": {str(physics_enabled).lower()},
            "barnesHut": {{"gravitationalConstant": -3000, "springLength": 200}},
            "stabilization": {{"iterations": 100}}
        }}
    }}
    """)

    # Add nodes
    for node in graph_manager.nodes:
        color = NODE_COLORS.get(node.type, "#cbd5e0")
        label = f"{node.label}\n[{node.type.value}]"
        title_text = f"<b>{node.label}</b><br>{node.type.value}<br><br>{node.description}"
        if node.tags:
            title_text += f"<br><br>Tags: {', '.join(node.tags)}"

        net.add_node(
            node.id,
            label=label,
            title=title_text,
            color=color,
            shape="box" if node.type == NodeType.STANDARD else "dot",
            size=25 if node.type == NodeType.ANTI_PATTERN else 20,
        )

    # Add edges
    for edge in graph_manager.edges:
        color = EDGE_COLORS.get(edge.type, "#a0aec0")
        net.add_edge(
            edge.source_id,
            edge.target_id,
            title=f"{edge.type.value}: {edge.description}",
            label=edge.type.value,
            color=color,
            width=max(0.5, edge.weight),
        )

    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(str(path))

    logger.info("Knowledge graph visualization saved to %s (%d nodes, %d edges)", path, graph_manager.node_count, graph_manager.edge_count)
    return str(path)
