"""Tests for D4: coderace history command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from coderace.cli import app
from coderace.commands.history import (
    format_history_json,
    format_history_markdown,
    format_history_terminal,
)
from coderace.store import ResultStore

runner = CliRunner()


def _populate_store(store: ResultStore) -> None:
    """Add sample runs."""
    store.save_run("task-a", [
        {"agent": "claude", "composite_score": 85.0, "wall_time": 10.0,
         "lines_changed": 42, "tests_pass": True, "exit_clean": True,
         "lint_clean": True},
        {"agent": "codex", "composite_score": 70.0, "wall_time": 15.0,
         "lines_changed": 98, "tests_pass": True, "exit_clean": True,
         "lint_clean": False},
    ])
    store.save_run("task-b", [
        {"agent": "aider", "composite_score": 60.0, "wall_time": 12.0,
         "lines_changed": 50, "tests_pass": False, "exit_clean": True,
         "lint_clean": True},
    ])
    store.save_run("task-a", [
        {"agent": "claude", "composite_score": 90.0, "wall_time": 8.0,
         "lines_changed": 35, "tests_pass": True, "exit_clean": True,
         "lint_clean": True},
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
        output = format_history_terminal([])
        assert "history" in output.lower()

    def test_terminal_with_data(self, populated_store: ResultStore) -> None:
        runs = populated_store.get_runs()
        output = format_history_terminal(runs)
        assert "claude" in output
        assert "task-a" in output

    def test_markdown_empty(self) -> None:
        output = format_history_markdown([])
        assert "No runs" in output

    def test_markdown_with_data(self, populated_store: ResultStore) -> None:
        runs = populated_store.get_runs()
        output = format_history_markdown(runs)
        assert "| Run ID |" in output
        assert "`task-a`" in output

    def test_json_format(self, populated_store: ResultStore) -> None:
        runs = populated_store.get_runs()
        output = format_history_json(runs)
        data = json.loads(output)
        assert "history" in data
        assert len(data["history"]) == 3


class TestHistoryCommand:
    def test_empty_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "no runs" in result.output.lower()

    def test_default_view(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "task-a" in result.output

    def test_task_filter(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--task", "task-b"])
        assert result.exit_code == 0
        assert "task-b" in result.output

    def test_agent_filter(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--agent", "aider"])
        assert result.exit_code == 0
        assert "task-b" in result.output

    def test_limit(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--limit", "1", "--format", "json"])
        data = json.loads(result.output)
        assert len(data["history"]) == 1

    def test_format_markdown(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--format", "markdown"])
        assert result.exit_code == 0
        assert "| Run ID |" in result.output

    def test_format_json(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "history" in data

    def test_invalid_format(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--format", "csv"])
        assert result.exit_code == 1

    def test_help_text(self) -> None:
        result = runner.invoke(app, ["history", "--help"])
        assert result.exit_code == 0
        assert "--task" in result.output
        assert "--agent" in result.output
        assert "--limit" in result.output
        assert "--format" in result.output

    def test_json_includes_winner(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--format", "json"])
        data = json.loads(result.output)
        # First run (newest) has claude as sole agent and winner
        run = data["history"][0]
        assert run["winner"] == "claude"

    def test_newest_first(self, populated_store: ResultStore) -> None:
        db_path = populated_store._db_path
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--format", "json"])
        data = json.loads(result.output)
        # Run IDs should be descending (newest first)
        ids = [r["run_id"] for r in data["history"]]
        assert ids == sorted(ids, reverse=True)
