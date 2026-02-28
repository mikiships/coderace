"""Tests for the tasks CLI command group and --builtin flag."""

from __future__ import annotations

from typer.testing import CliRunner

from coderace.cli import app

runner = CliRunner()


def test_tasks_list() -> None:
    result = runner.invoke(app, ["tasks", "list"])
    assert result.exit_code == 0
    assert "Verify" in result.output
    assert "yes" in result.output
    assert "fibonacci" in result.output
    assert "json-parser" in result.output
    assert "binary-search-tree" in result.output
    assert "regex-engine" in result.output


def test_tasks_show_fibonacci() -> None:
    result = runner.invoke(app, ["tasks", "show", "fibonacci"])
    assert result.exit_code == 0
    assert "name: fibonacci" in result.output
    assert "test_command" in result.output


def test_tasks_show_missing() -> None:
    result = runner.invoke(app, ["tasks", "show", "nonexistent-xyz"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_run_builtin_resolves(tmp_path: str) -> None:
    """--builtin should resolve to the built-in task file (will fail at repo check, not file-not-found)."""
    result = runner.invoke(app, ["run", "--builtin", "fibonacci"])
    # It should get past the task-loading stage.
    # It will fail because the repo has uncommitted changes or similar,
    # but NOT with "Task file not found" — that proves resolution worked.
    assert "Task file not found" not in (result.output or "")


def test_run_builtin_missing() -> None:
    result = runner.invoke(app, ["run", "--builtin", "nonexistent-xyz"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_run_no_args() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
