"""SQLite-backed persistent storage for race results."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _default_db_path() -> Path:
    """Return the default database path (~/.coderace/results.db)."""
    return Path.home() / ".coderace" / "results.db"


def get_db_path() -> Path:
    """Return the database path from env var or default."""
    env = os.environ.get("CODERACE_DB")
    if env:
        return Path(env)
    return _default_db_path()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    git_ref TEXT,
    config_hash TEXT,
    agent_count INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_name);
CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp);

CREATE TABLE IF NOT EXISTS agent_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
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

CREATE INDEX IF NOT EXISTS idx_agent_results_run ON agent_results(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_results_agent ON agent_results(agent);

CREATE TABLE IF NOT EXISTS benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_id TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    agents TEXT NOT NULL,
    tasks TEXT NOT NULL,
    winner TEXT,
    elapsed REAL
);

CREATE INDEX IF NOT EXISTS idx_benchmarks_timestamp ON benchmarks(timestamp);

CREATE TABLE IF NOT EXISTS benchmark_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_id TEXT NOT NULL REFERENCES benchmarks(benchmark_id),
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

CREATE INDEX IF NOT EXISTS idx_benchmark_results_bid ON benchmark_results(benchmark_id);
"""


@dataclass
class RunRecord:
    """A saved run record."""

    run_id: int
    task_name: str
    timestamp: str
    git_ref: Optional[str]
    agents: list[AgentRecord]


@dataclass
class AgentRecord:
    """A saved agent result record."""

    agent: str
    composite_score: float
    wall_time: float
    lines_changed: int
    tests_pass: bool
    exit_clean: bool
    lint_clean: bool
    cost_usd: Optional[float]
    model_name: Optional[str]
    is_winner: bool


@dataclass
class AgentStat:
    """Aggregate statistics for an agent across runs."""

    agent: str
    wins: int
    races: int
    win_rate: float
    avg_score: float
    avg_cost: Optional[float]
    avg_time: float


class ResultStore:
    """SQLite-backed result store for coderace runs."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = get_db_path()
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path), timeout=10)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_tables(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def save_run(
        self,
        task_name: str,
        results: list[dict],
        git_ref: str | None = None,
        config_hash: str | None = None,
    ) -> int:
        """Save a run with its agent results.

        Args:
            task_name: Name of the task.
            results: List of dicts with keys: agent, composite_score, wall_time,
                     lines_changed, tests_pass, exit_clean, lint_clean,
                     cost_usd (optional), model_name (optional).
            git_ref: Git ref at time of run.
            config_hash: Hash of task configuration.

        Returns:
            The run ID.
        """
        conn = self._get_conn()
        timestamp = datetime.now(timezone.utc).isoformat()

        cursor = conn.execute(
            "INSERT INTO runs (task_name, timestamp, git_ref, config_hash, agent_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (task_name, timestamp, git_ref, config_hash, len(results)),
        )
        run_id = cursor.lastrowid
        assert run_id is not None

        # Determine winner(s): highest composite_score
        if results:
            max_score = max(r["composite_score"] for r in results)
        else:
            max_score = 0.0

        for r in results:
            is_winner = 1 if r["composite_score"] == max_score else 0
            conn.execute(
                "INSERT INTO agent_results "
                "(run_id, agent, composite_score, wall_time, lines_changed, "
                "tests_pass, exit_clean, lint_clean, cost_usd, model_name, is_winner) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    r["agent"],
                    r["composite_score"],
                    r["wall_time"],
                    r["lines_changed"],
                    1 if r["tests_pass"] else 0,
                    1 if r["exit_clean"] else 0,
                    1 if r["lint_clean"] else 0,
                    r.get("cost_usd"),
                    r.get("model_name"),
                    is_winner,
                ),
            )

        conn.commit()
        return run_id

    def get_runs(
        self,
        task_name: str | None = None,
        agent: str | None = None,
        limit: int = 50,
    ) -> list[RunRecord]:
        """Query past runs.

        Args:
            task_name: Filter by task name.
            agent: Filter to only runs that include this agent.
            limit: Maximum number of runs to return.

        Returns:
            List of RunRecord objects, newest first.
        """
        conn = self._get_conn()

        query = "SELECT DISTINCT r.id, r.task_name, r.timestamp, r.git_ref FROM runs r"
        params: list = []

        if agent:
            query += " JOIN agent_results ar ON ar.run_id = r.id"

        conditions = []
        if task_name:
            conditions.append("r.task_name = ?")
            params.append(task_name)
        if agent:
            conditions.append("ar.agent = ?")
            params.append(agent)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY r.timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()

        result = []
        for row in rows:
            agents = self._get_agents_for_run(row["id"])
            result.append(
                RunRecord(
                    run_id=row["id"],
                    task_name=row["task_name"],
                    timestamp=row["timestamp"],
                    git_ref=row["git_ref"],
                    agents=agents,
                )
            )
        return result

    def _get_agents_for_run(self, run_id: int) -> list[AgentRecord]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM agent_results WHERE run_id = ? ORDER BY composite_score DESC",
            (run_id,),
        ).fetchall()
        return [
            AgentRecord(
                agent=r["agent"],
                composite_score=r["composite_score"],
                wall_time=r["wall_time"],
                lines_changed=r["lines_changed"],
                tests_pass=bool(r["tests_pass"]),
                exit_clean=bool(r["exit_clean"]),
                lint_clean=bool(r["lint_clean"]),
                cost_usd=r["cost_usd"],
                model_name=r["model_name"],
                is_winner=bool(r["is_winner"]),
            )
            for r in rows
        ]

    def get_agent_stats(
        self,
        agent: str | None = None,
        task_name: str | None = None,
        since: str | None = None,
        min_runs: int = 0,
    ) -> list[AgentStat]:
        """Aggregate statistics per agent.

        Args:
            agent: Filter to a specific agent.
            task_name: Filter to a specific task.
            since: ISO date or relative shorthand ("7d", "30d").
            min_runs: Exclude agents with fewer than this many races.

        Returns:
            List of AgentStat objects, sorted by win rate descending.
        """
        conn = self._get_conn()

        query = (
            "SELECT ar.agent, "
            "COUNT(*) as races, "
            "SUM(ar.is_winner) as wins, "
            "AVG(ar.composite_score) as avg_score, "
            "AVG(ar.cost_usd) as avg_cost, "
            "AVG(ar.wall_time) as avg_time "
            "FROM agent_results ar "
            "JOIN runs r ON r.id = ar.run_id"
        )
        params: list = []
        conditions = []

        if agent:
            conditions.append("ar.agent = ?")
            params.append(agent)
        if task_name:
            conditions.append("r.task_name = ?")
            params.append(task_name)
        if since:
            since_dt = _parse_since(since)
            if since_dt:
                conditions.append("r.timestamp >= ?")
                params.append(since_dt)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " GROUP BY ar.agent"

        if min_runs > 0:
            query += " HAVING races >= ?"
            params.append(min_runs)

        query += " ORDER BY wins * 1.0 / COUNT(*) DESC, avg_score DESC"

        rows = conn.execute(query, params).fetchall()
        return [
            AgentStat(
                agent=r["agent"],
                wins=r["wins"],
                races=r["races"],
                win_rate=r["wins"] / r["races"] if r["races"] > 0 else 0.0,
                avg_score=r["avg_score"],
                avg_cost=r["avg_cost"],
                avg_time=r["avg_time"],
            )
            for r in rows
        ]


    def save_benchmark(self, benchmark_result, stats) -> None:
        """Save a BenchmarkResult and its stats to the store."""
        from coderace.benchmark_stats import BenchmarkStats

        conn = self._get_conn()
        ts = datetime.now(timezone.utc).isoformat()
        winner = stats.agent_stats[0].agent if stats.agent_stats else None
        elapsed = benchmark_result.elapsed if benchmark_result.finished_at else None

        agents_str = ",".join(benchmark_result.agents)
        tasks_str = ",".join(benchmark_result.tasks)

        conn.execute(
            "INSERT OR REPLACE INTO benchmarks "
            "(benchmark_id, timestamp, agents, tasks, winner, elapsed) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (benchmark_result.benchmark_id, ts, agents_str, tasks_str, winner, elapsed),
        )

        for r in benchmark_result.results:
            conn.execute(
                "INSERT INTO benchmark_results "
                "(benchmark_id, task_name, agent, score, wall_time, tests_pass, "
                "exit_clean, lint_clean, timed_out, cost_usd, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    benchmark_result.benchmark_id,
                    r.task_name,
                    r.agent,
                    r.score,
                    r.wall_time,
                    1 if r.tests_pass else 0,
                    1 if r.exit_clean else 0,
                    1 if r.lint_clean else 0,
                    1 if r.timed_out else 0,
                    r.cost_usd,
                    r.error,
                ),
            )
        conn.commit()

    def get_benchmarks(self, limit: int = 10) -> list[dict]:
        """List past benchmark runs, newest first."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT benchmark_id, timestamp, agents, tasks, winner, elapsed "
            "FROM benchmarks ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for row in rows:
            tasks_list = row["tasks"].split(",") if row["tasks"] else []
            result.append({
                "benchmark_id": row["benchmark_id"],
                "timestamp": row["timestamp"],
                "agents": row["agents"],
                "task_count": len(tasks_list),
                "winner": row["winner"] or "-",
                "elapsed": row["elapsed"],
            })
        return result

    def get_benchmark(self, benchmark_id: str) -> dict | None:
        """Retrieve a full benchmark result by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM benchmarks WHERE benchmark_id = ?",
            (benchmark_id,),
        ).fetchone()
        if row is None:
            return None

        detail_rows = conn.execute(
            "SELECT * FROM benchmark_results WHERE benchmark_id = ?",
            (benchmark_id,),
        ).fetchall()

        agents = row["agents"].split(",") if row["agents"] else []
        tasks = row["tasks"].split(",") if row["tasks"] else []

        results = [
            {
                "task_name": r["task_name"],
                "agent": r["agent"],
                "score": r["score"],
                "wall_time": r["wall_time"],
                "tests_pass": bool(r["tests_pass"]),
                "exit_clean": bool(r["exit_clean"]),
                "lint_clean": bool(r["lint_clean"]),
                "timed_out": bool(r["timed_out"]),
                "cost_usd": r["cost_usd"],
                "error": r["error"],
            }
            for r in detail_rows
        ]

        return {
            "benchmark_id": row["benchmark_id"],
            "timestamp": row["timestamp"],
            "agents": agents,
            "tasks": tasks,
            "winner": row["winner"],
            "elapsed": row["elapsed"],
            "results": results,
        }


def _parse_since(since: str) -> str | None:
    """Parse a since string into an ISO datetime string.

    Supports ISO dates (2024-01-01) and relative shorthand (7d, 30d).
    """
    from datetime import timedelta

    since = since.strip()

    # Relative shorthand: "7d", "30d", etc.
    if since.endswith("d") and since[:-1].isdigit():
        days = int(since[:-1])
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return dt.isoformat()

    # Try ISO date
    try:
        dt = datetime.fromisoformat(since)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return None
