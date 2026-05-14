"""Tutoring CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()
app = typer.Typer(name="tutor", help="智能辅导", no_args_is_help=True)


@app.command("ask")
def tutor_ask(
    question: str = typer.Argument(..., help="你的问题"),
    context: str = typer.Option(
        None, "--context", "-c", help="附加上下文（如：新人、前端、后端）"
    ),
) -> None:
    """向智能辅导引擎提问."""
    console.print(f"[bold]提问[/] — {question}")
    if context:
        console.print(f"[dim]上下文: {context}[/]")
    console.print("[yellow]此功能将在 Phase 4 中实现[/]")
