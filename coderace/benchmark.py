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
    trial_number: int = 1
    verify_applicable: bool = False
    verify_passed: bool = False
    verify_score: float = 0.0
    verify_output: str = ""
    cost_usd: Optional[float] = None
    error: Optional[str] = None  # error message if run failed entirely


@dataclass
class BenchmarkResult:
    """Collected results from a full benchmark run."""

    benchmark_id: str  # timestamp-based unique ID
    agents: list[str]
    tasks: list[str]
    trials: int = 1
    results: list[TaskAgentResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def get(
        self,
        task_name: str,
        agent: str,
        trial_number: int | None = None,
    ) -> Optional[TaskAgentResult]:
        """Look up a specific (task, agent) result."""
        for r in self.results:
            if (
                r.task_name == task_name
                and r.agent == agent
                and (trial_number is None or r.trial_number == trial_number)
            ):
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
    trials: int = 1,
    progress_callback=None,
) -> BenchmarkResult:
    """Run a benchmark: all tasks x all agents.

    Args:
        agents: Agent names to race.
        tasks: Built-in task names to run.
        timeout: Per-task timeout in seconds.
        parallel: Number of agents to run in parallel (default 1 = sequential).
        trials: Number of repeat trials per (task, agent) pair.
        progress_callback: Optional callable(task, agent, status) for progress.

    Returns:
        BenchmarkResult with all collected results.
    """
    import tempfile
    from pathlib import Path

    from coderace.adapters import ADAPTERS, make_display_name, parse_agent_spec
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
    if trials < 1:
        raise ValueError("trials must be >= 1")
    # Normalize agent specs to display names so result.agents matches
    # TaskAgentResult.agent (which uses adapter display names).
    display_agents = [
        make_display_name(*parse_agent_spec(a)) for a in agents
    ]
    result = BenchmarkResult(
        benchmark_id=benchmark_id,
        agents=display_agents,
        tasks=list(tasks),
        trials=trials,
    )

    # Track temp dirs for built-in tasks so we can clean up
    _temp_dirs: list[Path] = []

    for task_name in tasks:
        try:
            task_path = get_builtin_path(task_name)
            task = load_task(task_path)
        except Exception as exc:
            if progress_callback:
                progress_callback(task_name, "*", f"ERROR: {exc}")
            for trial_number in range(1, trials + 1):
                for agent in agents:
                    result.results.append(TaskAgentResult(
                        task_name=task_name,
                        agent=agent,
                        trial_number=trial_number,
                        score=0.0,
                        wall_time=0.0,
                        tests_pass=False,
                        exit_clean=False,
                        lint_clean=False,
                        timed_out=False,
                        error=str(exc),
                    ))
            continue

        # Built-in tasks have repo=CWD which is wrong -- scaffold a temp git repo
        repo = task.repo
        if task.repo == Path.cwd().resolve():
            import shutil
            import subprocess as _sp
            tmp = Path(tempfile.mkdtemp(prefix=f"coderace-bench-{task_name}-"))
            _temp_dirs.append(tmp)
            _sp.run(["git", "init", str(tmp)], capture_output=True, check=True)
            # Create an initial commit so branches can be created
            _sp.run(
                ["git", "commit", "--allow-empty", "-m", "initial"],
                cwd=tmp, capture_output=True, check=True,
            )
            task.repo = tmp
            repo = tmp

        if not repo.exists():
            for trial_number in range(1, trials + 1):
                for agent in agents:
                    result.results.append(TaskAgentResult(
                        task_name=task_name,
                        agent=agent,
                        trial_number=trial_number,
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
            for trial_number in range(1, trials + 1):
                for agent in agents:
                    result.results.append(TaskAgentResult(
                        task_name=task_name,
                        agent=agent,
                        trial_number=trial_number,
                        score=0.0,
                        wall_time=0.0,
                        tests_pass=False,
                        exit_clean=False,
                        lint_clean=False,
                        timed_out=False,
                        error=str(exc),
                    ))
            continue

        for trial_number in range(1, trials + 1):
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
                    trial_number=trial_number,
                    total_trials=trials,
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
                    trial_number=trial_number,
                    total_trials=trials,
                )

    result.finish()

    # Clean up temp directories for built-in tasks
    import shutil as _shutil
    for tmp_dir in _temp_dirs:
        _shutil.rmtree(tmp_dir, ignore_errors=True)

    return result


def _format_trial_status(status: str, trial_number: int, total_trials: int) -> str:
    """Prefix a progress status with trial metadata when running repeated trials."""
    if total_trials <= 1:
        return status
    return f"Trial {trial_number}/{total_trials} | {status}"


def _run_single_agent(
    task,
    task_name: str,
    agent: str,
    base_ref: str,
    timeout: int,
    progress_callback,
    trial_number: int,
    total_trials: int,
) -> TaskAgentResult:
    """Run a single (task, agent) pair and return the result."""
    from coderace.adapters import ADAPTERS, instantiate_adapter, parse_agent_spec
    from coderace.git_ops import branch_name_for, checkout, create_branch, get_diff_stat
    from coderace.scorer import compute_score

    repo = task.repo
    agent_base, _agent_model = parse_agent_spec(agent)

    if progress_callback:
        progress_callback(
            task_name,
            agent,
            _format_trial_status("running", trial_number, total_trials),
        )

    if agent_base not in ADAPTERS:
        if progress_callback:
            progress_callback(
                task_name,
                agent,
                _format_trial_status("unknown agent", trial_number, total_trials),
            )
        return TaskAgentResult(
            task_name=task_name,
            agent=agent,
            trial_number=trial_number,
            score=0.0,
            wall_time=0.0,
            tests_pass=False,
            exit_clean=False,
            lint_clean=False,
            timed_out=False,
            error=f"Unknown agent: {agent}",
        )

    branch_key = agent.replace(":", "-").replace(" ", "_")
    branch = branch_name_for(task_name, branch_key) + f"-bench"
    try:
        # Delete stale branch from previous runs if it exists
        import subprocess as _sp
        _sp.run(["git", "branch", "-D", branch], cwd=repo, capture_output=True)
        create_branch(repo, branch, base_ref)
    except Exception as exc:
        if progress_callback:
            progress_callback(
                task_name,
                agent,
                _format_trial_status("branch error", trial_number, total_trials),
            )
        return TaskAgentResult(
            task_name=task_name,
            agent=agent,
            trial_number=trial_number,
            score=0.0,
            wall_time=0.0,
            tests_pass=False,
            exit_clean=False,
            lint_clean=False,
            timed_out=False,
            error=str(exc),
        )

    try:
        adapter = instantiate_adapter(agent)
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
            verify_command=task.verify_command,
            verify_files=task.verify_files,
        )
        checkout(repo, base_ref)

        cost_usd = None
        if agent_result.cost_result is not None:
            cost_usd = agent_result.cost_result.estimated_cost_usd

        status = "timed out" if agent_result.timed_out else f"done ({agent_result.wall_time:.1f}s)"
        if progress_callback:
            progress_callback(
                task_name,
                agent,
                _format_trial_status(status, trial_number, total_trials),
            )

        return TaskAgentResult(
            task_name=task_name,
            agent=agent_result.agent,  # use display name (e.g. "codex (gpt-5.4)")
            trial_number=trial_number,
            score=score.composite,
            wall_time=agent_result.wall_time,
            tests_pass=score.breakdown.tests_pass,
            exit_clean=score.breakdown.exit_clean,
            lint_clean=score.breakdown.lint_clean,
            timed_out=agent_result.timed_out,
            verify_applicable=bool(task.verify_command),
            verify_passed=score.verify_passed,
            verify_score=score.verify_score,
            verify_output=score.verify_output,
            cost_usd=cost_usd,
        )
    except Exception as exc:
        try:
            checkout(repo, base_ref)
        except Exception:
            pass
        if progress_callback:
            progress_callback(
                task_name,
                agent,
                _format_trial_status("error", trial_number, total_trials),
            )
        return TaskAgentResult(
            task_name=task_name,
            agent=agent,
            trial_number=trial_number,
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
    trial_number: int,
    total_trials: int,
) -> None:
    """Run all agents for one task sequentially."""
    for agent in agents:
        tar = _run_single_agent(
            task,
            task_name,
            agent,
            base_ref,
            timeout,
            progress_callback,
            trial_number,
            total_trials,
        )
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
    trial_number: int,
    total_trials: int,
) -> None:
    """Run agents for one task in parallel using worktrees."""
    import tempfile
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from pathlib import Path

    from coderace.adapters import ADAPTERS, instantiate_adapter, parse_agent_spec
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
        agent_base, _agent_model = parse_agent_spec(agent)
        if agent_base not in ADAPTERS:
            return TaskAgentResult(
                task_name=task_name, agent=agent, trial_number=trial_number,
                score=0.0, wall_time=0.0,
                tests_pass=False, exit_clean=False, lint_clean=False,
                timed_out=False, error=f"Unknown agent: {agent}",
            )

        branch_key = agent.replace(":", "-").replace(" ", "_")
        worktree_dir = Path(tempfile.mkdtemp(prefix=f"coderace-bench-{branch_key}-"))
        branch = branch_name_for(task_name, branch_key) + "-bench"
        try:
            # Delete stale branch from previous runs if it exists
            import subprocess as _sp2
            _sp2.run(["git", "branch", "-D", branch], cwd=repo, capture_output=True)
            create_branch(repo, branch, base_ref)
            checkout(repo, base_ref)
            add_worktree(repo, worktree_dir, branch)

            if progress_callback:
                progress_callback(
                    task_name,
                    agent,
                    _format_trial_status("running", trial_number, total_trials),
                )

            adapter = instantiate_adapter(agent)
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
                verify_command=task.verify_command,
                verify_files=task.verify_files,
            )

            cost_usd = None
            if agent_result.cost_result is not None:
                cost_usd = agent_result.cost_result.estimated_cost_usd

            status = "timed out" if agent_result.timed_out else f"done ({agent_result.wall_time:.1f}s)"
            if progress_callback:
                progress_callback(
                    task_name,
                    agent,
                    _format_trial_status(status, trial_number, total_trials),
                )

            return TaskAgentResult(
                task_name=task_name,
                agent=agent_result.agent,  # display name (e.g. "codex (gpt-5.4)")
                trial_number=trial_number,
                score=score.composite, wall_time=agent_result.wall_time,
                tests_pass=score.breakdown.tests_pass,
                exit_clean=score.breakdown.exit_clean,
                lint_clean=score.breakdown.lint_clean,
                timed_out=agent_result.timed_out,
                verify_applicable=bool(task.verify_command),
                verify_passed=score.verify_passed,
                verify_score=score.verify_score,
                verify_output=score.verify_output,
                cost_usd=cost_usd,
            )
        except Exception as exc:
            if progress_callback:
                progress_callback(
                    task_name,
                    agent,
                    _format_trial_status("error", trial_number, total_trials),
                )
            return TaskAgentResult(
                task_name=task_name, agent=agent, trial_number=trial_number,
                score=0.0, wall_time=0.0,
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

    Uses `difficulty` from built-in task YAML when present, with legacy fallbacks.
    """
    from coderace.builtins import list_builtins, load_builtin

    legacy_difficulty_map: dict[str, str] = {
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
    filtered: list[str] = []
    for task_name in all_tasks:
        try:
            data = load_builtin(task_name)
            task_difficulty = str(
                data.get(
                    "difficulty",
                    legacy_difficulty_map.get(task_name, "medium"),
                )
            ).lower()
        except Exception:
            task_difficulty = legacy_difficulty_map.get(task_name, "medium")
        if task_difficulty in difficulty_set:
            filtered.append(task_name)
    return filtered
