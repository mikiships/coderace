"""Built-in task library for coderace."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml


def _tasks_path() -> Path:
    """Return the path to the bundled tasks directory."""
    return Path(str(resources.files("coderace.builtins") / "tasks"))


def list_builtins() -> list[str]:
    """List all available built-in task names (without .yaml extension)."""
    tasks_dir = _tasks_path()
    if not tasks_dir.is_dir():
        return []
    return sorted(p.stem for p in tasks_dir.glob("*.yaml"))


def list_builtin_tasks() -> list[str]:
    """Backward-compatible alias for listing built-in task names."""
    return list_builtins()


def load_builtin(name: str) -> dict:
    """Load a built-in task by name and return its parsed YAML as a dict."""
    path = get_builtin_path(name)
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Built-in task {name!r} is not a valid YAML mapping")
    return data


def get_builtin_path(name: str) -> Path:
    """Return the filesystem path to a built-in task YAML file."""
    path = _tasks_path() / f"{name}.yaml"
    if not path.exists():
        available = list_builtins()
        raise FileNotFoundError(
            f"Built-in task {name!r} not found. Available: {', '.join(available) or '(none)'}"
        )
    return path
