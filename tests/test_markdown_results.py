"""Tests for --format markdown / D4 results output."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from coderace.cli import app
from coderace.commands.results import format_markdown_from_json, format_markdown_results
from coderace.types import Score, ScoreBreakdown

runner = CliRunner()

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_SCORES = [
    Score(
        agent="claude",
        composite=85.0,
        breakdown=ScoreBreakdown(
            tests_pass=True,
            exit_clean=True,
            lint_clean=True,
            wall_time=10.5,
            lines_changed=42,
        ),
    ),
    Score(
        agent="codex",
        composite=70.0,
        breakdown=ScoreBreakdown(
            tests_pass=True,
            exit_clean=True,
            lint_clean=False,
            wall_time=15.2,
            lines_changed=98,
        ),
    ),
    Score(
        agent="aider",
        composite=55.0,
        breakdown=ScoreBreakdown(
            tests_pass=False,
            exit_clean=True,
            lint_clean=True,
            wall_time=8.1,
            lines_changed=31,
        ),
    ),
]

SAMPLE_JSON_RESULTS = [
    {
        "rank": 1,
        "agent": "claude",
        "composite_score": 85.0,
        "breakdown": {
            "tests_pass": True,
            "exit_clean": True,
            "lint_clean": True,
            "wall_time": 10.5,
            "lines_changed": 42,
        },
        "tests_output": "",
        "lint_output": "",
        "diff_stat": "",
    },
    {
        "rank": 2,
        "agent": "codex",
        "composite_score": 70.0,
        "breakdown": {
            "tests_pass": True,
            "exit_clean": True,
            "lint_clean": False,
            "wall_time": 15.2,
            "lines_changed": 98,
        },
        "tests_output": "",
        "lint_output": "",
        "diff_stat": "",
    },
]


# ---------------------------------------------------------------------------
# format_markdown_results (from Score objects)
# ---------------------------------------------------------------------------


def test_markdown_results_has_heading() -> None:
    md = format_markdown_results(SAMPLE_SCORES, task_name="my-task")
    assert "## coderace results: my-task" in md


def test_markdown_results_has_winner() -> None:
    md = format_markdown_results(SAMPLE_SCORES, task_name="task")
    assert "claude" in md
    assert "85.0" in md


def test_markdown_results_table_header() -> None:
    md = format_markdown_results(SAMPLE_SCORES)
    assert "| Rank |" in md
    assert "| Agent |" in md
    assert "| Score |" in md


def test_markdown_results_all_agents() -> None:
    md = format_markdown_results(SAMPLE_SCORES)
    assert "claude" in md
    assert "codex" in md
    assert "aider" in md


def test_markdown_results_pass_fail_icons() -> None:
    md = format_markdown_results(SAMPLE_SCORES)
    assert "✅" in md
    assert "❌" in md


def test_markdown_results_sorted_by_score() -> None:
    """Winner (claude, 85.0) should appear before codex and aider."""
    md = format_markdown_results(SAMPLE_SCORES)
    claude_idx = md.index("claude")
    codex_idx = md.index("codex")
    assert claude_idx < codex_idx


def test_markdown_results_empty() -> None:
    md = format_markdown_results([], task_name="empty")
    assert "No results" in md


def test_markdown_results_no_task_name() -> None:
    md = format_markdown_results(SAMPLE_SCORES)
    assert "## coderace results" in md


# ---------------------------------------------------------------------------
# format_markdown_from_json
# ---------------------------------------------------------------------------


def test_format_markdown_from_json_basic() -> None:
    md = format_markdown_from_json(SAMPLE_JSON_RESULTS, task_name="t")
    assert "claude" in md
    assert "85.0" in md


def test_format_markdown_from_json_empty() -> None:
    md = format_markdown_from_json([], task_name="x")
    assert "No results" in md


def test_format_markdown_from_json_icons() -> None:
    md = format_markdown_from_json(SAMPLE_JSON_RESULTS)
    assert "✅" in md


# ---------------------------------------------------------------------------
# CLI: coderace results --format markdown
# ---------------------------------------------------------------------------


def _write_results_json(results_dir: Path, task_name: str) -> None:
    """Write a minimal results JSON file for CLI tests."""
    results_dir.mkdir(parents=True, exist_ok=True)
    data = {"results": SAMPLE_JSON_RESULTS}
    (results_dir / f"{task_name}-results.json").write_text(json.dumps(data))


def test_cli_results_format_markdown(tmp_path: Path, task_yaml: Path) -> None:
    """coderace results --format markdown should output a markdown table."""
    from coderace.task import load_task

    task = load_task(task_yaml)
    results_dir = task_yaml.parent / ".coderace"
    _write_results_json(results_dir, task.name)

    result = runner.invoke(app, ["results", str(task_yaml), "--format", "markdown"])
    assert result.exit_code == 0, result.output
    assert "## coderace results" in result.output
    assert "|" in result.output  # markdown table


def test_cli_results_format_json(tmp_path: Path, task_yaml: Path) -> None:
    """coderace results --format json should output valid JSON."""
    from coderace.task import load_task

    task = load_task(task_yaml)
    results_dir = task_yaml.parent / ".coderace"
    _write_results_json(results_dir, task.name)

    result = runner.invoke(app, ["results", str(task_yaml), "--format", "json"])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert "results" in parsed


def test_cli_results_format_unknown(task_yaml: Path) -> None:
    """Unknown --format should exit non-zero."""
    from coderace.task import load_task

    task = load_task(task_yaml)
    results_dir = task_yaml.parent / ".coderace"
    _write_results_json(results_dir, task.name)

    result = runner.invoke(app, ["results", str(task_yaml), "--format", "csv"])
    assert result.exit_code != 0


def test_cli_results_format_terminal_default(task_yaml: Path) -> None:
    """Default (no --format or --format terminal) should use Rich table."""
    from coderace.task import load_task

    task = load_task(task_yaml)
    results_dir = task_yaml.parent / ".coderace"
    _write_results_json(results_dir, task.name)

    result = runner.invoke(app, ["results", str(task_yaml)])
    assert result.exit_code == 0
