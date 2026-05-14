"""Tutoring CLI commands."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from codereviewmate.core.knowledge.engine import KnowledgeEngine
from codereviewmate.core.knowledge.tutor import TutorEngine
from codereviewmate.core.llm.factory import create_llm_provider

console = Console()
app = typer.Typer(name="tutor", help="智能辅导", no_args_is_help=True)


@app.command("ask")
def tutor_ask(
    question: str = typer.Argument(..., help="你的问题"),
    context: str = typer.Option(
        None, "--context", "-c", help="附加上下文（如：新人、前端、后端）"
    ),
    no_llm: bool = typer.Option(
        False, "--no-llm", help="仅使用知识图谱，不调用 LLM"
    ),
) -> None:
    """向智能辅导引擎提问."""
    console.print(f"[bold]辅导提问[/]: {question}")
    if context:
        console.print(f"[dim]上下文: {context}[/]")

    async def _run():
        engine = KnowledgeEngine()
        engine.load()

        # Try to create LLM, but allow graceful fallback
        try:
            llm = None if no_llm else create_llm_provider()
        except Exception:
            llm = None
            if not no_llm:
                console.print("[yellow]LLM 不可用，使用知识图谱回答[/]")

        tutor = TutorEngine(llm=llm, graph=engine.graph)
        response = await tutor.ask(
            question=question,
            context=context or "",
            use_llm=not no_llm and llm is not None,
        )

        console.print()
        if response.answer:
            # Try to render as markdown
            try:
                console.print(Markdown(response.answer))
            except Exception:
                console.print(response.answer)

        if response.related_nodes:
            console.print()
            console.print("[bold]相关知识点:[/]")
            for node in response.related_nodes[:5]:
                console.print(f"  - [{node.type.value}] {node.label}")

        if response.suggested_readings:
            console.print()
            console.print("[bold dim]推荐进一步了解:[/]")
            for reading in response.suggested_readings[:3]:
                console.print(f"  [dim]- {reading}[/]")

        if response.sources:
            console.print()
            console.print(f"[dim]参考了 {len(response.sources)} 个知识来源[/]")

    asyncio.run(_run())
