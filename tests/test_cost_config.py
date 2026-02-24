"""Tests for D3: cost configuration (pricing YAML + --no-cost flag)."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderace.task import create_template, load_task
from coderace.types import Task


# ---------------------------------------------------------------------------
# Task.pricing field
# ---------------------------------------------------------------------------


def test_task_pricing_defaults_to_none(task_yaml: Path) -> None:
    task = load_task(task_yaml)
    assert task.pricing is None


def test_task_pricing_parsed_from_yaml(tmp_path: Path) -> None:
    yaml = """name: t
description: d
test_command: echo ok
agents:
  - claude
pricing:
  claude:
    input_per_1m: 3.0
    output_per_1m: 15.0
"""
    path = tmp_path / "task.yaml"
    path.write_text(yaml)
    task = load_task(path)
    assert task.pricing is not None
    assert "claude" in task.pricing
    assert task.pricing["claude"] == (3.0, 15.0)


def test_task_pricing_multiple_agents(tmp_path: Path) -> None:
    yaml = """name: t
description: d
test_command: echo ok
agents:
  - claude
  - codex
pricing:
  claude:
    input_per_1m: 3.0
    output_per_1m: 15.0
  codex:
    input_per_1m: 5.0
    output_per_1m: 20.0
"""
    path = tmp_path / "task.yaml"
    path.write_text(yaml)
    task = load_task(path)
    assert task.pricing is not None
    assert task.pricing["claude"] == (3.0, 15.0)
    assert task.pricing["codex"] == (5.0, 20.0)


def test_task_pricing_model_name_key(tmp_path: Path) -> None:
    """pricing key can be a model name instead of agent name."""
    yaml = """name: t
description: d
test_command: echo ok
agents:
  - claude
pricing:
  claude-opus-4-6:
    input_per_1m: 15.0
    output_per_1m: 75.0
"""
    path = tmp_path / "task.yaml"
    path.write_text(yaml)
    task = load_task(path)
    assert task.pricing is not None
    assert task.pricing["claude-opus-4-6"] == (15.0, 75.0)


def test_task_pricing_invalid_not_mapping(tmp_path: Path) -> None:
    yaml = """name: t
description: d
test_command: echo ok
agents:
  - claude
pricing: "not-a-dict"
"""
    path = tmp_path / "task.yaml"
    path.write_text(yaml)
    with pytest.raises(ValueError, match="pricing must be a mapping"):
        load_task(path)


def test_task_pricing_invalid_entry_not_mapping(tmp_path: Path) -> None:
    yaml = """name: t
description: d
test_command: echo ok
agents:
  - claude
pricing:
  claude: 3.0
"""
    path = tmp_path / "task.yaml"
    path.write_text(yaml)
    with pytest.raises(ValueError, match="mapping"):
        load_task(path)


def test_task_pricing_missing_field(tmp_path: Path) -> None:
    yaml = """name: t
description: d
test_command: echo ok
agents:
  - claude
pricing:
  claude:
    input_per_1m: 3.0
"""
    path = tmp_path / "task.yaml"
    path.write_text(yaml)
    with pytest.raises(ValueError, match="missing required field"):
        load_task(path)


def test_task_pricing_negative_value(tmp_path: Path) -> None:
    yaml = """name: t
description: d
test_command: echo ok
agents:
  - claude
pricing:
  claude:
    input_per_1m: -1.0
    output_per_1m: 15.0
"""
    path = tmp_path / "task.yaml"
    path.write_text(yaml)
    with pytest.raises(ValueError, match="prices must be >= 0"):
        load_task(path)


def test_task_pricing_zero_allowed(tmp_path: Path) -> None:
    """Zero price is valid (free tier)."""
    yaml = """name: t
description: d
test_command: echo ok
agents:
  - claude
pricing:
  claude:
    input_per_1m: 0.0
    output_per_1m: 0.0
"""
    path = tmp_path / "task.yaml"
    path.write_text(yaml)
    task = load_task(path)
    assert task.pricing is not None
    assert task.pricing["claude"] == (0.0, 0.0)


# ---------------------------------------------------------------------------
# Custom pricing affects cost calculation
# ---------------------------------------------------------------------------


def test_custom_pricing_affects_cost() -> None:
    from coderace.cost import calculate_cost

    # Standard pricing
    standard = calculate_cost(1_000_000, 0, "claude-sonnet-4-6")
    assert abs(standard - 3.0) < 0.01

    # Custom pricing (cheaper)
    custom = {"claude-sonnet-4-6": (1.0, 5.0)}
    cheap = calculate_cost(1_000_000, 0, "claude-sonnet-4-6", custom_pricing=custom)
    assert abs(cheap - 1.0) < 0.01


def test_custom_pricing_used_in_parse_claude() -> None:
    from coderace.cost import parse_claude_cost

    stdout = '{"usage": {"input_tokens": 1_000_000, "output_tokens": 0}}'
    # Can't easily get 1M tokens in JSON but test with smaller numbers
    stdout = '{"usage": {"input_tokens": 1000, "output_tokens": 100}}'

    custom = {"claude": (1.0, 2.0)}  # cheap custom pricing
    result = parse_claude_cost(stdout, "", custom_pricing=custom)
    assert result is not None
    # 1000 * 1.0/1M + 100 * 2.0/1M = 0.001 + 0.0002 = 0.0012
    expected = (1000 * 1.0 + 100 * 2.0) / 1_000_000
    assert abs(result.estimated_cost_usd - expected) < 0.0001


# ---------------------------------------------------------------------------
# --no-cost flag: disables cost tracking in adapter.run()
# ---------------------------------------------------------------------------


def test_no_cost_flag_disables_parsing() -> None:
    """When no_cost=True, base.run() should not call parse_cost."""
    from unittest.mock import MagicMock, patch

    from coderace.adapters.claude import ClaudeAdapter

    adapter = ClaudeAdapter()

    with patch.object(adapter, "parse_cost", return_value=MagicMock()) as mock_parse:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"usage": {"input_tokens": 100, "output_tokens": 20}}',
                stderr="",
            )
            result = adapter.run("task", Path("/tmp"), timeout=10, no_cost=True)

    assert result.cost_result is None
    mock_parse.assert_not_called()


def test_cost_enabled_by_default() -> None:
    """Without no_cost, parse_cost is called."""
    from unittest.mock import MagicMock, patch

    from coderace.adapters.claude import ClaudeAdapter

    fake_cost = MagicMock()
    adapter = ClaudeAdapter()

    with patch.object(adapter, "parse_cost", return_value=fake_cost) as mock_parse:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )
            result = adapter.run("task", Path("/tmp"), timeout=10)

    mock_parse.assert_called_once()
    assert result.cost_result is fake_cost


# ---------------------------------------------------------------------------
# coderace init template includes pricing comments
# ---------------------------------------------------------------------------


def test_init_template_includes_pricing_comment() -> None:
    template_path = create_template("test-task", Path("/tmp"))
    content = template_path.read_text()
    assert "pricing" in content
    assert "input_per_1m" in content
    assert "output_per_1m" in content
    # Clean up
    template_path.unlink(missing_ok=True)


def test_init_template_pricing_is_commented_out() -> None:
    """Pricing section should be commented out by default."""
    template_path = create_template("test-task2", Path("/tmp"))
    content = template_path.read_text()
    # The pricing: line should appear with # prefix
    assert "# pricing:" in content
    template_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CLI: --no-cost flag present
# ---------------------------------------------------------------------------


def test_cli_run_has_no_cost_flag() -> None:
    from typer.testing import CliRunner
    from coderace.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--no-cost" in result.output


# ---------------------------------------------------------------------------
# Task dataclass: pricing field
# ---------------------------------------------------------------------------


def test_task_pricing_field_exists() -> None:
    task = Task(
        name="t",
        description="d",
        repo=Path("."),
        test_command="echo ok",
        agents=["claude"],
    )
    assert hasattr(task, "pricing")
    assert task.pricing is None


def test_task_with_pricing() -> None:
    task = Task(
        name="t",
        description="d",
        repo=Path("."),
        test_command="echo ok",
        agents=["claude"],
        pricing={"claude": (3.0, 15.0)},
    )
    assert task.pricing == {"claude": (3.0, 15.0)}
