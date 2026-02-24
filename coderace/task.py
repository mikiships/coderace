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

    scoring_raw = data.get("scoring")
    if scoring_raw is not None and not isinstance(scoring_raw, dict):
        raise ValueError(f"scoring must be a mapping, got {type(scoring_raw).__name__}")

    pricing_raw = data.get("pricing")
    pricing: dict[str, tuple[float, float]] | None = None
    if pricing_raw is not None:
        if not isinstance(pricing_raw, dict):
            raise ValueError(f"pricing must be a mapping, got {type(pricing_raw).__name__}")
        pricing = {}
        for key, entry in pricing_raw.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"pricing.{key} must be a mapping with input_per_1m/output_per_1m, "
                    f"got {type(entry).__name__}"
                )
            try:
                inp = float(entry["input_per_1m"])
                out = float(entry["output_per_1m"])
            except KeyError as e:
                raise ValueError(
                    f"pricing.{key} missing required field: {e}"
                ) from e
            if inp < 0 or out < 0:
                raise ValueError(f"pricing.{key}: prices must be >= 0")
            pricing[key] = (inp, out)

    task = Task(
        name=data["name"],
        description=data["description"],
        repo=repo.resolve(),
        test_command=data["test_command"],
        agents=data["agents"],
        lint_command=data.get("lint_command"),
        timeout=data.get("timeout", 300),
        scoring=scoring_raw,
        pricing=pricing,
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
  - opencode
# Optional: customize scoring weights (defaults shown, will be normalized)
# scoring:
#   tests: 40
#   exit: 20
#   lint: 15
#   time: 15
#   lines: 10
# Optional: override pricing for cost tracking (USD per 1M tokens)
# Use agent name or model name as key.
# pricing:
#   claude:
#     input_per_1m: 3.00   # override if using a non-default model
#     output_per_1m: 15.00
#   codex:
#     input_per_1m: 3.00
#     output_per_1m: 15.00
"""
    path.write_text(template)
    return path
