"""Tests for D2: cost integration into race results pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coderace.cost import CostResult
from coderace.reporter import load_results_json, print_results, save_results_json
from coderace.stats import AgentStats, aggregate_runs
from coderace.types import AgentResult, Score, ScoreBreakdown


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cost() -> CostResult:
    return CostResult(
        input_tokens=1000,
        output_tokens=200,
        estimated_cost_usd=0.006,
        model_name="claude-sonnet-4-6",
        pricing_source="parsed",
    )


def _make_scores_with_cost() -> list[Score]:
    return [
        Score(
            agent="claude",
            composite=85.0,
            breakdown=ScoreBreakdown(
                tests_pass=True, exit_clean=True, lint_clean=True, wall_time=10.5, lines_changed=42
            ),
            cost_result=CostResult(
                input_tokens=1000,
                output_tokens=200,
                estimated_cost_usd=0.0060,
                model_name="claude-sonnet-4-6",
                pricing_source="parsed",
            ),
        ),
        Score(
            agent="codex",
            composite=70.0,
            breakdown=ScoreBreakdown(
                tests_pass=True, exit_clean=True, lint_clean=False, wall_time=15.2, lines_changed=98
            ),
            cost_result=CostResult(
                input_tokens=800,
                output_tokens=150,
                estimated_cost_usd=0.0049,
                model_name="gpt-5.3-codex",
                pricing_source="parsed",
            ),
        ),
    ]


def _make_scores_no_cost() -> list[Score]:
    return [
        Score(
            agent="aider",
            composite=60.0,
            breakdown=ScoreBreakdown(
                tests_pass=False, exit_clean=True, lint_clean=True, wall_time=8.0, lines_changed=20
            ),
            cost_result=None,
        ),
    ]


# ---------------------------------------------------------------------------
# AgentResult has cost_result field
# ---------------------------------------------------------------------------


def test_agent_result_default_cost_is_none() -> None:
    result = AgentResult(
        agent="claude",
        exit_code=0,
        stdout="",
        stderr="",
        wall_time=10.0,
    )
    assert result.cost_result is None


def test_agent_result_accepts_cost_result() -> None:
    cr = _make_cost()
    result = AgentResult(
        agent="claude",
        exit_code=0,
        stdout="",
        stderr="",
        wall_time=10.0,
        cost_result=cr,
    )
    assert result.cost_result is cr


# ---------------------------------------------------------------------------
# Score has cost_result field
# ---------------------------------------------------------------------------


def test_score_default_cost_is_none() -> None:
    score = Score(agent="claude", composite=80.0)
    assert score.cost_result is None


def test_score_accepts_cost_result() -> None:
    cr = _make_cost()
    score = Score(agent="claude", composite=80.0, cost_result=cr)
    assert score.cost_result is cr


# ---------------------------------------------------------------------------
# scorer propagates cost from AgentResult
# ---------------------------------------------------------------------------


def test_scorer_propagates_cost(tmp_path: Path) -> None:
    from coderace.scorer import compute_score

    cr = _make_cost()
    result = AgentResult(
        agent="claude",
        exit_code=0,
        stdout="",
        stderr="",
        wall_time=5.0,
        cost_result=cr,
    )
    score = compute_score(
        result=result,
        test_command="echo ok",
        lint_command=None,
        workdir=tmp_path,
        diff_lines=10,
        all_wall_times=[5.0],
        all_diff_lines=[10],
    )
    assert score.cost_result is cr


def test_scorer_propagates_none_cost(tmp_path: Path) -> None:
    from coderace.scorer import compute_score

    result = AgentResult(
        agent="claude",
        exit_code=0,
        stdout="",
        stderr="",
        wall_time=5.0,
        cost_result=None,
    )
    score = compute_score(
        result=result,
        test_command="echo ok",
        lint_command=None,
        workdir=tmp_path,
        diff_lines=10,
        all_wall_times=[5.0],
        all_diff_lines=[10],
    )
    assert score.cost_result is None


# ---------------------------------------------------------------------------
# reporter: terminal table includes Cost column
# ---------------------------------------------------------------------------


def test_print_results_shows_cost() -> None:
    scores = _make_scores_with_cost()
    output = print_results(scores)
    assert "Cost" in output
    assert "$0.006" in output or "$0.0060" in output


def test_print_results_shows_dash_when_no_cost() -> None:
    scores = _make_scores_no_cost()
    output = print_results(scores)
    assert "Cost" in output
    # dash for no cost
    assert "-" in output


# ---------------------------------------------------------------------------
# save_results_json includes cost
# ---------------------------------------------------------------------------


def test_save_results_json_includes_cost(tmp_path: Path) -> None:
    scores = _make_scores_with_cost()
    path = tmp_path / "results.json"
    save_results_json(scores, path)

    data = json.loads(path.read_text())
    result0 = data["results"][0]
    assert "cost" in result0
    assert result0["cost"] is not None
    assert "estimated_cost_usd" in result0["cost"]
    assert "input_tokens" in result0["cost"]
    assert "output_tokens" in result0["cost"]
    assert "model_name" in result0["cost"]
    assert "pricing_source" in result0["cost"]


def test_save_results_json_cost_none_when_missing(tmp_path: Path) -> None:
    scores = _make_scores_no_cost()
    path = tmp_path / "results.json"
    save_results_json(scores, path)

    data = json.loads(path.read_text())
    result0 = data["results"][0]
    assert "cost" in result0
    assert result0["cost"] is None


def test_load_results_json_round_trip(tmp_path: Path) -> None:
    scores = _make_scores_with_cost()
    path = tmp_path / "results.json"
    save_results_json(scores, path)
    loaded = load_results_json(path)
    assert loaded[0]["cost"]["estimated_cost_usd"] == pytest.approx(0.006, rel=1e-3)


# ---------------------------------------------------------------------------
# Markdown output includes Cost column
# ---------------------------------------------------------------------------


def test_markdown_results_includes_cost_column() -> None:
    from coderace.commands.results import format_markdown_results
    scores = _make_scores_with_cost()
    md = format_markdown_results(scores, task_name="t")
    assert "Cost" in md
    assert "$0.006" in md or "$0.0060" in md


def test_markdown_results_dash_when_no_cost() -> None:
    from coderace.commands.results import format_markdown_results
    scores = _make_scores_no_cost()
    md = format_markdown_results(scores)
    assert "Cost" in md


def test_markdown_from_json_includes_cost() -> None:
    from coderace.commands.results import format_markdown_from_json
    data = [
        {
            "rank": 1,
            "agent": "claude",
            "composite_score": 85.0,
            "breakdown": {"tests_pass": True, "exit_clean": True, "lint_clean": True, "wall_time": 10.0, "lines_changed": 42},
            "cost": {"estimated_cost_usd": 0.0060, "input_tokens": 1000, "output_tokens": 200, "model_name": "claude-sonnet-4-6", "pricing_source": "parsed"},
        }
    ]
    md = format_markdown_from_json(data, task_name="t")
    assert "Cost" in md
    assert "$0.006" in md or "$0.0060" in md


def test_markdown_from_json_no_cost_shows_dash() -> None:
    from coderace.commands.results import format_markdown_from_json
    data = [
        {
            "rank": 1,
            "agent": "aider",
            "composite_score": 60.0,
            "breakdown": {"tests_pass": False, "exit_clean": True, "lint_clean": True, "wall_time": 8.0, "lines_changed": 20},
            "cost": None,
        }
    ]
    md = format_markdown_from_json(data)
    assert "Cost" in md


# ---------------------------------------------------------------------------
# HTML report includes Cost column
# ---------------------------------------------------------------------------


def test_html_report_includes_cost_column() -> None:
    from coderace.html_report import generate_html_report
    scores = _make_scores_with_cost()
    html = generate_html_report(scores, task_name="t")
    assert "Cost (USD)" in html
    assert "$/score" in html
    assert "$0.006" in html or "$0.0060" in html


def test_html_report_dash_when_no_cost() -> None:
    from coderace.html_report import generate_html_report
    scores = _make_scores_no_cost()
    html_out = generate_html_report(scores)
    assert "Cost (USD)" in html_out
    # "-" should appear for null cost
    assert "-" in html_out


# ---------------------------------------------------------------------------
# stats: aggregate cost
# ---------------------------------------------------------------------------


def test_aggregate_runs_cost_mean() -> None:
    run1 = [
        Score(agent="claude", composite=80.0, breakdown=ScoreBreakdown(),
              cost_result=CostResult(1000, 200, 0.006, "claude-sonnet-4-6", "parsed")),
    ]
    run2 = [
        Score(agent="claude", composite=85.0, breakdown=ScoreBreakdown(),
              cost_result=CostResult(1100, 210, 0.008, "claude-sonnet-4-6", "parsed")),
    ]
    stats = aggregate_runs([run1, run2])
    assert len(stats) == 1
    s = stats[0]
    assert s.cost_mean == pytest.approx(0.007, abs=1e-4)
    assert s.cost_stddev > 0


def test_aggregate_runs_cost_zero_when_no_data() -> None:
    run1 = [
        Score(agent="aider", composite=60.0, breakdown=ScoreBreakdown(), cost_result=None),
    ]
    stats = aggregate_runs([run1])
    assert stats[0].cost_mean == 0.0
    assert stats[0].cost_stddev == 0.0


def test_agent_stats_has_cost_fields() -> None:
    s = AgentStats(
        agent="test",
        runs=2,
        score_mean=80.0,
        score_stddev=2.0,
        time_mean=10.0,
        time_stddev=1.0,
        lines_mean=50.0,
        lines_stddev=5.0,
        tests_pass_rate=1.0,
        exit_clean_rate=1.0,
        lint_clean_rate=1.0,
        per_run_scores=[80.0, 80.0],
    )
    assert hasattr(s, "cost_mean")
    assert hasattr(s, "cost_stddev")
    assert s.cost_mean == 0.0
    assert s.cost_stddev == 0.0


# ---------------------------------------------------------------------------
# base adapter: parse_cost fails gracefully
# ---------------------------------------------------------------------------


def test_base_adapter_parse_cost_returns_none() -> None:
    from coderace.adapters.base import BaseAdapter

    class ConcreteAdapter(BaseAdapter):
        name = "test"
        def build_command(self, task_description: str) -> list[str]:
            return ["echo", task_description]

    adapter = ConcreteAdapter()
    result = adapter.parse_cost("any stdout", "any stderr")
    assert result is None
