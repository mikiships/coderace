"""Aggregate statistics computation for benchmark results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from coderace.benchmark import BenchmarkResult, TaskAgentResult


@dataclass
class AgentBenchmarkStat:
    """Aggregate metrics for one agent across all benchmark tasks."""

    agent: str
    total_score: float
    avg_score: float
    pass_rate: float        # fraction of tasks with score > 0
    avg_time: float         # seconds
    total_cost: Optional[float]
    cost_efficiency: Optional[float]  # score per dollar
    win_count: int          # tasks where this agent scored highest
    task_count: int


@dataclass
class TaskBenchmarkStat:
    """Aggregate metrics for one task across all agents."""

    task_name: str
    best_agent: Optional[str]
    best_score: float
    avg_score: float
    fastest_agent: Optional[str]
    fastest_time: Optional[float]


@dataclass
class BenchmarkStats:
    """All aggregate statistics from a benchmark run."""

    agent_stats: list[AgentBenchmarkStat]
    task_stats: list[TaskBenchmarkStat]
    win_matrix: dict[str, dict[str, int]]  # win_matrix[task][agent] = 1 if winner


def compute_benchmark_stats(result: BenchmarkResult) -> BenchmarkStats:
    """Compute aggregate statistics from a BenchmarkResult."""
    agents = result.agents
    tasks = result.tasks

    # Build lookup: (task, agent) -> TaskAgentResult
    lookup: dict[tuple[str, str], TaskAgentResult] = {}
    for r in result.results:
        lookup[(r.task_name, r.agent)] = r

    # Win matrix: for each task, which agent scored highest?
    win_matrix: dict[str, dict[str, int]] = {}
    for task_name in tasks:
        task_scores: dict[str, float] = {}
        for agent in agents:
            r = lookup.get((task_name, agent))
            if r is not None:
                task_scores[agent] = r.score

        if task_scores:
            max_score = max(task_scores.values())
            winners = {a for a, s in task_scores.items() if s == max_score and s > 0}
        else:
            winners = set()

        win_matrix[task_name] = {a: (1 if a in winners else 0) for a in agents}

    # Per-agent stats
    agent_stats: list[AgentBenchmarkStat] = []
    for agent in agents:
        agent_results = [lookup[(t, agent)] for t in tasks if (t, agent) in lookup]
        task_count = len(agent_results)

        if task_count == 0:
            agent_stats.append(AgentBenchmarkStat(
                agent=agent, total_score=0.0, avg_score=0.0,
                pass_rate=0.0, avg_time=0.0, total_cost=None,
                cost_efficiency=None, win_count=0, task_count=0,
            ))
            continue

        scores = [r.score for r in agent_results]
        total_score = sum(scores)
        avg_score = total_score / task_count
        pass_rate = sum(1 for s in scores if s > 0) / task_count
        avg_time = sum(r.wall_time for r in agent_results) / task_count

        costs = [r.cost_usd for r in agent_results if r.cost_usd is not None]
        total_cost = sum(costs) if costs else None
        if total_cost is not None and total_cost > 0:
            cost_efficiency = total_score / total_cost
        else:
            cost_efficiency = None

        win_count = sum(win_matrix[t].get(agent, 0) for t in tasks if t in win_matrix)

        agent_stats.append(AgentBenchmarkStat(
            agent=agent,
            total_score=total_score,
            avg_score=avg_score,
            pass_rate=pass_rate,
            avg_time=avg_time,
            total_cost=total_cost,
            cost_efficiency=cost_efficiency,
            win_count=win_count,
            task_count=task_count,
        ))

    # Sort by total score descending
    agent_stats.sort(key=lambda s: s.total_score, reverse=True)

    # Per-task stats
    task_stats: list[TaskBenchmarkStat] = []
    for task_name in tasks:
        task_results = [(a, lookup[(task_name, a)]) for a in agents if (task_name, a) in lookup]

        if not task_results:
            task_stats.append(TaskBenchmarkStat(
                task_name=task_name, best_agent=None, best_score=0.0,
                avg_score=0.0, fastest_agent=None, fastest_time=None,
            ))
            continue

        best = max(task_results, key=lambda x: x[1].score)
        avg_score = sum(r.score for _, r in task_results) / len(task_results)

        timed_results = [(a, r) for a, r in task_results if not r.timed_out and r.wall_time > 0]
        if timed_results:
            fastest = min(timed_results, key=lambda x: x[1].wall_time)
            fastest_agent = fastest[0]
            fastest_time = fastest[1].wall_time
        else:
            fastest_agent = None
            fastest_time = None

        task_stats.append(TaskBenchmarkStat(
            task_name=task_name,
            best_agent=best[0],
            best_score=best[1].score,
            avg_score=avg_score,
            fastest_agent=fastest_agent,
            fastest_time=fastest_time,
        ))

    return BenchmarkStats(
        agent_stats=agent_stats,
        task_stats=task_stats,
        win_matrix=win_matrix,
    )
