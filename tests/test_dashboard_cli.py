"""Tests for D2: coderace dashboard CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from coderace.cli import app
from coderace.store import ResultStore

runner = CliRunner()


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


class TestDashboardCommand:
    def test_default_output(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "dashboard.html"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path)])
        assert result.exit_code == 0
        assert output_path.exists()
        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "coderace Leaderboard" in content

    def test_custom_output_path(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "subdir" / "report.html"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["dashboard", "--output", str(output_path)])
        assert result.exit_code == 0
        assert output_path.exists()
        assert "Dashboard written to:" in result.output

    def test_task_filter(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "filtered.html"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path), "--task", "fizzbuzz"])
        assert result.exit_code == 0
        content = output_path.read_text()
        assert "fizzbuzz" in content

    def test_last_flag(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "last.html"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path), "--last", "1"])
        assert result.exit_code == 0
        assert output_path.exists()

    def test_custom_title(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "titled.html"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path), "--title", "My Team"])
        assert result.exit_code == 0
        content = output_path.read_text()
        assert "My Team" in content

    def test_empty_database(self, empty_store: ResultStore, tmp_path: Path) -> None:
        db_path = empty_store._db_path
        output_path = tmp_path / "empty.html"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path)])
        assert result.exit_code == 0
        content = output_path.read_text()
        assert "No races yet" in content
        assert "<!DOCTYPE html>" in content

    def test_open_flag_calls_webbrowser(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "open.html"
        with patch("coderace.store.get_db_path", return_value=db_path), \
             patch("webbrowser.open") as mock_open:
            result = runner.invoke(app, ["dashboard", "-o", str(output_path), "--open"])
        assert result.exit_code == 0
        mock_open.assert_called_once()
        assert "Opened in browser" in result.output

    def test_help_text(self) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--task" in result.output
        assert "--last" in result.output
        assert "--title" in result.output
        assert "--open" in result.output

    def test_html_contains_agent_data(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "data.html"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path)])
        assert result.exit_code == 0
        content = output_path.read_text()
        assert "claude" in content
        assert "codex" in content

    def test_html_is_self_contained(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "selfcontained.html"
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path)])
        assert result.exit_code == 0
        content = output_path.read_text()
        assert "<style>" in content
        assert "cdn" not in content.lower()
