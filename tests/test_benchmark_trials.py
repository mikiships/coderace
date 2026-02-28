"""Tests for benchmark trials mode (D1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from coderace.benchmark import (
    BenchmarkResult,
    TaskAgentResult,
    _format_trial_status,
    run_benchmark,
)
from coderace.benchmark_stats import compute_benchmark_stats
from coderace.cli import app
from coderace.store import ResultStore


runner = CliRunner()


class _FakeTask:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.description = "fake benchmark task"
        self.test_command = "python3 -m pytest -q"
        self.lint_command = None
        self.verify_command = None
        self.verify_files = None

    def get_weights(self) -> dict[str, float]:
        return {}


def _make_trial_result(task_name: str, agent: str, trial_number: int) -> TaskAgentResult:
    return TaskAgentResult(
        task_name=task_name,
        agent=agent,
        score=80.0 + trial_number,
        wall_time=10.0 + trial_number,
        tests_pass=True,
        exit_clean=True,
        lint_clean=True,
        timed_out=False,
        trial_number=trial_number,
    )


def test_single_trial_backward_compatibility(tmp_path: Path) -> None:
    fake_task = _FakeTask(tmp_path)
    calls: list[tuple[int, int]] = []

    def fake_run_task_sequential(
        task,
        task_name,
        agents,
        base_ref,
        timeout,
        result,
        progress_callback,
        trial_number,
        total_trials,
    ) -> None:
        calls.append((trial_number, total_trials))
        for agent in agents:
            result.results.append(_make_trial_result(task_name, agent, trial_number))

    with (
        patch("coderace.builtins.get_builtin_path", return_value=tmp_path / "task.yaml"),
        patch("coderace.task.load_task", return_value=fake_task),
        patch("coderace.git_ops.get_current_ref", return_value="main"),
        patch("coderace.benchmark._run_task_sequential", side_effect=fake_run_task_sequential),
    ):
        bench = run_benchmark(agents=["claude", "codex"], tasks=["fibonacci"])

    assert bench.trials == 1
    assert calls == [(1, 1)]
    assert len(bench.results) == 2
    assert all(r.trial_number == 1 for r in bench.results)


def test_multi_trial_execution_runs_all_trials(tmp_path: Path) -> None:
    fake_task = _FakeTask(tmp_path)
    calls: list[tuple[int, int]] = []

    def fake_run_task_sequential(
        task,
        task_name,
        agents,
        base_ref,
        timeout,
        result,
        progress_callback,
        trial_number,
        total_trials,
    ) -> None:
        calls.append((trial_number, total_trials))
        for agent in agents:
            result.results.append(_make_trial_result(task_name, agent, trial_number))

    with (
        patch("coderace.builtins.get_builtin_path", return_value=tmp_path / "task.yaml"),
        patch("coderace.task.load_task", return_value=fake_task),
        patch("coderace.git_ops.get_current_ref", return_value="main"),
        patch("coderace.benchmark._run_task_sequential", side_effect=fake_run_task_sequential),
    ):
        bench = run_benchmark(
            agents=["claude", "codex"],
            tasks=["fibonacci"],
            trials=3,
        )

    assert bench.trials == 3
    assert calls == [(1, 3), (2, 3), (3, 3)]
    assert len(bench.results) == 6
    assert sorted(r.trial_number for r in bench.results) == [1, 1, 2, 2, 3, 3]


def test_progress_status_includes_trial_number_for_multi_trial() -> None:
    assert _format_trial_status("running", 2, 5) == "Trial 2/5 | running"
    assert _format_trial_status("running", 1, 1) == "running"


def test_benchmark_cli_trials_flag_forwards_to_runner() -> None:
    captured: dict[str, object] = {}

    def fake_run_benchmark(*, agents, tasks, timeout, parallel, trials, progress_callback):
        captured["agents"] = agents
        captured["tasks"] = tasks
        captured["timeout"] = timeout
        captured["parallel"] = parallel
        captured["trials"] = trials
        bench = BenchmarkResult(
            benchmark_id="bench-test-trials",
            agents=list(agents),
            tasks=list(tasks),
            trials=trials,
            results=[],
        )
        bench.finish()
        return bench

    with patch("coderace.benchmark.run_benchmark", side_effect=fake_run_benchmark):
        result = runner.invoke(
            app,
            [
                "benchmark",
                "--agents",
                "claude",
                "--tasks",
                "fibonacci",
                "--trials",
                "4",
                "--no-save",
            ],
        )

    assert result.exit_code == 0
    assert captured["trials"] == 4
    assert captured["agents"] == ["claude"]
    assert captured["tasks"] == ["fibonacci"]


def test_benchmark_dry_run_count_includes_trials() -> None:
    result = runner.invoke(
        app,
        [
            "benchmark",
            "--agents",
            "claude,codex",
            "--tasks",
            "fibonacci",
            "--trials",
            "3",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "6 runs" in result.output


def test_save_benchmark_stores_trial_number(tmp_path: Path) -> None:
    store = ResultStore(db_path=tmp_path / "results.db")
    try:
        bench = BenchmarkResult(
            benchmark_id="bench-trials-store",
            agents=["claude"],
            tasks=["fibonacci"],
            trials=2,
            results=[
                _make_trial_result("fibonacci", "claude", 1),
                _make_trial_result("fibonacci", "claude", 2),
            ],
        )
        bench.finish()
        stats = compute_benchmark_stats(bench)
        store.save_benchmark(bench, stats)

        detail = store.get_benchmark("bench-trials-store")
        assert detail is not None
        assert [r["trial_number"] for r in detail["results"]] == [1, 2]
    finally:
        store.close()
