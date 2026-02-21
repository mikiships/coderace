"""Results reporting (terminal table + JSON)."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from coderace.types import Score


def print_results(scores: list[Score], console: Console | None = None) -> str:
    """Print a rich table of results. Returns the table as a string."""
    console = console or Console()

    # Sort by composite score descending
    ranked = sorted(scores, key=lambda s: s.composite, reverse=True)

    table = Table(title="coderace results", show_lines=True)
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("Agent", style="cyan")
    table.add_column("Score", justify="right", style="bold green")
    table.add_column("Tests", justify="center")
    table.add_column("Exit", justify="center")
    table.add_column("Lint", justify="center")
    table.add_column("Time (s)", justify="right")
    table.add_column("Lines", justify="right")

    for i, score in enumerate(ranked, 1):
        b = score.breakdown
        table.add_row(
            str(i),
            score.agent,
            f"{score.composite:.1f}",
            _bool_icon(b.tests_pass),
            _bool_icon(b.exit_clean),
            _bool_icon(b.lint_clean),
            f"{b.wall_time:.1f}",
            str(b.lines_changed),
        )

    console.print(table)

    # Return as string for testing
    str_console = Console(file=None, force_terminal=False, width=100)
    with str_console.capture() as capture:
        str_console.print(table)
    return capture.get()


def save_results_json(scores: list[Score], output_path: Path) -> None:
    """Save results as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "results": [
            {
                "rank": i,
                "agent": score.agent,
                "composite_score": score.composite,
                "breakdown": {
                    "tests_pass": score.breakdown.tests_pass,
                    "exit_clean": score.breakdown.exit_clean,
                    "lint_clean": score.breakdown.lint_clean,
                    "wall_time": round(score.breakdown.wall_time, 2),
                    "lines_changed": score.breakdown.lines_changed,
                },
                "tests_output": score.tests_output,
                "lint_output": score.lint_output,
                "diff_stat": score.diff_stat,
            }
            for i, score in enumerate(
                sorted(scores, key=lambda s: s.composite, reverse=True), 1
            )
        ]
    }

    output_path.write_text(json.dumps(data, indent=2) + "\n")


def load_results_json(path: Path) -> list[dict]:
    """Load results from a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"No results found at {path}")
    data = json.loads(path.read_text())
    return data.get("results", [])


def _bool_icon(val: bool) -> str:
    return "[green]PASS[/green]" if val else "[red]FAIL[/red]"
