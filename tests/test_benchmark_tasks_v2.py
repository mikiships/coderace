"""Tests for batch 2 benchmark tasks: bug-hunt, refactor, concurrent-queue, api-client."""

from __future__ import annotations

import pytest

from coderace.builtins import get_builtin_path, load_builtin
from coderace.task import load_task


NEW_TASKS = ["bug-hunt", "refactor", "concurrent-queue", "api-client"]


@pytest.mark.parametrize("task_name", NEW_TASKS)
def test_task_loads_as_builtin(task_name):
    data = load_builtin(task_name)
    assert data["name"] == task_name
    assert "description" in data
    assert "test_command" in data
    assert "agents" in data


@pytest.mark.parametrize("task_name", NEW_TASKS)
def test_task_has_verify_suite(task_name):
    data = load_builtin(task_name)
    assert "verify_command" in data
    assert "verify_files" in data
    assert isinstance(data["verify_files"], dict)
    assert len(data["verify_files"]) >= 1


@pytest.mark.parametrize("task_name", NEW_TASKS)
def test_task_loads_via_load_task(task_name):
    path = get_builtin_path(task_name)
    task = load_task(path)
    assert task.name == task_name
    assert task.verify_command is not None
    assert task.verify_files is not None
    assert task.timeout > 0
    assert len(task.agents) >= 1


@pytest.mark.parametrize("task_name", NEW_TASKS)
def test_task_has_scoring_weights(task_name):
    data = load_builtin(task_name)
    assert "scoring" in data
    scoring = data["scoring"]
    assert isinstance(scoring, dict)
    assert "tests" in scoring or "tests_pass" in scoring
    assert "verify" in scoring or "verify_passed" in scoring


@pytest.mark.parametrize("task_name", NEW_TASKS)
def test_task_has_lint_command(task_name):
    data = load_builtin(task_name)
    assert "lint_command" in data
    assert "ruff" in data["lint_command"]


@pytest.mark.parametrize("task_name", NEW_TASKS)
def test_task_yaml_valid(task_name):
    path = get_builtin_path(task_name)
    task = load_task(path)
    errors = task.validate()
    assert not errors, f"Validation errors for {task_name}: {errors}"


@pytest.mark.parametrize("task_name", NEW_TASKS)
def test_task_difficulty_is_hard(task_name):
    data = load_builtin(task_name)
    assert data.get("difficulty") == "hard"


def test_all_new_tasks_in_builtins_list():
    from coderace.builtins import list_builtins
    builtins = list_builtins()
    for task_name in NEW_TASKS:
        assert task_name in builtins


def test_total_builtins_at_least_20():
    from coderace.builtins import list_builtins
    assert len(list_builtins()) >= 20
