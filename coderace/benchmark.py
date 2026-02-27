"""Benchmark runner: orchestrates running multiple tasks against multiple agents."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaskAgentResult:
    """Result for a single (task, agent) pair in a benchmark run."""

    task_name: str
    agent: str
    score: float  # composite score (0-100 scale)
    wall_time: float  # seconds
    tests_pass: bool
    exit_clean: bool
    lint_clean: bool
    timed_out: bool
    cost_usd: Optional[float] = None
    error: Optional[str] = None  # error message if run failed entirely


@dataclass
class BenchmarkResult:
    """Collected results from a full benchmark run."""

    benchmark_id: str  # timestamp-based unique ID
    agents: list[str]
    tasks: list[str]
    results: list[TaskAgentResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def get(self, task_name: str, agent: str) -> Optional[TaskAgentResult]:
        """Look up a specific (task, agent) result."""
        for r in self.results:
            if r.task_name == task_name and r.agent == agent:
                return r
        return None

    def finish(self) -> None:
        """Mark the benchmark as finished."""
        self.finished_at = time.time()

    @property
    def elapsed(self) -> float:
        """Total elapsed time in seconds."""
        end = self.finished_at or time.time()
        return end - self.started_at


def _make_benchmark_id() -> str:
    """Create a timestamp-based benchmark ID."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("bench-%Y%m%d-%H%M%S")


def run_benchmark(
    agents: list[str],
    tasks: list[str],
    timeout: int = 300,
    parallel: int = 1,
    progress_callback=None,
) -> BenchmarkResult:
    """Run a benchmark: all tasks x all agents.

    Args:
        agents: Agent names to race.
        tasks: Built-in task names to run.
        timeout: Per-task timeout in seconds.
        parallel: Number of agents to run in parallel (default 1 = sequential).
        progress_callback: Optional callable(task, agent, status) for progress.

    Returns:
        BenchmarkResult with all collected results.
    """
    import tempfile
    from pathlib import Path

    from coderace.adapters import ADAPTERS
    from coderace.builtins import get_builtin_path
    from coderace.git_ops import (
        branch_name_for,
        checkout,
        create_branch,
        get_current_ref,
        get_diff_stat,
    )
    from coderace.scorer import compute_score
    from coderace.task import load_task

    benchmark_id = _make_benchmark_id()
    result = BenchmarkResult(
        benchmark_id=benchmark_id,
        agents=list(agents),
        tasks=list(tasks),
    )

    for task_name in tasks:
        try:
            task_path = get_builtin_path(task_name)
            task = load_task(task_path)
        except Exception as exc:
            if progress_callback:
                progress_callback(task_name, "*", f"ERROR: {exc}")
            for agent in agents:
                result.results.append(TaskAgentResult(
                    task_name=task_name,
                    agent=agent,
                    score=0.0,
                    wall_time=0.0,
                    tests_pass=False,
                    exit_clean=False,
                    lint_clean=False,
                    timed_out=False,
                    error=str(exc),
                ))
            continue

        repo = task.repo
        if not repo.exists():
            for agent in agents:
                result.results.append(TaskAgentResult(
                    task_name=task_name,
                    agent=agent,
                    score=0.0,
                    wall_time=0.0,
                    tests_pass=False,
                    exit_clean=False,
                    lint_clean=False,
                    timed_out=False,
                    error=f"Repo not found: {repo}",
                ))
            continue

        try:
            base_ref = get_current_ref(repo)
        except Exception as exc:
            for agent in agents:
                result.results.append(TaskAgentResult(
                    task_name=task_name,
                    agent=agent,
                    score=0.0,
                    wall_time=0.0,
                    tests_pass=False,
                    exit_clean=False,
                    lint_clean=False,
                    timed_out=False,
                    error=str(exc),
                ))
            continue

        if parallel > 1 and len(agents) > 1:
            _run_task_parallel(
                task=task,
                task_name=task_name,
                agents=agents,
                base_ref=base_ref,
                timeout=timeout,
                result=result,
                progress_callback=progress_callback,
                max_workers=parallel,
            )
        else:
            _run_task_sequential(
                task=task,
                task_name=task_name,
                agents=agents,
                base_ref=base_ref,
                timeout=timeout,
                result=result,
                progress_callback=progress_callback,
            )

    result.finish()
    return result


def _run_single_agent(
    task,
    task_name: str,
    agent: str,
    base_ref: str,
    timeout: int,
    progress_callback,
) -> TaskAgentResult:
    """Run a single (task, agent) pair and return the result."""
    from coderace.adapters import ADAPTERS
    from coderace.git_ops import branch_name_for, checkout, create_branch, get_diff_stat
    from coderace.scorer import compute_score

    repo = task.repo

    if progress_callback:
        progress_callback(task_name, agent, "running")

    if agent not in ADAPTERS:
        if progress_callback:
            progress_callback(task_name, agent, "unknown agent")
        return TaskAgentResult(
            task_name=task_name,
            agent=agent,
            score=0.0,
            wall_time=0.0,
            tests_pass=False,
            exit_clean=False,
            lint_clean=False,
            timed_out=False,
            error=f"Unknown agent: {agent}",
        )

    branch = branch_name_for(task_name, agent) + f"-bench"
    try:
        create_branch(repo, branch, base_ref)
    except Exception as exc:
        if progress_callback:
            progress_callback(task_name, agent, f"branch error")
        return TaskAgentResult(
            task_name=task_name,
            agent=agent,
            score=0.0,
            wall_time=0.0,
            tests_pass=False,
            exit_clean=False,
            lint_clean=False,
            timed_out=False,
            error=str(exc),
        )

    try:
        adapter = ADAPTERS[agent]()
        agent_result = adapter.run(task.description, repo, timeout)
        _, lines = get_diff_stat(repo, base_ref)

        checkout(repo, branch)
        score = compute_score(
            result=agent_result,
            test_command=task.test_command,
            lint_command=task.lint_command,
            workdir=repo,
            diff_lines=lines,
            all_wall_times=[agent_result.wall_time],
            all_diff_lines=[lines],
            weights=task.get_weights(),
        )
        checkout(repo, base_ref)

        cost_usd = None
        if agent_result.cost_result is not None:
            cost_usd = agent_result.cost_result.estimated_cost_usd

        status = "timed out" if agent_result.timed_out else f"done ({agent_result.wall_time:.1f}s)"
        if progress_callback:
            progress_callback(task_name, agent, status)

        return TaskAgentResult(
            task_name=task_name,
            agent=agent,
            score=score.composite,
            wall_time=agent_result.wall_time,
            tests_pass=score.breakdown.tests_pass,
            exit_clean=score.breakdown.exit_clean,
            lint_clean=score.breakdown.lint_clean,
            timed_out=agent_result.timed_out,
            cost_usd=cost_usd,
        )
    except Exception as exc:
        try:
            checkout(repo, base_ref)
        except Exception:
            pass
        if progress_callback:
            progress_callback(task_name, agent, f"error")
        return TaskAgentResult(
            task_name=task_name,
            agent=agent,
            score=0.0,
            wall_time=0.0,
            tests_pass=False,
            exit_clean=False,
            lint_clean=False,
            timed_out=False,
            error=str(exc),
        )


def _run_task_sequential(
    task,
    task_name: str,
    agents: list[str],
    base_ref: str,
    timeout: int,
    result: BenchmarkResult,
    progress_callback,
) -> None:
    """Run all agents for one task sequentially."""
    for agent in agents:
        tar = _run_single_agent(task, task_name, agent, base_ref, timeout, progress_callback)
        result.results.append(tar)


def _run_task_parallel(
    task,
    task_name: str,
    agents: list[str],
    base_ref: str,
    timeout: int,
    result: BenchmarkResult,
    progress_callback,
    max_workers: int,
) -> None:
    """Run agents for one task in parallel using worktrees."""
    import tempfile
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from pathlib import Path

    from coderace.adapters import ADAPTERS
    from coderace.git_ops import (
        add_worktree,
        branch_name_for,
        checkout,
        create_branch,
        get_diff_stat,
        prune_worktrees,
        remove_worktree,
    )
    from coderace.scorer import compute_score

    repo = task.repo

    def run_in_worktree(agent: str) -> TaskAgentResult:
        if agent not in ADAPTERS:
            return TaskAgentResult(
                task_name=task_name, agent=agent, score=0.0, wall_time=0.0,
                tests_pass=False, exit_clean=False, lint_clean=False,
                timed_out=False, error=f"Unknown agent: {agent}",
            )

        worktree_dir = Path(tempfile.mkdtemp(prefix=f"coderace-bench-{agent}-"))
        branch = branch_name_for(task_name, agent) + "-bench"
        try:
            create_branch(repo, branch, base_ref)
            checkout(repo, base_ref)
            add_worktree(repo, worktree_dir, branch)

            if progress_callback:
                progress_callback(task_name, agent, "running")

            adapter = ADAPTERS[agent]()
            agent_result = adapter.run(task.description, worktree_dir, timeout)
            _, lines = get_diff_stat(worktree_dir, base_ref)

            score = compute_score(
                result=agent_result,
                test_command=task.test_command,
                lint_command=task.lint_command,
                workdir=worktree_dir,
                diff_lines=lines,
                all_wall_times=[agent_result.wall_time],
                all_diff_lines=[lines],
                weights=task.get_weights(),
            )

            cost_usd = None
            if agent_result.cost_result is not None:
                cost_usd = agent_result.cost_result.estimated_cost_usd

            status = "timed out" if agent_result.timed_out else f"done ({agent_result.wall_time:.1f}s)"
            if progress_callback:
                progress_callback(task_name, agent, status)

            return TaskAgentResult(
                task_name=task_name, agent=agent,
                score=score.composite, wall_time=agent_result.wall_time,
                tests_pass=score.breakdown.tests_pass,
                exit_clean=score.breakdown.exit_clean,
                lint_clean=score.breakdown.lint_clean,
                timed_out=agent_result.timed_out,
                cost_usd=cost_usd,
            )
        except Exception as exc:
            if progress_callback:
                progress_callback(task_name, agent, "error")
            return TaskAgentResult(
                task_name=task_name, agent=agent, score=0.0, wall_time=0.0,
                tests_pass=False, exit_clean=False, lint_clean=False,
                timed_out=False, error=str(exc),
            )
        finally:
            remove_worktree(repo, worktree_dir)
            import shutil
            if worktree_dir.exists():
                shutil.rmtree(worktree_dir, ignore_errors=True)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(agents))) as executor:
        futures = {executor.submit(run_in_worktree, agent): agent for agent in agents}
        for future in as_completed(futures):
            result.results.append(future.result())

    prune_worktrees(repo)


def list_benchmark_tasks(difficulty: list[str] | None = None) -> list[str]:
    """Return available benchmark task names, optionally filtered by difficulty.

    Since built-in task YAMLs don't have a difficulty field, we use a static map.
    """
    from coderace.builtins import list_builtins

    _DIFFICULTY_MAP: dict[str, str] = {
        "fibonacci": "easy",
        "binary-search-tree": "medium",
        "json-parser": "medium",
        "csv-analyzer": "medium",
        "markdown-to-html": "easy",
        "http-server": "hard",
    }

    all_tasks = list_builtins()
    if not difficulty:
        return all_tasks

    difficulty_set = {d.lower() for d in difficulty}
    return [t for t in all_tasks if _DIFFICULTY_MAP.get(t, "medium") in difficulty_set]
