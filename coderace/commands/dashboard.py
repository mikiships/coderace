"""Dashboard command — generate HTML dashboard from race results."""

from __future__ import annotations

import webbrowser
from pathlib import Path

import typer
from rich.console import Console

from coderace.dashboard import generate_dashboard
from coderace.store import ResultStore


def dashboard_command(
    output: Path = typer.Option(
        "dashboard.html", "--output", "-o", help="Output file path"
    ),
    task: str | None = typer.Option(
        None, "--task", help="Filter to a specific task"
    ),
    last: int | None = typer.Option(
        None, "--last", help="Only include last N races"
    ),
    title: str = typer.Option(
        "coderace Leaderboard", "--title", help="Custom dashboard title"
    ),
    open_browser: bool = typer.Option(
        False, "--open", help="Open dashboard in browser after generation"
    ),
) -> None:
    """Generate an HTML dashboard from race results."""
    console = Console()

    try:
        store = ResultStore()
    except Exception as exc:
        console.print(f"[red]Cannot open result store: {exc}[/red]")
        raise typer.Exit(1)

    try:
        html = generate_dashboard(
            store,
            task_name=task,
            limit=last,
            title=title,
        )
    finally:
        store.close()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    console.print(f"[green]Dashboard written to:[/green] {output}")

    if open_browser:
        url = output.resolve().as_uri()
        webbrowser.open(url)
        console.print(f"[dim]Opened in browser[/dim]")
