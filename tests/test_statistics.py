"""Tests for statistical benchmarking analysis (D2)."""

from __future__ import annotations

import pytest

from coderace.benchmark import BenchmarkResult, TaskAgentResult
from coderace.statistics import compute_aggregate_stats, compute_trial_stats


def _row(
    task: str,
    agent: str,
    trial: int,
    score: float,
    wall_time: float = 10.0,
    cost_usd: float | None = None,
    timed_out: bool = False,
    error: str | None = None,
) -> TaskAgentResult:
    return TaskAgentResult(
        task_name=task,
        agent=agent,
        score=score,
        wall_time=wall_time,
        tests_pass=score > 0,
        exit_clean=not bool(error),
        lint_clean=True,
        timed_out=timed_out,
        trial_number=trial,
        cost_usd=cost_usd,
        error=error,
    )


def _bench(
    agents: list[str],
    tasks: list[str],
    results: list[TaskAgentResult],
    trials: int,
) -> BenchmarkResult:
    return BenchmarkResult(
        benchmark_id="bench-stats-test",
        agents=agents,
        tasks=tasks,
        trials=trials,
        results=results,
    )


def test_trial_stats_single_trial_ci_is_degenerate() -> None:
    result = _bench(
        agents=["claude"],
        tasks=["fibonacci"],
        trials=1,
        results=[_row("fibonacci", "claude", trial=1, score=88.0, wall_time=9.0, cost_usd=0.02)],
    )

    stats = compute_trial_stats(result)
    assert len(stats) == 1
    row = stats[0]
    assert row.trials == 1
    assert row.mean_score == pytest.approx(88.0)
    assert row.stddev_score == pytest.approx(0.0)
    assert row.ci_95 == pytest.approx((88.0, 88.0))
    assert row.pass_rate == pytest.approx(1.0)


def test_trial_stats_three_trials_mean_stddev_and_cost() -> None:
    result = _bench(
        agents=["claude"],
        tasks=["fibonacci"],
        trials=3,
        results=[
            _row("fibonacci", "claude", 1, 80.0, wall_time=10.0, cost_usd=0.01),
            _row("fibonacci", "claude", 2, 90.0, wall_time=12.0, cost_usd=0.02),
            _row("fibonacci", "claude", 3, 100.0, wall_time=14.0, cost_usd=0.03),
        ],
    )

    row = compute_trial_stats(result)[0]
    assert row.trials == 3
    assert row.mean_score == pytest.approx(90.0)
    assert row.stddev_score == pytest.approx(10.0)
    assert row.mean_wall_time == pytest.approx(12.0)
    assert row.stddev_wall_time == pytest.approx(2.0)
    assert row.mean_cost == pytest.approx(0.02)
    assert row.stddev_cost == pytest.approx(0.01)


def test_trial_stats_ten_trials_are_aggregated() -> None:
    rows = [
        _row("fibonacci", "claude", idx, float(idx), wall_time=float(idx) + 1.0)
        for idx in range(1, 11)
    ]
    result = _bench(
        agents=["claude"],
        tasks=["fibonacci"],
        trials=10,
        results=rows,
    )

    stat = compute_trial_stats(result)[0]
    assert stat.trials == 10
    assert stat.mean_score == pytest.approx(5.5)
    assert stat.ci_95[0] < stat.mean_score < stat.ci_95[1]


def test_trial_stats_all_zero_scores_have_zero_pass_rate() -> None:
    result = _bench(
        agents=["claude"],
        tasks=["fibonacci"],
        trials=3,
        results=[
            _row("fibonacci", "claude", 1, 0.0),
            _row("fibonacci", "claude", 2, 0.0),
            _row("fibonacci", "claude", 3, 0.0),
        ],
    )

    stat = compute_trial_stats(result)[0]
    assert stat.pass_rate == 0.0
    assert stat.consistency_score == 1.0


def test_aggregate_stats_single_agent_win_rate_is_one() -> None:
    result = _bench(
        agents=["claude"],
        tasks=["fibonacci", "json-parser"],
        trials=2,
        results=[
            _row("fibonacci", "claude", 1, 85.0),
            _row("fibonacci", "claude", 2, 86.0),
            _row("json-parser", "claude", 1, 70.0),
            _row("json-parser", "claude", 2, 72.0),
        ],
    )

    aggregate = compute_aggregate_stats(result)
    assert len(aggregate) == 1
    assert aggregate[0].win_rate == 1.0


def test_aggregate_stats_multi_agent_win_rate_by_task_means() -> None:
    result = _bench(
        agents=["claude", "codex"],
        tasks=["fibonacci", "json-parser"],
        trials=2,
        results=[
            _row("fibonacci", "claude", 1, 90.0),
            _row("fibonacci", "claude", 2, 92.0),
            _row("fibonacci", "codex", 1, 80.0),
            _row("fibonacci", "codex", 2, 82.0),
            _row("json-parser", "claude", 1, 60.0),
            _row("json-parser", "claude", 2, 62.0),
            _row("json-parser", "codex", 1, 88.0),
            _row("json-parser", "codex", 2, 90.0),
        ],
    )

    aggregates = {row.agent: row for row in compute_aggregate_stats(result)}
    assert aggregates["claude"].win_rate == pytest.approx(0.5)
    assert aggregates["codex"].win_rate == pytest.approx(0.5)


def test_aggregate_stats_reliability_excludes_timeouts_and_errors() -> None:
    result = _bench(
        agents=["claude"],
        tasks=["fibonacci"],
        trials=4,
        results=[
            _row("fibonacci", "claude", 1, 90.0),
            _row("fibonacci", "claude", 2, 80.0),
            _row("fibonacci", "claude", 3, 0.0, timed_out=True),
            _row("fibonacci", "claude", 4, 0.0, error="runner failed"),
        ],
    )

    aggregate = compute_aggregate_stats(result)[0]
    assert aggregate.reliability == pytest.approx(0.5)


def test_aggregate_stats_cost_efficiency_uses_mean_cost() -> None:
    result = _bench(
        agents=["claude"],
        tasks=["fibonacci"],
        trials=2,
        results=[
            _row("fibonacci", "claude", 1, 80.0, cost_usd=0.02),
            _row("fibonacci", "claude", 2, 100.0, cost_usd=0.04),
        ],
    )

    aggregate = compute_aggregate_stats(result)[0]
    assert aggregate.mean_score == pytest.approx(90.0)
    assert aggregate.cost_efficiency == pytest.approx(3000.0)


def test_aggregate_ci_width_shrinks_with_more_trials() -> None:
    result_3 = _bench(
        agents=["claude"],
        tasks=["fibonacci"],
        trials=3,
        results=[
            _row("fibonacci", "claude", 1, 70.0),
            _row("fibonacci", "claude", 2, 80.0),
            _row("fibonacci", "claude", 3, 90.0),
        ],
    )
    result_10 = _bench(
        agents=["claude"],
        tasks=["fibonacci"],
        trials=10,
        results=[
            _row("fibonacci", "claude", idx, score)
            for idx, score in enumerate(
                [74.0, 76.0, 78.0, 79.0, 80.0, 81.0, 82.0, 84.0, 86.0, 88.0],
                start=1,
            )
        ],
    )

    ci_3 = compute_aggregate_stats(result_3)[0].score_ci_95
    ci_10 = compute_aggregate_stats(result_10)[0].score_ci_95
    width_3 = ci_3[1] - ci_3[0]
    width_10 = ci_10[1] - ci_10[0]
    assert width_10 < width_3
