"""Tests for built-in task library."""

from __future__ import annotations

import pytest

from coderace.builtins import get_builtin_path, list_builtins, load_builtin


def test_list_builtins_returns_list() -> None:
    names = list_builtins()
    assert isinstance(names, list)
    assert len(names) >= 1
    assert "fibonacci" in names


def test_list_builtins_sorted() -> None:
    names = list_builtins()
    assert names == sorted(names)


def test_load_builtin_fibonacci() -> None:
    data = load_builtin("fibonacci")
    assert isinstance(data, dict)
    assert data["name"] == "fibonacci"
    assert "description" in data
    assert "test_command" in data
    assert "agents" in data


def test_load_builtin_has_required_fields() -> None:
    """Every built-in task must have the required fields."""
    required = {"name", "description", "test_command", "agents"}
    for name in list_builtins():
        data = load_builtin(name)
        missing = required - set(data.keys())
        assert not missing, f"Built-in {name!r} missing fields: {missing}"


def test_load_builtin_missing_task() -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        load_builtin("nonexistent-task-xyz")


def test_get_builtin_path_exists() -> None:
    path = get_builtin_path("fibonacci")
    assert path.exists()
    assert path.suffix == ".yaml"


def test_get_builtin_path_missing() -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        get_builtin_path("nonexistent-task-xyz")
