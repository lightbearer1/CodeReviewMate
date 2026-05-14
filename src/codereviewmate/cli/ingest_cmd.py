"""Document ingestion CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codereviewmate.core.context.engine import get_rag_engine
from codereviewmate.core.models.document import DocumentType

console = Console()
app = typer.Typer(name="ingest", help="文档摄入管理", no_args_is_help=True)


@app.command("document")
def ingest_document(
    path: str = typer.Argument(..., help="文档文件路径"),
    doc_type: str = typer.Option(
        "architecture", "--type", "-t",
        help=f"文档类型: {', '.join(t.value for t in DocumentType)}",
    ),
    tags: str = typer.Option(
        "", "--tags",
        help="标签（逗号分隔）",
    ),
) -> None:
    """摄入单个文档文件."""
    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[red]文件不存在: {path}[/]")
        raise typer.Exit(1)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    async def _run():
        engine = get_rag_engine()
        doc_type_enum = DocumentType(doc_type)
        count = await engine._ingestor.ingest_file(file_path, doc_type_enum, tag_list)
        return count

    count = asyncio.run(_run())
    console.print(f"[green]摄入完成:[/] {file_path.name} → {count} 个块")


@app.command("directory")
def ingest_directory(
    path: str = typer.Argument(..., help="文档目录路径"),
    doc_type: str = typer.Option(
        "architecture", "--type", "-t",
        help=f"文档类型: {', '.join(t.value for t in DocumentType)}",
    ),
    glob_pattern: str = typer.Option(
        "*.md", "--glob", "-g", help="文件匹配模式"
    ),
) -> None:
    """摄入目录中所有匹配的文档."""
    dir_path = Path(path)
    if not dir_path.is_dir():
        console.print(f"[red]目录不存在: {path}[/]")
        raise typer.Exit(1)

    async def _run():
        engine = get_rag_engine()
        return await engine.ingest_directory(path, doc_type, glob_pattern)

    results = asyncio.run(_run())
    table = Table(title=f"摄入结果 — {path}")
    table.add_column("文件", style="cyan")
    table.add_column("块数", style="green")

    total = 0
    for fname, count in results.items():
        status = str(count) if count >= 0 else "[red]失败[/]"
        table.add_row(fname, status)
        if count > 0:
            total += count

    console.print(table)
    console.print(f"[bold green]总计: {total} 个块[/]")


@app.command("text")
def ingest_text(
    title: str = typer.Option(..., "--title", "-t", help="文档标题"),
    content: str = typer.Option(..., "--content", "-c", help="文档内容"),
    doc_type: str = typer.Option(
        "other", "--type", help="文档类型"
    ),
    source: str = typer.Option(
        "", "--source", "-s", help="来源标识"
    ),
) -> None:
    """摄入纯文本内容."""
    async def _run():
        engine = get_rag_engine()
        return await engine.ingest_text(title, content, doc_type, source)

    count = asyncio.run(_run())
    console.print(f"[green]摄入完成:[/] '{title}' → {count} 个块")


@app.command("stats")
def ingest_stats() -> None:
    """查看知识库统计信息."""
    engine = get_rag_engine()
    stats = engine.stats()

    console.print(f"[bold]知识库统计[/]")
    console.print(f"  总块数: {stats['total_chunks']}")
    console.print(f"  文档数: {len(stats['documents'])}")
    if stats["documents"]:
        console.print("  文档列表:")
        for doc_id in stats["documents"]:
            console.print(f"    - {doc_id}")


@app.command("reset")
def ingest_reset(
    confirm: bool = typer.Option(
        False, "--confirm", help="确认清空所有数据"
    ),
) -> None:
    """清空知识库所有数据."""
    if not confirm:
        console.print("[yellow]使用 --confirm 确认清空所有数据[/]")
        raise typer.Exit(1)

    engine = get_rag_engine()
    engine.reset()
    console.print("[green]知识库已清空[/]")


@app.command("search")
def ingest_search(
    query: str = typer.Argument(..., help="搜索查询"),
    top_k: int = typer.Option(5, "--top", "-k", help="返回结果数"),
) -> None:
    """搜索知识库."""
    async def _run():
        engine = get_rag_engine()
        return await engine.search(query, top_k)

    results = asyncio.run(_run())

    if not results:
        console.print("[yellow]未找到相关结果[/]")
        return

    table = Table(title=f"搜索结果 — {query}")
    table.add_column("#", style="dim")
    table.add_column("文档", style="cyan")
    table.add_column("内容预览", style="green")
    table.add_column("相关度", style="yellow")

    for i, sc in enumerate(results, 1):
        title = sc.chunk.metadata.get("title", "Unknown")
        preview = sc.chunk.content[:100].replace("\n", " ") + "..."
        table.add_row(str(i), title, preview, f"{sc.score:.3f}")

    console.print(table)
