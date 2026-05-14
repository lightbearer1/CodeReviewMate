"""Configuration management CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codereviewmate.core.config.manager import get_config_manager

console = Console()
app = typer.Typer(name="config", help="配置管理", no_args_is_help=True)


@app.command("show")
def show_config() -> None:
    """显示当前配置."""
    config = get_config_manager().config
    table = Table(title="当前配置")
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")

    table.add_row("LLM 提供者", config.llm.provider.value)
    table.add_row("LLM 模型", config.llm.model)
    table.add_row("嵌入提供者", config.embedding.provider.value)
    table.add_row("嵌入模型", config.embedding.model)
    table.add_row("预提交审查", str(config.review.pre_commit_enabled))
    table.add_row("深度审查", str(config.review.deep_review_enabled))
    table.add_row("自动修复", str(config.review.auto_fix_enabled))
    table.add_row("知识图谱路径", config.knowledge.graph_storage_path)

    console.print(table)


@app.command("init")
def init_config(
    force: bool = typer.Option(False, "--force", "-f", help="覆盖已有配置文件"),
) -> None:
    """在当前目录初始化默认配置文件."""
    target = Path.cwd() / ".codereviewmate.yaml"
    if target.exists() and not force:
        console.print(f"[yellow]配置文件已存在: {target}[/]")
        console.print("使用 --force 强制覆盖")
        raise typer.Exit(1)

    get_config_manager().save_team_config(target)
    console.print(f"[green]配置文件已创建: {target}[/]")


@app.command("validate")
def validate_config(
    path: str = typer.Argument(".codereviewmate.yaml", help="配置文件路径"),
) -> None:
    """验证配置文件格式."""
    config_path = Path(path)
    if not config_path.exists():
        console.print(f"[red]文件不存在: {path}[/]")
        raise typer.Exit(1)

    try:
        get_config_manager().load(team_config_path=config_path)
        console.print(f"[green]配置文件有效: {path}[/]")
    except Exception as e:
        console.print(f"[red]配置文件无效: {e}[/]")
        raise typer.Exit(1)
