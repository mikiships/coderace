"""CLI command: coderace benchmark"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(help="Benchmark agents across built-in tasks.")
console = Console()


@app.callback(invoke_without_command=True)
def benchmark_main(
    ctx: typer.Context,
    agents: Optional[str] = typer.Option(
        None, "--agents", "-a", help="Comma-separated list of agents (e.g. claude,codex)"
    ),
    tasks: Optional[str] = typer.Option(
        None, "--tasks", "-t", help="Comma-separated task names (default: all built-ins)"
    ),
    difficulty: Optional[str] = typer.Option(
        None, "--difficulty", "-d", help="Filter by difficulty: easy,medium,hard"
    ),
    timeout: int = typer.Option(
        300, "--timeout", help="Per-task timeout in seconds"
    ),
    parallel: int = typer.Option(
        1, "--parallel", "-p", help="Number of agents to run in parallel (default: 1)"
    ),
    trials: int = typer.Option(
        1, "--trials", help="Repeat each (task, agent) pair N times (default: 1)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="List what would run without executing"
    ),
    fmt: Optional[str] = typer.Option(
        None, "--format", "-F", help="Output format: terminal (default) | markdown | html"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save report to file (auto-selects format by extension)"
    ),
    export: Optional[str] = typer.Option(
        None, "--export", help="Export standardized benchmark JSON to file"
    ),
    no_save: bool = typer.Option(
        False, "--no-save", help="Skip saving benchmark results to the store"
    ),
) -> None:
    """Run all (or selected) built-in tasks against one or more agents and produce a comparison report."""
    if ctx.invoked_subcommand is not None:
        return

    if not agents:
        console.print("[red]--agents is required. Use --agents claude,codex[/red]")
        raise typer.Exit(1)

    from coderace.benchmark import list_benchmark_tasks

    agent_list = [a.strip() for a in agents.split(",") if a.strip()]
    if not agent_list:
        console.print("[red]No agents specified. Use --agents claude,codex[/red]")
        raise typer.Exit(1)

    # Resolve task list
    if tasks:
        task_list = [t.strip() for t in tasks.split(",") if t.strip()]
    else:
        diff_filter = [d.strip() for d in difficulty.split(",")] if difficulty else None
        task_list = list_benchmark_tasks(diff_filter)

    if not task_list:
        console.print("[yellow]No tasks match the given filters.[/yellow]")
        raise typer.Exit(0)

    if trials < 1:
        console.print("[red]--trials must be >= 1[/red]")
        raise typer.Exit(1)

    # Dry-run mode
    if dry_run:
        run_count = len(task_list) * len(agent_list) * trials
        console.print(
            f"[bold]Dry run:[/bold] {len(task_list)} tasks x {len(agent_list)} agents "
            f"x {trials} trial(s) = {run_count} runs\n"
        )
        from rich.table import Table
        table = Table(title="Would run", show_lines=True)
        table.add_column("Task")
        table.add_column("Agent")
        if trials > 1:
            table.add_column("Trial", justify="right")
        for task_name in task_list:
            for agent in agent_list:
                for trial_number in range(1, trials + 1):
                    if trials > 1:
                        table.add_row(task_name, agent, str(trial_number))
                    else:
                        table.add_row(task_name, agent)
        console.print(table)
        return

    console.print(f"[bold cyan]coderace benchmark[/bold cyan]")
    console.print(f"[dim]Agents: {', '.join(agent_list)}[/dim]")
    console.print(f"[dim]Tasks:  {', '.join(task_list)}[/dim]")
    console.print(
        f"[dim]Timeout: {timeout}s per task | Parallel: {parallel} | Trials: {trials}[/dim]"
    )
    console.print()

    from coderace.benchmark import run_benchmark

    status_lines: list[str] = []

    def progress_callback(task_name: str, agent: str, status: str) -> None:
        line = f"  {task_name} / {agent}: {status}"
        console.print(f"[dim]{line}[/dim]")
        status_lines.append(line)

    benchmark_result = run_benchmark(
        agents=agent_list,
        tasks=task_list,
        timeout=timeout,
        parallel=parallel,
        trials=trials,
        progress_callback=progress_callback,
    )
    rating_update = _update_benchmark_ratings(benchmark_result)

    console.print()

    # Determine output format
    out_fmt = fmt
    if output and out_fmt is None:
        if output.endswith(".html"):
            out_fmt = "html"
        elif output.endswith(".md"):
            out_fmt = "markdown"

    # Print/save report
    from coderace.benchmark_report import (
        render_benchmark_html,
        render_benchmark_markdown,
        render_benchmark_terminal,
    )
    from coderace.benchmark_stats import compute_benchmark_stats

    stats = compute_benchmark_stats(benchmark_result)
    elo_ratings = rating_update.after if rating_update is not None else None

    if out_fmt == "markdown":
        md = render_benchmark_markdown(benchmark_result, stats, elo_ratings=elo_ratings)
        if output:
            from pathlib import Path
            Path(output).write_text(md, encoding="utf-8")
            console.print(f"[green]Markdown report saved to:[/green] {output}")
        else:
            import sys
            sys.stdout.write(md)
    elif out_fmt == "html":
        html_content = render_benchmark_html(benchmark_result, stats, elo_ratings=elo_ratings)
        if output:
            from pathlib import Path
            Path(output).write_text(html_content, encoding="utf-8")
            console.print(f"[green]HTML report saved to:[/green] {output}")
        else:
            import sys
            sys.stdout.write(html_content)
    else:
        render_benchmark_terminal(benchmark_result, stats, console, elo_ratings=elo_ratings)
        if output:
            # Save markdown to file even in terminal mode if --output given
            md = render_benchmark_markdown(benchmark_result, stats, elo_ratings=elo_ratings)
            from pathlib import Path
            Path(output).write_text(md, encoding="utf-8")
            console.print(f"\n[dim]Report saved to {output}[/dim]")

    _print_rating_deltas(rating_update, benchmark_result.agents)
    if export:
        _export_benchmark_json(
            benchmark_result=benchmark_result,
            export_path=export,
            timeout=timeout,
            trials=trials,
            tasks=task_list,
            agents=agent_list,
            elo_ratings=elo_ratings or {},
        )
        console.print(f"[green]Benchmark export saved to:[/green] {export}")

    # Save to store
    if not no_save:
        _save_benchmark_to_store(benchmark_result, stats)
        console.print(f"\n[dim]Benchmark {benchmark_result.benchmark_id} saved to store.[/dim]")


def _save_benchmark_to_store(benchmark_result, stats) -> None:
    """Persist benchmark results to SQLite store."""
    try:
        from coderace.store import ResultStore
        store = ResultStore()
        store.save_benchmark(benchmark_result, stats)
        store.close()
    except Exception:
        pass


def _update_benchmark_ratings(benchmark_result):
    """Update persisted ELO ratings from a completed benchmark."""
    store = None
    try:
        from coderace.elo import update_ratings
        from coderace.store import ResultStore

        store = ResultStore()
        current = store.get_elo_ratings()
        rating_update = update_ratings(benchmark_result, current_ratings=current)
        store.upsert_elo_ratings(rating_update.after)
        return rating_update
    except Exception:
        return None
    finally:
        if store is not None:
            store.close()


def _print_rating_deltas(rating_update, agents: list[str]) -> None:
    """Print ELO rating deltas for benchmark participants."""
    if rating_update is None:
        return
    from rich.table import Table

    ordered_agents = sorted(
        agents,
        key=lambda agent: rating_update.after.get(agent, 1500.0),
        reverse=True,
    )
    table = Table(title="ELO Ratings", show_lines=True)
    table.add_column("Agent", style="cyan")
    table.add_column("Before", justify="right")
    table.add_column("After", justify="right")
    table.add_column("Delta", justify="right")

    for agent in ordered_agents:
        before = rating_update.before.get(agent, 1500.0)
        after = rating_update.after.get(agent, before)
        delta = after - before
        table.add_row(
            agent,
            f"{before:.1f}",
            f"{after:.1f}",
            f"{delta:+.1f}",
        )

    console.print()
    console.print(table)


def _export_benchmark_json(
    benchmark_result,
    export_path: str,
    timeout: int,
    trials: int,
    tasks: list[str],
    agents: list[str],
    elo_ratings: dict[str, float],
) -> None:
    """Write standardized benchmark export JSON."""
    from coderace.export import export_benchmark_json

    export_benchmark_json(
        benchmark_result=benchmark_result,
        output_path=export_path,
        timeout=timeout,
        trials=trials,
        tasks=tasks,
        agents=agents,
        elo_ratings=elo_ratings,
    )


@app.command("history")
def benchmark_history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of past benchmarks to show"),
    fmt: Optional[str] = typer.Option(None, "--format", "-F", help="Output format: terminal | json"),
) -> None:
    """List past benchmark runs."""
    from coderace.store import ResultStore

    try:
        store = ResultStore()
    except Exception as exc:
        console.print(f"[red]Cannot open result store: {exc}[/red]")
        raise typer.Exit(1)

    try:
        runs = store.get_benchmarks(limit=limit)
    finally:
        store.close()

    if not runs:
        console.print("[yellow]No benchmark runs recorded yet.[/yellow]")
        return

    if fmt == "json":
        import json, sys
        sys.stdout.write(json.dumps(runs, indent=2) + "\n")
        return

    from rich.table import Table
    table = Table(title="Benchmark History", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("Timestamp")
    table.add_column("Agents")
    table.add_column("Tasks")
    table.add_column("Winner")

    for run in runs:
        table.add_row(
            run.get("benchmark_id", "-"),
            run.get("timestamp", "-"),
            run.get("agents", "-"),
            str(run.get("task_count", "-")),
            run.get("winner", "-"),
        )
    console.print(table)


@app.command("show")
def benchmark_show(
    benchmark_id: str = typer.Argument(help="Benchmark ID to display"),
    fmt: Optional[str] = typer.Option(None, "--format", "-F", help="Output format: terminal | markdown | html | json"),
) -> None:
    """Display a past benchmark result."""
    from coderace.store import ResultStore

    try:
        store = ResultStore()
    except Exception as exc:
        console.print(f"[red]Cannot open result store: {exc}[/red]")
        raise typer.Exit(1)

    try:
        data = store.get_benchmark(benchmark_id)
        elo_ratings = store.get_elo_ratings()
    finally:
        store.close()

    if data is None:
        console.print(f"[red]Benchmark {benchmark_id!r} not found.[/red]")
        raise typer.Exit(1)

    if fmt == "json":
        import json, sys
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
        return

    # Reconstruct BenchmarkResult from stored data and display
    from coderace.benchmark import BenchmarkResult, TaskAgentResult
    from coderace.benchmark_report import render_benchmark_terminal, render_benchmark_markdown, render_benchmark_html
    from coderace.benchmark_stats import compute_benchmark_stats

    results = []
    for r in data.get("results", []):
        results.append(TaskAgentResult(
            task_name=r["task_name"],
            agent=r["agent"],
            trial_number=r.get("trial_number", 1),
            score=r["score"],
            wall_time=r["wall_time"],
            tests_pass=r["tests_pass"],
            exit_clean=r["exit_clean"],
            lint_clean=r["lint_clean"],
            timed_out=r["timed_out"],
            verify_applicable=r.get("verify_applicable", False),
            verify_passed=r.get("verify_passed", False),
            verify_score=r.get("verify_score", 0.0),
            verify_output=r.get("verify_output", ""),
            cost_usd=r.get("cost_usd"),
            error=r.get("error"),
        ))

    bench = BenchmarkResult(
        benchmark_id=data["benchmark_id"],
        agents=data["agents"],
        tasks=data["tasks"],
        results=results,
    )
    stats = compute_benchmark_stats(bench)

    if fmt == "markdown":
        import sys
        sys.stdout.write(render_benchmark_markdown(bench, stats, elo_ratings=elo_ratings))
    elif fmt == "html":
        import sys
        sys.stdout.write(render_benchmark_html(bench, stats, elo_ratings=elo_ratings))
    else:
        render_benchmark_terminal(bench, stats, console, elo_ratings=elo_ratings)
