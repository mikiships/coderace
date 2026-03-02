"""Context evaluation: A/B testing context files against coding tasks."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Well-known context file names that should be removed during baseline runs
KNOWN_CONTEXT_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
    "CONVENTIONS.md",
    ".windsurfrules",
]


@dataclass
class TrialResult:
    """Result of a single trial (one agent, one task, one condition)."""

    agent: str
    task_name: str
    condition: str  # "baseline" or "treatment"
    trial_number: int
    passed: bool
    wall_time: float
    score: float
    error: Optional[str] = None


@dataclass
class ContextEvalResult:
    """Collected results from a full context-eval run."""

    context_file: str
    agents: list[str]
    tasks: list[str]
    trials_per_condition: int
    results: list[TrialResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def finish(self) -> None:
        self.finished_at = time.time()

    @property
    def elapsed(self) -> float:
        end = self.finished_at or time.time()
        return end - self.started_at

    def get_results(
        self,
        agent: str | None = None,
        task_name: str | None = None,
        condition: str | None = None,
    ) -> list[TrialResult]:
        out = self.results
        if agent is not None:
            out = [r for r in out if r.agent == agent]
        if task_name is not None:
            out = [r for r in out if r.task_name == task_name]
        if condition is not None:
            out = [r for r in out if r.condition == condition]
        return out


def _backup_context_files(workdir: Path) -> dict[Path, Path]:
    """Back up any existing context files in the workdir. Returns {original: backup}."""
    backups: dict[Path, Path] = {}
    for name in KNOWN_CONTEXT_FILES:
        original = workdir / name
        if original.exists():
            backup = original.with_suffix(original.suffix + ".coderace-backup")
            shutil.copy2(str(original), str(backup))
            backups[original] = backup
    return backups


def _restore_context_files(backups: dict[Path, Path]) -> None:
    """Restore backed-up context files."""
    for original, backup in backups.items():
        if backup.exists():
            shutil.copy2(str(backup), str(original))
            backup.unlink()


def _remove_context_files(workdir: Path) -> list[Path]:
    """Remove known context files from workdir for baseline condition. Returns removed paths."""
    removed: list[Path] = []
    for name in KNOWN_CONTEXT_FILES:
        path = workdir / name
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed


def _place_context_file(context_file: Path, workdir: Path) -> Path:
    """Copy the context file into the workdir. Returns the destination path."""
    dest = workdir / context_file.name
    shutil.copy2(str(context_file), str(dest))
    return dest


def _remove_placed_context_file(placed_path: Path) -> None:
    """Remove a context file that was placed for treatment condition."""
    if placed_path.exists():
        placed_path.unlink()


def run_context_eval(
    context_file: Path,
    agents: list[str],
    task_paths: list[Path],
    trials: int = 3,
    timeout: int = 300,
    progress_callback=None,
) -> ContextEvalResult:
    """Run A/B context evaluation.

    For each agent x task:
      1. Run N trials WITHOUT the context file (baseline)
      2. Run N trials WITH the context file (treatment)

    Args:
        context_file: Path to the context file to evaluate.
        agents: Agent names to test.
        task_paths: Paths to task YAML files.
        trials: Number of trials per condition (min 2).
        timeout: Per-task timeout in seconds.
        progress_callback: Optional callable(agent, task, condition, trial, status).

    Returns:
        ContextEvalResult with all trial results.
    """
    import subprocess as _sp
    import tempfile

    from coderace.adapters import ADAPTERS
    from coderace.builtins import get_builtin_path
    from coderace.scorer import compute_score
    from coderace.task import load_task

    task_names = []
    for tp in task_paths:
        task = load_task(tp)
        task_names.append(task.name)

    eval_result = ContextEvalResult(
        context_file=str(context_file),
        agents=list(agents),
        tasks=task_names,
        trials_per_condition=trials,
    )

    for task_path in task_paths:
        task = load_task(task_path)
        task_name = task.name

        # Scaffold a temp git repo for each task
        tmp = Path(tempfile.mkdtemp(prefix=f"coderace-ctx-{task_name}-"))
        _sp.run(["git", "init", str(tmp)], capture_output=True, check=True)
        _sp.run(
            ["git", "commit", "--allow-empty", "-m", "initial"],
            cwd=tmp, capture_output=True, check=True,
        )

        for agent in agents:
            if agent not in ADAPTERS:
                for condition in ("baseline", "treatment"):
                    for trial_num in range(1, trials + 1):
                        eval_result.results.append(TrialResult(
                            agent=agent,
                            task_name=task_name,
                            condition=condition,
                            trial_number=trial_num,
                            passed=False,
                            wall_time=0.0,
                            score=0.0,
                            error=f"Unknown agent: {agent}",
                        ))
                continue

            for condition in ("baseline", "treatment"):
                for trial_num in range(1, trials + 1):
                    if progress_callback:
                        progress_callback(agent, task_name, condition, trial_num, "running")

                    # Prepare the working directory
                    backups = _backup_context_files(tmp)

                    try:
                        if condition == "baseline":
                            _remove_context_files(tmp)
                        else:
                            # Place the context file
                            placed = _place_context_file(context_file, tmp)

                        # Create a fresh branch for this trial
                        branch = f"ctx-{task_name}-{agent}-{condition}-t{trial_num}"
                        _sp.run(["git", "branch", "-D", branch], cwd=tmp, capture_output=True)

                        from coderace.git_ops import (
                            checkout,
                            create_branch,
                            get_current_ref,
                            get_diff_stat,
                        )

                        base_ref = get_current_ref(tmp)
                        create_branch(tmp, branch, base_ref)

                        adapter = ADAPTERS[agent]()
                        agent_result = adapter.run(task.description, tmp, timeout)
                        _, lines = get_diff_stat(tmp, base_ref)

                        checkout(tmp, branch)
                        score = compute_score(
                            result=agent_result,
                            test_command=task.test_command,
                            lint_command=task.lint_command,
                            workdir=tmp,
                            diff_lines=lines,
                            all_wall_times=[agent_result.wall_time],
                            all_diff_lines=[lines],
                            weights=task.get_weights(),
                            verify_command=task.verify_command,
                            verify_files=task.verify_files,
                        )
                        checkout(tmp, base_ref)

                        passed = score.breakdown.tests_pass
                        trial_result = TrialResult(
                            agent=agent,
                            task_name=task_name,
                            condition=condition,
                            trial_number=trial_num,
                            passed=passed,
                            wall_time=agent_result.wall_time,
                            score=score.composite,
                        )

                        if progress_callback:
                            status = f"done ({agent_result.wall_time:.1f}s)"
                            progress_callback(agent, task_name, condition, trial_num, status)

                    except Exception as exc:
                        trial_result = TrialResult(
                            agent=agent,
                            task_name=task_name,
                            condition=condition,
                            trial_number=trial_num,
                            passed=False,
                            wall_time=0.0,
                            score=0.0,
                            error=str(exc),
                        )
                        if progress_callback:
                            progress_callback(agent, task_name, condition, trial_num, "error")
                        try:
                            checkout(tmp, base_ref)
                        except Exception:
                            pass
                    finally:
                        # Clean up: remove placed context file and restore backups
                        if condition == "treatment":
                            _remove_placed_context_file(tmp / context_file.name)
                        _restore_context_files(backups)

                    eval_result.results.append(trial_result)

        # Clean up temp dir
        shutil.rmtree(tmp, ignore_errors=True)

    eval_result.finish()
    return eval_result
