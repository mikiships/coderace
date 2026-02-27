"""Tests for the benchmark suite (D1-D4)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coderace.benchmark import (
    BenchmarkResult,
    TaskAgentResult,
    _make_benchmark_id,
    list_benchmark_tasks,
)
from coderace.benchmark_stats import (
    AgentBenchmarkStat,
    BenchmarkStats,
    TaskBenchmarkStat,
    compute_benchmark_stats,
)
from coderace.benchmark_report import (
    render_benchmark_html,
    render_benchmark_markdown,
    render_benchmark_terminal,
)


# ---------------------------------------------------------------------------
# D1: BenchmarkResult dataclass
# ---------------------------------------------------------------------------

class TestBenchmarkResult:
    def test_make_benchmark_id(self):
        bid = _make_benchmark_id()
        assert bid.startswith("bench-")
        assert len(bid) > 10

    def test_benchmark_result_defaults(self):
        br = BenchmarkResult(
            benchmark_id="bench-test",
            agents=["claude", "codex"],
            tasks=["fibonacci"],
        )
        assert br.agents == ["claude", "codex"]
        assert br.tasks == ["fibonacci"]
        assert br.results == []
        assert br.finished_at is None

    def test_benchmark_result_get(self):
        tar = TaskAgentResult(
            task_name="fibonacci",
            agent="claude",
            score=95.0,
            wall_time=3.2,
            tests_pass=True,
            exit_clean=True,
            lint_clean=True,
            timed_out=False,
        )
        br = BenchmarkResult(
            benchmark_id="bench-test",
            agents=["claude"],
            tasks=["fibonacci"],
            results=[tar],
        )
        assert br.get("fibonacci", "claude") is tar
        assert br.get("fibonacci", "codex") is None
        assert br.get("json-parser", "claude") is None

    def test_benchmark_result_finish(self):
        br = BenchmarkResult(
            benchmark_id="bench-test",
            agents=["claude"],
            tasks=["fibonacci"],
        )
        assert br.finished_at is None
        br.finish()
        assert br.finished_at is not None
        assert br.elapsed >= 0

    def test_task_agent_result_defaults(self):
        tar = TaskAgentResult(
            task_name="fibonacci",
            agent="claude",
            score=80.0,
            wall_time=5.0,
            tests_pass=True,
            exit_clean=True,
            lint_clean=False,
            timed_out=False,
        )
        assert tar.cost_usd is None
        assert tar.error is None


class TestListBenchmarkTasks:
    def test_returns_list(self):
        tasks = list_benchmark_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_filter_by_difficulty_easy(self):
        easy_tasks = list_benchmark_tasks(difficulty=["easy"])
        all_tasks = list_benchmark_tasks()
        assert len(easy_tasks) <= len(all_tasks)
        assert len(easy_tasks) >= 1

    def test_filter_by_difficulty_empty(self):
        # "impossible" difficulty -> empty
        result = list_benchmark_tasks(difficulty=["impossible"])
        assert result == []

    def test_filter_multiple_difficulties(self):
        easy_medium = list_benchmark_tasks(difficulty=["easy", "medium"])
        all_tasks = list_benchmark_tasks()
        assert len(easy_medium) <= len(all_tasks)


# ---------------------------------------------------------------------------
# D2: Aggregate statistics
# ---------------------------------------------------------------------------

def _make_sample_benchmark():
    """Build a BenchmarkResult with mock data for 2 agents x 2 tasks."""
    results = [
        TaskAgentResult("fibonacci", "claude", score=100.0, wall_time=3.0,
                        tests_pass=True, exit_clean=True, lint_clean=True, timed_out=False, cost_usd=0.01),
        TaskAgentResult("fibonacci", "codex", score=80.0, wall_time=5.0,
                        tests_pass=True, exit_clean=True, lint_clean=False, timed_out=False, cost_usd=0.02),
        TaskAgentResult("json-parser", "claude", score=60.0, wall_time=10.0,
                        tests_pass=True, exit_clean=False, lint_clean=False, timed_out=False, cost_usd=0.03),
        TaskAgentResult("json-parser", "codex", score=90.0, wall_time=7.0,
                        tests_pass=True, exit_clean=True, lint_clean=True, timed_out=False, cost_usd=0.015),
    ]
    br = BenchmarkResult(
        benchmark_id="bench-test-001",
        agents=["claude", "codex"],
        tasks=["fibonacci", "json-parser"],
        results=results,
    )
    br.finish()
    return br


class TestComputeBenchmarkStats:
    def setup_method(self):
        self.br = _make_sample_benchmark()
        self.stats = compute_benchmark_stats(self.br)

    def test_returns_benchmark_stats(self):
        assert isinstance(self.stats, BenchmarkStats)

    def test_agent_stats_count(self):
        assert len(self.stats.agent_stats) == 2

    def test_agent_total_score(self):
        stat_map = {s.agent: s for s in self.stats.agent_stats}
        # claude: 100 + 60 = 160
        assert stat_map["claude"].total_score == pytest.approx(160.0)
        # codex: 80 + 90 = 170
        assert stat_map["codex"].total_score == pytest.approx(170.0)

    def test_agent_stats_sorted_by_total_score(self):
        # codex (170) > claude (160)
        assert self.stats.agent_stats[0].agent == "codex"

    def test_agent_avg_score(self):
        stat_map = {s.agent: s for s in self.stats.agent_stats}
        assert stat_map["claude"].avg_score == pytest.approx(80.0)
        assert stat_map["codex"].avg_score == pytest.approx(85.0)

    def test_agent_pass_rate(self):
        stat_map = {s.agent: s for s in self.stats.agent_stats}
        # Both agents scored > 0 on both tasks
        assert stat_map["claude"].pass_rate == pytest.approx(1.0)
        assert stat_map["codex"].pass_rate == pytest.approx(1.0)

    def test_agent_win_count(self):
        stat_map = {s.agent: s for s in self.stats.agent_stats}
        # claude wins fibonacci (100 > 80), codex wins json-parser (90 > 60)
        assert stat_map["claude"].win_count == 1
        assert stat_map["codex"].win_count == 1

    def test_agent_total_cost(self):
        stat_map = {s.agent: s for s in self.stats.agent_stats}
        assert stat_map["claude"].total_cost == pytest.approx(0.04)
        assert stat_map["codex"].total_cost == pytest.approx(0.035)

    def test_task_stats_count(self):
        assert len(self.stats.task_stats) == 2

    def test_task_best_agent(self):
        ts_map = {ts.task_name: ts for ts in self.stats.task_stats}
        assert ts_map["fibonacci"].best_agent == "claude"
        assert ts_map["json-parser"].best_agent == "codex"

    def test_task_fastest_agent(self):
        ts_map = {ts.task_name: ts for ts in self.stats.task_stats}
        assert ts_map["fibonacci"].fastest_agent == "claude"
        assert ts_map["json-parser"].fastest_agent == "codex"

    def test_win_matrix_structure(self):
        wm = self.stats.win_matrix
        assert "fibonacci" in wm
        assert "json-parser" in wm
        assert wm["fibonacci"]["claude"] == 1
        assert wm["fibonacci"]["codex"] == 0
        assert wm["json-parser"]["claude"] == 0
        assert wm["json-parser"]["codex"] == 1

    def test_zero_score_not_counted_as_win(self):
        """A zero score should not count as a win."""
        results = [
            TaskAgentResult("fibonacci", "claude", score=0.0, wall_time=3.0,
                            tests_pass=False, exit_clean=False, lint_clean=False, timed_out=False),
            TaskAgentResult("fibonacci", "codex", score=0.0, wall_time=5.0,
                            tests_pass=False, exit_clean=False, lint_clean=False, timed_out=False),
        ]
        br = BenchmarkResult("bench-zero", ["claude", "codex"], ["fibonacci"], results=results)
        stats = compute_benchmark_stats(br)
        wm = stats.win_matrix
        assert wm["fibonacci"]["claude"] == 0
        assert wm["fibonacci"]["codex"] == 0

    def test_single_agent_single_task(self):
        results = [
            TaskAgentResult("fibonacci", "claude", score=75.0, wall_time=4.0,
                            tests_pass=True, exit_clean=True, lint_clean=True, timed_out=False),
        ]
        br = BenchmarkResult("bench-solo", ["claude"], ["fibonacci"], results=results)
        stats = compute_benchmark_stats(br)
        assert len(stats.agent_stats) == 1
        assert stats.agent_stats[0].agent == "claude"
        assert stats.agent_stats[0].win_count == 1

    def test_no_cost_data(self):
        """When cost_usd is None, total_cost should be None."""
        results = [
            TaskAgentResult("fibonacci", "claude", score=50.0, wall_time=3.0,
                            tests_pass=True, exit_clean=True, lint_clean=True, timed_out=False, cost_usd=None),
        ]
        br = BenchmarkResult("bench-nocost", ["claude"], ["fibonacci"], results=results)
        stats = compute_benchmark_stats(br)
        assert stats.agent_stats[0].total_cost is None
        assert stats.agent_stats[0].cost_efficiency is None


# ---------------------------------------------------------------------------
# D3: Report formats
# ---------------------------------------------------------------------------

class TestBenchmarkReports:
    def setup_method(self):
        self.br = _make_sample_benchmark()
        self.stats = compute_benchmark_stats(self.br)

    def test_terminal_output_no_crash(self, capsys):
        from rich.console import Console
        console = Console(no_color=True)
        render_benchmark_terminal(self.br, self.stats, console)
        # No assertion needed, just confirming it doesn't crash

    def test_markdown_output_structure(self):
        md = render_benchmark_markdown(self.br, self.stats)
        assert "| Task |" in md
        assert "fibonacci" in md
        assert "json-parser" in md
        assert "claude" in md
        assert "codex" in md
        assert "TOTAL" in md
        assert "Win Rate" in md

    def test_markdown_contains_benchmark_id(self):
        md = render_benchmark_markdown(self.br, self.stats)
        assert "bench-test-001" in md

    def test_markdown_task_insights(self):
        md = render_benchmark_markdown(self.br, self.stats)
        assert "Task Insights" in md

    def test_html_output_structure(self):
        html = render_benchmark_html(self.br, self.stats)
        assert "<!DOCTYPE html>" in html
        assert "fibonacci" in html
        assert "json-parser" in html
        assert "claude" in html
        assert "codex" in html
        assert "bench-test-001" in html

    def test_html_is_self_contained(self):
        html = render_benchmark_html(self.br, self.stats)
        assert "<style>" in html
        assert "</html>" in html

    def test_html_shows_winner(self):
        html = render_benchmark_html(self.br, self.stats)
        assert "Winner" in html
        # codex has higher total score
        assert "codex" in html

    def test_single_agent_report(self):
        results = [
            TaskAgentResult("fibonacci", "claude", score=90.0, wall_time=3.0,
                            tests_pass=True, exit_clean=True, lint_clean=True, timed_out=False),
        ]
        br = BenchmarkResult("bench-single", ["claude"], ["fibonacci"], results=results)
        stats = compute_benchmark_stats(br)
        md = render_benchmark_markdown(br, stats)
        assert "claude" in md
        assert "90.0" in md

    def test_timed_out_result_in_markdown(self):
        results = [
            TaskAgentResult("fibonacci", "claude", score=0.0, wall_time=300.0,
                            tests_pass=False, exit_clean=False, lint_clean=False, timed_out=True),
            TaskAgentResult("fibonacci", "codex", score=80.0, wall_time=5.0,
                            tests_pass=True, exit_clean=True, lint_clean=True, timed_out=False),
        ]
        br = BenchmarkResult("bench-timeout", ["claude", "codex"], ["fibonacci"], results=results)
        stats = compute_benchmark_stats(br)
        md = render_benchmark_markdown(br, stats)
        assert "TIMEOUT" in md

    def test_error_result_in_markdown(self):
        results = [
            TaskAgentResult("fibonacci", "claude", score=0.0, wall_time=0.0,
                            tests_pass=False, exit_clean=False, lint_clean=False,
                            timed_out=False, error="Unknown agent"),
        ]
        br = BenchmarkResult("bench-err", ["claude"], ["fibonacci"], results=results)
        stats = compute_benchmark_stats(br)
        md = render_benchmark_markdown(br, stats)
        assert "ERR" in md


# ---------------------------------------------------------------------------
# D4: Storage
# ---------------------------------------------------------------------------

class TestBenchmarkStorage:
    def test_save_and_retrieve_benchmark(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            os.environ["CODERACE_DB"] = str(db_path)
            try:
                from coderace.store import ResultStore
                store = ResultStore()

                br = _make_sample_benchmark()
                stats = compute_benchmark_stats(br)
                store.save_benchmark(br, stats)

                runs = store.get_benchmarks(limit=5)
                assert len(runs) == 1
                assert runs[0]["benchmark_id"] == "bench-test-001"
                assert runs[0]["winner"] == "codex"

                detail = store.get_benchmark("bench-test-001")
                assert detail is not None
                assert detail["benchmark_id"] == "bench-test-001"
                assert set(detail["agents"]) == {"claude", "codex"}
                assert len(detail["results"]) == 4

                store.close()
            finally:
                del os.environ["CODERACE_DB"]

    def test_get_benchmark_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            os.environ["CODERACE_DB"] = str(db_path)
            try:
                from coderace.store import ResultStore
                store = ResultStore()
                result = store.get_benchmark("nonexistent-id")
                assert result is None
                store.close()
            finally:
                del os.environ["CODERACE_DB"]

    def test_get_benchmarks_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            os.environ["CODERACE_DB"] = str(db_path)
            try:
                from coderace.store import ResultStore
                store = ResultStore()
                runs = store.get_benchmarks()
                assert runs == []
                store.close()
            finally:
                del os.environ["CODERACE_DB"]

    def test_benchmark_results_stored_correctly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            os.environ["CODERACE_DB"] = str(db_path)
            try:
                from coderace.store import ResultStore
                store = ResultStore()

                br = _make_sample_benchmark()
                stats = compute_benchmark_stats(br)
                store.save_benchmark(br, stats)

                detail = store.get_benchmark("bench-test-001")
                results_map = {(r["task_name"], r["agent"]): r for r in detail["results"]}

                claude_fib = results_map[("fibonacci", "claude")]
                assert claude_fib["score"] == pytest.approx(100.0)
                assert claude_fib["tests_pass"] is True
                assert claude_fib["timed_out"] is False

                codex_json = results_map[("json-parser", "codex")]
                assert codex_json["score"] == pytest.approx(90.0)

                store.close()
            finally:
                del os.environ["CODERACE_DB"]


# ---------------------------------------------------------------------------
# Integration: dry-run mode
# ---------------------------------------------------------------------------

class TestDryRunIntegration:
    def test_dry_run_lists_combinations(self):
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "benchmark", "--agents", "claude,codex",
            "--tasks", "fibonacci,json-parser",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "fibonacci" in result.output
        assert "json-parser" in result.output
        assert "claude" in result.output
        assert "codex" in result.output

    def test_dry_run_shows_count(self):
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "benchmark", "--agents", "claude,codex",
            "--tasks", "fibonacci",
            "--dry-run",
        ])
        assert result.exit_code == 0
        # 1 task x 2 agents = 2 runs
        assert "2 runs" in result.output

    def test_no_tasks_match_filter(self):
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "benchmark", "--agents", "claude",
            "--difficulty", "impossible",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "No tasks" in result.output
