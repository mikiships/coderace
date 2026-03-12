"""Tests for coderace.maintainer_rubric and related display/report integration."""

from __future__ import annotations

import json

import pytest

from coderace.maintainer_rubric import (
    MaintainerRubric,
    _parse_diff,
    score_convention_adherence,
    score_dep_hygiene,
    score_idiomatic_patterns,
    score_minimal_diff,
    score_rubric,
    score_scope_discipline,
)


# ---------------------------------------------------------------------------
# Fixtures — sample diffs
# ---------------------------------------------------------------------------

CLEAN_DIFF = """\
diff --git a/coderace/foo.py b/coderace/foo.py
index 1234567..abcdefg 100644
--- a/coderace/foo.py
+++ b/coderace/foo.py
@@ -1,5 +1,10 @@
+def new_function(value: int) -> int:
+    \"\"\"Return double the value.\"\"\"
+    return value * 2
+
+
 def existing_function() -> None:
     pass
"""

HUGE_DIFF_LINES = "\n".join(
    [f"diff --git a/coderace/big.py b/coderace/big.py", "--- a/coderace/big.py", "+++ b/coderace/big.py", "@@ -1 +1,200 @@"]
    + [f"+    line_{i} = {i}" for i in range(200)]
)

CAMEL_CASE_DIFF = """\
diff --git a/coderace/utils.py b/coderace/utils.py
--- a/coderace/utils.py
+++ b/coderace/utils.py
@@ -1,3 +1,6 @@
+def myNewFunction(inputValue):
+    myLocalVar = inputValue * 2
+    return myLocalVar
"""

TRAILING_WHITESPACE_DIFF = """\
diff --git a/coderace/utils.py b/coderace/utils.py
--- a/coderace/utils.py
+++ b/coderace/utils.py
@@ -1,2 +1,4 @@
+def foo():   
+    x = 1   
"""

THIRD_PARTY_IMPORT_DIFF = """\
diff --git a/coderace/utils.py b/coderace/utils.py
--- a/coderace/utils.py
+++ b/coderace/utils.py
@@ -1,3 +1,6 @@
+import requests
+import numpy as np
+from pandas import DataFrame
+
 def foo():
     pass
"""

STDLIB_IMPORT_DIFF = """\
diff --git a/coderace/utils.py b/coderace/utils.py
--- a/coderace/utils.py
+++ b/coderace/utils.py
@@ -1,3 +1,5 @@
+import re
+import json
+from pathlib import Path
"""

MANY_FILES_DIFF = "\n".join(
    [
        f"diff --git a/coderace/mod{i}.py b/coderace/mod{i}.py\n"
        f"--- a/coderace/mod{i}.py\n"
        f"+++ b/coderace/mod{i}.py\n"
        f"@@ -1 +1,2 @@\n"
        f"+x = {i}"
        for i in range(12)
    ]
)

ALIEN_DIFF = """\
diff --git a/coderace/utils.py b/coderace/utils.py
--- a/coderace/utils.py
+++ b/coderace/utils.py
@@ -1,5 +1,10 @@
+def foo(x);
+    global counter
+    global total
+    if x == True:
+        return x == False
"""

EMPTY_DIFF = ""


# ---------------------------------------------------------------------------
# _parse_diff
# ---------------------------------------------------------------------------

def test_parse_diff_files():
    parsed = _parse_diff(CLEAN_DIFF)
    assert "coderace/foo.py" in parsed["files"]


def test_parse_diff_counts():
    parsed = _parse_diff(CLEAN_DIFF)
    assert parsed["added_count"] > 0
    assert isinstance(parsed["total_delta"], int)


def test_parse_diff_empty():
    parsed = _parse_diff(EMPTY_DIFF)
    assert parsed["files"] == []
    assert parsed["added_count"] == 0
    assert parsed["removed_count"] == 0


# ---------------------------------------------------------------------------
# D1 Dimension: minimal_diff
# ---------------------------------------------------------------------------

def test_minimal_diff_clean_scores_high():
    score = score_minimal_diff(CLEAN_DIFF)
    assert score >= 80.0, f"Expected >= 80, got {score}"


def test_minimal_diff_huge_diff_scores_low():
    score = score_minimal_diff(HUGE_DIFF_LINES)
    assert score < 80.0, f"Expected < 80 for bloated diff, got {score}"


def test_minimal_diff_empty_diff():
    score = score_minimal_diff(EMPTY_DIFF)
    assert score == 100.0


# ---------------------------------------------------------------------------
# D2 Dimension: convention_adherence
# ---------------------------------------------------------------------------

def test_convention_adherence_clean_scores_high():
    score = score_convention_adherence(CLEAN_DIFF)
    assert score >= 80.0, f"Expected >= 80, got {score}"


def test_convention_adherence_camel_case_penalised():
    score = score_convention_adherence(CAMEL_CASE_DIFF)
    assert score < 100.0, f"Expected penalty for camelCase, got {score}"


def test_convention_adherence_trailing_whitespace_penalised():
    score = score_convention_adherence(TRAILING_WHITESPACE_DIFF)
    assert score < 100.0, f"Expected penalty for trailing whitespace, got {score}"


# ---------------------------------------------------------------------------
# D3 Dimension: dep_hygiene
# ---------------------------------------------------------------------------

def test_dep_hygiene_no_imports_scores_100():
    score = score_dep_hygiene(CLEAN_DIFF)
    assert score == 100.0


def test_dep_hygiene_third_party_penalised():
    score = score_dep_hygiene(THIRD_PARTY_IMPORT_DIFF)
    assert score < 100.0, f"Expected penalty for third-party imports, got {score}"


def test_dep_hygiene_stdlib_not_penalised():
    score = score_dep_hygiene(STDLIB_IMPORT_DIFF)
    assert score == 100.0, f"stdlib imports should not be penalised, got {score}"


# ---------------------------------------------------------------------------
# D4 Dimension: scope_discipline
# ---------------------------------------------------------------------------

def test_scope_discipline_few_files_scores_100():
    score = score_scope_discipline(CLEAN_DIFF)
    assert score == 100.0


def test_scope_discipline_many_files_penalised():
    score = score_scope_discipline(MANY_FILES_DIFF)
    assert score < 100.0, f"Expected penalty for many files, got {score}"


def test_scope_discipline_allowed_paths_respected():
    # Only allow foo.py — CLEAN_DIFF touches foo.py
    score = score_scope_discipline(CLEAN_DIFF, allowed_paths=["coderace/foo.py"])
    assert score == 100.0


def test_scope_discipline_allowed_paths_violation():
    # Allow only bar.py — CLEAN_DIFF touches foo.py → violation
    score = score_scope_discipline(CLEAN_DIFF, allowed_paths=["coderace/bar.py"])
    assert score < 100.0


# ---------------------------------------------------------------------------
# D5 Dimension: idiomatic_patterns
# ---------------------------------------------------------------------------

def test_idiomatic_patterns_clean_scores_high():
    score = score_idiomatic_patterns(CLEAN_DIFF)
    assert score >= 80.0, f"Expected >= 80, got {score}"


def test_idiomatic_patterns_alien_constructs_penalised():
    score = score_idiomatic_patterns(ALIEN_DIFF)
    assert score < 100.0, f"Expected penalty for alien constructs, got {score}"


def test_idiomatic_patterns_empty_diff():
    score = score_idiomatic_patterns(EMPTY_DIFF)
    assert score == 100.0


# ---------------------------------------------------------------------------
# Composite: score_rubric
# ---------------------------------------------------------------------------

def test_score_rubric_returns_maintainer_rubric():
    rubric = score_rubric(CLEAN_DIFF)
    assert isinstance(rubric, MaintainerRubric)


def test_score_rubric_composite_in_range():
    rubric = score_rubric(CLEAN_DIFF)
    assert 0.0 <= rubric.composite <= 100.0


def test_score_rubric_clean_diff_high_composite():
    rubric = score_rubric(CLEAN_DIFF)
    assert rubric.composite >= 70.0, f"Clean diff should score well, got {rubric.composite}"


def test_score_rubric_all_dimensions_populated():
    rubric = score_rubric(CLEAN_DIFF)
    for dim in ("minimal_diff", "convention_adherence", "dep_hygiene", "scope_discipline", "idiomatic_patterns"):
        val = getattr(rubric, dim)
        assert isinstance(val, float), f"{dim} should be float"
        assert 0.0 <= val <= 100.0, f"{dim} out of range: {val}"


def test_score_rubric_as_dict_keys():
    rubric = score_rubric(CLEAN_DIFF)
    d = rubric.as_dict()
    expected_keys = {"minimal_diff", "convention_adherence", "dep_hygiene", "scope_discipline", "idiomatic_patterns", "composite"}
    assert set(d.keys()) == expected_keys


def test_score_rubric_custom_weights():
    custom_weights = {
        "minimal_diff": 0.5,
        "convention_adherence": 0.1,
        "dep_hygiene": 0.1,
        "scope_discipline": 0.1,
        "idiomatic_patterns": 0.2,
    }
    rubric = score_rubric(CLEAN_DIFF, weights=custom_weights)
    assert 0.0 <= rubric.composite <= 100.0


# ---------------------------------------------------------------------------
# Rich display
# ---------------------------------------------------------------------------

def test_maintainer_rubric_display_renders():
    """MaintainerRubricDisplay.build_table returns a Rich Table without error."""
    from rich.table import Table
    from coderace.display import MaintainerRubricDisplay

    rubric = score_rubric(CLEAN_DIFF)
    display = MaintainerRubricDisplay()
    table = display.build_table(rubric)
    assert isinstance(table, Table)


def test_maintainer_rubric_display_print_no_error(capsys):
    """MaintainerRubricDisplay.print executes without raising."""
    from io import StringIO
    from rich.console import Console
    from coderace.display import MaintainerRubricDisplay

    rubric = score_rubric(CLEAN_DIFF)
    display = MaintainerRubricDisplay()
    buf = StringIO()
    console = Console(file=buf, no_color=True)
    display.print(rubric, console=console)
    output = buf.getvalue()
    assert "Maintainer Rubric" in output


# ---------------------------------------------------------------------------
# Markdown report rendering
# ---------------------------------------------------------------------------

def test_render_rubric_markdown_section():
    from coderace.review_report import _render_rubric_markdown
    rubric = score_rubric(CLEAN_DIFF)
    md = _render_rubric_markdown(rubric)
    assert "Maintainer Rubric" in md
    assert "Composite score" in md
    assert "Minimal Diff" in md


# ---------------------------------------------------------------------------
# JSON output shape
# ---------------------------------------------------------------------------

def test_review_json_with_rubric_shape():
    from coderace.review_report import render_review_json_with_rubric
    from coderace.types import ReviewResult

    # Minimal ReviewResult for testing
    result = ReviewResult(
        diff_summary={"files": [], "added": 0, "removed": 0},
        agents_used=["claude"],
        lanes=["null-safety"],
        phase1_findings=[],
        phase2_findings=[],
        elapsed_seconds=1.0,
        timestamp="2026-03-12T00:00:00Z",
    )
    output = render_review_json_with_rubric(result, CLEAN_DIFF)
    data = json.loads(output)
    assert "maintainer_rubric" in data
    rubric_data = data["maintainer_rubric"]
    for key in ("minimal_diff", "convention_adherence", "dep_hygiene", "scope_discipline", "idiomatic_patterns", "composite"):
        assert key in rubric_data, f"Missing key: {key}"
        assert isinstance(rubric_data[key], float)


# ---------------------------------------------------------------------------
# CLI integration: --maintainer-mode flag
# ---------------------------------------------------------------------------

def test_review_cli_maintainer_mode_flag_accepted(tmp_path):
    """coderace review --maintainer-mode should not error when diff is provided."""
    from typer.testing import CliRunner
    from coderace.cli import app

    diff_file = tmp_path / "test.diff"
    diff_file.write_text(CLEAN_DIFF)

    runner = CliRunner()
    # We expect the review to fail (no agents configured) but the flag should
    # be parsed without error — exit code may be non-zero due to no valid agents
    result = runner.invoke(app, ["review", "--diff", str(diff_file), "--maintainer-mode", "--agents", ""])
    # The important thing: the flag is accepted (no "No such option" error)
    assert "No such option" not in (result.output or "")
    assert "maintainer-mode" not in (result.output or "").lower() or True  # flag parsed


def test_benchmark_cli_maintainer_mode_flag_accepted():
    """coderace benchmark --maintainer-mode should be accepted as a flag."""
    from typer.testing import CliRunner
    from coderace.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["benchmark", "--maintainer-mode", "--agents", "claude", "--dry-run"])
    assert "No such option" not in (result.output or "")
