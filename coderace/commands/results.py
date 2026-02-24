"""coderace results formatting helpers."""

from __future__ import annotations

from coderace.types import Score


def _bool_md(val: bool) -> str:
    return "✅" if val else "❌"


def format_markdown_results(scores: list[Score], task_name: str = "") -> str:
    """Render a list of :class:`Score` objects as a markdown table.

    The table is sorted by composite score (descending) and includes rank,
    agent, composite score, and per-metric breakdown columns.

    Args:
        scores: List of scored agent results.
        task_name: Optional task name used in the heading.

    Returns:
        Markdown string with a heading, summary line, and results table.
    """
    if not scores:
        heading = (
            f"## coderace results: {task_name}\n\n" if task_name else "## coderace results\n\n"
        )
        return heading + "_No results recorded._\n"

    ranked = sorted(scores, key=lambda s: s.composite, reverse=True)
    winner = ranked[0]

    heading = f"## coderace results: {task_name}\n\n" if task_name else "## coderace results\n\n"

    summary = (
        f"**Winner:** `{winner.agent}` — {winner.composite:.1f} pts"
        f" | {len(ranked)} agent(s) raced\n\n"
    )

    # Table header
    header = "| Rank | Agent | Score | Tests | Lint | Exit | Time (s) | Lines | Cost (USD) |\n"
    separator = "|------|-------|------:|:-----:|:----:|:----:|---------:|------:|-----------:|\n"

    rows: list[str] = []
    for i, score in enumerate(ranked, 1):
        b = score.breakdown
        cost_str = (
            f"${score.cost_result.estimated_cost_usd:.4f}"
            if score.cost_result is not None
            else "-"
        )
        row = (
            f"| {i} | `{score.agent}` | {score.composite:.1f} |"
            f" {_bool_md(b.tests_pass)} | {_bool_md(b.lint_clean)} |"
            f" {_bool_md(b.exit_clean)} | {b.wall_time:.1f} | {b.lines_changed} | {cost_str} |"
        )
        rows.append(row)

    table = header + separator + "\n".join(rows) + "\n"

    return heading + summary + table


def format_markdown_from_json(data: list[dict], task_name: str = "") -> str:
    """Render markdown results from the JSON list returned by :func:`load_results_json`.

    This lets the ``results`` command produce markdown without re-constructing
    :class:`Score` objects from JSON.

    Args:
        data: List of result dicts as returned by ``load_results_json``.
        task_name: Optional task name for the heading.

    Returns:
        Markdown string.
    """
    if not data:
        heading = (
            f"## coderace results: {task_name}\n\n" if task_name else "## coderace results\n\n"
        )
        return heading + "_No results recorded._\n"

    winner = data[0]
    agent = winner.get("agent", "?")
    score = winner.get("composite_score", 0.0)
    n = len(data)

    heading = f"## coderace results: {task_name}\n\n" if task_name else "## coderace results\n\n"
    summary = f"**Winner:** `{agent}` — {score:.1f} pts | {n} agent(s) raced\n\n"

    header = "| Rank | Agent | Score | Tests | Lint | Exit | Time (s) | Lines | Cost (USD) |\n"
    separator = "|------|-------|------:|:-----:|:----:|:----:|---------:|------:|-----------:|\n"

    rows: list[str] = []
    for entry in data:
        b = entry.get("breakdown", {})
        cost_info = entry.get("cost")
        cost_str = (
            f"${cost_info['estimated_cost_usd']:.4f}"
            if cost_info is not None
            else "-"
        )
        rank = entry.get("rank", "?")
        a = entry.get("agent", "?")
        sc = entry.get("composite_score", 0.0)
        row = (
            f"| {rank} | `{a}` | {sc:.1f} |"
            f" {_bool_md(b.get('tests_pass', False))} |"
            f" {_bool_md(b.get('lint_clean', False))} |"
            f" {_bool_md(b.get('exit_clean', False))} |"
            f" {b.get('wall_time', 0.0):.1f} | {b.get('lines_changed', 0)} | {cost_str} |"
        )
        rows.append(row)

    return heading + summary + header + separator + "\n".join(rows) + "\n"
