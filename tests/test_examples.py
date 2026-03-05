"""Tests that example task YAML files are valid."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from coderace.types import normalize_weights

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
EXAMPLE_FILES = list(EXAMPLES_DIR.glob("*.yaml"))


@pytest.mark.parametrize("example_path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_example_yaml_is_valid_yaml(example_path: Path) -> None:
    """Each example file must be valid YAML."""
    content = example_path.read_text()
    data = yaml.safe_load(content)
    assert isinstance(data, dict), f"{example_path.name} must be a YAML mapping"


@pytest.mark.parametrize("example_path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_example_yaml_has_required_fields(example_path: Path) -> None:
    """Each example file must have all required task fields."""
    content = example_path.read_text()
    data = yaml.safe_load(content)
    required = {"name", "description", "test_command", "agents"}
    missing = required - set(data.keys())
    assert not missing, f"{example_path.name} missing fields: {missing}"


@pytest.mark.parametrize("example_path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_example_yaml_agents_are_known(example_path: Path) -> None:
    """Each example file must only list known agents (supports agent:model syntax)."""
    content = example_path.read_text()
    data = yaml.safe_load(content)
    known = {"claude", "codex", "aider", "gemini", "opencode"}
    agents = data.get("agents", [])
    assert agents, f"{example_path.name} must list at least one agent"
    # Strip optional :model suffix before checking
    unknown = {a for a in agents if a.split(":")[0] not in known}
    assert not unknown, f"{example_path.name} has unknown agents: {unknown}"


@pytest.mark.parametrize("example_path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_example_yaml_scoring_is_valid(example_path: Path) -> None:
    """If scoring is specified, it must be valid."""
    content = example_path.read_text()
    data = yaml.safe_load(content)
    scoring = data.get("scoring")
    if scoring is not None:
        assert isinstance(scoring, dict), (
            f"{example_path.name} scoring must be a mapping"
        )
        # Must not raise
        result = normalize_weights(scoring)
        assert abs(sum(result.values()) - 1.0) < 1e-9


def test_all_examples_exist() -> None:
    """There must be at least 3 example files."""
    assert len(EXAMPLE_FILES) >= 3, (
        f"Expected >= 3 example files, found {len(EXAMPLE_FILES)}"
    )
