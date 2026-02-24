"""History command — show past runs."""

from __future__ import annotations

import json
import sys

from rich.console import Console
from rich.table import Table

from coderace.store import RunRecord


def format_history_terminal(runs: list[RunRecord], console: Console | None = None) -> str:
    """Render run history as a Rich terminal table."""
    console = console or Console()

    table = Table(title="coderace history", show_lines=True)
    table.add_column("Run ID", justify="center", style="bold")
    table.add_column("Date", style="dim")
    table.add_column("Task", style="cyan")
    table.add_column("Agents")
    table.add_column("Winner", style="bold green")
    table.add_column("Best Score", justify="right")

    for run in runs:
        agents_str = ", ".join(a.agent for a in run.agents)
        winners = [a for a in run.agents if a.is_winner]
        winner_str = ", ".join(w.agent for w in winners) if winners else "-"
        best_score = max((a.composite_score for a in run.agents), default=0.0)

        # Format timestamp for display (date + time, no microseconds)
        ts = run.timestamp
        if "T" in ts:
            ts = ts.split("T")[0] + " " + ts.split("T")[1][:8]

        table.add_row(
            str(run.run_id),
            ts,
            run.task_name,
            agents_str,
            winner_str,
            f"{best_score:.1f}",
        )

    console.print(table)

    str_console = Console(file=None, force_terminal=False, width=120)
    with str_console.capture() as capture:
        str_console.print(table)
    return capture.get()


def format_history_markdown(runs: list[RunRecord]) -> str:
    """Render run history as a markdown table."""
    if not runs:
        return "## coderace history\n\n_No runs recorded._\n"

    header = "## coderace history\n\n"
    cols = "| Run ID | Date | Task | Agents | Winner | Best Score |\n"
    sep = "|--------|------|------|--------|--------|----------:|\n"

    rows: list[str] = []
    for run in runs:
        agents_str = ", ".join(a.agent for a in run.agents)
        winners = [a for a in run.agents if a.is_winner]
        winner_str = ", ".join(f"`{w.agent}`" for w in winners) if winners else "-"
        best_score = max((a.composite_score for a in run.agents), default=0.0)

        ts = run.timestamp
        if "T" in ts:
            ts = ts.split("T")[0] + " " + ts.split("T")[1][:8]

        row = f"| {run.run_id} | {ts} | `{run.task_name}` | {agents_str} | {winner_str} | {best_score:.1f} |"
        rows.append(row)

    return header + cols + sep + "\n".join(rows) + "\n"


def format_history_json(runs: list[RunRecord]) -> str:
    """Render run history as JSON."""
    data = {
        "history": [
            {
                "run_id": run.run_id,
                "timestamp": run.timestamp,
                "task_name": run.task_name,
                "agents": [
                    {
                        "agent": a.agent,
                        "composite_score": round(a.composite_score, 2),
                        "is_winner": a.is_winner,
                    }
                    for a in run.agents
                ],
                "winner": next(
                    (a.agent for a in run.agents if a.is_winner), None
                ),
                "best_score": round(
                    max((a.composite_score for a in run.agents), default=0.0), 2
                ),
            }
            for run in runs
        ]
    }
    return json.dumps(data, indent=2) + "\n"
