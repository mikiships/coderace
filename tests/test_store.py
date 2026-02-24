"""Tests for coderace.store — ResultStore."""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

import pytest

from coderace.store import ResultStore, get_db_path


def _make_result(agent: str, score: float = 75.0, **kwargs) -> dict:
    """Helper to build a minimal agent result dict."""
    base = {
        "agent": agent,
        "composite_score": score,
        "wall_time": 10.5,
        "lines_changed": 42,
        "tests_pass": True,
        "exit_clean": True,
        "lint_clean": True,
    }
    base.update(kwargs)
    return base


@pytest.fixture
def store(tmp_path: Path) -> ResultStore:
    db_path = tmp_path / "test.db"
    s = ResultStore(db_path=db_path)
    yield s
    s.close()


class TestSaveRun:
    def test_save_and_returns_id(self, store: ResultStore) -> None:
        run_id = store.save_run("task-1", [_make_result("claude")])
        assert isinstance(run_id, int)
        assert run_id >= 1

    def test_save_multiple_agents(self, store: ResultStore) -> None:
        results = [
            _make_result("claude", score=85.0),
            _make_result("codex", score=70.0),
        ]
        run_id = store.save_run("task-1", results)
        runs = store.get_runs()
        assert len(runs) == 1
        assert len(runs[0].agents) == 2

    def test_save_empty_results(self, store: ResultStore) -> None:
        run_id = store.save_run("task-1", [])
        runs = store.get_runs()
        assert len(runs) == 1
        assert len(runs[0].agents) == 0

    def test_winner_detection(self, store: ResultStore) -> None:
        results = [
            _make_result("claude", score=85.0),
            _make_result("codex", score=70.0),
            _make_result("aider", score=60.0),
        ]
        store.save_run("task-1", results)
        runs = store.get_runs()
        agents = runs[0].agents
        winners = [a for a in agents if a.is_winner]
        assert len(winners) == 1
        assert winners[0].agent == "claude"

    def test_tied_winners(self, store: ResultStore) -> None:
        results = [
            _make_result("claude", score=80.0),
            _make_result("codex", score=80.0),
        ]
        store.save_run("task-1", results)
        runs = store.get_runs()
        winners = [a for a in runs[0].agents if a.is_winner]
        assert len(winners) == 2


class TestGetRuns:
    def test_empty_db(self, store: ResultStore) -> None:
        runs = store.get_runs()
        assert runs == []

    def test_filter_by_task(self, store: ResultStore) -> None:
        store.save_run("task-a", [_make_result("claude")])
        store.save_run("task-b", [_make_result("codex")])

        runs = store.get_runs(task_name="task-a")
        assert len(runs) == 1
        assert runs[0].task_name == "task-a"

    def test_filter_by_agent(self, store: ResultStore) -> None:
        store.save_run("task-1", [_make_result("claude"), _make_result("codex")])
        store.save_run("task-2", [_make_result("aider")])

        runs = store.get_runs(agent="claude")
        assert len(runs) == 1
        assert runs[0].task_name == "task-1"

    def test_limit(self, store: ResultStore) -> None:
        for i in range(10):
            store.save_run(f"task-{i}", [_make_result("claude")])

        runs = store.get_runs(limit=3)
        assert len(runs) == 3

    def test_newest_first(self, store: ResultStore) -> None:
        store.save_run("task-old", [_make_result("claude")])
        store.save_run("task-new", [_make_result("claude")])

        runs = store.get_runs()
        # Newest first
        assert runs[0].task_name == "task-new"
        assert runs[1].task_name == "task-old"

    def test_git_ref_saved(self, store: ResultStore) -> None:
        store.save_run("task-1", [_make_result("claude")], git_ref="abc123")
        runs = store.get_runs()
        assert runs[0].git_ref == "abc123"


class TestGetAgentStats:
    def test_empty_db(self, store: ResultStore) -> None:
        stats = store.get_agent_stats()
        assert stats == []

    def test_single_run(self, store: ResultStore) -> None:
        store.save_run("task-1", [
            _make_result("claude", score=85.0),
            _make_result("codex", score=70.0),
        ])
        stats = store.get_agent_stats()
        assert len(stats) == 2
        claude_stat = next(s for s in stats if s.agent == "claude")
        assert claude_stat.wins == 1
        assert claude_stat.races == 1
        assert claude_stat.win_rate == 1.0
        assert claude_stat.avg_score == 85.0

    def test_multi_run_stats(self, store: ResultStore) -> None:
        # Claude wins first, codex wins second
        store.save_run("task-1", [
            _make_result("claude", score=90.0),
            _make_result("codex", score=70.0),
        ])
        store.save_run("task-2", [
            _make_result("claude", score=60.0),
            _make_result("codex", score=80.0),
        ])
        stats = store.get_agent_stats()
        for s in stats:
            assert s.wins == 1
            assert s.races == 2
            assert s.win_rate == 0.5

    def test_filter_by_agent(self, store: ResultStore) -> None:
        store.save_run("t", [
            _make_result("claude", score=80.0),
            _make_result("codex", score=70.0),
        ])
        stats = store.get_agent_stats(agent="claude")
        assert len(stats) == 1
        assert stats[0].agent == "claude"

    def test_filter_by_task(self, store: ResultStore) -> None:
        store.save_run("task-a", [_make_result("claude", score=80.0)])
        store.save_run("task-b", [_make_result("claude", score=60.0)])
        stats = store.get_agent_stats(task_name="task-a")
        assert len(stats) == 1
        assert stats[0].avg_score == 80.0

    def test_min_runs_filter(self, store: ResultStore) -> None:
        store.save_run("t", [_make_result("claude"), _make_result("codex")])
        store.save_run("t", [_make_result("claude")])
        # claude has 2 races, codex has 1
        stats = store.get_agent_stats(min_runs=2)
        assert len(stats) == 1
        assert stats[0].agent == "claude"

    def test_cost_tracking(self, store: ResultStore) -> None:
        store.save_run("t", [
            _make_result("claude", cost_usd=0.05, model_name="claude-sonnet-4-6"),
        ])
        stats = store.get_agent_stats()
        assert stats[0].avg_cost == pytest.approx(0.05)

    def test_since_filter(self, store: ResultStore) -> None:
        # Insert a run, then filter with a future date (should return 0)
        store.save_run("t", [_make_result("claude")])
        stats = store.get_agent_stats(since="2099-01-01")
        assert stats == []


class TestEdgeCases:
    def test_auto_create_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "sub" / "dir" / "test.db"
        store = ResultStore(db_path=db_path)
        assert db_path.exists()
        store.close()

    def test_env_var_db_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db = tmp_path / "env.db"
        monkeypatch.setenv("CODERACE_DB", str(db))
        assert get_db_path() == db

    def test_default_db_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CODERACE_DB", raising=False)
        path = get_db_path()
        assert path == Path.home() / ".coderace" / "results.db"

    def test_concurrent_writes(self, tmp_path: Path) -> None:
        db_path = tmp_path / "concurrent.db"
        errors: list[Exception] = []

        def write_run(idx: int) -> None:
            try:
                s = ResultStore(db_path=db_path)
                s.save_run(f"task-{idx}", [_make_result("claude", score=float(idx))])
                s.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_run, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent write errors: {errors}"

        # Verify all runs saved
        s = ResultStore(db_path=db_path)
        runs = s.get_runs(limit=100)
        assert len(runs) == 5
        s.close()

    def test_close_and_reopen(self, tmp_path: Path) -> None:
        db_path = tmp_path / "reopen.db"
        store = ResultStore(db_path=db_path)
        store.save_run("t", [_make_result("claude")])
        store.close()

        store2 = ResultStore(db_path=db_path)
        runs = store2.get_runs()
        assert len(runs) == 1
        store2.close()

    def test_agent_fields_round_trip(self, store: ResultStore) -> None:
        result = _make_result(
            "claude",
            score=85.5,
            wall_time=12.3,
            lines_changed=99,
            tests_pass=False,
            exit_clean=True,
            lint_clean=False,
            cost_usd=0.123,
            model_name="claude-sonnet-4-6",
        )
        store.save_run("t", [result])
        runs = store.get_runs()
        a = runs[0].agents[0]
        assert a.agent == "claude"
        assert a.composite_score == pytest.approx(85.5)
        assert a.wall_time == pytest.approx(12.3)
        assert a.lines_changed == 99
        assert a.tests_pass is False
        assert a.exit_clean is True
        assert a.lint_clean is False
        assert a.cost_usd == pytest.approx(0.123)
        assert a.model_name == "claude-sonnet-4-6"
