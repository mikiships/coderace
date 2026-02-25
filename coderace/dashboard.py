"""Dashboard HTML generator for coderace results."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Optional

from coderace.store import AgentStat, ResultStore, RunRecord


def generate_dashboard(
    store: ResultStore,
    *,
    task_name: str | None = None,
    limit: int | None = None,
    title: str = "coderace Leaderboard",
) -> str:
    """Generate a self-contained HTML dashboard from the result store.

    Args:
        store: ResultStore instance to read data from.
        task_name: Filter to a specific task.
        limit: Only include the last N races.
        title: Custom title for the dashboard.

    Returns:
        Complete HTML string for the dashboard.
    """
    stats = store.get_agent_stats(task_name=task_name)
    runs = store.get_runs(task_name=task_name, limit=limit or 50)

    if not stats and not runs:
        return _generate_empty_dashboard(title)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    safe_title = html.escape(title)

    leaderboard_html = _build_leaderboard_table(stats)
    history_html = _build_race_history(runs)
    agent_cards_html = _build_agent_cards(stats, runs)
    cost_chart_html = _build_cost_chart(stats)

    return _assemble_page(
        title=safe_title,
        timestamp=now,
        leaderboard=leaderboard_html,
        history=history_html,
        agent_cards=agent_cards_html,
        cost_chart=cost_chart_html,
    )


def _generate_empty_dashboard(title: str) -> str:
    """Generate a dashboard page when no data exists."""
    safe_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
{_get_css()}
</head>
<body data-theme="dark">
<div class="container">
  <header class="hero">
    <h1>{safe_title}</h1>
    <p class="subtitle">No races yet</p>
  </header>
  <section class="empty-state">
    <p>No race data found. Run your first race to see results here.</p>
    <pre><code>coderace run task.yaml</code></pre>
    <p>Then generate the dashboard:</p>
    <pre><code>coderace dashboard</code></pre>
  </section>
</div>
{_get_theme_toggle_js()}
</body>
</html>"""


def _build_leaderboard_table(stats: list[AgentStat]) -> str:
    """Build the aggregate leaderboard table HTML."""
    if not stats:
        return ""

    rows = ""
    for i, s in enumerate(stats, 1):
        cost_str = f"${s.avg_cost:.4f}" if s.avg_cost is not None else "-"
        win_rate = f"{s.win_rate * 100:.0f}%"
        rows += (
            f'<tr><td class="rank">{i}</td>'
            f'<td class="agent">{html.escape(s.agent)}</td>'
            f'<td class="num">{s.wins}</td>'
            f'<td class="num">{s.avg_score:.1f}</td>'
            f'<td class="num">{s.avg_time:.1f}s</td>'
            f'<td class="num">{win_rate}</td>'
            f'<td class="num">{cost_str}</td></tr>\n'
        )

    return f"""<section class="section">
  <h2>Aggregate Leaderboard</h2>
  <div class="table-wrap">
  <table>
    <thead><tr>
      <th>Rank</th><th>Agent</th><th>Wins</th><th>Avg Score</th>
      <th>Avg Time</th><th>Win Rate</th><th>Avg Cost</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</section>"""


def _build_race_history(runs: list[RunRecord]) -> str:
    """Build the race history section HTML."""
    if not runs:
        return ""

    rows = ""
    for run in runs:
        ts = run.timestamp
        if "T" in ts:
            ts = ts.split("T")[0] + " " + ts.split("T")[1][:8]

        winners = [a for a in run.agents if a.is_winner]
        winner_str = ", ".join(html.escape(w.agent) for w in winners) if winners else "-"
        agent_count = len(run.agents)

        # Build expandable detail rows
        detail_rows = ""
        for a in run.agents:
            winner_badge = ' <span class="badge">W</span>' if a.is_winner else ""
            cost_str = f"${a.cost_usd:.4f}" if a.cost_usd is not None else "-"
            detail_rows += (
                f'<tr class="detail-row" data-run="{run.run_id}">'
                f"<td></td>"
                f'<td class="agent">{html.escape(a.agent)}{winner_badge}</td>'
                f'<td class="num">{a.composite_score:.1f}</td>'
                f'<td class="num">{a.wall_time:.1f}s</td>'
                f'<td class="num">{cost_str}</td></tr>\n'
            )

        rows += (
            f'<tr class="run-row" data-run="{run.run_id}" onclick="toggleRun({run.run_id})">'
            f"<td>{ts}</td>"
            f'<td class="agent">{html.escape(run.task_name)}</td>'
            f"<td>{winner_str}</td>"
            f'<td class="num">{agent_count}</td></tr>\n'
            f"{detail_rows}"
        )

    return f"""<section class="section">
  <h2>Race History</h2>
  <div class="table-wrap">
  <table>
    <thead><tr>
      <th>Date</th><th>Task</th><th>Winner</th><th>Agents</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</section>"""


def _build_agent_cards(stats: list[AgentStat], runs: list[RunRecord]) -> str:
    """Build per-agent performance cards."""
    if not stats:
        return ""

    # Compute best score per agent from runs
    best_scores: dict[str, float] = {}
    for run in runs:
        for a in run.agents:
            if a.agent not in best_scores or a.composite_score > best_scores[a.agent]:
                best_scores[a.agent] = a.composite_score

    cards = ""
    for s in stats:
        cost_str = f"${s.avg_cost:.4f}" if s.avg_cost is not None else "-"
        best = best_scores.get(s.agent, 0.0)
        cards += f"""<div class="card">
  <h3>{html.escape(s.agent)}</h3>
  <div class="card-stats">
    <div class="stat"><span class="stat-val">{s.races}</span><span class="stat-label">Races</span></div>
    <div class="stat"><span class="stat-val">{s.wins}</span><span class="stat-label">Wins</span></div>
    <div class="stat"><span class="stat-val">{s.avg_score:.1f}</span><span class="stat-label">Avg Score</span></div>
    <div class="stat"><span class="stat-val">{best:.1f}</span><span class="stat-label">Best Score</span></div>
    <div class="stat"><span class="stat-val">{cost_str}</span><span class="stat-label">Avg Cost</span></div>
  </div>
</div>
"""

    return f"""<section class="section">
  <h2>Agent Performance</h2>
  <div class="card-grid">{cards}</div>
</section>"""


def _build_cost_chart(stats: list[AgentStat]) -> str:
    """Build a CSS-only bar chart showing cost-per-point for each agent."""
    # Filter to agents that have cost data and positive avg_score
    entries: list[tuple[str, float]] = []
    for s in stats:
        if s.avg_cost is not None and s.avg_cost > 0 and s.avg_score > 0:
            cpp = s.avg_cost / s.avg_score
            entries.append((s.agent, cpp))

    if not entries:
        return ""

    max_cpp = max(cpp for _, cpp in entries)

    bars = ""
    for agent, cpp in entries:
        pct = (cpp / max_cpp * 100) if max_cpp > 0 else 0
        bars += (
            f'<div class="bar-row">'
            f'<span class="bar-label">{html.escape(agent)}</span>'
            f'<div class="bar-track">'
            f'<div class="bar-fill" style="width:{pct:.1f}%"></div>'
            f"</div>"
            f'<span class="bar-value">${cpp:.5f}/pt</span>'
            f"</div>\n"
        )

    return f"""<section class="section">
  <h2>Cost Efficiency</h2>
  <p class="chart-note">Cost per point (lower is better)</p>
  <div class="bar-chart">{bars}</div>
</section>"""


def _get_css() -> str:
    """Return the inline CSS for the dashboard."""
    return """<style>
:root {
  --bg: #0a0a0f;
  --bg-card: #13131a;
  --bg-table: #13131a;
  --bg-hover: #1a1a24;
  --border: #23232f;
  --text: #e8e8ed;
  --text-muted: #8888a0;
  --accent: #6366f1;
  --accent-dim: #4f46e5;
  --green: #22c55e;
  --bar-fill: #6366f1;
  --radius: 8px;
}
[data-theme="light"] {
  --bg: #fafafa;
  --bg-card: #ffffff;
  --bg-table: #ffffff;
  --bg-hover: #f4f4f5;
  --border: #e4e4e7;
  --text: #18181b;
  --text-muted: #71717a;
  --accent: #4f46e5;
  --accent-dim: #6366f1;
  --bar-fill: #4f46e5;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
}
.container { max-width: 960px; margin: 0 auto; padding: 2rem 1.5rem; }
.hero { text-align: center; padding: 2rem 0 1.5rem; }
.hero h1 { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; }
.subtitle { color: var(--text-muted); font-size: 0.875rem; margin-top: 0.25rem; }
.theme-toggle {
  position: fixed; top: 1rem; right: 1rem; background: var(--bg-card);
  border: 1px solid var(--border); border-radius: var(--radius);
  color: var(--text); cursor: pointer; padding: 0.4rem 0.75rem;
  font-size: 0.8rem;
}
.section { margin-top: 2.5rem; }
.section h2 { font-size: 1.125rem; font-weight: 600; margin-bottom: 0.75rem; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
thead th {
  text-align: left; padding: 0.625rem 0.75rem; border-bottom: 2px solid var(--border);
  color: var(--text-muted); font-weight: 500; font-size: 0.75rem;
  text-transform: uppercase; letter-spacing: 0.05em;
}
tbody td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }
tbody tr:hover { background: var(--bg-hover); }
.rank { text-align: center; font-weight: 600; }
.agent { font-weight: 500; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.run-row { cursor: pointer; }
.detail-row { display: none; background: var(--bg-card); }
.detail-row td { padding-left: 2rem; color: var(--text-muted); font-size: 0.8125rem; }
.badge {
  display: inline-block; background: var(--green); color: #000; font-size: 0.625rem;
  padding: 0.1rem 0.35rem; border-radius: 3px; font-weight: 700; margin-left: 0.35rem;
  vertical-align: middle;
}
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; }
.card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 1.25rem;
}
.card h3 { font-size: 1rem; font-weight: 600; margin-bottom: 0.75rem; }
.card-stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 0.75rem; }
.stat { display: flex; flex-direction: column; }
.stat-val { font-size: 1.125rem; font-weight: 700; }
.stat-label { font-size: 0.6875rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
.chart-note { color: var(--text-muted); font-size: 0.8125rem; margin-bottom: 0.75rem; }
.bar-chart { display: flex; flex-direction: column; gap: 0.5rem; }
.bar-row { display: flex; align-items: center; gap: 0.75rem; }
.bar-label { width: 100px; text-align: right; font-size: 0.8125rem; font-weight: 500; flex-shrink: 0; }
.bar-track { flex: 1; height: 20px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--bar-fill); border-radius: 4px; transition: width 0.3s; }
.bar-value { width: 100px; font-size: 0.75rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.empty-state { text-align: center; padding: 3rem 1rem; color: var(--text-muted); }
.empty-state pre {
  display: inline-block; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 0.5rem 1rem; margin: 0.75rem 0; font-size: 0.875rem;
}
@media (max-width: 640px) {
  .container { padding: 1rem; }
  .hero h1 { font-size: 1.375rem; }
  .card-grid { grid-template-columns: 1fr; }
  .bar-label { width: 70px; font-size: 0.75rem; }
  .bar-value { width: 80px; }
}
</style>"""


def _get_theme_toggle_js() -> str:
    """Return the inline JS for theme toggle and run expansion."""
    return """<script>
function toggleTheme(){var b=document.body;b.dataset.theme=b.dataset.theme==="dark"?"light":"dark";
document.querySelector(".theme-toggle").textContent=b.dataset.theme==="dark"?"Light":"Dark";}
function toggleRun(id){document.querySelectorAll('.detail-row[data-run="'+id+'"]').forEach(function(r){
r.style.display=r.style.display==="table-row"?"none":"table-row";});}
</script>"""


def _assemble_page(
    *,
    title: str,
    timestamp: str,
    leaderboard: str,
    history: str,
    agent_cards: str,
    cost_chart: str,
) -> str:
    """Assemble the full HTML page from sections."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{_get_css()}
</head>
<body data-theme="dark">
<button class="theme-toggle" onclick="toggleTheme()">Light</button>
<div class="container">
  <header class="hero">
    <h1>{title}</h1>
    <p class="subtitle">Last updated: {timestamp}</p>
  </header>
{leaderboard}
{history}
{agent_cards}
{cost_chart}
</div>
{_get_theme_toggle_js()}
</body>
</html>"""
