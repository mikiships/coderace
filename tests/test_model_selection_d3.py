"""Tests for D3: agent:model CLI syntax parsing and adapter factory."""

from __future__ import annotations

import pytest

from coderace.adapters import (
    instantiate_adapter,
    make_display_name,
    parse_agent_spec,
)
from coderace.adapters.claude import ClaudeAdapter
from coderace.adapters.codex import CodexAdapter


# ---------------------------------------------------------------------------
# parse_agent_spec
# ---------------------------------------------------------------------------


def test_parse_agent_spec_no_model() -> None:
    assert parse_agent_spec("codex") == ("codex", None)


def test_parse_agent_spec_with_model() -> None:
    assert parse_agent_spec("codex:gpt-5.4") == ("codex", "gpt-5.4")


def test_parse_agent_spec_claude_with_model() -> None:
    assert parse_agent_spec("claude:opus-4-6") == ("claude", "opus-4-6")


def test_parse_agent_spec_empty_model_returns_none() -> None:
    name, model = parse_agent_spec("codex:")
    assert name == "codex"
    assert model is None


def test_parse_agent_spec_strips_whitespace() -> None:
    name, model = parse_agent_spec(" codex : gpt-5.4 ")
    assert name == "codex"
    assert model == "gpt-5.4"


def test_parse_agent_spec_model_with_colons() -> None:
    # Only first colon splits; model can contain colons
    name, model = parse_agent_spec("codex:provider:model")
    assert name == "codex"
    assert model == "provider:model"


# ---------------------------------------------------------------------------
# make_display_name
# ---------------------------------------------------------------------------


def test_make_display_name_no_model() -> None:
    assert make_display_name("codex", None) == "codex"


def test_make_display_name_with_model() -> None:
    assert make_display_name("codex", "gpt-5.4") == "codex (gpt-5.4)"


def test_make_display_name_empty_model_treated_as_none() -> None:
    # Empty string is falsy
    assert make_display_name("codex", "") == "codex"


# ---------------------------------------------------------------------------
# instantiate_adapter
# ---------------------------------------------------------------------------


def test_instantiate_adapter_no_model() -> None:
    adapter = instantiate_adapter("codex")
    assert isinstance(adapter, CodexAdapter)
    assert adapter.model is None
    assert adapter.name == "codex"


def test_instantiate_adapter_with_model() -> None:
    adapter = instantiate_adapter("codex:gpt-5.4")
    assert isinstance(adapter, CodexAdapter)
    assert adapter.model == "gpt-5.4"
    assert adapter.name == "codex (gpt-5.4)"


def test_instantiate_adapter_claude_with_model() -> None:
    adapter = instantiate_adapter("claude:opus-4-6")
    assert isinstance(adapter, ClaudeAdapter)
    assert adapter.model == "opus-4-6"
    assert adapter.name == "claude (opus-4-6)"


def test_instantiate_adapter_unknown_raises() -> None:
    with pytest.raises(KeyError):
        instantiate_adapter("unknown-agent")


def test_instantiate_adapter_build_command_includes_model() -> None:
    adapter = instantiate_adapter("codex:gpt-5.4")
    cmd = adapter.build_command("do task")
    assert "--model" in cmd
    assert "gpt-5.4" in cmd


def test_instantiate_adapter_no_model_no_flag() -> None:
    adapter = instantiate_adapter("codex")
    cmd = adapter.build_command("do task")
    assert "--model" not in cmd


# ---------------------------------------------------------------------------
# Duplicate agents with different models
# ---------------------------------------------------------------------------


def test_duplicate_agents_different_models() -> None:
    """Same agent type with different models produces distinct display names."""
    a1 = instantiate_adapter("codex:gpt-5.4")
    a2 = instantiate_adapter("codex:gpt-5.3-codex")
    assert a1.name != a2.name
    assert a1.model == "gpt-5.4"
    assert a2.model == "gpt-5.3-codex"


# ---------------------------------------------------------------------------
# Task validation with agent:model syntax
# ---------------------------------------------------------------------------


def test_task_validate_accepts_agent_model_syntax() -> None:
    from pathlib import Path
    from coderace.types import Task

    task = Task(
        name="test",
        description="desc",
        repo=Path("."),
        test_command="pytest",
        agents=["codex:gpt-5.4", "claude:opus-4-6"],
    )
    # Mock repo exists check — validation doesn't check disk
    errors = task.validate()
    # Should have no errors about unknown agents
    agent_errors = [e for e in errors if "Unknown agent" in e]
    assert not agent_errors, f"Got agent errors: {agent_errors}"


def test_task_validate_rejects_unknown_agent_with_model() -> None:
    from pathlib import Path
    from coderace.types import Task

    task = Task(
        name="test",
        description="desc",
        repo=Path("."),
        test_command="pytest",
        agents=["bogus:some-model"],
    )
    errors = task.validate()
    agent_errors = [e for e in errors if "Unknown agent" in e]
    assert agent_errors, "Should have rejected unknown agent"
