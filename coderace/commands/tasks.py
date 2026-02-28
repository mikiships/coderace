"""Built-in task discovery commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from coderace.builtins import get_builtin_path, list_builtins, load_builtin

app = typer.Typer(
    name="tasks",
    help="Discover and inspect built-in benchmark tasks.",
    no_args_is_help=True,
)
console = Console()


@app.command("list")
def list_tasks() -> None:
    """List all available built-in tasks."""
    names = list_builtins()
    if not names:
        console.print("[yellow]No built-in tasks found.[/yellow]")
        return

    table = Table(title="Built-in Tasks", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Verify", justify="center")
    table.add_column("Description")

    for name in names:
        data = load_builtin(name)
        desc = data.get("description", "").strip().split("\n")[0]
        has_verify = bool(data.get("verify_command"))
        verify_label = "[green]yes[/green]" if has_verify else "-"
        table.add_row(name, verify_label, desc)

    console.print(table)
    console.print(f"\n[dim]Run a task: coderace run --builtin <name>[/dim]")


@app.command("show")
def show_task(
    name: str = typer.Argument(help="Built-in task name"),
) -> None:
    """Print the full YAML of a built-in task."""
    import sys

    try:
        path = get_builtin_path(name)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    sys.stdout.write(path.read_text())
