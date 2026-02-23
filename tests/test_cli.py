"""CLI integration tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from coderace import __version__
from coderace.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Race coding agents" in result.output


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_init(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "my-task", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "my-task.yaml").exists()


def test_run_missing_task_file() -> None:
    result = runner.invoke(app, ["run", "/nonexistent/task.yaml"])
    assert result.exit_code != 0


def test_results_no_prior_run(task_yaml: Path) -> None:
    result = runner.invoke(app, ["results", str(task_yaml)])
    assert result.exit_code != 0
    assert "No results found" in result.output
