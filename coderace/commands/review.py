"""CLI command: coderace review."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from coderace.adapters import ADAPTERS, parse_agent_spec
from coderace.review import DEFAULT_REVIEW_AGENTS, DEFAULT_REVIEW_LANES, run_review
from coderace.review_report import render_review_json, render_review_markdown
from coderace.maintainer_rubric import score_rubric
from coderace.display import MaintainerRubricDisplay

app = typer.Typer(
    help="Run multi-lane parallel agent review on a diff.",
    context_settings={"allow_interspersed_args": True},
)


def _parse_csv_option(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _validate_agents(agents: list[str]) -> list[str]:
    valid_agents: list[str] = []
    for agent in agents:
        if parse_agent_spec(agent)[0] in ADAPTERS:
            valid_agents.append(agent)
    return valid_agents


def _read_stdin_diff() -> str:
    if sys.stdin.isatty():
        raise ValueError(
            "No diff provided. Use --diff, --commit, --branch, or pipe diff text to stdin."
        )
    return sys.stdin.read()


def _read_diff_source(
    diff_file: Path | None,
    commit: str | None,
    branch: str | None,
    workdir: Path,
) -> str:
    if diff_file is not None:
        if not diff_file.exists():
            raise FileNotFoundError(f"Diff file not found: {diff_file}")
        return diff_file.read_text(encoding="utf-8")
    if commit:
        return _git_diff(["git", "diff", f"{commit}~1", commit], workdir)
    if branch:
        if "..." not in branch:
            raise ValueError("Branch diff must use <base>...<head> syntax.")
        base, head = branch.split("...", 1)
        return _git_diff(["git", "diff", f"{base}...{head}"], workdir)
    return _read_stdin_diff()


def _git_diff(command: list[str], workdir: Path) -> str:
    result = subprocess.run(
        command,
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return result.stdout


@app.callback(invoke_without_command=True)
def review_main(
    ctx: typer.Context,
    diff_file: Path | None = typer.Option(
        None,
        "--diff",
        help="Read diff from file (default: stdin)",
    ),
    commit: str | None = typer.Option(
        None,
        "--commit",
        help="Generate diff from commit ref (for example HEAD~1 or abc123)",
    ),
    branch: str | None = typer.Option(
        None,
        "--branch",
        help="Generate diff from branch range (for example main...my-branch)",
    ),
    lanes: str = typer.Option(
        ",".join(DEFAULT_REVIEW_LANES),
        "--lanes",
        help="Comma-separated review lanes",
    ),
    agents: str = typer.Option(
        ",".join(DEFAULT_REVIEW_AGENTS),
        "--agents",
        help="Comma-separated agents",
    ),
    cross_review: bool = typer.Option(
        False,
        "--cross-review",
        help="Run Phase 2 cross-review after Phase 1",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Write report to file (default: stdout)",
    ),
    fmt: str = typer.Option(
        "markdown",
        "--format",
        help="Output format: markdown|json",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Plain output (no rich markup)",
    ),
    maintainer_mode: bool = typer.Option(
        False,
        "--maintainer-mode",
        help="Append maintainer rubric section to review output (static analysis, no LLM)",
    ),
) -> None:
    """Run multi-lane parallel agent review on a diff."""
    if ctx.invoked_subcommand is not None:
        return

    console = Console(stderr=True, no_color=no_color)
    workdir = Path.cwd()

    try:
        diff_text = _read_diff_source(diff_file, commit, branch, workdir)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    if not diff_text.strip():
        console.print("[red]Diff input is empty.[/red]")
        raise typer.Exit(1)

    resolved_lanes = _parse_csv_option(lanes)
    resolved_agents = _parse_csv_option(agents)
    valid_agents = _validate_agents(resolved_agents)
    invalid_agents = [agent for agent in resolved_agents if agent not in valid_agents]
    for agent in invalid_agents:
        console.print(f"[red]Unknown agent: {agent}[/red]")
    if not valid_agents:
        console.print("[red]No valid agents to run.[/red]")
        raise typer.Exit(1)

    try:
        result = run_review(
            diff_text,
            resolved_lanes,
            valid_agents,
            cross_review=cross_review,
            workdir=workdir,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    if fmt == "json":
        rendered = render_review_json(result)
    elif fmt == "markdown":
        rendered = render_review_markdown(result)
    else:
        console.print(f"[red]Unknown format: {fmt}. Choose from markdown or json.[/red]")
        raise typer.Exit(1)

    if output is not None:
        output.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Review report written to:[/green] {output}")
        if maintainer_mode:
            _append_maintainer_rubric(diff_text, console, no_color)
        return

    typer.echo(rendered, nl=False)

    if maintainer_mode:
        _append_maintainer_rubric(diff_text, console, no_color)


def _append_maintainer_rubric(diff_text: str, console: Console, no_color: bool) -> None:
    """Score the diff with the maintainer rubric and print the result."""
    rubric = score_rubric(diff_text)
    display_console = Console(no_color=no_color)
    display = MaintainerRubricDisplay()
    display_console.print()
    display.print(rubric, console=display_console)
