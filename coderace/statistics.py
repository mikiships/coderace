"""Statistical analysis for multi-trial benchmark runs."""

from __future__ import annotations

import math
import statistics as _statistics
from dataclasses import dataclass
from typing import Optional

from coderace.benchmark import BenchmarkResult, TaskAgentResult


@dataclass
class TrialStats:
    """Aggregated statistics for one (task, agent) pair across trials."""

    task_name: str
    agent: str
    trials: int
    mean_score: float
    stddev_score: float
    ci_95: tuple[float, float]
    mean_wall_time: float
    stddev_wall_time: float
    mean_cost: float
    stddev_cost: float
    pass_rate: float
    consistency_score: float


@dataclass
class AgentAggregateStats:
    """Aggregated statistics for one agent across all benchmark tasks/trials."""

    agent: str
    task_count: int
    trial_count: int
    mean_score: float
    score_ci_95: tuple[float, float]
    win_rate: float
    cost_efficiency: Optional[float]
    reliability: float


_T_CRITICAL_95: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def _mean(values: list[float]) -> float:
    return _statistics.fmean(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return _statistics.stdev(values)


def _t_critical_95(sample_size: int) -> float:
    if sample_size <= 1:
        return 0.0
    df = sample_size - 1
    if df in _T_CRITICAL_95:
        return _T_CRITICAL_95[df]
    return 1.96


def _confidence_interval_95(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    sample_size = len(values)
    mean_val = _mean(values)
    if sample_size == 1:
        return (mean_val, mean_val)
    stddev = _stddev(values)
    margin = _t_critical_95(sample_size) * (stddev / math.sqrt(sample_size))
    return (mean_val - margin, mean_val + margin)


def _consistency_score(scores: list[float]) -> float:
    if not scores:
        return 0.0
    mean_score = _mean(scores)
    stddev_score = _stddev(scores)
    if mean_score == 0:
        return 1.0 if stddev_score == 0 else 0.0
    cv = stddev_score / abs(mean_score)
    return max(0.0, 1.0 - cv)


def compute_trial_stats(result: BenchmarkResult) -> list[TrialStats]:
    """Compute per-(task, agent) trial-level statistics from a benchmark run."""
    grouped: dict[tuple[str, str], list[TaskAgentResult]] = {}
    for row in result.results:
        grouped.setdefault((row.task_name, row.agent), []).append(row)

    stats: list[TrialStats] = []
    for task_name, agent in sorted(grouped.keys()):
        rows = grouped[(task_name, agent)]
        scores = [r.score for r in rows]
        wall_times = [r.wall_time for r in rows]
        costs = [r.cost_usd for r in rows if r.cost_usd is not None]

        stats.append(
            TrialStats(
                task_name=task_name,
                agent=agent,
                trials=len(rows),
                mean_score=_mean(scores),
                stddev_score=_stddev(scores),
                ci_95=_confidence_interval_95(scores),
                mean_wall_time=_mean(wall_times),
                stddev_wall_time=_stddev(wall_times),
                mean_cost=_mean(costs),
                stddev_cost=_stddev(costs),
                pass_rate=sum(1 for s in scores if s > 0) / len(scores) if scores else 0.0,
                consistency_score=_consistency_score(scores),
            )
        )
    return stats


def compute_aggregate_stats(
    result: BenchmarkResult,
    trial_stats: list[TrialStats] | None = None,
) -> list[AgentAggregateStats]:
    """Compute per-agent aggregate statistics from multi-trial benchmark results."""
    if trial_stats is None:
        trial_stats = compute_trial_stats(result)

    rows_by_agent: dict[str, list[TaskAgentResult]] = {}
    for row in result.results:
        rows_by_agent.setdefault(row.agent, []).append(row)

    stats_by_task: dict[str, list[TrialStats]] = {}
    for stat in trial_stats:
        stats_by_task.setdefault(stat.task_name, []).append(stat)

    wins_by_agent: dict[str, int] = {agent: 0 for agent in result.agents}
    for task_name in result.tasks:
        task_rows = stats_by_task.get(task_name, [])
        if not task_rows:
            continue
        max_mean = max(r.mean_score for r in task_rows)
        for row in task_rows:
            if row.mean_score == max_mean:
                wins_by_agent[row.agent] = wins_by_agent.get(row.agent, 0) + 1

    task_count = len(result.tasks)
    aggregate: list[AgentAggregateStats] = []
    for agent in result.agents:
        rows = rows_by_agent.get(agent, [])
        scores = [r.score for r in rows]
        costs = [r.cost_usd for r in rows if r.cost_usd is not None]
        mean_cost = _mean(costs)
        reliability = (
            sum(1 for r in rows if not r.timed_out and not r.error) / len(rows)
            if rows
            else 0.0
        )
        mean_score = _mean(scores)
        aggregate.append(
            AgentAggregateStats(
                agent=agent,
                task_count=task_count,
                trial_count=len(rows),
                mean_score=mean_score,
                score_ci_95=_confidence_interval_95(scores),
                win_rate=(wins_by_agent.get(agent, 0) / task_count) if task_count else 0.0,
                cost_efficiency=(mean_score / mean_cost) if mean_cost > 0 else None,
                reliability=reliability,
            )
        )

    aggregate.sort(key=lambda row: row.mean_score, reverse=True)
    return aggregate
