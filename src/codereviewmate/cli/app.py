"""CLI application entry point for CodeReviewMate."""

from __future__ import annotations

import logging
import sys

import typer
from rich.console import Console
from rich.logging import RichHandler

from codereviewmate import __version__
from codereviewmate.cli import config_cmd, ingest_cmd, knowledge_cmd, review_cmd, tutor_cmd

console = Console()
app = typer.Typer(
    name="codereviewmate",
    help="智能代码审查与知识沉淀 Agent",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

app.add_typer(review_cmd.app, name="review", help="代码审查命令组")
app.add_typer(knowledge_cmd.app, name="knowledge", help="知识图谱命令组")
app.add_typer(config_cmd.app, name="config", help="配置管理命令组")
app.add_typer(tutor_cmd.app, name="tutor", help="智能辅导命令组")
app.add_typer(ingest_cmd.app, name="ingest", help="文档摄入命令组")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)


@app.callback()
def main_callback(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="启用详细日志输出"
    ),
    version: bool = typer.Option(
        False, "--version", "-V", help="显示版本号", is_eager=True,
    ),
) -> None:
    if version:
        console.print(f"[bold]CodeReviewMate[/bold] v{__version__}")
        raise typer.Exit()

    setup_logging(verbose)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="绑定地址"),
    port: int = typer.Option(8800, "--port", "-p", help="监听端口"),
    reload: bool = typer.Option(False, "--reload", help="开发模式自动重载"),
) -> None:
    """启动 API 服务器."""
    import uvicorn

    console.print(f"[bold green]CodeReviewMate[/] API 服务启动于 http://{host}:{port}")
    uvicorn.run(
        "codereviewmate.server.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
