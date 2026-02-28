"""Standardized benchmark export format."""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from coderace import __version__
from coderace.benchmark import BenchmarkResult, TaskAgentResult
from coderace.statistics import compute_aggregate_stats, compute_trial_stats


def collect_system_info() -> dict[str, str]:
    """Collect basic runtime system info for benchmark exports."""
    cpu = platform.processor() or platform.machine() or "unknown"
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu": cpu,
    }


def export_benchmark_json(
    benchmark_result: BenchmarkResult,
    output_path: str | Path,
    *,
    timeout: int,
    trials: int,
    tasks: list[str],
    agents: list[str],
    elo_ratings: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Export benchmark results to the standardized JSON schema."""
    trial_stats = compute_trial_stats(benchmark_result)
    aggregate_stats = compute_aggregate_stats(benchmark_result, trial_stats=trial_stats)

    rows_by_pair: dict[tuple[str, str], list[TaskAgentResult]] = {}
    for row in benchmark_result.results:
        rows_by_pair.setdefault((row.task_name, row.agent), []).append(row)

    result_rows: list[dict[str, Any]] = []
    for stat in trial_stats:
        pair_rows = sorted(
            rows_by_pair.get((stat.task_name, stat.agent), []),
            key=lambda row: row.trial_number,
        )
        per_trial = [
            {
                "trial_number": row.trial_number,
                "score": row.score,
                "wall_time": row.wall_time,
                "cost_usd": row.cost_usd,
                "timed_out": row.timed_out,
                "error": row.error,
                "tests_pass": row.tests_pass,
                "exit_clean": row.exit_clean,
                "lint_clean": row.lint_clean,
            }
            for row in pair_rows
        ]
        result_rows.append(
            {
                "task": stat.task_name,
                "agent": stat.agent,
                "trials": stat.trials,
                "mean_score": stat.mean_score,
                "stddev_score": stat.stddev_score,
                "ci_95": [stat.ci_95[0], stat.ci_95[1]],
                "mean_time": stat.mean_wall_time,
                "mean_cost": stat.mean_cost,
                "pass_rate": stat.pass_rate,
                "consistency_score": stat.consistency_score,
                "per_trial": per_trial,
            }
        )

    summary = {
        "agents": [
            {
                "agent": row.agent,
                "task_count": row.task_count,
                "trial_count": row.trial_count,
                "mean_score": row.mean_score,
                "score_ci_95": [row.score_ci_95[0], row.score_ci_95[1]],
                "win_rate": row.win_rate,
                "cost_efficiency": row.cost_efficiency,
                "reliability": row.reliability,
            }
            for row in aggregate_stats
        ]
    }

    payload = {
        "coderace_version": __version__,
        "benchmark_id": benchmark_result.benchmark_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "system": collect_system_info(),
        "config": {
            "trials": trials,
            "timeout": timeout,
            "tasks": list(tasks),
            "agents": list(agents),
        },
        "results": result_rows,
        "elo_ratings": dict(elo_ratings or {}),
        "summary": summary,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
