"""Scoring engine for agent results."""

from __future__ import annotations

import subprocess
from pathlib import Path

from coderace.types import DEFAULT_WEIGHTS, AgentResult, Score, ScoreBreakdown


def run_command(cmd: str, cwd: Path, timeout: int = 120) -> tuple[int, str]:
    """Run a shell command, return (exit_code, output)."""
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return proc.returncode, output
    except subprocess.TimeoutExpired:
        return -1, "Command timed out"
    except Exception as e:
        return -1, str(e)


def _resolve_workspace_path(workdir: Path, rel_path: str) -> Path:
    """Resolve a verify file path and ensure it stays within the workspace."""
    file_path = Path(rel_path)
    if file_path.is_absolute():
        raise ValueError(f"verify_files path must be relative: {rel_path!r}")

    resolved = (workdir / file_path).resolve()
    workspace_root = workdir.resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(f"verify_files path escapes workspace: {rel_path!r}") from exc
    return resolved


def _write_verify_files(workdir: Path, verify_files: dict[str, str]) -> None:
    """Write verification files into the workspace, overwriting existing files."""
    for rel_path, content in verify_files.items():
        target = _resolve_workspace_path(workdir, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def compute_score(
    result: AgentResult,
    test_command: str,
    lint_command: str | None,
    workdir: Path,
    diff_lines: int,
    all_wall_times: list[float],
    all_diff_lines: list[int],
    weights: dict[str, float] | None = None,
    verify_command: str | None = None,
    verify_files: dict[str, str] | None = None,
) -> Score:
    """Compute a composite score for an agent result."""
    breakdown = ScoreBreakdown()

    # Tests
    test_exit, test_output = run_command(test_command, workdir)
    breakdown.tests_pass = test_exit == 0

    verify_passed = False
    verify_score = 0.0
    verify_output = ""
    if verify_command and verify_files is not None:
        try:
            _write_verify_files(workdir, verify_files)
            verify_exit, verify_output = run_command(verify_command, workdir)
            verify_passed = verify_exit == 0
            verify_score = 100.0 if verify_passed else 0.0
        except Exception as exc:
            verify_output = f"Failed to run verification tests: {exc}"
            verify_passed = False
            verify_score = 0.0

    # Exit clean
    breakdown.exit_clean = result.exit_code == 0 and not result.timed_out

    # Lint
    lint_output = ""
    if lint_command:
        lint_exit, lint_output = run_command(lint_command, workdir)
        breakdown.lint_clean = lint_exit == 0
    else:
        breakdown.lint_clean = True  # No lint command = pass

    # Raw metrics
    breakdown.wall_time = result.wall_time
    breakdown.lines_changed = diff_lines

    # Use custom weights or defaults
    w = weights if weights is not None else DEFAULT_WEIGHTS

    # Compute composite
    composite = 0.0

    # Boolean metrics
    composite += w["tests_pass"] * (100.0 if breakdown.tests_pass else 0.0)
    composite += w["exit_clean"] * (100.0 if breakdown.exit_clean else 0.0)
    composite += w["lint_clean"] * (100.0 if breakdown.lint_clean else 0.0)

    # Wall time: normalize (lower is better)
    composite += w["wall_time"] * _normalize_lower_better(
        result.wall_time, all_wall_times
    )

    # Lines changed: normalize (fewer is better)
    composite += w["lines_changed"] * _normalize_lower_better(
        float(diff_lines), [float(x) for x in all_diff_lines]
    )

    return Score(
        agent=result.agent,
        composite=round(composite, 1),
        breakdown=breakdown,
        tests_output=test_output,
        verify_passed=verify_passed,
        verify_score=verify_score,
        verify_output=verify_output,
        lint_output=lint_output,
        cost_result=result.cost_result,
    )


def _normalize_lower_better(value: float, all_values: list[float]) -> float:
    """Normalize a metric where lower is better. Returns 0-100 score."""
    if not all_values:
        return 50.0

    valid = [v for v in all_values if v > 0]
    if not valid:
        return 50.0

    if len(valid) == 1:
        return 100.0 if value == valid[0] else 50.0

    min_val = min(valid)
    max_val = max(valid)

    if max_val == min_val:
        return 100.0

    if value <= 0:
        return 50.0

    # Invert: best (min) gets 100, worst (max) gets 0
    normalized = 100.0 * (1.0 - (value - min_val) / (max_val - min_val))
    return max(0.0, min(100.0, normalized))
