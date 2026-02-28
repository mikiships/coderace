"""Tests for benchmark export format and statistical report rendering (D4)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from coderace.benchmark import BenchmarkResult, TaskAgentResult
from coderace.benchmark_report import render_benchmark_html, render_benchmark_markdown
from coderace.benchmark_stats import compute_benchmark_stats
from coderace.cli import app
from coderace.export import collect_system_info, export_benchmark_json


runner = CliRunner()


def _row(task: str, agent: str, trial: int, score: float, wall: float, cost: float) -> TaskAgentResult:
    return TaskAgentResult(
        task_name=task,
        agent=agent,
        score=score,
        wall_time=wall,
        tests_pass=True,
        exit_clean=True,
        lint_clean=True,
        timed_out=False,
        trial_number=trial,
        cost_usd=cost,
    )


def _benchmark_trials() -> BenchmarkResult:
    rows = [
        _row("fibonacci", "claude", 1, 90.0, 10.0, 0.02),
        _row("fibonacci", "claude", 2, 85.0, 12.0, 0.025),
        _row("fibonacci", "codex", 1, 80.0, 11.0, 0.015),
        _row("fibonacci", "codex", 2, 79.0, 13.0, 0.017),
    ]
    bench = BenchmarkResult(
        benchmark_id="bench-export-001",
        agents=["claude", "codex"],
        tasks=["fibonacci"],
        trials=2,
        results=rows,
    )
    bench.finish()
    return bench


def _benchmark_single_trial() -> BenchmarkResult:
    rows = [
        _row("fibonacci", "claude", 1, 90.0, 10.0, 0.02),
        _row("fibonacci", "codex", 1, 80.0, 11.0, 0.015),
    ]
    bench = BenchmarkResult(
        benchmark_id="bench-export-002",
        agents=["claude", "codex"],
        tasks=["fibonacci"],
        trials=1,
        results=rows,
    )
    bench.finish()
    return bench


def test_collect_system_info_includes_required_keys() -> None:
    info = collect_system_info()
    assert set(info.keys()) == {"os", "python", "cpu"}
    assert info["os"]
    assert info["python"]
    assert info["cpu"]


def test_export_benchmark_json_structure(tmp_path: Path) -> None:
    bench = _benchmark_trials()
    export_path = tmp_path / "benchmark.json"
    payload = export_benchmark_json(
        benchmark_result=bench,
        output_path=export_path,
        timeout=300,
        trials=2,
        tasks=bench.tasks,
        agents=bench.agents,
        elo_ratings={"claude": 1516.0, "codex": 1484.0},
    )

    assert export_path.exists()
    loaded = json.loads(export_path.read_text())
    assert loaded["benchmark_id"] == "bench-export-001"
    assert loaded["config"]["trials"] == 2
    assert loaded["system"]["os"]
    assert loaded["results"][0]["task"] == "fibonacci"
    assert loaded["results"][0]["agent"] in {"claude", "codex"}
    assert "ci_95" in loaded["results"][0]
    assert "per_trial" in loaded["results"][0]
    assert loaded["elo_ratings"]["claude"] == 1516.0
    assert payload["summary"]["agents"]


def test_markdown_report_with_trials_shows_stat_columns() -> None:
    bench = _benchmark_trials()
    stats = compute_benchmark_stats(bench)
    report = render_benchmark_markdown(
        bench,
        stats,
        elo_ratings={"claude": 1516.0, "codex": 1484.0},
    )
    assert "CI (95%)" in report
    assert "Consistency" in report
    assert "Reliability" in report
    assert "+/-" in report


def test_markdown_report_single_trial_backward_compatible() -> None:
    bench = _benchmark_single_trial()
    stats = compute_benchmark_stats(bench)
    report = render_benchmark_markdown(bench, stats)
    assert "| Task | claude | codex |" in report
    assert "CI (95%)" not in report


def test_report_includes_elo_ratings_sections() -> None:
    bench = _benchmark_single_trial()
    stats = compute_benchmark_stats(bench)
    elo = {"claude": 1510.0, "codex": 1490.0}
    markdown = render_benchmark_markdown(bench, stats, elo_ratings=elo)
    html = render_benchmark_html(bench, stats, elo_ratings=elo)
    assert "ELO Ratings" in markdown
    assert "ELO Ratings" in html
    assert "1510.0" in markdown


def test_benchmark_cli_export_flag_writes_json(tmp_path: Path) -> None:
    bench = _benchmark_trials()
    export_path = tmp_path / "cli-export.json"

    def fake_run_benchmark(*, agents, tasks, timeout, parallel, trials, progress_callback):
        return bench

    rating_update = SimpleNamespace(
        before={"claude": 1500.0, "codex": 1500.0},
        after={"claude": 1516.0, "codex": 1484.0},
    )

    with (
        patch("coderace.benchmark.run_benchmark", side_effect=fake_run_benchmark),
        patch("coderace.commands.benchmark._update_benchmark_ratings", return_value=rating_update),
    ):
        result = runner.invoke(
            app,
            [
                "benchmark",
                "--agents",
                "claude,codex",
                "--tasks",
                "fibonacci",
                "--trials",
                "2",
                "--export",
                str(export_path),
                "--no-save",
            ],
        )

    assert result.exit_code == 0
    data = json.loads(export_path.read_text())
    assert data["config"]["trials"] == 2
    assert data["elo_ratings"]["claude"] == 1516.0
