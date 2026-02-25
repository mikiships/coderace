"""Tests for D1: dashboard generator core."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderace.dashboard import (
    _build_agent_cards,
    _build_cost_chart,
    _build_leaderboard_table,
    _build_race_history,
    generate_dashboard,
)
from coderace.store import AgentStat, ResultStore, RunRecord


def _make_result(agent: str, score: float = 75.0, **kwargs) -> dict:
    """Helper to build a minimal agent result dict."""
    base = {
        "agent": agent,
        "composite_score": score,
        "wall_time": 10.5,
        "lines_changed": 42,
        "tests_pass": True,
        "exit_clean": True,
        "lint_clean": True,
    }
    base.update(kwargs)
    return base


def _populate_store(store: ResultStore) -> None:
    """Add sample data to the store."""
    store.save_run("fizzbuzz", [
        {"agent": "claude", "composite_score": 85.0, "wall_time": 10.0,
         "lines_changed": 42, "tests_pass": True, "exit_clean": True,
         "lint_clean": True, "cost_usd": 0.05},
        {"agent": "codex", "composite_score": 70.0, "wall_time": 15.0,
         "lines_changed": 98, "tests_pass": True, "exit_clean": True,
         "lint_clean": False, "cost_usd": 0.03},
    ])
    store.save_run("sorting", [
        {"agent": "claude", "composite_score": 60.0, "wall_time": 12.0,
         "lines_changed": 50, "tests_pass": False, "exit_clean": True,
         "lint_clean": True, "cost_usd": 0.04},
        {"agent": "codex", "composite_score": 80.0, "wall_time": 11.0,
         "lines_changed": 30, "tests_pass": True, "exit_clean": True,
         "lint_clean": True, "cost_usd": 0.06},
    ])
    store.save_run("fizzbuzz", [
        {"agent": "claude", "composite_score": 90.0, "wall_time": 8.0,
         "lines_changed": 35, "tests_pass": True, "exit_clean": True,
         "lint_clean": True, "cost_usd": 0.06},
        {"agent": "codex", "composite_score": 65.0, "wall_time": 14.0,
         "lines_changed": 88, "tests_pass": True, "exit_clean": False,
         "lint_clean": True, "cost_usd": 0.02},
    ])


@pytest.fixture
def populated_store(tmp_path: Path) -> ResultStore:
    db_path = tmp_path / "test.db"
    store = ResultStore(db_path=db_path)
    _populate_store(store)
    yield store
    store.close()


@pytest.fixture
def empty_store(tmp_path: Path) -> ResultStore:
    db_path = tmp_path / "empty.db"
    store = ResultStore(db_path=db_path)
    yield store
    store.close()


class TestGenerateDashboard:
    def test_returns_valid_html(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_contains_all_sections(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert "Aggregate Leaderboard" in html
        assert "Race History" in html
        assert "Agent Performance" in html
        assert "Cost Efficiency" in html

    def test_default_title(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert "coderace Leaderboard" in html

    def test_custom_title(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store, title="My Team Dashboard")
        assert "My Team Dashboard" in html

    def test_title_html_escaped(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store, title="<script>alert(1)</script>")
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_contains_agent_names(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert "claude" in html
        assert "codex" in html

    def test_contains_timestamp(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert "Last updated:" in html

    def test_task_filter(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store, task_name="fizzbuzz")
        assert "fizzbuzz" in html

    def test_dark_mode_default(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert 'data-theme="dark"' in html

    def test_theme_toggle_present(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert "toggleTheme" in html
        assert "theme-toggle" in html

    def test_no_external_dependencies(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert "cdn" not in html.lower()
        assert "https://" not in html
        assert "http://" not in html

    def test_self_contained_css(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert "<style>" in html
        assert "</style>" in html

    def test_responsive_meta_tag(self, populated_store: ResultStore) -> None:
        html = generate_dashboard(populated_store)
        assert 'name="viewport"' in html


class TestEmptyDashboard:
    def test_empty_db_valid_html(self, empty_store: ResultStore) -> None:
        html = generate_dashboard(empty_store)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_empty_db_shows_message(self, empty_store: ResultStore) -> None:
        html = generate_dashboard(empty_store)
        assert "No races yet" in html

    def test_empty_db_shows_instructions(self, empty_store: ResultStore) -> None:
        html = generate_dashboard(empty_store)
        assert "coderace run task.yaml" in html
        assert "coderace dashboard" in html


class TestSingleRace:
    def test_single_agent_single_run(self, tmp_path: Path) -> None:
        db_path = tmp_path / "single.db"
        store = ResultStore(db_path=db_path)
        store.save_run("task-1", [
            _make_result("claude", score=85.0, cost_usd=0.05),
        ])
        html = generate_dashboard(store)
        assert "claude" in html
        assert "Aggregate Leaderboard" in html
        assert "Agent Performance" in html
        store.close()


class TestLeaderboardTable:
    def test_agent_stats_in_table(self) -> None:
        stats = [
            AgentStat(agent="claude", wins=2, races=3, win_rate=0.667,
                      avg_score=78.3, avg_cost=0.05, avg_time=10.0),
            AgentStat(agent="codex", wins=1, races=3, win_rate=0.333,
                      avg_score=71.7, avg_cost=0.037, avg_time=13.3),
        ]
        html = _build_leaderboard_table(stats)
        assert "claude" in html
        assert "codex" in html
        assert "78.3" in html
        assert "$0.0500" in html

    def test_null_cost_shows_dash(self) -> None:
        stats = [
            AgentStat(agent="claude", wins=1, races=1, win_rate=1.0,
                      avg_score=85.0, avg_cost=None, avg_time=10.0),
        ]
        html = _build_leaderboard_table(stats)
        assert ">-<" in html

    def test_empty_stats_returns_empty(self) -> None:
        assert _build_leaderboard_table([]) == ""


class TestRaceHistory:
    def test_empty_returns_empty(self) -> None:
        assert _build_race_history([]) == ""

    def test_run_rows_present(self, populated_store: ResultStore) -> None:
        runs = populated_store.get_runs()
        html = _build_race_history(runs)
        assert "fizzbuzz" in html
        assert "sorting" in html

    def test_expandable_rows(self, populated_store: ResultStore) -> None:
        runs = populated_store.get_runs()
        html = _build_race_history(runs)
        assert "detail-row" in html
        assert "toggleRun" in html


class TestAgentCards:
    def test_empty_returns_empty(self) -> None:
        assert _build_agent_cards([], []) == ""

    def test_card_contains_agent_stats(self) -> None:
        stats = [
            AgentStat(agent="claude", wins=2, races=3, win_rate=0.667,
                      avg_score=78.3, avg_cost=0.05, avg_time=10.0),
        ]
        html = _build_agent_cards(stats, [])
        assert "claude" in html
        assert "Races" in html
        assert "Wins" in html
        assert "Avg Score" in html
        assert "Best Score" in html
        assert "Avg Cost" in html


class TestCostChart:
    def test_empty_returns_empty(self) -> None:
        assert _build_cost_chart([]) == ""

    def test_no_cost_data_returns_empty(self) -> None:
        stats = [
            AgentStat(agent="claude", wins=1, races=1, win_rate=1.0,
                      avg_score=85.0, avg_cost=None, avg_time=10.0),
        ]
        assert _build_cost_chart(stats) == ""

    def test_bar_chart_rendered(self) -> None:
        stats = [
            AgentStat(agent="claude", wins=1, races=1, win_rate=1.0,
                      avg_score=85.0, avg_cost=0.05, avg_time=10.0),
            AgentStat(agent="codex", wins=0, races=1, win_rate=0.0,
                      avg_score=70.0, avg_cost=0.03, avg_time=15.0),
        ]
        html = _build_cost_chart(stats)
        assert "bar-fill" in html
        assert "claude" in html
        assert "codex" in html
        assert "/pt" in html

    def test_bar_widths_are_relative(self) -> None:
        stats = [
            AgentStat(agent="expensive", wins=1, races=1, win_rate=1.0,
                      avg_score=50.0, avg_cost=0.10, avg_time=10.0),
            AgentStat(agent="cheap", wins=0, races=1, win_rate=0.0,
                      avg_score=100.0, avg_cost=0.01, avg_time=5.0),
        ]
        html = _build_cost_chart(stats)
        # "expensive" has higher cost per point, so should be 100% width
        assert 'width:100.0%' in html
