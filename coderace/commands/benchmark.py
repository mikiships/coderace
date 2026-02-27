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
    agents: str = typer.Option(
        ..., "--agents", "-a", help="Comma-separated list of agents (e.g. claude,codex)"
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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="List what would run without executing"
    ),
    fmt: Optional[str] = typer.Option(
        None, "--format", "-F", help="Output format: terminal (default) | markdown | html"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save report to file (auto-selects format by extension)"
    ),
    no_save: bool = typer.Option(
        False, "--no-save", help="Skip saving benchmark results to the store"
    ),
) -> None:
    """Run all (or selected) built-in tasks against one or more agents and produce a comparison report."""
    if ctx.invoked_subcommand is not None:
        return

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

    # Dry-run mode
    if dry_run:
        console.print(f"[bold]Dry run:[/bold] {len(task_list)} tasks x {len(agent_list)} agents = {len(task_list) * len(agent_list)} runs\n")
        from rich.table import Table
        table = Table(title="Would run", show_lines=True)
        table.add_column("Task")
        table.add_column("Agent")
        for task_name in task_list:
            for agent in agent_list:
                table.add_row(task_name, agent)
        console.print(table)
        return

    console.print(f"[bold cyan]coderace benchmark[/bold cyan]")
    console.print(f"[dim]Agents: {', '.join(agent_list)}[/dim]")
    console.print(f"[dim]Tasks:  {', '.join(task_list)}[/dim]")
    console.print(f"[dim]Timeout: {timeout}s per task | Parallel: {parallel}[/dim]")
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
        progress_callback=progress_callback,
    )

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

    if out_fmt == "markdown":
        md = render_benchmark_markdown(benchmark_result, stats)
        if output:
            from pathlib import Path
            Path(output).write_text(md, encoding="utf-8")
            console.print(f"[green]Markdown report saved to:[/green] {output}")
        else:
            import sys
            sys.stdout.write(md)
    elif out_fmt == "html":
        html_content = render_benchmark_html(benchmark_result, stats)
        if output:
            from pathlib import Path
            Path(output).write_text(html_content, encoding="utf-8")
            console.print(f"[green]HTML report saved to:[/green] {output}")
        else:
            import sys
            sys.stdout.write(html_content)
    else:
        render_benchmark_terminal(benchmark_result, stats, console)
        if output:
            # Save markdown to file even in terminal mode if --output given
            md = render_benchmark_markdown(benchmark_result, stats)
            from pathlib import Path
            Path(output).write_text(md, encoding="utf-8")
            console.print(f"\n[dim]Report saved to {output}[/dim]")

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
            score=r["score"],
            wall_time=r["wall_time"],
            tests_pass=r["tests_pass"],
            exit_clean=r["exit_clean"],
            lint_clean=r["lint_clean"],
            timed_out=r["timed_out"],
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
        sys.stdout.write(render_benchmark_markdown(bench, stats))
    elif fmt == "html":
        import sys
        sys.stdout.write(render_benchmark_html(bench, stats))
    else:
        render_benchmark_terminal(bench, stats, console)
