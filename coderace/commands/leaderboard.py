"""Leaderboard command — aggregate rankings across all runs."""

from __future__ import annotations

import json
import sys

from rich.console import Console
from rich.table import Table

from coderace.store import AgentStat, ResultStore


def format_leaderboard_terminal(stats: list[AgentStat], console: Console | None = None) -> str:
    """Render leaderboard as a Rich terminal table."""
    console = console or Console()

    table = Table(title="coderace leaderboard", show_lines=True)
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("Agent", style="cyan")
    table.add_column("Wins", justify="right")
    table.add_column("Races", justify="right")
    table.add_column("Win%", justify="right", style="bold green")
    table.add_column("Avg Score", justify="right")
    table.add_column("Avg Cost", justify="right")
    table.add_column("Avg Time", justify="right")

    for i, s in enumerate(stats, 1):
        cost_str = f"${s.avg_cost:.4f}" if s.avg_cost is not None else "-"
        table.add_row(
            str(i),
            s.agent,
            str(s.wins),
            str(s.races),
            f"{s.win_rate * 100:.0f}%",
            f"{s.avg_score:.1f}",
            cost_str,
            f"{s.avg_time:.1f}",
        )

    console.print(table)

    str_console = Console(file=None, force_terminal=False, width=100)
    with str_console.capture() as capture:
        str_console.print(table)
    return capture.get()


def format_leaderboard_markdown(stats: list[AgentStat]) -> str:
    """Render leaderboard as a markdown table."""
    if not stats:
        return "## coderace leaderboard\n\n_No data._\n"

    header = "## coderace leaderboard\n\n"
    cols = "| Rank | Agent | Wins | Races | Win% | Avg Score | Avg Cost | Avg Time |\n"
    sep = "|------|-------|-----:|------:|-----:|----------:|---------:|---------:|\n"

    rows: list[str] = []
    for i, s in enumerate(stats, 1):
        cost_str = f"${s.avg_cost:.4f}" if s.avg_cost is not None else "-"
        row = (
            f"| {i} | `{s.agent}` | {s.wins} | {s.races} |"
            f" {s.win_rate * 100:.0f}% | {s.avg_score:.1f} |"
            f" {cost_str} | {s.avg_time:.1f} |"
        )
        rows.append(row)

    return header + cols + sep + "\n".join(rows) + "\n"


def format_leaderboard_json(stats: list[AgentStat]) -> str:
    """Render leaderboard as JSON."""
    data = {
        "leaderboard": [
            {
                "rank": i,
                "agent": s.agent,
                "wins": s.wins,
                "races": s.races,
                "win_rate": round(s.win_rate, 4),
                "avg_score": round(s.avg_score, 2),
                "avg_cost": round(s.avg_cost, 6) if s.avg_cost is not None else None,
                "avg_time": round(s.avg_time, 2),
            }
            for i, s in enumerate(stats, 1)
        ]
    }
    return json.dumps(data, indent=2) + "\n"


def format_leaderboard_html(stats: list[AgentStat]) -> str:
    """Render leaderboard as a standalone HTML page."""
    rows_html = ""
    for i, s in enumerate(stats, 1):
        cost_str = f"${s.avg_cost:.4f}" if s.avg_cost is not None else "-"
        rows_html += (
            f"<tr><td>{i}</td><td>{s.agent}</td><td>{s.wins}</td>"
            f"<td>{s.races}</td><td>{s.win_rate * 100:.0f}%</td>"
            f"<td>{s.avg_score:.1f}</td><td>{cost_str}</td>"
            f"<td>{s.avg_time:.1f}</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html><head><title>coderace leaderboard</title>
<style>
body {{ font-family: monospace; background: #1a1a2e; color: #eee; padding: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #444; padding: 8px; text-align: right; }}
th {{ background: #16213e; }}
tr:nth-child(even) {{ background: #1a1a2e; }}
tr:nth-child(odd) {{ background: #16213e; }}
td:nth-child(2) {{ text-align: left; }}
</style></head>
<body>
<h1>coderace leaderboard</h1>
<table>
<tr><th>Rank</th><th>Agent</th><th>Wins</th><th>Races</th><th>Win%</th><th>Avg Score</th><th>Avg Cost</th><th>Avg Time</th></tr>
{rows_html}</table>
</body></html>
"""
