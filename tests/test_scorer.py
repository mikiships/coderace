"""Tests for scoring engine."""

from __future__ import annotations

from coderace.scorer import WEIGHTS, _normalize_lower_better


def test_weights_sum_to_one() -> None:
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


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
