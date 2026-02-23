"""Tests for statistical aggregation."""

from __future__ import annotations

from coderace.stats import aggregate_runs
from coderace.types import Score, ScoreBreakdown


def _make_score(agent: str, composite: float, wall_time: float = 10.0, lines: int = 50) -> Score:
    return Score(
        agent=agent,
        composite=composite,
        breakdown=ScoreBreakdown(
            tests_pass=composite >= 50,
            exit_clean=True,
            lint_clean=True,
            wall_time=wall_time,
            lines_changed=lines,
        ),
    )


def test_aggregate_single_run() -> None:
    scores = [_make_score("claude", 85.0), _make_score("codex", 70.0)]
    stats = aggregate_runs([scores])
    assert len(stats) == 2
    assert stats[0].agent == "claude"
    assert stats[0].score_mean == 85.0
    assert stats[0].score_stddev == 0.0
    assert stats[0].runs == 1


def test_aggregate_multiple_runs_mean() -> None:
    run1 = [_make_score("claude", 80.0), _make_score("codex", 60.0)]
    run2 = [_make_score("claude", 90.0), _make_score("codex", 70.0)]
    stats = aggregate_runs([run1, run2])
    claude = next(s for s in stats if s.agent == "claude")
    assert claude.score_mean == 85.0
    assert claude.runs == 2


def test_aggregate_multiple_runs_stddev() -> None:
    run1 = [_make_score("claude", 80.0)]
    run2 = [_make_score("claude", 90.0)]
    stats = aggregate_runs([run1, run2])
    claude = stats[0]
    # stddev of [80, 90] = sqrt(((80-85)^2 + (90-85)^2) / 1) = sqrt(50) ~ 7.07
    assert claude.score_stddev > 0


def test_aggregate_sorted_by_mean_desc() -> None:
    run1 = [_make_score("aider", 50.0), _make_score("claude", 90.0), _make_score("codex", 70.0)]
    stats = aggregate_runs([run1])
    assert stats[0].agent == "claude"
    assert stats[1].agent == "codex"
    assert stats[2].agent == "aider"


def test_aggregate_tests_pass_rate() -> None:
    # Run 1: tests pass for claude, Run 2: tests fail (score < 50)
    run1 = [Score("claude", 80.0, ScoreBreakdown(tests_pass=True, exit_clean=True))]
    run2 = [Score("claude", 30.0, ScoreBreakdown(tests_pass=False, exit_clean=True))]
    stats = aggregate_runs([run1, run2])
    assert stats[0].tests_pass_rate == 0.5


def test_aggregate_empty_runs() -> None:
    stats = aggregate_runs([])
    assert stats == []


def test_aggregate_preserves_per_run_scores() -> None:
    run1 = [_make_score("claude", 80.0)]
    run2 = [_make_score("claude", 90.0)]
    stats = aggregate_runs([run1, run2])
    assert sorted(stats[0].per_run_scores) == [80.0, 90.0]
