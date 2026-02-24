"""Tests for D2: auto-save integration between coderace run and ResultStore."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from coderace.cost import CostResult
from coderace.store import ResultStore
from coderace.types import Score, ScoreBreakdown


def _make_score(agent: str, composite: float = 75.0, **kwargs) -> Score:
    breakdown = ScoreBreakdown(
        tests_pass=kwargs.get("tests_pass", True),
        exit_clean=kwargs.get("exit_clean", True),
        lint_clean=kwargs.get("lint_clean", True),
        wall_time=kwargs.get("wall_time", 10.0),
        lines_changed=kwargs.get("lines_changed", 42),
    )
    cost = kwargs.get("cost_result")
    return Score(agent=agent, composite=composite, breakdown=breakdown, cost_result=cost)


class TestAutoSave:
    def test_auto_save_single_run(self, tmp_path: Path) -> None:
        """Normal save: scores saved to DB after run."""
        from coderace.cli import _auto_save_to_store

        db_path = tmp_path / "test.db"
        scores = [
            _make_score("claude", 85.0),
            _make_score("codex", 70.0),
        ]

        with patch("coderace.store.get_db_path", return_value=db_path):
            _auto_save_to_store("test-task", [scores], git_ref="abc123")

        store = ResultStore(db_path=db_path)
        runs = store.get_runs()
        assert len(runs) == 1
        assert runs[0].task_name == "test-task"
        assert runs[0].git_ref == "abc123"
        assert len(runs[0].agents) == 2
        store.close()

    def test_auto_save_multi_run(self, tmp_path: Path) -> None:
        """Multi-run: each run saved separately."""
        from coderace.cli import _auto_save_to_store

        db_path = tmp_path / "test.db"
        run1 = [_make_score("claude", 85.0)]
        run2 = [_make_score("claude", 80.0)]

        with patch("coderace.store.get_db_path", return_value=db_path):
            _auto_save_to_store("test-task", [run1, run2])

        store = ResultStore(db_path=db_path)
        runs = store.get_runs()
        assert len(runs) == 2
        store.close()

    def test_auto_save_with_cost(self, tmp_path: Path) -> None:
        """Cost data propagated to store."""
        from coderace.cli import _auto_save_to_store

        db_path = tmp_path / "test.db"
        cost = CostResult(
            input_tokens=1000,
            output_tokens=500,
            estimated_cost_usd=0.05,
            model_name="claude-sonnet-4-6",
            pricing_source="parsed",
        )
        scores = [_make_score("claude", 85.0, cost_result=cost)]

        with patch("coderace.store.get_db_path", return_value=db_path):
            _auto_save_to_store("test-task", [scores])

        store = ResultStore(db_path=db_path)
        runs = store.get_runs()
        a = runs[0].agents[0]
        assert a.cost_usd == pytest.approx(0.05)
        assert a.model_name == "claude-sonnet-4-6"
        store.close()

    def test_auto_save_graceful_on_db_error(self, tmp_path: Path) -> None:
        """DB errors don't crash the run."""
        from coderace.cli import _auto_save_to_store

        scores = [_make_score("claude")]

        # Use a path that can't be created (file as parent)
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir")
        bad_path = blocker / "sub" / "test.db"

        with patch("coderace.store.get_db_path", return_value=bad_path):
            # Should not raise
            _auto_save_to_store("test-task", [scores])

    def test_no_save_when_empty_scores(self, tmp_path: Path) -> None:
        """No save when all_run_scores is empty list."""
        from coderace.cli import _auto_save_to_store

        db_path = tmp_path / "test.db"

        with patch("coderace.store.get_db_path", return_value=db_path):
            _auto_save_to_store("t", [])

        # DB should still be created (store init creates it), but no runs
        store = ResultStore(db_path=db_path)
        runs = store.get_runs()
        assert len(runs) == 0
        store.close()

    def test_agent_result_fields_correct(self, tmp_path: Path) -> None:
        """All score breakdown fields correctly mapped."""
        from coderace.cli import _auto_save_to_store

        db_path = tmp_path / "test.db"
        scores = [
            _make_score(
                "claude",
                85.0,
                tests_pass=False,
                exit_clean=True,
                lint_clean=False,
                wall_time=12.3,
                lines_changed=77,
            )
        ]

        with patch("coderace.store.get_db_path", return_value=db_path):
            _auto_save_to_store("t", [scores])

        store = ResultStore(db_path=db_path)
        runs = store.get_runs()
        a = runs[0].agents[0]
        assert a.agent == "claude"
        assert a.composite_score == pytest.approx(85.0)
        assert a.tests_pass is False
        assert a.exit_clean is True
        assert a.lint_clean is False
        assert a.wall_time == pytest.approx(12.3)
        assert a.lines_changed == 77
        store.close()

    def test_winner_set_correctly(self, tmp_path: Path) -> None:
        """Winner correctly identified in auto-save."""
        from coderace.cli import _auto_save_to_store

        db_path = tmp_path / "test.db"
        scores = [
            _make_score("claude", 90.0),
            _make_score("codex", 60.0),
        ]

        with patch("coderace.store.get_db_path", return_value=db_path):
            _auto_save_to_store("t", [scores])

        store = ResultStore(db_path=db_path)
        runs = store.get_runs()
        agents = runs[0].agents
        winners = [a for a in agents if a.is_winner]
        assert len(winners) == 1
        assert winners[0].agent == "claude"
        store.close()

    def test_no_cost_result_stores_none(self, tmp_path: Path) -> None:
        """When cost_result is None, cost_usd stored as None."""
        from coderace.cli import _auto_save_to_store

        db_path = tmp_path / "test.db"
        scores = [_make_score("claude", 75.0)]

        with patch("coderace.store.get_db_path", return_value=db_path):
            _auto_save_to_store("t", [scores])

        store = ResultStore(db_path=db_path)
        runs = store.get_runs()
        a = runs[0].agents[0]
        assert a.cost_usd is None
        assert a.model_name is None
        store.close()
