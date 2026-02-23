"""Statistical aggregation for multi-run results."""

from __future__ import annotations

import math
from dataclasses import dataclass

from coderace.types import Score


@dataclass
class AgentStats:
    """Aggregated statistics for an agent across multiple runs."""

    agent: str
    runs: int
    score_mean: float
    score_stddev: float
    time_mean: float
    time_stddev: float
    lines_mean: float
    lines_stddev: float
    tests_pass_rate: float  # 0.0 - 1.0
    exit_clean_rate: float
    lint_clean_rate: float
    per_run_scores: list[float]


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def aggregate_runs(
    all_run_scores: list[list[Score]],
) -> list[AgentStats]:
    """Aggregate scores across multiple runs per agent.

    Args:
        all_run_scores: list of per-run score lists.
            Each inner list has one Score per agent that ran.

    Returns:
        AgentStats for each agent, sorted by score_mean descending.
    """
    # Group scores by agent
    agent_scores: dict[str, list[Score]] = {}
    for run_scores in all_run_scores:
        for score in run_scores:
            agent_scores.setdefault(score.agent, []).append(score)

    stats = []
    for agent, scores in agent_scores.items():
        composites = [s.composite for s in scores]
        times = [s.breakdown.wall_time for s in scores]
        lines = [float(s.breakdown.lines_changed) for s in scores]

        stats.append(
            AgentStats(
                agent=agent,
                runs=len(scores),
                score_mean=round(_mean(composites), 1),
                score_stddev=round(_stddev(composites), 1),
                time_mean=round(_mean(times), 1),
                time_stddev=round(_stddev(times), 1),
                lines_mean=round(_mean(lines), 1),
                lines_stddev=round(_stddev(lines), 1),
                tests_pass_rate=round(
                    sum(1 for s in scores if s.breakdown.tests_pass)
                    / len(scores),
                    2,
                ),
                exit_clean_rate=round(
                    sum(1 for s in scores if s.breakdown.exit_clean)
                    / len(scores),
                    2,
                ),
                lint_clean_rate=round(
                    sum(1 for s in scores if s.breakdown.lint_clean)
                    / len(scores),
                    2,
                ),
                per_run_scores=composites,
            )
        )

    stats.sort(key=lambda s: s.score_mean, reverse=True)
    return stats
