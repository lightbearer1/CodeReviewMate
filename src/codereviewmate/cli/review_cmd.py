"""Code review CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()
app = typer.Typer(name="review", help="代码审查", no_args_is_help=True)


@app.command("pre-commit")
def review_pre_commit(
    repo_path: str = typer.Option(
        ".", "--repo", "-r", help="仓库路径"
    ),
    staged_only: bool = typer.Option(
        True, "--staged/--all", help="仅审查暂存区文件"
    ),
) -> None:
    """执行快速预提交审查."""
    console.print(f"[bold]预提交审查[/] — 仓库: {repo_path}")
    console.print("[yellow]此功能将在 Phase 2 中实现[/]")


@app.command("deep")
def review_deep(
    repo_path: str = typer.Option(
        ".", "--repo", "-r", help="仓库路径"
    ),
    pr_id: str = typer.Option(
        None, "--pr", help="PR ID (GitHub/GitLab)"
    ),
) -> None:
    """执行深度架构合规审查."""
    console.print(f"[bold]深度审查[/] — 仓库: {repo_path}")
    console.print("[yellow]此功能将在 Phase 3 中实现[/]")


@app.command("full")
def review_full(
    repo_path: str = typer.Option(
        ".", "--repo", "-r", help="仓库路径"
    ),
    pr_id: str = typer.Option(
        None, "--pr", help="PR ID (GitHub/GitLab)"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="输出报告路径"
    ),
) -> None:
    """执行完整审查流程."""
    console.print(f"[bold]完整审查[/] — 仓库: {repo_path}")
    console.print("[yellow]此功能将在 Phase 3 中实现[/]")
