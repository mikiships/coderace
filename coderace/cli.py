"""CLI interface for coderace."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from coderace import __version__
from coderace.adapters import ADAPTERS
from coderace.git_ops import (
    add_worktree,
    branch_name_for,
    checkout,
    create_branch,
    get_current_ref,
    get_diff_stat,
    has_uncommitted_changes,
    prune_worktrees,
    remove_worktree,
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


def _run_agent_sequential(
    agent_name: str,
    task_description: str,
    repo: Path,
    branch: str,
    base_ref: str,
    timeout: int,
) -> tuple[AgentResult | None, int]:
    """Run a single agent sequentially (on the main repo). Returns (result, lines_changed)."""
    try:
        create_branch(repo, branch, base_ref)
    except Exception:
        return None, 0

    adapter = ADAPTERS[agent_name]()
    result = adapter.run(task_description, repo, timeout)

    _, lines = get_diff_stat(repo, base_ref)
    return result, lines


def _run_agent_worktree(
    agent_name: str,
    task_description: str,
    repo: Path,
    branch: str,
    base_ref: str,
    timeout: int,
) -> tuple[AgentResult | None, int]:
    """Run a single agent in a git worktree (for parallel execution)."""
    import tempfile

    worktree_dir = Path(tempfile.mkdtemp(prefix=f"coderace-{agent_name}-"))

    try:
        # Create branch first (from main repo)
        create_branch(repo, branch, base_ref)
        # Checkout back so worktree can use the branch
        checkout(repo, base_ref)
        # Create worktree
        add_worktree(repo, worktree_dir, branch)

        adapter = ADAPTERS[agent_name]()
        result = adapter.run(task_description, worktree_dir, timeout)

        _, lines = get_diff_stat(worktree_dir, base_ref)
        return result, lines
    except Exception:
        return None, 0
    finally:
        remove_worktree(repo, worktree_dir)
        # Clean up temp dir if it still exists
        import shutil

        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)


@app.command()
def run(
    task_file: Path = typer.Argument(help="Path to task YAML file"),
    agents: list[str] | None = typer.Option(None, "--agent", "-a", help="Override agent list"),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Run agents in parallel"),
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
    mode = "parallel" if parallel else "sequential"
    console.print(f"[dim]Base ref: {base_ref[:8]} | Mode: {mode}[/dim]")
    console.print(f"[dim]Task: {task.name}[/dim]")
    console.print(f"[dim]Agents: {', '.join(task.agents)}[/dim]")
    console.print()

    # Validate agents
    valid_agents = [a for a in task.agents if a in ADAPTERS]
    invalid = set(task.agents) - set(valid_agents)
    for name in invalid:
        console.print(f"[red]Unknown agent: {name}[/red]")

    if not valid_agents:
        console.print("[red]No valid agents to run.[/red]")
        raise typer.Exit(1)

    agent_results: list[AgentResult] = []
    diff_lines_map: dict[str, int] = {}

    if parallel and len(valid_agents) > 1:
        console.print("[cyan]Racing agents in parallel...[/cyan]")
        from concurrent.futures import ThreadPoolExecutor, as_completed

        futures = {}
        with ThreadPoolExecutor(max_workers=len(valid_agents)) as executor:
            for agent_name in valid_agents:
                branch = branch_name_for(task.name, agent_name)
                future = executor.submit(
                    _run_agent_worktree,
                    agent_name,
                    task.description,
                    repo,
                    branch,
                    base_ref,
                    task.timeout,
                )
                futures[future] = agent_name

            for future in as_completed(futures):
                agent_name = futures[future]
                result, lines = future.result()
                if result:
                    agent_results.append(result)
                    diff_lines_map[agent_name] = lines
                    if result.timed_out:
                        console.print(
                            f"  [yellow]{agent_name}: timed out after {task.timeout}s[/yellow]"
                        )
                    elif result.exit_code != 0:
                        console.print(
                            f"  [yellow]{agent_name}: exit code {result.exit_code}[/yellow]"
                        )
                    else:
                        console.print(
                            f"  [green]{agent_name}: completed in {result.wall_time:.1f}s[/green]"
                        )
                else:
                    console.print(f"  [red]{agent_name}: failed to run[/red]")

        prune_worktrees(repo)
    else:
        # Sequential mode
        for agent_name in valid_agents:
            branch = branch_name_for(task.name, agent_name)
            console.print(f"[cyan]Running {agent_name}...[/cyan]")

            result, lines = _run_agent_sequential(
                agent_name, task.description, repo, branch, base_ref, task.timeout
            )

            if result is None:
                console.print(f"  [red]Failed to create branch for {agent_name}[/red]")
                continue

            agent_results.append(result)
            diff_lines_map[agent_name] = lines

            if result.timed_out:
                console.print(f"  [yellow]Timed out after {task.timeout}s[/yellow]")
            elif result.exit_code != 0:
                console.print(f"  [yellow]Exit code: {result.exit_code}[/yellow]")
            else:
                console.print(f"  [green]Completed in {result.wall_time:.1f}s[/green]")

            console.print(f"  [dim]Lines changed: {lines}[/dim]")

    if not agent_results:
        console.print("[red]No agents ran successfully.[/red]")
        raise typer.Exit(1)

    # Score each agent (checkout each branch for test/lint)
    all_wall_times = [r.wall_time for r in agent_results]
    all_diff_lines = [diff_lines_map.get(r.agent, 0) for r in agent_results]
    scores: list[Score] = []

    for result in agent_results:
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
            weights=task.get_weights(),
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
