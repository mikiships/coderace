"""Tests for reporter output."""

from __future__ import annotations

import json
from pathlib import Path

from coderace.reporter import load_results_json, print_results, save_results_json
from coderace.types import Score, ScoreBreakdown


def _make_scores() -> list[Score]:
    return [
        Score(
            agent="claude",
            composite=85.0,
            breakdown=ScoreBreakdown(
                tests_pass=True, exit_clean=True, lint_clean=True, wall_time=10.5, lines_changed=42
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
    ]


def test_print_results_returns_string() -> None:
    scores = _make_scores()
    output = print_results(scores)
    assert "claude" in output
    assert "codex" in output
    assert "85.0" in output


def test_save_and_load_json(tmp_path: Path) -> None:
    scores = _make_scores()
    json_path = tmp_path / ".coderace" / "results.json"
    save_results_json(scores, json_path)

    assert json_path.exists()
    data = load_results_json(json_path)
    assert len(data) == 2
    assert data[0]["agent"] == "claude"  # Higher score first
    assert data[0]["composite_score"] == 85.0


def test_json_structure(tmp_path: Path) -> None:
    scores = _make_scores()
    json_path = tmp_path / "results.json"
    save_results_json(scores, json_path)

    raw = json.loads(json_path.read_text())
    assert "results" in raw
    entry = raw["results"][0]
    assert "breakdown" in entry
    assert "tests_pass" in entry["breakdown"]
    assert "wall_time" in entry["breakdown"]
