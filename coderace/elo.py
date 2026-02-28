"""Persistent ELO ratings for benchmark participants."""

from __future__ import annotations

from dataclasses import dataclass

from coderace.benchmark import BenchmarkResult
from coderace.statistics import compute_trial_stats

INITIAL_RATING = 1500.0
K_FACTOR = 32.0
DRAW_MARGIN = 1.0


@dataclass
class RatingUpdate:
    """Rating snapshot before/after applying a benchmark run."""

    before: dict[str, float]
    after: dict[str, float]
    deltas: dict[str, float]


def expected_score(rating_a: float, rating_b: float) -> float:
    """Expected score for player A against player B."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_pair_ratings(
    rating_a: float,
    rating_b: float,
    actual_a: float,
    k_factor: float = K_FACTOR,
) -> tuple[float, float]:
    """Apply one ELO match and return updated ratings for (A, B)."""
    expected_a = expected_score(rating_a, rating_b)
    expected_b = 1.0 - expected_a
    actual_b = 1.0 - actual_a
    new_a = rating_a + k_factor * (actual_a - expected_a)
    new_b = rating_b + k_factor * (actual_b - expected_b)
    return new_a, new_b


def update_ratings(
    benchmark_result: BenchmarkResult,
    current_ratings: dict[str, float] | None = None,
    *,
    initial_rating: float = INITIAL_RATING,
    k_factor: float = K_FACTOR,
    draw_margin: float = DRAW_MARGIN,
) -> RatingUpdate:
    """Update ELO ratings from benchmark outcomes.

    Each task is treated as a round-robin match:
    - Use mean score per (task, agent) across trials
    - Compare each pair of agents on that task
    - Difference <= draw_margin is a draw
    """
    current = dict(current_ratings or {})
    ratings = {agent: current.get(agent, initial_rating) for agent in set(current) | set(benchmark_result.agents)}
    before = dict(ratings)

    trial_stats = compute_trial_stats(benchmark_result)
    scores_by_task: dict[str, dict[str, float]] = {}
    for stat in trial_stats:
        scores_by_task.setdefault(stat.task_name, {})[stat.agent] = stat.mean_score

    for task_name in benchmark_result.tasks:
        task_scores = scores_by_task.get(task_name, {})
        task_agents = sorted(task_scores.keys())
        for idx, agent_a in enumerate(task_agents):
            for agent_b in task_agents[idx + 1:]:
                score_a = task_scores[agent_a]
                score_b = task_scores[agent_b]
                if abs(score_a - score_b) <= draw_margin:
                    actual_a = 0.5
                elif score_a > score_b:
                    actual_a = 1.0
                else:
                    actual_a = 0.0
                new_a, new_b = update_pair_ratings(
                    ratings[agent_a],
                    ratings[agent_b],
                    actual_a,
                    k_factor=k_factor,
                )
                ratings[agent_a] = new_a
                ratings[agent_b] = new_b

    deltas = {
        agent: ratings[agent] - before.get(agent, initial_rating)
        for agent in ratings
    }
    return RatingUpdate(before=before, after=ratings, deltas=deltas)
