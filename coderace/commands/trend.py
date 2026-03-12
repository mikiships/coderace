"""Trend command — visualize agent score progression over time."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text

from coderace.store import RunRecord, AgentRecord

# Unicode sparkline characters (low → high)
_SPARK_CHARS = "▁▂▃▄▅▆▇█"
_SPARK_ASCII = "_.-*^"


@dataclass
class TrendPoint:
    """A single data point in a trend series."""

    run_id: int
    timestamp: str
    score: float
    delta: Optional[float]  # None for first point
    is_winner: bool


@dataclass
class AgentTaskTrend:
    """Score trend for an (agent, task) pair."""

    agent: str
    task: str
    points: list[TrendPoint] = field(default_factory=list)

    @property
    def runs(self) -> int:
        return len(self.points)

    @property
    def avg_score(self) -> float:
        if not self.points:
            return 0.0
        return sum(p.score for p in self.points) / len(self.points)

    @property
    def best_score(self) -> float:
        if not self.points:
            return 0.0
        return max(p.score for p in self.points)

    @property
    def latest_score(self) -> float:
        if not self.points:
            return 0.0
        return self.points[-1].score

    @property
    def latest_delta(self) -> Optional[float]:
        if len(self.points) < 2:
            return None
        return self.points[-1].delta

    @property
    def improvement_rate(self) -> Optional[float]:
        """Pct of runs where score improved vs previous run."""
        if len(self.points) < 2:
            return None
        improvements = sum(
            1 for p in self.points[1:] if p.delta is not None and p.delta > 0
        )
        return improvements / (len(self.points) - 1)

    def sparkline(self, use_unicode: bool = True) -> str:
        """Generate a sparkline string for the score series."""
        scores = [p.score for p in self.points]
        if not scores:
            return "—"
        if len(scores) == 1:
            return "—"

        chars = _SPARK_CHARS if use_unicode else _SPARK_ASCII
        n = len(chars)
        lo, hi = min(scores), max(scores)
        span = hi - lo

        result = []
        for s in scores:
            if span == 0:
                idx = n // 2
            else:
                idx = round((s - lo) / span * (n - 1))
            result.append(chars[idx])
        return "".join(result)


def _trend_direction(delta: Optional[float]) -> tuple[str, str]:
    """Return (symbol, rich_style) for a delta value."""
    if delta is None:
        return "—", "dim"
    if delta > 0.05:
        return f"↑ +{delta:.1f}", "green"
    if delta < -0.05:
        return f"↓ {delta:.1f}", "red"
    return f"→ {delta:.1f}", "white"


def _build_trends(
    runs: list[RunRecord],
    agent_filter: Optional[str],
    task_filter: Optional[str],
) -> list[AgentTaskTrend]:
    """Build per-(agent, task) trend objects from run records."""
    # Group: (agent, task) -> list of (timestamp, run_id, score, is_winner)
    groups: dict[tuple[str, str], list[tuple[str, int, float, bool]]] = {}

    for run in runs:
        if task_filter and run.task_name != task_filter:
            continue
        for ar in run.agents:
            if agent_filter and ar.agent != agent_filter:
                continue
            key = (ar.agent, run.task_name)
            groups.setdefault(key, []).append(
                (run.timestamp, run.run_id, ar.composite_score, ar.is_winner)
            )

    trends: list[AgentTaskTrend] = []
    for (agent, task), entries in sorted(groups.items()):
        # Sort chronologically (oldest first) so delta makes sense
        entries.sort(key=lambda x: x[0])
        trend = AgentTaskTrend(agent=agent, task=task)
        prev_score: Optional[float] = None
        for ts, run_id, score, is_winner in entries:
            delta = score - prev_score if prev_score is not None else None
            trend.points.append(
                TrendPoint(
                    run_id=run_id,
                    timestamp=ts,
                    score=score,
                    delta=delta,
                    is_winner=is_winner,
                )
            )
            prev_score = score
        trends.append(trend)

    return trends


def format_trend_terminal(
    trends: list[AgentTaskTrend],
    detail_agent: Optional[str] = None,
    console: Optional[Console] = None,
) -> str:
    """Render trend data as a Rich terminal table."""
    console = console or Console()

    if not trends:
        console.print("[yellow]No trend data found.[/yellow]")
        return ""

    use_unicode = sys.stdout.encoding.lower().startswith(("utf", "us-ascii")) if hasattr(sys.stdout, "encoding") else True

    if detail_agent:
        # Detailed per-task view for a single agent
        table = Table(title=f"coderace trend — {detail_agent}", show_lines=True)
        table.add_column("Run ID", justify="center", style="bold")
        table.add_column("Date", style="dim")
        table.add_column("Task", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Delta", justify="right")
        table.add_column("Result")

        for trend in trends:
            for p in trend.points:
                ts = p.timestamp
                if "T" in ts:
                    ts = ts.split("T")[0] + " " + ts.split("T")[1][:8]

                sym, sty = _trend_direction(p.delta)
                result_str = "win" if p.is_winner else "loss"
                result_style = "green" if p.is_winner else "dim"

                table.add_row(
                    str(p.run_id),
                    ts,
                    trend.task,
                    f"{p.score:.1f}",
                    Text(sym, style=sty),
                    Text(result_str, style=result_style),
                )

        console.print(table)

        # Summary stats
        total_runs = sum(t.runs for t in trends)
        all_scores = [p.score for t in trends for p in t.points]
        avg = sum(all_scores) / len(all_scores) if all_scores else 0.0
        best = max(all_scores) if all_scores else 0.0
        improvement_rates = [t.improvement_rate for t in trends if t.improvement_rate is not None]
        avg_impr = sum(improvement_rates) / len(improvement_rates) if improvement_rates else None

        console.print(f"\n[bold]Summary for {detail_agent}[/bold]")
        console.print(f"  Total runs:       {total_runs}")
        console.print(f"  Avg score:        {avg:.1f}")
        console.print(f"  Best score:       {best:.1f}")
        if avg_impr is not None:
            console.print(f"  Improvement rate: {avg_impr:.0%}")
        else:
            console.print("  Improvement rate: — (need 2+ runs per task)")
    else:
        # Summary table: one row per (agent, task)
        table = Table(title="coderace trend", show_lines=True)
        table.add_column("Agent", style="cyan")
        table.add_column("Task")
        table.add_column("Runs", justify="right")
        table.add_column("Avg Score", justify="right")
        table.add_column("Best Score", justify="right")
        table.add_column("Latest Score", justify="right")
        table.add_column("Trend")

        for trend in trends:
            spark = trend.sparkline(use_unicode=use_unicode)
            sym, sty = _trend_direction(trend.latest_delta)

            if trend.runs < 2:
                trend_cell: str | Text = Text("—", style="dim")
            elif trend.latest_delta is not None and trend.latest_delta > 0.05:
                trend_cell = Text(f"{spark} {sym}", style="green")
            elif trend.latest_delta is not None and trend.latest_delta < -0.05:
                trend_cell = Text(f"{spark} {sym}", style="red")
            else:
                trend_cell = Text(f"{spark} {sym}", style="white")

            table.add_row(
                trend.agent,
                trend.task,
                str(trend.runs),
                f"{trend.avg_score:.1f}",
                f"{trend.best_score:.1f}",
                f"{trend.latest_score:.1f}",
                trend_cell,
            )

        console.print(table)

    str_console = Console(file=None, force_terminal=False, width=120)
    with str_console.capture() as capture:
        str_console.print(table)
    return capture.get()


def format_trend_markdown(
    trends: list[AgentTaskTrend],
    detail_agent: Optional[str] = None,
) -> str:
    """Render trend data as a markdown table."""
    if not trends:
        return "## coderace trend\n\n_No trend data found._\n"

    header = "## coderace trend\n\n"

    if detail_agent:
        cols = "| Run ID | Date | Task | Score | Delta | Result |\n"
        sep = "|--------|------|------|------:|------:|--------|\n"
        rows: list[str] = []
        for trend in trends:
            for p in trend.points:
                ts = p.timestamp
                if "T" in ts:
                    ts = ts.split("T")[0] + " " + ts.split("T")[1][:8]
                delta_str = f"+{p.delta:.1f}" if p.delta is not None and p.delta > 0 else (f"{p.delta:.1f}" if p.delta is not None else "—")
                result_str = "win" if p.is_winner else "loss"
                rows.append(f"| {p.run_id} | {ts} | `{trend.task}` | {p.score:.1f} | {delta_str} | {result_str} |")
        return header + cols + sep + "\n".join(rows) + "\n"
    else:
        cols = "| Agent | Task | Runs | Avg Score | Best Score | Latest Score | Trend |\n"
        sep = "|-------|------|-----:|----------:|-----------:|-------------:|-------|\n"
        rows = []
        for trend in trends:
            delta = trend.latest_delta
            if delta is None:
                trend_str = "—"
            elif delta > 0.05:
                trend_str = f"↑ +{delta:.1f}"
            elif delta < -0.05:
                trend_str = f"↓ {delta:.1f}"
            else:
                trend_str = f"→ {delta:.1f}"
            rows.append(
                f"| {trend.agent} | `{trend.task}` | {trend.runs} | {trend.avg_score:.1f} | {trend.best_score:.1f} | {trend.latest_score:.1f} | {trend_str} |"
            )
        return header + cols + sep + "\n".join(rows) + "\n"


def format_trend_json(trends: list[AgentTaskTrend]) -> str:
    """Render trend data as JSON."""
    data = {
        "trends": [
            {
                "agent": t.agent,
                "task": t.task,
                "runs": [
                    {
                        "run_id": p.run_id,
                        "timestamp": p.timestamp,
                        "score": round(p.score, 2),
                        "delta": round(p.delta, 2) if p.delta is not None else None,
                        "is_winner": p.is_winner,
                    }
                    for p in t.points
                ],
                "summary": {
                    "total_runs": t.runs,
                    "avg_score": round(t.avg_score, 2),
                    "best_score": round(t.best_score, 2),
                    "latest_score": round(t.latest_score, 2),
                    "trend_pct": round(t.improvement_rate * 100, 1) if t.improvement_rate is not None else None,
                },
            }
            for t in trends
        ]
    }
    return json.dumps(data, indent=2) + "\n"
