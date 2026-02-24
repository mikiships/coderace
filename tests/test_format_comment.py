"""Tests for scripts/format-comment.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# The module name has a hyphen, so we use importlib to load it.


def _load_format_comment() -> object:
    spec = importlib.util.spec_from_file_location(
        "format_comment",
        Path(__file__).parent.parent / "scripts" / "format-comment.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


fc = _load_format_comment()


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_RESULTS = [
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
    },
    {
        "rank": 3,
        "agent": "aider",
        "composite_score": 55.0,
        "breakdown": {
            "tests_pass": False,
            "exit_clean": True,
            "lint_clean": True,
            "wall_time": 8.1,
            "lines_changed": 31,
        },
    },
]


# ---------------------------------------------------------------------------
# format_results_table
# ---------------------------------------------------------------------------


def test_format_results_table_contains_header() -> None:
    table = fc.format_results_table(SAMPLE_RESULTS)  # type: ignore[attr-defined]
    assert "Rank" in table
    assert "Agent" in table
    assert "Score" in table


def test_format_results_table_contains_all_agents() -> None:
    table = fc.format_results_table(SAMPLE_RESULTS)  # type: ignore[attr-defined]
    assert "claude" in table
    assert "codex" in table
    assert "aider" in table


def test_format_results_table_pass_fail_icons() -> None:
    table = fc.format_results_table(SAMPLE_RESULTS)  # type: ignore[attr-defined]
    assert "✅" in table  # at least one passing
    assert "❌" in table  # at least one failing


def test_format_results_table_scores() -> None:
    table = fc.format_results_table(SAMPLE_RESULTS)  # type: ignore[attr-defined]
    assert "85.0" in table
    assert "70.0" in table
    assert "55.0" in table


def test_format_results_table_empty() -> None:
    table = fc.format_results_table([])  # type: ignore[attr-defined]
    # Should still have a header row
    assert "Rank" in table


# ---------------------------------------------------------------------------
# format_summary
# ---------------------------------------------------------------------------


def test_format_summary_winner() -> None:
    summary = fc.format_summary(SAMPLE_RESULTS, "my-task")  # type: ignore[attr-defined]
    assert "claude" in summary
    assert "85.0" in summary
    assert "my-task" in summary


def test_format_summary_empty_results() -> None:
    summary = fc.format_summary([], "empty-task")  # type: ignore[attr-defined]
    assert "no results" in summary.lower()


def test_format_summary_failing_winner() -> None:
    failing = [
        {
            "rank": 1,
            "agent": "aider",
            "composite_score": 40.0,
            "breakdown": {
                "tests_pass": False,
                "exit_clean": True,
                "lint_clean": False,
                "wall_time": 5.0,
                "lines_changed": 10,
            },
        }
    ]
    summary = fc.format_summary(failing, "task")  # type: ignore[attr-defined]
    assert "⚠️" in summary  # failing winner gets warning badge


# ---------------------------------------------------------------------------
# format_comment
# ---------------------------------------------------------------------------


def test_format_comment_contains_marker() -> None:
    comment = fc.format_comment(SAMPLE_RESULTS, "my-task")  # type: ignore[attr-defined]
    assert "<!-- coderace-results -->" in comment


def test_format_comment_contains_table() -> None:
    comment = fc.format_comment(SAMPLE_RESULTS, "my-task")  # type: ignore[attr-defined]
    assert "claude" in comment
    assert "85.0" in comment


def test_format_comment_includes_json_details() -> None:
    raw = json.dumps({"results": SAMPLE_RESULTS})
    comment = fc.format_comment(SAMPLE_RESULTS, "my-task", json_raw=raw)  # type: ignore[attr-defined]
    assert "<details>" in comment
    assert "```json" in comment


def test_format_comment_no_results() -> None:
    comment = fc.format_comment([], "empty-task")  # type: ignore[attr-defined]
    assert "no results" in comment.lower()
    assert "<!-- coderace-results -->" in comment


def test_format_comment_footer() -> None:
    comment = fc.format_comment(SAMPLE_RESULTS, "task")  # type: ignore[attr-defined]
    assert "coderace" in comment.lower()


# ---------------------------------------------------------------------------
# main() CLI entry point
# ---------------------------------------------------------------------------


def test_main_missing_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    missing = tmp_path / "nonexistent-results.json"
    ret = fc.main(["--json-file", str(missing), "--task-name", "test"])  # type: ignore[attr-defined]
    assert ret == 0
    captured = capsys.readouterr()
    assert "no results" in captured.out.lower()


def test_main_writes_to_file(tmp_path: Path) -> None:
    json_file = tmp_path / "task-results.json"
    json_file.write_text(json.dumps({"results": SAMPLE_RESULTS}))
    out_file = tmp_path / "comment.md"

    ret = fc.main([  # type: ignore[attr-defined]
        "--json-file", str(json_file),
        "--task-name", "my-task",
        "--output", str(out_file),
    ])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text()
    assert "claude" in content


def test_main_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    bad = tmp_path / "bad-results.json"
    bad.write_text("NOT JSON AT ALL")
    ret = fc.main(["--json-file", str(bad), "--task-name", "x"])  # type: ignore[attr-defined]
    assert ret == 0  # graceful degradation
    captured = capsys.readouterr()
    assert "no results" in captured.out.lower()
