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


def compute_score(
    result: AgentResult,
    test_command: str,
    lint_command: str | None,
    workdir: Path,
    diff_lines: int,
    all_wall_times: list[float],
    all_diff_lines: list[int],
    weights: dict[str, float] | None = None,
) -> Score:
    """Compute a composite score for an agent result."""
    breakdown = ScoreBreakdown()

    # Tests
    test_exit, test_output = run_command(test_command, workdir)
    breakdown.tests_pass = test_exit == 0

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
