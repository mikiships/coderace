"""Tests for HTML report generation."""

from __future__ import annotations

from pathlib import Path

from coderace.html_report import generate_html_report, save_html_report
from coderace.types import Score, ScoreBreakdown


def _make_scores() -> list[Score]:
    return [
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
    ]


def test_generate_html_contains_agents() -> None:
    html = generate_html_report(_make_scores(), task_name="fix-bug")
    assert "claude" in html
    assert "codex" in html
    assert "85.0" in html
    assert "70.0" in html


def test_generate_html_contains_structure() -> None:
    html = generate_html_report(_make_scores())
    assert "<!DOCTYPE html>" in html
    assert "<table" in html
    assert "coderace" in html
    assert "PASS" in html
    assert "FAIL" in html


def test_generate_html_sortable_js() -> None:
    html = generate_html_report(_make_scores())
    assert "<script>" in html
    assert "sorted-asc" in html


def test_generate_html_with_weights() -> None:
    weights = {
        "tests_pass": 0.5, "exit_clean": 0.2,
        "lint_clean": 0.1, "wall_time": 0.1,
        "lines_changed": 0.1,
    }
    html = generate_html_report(_make_scores(), weights=weights)
    assert "Scoring:" in html
    assert "50%" in html


def test_generate_html_without_weights() -> None:
    html = generate_html_report(_make_scores())
    assert "Scoring:" not in html


def test_generate_html_escapes_task_name() -> None:
    html = generate_html_report(_make_scores(), task_name='<script>alert("xss")</script>')
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_save_html_report(tmp_path: Path) -> None:
    output = tmp_path / "report.html"
    save_html_report(_make_scores(), output, task_name="test")
    assert output.exists()
    content = output.read_text()
    assert "<!DOCTYPE html>" in content
    assert "claude" in content


def test_save_html_creates_parent_dirs(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "dir" / "report.html"
    save_html_report(_make_scores(), output)
    assert output.exists()
