"""Task definition loading and validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from coderace.types import Task


def load_task(path: str | Path) -> Task:
    """Load a task from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Task file must contain a YAML mapping, got {type(data).__name__}")

    required = {"name", "description", "test_command", "agents"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")

    repo_str = data.get("repo", ".")
    repo = Path(repo_str)
    if not repo.is_absolute():
        repo = path.parent / repo

    task = Task(
        name=data["name"],
        description=data["description"],
        repo=repo.resolve(),
        test_command=data["test_command"],
        agents=data["agents"],
        lint_command=data.get("lint_command"),
        timeout=data.get("timeout", 300),
    )

    errors = task.validate()
    if errors:
        raise ValueError(f"Invalid task: {'; '.join(errors)}")

    return task


def create_template(name: str, output_dir: Path | None = None) -> Path:
    """Create a task YAML template."""
    output_dir = output_dir or Path.cwd()
    path = output_dir / f"{name}.yaml"

    template = f"""name: {name}
description: |
  Describe the task here. What should the agent fix or build?
  Be specific about which files to change and what the expected behavior is.
repo: .
test_command: pytest tests/ -x
lint_command: ruff check .
timeout: 300
agents:
  - claude
  - codex
  - aider
"""
    path.write_text(template)
    return path
