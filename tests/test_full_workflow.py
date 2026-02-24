"""Integration test: run -> save -> leaderboard -> history full workflow."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from coderace.cli import app
from coderace.store import ResultStore

runner = CliRunner()


class TestFullWorkflow:
    """End-to-end workflow: save results, query leaderboard, query history."""

    def test_save_then_leaderboard_then_history(self, tmp_path: Path) -> None:
        """Full roundtrip: save multiple runs, query leaderboard, query history."""
        db_path = tmp_path / "workflow.db"
        store = ResultStore(db_path=db_path)

        # Simulate 3 races
        store.save_run("fix-auth-bug", [
            {"agent": "claude", "composite_score": 85.0, "wall_time": 10.0,
             "lines_changed": 42, "tests_pass": True, "exit_clean": True,
             "lint_clean": True, "cost_usd": 0.05},
            {"agent": "codex", "composite_score": 70.0, "wall_time": 15.0,
             "lines_changed": 98, "tests_pass": True, "exit_clean": True,
             "lint_clean": False, "cost_usd": 0.03},
        ])
        store.save_run("add-types", [
            {"agent": "claude", "composite_score": 60.0, "wall_time": 20.0,
             "lines_changed": 100, "tests_pass": False, "exit_clean": True,
             "lint_clean": True, "cost_usd": 0.08},
            {"agent": "codex", "composite_score": 80.0, "wall_time": 12.0,
             "lines_changed": 55, "tests_pass": True, "exit_clean": True,
             "lint_clean": True, "cost_usd": 0.04},
        ])
        store.save_run("fix-auth-bug", [
            {"agent": "claude", "composite_score": 90.0, "wall_time": 8.0,
             "lines_changed": 30, "tests_pass": True, "exit_clean": True,
             "lint_clean": True, "cost_usd": 0.06},
            {"agent": "aider", "composite_score": 55.0, "wall_time": 25.0,
             "lines_changed": 120, "tests_pass": False, "exit_clean": True,
             "lint_clean": False, "cost_usd": 0.02},
        ])
        store.close()

        # Leaderboard: check all agents present, ranking correct
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--format", "json"])
        assert result.exit_code == 0
        lb = json.loads(result.output)["leaderboard"]
        agents = [e["agent"] for e in lb]
        assert "claude" in agents
        assert "codex" in agents
        assert "aider" in agents

        # Claude: 2 wins (fix-auth-bug x2), codex: 1 win (add-types), aider: 0 wins
        claude_entry = next(e for e in lb if e["agent"] == "claude")
        codex_entry = next(e for e in lb if e["agent"] == "codex")
        aider_entry = next(e for e in lb if e["agent"] == "aider")
        assert claude_entry["wins"] == 2
        assert codex_entry["wins"] == 1
        assert aider_entry["wins"] == 0

        # History: 3 runs total
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--format", "json"])
        assert result.exit_code == 0
        history = json.loads(result.output)["history"]
        assert len(history) == 3

        # History: newest first
        assert history[0]["run_id"] > history[-1]["run_id"]

        # History: filter by task
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--task", "fix-auth-bug", "--format", "json"])
        history = json.loads(result.output)["history"]
        assert len(history) == 2
        assert all(r["task_name"] == "fix-auth-bug" for r in history)

        # History: filter by agent
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["history", "--agent", "aider", "--format", "json"])
        history = json.loads(result.output)["history"]
        assert len(history) == 1

        # Leaderboard: filter by task
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--task", "fix-auth-bug", "--format", "json"])
        lb = json.loads(result.output)["leaderboard"]
        task_agents = [e["agent"] for e in lb]
        assert "claude" in task_agents
        # codex not in fix-auth-bug runs (only run 1 and 3 have fix-auth-bug, run1 has codex)
        assert "codex" in task_agents  # codex was in first fix-auth-bug run

        # Leaderboard: min-runs filter
        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--min-runs", "3", "--format", "json"])
        lb = json.loads(result.output)["leaderboard"]
        # Only claude has 3 races
        assert len(lb) == 1
        assert lb[0]["agent"] == "claude"

    def test_corrupted_db_graceful(self, tmp_path: Path) -> None:
        """Corrupted DB file handled gracefully."""
        db_path = tmp_path / "bad.db"
        db_path.write_text("not a sqlite database")

        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard"])
        # Should fail gracefully (exit 1 or show error)
        assert result.exit_code != 0 or "error" in result.output.lower() or "cannot" in result.output.lower()

    def test_single_agent_race(self, tmp_path: Path) -> None:
        """Single agent in a race still works."""
        db_path = tmp_path / "single.db"
        store = ResultStore(db_path=db_path)
        store.save_run("solo-task", [
            {"agent": "claude", "composite_score": 75.0, "wall_time": 10.0,
             "lines_changed": 42, "tests_pass": True, "exit_clean": True,
             "lint_clean": True},
        ])
        store.close()

        with patch("coderace.store.get_db_path", return_value=db_path):
            result = runner.invoke(app, ["leaderboard", "--format", "json"])
        lb = json.loads(result.output)["leaderboard"]
        assert len(lb) == 1
        assert lb[0]["wins"] == 1
        assert lb[0]["win_rate"] == 1.0

    def test_auto_save_then_query(self, tmp_path: Path) -> None:
        """_auto_save_to_store results are visible in leaderboard/history."""
        from coderace.cli import _auto_save_to_store
        from coderace.cost import CostResult
        from coderace.types import Score, ScoreBreakdown

        db_path = tmp_path / "autosave.db"

        scores = [
            Score(
                agent="claude",
                composite=85.0,
                breakdown=ScoreBreakdown(
                    tests_pass=True, exit_clean=True, lint_clean=True,
                    wall_time=10.0, lines_changed=42,
                ),
                cost_result=CostResult(
                    input_tokens=1000, output_tokens=500,
                    estimated_cost_usd=0.05, model_name="claude-sonnet-4-6",
                    pricing_source="parsed",
                ),
            ),
        ]

        with patch("coderace.store.get_db_path", return_value=db_path):
            _auto_save_to_store("my-task", [scores], git_ref="abc123")

            # Check leaderboard
            result = runner.invoke(app, ["leaderboard", "--format", "json"])
            lb = json.loads(result.output)["leaderboard"]
            assert len(lb) == 1
            assert lb[0]["agent"] == "claude"

            # Check history
            result = runner.invoke(app, ["history", "--format", "json"])
            h = json.loads(result.output)["history"]
            assert len(h) == 1
            assert h[0]["task_name"] == "my-task"
