"""Tests for D3: Dashboard integration with context-eval results."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coderace.dashboard import _build_context_eval_section, generate_dashboard
from coderace.store import ResultStore


def _sample_context_eval_data() -> dict:
    """Return sample context-eval JSON data for testing."""
    return {
        "type": "context-eval",
        "context_file": "CLAUDE.md",
        "trials_per_condition": 3,
        "agents": [
            {
                "agent": "claude",
                "baseline_pass_rate": 0.67,
                "treatment_pass_rate": 1.0,
                "baseline_mean_score": 55.0,
                "treatment_mean_score": 81.0,
                "delta": 26.0,
                "ci_95": [10.5, 41.5],
                "effect_size": 2.1,
            },
            {
                "agent": "codex",
                "baseline_pass_rate": 0.33,
                "treatment_pass_rate": 0.67,
                "baseline_mean_score": 45.0,
                "treatment_mean_score": 70.0,
                "delta": 25.0,
                "ci_95": [8.0, 42.0],
                "effect_size": 1.8,
            },
        ],
        "tasks": [],
        "summary": {
            "overall_delta": 25.5,
            "overall_ci_95": [12.0, 39.0],
            "verdict": "Context file improved performance by +25.5 points (CI: [12.0, 39.0])",
        },
        "trials": [],
    }


class TestBuildContextEvalSection:
    def test_returns_empty_for_none(self) -> None:
        assert _build_context_eval_section(None) == ""

    def test_returns_empty_for_wrong_type(self) -> None:
        assert _build_context_eval_section({"type": "other"}) == ""

    def test_returns_empty_for_no_agents(self) -> None:
        assert _build_context_eval_section({"type": "context-eval", "agents": []}) == ""

    def test_contains_section_heading(self) -> None:
        data = _sample_context_eval_data()
        html = _build_context_eval_section(data)
        assert "Context Eval: A/B Comparison" in html

    def test_contains_context_file_name(self) -> None:
        data = _sample_context_eval_data()
        html = _build_context_eval_section(data)
        assert "CLAUDE.md" in html

    def test_contains_agent_names(self) -> None:
        data = _sample_context_eval_data()
        html = _build_context_eval_section(data)
        assert "claude" in html
        assert "codex" in html

    def test_contains_bar_chart(self) -> None:
        data = _sample_context_eval_data()
        html = _build_context_eval_section(data)
        assert "ab-baseline" in html
        assert "ab-treatment" in html
        assert "Baseline" in html
        assert "Treatment" in html

    def test_contains_delta_table(self) -> None:
        data = _sample_context_eval_data()
        html = _build_context_eval_section(data)
        assert "Delta" in html
        assert "CI (95%)" in html
        assert "Effect Size" in html

    def test_contains_verdict(self) -> None:
        data = _sample_context_eval_data()
        html = _build_context_eval_section(data)
        assert "improved" in html

    def test_positive_delta_has_class(self) -> None:
        data = _sample_context_eval_data()
        html = _build_context_eval_section(data)
        assert "positive" in html

    def test_negative_delta_has_class(self) -> None:
        data = _sample_context_eval_data()
        data["agents"][0]["delta"] = -5.0
        html = _build_context_eval_section(data)
        assert "negative" in html

    def test_html_escapes_context_file(self) -> None:
        data = _sample_context_eval_data()
        data["context_file"] = "<script>alert(1)</script>"
        html = _build_context_eval_section(data)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


class TestDashboardWithContextEval:
    def test_dashboard_includes_context_eval(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        store = ResultStore(db_path=db_path)
        store.save_run("test-task", [
            {"agent": "claude", "composite_score": 85.0, "wall_time": 10.0,
             "lines_changed": 42, "tests_pass": True, "exit_clean": True,
             "lint_clean": True},
        ])

        data = _sample_context_eval_data()
        html = generate_dashboard(store, context_eval_data=data)
        store.close()

        assert "Context Eval: A/B Comparison" in html
        assert "CLAUDE.md" in html

    def test_dashboard_without_context_eval(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        store = ResultStore(db_path=db_path)
        store.save_run("test-task", [
            {"agent": "claude", "composite_score": 85.0, "wall_time": 10.0,
             "lines_changed": 42, "tests_pass": True, "exit_clean": True,
             "lint_clean": True},
        ])

        html = generate_dashboard(store)
        store.close()

        assert "Context Eval" not in html

    def test_empty_store_with_context_eval_shows_section(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        store = ResultStore(db_path=db_path)
        data = _sample_context_eval_data()
        html = generate_dashboard(store, context_eval_data=data)
        store.close()

        assert "Context Eval: A/B Comparison" in html
        assert "</html>" in html


class TestDashboardCLIContextEval:
    def test_context_eval_flag(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app
        import os

        # Set up a temp DB
        db_path = tmp_path / "test.db"
        os.environ["CODERACE_DB"] = str(db_path)

        try:
            # Create a context-eval JSON file
            ctx_json = tmp_path / "context-eval.json"
            ctx_json.write_text(json.dumps(_sample_context_eval_data()))

            output_path = tmp_path / "dashboard.html"
            runner = CliRunner()
            result = runner.invoke(app, [
                "dashboard",
                "--output", str(output_path),
                "--context-eval", str(ctx_json),
            ])

            assert result.exit_code == 0
            html = output_path.read_text()
            assert "Context Eval: A/B Comparison" in html
        finally:
            del os.environ["CODERACE_DB"]

    def test_context_eval_file_not_found(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "dashboard",
            "--context-eval", "/nonexistent/eval.json",
        ])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()
