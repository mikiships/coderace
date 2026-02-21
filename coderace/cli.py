"""CLI interface for coderace."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from coderace import __version__
from coderace.adapters import ADAPTERS
from coderace.git_ops import (
    branch_name_for,
    checkout,
    create_branch,
    get_current_ref,
    get_diff_stat,
    has_uncommitted_changes,
)
from coderace.reporter import print_results, save_results_json
from coderace.scorer import compute_score
from coderace.task import create_template, load_task
from coderace.types import AgentResult, Score

app = typer.Typer(
    name="coderace",
    help="Race coding agents against each other on real tasks.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def init(
    name: str = typer.Argument(help="Task name"),
    output_dir: Path = typer.Option(".", "--output", "-o", help="Output directory"),
) -> None:
    """Create a task YAML template."""
    path = create_template(name, output_dir)
    console.print(f"[green]Created task template:[/green] {path}")
    console.print("Edit the file to define your task, then run: coderace run " + str(path))


@app.command()
def run(
    task_file: Path = typer.Argument(help="Path to task YAML file"),
    agents: list[str] | None = typer.Option(None, "--agent", "-a", help="Override agent list"),
) -> None:
    """Run all agents on a task and score the results."""
    task = load_task(task_file)

    if agents:
        task.agents = agents

    repo = task.repo
    if not repo.exists():
        console.print(f"[red]Repo not found:[/red] {repo}")
        raise typer.Exit(1)

    if has_uncommitted_changes(repo):
        console.print("[red]Repo has uncommitted changes. Commit or stash first.[/red]")
        raise typer.Exit(1)

    base_ref = get_current_ref(repo)
    console.print(f"[dim]Base ref: {base_ref[:8]}[/dim]")
    console.print(f"[dim]Task: {task.name}[/dim]")
    console.print(f"[dim]Agents: {', '.join(task.agents)}[/dim]")
    console.print()

    results: list[AgentResult] = []
    diff_lines_map: dict[str, int] = {}

    for agent_name in task.agents:
        if agent_name not in ADAPTERS:
            console.print(f"[red]Unknown agent: {agent_name}[/red]")
            continue

        branch = branch_name_for(task.name, agent_name)
        console.print(f"[cyan]Running {agent_name}...[/cyan]")

        # Create branch and run agent
        try:
            create_branch(repo, branch, base_ref)
        except Exception as e:
            console.print(f"[red]Failed to create branch for {agent_name}: {e}[/red]")
            continue

        adapter = ADAPTERS[agent_name]()
        result = adapter.run(task.description, repo, task.timeout)
        results.append(result)

        # Get diff stats while still on the branch
        _, lines = get_diff_stat(repo, base_ref)
        diff_lines_map[agent_name] = lines

        if result.timed_out:
            console.print(f"  [yellow]Timed out after {task.timeout}s[/yellow]")
        elif result.exit_code != 0:
            console.print(f"  [yellow]Exit code: {result.exit_code}[/yellow]")
        else:
            console.print(f"  [green]Completed in {result.wall_time:.1f}s[/green]")

        console.print(f"  [dim]Lines changed: {lines}[/dim]")

    if not results:
        console.print("[red]No agents ran successfully.[/red]")
        raise typer.Exit(1)

    # Score each agent (need to checkout each branch for test/lint)
    all_wall_times = [r.wall_time for r in results]
    all_diff_lines = [diff_lines_map.get(r.agent, 0) for r in results]
    scores: list[Score] = []

    for result in results:
        branch = branch_name_for(task.name, result.agent)
        checkout(repo, branch)

        score = compute_score(
            result=result,
            test_command=task.test_command,
            lint_command=task.lint_command,
            workdir=repo,
            diff_lines=diff_lines_map.get(result.agent, 0),
            all_wall_times=all_wall_times,
            all_diff_lines=all_diff_lines,
        )
        scores.append(score)

    # Return to base ref
    checkout(repo, base_ref)

    # Display and save results
    console.print()
    print_results(scores, console)

    results_dir = Path(task_file).parent / ".coderace"
    json_path = results_dir / f"{task.name}-results.json"
    save_results_json(scores, json_path)
    console.print(f"\n[dim]Results saved to {json_path}[/dim]")


@app.command()
def results(
    task_file: Path = typer.Argument(help="Path to task YAML file"),
) -> None:
    """Show results from the last run."""
    task = load_task(task_file)
    results_dir = Path(task_file).parent / ".coderace"
    json_path = results_dir / f"{task.name}-results.json"

    if not json_path.exists():
        console.print(f"[red]No results found. Run the task first:[/red] coderace run {task_file}")
        raise typer.Exit(1)

    from coderace.reporter import load_results_json

    data = load_results_json(json_path)

    from rich.table import Table

    table = Table(title=f"coderace results: {task.name}", show_lines=True)
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("Agent", style="cyan")
    table.add_column("Score", justify="right", style="bold green")
    table.add_column("Tests", justify="center")
    table.add_column("Exit", justify="center")
    table.add_column("Lint", justify="center")
    table.add_column("Time (s)", justify="right")
    table.add_column("Lines", justify="right")

    for entry in data:
        b = entry["breakdown"]
        table.add_row(
            str(entry["rank"]),
            entry["agent"],
            f"{entry['composite_score']:.1f}",
            _bool_icon(b["tests_pass"]),
            _bool_icon(b["exit_clean"]),
            _bool_icon(b["lint_clean"]),
            f"{b['wall_time']:.1f}",
            str(b["lines_changed"]),
        )

    console.print(table)


@app.command()
def version() -> None:
    """Show coderace version."""
    console.print(f"coderace {__version__}")


def _bool_icon(val: bool) -> str:
    return "[green]PASS[/green]" if val else "[red]FAIL[/red]"


if __name__ == "__main__":
    app()
