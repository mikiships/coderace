"""Tests for persistent ELO ratings (D3)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from coderace.benchmark import BenchmarkResult, TaskAgentResult
from coderace.cli import app
from coderace.commands.benchmark import _update_benchmark_ratings
from coderace.elo import (
    INITIAL_RATING,
    expected_score,
    update_pair_ratings,
    update_ratings,
)
from coderace.store import ResultStore


runner = CliRunner()


def _row(task: str, agent: str, trial: int, score: float) -> TaskAgentResult:
    return TaskAgentResult(
        task_name=task,
        agent=agent,
        score=score,
        wall_time=10.0,
        tests_pass=score > 0,
        exit_clean=True,
        lint_clean=True,
        timed_out=False,
        trial_number=trial,
    )


def _bench(
    tasks: list[str],
    agents: list[str],
    rows: list[TaskAgentResult],
    trials: int = 1,
) -> BenchmarkResult:
    return BenchmarkResult(
        benchmark_id="bench-elo-test",
        tasks=tasks,
        agents=agents,
        trials=trials,
        results=rows,
    )


def test_expected_score_is_half_for_equal_ratings() -> None:
    assert expected_score(1500.0, 1500.0) == 0.5


def test_single_match_update_changes_ratings() -> None:
    new_a, new_b = update_pair_ratings(1500.0, 1500.0, actual_a=1.0)
    assert new_a > 1500.0
    assert new_b < 1500.0


def test_update_ratings_initializes_missing_agents_to_1500() -> None:
    bench = _bench(
        tasks=["fibonacci"],
        agents=["claude", "codex"],
        rows=[
            _row("fibonacci", "claude", 1, 90.0),
            _row("fibonacci", "codex", 1, 70.0),
        ],
    )
    update = update_ratings(bench, current_ratings={})
    assert update.before["claude"] == INITIAL_RATING
    assert update.before["codex"] == INITIAL_RATING
    assert update.after["claude"] > INITIAL_RATING
    assert update.after["codex"] < INITIAL_RATING


def test_update_ratings_draw_when_scores_within_one_point() -> None:
    bench = _bench(
        tasks=["fibonacci"],
        agents=["claude", "codex"],
        rows=[
            _row("fibonacci", "claude", 1, 80.0),
            _row("fibonacci", "codex", 1, 79.2),
        ],
    )
    update = update_ratings(bench, current_ratings={"claude": 1500.0, "codex": 1500.0})
    assert update.after["claude"] == 1500.0
    assert update.after["codex"] == 1500.0


def test_multi_task_update_applies_round_robin_per_task() -> None:
    bench = _bench(
        tasks=["fibonacci", "json-parser"],
        agents=["claude", "codex"],
        rows=[
            _row("fibonacci", "claude", 1, 90.0),
            _row("fibonacci", "codex", 1, 70.0),
            _row("json-parser", "claude", 1, 60.0),
            _row("json-parser", "codex", 1, 95.0),
        ],
    )
    update = update_ratings(bench, current_ratings={"claude": 1500.0, "codex": 1500.0})
    assert update.after["claude"] != 1500.0
    assert update.after["codex"] != 1500.0
    assert update.after["codex"] > update.after["claude"]


def test_rating_convergence_with_repeated_wins() -> None:
    bench = _bench(
        tasks=["fibonacci"],
        agents=["claude", "codex"],
        rows=[
            _row("fibonacci", "claude", 1, 92.0),
            _row("fibonacci", "codex", 1, 61.0),
        ],
    )
    ratings: dict[str, float] = {}
    for _ in range(12):
        ratings = update_ratings(bench, current_ratings=ratings).after
    assert ratings["claude"] > ratings["codex"]
    assert ratings["claude"] - ratings["codex"] > 100.0


def test_store_reset_ratings_sets_all_to_1500(tmp_path: Path) -> None:
    store = ResultStore(db_path=tmp_path / "ratings.db")
    try:
        store.upsert_elo_ratings({"claude": 1530.0, "codex": 1470.0})
        reset_count = store.reset_elo_ratings()
        assert reset_count == 2
        ratings = store.get_elo_ratings()
        assert ratings["claude"] == 1500.0
        assert ratings["codex"] == 1500.0
    finally:
        store.close()


def test_ratings_cli_json_output(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "ratings.db"
    store = ResultStore(db_path=db_path)
    try:
        store.upsert_elo_ratings({"claude": 1510.0, "codex": 1490.0})
    finally:
        store.close()

    monkeypatch.setenv("CODERACE_DB", str(db_path))
    result = runner.invoke(app, ["ratings", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["claude"] == 1510.0
    assert payload["codex"] == 1490.0


def test_ratings_cli_reset_flag(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "ratings.db"
    store = ResultStore(db_path=db_path)
    try:
        store.upsert_elo_ratings({"claude": 1610.0})
    finally:
        store.close()

    monkeypatch.setenv("CODERACE_DB", str(db_path))
    result = runner.invoke(app, ["ratings", "--reset", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["claude"] == 1500.0


def test_result_store_backfills_elo_table_for_existing_db(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                git_ref TEXT,
                config_hash TEXT,
                agent_count INTEGER NOT NULL
            );
            CREATE TABLE agent_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                agent TEXT NOT NULL,
                composite_score REAL NOT NULL,
                wall_time REAL NOT NULL,
                lines_changed INTEGER NOT NULL,
                tests_pass INTEGER NOT NULL,
                exit_clean INTEGER NOT NULL,
                lint_clean INTEGER NOT NULL,
                cost_usd REAL,
                model_name TEXT,
                is_winner INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                benchmark_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                agents TEXT NOT NULL,
                tasks TEXT NOT NULL,
                winner TEXT,
                elapsed REAL
            );
            CREATE TABLE benchmark_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                benchmark_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                agent TEXT NOT NULL,
                score REAL NOT NULL,
                wall_time REAL NOT NULL,
                tests_pass INTEGER NOT NULL,
                exit_clean INTEGER NOT NULL,
                lint_clean INTEGER NOT NULL,
                timed_out INTEGER NOT NULL,
                cost_usd REAL,
                error TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    store = ResultStore(db_path=db_path)
    try:
        store.upsert_elo_ratings({"claude": 1522.5})
        ratings = store.get_elo_ratings()
        assert ratings["claude"] == 1522.5
    finally:
        store.close()


def test_benchmark_integration_updates_persisted_elo(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "ratings.db"
    monkeypatch.setenv("CODERACE_DB", str(db_path))
    bench = _bench(
        tasks=["fibonacci"],
        agents=["claude", "codex"],
        rows=[
            _row("fibonacci", "claude", 1, 95.0),
            _row("fibonacci", "codex", 1, 65.0),
        ],
    )

    update = _update_benchmark_ratings(bench)
    assert update is not None

    store = ResultStore(db_path=db_path)
    try:
        ratings = store.get_elo_ratings()
    finally:
        store.close()
    assert set(ratings) == {"claude", "codex"}
    assert ratings["claude"] > ratings["codex"]
