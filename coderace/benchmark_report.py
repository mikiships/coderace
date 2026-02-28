"""Benchmark report rendering: terminal, markdown, and HTML."""

from __future__ import annotations

import html as _html_mod
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console
from rich.table import Table

from coderace.benchmark import BenchmarkResult
from coderace.benchmark_stats import BenchmarkStats
from coderace.statistics import compute_aggregate_stats, compute_trial_stats


def _has_verification(result: BenchmarkResult) -> bool:
    return any(r.verify_applicable for r in result.results)


def _task_verify_percentage(
    result: BenchmarkResult,
    task_name: str,
    lookup: dict[tuple[str, str], object],
) -> str:
    applicable = 0
    passed = 0
    for agent in result.agents:
        entry = lookup.get((task_name, agent))
        if not entry or not entry.verify_applicable:
            continue
        applicable += 1
        if entry.verify_passed:
            passed += 1
    if applicable == 0:
        return "-"
    pct = int(round(passed / applicable * 100))
    return f"{pct}%"


def _truncate_output(output: str, max_lines: int = 20) -> str:
    if not output:
        return ""
    lines = output.splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    hidden = len(lines) - max_lines
    return "\n".join(lines[:max_lines] + [f"... (+{hidden} more lines)"])


def _verify_details_rows(
    result: BenchmarkResult,
    lookup: dict[tuple[str, str], object],
) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for task_name in result.tasks:
        for agent in result.agents:
            entry = lookup.get((task_name, agent))
            if not entry or not entry.verify_applicable:
                continue
            verify_pct = f"{int(round(entry.verify_score))}%"
            rows.append(
                (
                    task_name,
                    agent,
                    verify_pct,
                    _truncate_output(entry.verify_output),
                )
            )
    return rows


def _is_multi_trial(result: BenchmarkResult) -> bool:
    if result.trials > 1:
        return True
    seen: set[tuple[str, str]] = set()
    for row in result.results:
        key = (row.task_name, row.agent)
        if key in seen:
            return True
        seen.add(key)
    return False


def _task_reliability(result: BenchmarkResult, task_name: str) -> float:
    task_rows = [row for row in result.results if row.task_name == task_name]
    if not task_rows:
        return 0.0
    ok = sum(1 for row in task_rows if not row.timed_out and not row.error)
    return ok / len(task_rows)


def _render_elo_terminal(console: Console, elo_ratings: dict[str, float]) -> None:
    if not elo_ratings:
        return
    table = Table(title="ELO Ratings", show_lines=True, expand=False)
    table.add_column("Rank", justify="right")
    table.add_column("Agent", style="cyan")
    table.add_column("Rating", justify="right")
    for idx, (agent, rating) in enumerate(
        sorted(elo_ratings.items(), key=lambda item: item[1], reverse=True),
        start=1,
    ):
        table.add_row(str(idx), agent, f"{rating:.1f}")
    console.print()
    console.print(table)


def _render_elo_markdown(elo_ratings: dict[str, float]) -> str:
    if not elo_ratings:
        return ""
    lines = ["## ELO Ratings", "", "| Rank | Agent | Rating |", "|------|-------|--------|"]
    for idx, (agent, rating) in enumerate(
        sorted(elo_ratings.items(), key=lambda item: item[1], reverse=True),
        start=1,
    ):
        lines.append(f"| {idx} | {agent} | {rating:.1f} |")
    lines.append("")
    return "\n".join(lines)


def _render_elo_html(elo_ratings: dict[str, float]) -> str:
    if not elo_ratings:
        return ""
    rows = []
    for idx, (agent, rating) in enumerate(
        sorted(elo_ratings.items(), key=lambda item: item[1], reverse=True),
        start=1,
    ):
        rows.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{_html_mod.escape(agent)}</td>"
            f"<td>{rating:.1f}</td>"
            "</tr>"
        )
    rows_html = "\n".join(rows)
    return f"""
<h2>ELO Ratings</h2>
<table>
<thead><tr><th>Rank</th><th>Agent</th><th>Rating</th></tr></thead>
<tbody>
{rows_html}
</tbody>
</table>
"""


def _render_benchmark_terminal_trials(
    result: BenchmarkResult,
    console: Console,
    elo_ratings: dict[str, float] | None = None,
) -> None:
    trial_stats = compute_trial_stats(result)
    aggregate_stats = compute_aggregate_stats(result, trial_stats=trial_stats)
    trial_lookup = {(row.task_name, row.agent): row for row in trial_stats}
    aggregate_lookup = {row.agent: row for row in aggregate_stats}

    table = Table(title="coderace benchmark (statistical)", show_lines=True, expand=False)
    table.add_column("Task", style="bold")
    for agent in result.agents:
        table.add_column(agent, justify="center")
    table.add_column("CI (95%)", justify="center")
    table.add_column("Consistency", justify="center")
    table.add_column("Reliability", justify="center")

    for task_name in result.tasks:
        row_values = [task_name]
        task_stat_rows = []
        for agent in result.agents:
            stat = trial_lookup.get((task_name, agent))
            if stat is None:
                row_values.append("-")
                continue
            task_stat_rows.append(stat)
            row_values.append(
                f"[green]{stat.mean_score:.1f}+/-{stat.stddev_score:.1f}[/green] "
                f"[dim]({stat.mean_wall_time:.0f}s)[/dim]"
            )
        if task_stat_rows:
            best = max(task_stat_rows, key=lambda r: r.mean_score)
            ci_text = f"{best.ci_95[0]:.1f}..{best.ci_95[1]:.1f}"
            consistency = sum(r.consistency_score for r in task_stat_rows) / len(task_stat_rows)
        else:
            ci_text = "-"
            consistency = 0.0
        reliability = _task_reliability(result, task_name)
        row_values.extend(
            [
                ci_text,
                f"{int(round(consistency * 100))}%",
                f"{int(round(reliability * 100))}%",
            ]
        )
        table.add_row(*row_values)

    mean_row = ["[bold]Mean Score[/bold]"]
    for agent in result.agents:
        agg = aggregate_lookup.get(agent)
        mean_row.append(f"[bold]{agg.mean_score:.1f}[/bold]" if agg else "-")
    mean_row.extend(["-", "-", "-"])
    table.add_row(*mean_row)

    ci_row = ["[bold]CI (95%)[/bold]"]
    for agent in result.agents:
        agg = aggregate_lookup.get(agent)
        if agg:
            ci_row.append(f"{agg.score_ci_95[0]:.1f}..{agg.score_ci_95[1]:.1f}")
        else:
            ci_row.append("-")
    ci_row.extend(["-", "-", "-"])
    table.add_row(*ci_row)

    win_row = ["[bold]Win Rate[/bold]"]
    for agent in result.agents:
        agg = aggregate_lookup.get(agent)
        win_row.append(f"{int(round((agg.win_rate if agg else 0.0) * 100))}%")
    win_row.extend(["-", "-", "-"])
    table.add_row(*win_row)

    rel_row = ["[bold]Reliability[/bold]"]
    for agent in result.agents:
        agg = aggregate_lookup.get(agent)
        rel_row.append(f"{int(round((agg.reliability if agg else 0.0) * 100))}%")
    rel_row.extend(["-", "-", "-"])
    table.add_row(*rel_row)

    console.print(table)

    if aggregate_stats:
        winner = aggregate_stats[0]
        console.print(
            f"\n[bold green]Winner: {winner.agent}[/bold green] "
            f"(mean score: {winner.mean_score:.1f})"
        )

    _render_elo_terminal(console, elo_ratings or {})


def _render_benchmark_markdown_trials(
    result: BenchmarkResult,
    elo_ratings: dict[str, float] | None = None,
) -> str:
    trial_stats = compute_trial_stats(result)
    aggregate_stats = compute_aggregate_stats(result, trial_stats=trial_stats)
    trial_lookup = {(row.task_name, row.agent): row for row in trial_stats}
    aggregate_lookup = {row.agent: row for row in aggregate_stats}

    lines: list[str] = []
    lines.append("# coderace Benchmark Results\n")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")
    lines.append(f"Benchmark ID: `{result.benchmark_id}`\n")
    lines.append("")

    headers = ["Task", *result.agents, "CI (95%)", "Consistency", "Reliability"]
    separator = "|" + "|".join(["------"] * len(headers)) + "|"
    lines.append("| " + " | ".join(headers) + " |")
    lines.append(separator)

    for task_name in result.tasks:
        cells = [task_name]
        task_rows = []
        for agent in result.agents:
            stat = trial_lookup.get((task_name, agent))
            if stat is None:
                cells.append("-")
                continue
            task_rows.append(stat)
            cells.append(f"{stat.mean_score:.1f}+/-{stat.stddev_score:.1f} ({stat.mean_wall_time:.0f}s)")
        if task_rows:
            best = max(task_rows, key=lambda r: r.mean_score)
            ci_text = f"{best.ci_95[0]:.1f}..{best.ci_95[1]:.1f}"
            consistency = sum(r.consistency_score for r in task_rows) / len(task_rows)
        else:
            ci_text = "-"
            consistency = 0.0
        reliability = _task_reliability(result, task_name)
        cells.append(ci_text)
        cells.append(f"{int(round(consistency * 100))}%")
        cells.append(f"{int(round(reliability * 100))}%")
        lines.append("| " + " | ".join(cells) + " |")

    lines.append(separator)

    mean_cells = ["**Mean Score**"]
    for agent in result.agents:
        agg = aggregate_lookup.get(agent)
        mean_cells.append(f"**{agg.mean_score:.1f}**" if agg else "-")
    mean_cells.extend(["-", "-", "-"])
    lines.append("| " + " | ".join(mean_cells) + " |")

    ci_cells = ["**CI (95%)**"]
    for agent in result.agents:
        agg = aggregate_lookup.get(agent)
        ci_cells.append(f"{agg.score_ci_95[0]:.1f}..{agg.score_ci_95[1]:.1f}" if agg else "-")
    ci_cells.extend(["-", "-", "-"])
    lines.append("| " + " | ".join(ci_cells) + " |")

    win_cells = ["**Win Rate**"]
    for agent in result.agents:
        agg = aggregate_lookup.get(agent)
        win_cells.append(f"{int(round((agg.win_rate if agg else 0.0) * 100))}%")
    win_cells.extend(["-", "-", "-"])
    lines.append("| " + " | ".join(win_cells) + " |")

    rel_cells = ["**Reliability**"]
    for agent in result.agents:
        agg = aggregate_lookup.get(agent)
        rel_cells.append(f"{int(round((agg.reliability if agg else 0.0) * 100))}%")
    rel_cells.extend(["-", "-", "-"])
    lines.append("| " + " | ".join(rel_cells) + " |")

    lines.append("")
    elo_section = _render_elo_markdown(elo_ratings or {})
    if elo_section:
        lines.append(elo_section)
    return "\n".join(lines)


def _render_benchmark_html_trials(
    result: BenchmarkResult,
    elo_ratings: dict[str, float] | None = None,
) -> str:
    trial_stats = compute_trial_stats(result)
    aggregate_stats = compute_aggregate_stats(result, trial_stats=trial_stats)
    trial_lookup = {(row.task_name, row.agent): row for row in trial_stats}
    aggregate_lookup = {row.agent: row for row in aggregate_stats}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def esc(s: str) -> str:
        return _html_mod.escape(str(s))

    task_rows = ""
    for task_name in result.tasks:
        task_rows += f"<tr><td class='task'>{esc(task_name)}</td>"
        task_stats = []
        for agent in result.agents:
            stat = trial_lookup.get((task_name, agent))
            if stat is None:
                task_rows += "<td>-</td>"
            else:
                task_stats.append(stat)
                task_rows += (
                    f"<td class='pass'>{stat.mean_score:.1f}+/-{stat.stddev_score:.1f}"
                    f"<br><small>({stat.mean_wall_time:.0f}s)</small></td>"
                )
        if task_stats:
            best = max(task_stats, key=lambda row: row.mean_score)
            ci_text = f"{best.ci_95[0]:.1f}..{best.ci_95[1]:.1f}"
            consistency = sum(row.consistency_score for row in task_stats) / len(task_stats)
        else:
            ci_text = "-"
            consistency = 0.0
        reliability = _task_reliability(result, task_name)
        task_rows += f"<td>{esc(ci_text)}</td>"
        task_rows += f"<td>{int(round(consistency * 100))}%</td>"
        task_rows += f"<td>{int(round(reliability * 100))}%</td>"
        task_rows += "</tr>\n"

    mean_cells = ""
    ci_cells = ""
    win_cells = ""
    rel_cells = ""
    for agent in result.agents:
        agg = aggregate_lookup.get(agent)
        if agg:
            mean_cells += f"<td><strong>{agg.mean_score:.1f}</strong></td>"
            ci_cells += f"<td>{agg.score_ci_95[0]:.1f}..{agg.score_ci_95[1]:.1f}</td>"
            win_cells += f"<td>{int(round(agg.win_rate * 100))}%</td>"
            rel_cells += f"<td>{int(round(agg.reliability * 100))}%</td>"
        else:
            mean_cells += "<td>-</td>"
            ci_cells += "<td>-</td>"
            win_cells += "<td>-</td>"
            rel_cells += "<td>-</td>"
    winner = aggregate_stats[0].agent if aggregate_stats else "-"
    agent_headers = "".join(f"<th>{esc(agent)}</th>" for agent in result.agents)
    elo_section = _render_elo_html(elo_ratings or {})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>coderace Benchmark — {esc(result.benchmark_id)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 2rem; }}
  h1, h2 {{ color: #58a6ff; }}
  .meta {{ color: #8b949e; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  .winner {{ background: #1f6feb33; border: 1px solid #1f6feb; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
  th {{ background: #161b22; color: #58a6ff; padding: 0.6rem 1rem; border: 1px solid #30363d; }}
  td {{ padding: 0.5rem 1rem; border: 1px solid #30363d; text-align: center; }}
  td.task {{ text-align: left; font-weight: 500; color: #e6edf3; }}
  td.pass {{ color: #3fb950; }}
  tr.summary td {{ background: #161b22; font-weight: bold; color: #e6edf3; }}
  small {{ color: #8b949e; }}
</style>
</head>
<body>
<h1>coderace Benchmark (Statistical)</h1>
<div class="meta">
  ID: {esc(result.benchmark_id)} &nbsp;|&nbsp; Generated: {now}
</div>
<div class="winner">
  <strong>Winner:</strong> {esc(winner)}
</div>
<h2>Results</h2>
<table>
<thead><tr><th>Task</th>{agent_headers}<th>CI (95%)</th><th>Consistency</th><th>Reliability</th></tr></thead>
<tbody>
{task_rows}
<tr class="summary"><td>Mean Score</td>{mean_cells}<td>-</td><td>-</td><td>-</td></tr>
<tr class="summary"><td>CI (95%)</td>{ci_cells}<td>-</td><td>-</td><td>-</td></tr>
<tr class="summary"><td>Win Rate</td>{win_cells}<td>-</td><td>-</td><td>-</td></tr>
<tr class="summary"><td>Reliability</td>{rel_cells}<td>-</td><td>-</td><td>-</td></tr>
</tbody>
</table>
{elo_section}
</body>
</html>
"""


def render_benchmark_terminal(
    result: BenchmarkResult,
    stats: BenchmarkStats,
    console: Optional[Console] = None,
    elo_ratings: dict[str, float] | None = None,
) -> None:
    """Render a Rich terminal table for the benchmark results."""
    console = console or Console()
    if _is_multi_trial(result):
        _render_benchmark_terminal_trials(result, console, elo_ratings=elo_ratings)
        return

    agents = result.agents
    tasks = result.tasks
    has_verify = _has_verification(result)

    # Lookup: (task, agent) -> TaskAgentResult
    lookup = {(r.task_name, r.agent): r for r in result.results}

    # Build table: tasks as rows, agents as columns
    table = Table(title="coderace benchmark", show_lines=True, expand=False)
    table.add_column("Task", style="bold")
    for agent in agents:
        table.add_column(agent, justify="center")
    if has_verify:
        table.add_column("Verify", justify="center")

    for task_name in tasks:
        row = [task_name]
        for agent in agents:
            r = lookup.get((task_name, agent))
            if r is None:
                row.append("-")
            elif r.error:
                row.append("[red]ERR[/red]")
            elif r.timed_out:
                row.append(f"[yellow]TIMEOUT[/yellow]")
            else:
                score_str = f"{r.score:.1f}"
                time_str = f"({r.wall_time:.0f}s)"
                row.append(f"[green]{score_str}[/green] [dim]{time_str}[/dim]")
        if has_verify:
            row.append(_task_verify_percentage(result, task_name, lookup))
        table.add_row(*row)

    # Summary rows
    agent_stat_map = {s.agent: s for s in stats.agent_stats}

    # Total score row
    total_row = ["[bold]TOTAL[/bold]"]
    for agent in agents:
        s = agent_stat_map.get(agent)
        total_row.append(f"[bold]{s.total_score:.1f}[/bold]" if s else "-")
    if has_verify:
        total_row.append("-")
    table.add_row(*total_row)

    # Win rate row
    win_row = ["[bold]Win Rate[/bold]"]
    for agent in agents:
        s = agent_stat_map.get(agent)
        if s and s.task_count > 0:
            pct = int(s.win_count / s.task_count * 100)
            win_row.append(f"{pct}%")
        else:
            win_row.append("-")
    if has_verify:
        win_row.append("-")
    table.add_row(*win_row)

    # Avg time row
    time_row = ["[bold]Avg Time[/bold]"]
    for agent in agents:
        s = agent_stat_map.get(agent)
        time_row.append(f"{s.avg_time:.1f}s" if s else "-")
    if has_verify:
        time_row.append("-")
    table.add_row(*time_row)

    # Total cost row
    cost_row = ["[bold]Total Cost[/bold]"]
    for agent in agents:
        s = agent_stat_map.get(agent)
        if s and s.total_cost is not None:
            cost_row.append(f"${s.total_cost:.4f}")
        else:
            cost_row.append("-")
    if has_verify:
        cost_row.append("-")
    table.add_row(*cost_row)

    console.print(table)

    # Winner callout
    if stats.agent_stats:
        winner = stats.agent_stats[0]
        console.print(f"\n[bold green]Winner: {winner.agent}[/bold green] "
                      f"(total score: {winner.total_score:.1f}, "
                      f"{winner.win_count}/{winner.task_count} task wins)")

    if has_verify:
        details = _verify_details_rows(result, lookup)
        if details:
            verify_table = Table(title="verification details", show_lines=True, expand=False)
            verify_table.add_column("Task", style="bold")
            verify_table.add_column("Agent", style="cyan")
            verify_table.add_column("Verify", justify="center")
            verify_table.add_column("Output")
            for task_name, agent, verify_pct, output in details:
                verify_table.add_row(task_name, agent, verify_pct, output or "-")
            console.print()
            console.print(verify_table)

    _render_elo_terminal(console, elo_ratings or {})


def render_benchmark_markdown(
    result: BenchmarkResult,
    stats: BenchmarkStats,
    elo_ratings: dict[str, float] | None = None,
) -> str:
    """Render a GitHub-flavored markdown table for the benchmark results."""
    if _is_multi_trial(result):
        return _render_benchmark_markdown_trials(result, elo_ratings=elo_ratings)
    agents = result.agents
    tasks = result.tasks
    lookup = {(r.task_name, r.agent): r for r in result.results}
    agent_stat_map = {s.agent: s for s in stats.agent_stats}
    has_verify = _has_verification(result)

    lines: list[str] = []
    lines.append("# coderace Benchmark Results\n")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")
    lines.append(f"Benchmark ID: `{result.benchmark_id}`\n")

    # Header row
    header_cells = ["Task", *agents]
    if has_verify:
        header_cells.append("Verify")
    header = "| " + " | ".join(header_cells) + " |"
    separator = "|" + "|".join(["------"] * len(header_cells)) + "|"
    lines.append(header)
    lines.append(separator)

    for task_name in tasks:
        cells = [task_name]
        for agent in agents:
            r = lookup.get((task_name, agent))
            if r is None:
                cells.append("-")
            elif r.error:
                cells.append("ERR")
            elif r.timed_out:
                cells.append("TIMEOUT")
            else:
                cells.append(f"{r.score:.1f} ({r.wall_time:.0f}s)")
        if has_verify:
            cells.append(_task_verify_percentage(result, task_name, lookup))
        lines.append("| " + " | ".join(cells) + " |")

    # Summary separator
    lines.append(separator)

    # Total
    total_cells = ["**TOTAL**"]
    for agent in agents:
        s = agent_stat_map.get(agent)
        total_cells.append(f"**{s.total_score:.1f}**" if s else "-")
    if has_verify:
        total_cells.append("-")
    lines.append("| " + " | ".join(total_cells) + " |")

    # Win rate
    win_cells = ["**Win Rate**"]
    for agent in agents:
        s = agent_stat_map.get(agent)
        if s and s.task_count > 0:
            pct = int(s.win_count / s.task_count * 100)
            win_cells.append(f"{pct}%")
        else:
            win_cells.append("-")
    if has_verify:
        win_cells.append("-")
    lines.append("| " + " | ".join(win_cells) + " |")

    # Avg time
    time_cells = ["**Avg Time**"]
    for agent in agents:
        s = agent_stat_map.get(agent)
        time_cells.append(f"{s.avg_time:.1f}s" if s else "-")
    if has_verify:
        time_cells.append("-")
    lines.append("| " + " | ".join(time_cells) + " |")

    # Total cost
    cost_cells = ["**Total Cost**"]
    for agent in agents:
        s = agent_stat_map.get(agent)
        if s and s.total_cost is not None:
            cost_cells.append(f"${s.total_cost:.4f}")
        else:
            cost_cells.append("-")
    if has_verify:
        cost_cells.append("-")
    lines.append("| " + " | ".join(cost_cells) + " |")

    lines.append("")

    # Task insights
    if stats.task_stats:
        lines.append("## Task Insights\n")
        lines.append("| Task | Best Agent | Best Score | Avg Score | Fastest Agent |")
        lines.append("|------|-----------|-----------|----------|--------------|")
        for ts in stats.task_stats:
            fastest = f"{ts.fastest_agent} ({ts.fastest_time:.0f}s)" if ts.fastest_agent else "-"
            lines.append(
                f"| {ts.task_name} | {ts.best_agent or '-'} | "
                f"{ts.best_score:.1f} | {ts.avg_score:.1f} | {fastest} |"
            )
        lines.append("")

    if has_verify:
        details = _verify_details_rows(result, lookup)
        if details:
            lines.append("## Verification Details\n")
            lines.append("| Task | Agent | Verify | Output |")
            lines.append("|------|-------|--------|--------|")
            for task_name, agent, verify_pct, output in details:
                safe_output = (output or "-").replace("|", "\\|").replace("\n", "<br>")
                lines.append(
                    f"| {task_name} | {agent} | {verify_pct} | {safe_output} |"
                )
            lines.append("")

    elo_section = _render_elo_markdown(elo_ratings or {})
    if elo_section:
        lines.append(elo_section)

    return "\n".join(lines)


def render_benchmark_html(
    result: BenchmarkResult,
    stats: BenchmarkStats,
    elo_ratings: dict[str, float] | None = None,
) -> str:
    """Render a self-contained HTML report for the benchmark results."""
    if _is_multi_trial(result):
        return _render_benchmark_html_trials(result, elo_ratings=elo_ratings)
    agents = result.agents
    tasks = result.tasks
    lookup = {(r.task_name, r.agent): r for r in result.results}
    agent_stat_map = {s.agent: s for s in stats.agent_stats}
    has_verify = _has_verification(result)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def esc(s: str) -> str:
        return _html_mod.escape(str(s))

    # Build task rows
    task_rows = ""
    for task_name in tasks:
        task_rows += f"<tr><td class='task'>{esc(task_name)}</td>"
        for agent in agents:
            r = lookup.get((task_name, agent))
            if r is None:
                task_rows += "<td>-</td>"
            elif r.error:
                task_rows += "<td class='fail'>ERR</td>"
            elif r.timed_out:
                task_rows += "<td class='warn'>TIMEOUT</td>"
            else:
                cls = "pass" if r.score >= 50 else "fail"
                task_rows += f"<td class='{cls}'>{r.score:.1f}<br><small>({r.wall_time:.0f}s)</small></td>"
        if has_verify:
            verify = _task_verify_percentage(result, task_name, lookup)
            verify_cls = "pass" if verify == "100%" else ("fail" if verify == "0%" else "")
            task_rows += f"<td class='{verify_cls}'>{esc(verify)}</td>"
        task_rows += "</tr>\n"

    # Summary rows
    total_cells = ""
    for agent in agents:
        s = agent_stat_map.get(agent)
        total_cells += f"<td><strong>{s.total_score:.1f}</strong></td>" if s else "<td>-</td>"

    win_cells = ""
    for agent in agents:
        s = agent_stat_map.get(agent)
        if s and s.task_count > 0:
            pct = int(s.win_count / s.task_count * 100)
            win_cells += f"<td>{pct}%</td>"
        else:
            win_cells += "<td>-</td>"

    time_cells = ""
    for agent in agents:
        s = agent_stat_map.get(agent)
        time_cells += f"<td>{s.avg_time:.1f}s</td>" if s else "<td>-</td>"

    cost_cells = ""
    for agent in agents:
        s = agent_stat_map.get(agent)
        if s and s.total_cost is not None:
            cost_cells += f"<td>${s.total_cost:.4f}</td>"
        else:
            cost_cells += "<td>-</td>"

    summary_verify_cell = "<td>-</td>" if has_verify else ""

    agent_headers = "".join(f"<th>{esc(a)}</th>" for a in agents)
    verify_header = "<th>Verify</th>" if has_verify else ""
    winner = stats.agent_stats[0].agent if stats.agent_stats else "-"

    verify_details_section = ""
    if has_verify:
        detail_rows = ""
        for task_name, agent, verify_pct, output in _verify_details_rows(result, lookup):
            css = "pass" if verify_pct == "100%" else ("fail" if verify_pct == "0%" else "")
            formatted_output = esc(output or "-").replace("\n", "<br>")
            detail_rows += (
                f"<tr><td class='task'>{esc(task_name)}</td><td>{esc(agent)}</td>"
                f"<td class='{css}'>{esc(verify_pct)}</td><td><code>{formatted_output}</code></td></tr>\n"
            )
        if detail_rows:
            verify_details_section = f"""
<h2>Verification Details</h2>
<table>
<thead><tr><th>Task</th><th>Agent</th><th>Verify</th><th>Output</th></tr></thead>
<tbody>
{detail_rows}
</tbody>
</table>
"""

    elo_section = _render_elo_html(elo_ratings or {})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>coderace Benchmark — {esc(result.benchmark_id)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 2rem; }}
  h1, h2 {{ color: #58a6ff; }}
  .meta {{ color: #8b949e; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  .winner {{ background: #1f6feb33; border: 1px solid #1f6feb; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
  th {{ background: #161b22; color: #58a6ff; padding: 0.6rem 1rem; border: 1px solid #30363d; }}
  td {{ padding: 0.5rem 1rem; border: 1px solid #30363d; text-align: center; }}
  td.task {{ text-align: left; font-weight: 500; color: #e6edf3; }}
  td.pass {{ color: #3fb950; }}
  td.fail {{ color: #f85149; }}
  td.warn {{ color: #d29922; }}
  tr.summary td {{ background: #161b22; font-weight: bold; color: #e6edf3; }}
  small {{ color: #8b949e; }}
</style>
</head>
<body>
<h1>coderace Benchmark</h1>
<div class="meta">
  ID: {esc(result.benchmark_id)} &nbsp;|&nbsp; Generated: {now}
</div>
<div class="winner">
  <strong>Winner:</strong> {esc(winner)}
</div>
<h2>Results</h2>
<table>
<thead><tr><th>Task</th>{agent_headers}{verify_header}</tr></thead>
<tbody>
{task_rows}
<tr class="summary"><td>TOTAL</td>{total_cells}{summary_verify_cell}</tr>
<tr class="summary"><td>Win Rate</td>{win_cells}{summary_verify_cell}</tr>
<tr class="summary"><td>Avg Time</td>{time_cells}{summary_verify_cell}</tr>
<tr class="summary"><td>Total Cost</td>{cost_cells}{summary_verify_cell}</tr>
</tbody>
</table>
{verify_details_section}
{elo_section}
</body>
</html>
"""
