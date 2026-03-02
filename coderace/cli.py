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

from coderace.commands.tasks import app as tasks_app
from coderace.commands.benchmark import app as benchmark_app
from coderace.commands.context_eval import app as context_eval_app

app = typer.Typer(
    name="coderace",
    help="Race coding agents against each other on real tasks.",
    no_args_is_help=True,
)
app.add_typer(tasks_app, name="tasks")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(context_eval_app, name="context-eval")
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
    no_cost: bool = False,
    custom_pricing: dict | None = None,
) -> tuple[AgentResult | None, int]:
    """Run a single agent sequentially (on the main repo). Returns (result, lines_changed)."""
    try:
        create_branch(repo, branch, base_ref)
    except Exception:
        return None, 0

    adapter = ADAPTERS[agent_name]()
    result = adapter.run(task_description, repo, timeout, no_cost=no_cost, custom_pricing=custom_pricing)

    _, lines = get_diff_stat(repo, base_ref)
    return result, lines


def _run_agent_worktree(
    agent_name: str,
    task_description: str,
    repo: Path,
    branch: str,
    base_ref: str,
    timeout: int,
    no_cost: bool = False,
    custom_pricing: dict | None = None,
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
        result = adapter.run(task_description, worktree_dir, timeout, no_cost=no_cost, custom_pricing=custom_pricing)

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
    task_file: Path = typer.Argument(None, help="Path to task YAML file"),
    agents: list[str] | None = typer.Option(
        None, "--agent", "-a", help="Override agent list"
    ),
    parallel: bool = typer.Option(
        False, "--parallel", "-p", help="Run agents in parallel"
    ),
    runs: int = typer.Option(
        1, "--runs", "-n", help="Number of runs (>1 for stats)"
    ),
    no_cost: bool = typer.Option(
        False, "--no-cost", help="Disable cost tracking"
    ),
    no_save: bool = typer.Option(
        False, "--no-save", help="Skip saving results to the local database"
    ),
    builtin: str | None = typer.Option(
        None, "--builtin", help="Use a built-in task instead of a file"
    ),
) -> None:
    """Run all agents on a task and score the results."""
    if builtin and task_file:
        console.print("[red]Cannot use both --builtin and a task file path.[/red]")
        raise typer.Exit(1)

    if builtin:
        from coderace.builtins import get_builtin_path

        try:
            task_file = get_builtin_path(builtin)
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)
    elif task_file is None:
        console.print("[red]Provide a task file path or use --builtin <name>.[/red]")
        raise typer.Exit(1)

    task = load_task(task_file)

    if runs < 1:
        console.print("[red]--runs must be >= 1[/red]")
        raise typer.Exit(1)

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

    if runs > 1:
        console.print(
            f"[dim]Statistical mode: {runs} runs[/dim]"
        )

    all_run_scores: list[list[Score]] = []

    for run_idx in range(1, runs + 1):
        run_suffix = f"-run{run_idx}" if runs > 1 else ""

        if runs > 1:
            console.print(
                f"\n[bold]Run {run_idx}/{runs}[/bold]"
            )

        agent_results: list[AgentResult] = []
        diff_lines_map: dict[str, int] = {}

        if parallel and len(valid_agents) > 1:
            console.print(
                "[cyan]Racing agents in parallel...[/cyan]"
            )
            from concurrent.futures import (
                ThreadPoolExecutor,
                as_completed,
            )

            futures = {}
            with ThreadPoolExecutor(
                max_workers=len(valid_agents)
            ) as executor:
                for agent_name in valid_agents:
                    branch = (
                        branch_name_for(task.name, agent_name)
                        + run_suffix
                    )
                    future = executor.submit(
                        _run_agent_worktree,
                        agent_name,
                        task.description,
                        repo,
                        branch,
                        base_ref,
                        task.timeout,
                        no_cost,
                        task.pricing,
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
                                f"  [yellow]{agent_name}: "
                                f"timed out after "
                                f"{task.timeout}s[/yellow]"
                            )
                        elif result.exit_code != 0:
                            console.print(
                                f"  [yellow]{agent_name}: "
                                f"exit code "
                                f"{result.exit_code}[/yellow]"
                            )
                        else:
                            console.print(
                                f"  [green]{agent_name}: "
                                f"completed in "
                                f"{result.wall_time:.1f}s"
                                f"[/green]"
                            )
                    else:
                        console.print(
                            f"  [red]{agent_name}: "
                            f"failed to run[/red]"
                        )

            prune_worktrees(repo)
        else:
            # Sequential mode
            for agent_name in valid_agents:
                branch = (
                    branch_name_for(task.name, agent_name)
                    + run_suffix
                )
                console.print(
                    f"[cyan]Running {agent_name}...[/cyan]"
                )

                result, lines = _run_agent_sequential(
                    agent_name,
                    task.description,
                    repo,
                    branch,
                    base_ref,
                    task.timeout,
                    no_cost=no_cost,
                    custom_pricing=task.pricing,
                )

                if result is None:
                    console.print(
                        f"  [red]Failed to create branch "
                        f"for {agent_name}[/red]"
                    )
                    continue

                agent_results.append(result)
                diff_lines_map[agent_name] = lines

                if result.timed_out:
                    console.print(
                        f"  [yellow]Timed out after "
                        f"{task.timeout}s[/yellow]"
                    )
                elif result.exit_code != 0:
                    console.print(
                        f"  [yellow]Exit code: "
                        f"{result.exit_code}[/yellow]"
                    )
                else:
                    console.print(
                        f"  [green]Completed in "
                        f"{result.wall_time:.1f}s[/green]"
                    )

                console.print(
                    f"  [dim]Lines changed: {lines}[/dim]"
                )

        if not agent_results:
            console.print(
                "[red]No agents ran successfully.[/red]"
            )
            if run_idx == 1:
                raise typer.Exit(1)
            continue

        # Score each agent
        all_wall_times = [r.wall_time for r in agent_results]
        all_diff_lines = [
            diff_lines_map.get(r.agent, 0)
            for r in agent_results
        ]
        scores: list[Score] = []

        for result in agent_results:
            branch = (
                branch_name_for(task.name, result.agent)
                + run_suffix
            )
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
                verify_command=task.verify_command,
                verify_files=task.verify_files,
            )
            scores.append(score)

        # Return to base ref
        checkout(repo, base_ref)
        all_run_scores.append(scores)

    # Display results
    console.print()

    if runs == 1 and all_run_scores:
        # Single run: show normal table
        scores = all_run_scores[0]
        print_results(scores, console)

        results_dir = Path(task_file).parent / ".coderace"
        json_path = results_dir / f"{task.name}-results.json"
        save_results_json(scores, json_path)

        from coderace.html_report import save_html_report

        html_path = results_dir / f"{task.name}-results.html"
        save_html_report(
            scores,
            html_path,
            task_name=task.name,
            weights=task.get_weights(),
        )

        console.print(
            f"\n[dim]Results saved to {json_path}[/dim]"
        )
        console.print(f"[dim]HTML report: {html_path}[/dim]")
    elif all_run_scores:
        # Multi-run: show stats table
        from coderace.reporter import print_stats_results
        from coderace.stats import aggregate_runs

        stats = aggregate_runs(all_run_scores)
        print_stats_results(stats, console)

        # Also save per-run JSON
        results_dir = Path(task_file).parent / ".coderace"
        json_path = (
            results_dir / f"{task.name}-stats-results.json"
        )
        _save_stats_json(all_run_scores, stats, json_path)

        console.print(
            f"\n[dim]Stats results saved to {json_path}[/dim]"
        )

    # Auto-save to result store
    if not no_save and all_run_scores:
        _auto_save_to_store(task.name, all_run_scores, base_ref)


def _auto_save_to_store(
    task_name: str,
    all_run_scores: list[list[Score]],
    git_ref: str | None = None,
) -> None:
    """Save run results to the persistent result store (graceful fallback)."""
    try:
        from coderace.store import ResultStore

        store = ResultStore()
        for scores in all_run_scores:
            results = []
            for score in sorted(scores, key=lambda s: s.composite, reverse=True):
                r: dict = {
                    "agent": score.agent,
                    "composite_score": score.composite,
                    "wall_time": score.breakdown.wall_time,
                    "lines_changed": score.breakdown.lines_changed,
                    "tests_pass": score.breakdown.tests_pass,
                    "exit_clean": score.breakdown.exit_clean,
                    "lint_clean": score.breakdown.lint_clean,
                }
                if score.cost_result is not None:
                    r["cost_usd"] = score.cost_result.estimated_cost_usd
                    r["model_name"] = score.cost_result.model_name
                results.append(r)
            store.save_run(task_name, results, git_ref=git_ref)
        store.close()
    except Exception:
        # Graceful fallback: don't fail the run if store is unavailable
        pass


def _save_stats_json(
    all_run_scores: list[list[Score]],
    stats: list,
    output_path: Path,
) -> None:
    """Save multi-run statistical results to JSON."""
    import json

    from coderace.stats import AgentStats

    output_path.parent.mkdir(parents=True, exist_ok=True)

    per_run = []
    for run_idx, run_scores in enumerate(all_run_scores, 1):
        per_run.append(
            {
                "run": run_idx,
                "agents": [
                    {
                        "agent": s.agent,
                        "composite_score": s.composite,
                        "breakdown": {
                            "tests_pass": s.breakdown.tests_pass,
                            "exit_clean": s.breakdown.exit_clean,
                            "lint_clean": s.breakdown.lint_clean,
                            "wall_time": s.breakdown.wall_time,
                            "lines_changed": s.breakdown.lines_changed,
                        },
                    }
                    for s in run_scores
                ],
            }
        )

    aggregated = []
    for s in stats:
        assert isinstance(s, AgentStats)
        aggregated.append(
            {
                "rank": stats.index(s) + 1,
                "agent": s.agent,
                "runs": s.runs,
                "score_mean": s.score_mean,
                "score_stddev": s.score_stddev,
                "time_mean": s.time_mean,
                "time_stddev": s.time_stddev,
                "lines_mean": s.lines_mean,
                "lines_stddev": s.lines_stddev,
                "tests_pass_rate": s.tests_pass_rate,
                "exit_clean_rate": s.exit_clean_rate,
                "lint_clean_rate": s.lint_clean_rate,
                "per_run_scores": s.per_run_scores,
                "cost_mean": s.cost_mean,
                "cost_stddev": s.cost_stddev,
            }
        )

    data = {"type": "statistical", "per_run": per_run, "aggregated": aggregated}
    output_path.write_text(json.dumps(data, indent=2) + "\n")


@app.command()
def results(
    task_file: Path = typer.Argument(help="Path to task YAML file"),
    html_output: Path | None = typer.Option(
        None, "--html", help="Export as HTML report"
    ),
    fmt: str | None = typer.Option(
        None,
        "--format",
        "-F",
        help="Output format: terminal (default) | markdown | json",
    ),
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

    # -- markdown / json output (write to stdout, skip Rich table) --
    if fmt == "markdown":
        import sys

        from coderace.commands.results import format_markdown_from_json

        sys.stdout.write(format_markdown_from_json(data, task_name=task.name))
        return

    if fmt == "json":
        import json as _json
        import sys

        sys.stdout.write(_json.dumps({"results": data}, indent=2) + "\n")
        return

    if fmt is not None and fmt not in ("terminal", "markdown", "json"):
        console.print(
            f"[red]Unknown --format {fmt!r}. Choose: terminal, markdown, json[/red]"
        )
        raise typer.Exit(1)

    # -- default terminal Rich table --
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
    table.add_column("Cost (USD)", justify="right")

    for entry in data:
        b = entry["breakdown"]
        cost_info = entry.get("cost")
        cost_str = (
            f"${cost_info['estimated_cost_usd']:.4f}"
            if cost_info is not None
            else "-"
        )
        table.add_row(
            str(entry["rank"]),
            entry["agent"],
            f"{entry['composite_score']:.1f}",
            _bool_icon(b["tests_pass"]),
            _bool_icon(b["exit_clean"]),
            _bool_icon(b["lint_clean"]),
            f"{b['wall_time']:.1f}",
            str(b["lines_changed"]),
            cost_str,
        )

    console.print(table)

    if html_output is not None:
        from coderace.html_report import save_html_report
        from coderace.types import Score as ScoreType
        from coderace.types import ScoreBreakdown

        # Reconstruct Score objects from JSON data for HTML report
        score_objects = [
            ScoreType(
                agent=entry["agent"],
                composite=entry["composite_score"],
                breakdown=ScoreBreakdown(
                    tests_pass=entry["breakdown"]["tests_pass"],
                    exit_clean=entry["breakdown"]["exit_clean"],
                    lint_clean=entry["breakdown"]["lint_clean"],
                    wall_time=entry["breakdown"]["wall_time"],
                    lines_changed=entry["breakdown"]["lines_changed"],
                ),
            )
            for entry in data
        ]
        save_html_report(score_objects, html_output, task_name=task.name)
        console.print(f"\n[dim]HTML report saved to {html_output}[/dim]")


@app.command()
def diff(
    file: Path | None = typer.Option(
        None, "--file", "-f", help="Read diff from file (default: stdin)"
    ),
    mode: str = typer.Option(
        "review",
        "--mode",
        "-m",
        help="Task mode: review | fix | improve",
    ),
    agents: list[str] | None = typer.Option(
        None, "--agents", "-a", help="Agents to include (repeatable)"
    ),
    name: str = typer.Option("diff-task", "--name", "-n", help="Task name"),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write YAML to file (default: stdout)"
    ),
    test_command: str = typer.Option(
        "pytest tests/ -x", "--test-command", help="Test command for generated task"
    ),
    lint_command: str | None = typer.Option(
        "ruff check .", "--lint-command", help="Lint command for generated task"
    ),
) -> None:
    """Generate a coderace task YAML from a git diff (stdin or --file).

    Examples:

      git diff HEAD~1 | coderace diff --mode fix

      coderace diff --file my.patch --mode review --output task.yaml
    """
    from coderace.commands.diff import MODES, generate_task_yaml, read_diff

    if mode not in MODES:
        console.print(f"[red]Unknown mode {mode!r}. Choose from: {', '.join(sorted(MODES))}[/red]")
        raise typer.Exit(1)

    try:
        diff_text = read_diff(file)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    task_yaml = generate_task_yaml(
        diff=diff_text,
        mode=mode,
        agents=list(agents) if agents else None,
        name=name,
        test_command=test_command,
        lint_command=lint_command,
    )

    if output is not None:
        output.write_text(task_yaml, encoding="utf-8")
        console.print(f"[green]Task YAML written to:[/green] {output}")
    else:
        # Print raw YAML without Rich markup
        import sys
        sys.stdout.write(task_yaml)


@app.command()
def leaderboard(
    task: str | None = typer.Option(
        None, "--task", help="Filter by task name"
    ),
    since: str | None = typer.Option(
        None, "--since", help='Filter by time (ISO date or "7d", "30d")'
    ),
    min_runs: int = typer.Option(
        0, "--min-runs", help="Exclude agents with fewer than N races"
    ),
    fmt: str | None = typer.Option(
        None,
        "--format",
        "-F",
        help="Output format: terminal (default) | markdown | json | html",
    ),
) -> None:
    """Show aggregate leaderboard rankings across all runs."""
    from coderace.commands.leaderboard import (
        format_leaderboard_html,
        format_leaderboard_json,
        format_leaderboard_markdown,
        format_leaderboard_terminal,
    )
    from coderace.store import ResultStore

    try:
        store = ResultStore()
    except Exception as exc:
        console.print(f"[red]Cannot open result store: {exc}[/red]")
        raise typer.Exit(1)

    try:
        stats = store.get_agent_stats(
            task_name=task,
            since=since,
            min_runs=min_runs,
        )
    finally:
        store.close()

    if not stats:
        console.print("[yellow]No data yet. Run some races first.[/yellow]")
        return

    if fmt == "markdown":
        import sys

        sys.stdout.write(format_leaderboard_markdown(stats))
    elif fmt == "json":
        import sys

        sys.stdout.write(format_leaderboard_json(stats))
    elif fmt == "html":
        import sys

        sys.stdout.write(format_leaderboard_html(stats))
    elif fmt is not None and fmt != "terminal":
        console.print(
            f"[red]Unknown --format {fmt!r}. Choose: terminal, markdown, json, html[/red]"
        )
        raise typer.Exit(1)
    else:
        format_leaderboard_terminal(stats, console)


@app.command()
def ratings(
    reset: bool = typer.Option(False, "--reset", help="Reset all ELO ratings to 1500"),
    as_json: bool = typer.Option(False, "--json", help="Output ratings as JSON"),
) -> None:
    """Show or reset persistent benchmark ELO ratings."""
    from coderace.store import ResultStore

    try:
        store = ResultStore()
    except Exception as exc:
        console.print(f"[red]Cannot open result store: {exc}[/red]")
        raise typer.Exit(1)

    try:
        if reset:
            store.reset_elo_ratings(initial_rating=1500.0)
        ratings_map = store.get_elo_ratings()
    finally:
        store.close()

    if as_json:
        import json
        import sys

        sys.stdout.write(json.dumps(ratings_map, indent=2) + "\n")
        return

    if not ratings_map:
        console.print("[yellow]No ELO ratings yet. Run `coderace benchmark` first.[/yellow]")
        return

    from rich.table import Table

    table = Table(title="ELO Ratings", show_lines=True)
    table.add_column("Rank", justify="right")
    table.add_column("Agent", style="cyan")
    table.add_column("Rating", justify="right")

    for idx, (agent, rating) in enumerate(ratings_map.items(), start=1):
        table.add_row(str(idx), agent, f"{rating:.1f}")
    console.print(table)


@app.command()
def history(
    task: str | None = typer.Option(
        None, "--task", help="Filter by task name"
    ),
    agent: str | None = typer.Option(
        None, "--agent", help="Show only runs including this agent"
    ),
    limit: int = typer.Option(
        20, "--limit", "-n", help="Maximum number of runs to show"
    ),
    fmt: str | None = typer.Option(
        None,
        "--format",
        "-F",
        help="Output format: terminal (default) | markdown | json",
    ),
) -> None:
    """Show past race runs (newest first)."""
    from coderace.commands.history import (
        format_history_json,
        format_history_markdown,
        format_history_terminal,
    )
    from coderace.store import ResultStore

    try:
        store = ResultStore()
    except Exception as exc:
        console.print(f"[red]Cannot open result store: {exc}[/red]")
        raise typer.Exit(1)

    try:
        runs = store.get_runs(task_name=task, agent=agent, limit=limit)
    finally:
        store.close()

    if not runs:
        console.print("[yellow]No runs recorded yet.[/yellow]")
        return

    if fmt == "markdown":
        import sys

        sys.stdout.write(format_history_markdown(runs))
    elif fmt == "json":
        import sys

        sys.stdout.write(format_history_json(runs))
    elif fmt is not None and fmt != "terminal":
        console.print(
            f"[red]Unknown --format {fmt!r}. Choose: terminal, markdown, json[/red]"
        )
        raise typer.Exit(1)
    else:
        format_history_terminal(runs, console)


@app.command()
def dashboard(
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
    publish: bool = typer.Option(
        False, "--publish", help="Publish dashboard to here.now"
    ),
    here_now_key: str | None = typer.Option(
        None, "--here-now-key", help="here.now API key for persistent publish"
    ),
    context_eval_json: Path | None = typer.Option(
        None, "--context-eval", help="Include context-eval JSON results in dashboard"
    ),
) -> None:
    """Generate an HTML dashboard from race results."""
    import json
    import webbrowser

    from coderace.dashboard import generate_dashboard
    from coderace.store import ResultStore

    context_eval_data = None
    if context_eval_json is not None:
        if not context_eval_json.exists():
            console.print(f"[red]Context-eval file not found: {context_eval_json}[/red]")
            raise typer.Exit(1)
        context_eval_data = json.loads(context_eval_json.read_text())

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
            context_eval_data=context_eval_data,
        )
    finally:
        store.close()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    console.print(f"[green]Dashboard written to:[/green] {output}")

    if publish:
        from coderace.publish import PublishError, publish_html

        console.print("[cyan]Publishing to here.now...[/cyan]")
        try:
            result = publish_html(html, api_key=here_now_key)
            console.print(f"[green]Published:[/green] {result.url}")
            if result.expires:
                console.print("[dim]Anonymous publish — expires in 24h[/dim]")
        except PublishError as exc:
            console.print(f"[red]Publish failed: {exc}[/red]")
            raise typer.Exit(1)

    if open_browser:
        url = output.resolve().as_uri()
        webbrowser.open(url)
        console.print(f"[dim]Opened in browser[/dim]")


@app.command()
def version() -> None:
    """Show coderace version."""
    console.print(f"coderace {__version__}")


def _bool_icon(val: bool) -> str:
    return "[green]PASS[/green]" if val else "[red]FAIL[/red]"


if __name__ == "__main__":
    app()
