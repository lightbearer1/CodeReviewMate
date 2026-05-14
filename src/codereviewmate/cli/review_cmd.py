"""Code review CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codereviewmate.core.models.review import Severity
from codereviewmate.core.review.deep_review import DeepReviewEngine
from codereviewmate.core.review.pre_commit import PreCommitEngine
from codereviewmate.core.review.report import ReportGenerator
from codereviewmate.integrations.git.factory import GitPlatformType, detect_platform

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
        None, "--pr", help="PR ID (GitHub/GitLab/Gitee)"
    ),
    base_ref: str = typer.Option(
        "HEAD~1", "--base", help="基准引用 (默认 HEAD~1)"
    ),
    target_ref: str = typer.Option(
        "HEAD", "--target", help="目标引用 (默认 HEAD)"
    ),
    platform: str = typer.Option(
        "auto", "--platform", "-p", help="Git 平台: auto/local/github/gitlab/gitee"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="输出报告路径"
    ),
) -> None:
    """执行深度架构合规审查 (LLM 驱动)."""
    console.print(f"[bold]深度审查[/] — 仓库: {repo_path}")

    async def _run():
        engine = DeepReviewEngine()

        if pr_id:
            pt = GitPlatformType(platform) if platform != "auto" else detect_platform(repo_path)
            console.print(f"审查 PR [cyan]#{pr_id}[/] (平台: {pt.value})")
            result = await engine.review_pr(pr_id=pr_id, platform_type=pt, repo_path=repo_path)
        else:
            console.print(f"审查本地变更: [dim]{base_ref}..{target_ref}[/]")
            result = await engine.review_local(
                repo_path=repo_path, base_ref=base_ref, target_ref=target_ref
            )

        _display_deep_result(result)

        if output and result.issues:
            report = ReportGenerator().generate(deep=result)
            _write_report(report, output)

        if not result.passed:
            raise typer.Exit(1)

    asyncio.run(_run())


@app.command("full")
def review_full(
    repo_path: str = typer.Option(
        ".", "--repo", "-r", help="仓库路径"
    ),
    pr_id: str = typer.Option(
        None, "--pr", help="PR ID (GitHub/GitLab/Gitee)"
    ),
    platform: str = typer.Option(
        "auto", "--platform", "-p", help="Git 平台: auto/local/github/gitlab/gitee"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="输出报告路径"
    ),
) -> None:
    """执行完整审查流程 (Pre-commit + Deep)."""
    console.print(f"[bold]完整审查[/] — 仓库: {repo_path}")
    console.print()

    async def _run():
        # Phase 1: Pre-commit fast check
        console.print("[bold]Phase 1: 预提交检查[/]")
        pre_engine = PreCommitEngine()
        pre_result = pre_engine.check_diff(repo_path=repo_path, staged_only=False)
        _display_pre_commit_summary(pre_result)
        console.print()

        # Phase 2: Deep review
        console.print("[bold]Phase 2: 深度架构审查[/]")
        deep_engine = DeepReviewEngine()

        if pr_id:
            pt = GitPlatformType(platform) if platform != "auto" else detect_platform(repo_path)
            console.print(f"审查 PR [cyan]#{pr_id}[/] (平台: {pt.value})")
            deep_result = await deep_engine.review_pr(pr_id=pr_id, platform_type=pt, repo_path=repo_path)
        else:
            deep_result = await deep_engine.review_local(repo_path=repo_path)
        _display_deep_result(deep_result)

        # Generate combined report
        generator = ReportGenerator()
        report = generator.generate(pre_commit=pre_result, deep=deep_result)

        console.print()
        status_text = "通过" if report.passed else "未通过"
        status_color = "green" if report.passed else "red"
        console.print(f"[bold {status_color}]最终结果: {status_text}[/]")
        console.print(f"总耗时: {report.total_duration_ms:.0f}ms | 总问题数: {len(report.all_issues)}")

        if output:
            _write_report(report, output)

        if not report.passed:
            raise typer.Exit(1)

    asyncio.run(_run())


def _display_pre_commit_summary(result) -> None:
    """Display a compact pre-commit result summary."""
    total = len(result.issues)
    critical = sum(1 for i in result.issues if i.severity == Severity.CRITICAL)
    high = sum(1 for i in result.issues if i.severity == Severity.HIGH)
    status = "green" if result.passed else "red"
    status_text = "通过" if result.passed else "未通过"

    console.print(
        f"  结果: [{status}]{status_text}[/] | "
        f"文件: {result.checks_run} | "
        f"问题: {total} (严重: {critical}, 高: {high}) | "
        f"耗时: {result.duration_ms:.0f}ms"
    )


def _display_deep_result(result) -> None:
    """Display deep review results."""
    if result.architecture_compliance:
        arch = result.architecture_compliance
        score = arch.get("score", "N/A")
        score_color = "green" if score and score >= 80 else "yellow" if score and score >= 60 else "red"
        console.print(f"  架构评分: [{score_color}]{score}/100[/]")
        console.print(f"  合规: {'是' if arch.get('compliant') else '否'}")

    if result.summary:
        console.print()
        console.print(Panel(result.summary.strip(), title="审查摘要", border_style="dim"))

    if result.issues:
        console.print()
        table = Table(title="架构违规详情")
        table.add_column("严重度", style="bold")
        table.add_column("文件")
        table.add_column("描述")
        table.add_column("建议")

        for issue in result.issues:
            style = SEVERITY_COLORS.get(issue.severity, "")
            table.add_row(
                f"[{style}]{issue.severity.value}[/]",
                issue.file_path,
                issue.description[:80],
                (issue.suggestion or "-")[:60],
            )

        console.print(table)

    if result.token_usage:
        console.print(f"[dim]Token 用量: {result.token_usage}[/]")


def _write_report(report, output_path: str) -> None:
    """Write the review report to a file."""
    path = Path(output_path)
    suffix = path.suffix.lower()

    if suffix == ".md":
        content = ReportGenerator.format_markdown(report)
    elif suffix == ".html":
        content = ReportGenerator.format_html(report)
    else:
        content = ReportGenerator.format_text(report)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    console.print(f"[green]报告已保存到: {output_path}[/]")
