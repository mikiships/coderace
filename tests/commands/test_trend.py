"""Tests for coderace trend command."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from coderace.commands.trend import (
    AgentTaskTrend,
    TrendPoint,
    _build_trends,
    format_trend_json,
    format_trend_markdown,
    format_trend_terminal,
)
from coderace.store import AgentRecord, ResultStore, RunRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def store_with_data(tmp_db: Path) -> ResultStore:
    """ResultStore with pre-loaded runs."""
    store = ResultStore(db_path=tmp_db)

    # Run 1 (oldest) — agent-a scores 60, agent-b scores 55
    store.save_run(
        task_name="task-alpha",
        results=[
            {"agent": "agent-a", "composite_score": 60.0, "wall_time": 10.0, "lines_changed": 5, "tests_pass": True, "exit_clean": True, "lint_clean": True},
            {"agent": "agent-b", "composite_score": 55.0, "wall_time": 12.0, "lines_changed": 4, "tests_pass": True, "exit_clean": True, "lint_clean": False},
        ],
    )
    # Run 2 (middle) — agent-a improves, agent-b drops
    store.save_run(
        task_name="task-alpha",
        results=[
            {"agent": "agent-a", "composite_score": 70.0, "wall_time": 9.0, "lines_changed": 6, "tests_pass": True, "exit_clean": True, "lint_clean": True},
            {"agent": "agent-b", "composite_score": 50.0, "wall_time": 11.0, "lines_changed": 3, "tests_pass": False, "exit_clean": True, "lint_clean": False},
        ],
    )
    # Run 3 (newest) — agent-a flat, agent-b improves
    store.save_run(
        task_name="task-alpha",
        results=[
            {"agent": "agent-a", "composite_score": 70.5, "wall_time": 9.5, "lines_changed": 6, "tests_pass": True, "exit_clean": True, "lint_clean": True},
            {"agent": "agent-b", "composite_score": 65.0, "wall_time": 10.0, "lines_changed": 5, "tests_pass": True, "exit_clean": True, "lint_clean": True},
        ],
    )
    # Different task — only agent-a, single run
    store.save_run(
        task_name="task-beta",
        results=[
            {"agent": "agent-a", "composite_score": 80.0, "wall_time": 8.0, "lines_changed": 7, "tests_pass": True, "exit_clean": True, "lint_clean": True},
        ],
    )
    return store


def _make_runs(store: ResultStore) -> list[RunRecord]:
    return store.get_runs(limit=1000)


# ---------------------------------------------------------------------------
# TrendPoint and AgentTaskTrend unit tests
# ---------------------------------------------------------------------------


def test_trend_point_delta_none_for_first():
    p = TrendPoint(run_id=1, timestamp="2026-01-01", score=60.0, delta=None, is_winner=True)
    assert p.delta is None


def test_agent_task_trend_empty():
    t = AgentTaskTrend(agent="x", task="y")
    assert t.runs == 0
    assert t.avg_score == 0.0
    assert t.best_score == 0.0
    assert t.latest_score == 0.0
    assert t.latest_delta is None
    assert t.improvement_rate is None


def test_agent_task_trend_single_run():
    t = AgentTaskTrend(agent="x", task="y", points=[
        TrendPoint(run_id=1, timestamp="2026-01-01", score=70.0, delta=None, is_winner=True),
    ])
    assert t.runs == 1
    assert t.avg_score == pytest.approx(70.0)
    assert t.best_score == pytest.approx(70.0)
    assert t.latest_score == pytest.approx(70.0)
    assert t.latest_delta is None
    assert t.improvement_rate is None
    assert t.sparkline() == "—"


def test_agent_task_trend_improving():
    t = AgentTaskTrend(agent="x", task="y", points=[
        TrendPoint(run_id=1, timestamp="2026-01-01", score=50.0, delta=None, is_winner=False),
        TrendPoint(run_id=2, timestamp="2026-01-02", score=60.0, delta=10.0, is_winner=False),
        TrendPoint(run_id=3, timestamp="2026-01-03", score=75.0, delta=15.0, is_winner=True),
    ])
    assert t.runs == 3
    assert t.avg_score == pytest.approx((50 + 60 + 75) / 3)
    assert t.best_score == pytest.approx(75.0)
    assert t.latest_score == pytest.approx(75.0)
    assert t.latest_delta == pytest.approx(15.0)
    assert t.improvement_rate == pytest.approx(1.0)  # 2/2 improved


def test_agent_task_trend_regressing():
    t = AgentTaskTrend(agent="x", task="y", points=[
        TrendPoint(run_id=1, timestamp="2026-01-01", score=80.0, delta=None, is_winner=True),
        TrendPoint(run_id=2, timestamp="2026-01-02", score=70.0, delta=-10.0, is_winner=False),
        TrendPoint(run_id=3, timestamp="2026-01-03", score=60.0, delta=-10.0, is_winner=False),
    ])
    assert t.improvement_rate == pytest.approx(0.0)
    assert t.latest_delta == pytest.approx(-10.0)


def test_agent_task_trend_mixed():
    t = AgentTaskTrend(agent="x", task="y", points=[
        TrendPoint(run_id=1, timestamp="2026-01-01", score=50.0, delta=None, is_winner=False),
        TrendPoint(run_id=2, timestamp="2026-01-02", score=60.0, delta=10.0, is_winner=True),  # improved
        TrendPoint(run_id=3, timestamp="2026-01-03", score=55.0, delta=-5.0, is_winner=False),  # regressed
    ])
    assert t.improvement_rate == pytest.approx(0.5)  # 1/2


def test_sparkline_two_points():
    t = AgentTaskTrend(agent="x", task="y", points=[
        TrendPoint(run_id=1, timestamp="2026-01-01", score=40.0, delta=None, is_winner=False),
        TrendPoint(run_id=2, timestamp="2026-01-02", score=90.0, delta=50.0, is_winner=True),
    ])
    spark = t.sparkline(use_unicode=True)
    assert len(spark) == 2
    assert spark[0] < spark[1]  # low → high


def test_sparkline_all_same():
    t = AgentTaskTrend(agent="x", task="y", points=[
        TrendPoint(run_id=i, timestamp=f"2026-01-0{i}", score=70.0, delta=0.0 if i > 1 else None, is_winner=False)
        for i in range(1, 4)
    ])
    spark = t.sparkline(use_unicode=True)
    assert len(spark) == 3
    assert len(set(spark)) == 1  # all same char


def test_sparkline_ascii_fallback():
    t = AgentTaskTrend(agent="x", task="y", points=[
        TrendPoint(run_id=1, timestamp="2026-01-01", score=40.0, delta=None, is_winner=False),
        TrendPoint(run_id=2, timestamp="2026-01-02", score=90.0, delta=50.0, is_winner=True),
    ])
    spark = t.sparkline(use_unicode=False)
    assert all(c in "_.-*^" for c in spark)


# ---------------------------------------------------------------------------
# _build_trends tests
# ---------------------------------------------------------------------------


def test_build_trends_groups_by_agent_task(store_with_data):
    runs = _make_runs(store_with_data)
    trends = _build_trends(runs, agent_filter=None, task_filter=None)
    # agent-a/task-alpha, agent-b/task-alpha, agent-a/task-beta = 3 trends
    keys = {(t.agent, t.task) for t in trends}
    assert ("agent-a", "task-alpha") in keys
    assert ("agent-b", "task-alpha") in keys
    assert ("agent-a", "task-beta") in keys


def test_build_trends_chronological_order(store_with_data):
    runs = _make_runs(store_with_data)
    trends = _build_trends(runs, agent_filter=None, task_filter=None)
    t = next(t for t in trends if t.agent == "agent-a" and t.task == "task-alpha")
    timestamps = [p.timestamp for p in t.points]
    assert timestamps == sorted(timestamps)


def test_build_trends_delta_computed_correctly(store_with_data):
    runs = _make_runs(store_with_data)
    trends = _build_trends(runs, agent_filter=None, task_filter=None)
    t = next(t for t in trends if t.agent == "agent-a" and t.task == "task-alpha")
    assert t.points[0].delta is None
    assert t.points[1].delta == pytest.approx(10.0)
    assert t.points[2].delta == pytest.approx(0.5)


def test_build_trends_agent_filter(store_with_data):
    runs = _make_runs(store_with_data)
    trends = _build_trends(runs, agent_filter="agent-a", task_filter=None)
    assert all(t.agent == "agent-a" for t in trends)


def test_build_trends_task_filter(store_with_data):
    runs = _make_runs(store_with_data)
    trends = _build_trends(runs, agent_filter=None, task_filter="task-beta")
    assert all(t.task == "task-beta" for t in trends)
    assert len(trends) == 1


def test_build_trends_no_results_empty():
    trends = _build_trends([], agent_filter=None, task_filter=None)
    assert trends == []


def test_build_trends_single_run(store_with_data):
    runs = _make_runs(store_with_data)
    trends = _build_trends(runs, agent_filter="agent-a", task_filter="task-beta")
    assert len(trends) == 1
    assert trends[0].runs == 1
    assert trends[0].sparkline() == "—"


# ---------------------------------------------------------------------------
# Format tests
# ---------------------------------------------------------------------------


def _make_trends() -> list[AgentTaskTrend]:
    t1 = AgentTaskTrend(agent="agent-a", task="task-alpha", points=[
        TrendPoint(run_id=1, timestamp="2026-01-01T10:00:00", score=60.0, delta=None, is_winner=False),
        TrendPoint(run_id=2, timestamp="2026-01-02T10:00:00", score=70.0, delta=10.0, is_winner=True),
        TrendPoint(run_id=3, timestamp="2026-01-03T10:00:00", score=75.0, delta=5.0, is_winner=True),
    ])
    t2 = AgentTaskTrend(agent="agent-b", task="task-alpha", points=[
        TrendPoint(run_id=1, timestamp="2026-01-01T10:00:00", score=65.0, delta=None, is_winner=True),
    ])
    return [t1, t2]


def test_format_trend_json_valid():
    trends = _make_trends()
    output = format_trend_json(trends)
    data = json.loads(output)
    assert "trends" in data
    assert len(data["trends"]) == 2
    t = data["trends"][0]
    assert t["agent"] == "agent-a"
    assert t["task"] == "task-alpha"
    assert len(t["runs"]) == 3
    assert t["summary"]["total_runs"] == 3
    assert t["summary"]["avg_score"] == pytest.approx((60 + 70 + 75) / 3, rel=1e-2)
    assert t["summary"]["best_score"] == pytest.approx(75.0)
    assert t["summary"]["latest_score"] == pytest.approx(75.0)
    assert t["summary"]["trend_pct"] == pytest.approx(100.0)


def test_format_trend_json_single_run():
    t = AgentTaskTrend(agent="x", task="y", points=[
        TrendPoint(run_id=1, timestamp="2026-01-01", score=70.0, delta=None, is_winner=True),
    ])
    output = format_trend_json([t])
    data = json.loads(output)
    assert data["trends"][0]["summary"]["trend_pct"] is None


def test_format_trend_json_empty():
    output = format_trend_json([])
    data = json.loads(output)
    assert data["trends"] == []


def test_format_trend_markdown_summary():
    trends = _make_trends()
    output = format_trend_markdown(trends)
    assert "## coderace trend" in output
    assert "agent-a" in output
    assert "task-alpha" in output
    assert "↑" in output  # improving trend


def test_format_trend_markdown_empty():
    output = format_trend_markdown([])
    assert "No trend data found" in output


def test_format_trend_markdown_detail():
    trends = _make_trends()
    output = format_trend_markdown(trends, detail_agent="agent-a")
    assert "Run ID" in output
    assert "+10.0" in output or "10.0" in output


def test_format_trend_terminal_no_error():
    from io import StringIO
    from rich.console import Console
    trends = _make_trends()
    buf = StringIO()
    con = Console(file=buf, force_terminal=False)
    result = format_trend_terminal(trends, console=con)
    assert isinstance(result, str)


def test_format_trend_terminal_empty():
    from io import StringIO
    from rich.console import Console
    buf = StringIO()
    con = Console(file=buf, force_terminal=False)
    result = format_trend_terminal([], console=con)
    assert result == ""


def test_format_trend_terminal_detail():
    from io import StringIO
    from rich.console import Console
    trends = _make_trends()
    buf = StringIO()
    con = Console(file=buf, force_terminal=False)
    format_trend_terminal(trends, detail_agent="agent-a", console=con)
    # Just check it doesn't raise


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


def test_trend_command_no_data(tmp_db, monkeypatch):
    """trend command with empty DB prints no-data message and exits 0."""
    monkeypatch.setenv("CODERACE_DB", str(tmp_db))
    from typer.testing import CliRunner
    from coderace.cli import app
    runner = CliRunner()
    result = runner.invoke(app, ["trend"])
    assert result.exit_code == 0
    assert "No trend data found" in result.output


def test_trend_command_terminal(tmp_db, monkeypatch, store_with_data):
    """trend command renders terminal table with data."""
    monkeypatch.setenv("CODERACE_DB", str(tmp_db))
    # store_with_data already wrote to tmp_db via its own store instance
    from typer.testing import CliRunner
    from coderace.cli import app
    runner = CliRunner()
    result = runner.invoke(app, ["trend"])
    assert result.exit_code == 0


def test_trend_command_json(tmp_db, monkeypatch, store_with_data):
    """trend --format json outputs valid JSON."""
    monkeypatch.setenv("CODERACE_DB", str(tmp_db))
    from typer.testing import CliRunner
    from coderace.cli import app
    runner = CliRunner()
    result = runner.invoke(app, ["trend", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "trends" in data
    assert len(data["trends"]) > 0


def test_trend_command_markdown(tmp_db, monkeypatch, store_with_data):
    """trend --format markdown outputs markdown."""
    monkeypatch.setenv("CODERACE_DB", str(tmp_db))
    from typer.testing import CliRunner
    from coderace.cli import app
    runner = CliRunner()
    result = runner.invoke(app, ["trend", "--format", "markdown"])
    assert result.exit_code == 0
    assert "## coderace trend" in result.output


def test_trend_command_agent_filter(tmp_db, monkeypatch, store_with_data):
    """trend --agent filters to that agent."""
    monkeypatch.setenv("CODERACE_DB", str(tmp_db))
    from typer.testing import CliRunner
    from coderace.cli import app
    runner = CliRunner()
    result = runner.invoke(app, ["trend", "--agent", "agent-a", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert all(t["agent"] == "agent-a" for t in data["trends"])


def test_trend_command_task_filter(tmp_db, monkeypatch, store_with_data):
    """trend --task filters to that task."""
    monkeypatch.setenv("CODERACE_DB", str(tmp_db))
    from typer.testing import CliRunner
    from coderace.cli import app
    runner = CliRunner()
    result = runner.invoke(app, ["trend", "--task", "task-beta", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert all(t["task"] == "task-beta" for t in data["trends"])


def test_trend_command_invalid_format(tmp_db, monkeypatch, store_with_data):
    """trend --format badval exits non-zero when there is data to display."""
    monkeypatch.setenv("CODERACE_DB", str(tmp_db))
    from typer.testing import CliRunner
    from coderace.cli import app
    runner = CliRunner()
    result = runner.invoke(app, ["trend", "--format", "badval"])
    assert result.exit_code != 0
