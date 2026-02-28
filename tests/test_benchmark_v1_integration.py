"""Integration and edge-case tests for v1.0 statistical benchmarking flow."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from coderace.benchmark import BenchmarkResult, TaskAgentResult
from coderace.cli import app
from coderace.elo import update_ratings
from coderace.export import export_benchmark_json
from coderace.statistics import compute_aggregate_stats
from coderace.store import ResultStore


runner = CliRunner()


def _row(
    task: str,
    agent: str,
    trial: int,
    score: float,
    *,
    timed_out: bool = False,
    error: str | None = None,
) -> TaskAgentResult:
    return TaskAgentResult(
        task_name=task,
        agent=agent,
        score=score,
        wall_time=10.0 + trial,
        tests_pass=score > 0,
        exit_clean=error is None,
        lint_clean=score > 0,
        timed_out=timed_out,
        trial_number=trial,
        cost_usd=0.01 + 0.001 * trial if score > 0 else None,
        error=error,
    )


def _benchmark_result(
    *,
    tasks: list[str],
    agents: list[str],
    trials: int,
    failing_agent: str | None = None,
) -> BenchmarkResult:
    rows: list[TaskAgentResult] = []
    for task_idx, task in enumerate(tasks):
        for agent_idx, agent in enumerate(agents):
            for trial in range(1, trials + 1):
                if failing_agent == agent:
                    rows.append(
                        _row(
                            task,
                            agent,
                            trial,
                            0.0,
                            timed_out=True,
                            error="agent failed",
                        )
                    )
                else:
                    base = 70.0 + (task_idx * 5.0) - (agent_idx * 3.0)
                    rows.append(_row(task, agent, trial, base + trial))
    bench = BenchmarkResult(
        benchmark_id="bench-v1-integration",
        tasks=tasks,
        agents=agents,
        trials=trials,
        results=rows,
    )
    bench.finish()
    return bench


def test_integration_trials3_two_tasks_stats_elo_export(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "results.db"
    export_path = tmp_path / "benchmark-export.json"
    monkeypatch.setenv("CODERACE_DB", str(db_path))

    benchmark_result = _benchmark_result(
        tasks=["fibonacci", "json-parser"],
        agents=["claude", "codex"],
        trials=3,
    )

    with patch("coderace.benchmark.run_benchmark", return_value=benchmark_result):
        result = runner.invoke(
            app,
            [
                "benchmark",
                "--agents",
                "claude,codex",
                "--tasks",
                "fibonacci,json-parser",
                "--trials",
                "3",
                "--export",
                str(export_path),
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(export_path.read_text())
    assert payload["config"]["trials"] == 3
    assert len(payload["results"]) == 4  # 2 tasks x 2 agents
    assert all(len(row["per_trial"]) == 3 for row in payload["results"])
    assert set(payload["elo_ratings"]) == {"claude", "codex"}

    store = ResultStore(db_path=db_path)
    try:
        ratings = store.get_elo_ratings()
        benchmarks = store.get_benchmarks(limit=5)
    finally:
        store.close()
    assert set(ratings) == {"claude", "codex"}
    assert benchmarks[0]["benchmark_id"] == "bench-v1-integration"


def test_edge_case_single_agent_elo_stays_at_initial_rating() -> None:
    bench = _benchmark_result(
        tasks=["fibonacci"],
        agents=["claude"],
        trials=3,
    )
    rating_update = update_ratings(bench, current_ratings={})
    assert rating_update.after["claude"] == 1500.0


def test_edge_case_single_task_single_trial_export(tmp_path: Path) -> None:
    bench = _benchmark_result(
        tasks=["fibonacci"],
        agents=["claude"],
        trials=1,
    )
    payload = export_benchmark_json(
        benchmark_result=bench,
        output_path=tmp_path / "single.json",
        timeout=300,
        trials=1,
        tasks=["fibonacci"],
        agents=["claude"],
        elo_ratings={"claude": 1500.0},
    )
    assert payload["config"]["trials"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["ci_95"][0] == payload["results"][0]["ci_95"][1]


def test_edge_case_agent_always_fails_has_zero_reliability() -> None:
    bench = _benchmark_result(
        tasks=["fibonacci"],
        agents=["claude", "codex"],
        trials=3,
        failing_agent="codex",
    )
    aggregates = {row.agent: row for row in compute_aggregate_stats(bench)}
    assert aggregates["codex"].reliability == 0.0
