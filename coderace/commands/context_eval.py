"""CLI command: coderace context-eval"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(help="Evaluate whether a context file improves agent performance.")
console = Console()


@app.callback(invoke_without_command=True)
def context_eval_main(
    ctx: typer.Context,
    context_file: Path = typer.Option(
        ..., "--context-file", "-c", help="Path to the context file to evaluate (e.g. CLAUDE.md)"
    ),
    task: Optional[Path] = typer.Option(
        None, "--task", "-t", help="Path to a single task YAML file"
    ),
    benchmark: bool = typer.Option(
        False, "--benchmark", "-b", help="Run against built-in benchmark tasks"
    ),
    agents: Optional[str] = typer.Option(
        None, "--agents", "-a", help="Comma-separated list of agents (e.g. claude,codex)"
    ),
    trials: int = typer.Option(
        3, "--trials", "-n", help="Number of trials per condition (min: 2)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Save JSON results to this path"
    ),
    task_dir: Optional[Path] = typer.Option(
        None, "--task-dir", help="Custom task directory for benchmark mode"
    ),
) -> None:
    """Run A/B evaluation: baseline (no context) vs treatment (with context file)."""
    if ctx.invoked_subcommand is not None:
        return

    # Validate inputs
    if not context_file.exists():
        console.print(f"[red]Context file not found: {context_file}[/red]")
        raise typer.Exit(1)

    if not task and not benchmark:
        console.print("[red]Specify --task PATH or --benchmark.[/red]")
        raise typer.Exit(1)

    if task and benchmark:
        console.print("[red]Cannot use both --task and --benchmark.[/red]")
        raise typer.Exit(1)

    if trials < 2:
        console.print("[red]--trials must be >= 2 for statistical comparison.[/red]")
        raise typer.Exit(1)

    if not agents:
        console.print("[red]--agents is required. Use --agents claude,codex[/red]")
        raise typer.Exit(1)

    agent_list = [a.strip() for a in agents.split(",") if a.strip()]
    if not agent_list:
        console.print("[red]No agents specified.[/red]")
        raise typer.Exit(1)

    # Validate agents
    from coderace.adapters import ADAPTERS
    valid_agents = [a for a in agent_list if a in ADAPTERS]
    invalid = set(agent_list) - set(valid_agents)
    for name in invalid:
        console.print(f"[red]Unknown agent: {name}[/red]")
    if not valid_agents:
        console.print("[red]No valid agents to run.[/red]")
        raise typer.Exit(1)

    # Resolve task paths
    task_paths: list[Path] = []
    if task:
        if not task.exists():
            console.print(f"[red]Task file not found: {task}[/red]")
            raise typer.Exit(1)
        task_paths.append(task)
    elif benchmark:
        if task_dir:
            if not task_dir.is_dir():
                console.print(f"[red]Task directory not found: {task_dir}[/red]")
                raise typer.Exit(1)
            task_paths = sorted(task_dir.glob("*.yaml"))
            if not task_paths:
                console.print(f"[yellow]No .yaml files found in {task_dir}[/yellow]")
                raise typer.Exit(1)
        else:
            from coderace.builtins import get_builtin_path, list_builtins
            for name in list_builtins():
                task_paths.append(get_builtin_path(name))

    if not task_paths:
        console.print("[red]No tasks selected.[/red]")
        raise typer.Exit(1)

    console.print("[bold cyan]coderace context-eval[/bold cyan]")
    console.print(f"[dim]Context file: {context_file}[/dim]")
    console.print(f"[dim]Agents: {', '.join(valid_agents)}[/dim]")
    console.print(f"[dim]Tasks: {len(task_paths)}[/dim]")
    console.print(f"[dim]Trials per condition: {trials}[/dim]")
    console.print()

    from coderace.context_eval import run_context_eval

    def progress_callback(
        agent: str, task_name: str, condition: str, trial_num: int, status: str
    ) -> None:
        console.print(
            f"  [dim]{task_name} / {agent} / {condition} / trial {trial_num}: {status}[/dim]"
        )

    eval_result = run_context_eval(
        context_file=context_file,
        agents=valid_agents,
        task_paths=task_paths,
        trials=trials,
        progress_callback=progress_callback,
    )

    # Generate and display report
    from coderace.context_eval_report import (
        render_context_eval_json,
        render_context_eval_terminal,
    )

    console.print()
    render_context_eval_terminal(eval_result, console)

    if output:
        json_data = render_context_eval_json(eval_result)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(json_data, indent=2) + "\n")
        console.print(f"\n[dim]Results saved to {output}[/dim]")
