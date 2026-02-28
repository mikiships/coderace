"""Tests for scoring engine."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from coderace.scorer import compute_score, _normalize_lower_better
from coderace.types import (
    DEFAULT_WEIGHTS,
    VERIFY_AWARE_DEFAULT_WEIGHTS,
    AgentResult,
    normalize_weights,
)


def test_weights_sum_to_one() -> None:
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


# --- Custom scoring weights tests ---


def test_normalize_weights_aliases() -> None:
    result = normalize_weights({"tests": 50, "exit": 20, "lint": 10, "time": 10, "lines": 10})
    assert abs(result["tests_pass"] - 0.5) < 1e-9
    assert abs(sum(result.values()) - 1.0) < 1e-9


def test_normalize_weights_verify_alias() -> None:
    result = normalize_weights({"tests": 25, "verify": 30, "exit": 20, "lint": 15, "time": 5, "lines": 5})
    assert abs(result["verify_passed"] - 0.30) < 1e-9
    assert abs(sum(result.values()) - 1.0) < 1e-9


def test_normalize_weights_partial() -> None:
    """Missing keys default to 0."""
    result = normalize_weights({"tests": 100})
    assert result["tests_pass"] == 1.0
    assert result["exit_clean"] == 0.0


def test_normalize_weights_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown scoring key"):
        normalize_weights({"bogus": 50})


def test_normalize_weights_negative() -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        normalize_weights({"tests": -10})


def test_normalize_weights_all_zero() -> None:
    with pytest.raises(ValueError, match="must not all be zero"):
        normalize_weights({"tests": 0, "exit": 0, "lint": 0, "time": 0, "lines": 0})


def test_normalize_single_value() -> None:
    score = _normalize_lower_better(5.0, [5.0])
    assert score == 100.0


def test_normalize_best_value() -> None:
    score = _normalize_lower_better(1.0, [1.0, 5.0, 10.0])
    assert score == 100.0


def test_normalize_worst_value() -> None:
    score = _normalize_lower_better(10.0, [1.0, 5.0, 10.0])
    assert score == 0.0


def test_normalize_middle_value() -> None:
    score = _normalize_lower_better(5.0, [1.0, 5.0, 10.0])
    # (1 - (5-1)/(10-1)) * 100 = (1 - 4/9) * 100 = 55.55...
    assert 55.0 < score < 56.0


def test_normalize_equal_values() -> None:
    score = _normalize_lower_better(5.0, [5.0, 5.0, 5.0])
    assert score == 100.0


def test_normalize_empty_list() -> None:
    score = _normalize_lower_better(5.0, [])
    assert score == 50.0


def test_normalize_zero_value() -> None:
    score = _normalize_lower_better(0.0, [0.0, 5.0])
    assert score == 50.0  # zero treated as invalid


def _agent_result() -> AgentResult:
    return AgentResult(
        agent="claude",
        exit_code=0,
        stdout="",
        stderr="",
        wall_time=1.0,
    )


def _write_verify_checker(tmp_path: Path) -> Path:
    path = tmp_path / "verify_check.py"
    path.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "expected = sys.argv[1]\n"
        "actual = Path('target.txt').read_text().strip()\n"
        "print(actual)\n"
        "raise SystemExit(0 if actual == expected else 1)\n"
    )
    return path


def test_compute_score_runs_verification_after_tests(tmp_path: Path) -> None:
    test_setup = tmp_path / "test_setup.py"
    test_setup.write_text(
        "from pathlib import Path\n"
        "Path('target.txt').write_text('from-tests\\n')\n"
    )
    verify_script = _write_verify_checker(tmp_path)

    score = compute_score(
        result=_agent_result(),
        test_command=f"{sys.executable} {test_setup.name}",
        lint_command=None,
        workdir=tmp_path,
        diff_lines=1,
        all_wall_times=[1.0],
        all_diff_lines=[1],
        verify_command=f"{sys.executable} {verify_script.name} from-verify",
        verify_files={"target.txt": "from-verify\n"},
    )

    assert score.breakdown.tests_pass is True
    assert score.verify_passed is True
    assert score.verify_score == 100.0
    assert "from-verify" in score.verify_output
    assert (tmp_path / "target.txt").read_text() == "from-verify\n"


def test_compute_score_captures_verify_failure_output(tmp_path: Path) -> None:
    verify_script = _write_verify_checker(tmp_path)

    score = compute_score(
        result=_agent_result(),
        test_command="echo ok",
        lint_command=None,
        workdir=tmp_path,
        diff_lines=1,
        all_wall_times=[1.0],
        all_diff_lines=[1],
        verify_command=f"{sys.executable} {verify_script.name} from-verify",
        verify_files={"target.txt": "wrong\n"},
    )

    assert score.verify_passed is False
    assert score.verify_score == 0.0
    assert "wrong" in score.verify_output


def test_compute_score_skips_verify_without_verify_files(tmp_path: Path) -> None:
    score = compute_score(
        result=_agent_result(),
        test_command="echo ok",
        lint_command=None,
        workdir=tmp_path,
        diff_lines=1,
        all_wall_times=[1.0],
        all_diff_lines=[1],
        verify_command=f"{sys.executable} -c \"import sys; raise SystemExit(1)\"",
        verify_files=None,
    )

    assert score.verify_passed is False
    assert score.verify_score == 0.0
    assert score.verify_output == ""


def test_compute_score_rejects_verify_files_outside_workspace(tmp_path: Path) -> None:
    score = compute_score(
        result=_agent_result(),
        test_command="echo ok",
        lint_command=None,
        workdir=tmp_path,
        diff_lines=1,
        all_wall_times=[1.0],
        all_diff_lines=[1],
        verify_command="echo should-not-run",
        verify_files={"../outside.txt": "x"},
    )

    assert score.verify_passed is False
    assert score.verify_score == 0.0
    assert "escapes workspace" in score.verify_output


def test_compute_score_verify_aware_defaults_apply_when_verify_is_configured(
    tmp_path: Path,
) -> None:
    verify_script = _write_verify_checker(tmp_path)
    score = compute_score(
        result=_agent_result(),
        test_command="echo ok",
        lint_command=None,
        workdir=tmp_path,
        diff_lines=1,
        all_wall_times=[1.0],
        all_diff_lines=[1],
        weights=None,
        verify_command=f"{sys.executable} {verify_script.name} expected",
        verify_files={"target.txt": "wrong\n"},
    )

    # verify fails, all other metrics pass -> 0.70 * 100
    assert score.composite == 70.0
    assert score.breakdown.verify_passed is False


def test_compute_score_legacy_defaults_remain_without_verify(tmp_path: Path) -> None:
    score = compute_score(
        result=_agent_result(),
        test_command="false",
        lint_command=None,
        workdir=tmp_path,
        diff_lines=1,
        all_wall_times=[1.0],
        all_diff_lines=[1],
        weights=None,
        verify_command=None,
        verify_files=None,
    )

    # tests fail, but exit/lint/time/lines pass with legacy defaults:
    # 0.20 + 0.15 + 0.15 + 0.10 = 0.60
    assert score.composite == 60.0
    assert score.breakdown.verify_passed is False


def test_verify_aware_default_weights_sum_to_one() -> None:
    total = sum(VERIFY_AWARE_DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9
