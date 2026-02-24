"""Tests for D3: coderace leaderboard command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from coderace.cli import app
from coderace.commands.leaderboard import (
    format_leaderboard_html,
    format_leaderboard_json,
    format_leaderboard_markdown,
    format_leaderboard_terminal,
)
from coderace.store import AgentStat, ResultStore

runner = CliRunner()


def _make_stat(
    agent: str,
    wins: int = 1,
    races: int = 2,
    avg_score: float = 75.0,
    avg_cost: float | None = 0.05,
    avg_time: float = 12.0,
) -> AgentStat:
    return AgentStat(
        agent=agent,
        wins=wins,
        races=races,
        win_rate=wins / races if races > 0 else 0.0,
        avg_score=avg_score,
        avg_cost=avg_cost,
        avg_time=avg_time,
    )


def _populate_store(store: ResultStore) -> None:
    """Add sample data to the store."""
    # Run 1: claude wins
    store.save_run("task-a", [
        {"agent": "claude", "composite_score": 85.0, "wall_time": 10.0,
         "lines_changed": 42, "tests_pass": True, "exit_clean": True,
         "lint_clean": True, "cost_usd": 0.05},
        {"agent": "codex", "composite_score": 70.0, "wall_time": 15.0,
         "lines_changed": 98, "tests_pass": True, "exit_clean": True,
         "lint_clean": False, "cost_usd": 0.03},
    ])
    # Run 2: codex wins
    store.save_run("task-b", [
        {"agent": "claude", "composite_score": 60.0, "wall_time": 12.0,
         "lines_changed": 50, "tests_pass": False, "exit_clean": True,
         "lint_clean": True, "cost_usd": 0.04},
        {"agent": "codex", "composite_score": 80.0, "wall_time": 11.0,
         "lines_changed": 30, "tests_pass": True, "exit_clean": True,
         "lint_clean": True, "cost_usd": 0.06},
    ])
    # Run 3: claude wins again
    store.save_run("task-a", [
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


class TestFormatFunctions:
    def test_terminal_empty(self) -> None:
        output = format_leaderboard_terminal([], console=None)
        assert "leaderboard" in output.lower()

    def test_terminal_with_data(self) -> None:
        stats = [_make_stat("claude", wins=2, races=3), _make_stat("codex", wins=1, races=3)]
        output = format_leaderboard_terminal(stats)
        assert "claude" in output
        assert "codex" in output
        assert "67%" in output  # claude win rate

    def test_markdown_empty(self) -> None:
        output = format_leaderboard_markdown([])
        assert "No data" in output

    def test_markdown_with_data(self) -> None:
        stats = [_make_stat("claude", wins=2, races=3)]
        output = format_leaderboard_markdown(stats)
        assert "| 1 |" in output
        assert "`claude`" in output
        assert "67%" in output

    def test_json_format(self) -> None:
        stats = [_make_stat("claude", wins=2, races=3, avg_score=78.3)]
        output = format_leaderboard_json(stats)
        data = json.loads(output)
        assert "leaderboard" in data
        assert len(data["leaderboard"]) == 1
        entry = data["leaderboard"][0]
        assert entry["agent"] == "claude"
        assert entry["wins"] == 2
        assert entry["races"] == 3
        assert entry["avg_score"] == 78.3

    def test_json_null_cost(self) -> None:
        stats = [_make_stat("claude", avg_cost=None)]
        output = format_leaderboard_json(stats)
        data = json.loads(output)
        assert data["leaderboard"][0]["avg_cost"] is None

    def test_html_format(self) -> None:
        stats = [_make_stat("claude")]
        output = format_leaderboard_html(stats)
        assert "<html>" in output
        assert "claude" in output
        assert "leaderboard" in output.lower()

    def test_markdown_cost_none_shows_dash(self) -> None:
        stats = [_make_stat("claude", avg_cost=None)]
        output = format_leaderboard_markdown(stats)
        assert "| - |" in output


class TestLeaderboardCommand:
    def test_empty_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard"])
        assert result.exit_code == 0
        assert "no data" in result.output.lower()

    def test_default_view(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard"])
        assert result.exit_code == 0
        assert "claude" in result.output
        assert "codex" in result.output

    def test_task_filter(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--task", "task-a"])
        assert result.exit_code == 0
        assert "claude" in result.output

    def test_since_filter(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            # All runs are recent, so 7d should include them
            result = runner.invoke(app, ["leaderboard", "--since", "7d"])
        assert result.exit_code == 0
        assert "claude" in result.output

    def test_min_runs_filter(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            # Both agents have 3 races, require 4 -> empty
            result = runner.invoke(app, ["leaderboard", "--min-runs", "4"])
        assert result.exit_code == 0
        assert "no data" in result.output.lower()

    def test_format_markdown(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--format", "markdown"])
        assert result.exit_code == 0
        assert "| Rank |" in result.output

    def test_format_json(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "leaderboard" in data

    def test_format_html(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--format", "html"])
        assert result.exit_code == 0
        assert "<html>" in result.output

    def test_invalid_format(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--format", "csv"])
        assert result.exit_code == 1

    def test_ranking_logic(self, populated_store: ResultStore) -> None:
        """Claude has 2 wins/3 races, codex has 1 win/3 races. Claude should rank first."""
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--format", "json"])
        data = json.loads(result.output)
        lb = data["leaderboard"]
        assert lb[0]["agent"] == "claude"
        assert lb[0]["wins"] == 2
        assert lb[1]["agent"] == "codex"
        assert lb[1]["wins"] == 1

    def test_help_text(self) -> None:
        result = runner.invoke(app, ["leaderboard", "--help"])
        assert result.exit_code == 0
        assert "leaderboard" in result.output.lower()
        assert "--task" in result.output
        assert "--since" in result.output
        assert "--min-runs" in result.output
        assert "--format" in result.output
