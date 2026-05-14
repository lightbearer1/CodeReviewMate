"""Knowledge graph CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codereviewmate.core.knowledge.engine import KnowledgeEngine
from codereviewmate.core.knowledge.visualization import generate_html
from codereviewmate.core.models.knowledge import NodeType

console = Console()
app = typer.Typer(name="knowledge", help="知识图谱管理", no_args_is_help=True)


@app.command("viz")
def knowledge_viz(
    output: str = typer.Option(
        "knowledge_graph.html", "--output", "-o", help="输出文件路径"
    ),
) -> None:
    """生成知识图谱可视化 HTML."""
    console.print("[bold]生成知识图谱可视化[/]")

    engine = KnowledgeEngine()
    engine.load()

    if engine.graph.node_count == 0:
        console.print("[yellow]知识图谱为空，请先摄入文档或运行审查[/]")
        return

    path = generate_html(engine.graph, output_path=output)
    console.print(f"[green]可视化已生成: {path}[/]")
    console.print(f"节点: {engine.graph.node_count} | 边: {engine.graph.edge_count}")


@app.command("add")
def knowledge_add(
    label: str = typer.Argument(..., help="节点标签"),
    node_type: str = typer.Option(
        "concept", "--type", "-t", help="节点类型"
    ),
    description: str = typer.Option("", "--desc", "-d", help="节点描述"),
    tags: str = typer.Option("", "--tags", help="逗号分隔的标签"),
) -> None:
    """手动添加知识图谱节点."""
    try:
        nt = NodeType(node_type)
    except ValueError:
        valid_types = ", ".join(t.value for t in NodeType)
        console.print(f"[red]无效的节点类型: {node_type}。可选: {valid_types}[/]")
        raise typer.Exit(1)

    engine = KnowledgeEngine()
    engine.load()

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    node = engine.graph.add_node(
        label=label,
        node_type=nt,
        description=description,
        tags=tag_list,
    )

    engine.save()
    console.print(f"[green]节点已添加: {node.label} ({node.type.value})[/]")


@app.command("query")
def knowledge_query(
    query: str = typer.Argument(..., help="查询关键词"),
    limit: int = typer.Option(20, "--limit", "-n", help="返回结果数量"),
) -> None:
    """查询知识图谱."""
    engine = KnowledgeEngine()
    engine.load()

    results = engine.query(query, limit=limit)

    if not results:
        console.print(f"[dim]未找到与 '{query}' 相关的知识节点[/]")
        return

    table = Table(title=f"知识查询结果 — {query}")
    table.add_column("类型", style="bold")
    table.add_column("标签")
    table.add_column("描述")
    table.add_column("Tags")

    for node in results:
        type_color = {
            NodeType.ANTI_PATTERN: "red",
            NodeType.STANDARD: "blue",
            NodeType.PATTERN: "green",
            NodeType.EXAMPLE: "purple",
        }.get(node.type, "dim")

        table.add_row(
            f"[{type_color}]{node.type.value}[/]",
            node.label,
            node.description[:100],
            ", ".join(node.tags[:5]),
        )

    console.print(table)
    console.print(f"[dim]共 {len(results)} 条结果[/]")


@app.command("stats")
def knowledge_stats() -> None:
    """查看知识图谱统计信息."""
    engine = KnowledgeEngine()
    engine.load()

    stats = engine.get_stats()

    console.print(Panel.fit("[bold]知识图谱统计[/]", border_style="blue"))
    console.print(f"节点总数: {stats['total_nodes']}")
    console.print(f"边总数: {stats['total_edges']}")

    if stats["by_type"]:
        console.print("\n[bold]按类型分布:[/]")
        for node_type, count in sorted(stats["by_type"].items()):
            console.print(f"  {node_type}: {count}")

    if stats["top_tags"]:
        console.print("\n[bold]Top Tags:[/]")
        for tag, count in stats["top_tags"]:
            console.print(f"  [dim]#{tag}[/]: {count}")


@app.command("export")
def knowledge_export(
    output: str = typer.Option(
        "knowledge_graph.graphml", "--output", "-o", help="输出路径"
    ),
    format: str = typer.Option("graphml", "--format", "-f", help="导出格式: graphml, json"),
) -> None:
    """导出知识图谱."""
    engine = KnowledgeEngine()
    engine.load()

    if format == "graphml":
        engine.graph.save_graphml(output)
        console.print(f"[green]GraphML 已导出: {output}[/]")
    else:
        engine.graph.save(output)
        console.print(f"[green]JSON 已导出: {output}[/]")
