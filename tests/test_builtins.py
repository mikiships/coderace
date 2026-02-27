"""Tests for built-in task library."""

from __future__ import annotations

import pytest

from coderace.builtins import get_builtin_path, list_builtins, load_builtin


EXPECTED_BUILTINS = [
    "binary-search-tree",
    "csv-analyzer",
    "fibonacci",
    "http-server",
    "json-parser",
    "markdown-to-html",
]


def test_list_builtins_returns_list() -> None:
    names = list_builtins()
    assert isinstance(names, list)
    assert len(names) >= 6
    for expected in EXPECTED_BUILTINS:
        assert expected in names


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


def test_all_builtins_valid_yaml() -> None:
    """Every built-in task must be valid YAML with all expected fields."""
    required = {"name", "description", "test_command", "agents"}
    for name in EXPECTED_BUILTINS:
        data = load_builtin(name)
        missing = required - set(data.keys())
        assert not missing, f"Built-in {name!r} missing: {missing}"
        assert isinstance(data["agents"], list)
        assert len(data["agents"]) >= 1
        assert isinstance(data.get("timeout", 300), int)
        assert isinstance(data.get("scoring", {}), dict)
