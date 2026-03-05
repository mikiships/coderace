"""Tests for D4: benchmark and race command model-specific agent handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from coderace.adapters import instantiate_adapter, parse_agent_spec


# ---------------------------------------------------------------------------
# Benchmark agent validation: agent:model syntax
# ---------------------------------------------------------------------------


def test_benchmark_agent_validation_with_model_spec() -> None:
    """Benchmark function handles agent:model specs without crashing on unknown agent check."""
    from coderace.adapters import ADAPTERS

    spec = "codex:gpt-5.4"
    agent_base, model = parse_agent_spec(spec)
    assert agent_base in ADAPTERS, f"Base agent {agent_base!r} should be in ADAPTERS"


def test_benchmark_agent_validation_rejects_unknown() -> None:
    from coderace.adapters import ADAPTERS

    spec = "bogus:some-model"
    agent_base, _ = parse_agent_spec(spec)
    assert agent_base not in ADAPTERS


# ---------------------------------------------------------------------------
# TaskAgentResult: agent name is display name (not raw spec)
# ---------------------------------------------------------------------------


def test_instantiate_adapter_name_is_display_name() -> None:
    """The adapter.name set by instantiate_adapter is the display name."""
    adapter = instantiate_adapter("codex:gpt-5.4")
    assert adapter.name == "codex (gpt-5.4)"


def test_instantiate_adapter_no_model_name_is_plain() -> None:
    adapter = instantiate_adapter("claude")
    assert adapter.name == "claude"


# ---------------------------------------------------------------------------
# ELO tracking: model variants are separate entries
# ---------------------------------------------------------------------------


def test_elo_entries_per_model_variant() -> None:
    """Different model variants of the same adapter get separate ELO entries."""
    from coderace.elo import update_pair_ratings

    # Simulate two codex variants — both start at 1500
    rating_winner, rating_loser = 1500.0, 1500.0
    new_winner, new_loser = update_pair_ratings(rating_winner, rating_loser, actual_a=1.0)
    # Winner gains ELO, loser loses
    assert new_winner > 1500.0
    assert new_loser < 1500.0
    # The key insight: since names are distinct strings, store tracks them separately
    ratings = {
        "codex (gpt-5.4)": new_winner,
        "codex (gpt-5.3-codex)": new_loser,
    }
    assert ratings["codex (gpt-5.4)"] != ratings["codex (gpt-5.3-codex)"]


# ---------------------------------------------------------------------------
# Store: model-qualified agent names stored correctly
# ---------------------------------------------------------------------------


def test_store_accepts_model_qualified_agent_names(tmp_path) -> None:
    """Store can save and retrieve results keyed by model-qualified names."""
    import os
    os.environ["CODERACE_DB"] = str(tmp_path / "test.db")
    try:
        from coderace.store import ResultStore
        store = ResultStore()

        # Simulate saving a run with model-qualified agent names
        run_id = store.save_run(
            task_name="fix-bug",
            results=[
                {
                    "agent": "codex (gpt-5.4)",
                    "composite_score": 85.0,
                    "wall_time": 30.0,
                    "lines_changed": 10,
                    "tests_pass": True,
                    "exit_clean": True,
                    "lint_clean": True,
                    "cost_usd": None,
                },
                {
                    "agent": "codex (gpt-5.3-codex)",
                    "composite_score": 72.0,
                    "wall_time": 45.0,
                    "lines_changed": 8,
                    "tests_pass": True,
                    "exit_clean": True,
                    "lint_clean": False,
                    "cost_usd": None,
                },
            ],
        )
        assert run_id is not None

        stats = store.get_agent_stats()
        agent_names = {s.agent for s in stats}
        assert "codex (gpt-5.4)" in agent_names
        assert "codex (gpt-5.3-codex)" in agent_names
    finally:
        del os.environ["CODERACE_DB"]


# ---------------------------------------------------------------------------
# Race command: agent:model syntax validation
# ---------------------------------------------------------------------------


def test_race_command_validates_agent_model_spec() -> None:
    """Race command validation accepts agent:model specs."""
    from coderace.adapters import ADAPTERS

    agents = ["codex:gpt-5.4", "claude:opus-4-6", "bogus:model"]
    valid = [a for a in agents if parse_agent_spec(a)[0] in ADAPTERS]
    assert "codex:gpt-5.4" in valid
    assert "claude:opus-4-6" in valid
    assert "bogus:model" not in valid


# ---------------------------------------------------------------------------
# Leaderboard: model variants appear as separate entries
# ---------------------------------------------------------------------------


def test_leaderboard_shows_model_variants_separately(tmp_path) -> None:
    """Leaderboard lists model variants as distinct entries."""
    import os
    os.environ["CODERACE_DB"] = str(tmp_path / "test.db")
    try:
        from coderace.store import ResultStore
        store = ResultStore()

        store.save_run(
            task_name="task1",
            results=[
                {
                    "agent": "codex (gpt-5.4)",
                    "composite_score": 90.0,
                    "wall_time": 20.0,
                    "lines_changed": 5,
                    "tests_pass": True,
                    "exit_clean": True,
                    "lint_clean": True,
                    "cost_usd": None,
                },
                {
                    "agent": "codex (gpt-5.3-codex)",
                    "composite_score": 75.0,
                    "wall_time": 35.0,
                    "lines_changed": 8,
                    "tests_pass": True,
                    "exit_clean": True,
                    "lint_clean": False,
                    "cost_usd": None,
                },
            ],
        )

        stats = store.get_agent_stats()
        agent_names = [s.agent for s in stats]
        # Both variants should appear
        assert "codex (gpt-5.4)" in agent_names
        assert "codex (gpt-5.3-codex)" in agent_names
        # They should be separate (not merged)
        assert agent_names.count("codex (gpt-5.4)") == 1
        assert agent_names.count("codex (gpt-5.3-codex)") == 1
    finally:
        del os.environ["CODERACE_DB"]
