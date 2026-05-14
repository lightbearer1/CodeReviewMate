"""Code review CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codereviewmate.core.models.review import Severity
from codereviewmate.core.review.pre_commit import PreCommitEngine

console = Console()
app = typer.Typer(name="review", help="代码审查", no_args_is_help=True)


SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "cyan",
    Severity.INFO: "dim",
}


@app.command("pre-commit")
def review_pre_commit(
    repo_path: str = typer.Option(
        ".", "--repo", "-r", help="仓库路径"
    ),
    staged_only: bool = typer.Option(
        True, "--staged/--all", help="仅审查暂存区文件"
    ),
    no_patch: bool = typer.Option(
        False, "--no-patch", help="不自动应用修复补丁"
    ),
) -> None:
    """执行快速预提交审查."""
    console.print(f"[bold]预提交审查[/] — 仓库: {repo_path}")
    console.print()

    engine = PreCommitEngine()
    result = engine.check_diff(repo_path=repo_path, staged_only=staged_only)

    if result.checks_run == 0:
        console.print("[dim]没有需要检查的文件[/]")
        return

    # Summary
    total = len(result.issues)
    critical_count = sum(1 for i in result.issues if i.severity == Severity.CRITICAL)
    high_count = sum(1 for i in result.issues if i.severity == Severity.HIGH)

    status_color = "red" if not result.passed else "green"
    status_text = "未通过" if not result.passed else "通过"

    console.print(
        f"审查结果: [{status_color}]{status_text}[/] "
        f"({result.checks_run} 个文件, {result.duration_ms:.0f}ms)"
    )
    console.print(f"发现问题: {total} 个 (严重: {critical_count}, 高: {high_count})")

    if result.patches:
        console.print(f"自动修复: {len(result.patches)} 个补丁可用")

    # Issues table
    if result.issues:
        console.print()
        table = Table(title="发现问题详情")
        table.add_column("严重度", style="bold")
        table.add_column("类别")
        table.add_column("文件")
        table.add_column("行")
        table.add_column("描述")

        for issue in result.issues:
            style = SEVERITY_COLORS.get(issue.severity, "")
            line_str = (
                f"{issue.line_start}" if issue.line_start else "-"
            )
            table.add_row(
                f"[{style}]{issue.severity.value}[/]",
                issue.category.value,
                issue.file_path,
                line_str,
                issue.title,
            )

        console.print(table)

    # Patches
    if result.patches and not no_patch:
        console.print()
        for patch in result.patches[:5]:
            console.print(f"[dim]补丁: {patch.file_path}[/]")

    if not result.passed:
        raise typer.Exit(1)


@app.command("check")
def review_check(
    path: str = typer.Argument(..., help="要检查的文件路径"),
) -> None:
    """检查单个文件."""
    engine = PreCommitEngine()
    issues = engine.check_file(path)

    if not issues:
        console.print(f"[green]文件通过检查: {path}[/]")
        return

    table = Table(title=f"文件检查 — {path}")
    table.add_column("严重度")
    table.add_column("行")
    table.add_column("问题")
    table.add_column("建议")

    for issue in issues:
        style = SEVERITY_COLORS.get(issue.severity, "")
        table.add_row(
            f"[{style}]{issue.severity.value}[/]",
            str(issue.line_start or "-"),
            issue.title,
            issue.suggestion or "-",
        )

    console.print(table)
    raise typer.Exit(1)


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
