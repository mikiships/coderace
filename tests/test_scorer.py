"""Tests for scoring engine."""

from __future__ import annotations

import pytest

from coderace.scorer import _normalize_lower_better
from coderace.types import DEFAULT_WEIGHTS, normalize_weights


def test_weights_sum_to_one() -> None:
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


# --- Custom scoring weights tests ---


def test_normalize_weights_aliases() -> None:
    result = normalize_weights({"tests": 50, "exit": 20, "lint": 10, "time": 10, "lines": 10})
    assert abs(result["tests_pass"] - 0.5) < 1e-9
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
