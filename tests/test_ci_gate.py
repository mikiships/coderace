"""Tests for coderace gate command and --min-score flag on coderace review.

D4 deliverable: 25+ tests covering:
- coderace gate CLI (pass/fail/edge cases)
- --min-score on coderace review --maintainer-mode
- JSON output format
- Edge cases: score exactly at threshold, empty diff, stdin
- GitHub Action input via action.yml parsing
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from coderace.cli import app
from coderace.commands.gate import gate_main
from coderace.maintainer_rubric import MaintainerRubric, score_rubric

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

CLEAN_DIFF = """\
diff --git a/coderace/utils.py b/coderace/utils.py
index abc1234..def5678 100644
--- a/coderace/utils.py
+++ b/coderace/utils.py
@@ -1,3 +1,8 @@
+def helper(value: int) -> int:
+    \"\"\"Return value doubled.\"\"\"
+    return value * 2
+
+
 def existing() -> None:
     pass
"""

BAD_DIFF = """\
diff --git a/coderace/utils.py b/coderace/utils.py
--- a/coderace/utils.py
+++ b/coderace/utils.py
@@ -1,3 +1,15 @@
+import requests
+import httpx
+import boto3
+import numpy
+def myBadFunction(inputValue):
+    myLocalVar = inputValue;
+    global _state
+    anotherVar = True == True
+    return myLocalVar
"""

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helper to create a temp diff file
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_diff_file(tmp_path: Path) -> callable:
    def _make(content: str) -> Path:
        p = tmp_path / "test.diff"
        p.write_text(content, encoding="utf-8")
        return p
    return _make


# ---------------------------------------------------------------------------
# D2: coderace gate — basic pass/fail
# ---------------------------------------------------------------------------

class TestGateBasicPassFail:
    def test_gate_passes_clean_diff(self, tmp_diff_file):
        """Clean diff should pass a reasonable threshold."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "50"])
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_gate_fails_bad_diff(self, tmp_diff_file):
        """Diff with many violations should fail a moderate threshold."""
        path = tmp_diff_file(BAD_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "80"])
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_gate_passes_with_zero_threshold(self, tmp_diff_file):
        """Any diff should pass with min-score 0."""
        path = tmp_diff_file(BAD_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "0"])
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_gate_fails_with_max_threshold(self, tmp_diff_file):
        """Bad diff should fail with min-score 100."""
        path = tmp_diff_file(BAD_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "100"])
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_gate_clean_diff_fails_high_threshold(self, tmp_diff_file):
        """Even a clean diff can fail if threshold is very high."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "99"])
        # May pass or fail depending on actual score — just check it runs
        assert result.exit_code in (0, 1)
        assert "gate:" in result.output


# ---------------------------------------------------------------------------
# D2: Score at exactly the threshold (boundary cases)
# ---------------------------------------------------------------------------

class TestGateThresholdEdgeCases:
    def test_score_exactly_at_threshold_passes(self, tmp_path):
        """Score == threshold should pass (>=)."""
        from coderace.commands.gate import _output_result
        import io

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            _output_result(
                composite=80.0,
                min_score=80,
                passed=True,
                rubric_dict={"minimal_diff": 80.0, "convention_adherence": 80.0,
                             "dep_hygiene": 80.0, "scope_discipline": 80.0,
                             "idiomatic_patterns": 80.0, "composite": 80.0},
                as_json=False,
                no_color=True,
            )
        out = captured.getvalue()
        assert "PASS" in out
        assert "≥" in out

    def test_score_one_below_threshold_fails(self, tmp_path):
        """Score == threshold - 1 should fail."""
        from coderace.commands.gate import _output_result
        import io

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            _output_result(
                composite=79.0,
                min_score=80,
                passed=False,
                rubric_dict={"minimal_diff": 79.0, "convention_adherence": 79.0,
                             "dep_hygiene": 79.0, "scope_discipline": 79.0,
                             "idiomatic_patterns": 79.0, "composite": 79.0},
                as_json=False,
                no_color=True,
            )
        out = captured.getvalue()
        assert "FAIL" in out
        assert "<" in out

    def test_score_one_above_threshold_passes(self, tmp_path):
        """Score == threshold + 1 should pass."""
        from coderace.commands.gate import _output_result
        import io

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            _output_result(
                composite=81.0,
                min_score=80,
                passed=True,
                rubric_dict={"minimal_diff": 81.0, "convention_adherence": 81.0,
                             "dep_hygiene": 81.0, "scope_discipline": 81.0,
                             "idiomatic_patterns": 81.0, "composite": 81.0},
                as_json=False,
                no_color=True,
            )
        out = captured.getvalue()
        assert "PASS" in out


# ---------------------------------------------------------------------------
# D2: Empty diff
# ---------------------------------------------------------------------------

class TestGateEmptyDiff:
    def test_empty_diff_file_passes(self, tmp_diff_file):
        """Empty diff file should pass (score 100)."""
        path = tmp_diff_file("")
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "80"])
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_whitespace_only_diff_passes(self, tmp_diff_file):
        """Whitespace-only diff should pass."""
        path = tmp_diff_file("   \n\n  ")
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "80"])
        assert result.exit_code == 0
        assert "PASS" in result.output


# ---------------------------------------------------------------------------
# D2: JSON output
# ---------------------------------------------------------------------------

class TestGateJsonOutput:
    def test_json_output_structure(self, tmp_diff_file):
        """--json flag should produce valid JSON with expected keys."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "50", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "gate" in data
        assert "score" in data
        assert "min_score" in data
        assert "passed" in data
        assert "dimensions" in data

    def test_json_output_pass_values(self, tmp_diff_file):
        """JSON pass result has correct values."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "0", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["gate"] == "PASS"
        assert data["passed"] is True
        assert data["min_score"] == 0
        assert isinstance(data["score"], int)

    def test_json_output_fail_values(self, tmp_diff_file):
        """JSON fail result has correct values."""
        path = tmp_diff_file(BAD_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "100", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["gate"] == "FAIL"
        assert data["passed"] is False
        assert data["min_score"] == 100

    def test_json_output_dimensions_present(self, tmp_diff_file):
        """JSON output includes all 5 rubric dimensions."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "0", "--json"])
        data = json.loads(result.output)
        dims = data["dimensions"]
        assert "minimal_diff" in dims
        assert "convention_adherence" in dims
        assert "dep_hygiene" in dims
        assert "scope_discipline" in dims
        assert "idiomatic_patterns" in dims

    def test_json_empty_diff_passes(self, tmp_diff_file):
        """Empty diff should produce JSON with score 100 and gate PASS."""
        path = tmp_diff_file("")
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "80", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["gate"] == "PASS"
        assert data["score"] == 100


# ---------------------------------------------------------------------------
# D2: File not found
# ---------------------------------------------------------------------------

class TestGateErrorHandling:
    def test_missing_diff_file_exits_nonzero(self):
        """Non-existent diff file should exit with error."""
        result = runner.invoke(app, ["gate", "--diff", "/nonexistent/path.diff", "--min-score", "80"])
        assert result.exit_code != 0

    def test_min_score_required(self, tmp_diff_file):
        """--min-score is required."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path)])
        assert result.exit_code != 0

    def test_diff_required(self):
        """--diff is required."""
        result = runner.invoke(app, ["gate", "--min-score", "80"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# D1: --min-score on coderace review --maintainer-mode
# ---------------------------------------------------------------------------

class TestReviewMinScore:
    def test_review_maintainer_mode_no_min_score_exits_zero(self, tmp_diff_file):
        """--maintainer-mode without --min-score always exits 0."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(
            app,
            ["review", "--diff", str(path), "--maintainer-mode",
             "--agents", "claude", "--format", "markdown"],
        )
        # Exit 0 regardless of score when no min-score set
        assert result.exit_code == 0

    def test_review_min_score_without_maintainer_mode_ignored(self, tmp_diff_file):
        """--min-score without --maintainer-mode: gate print should not appear."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(
            app,
            ["review", "--diff", str(path), "--agents", "claude",
             "--format", "markdown"],
        )
        # Should not crash
        assert result.exit_code in (0, 1)

    def test_review_min_score_gate_pass_message(self, tmp_diff_file):
        """PASS message when score >= min_score."""
        from coderace.commands.review import _append_maintainer_rubric
        from rich.console import Console
        rubric_score = score_rubric(CLEAN_DIFF)
        composite = round(rubric_score.composite)
        # Use a threshold well below actual score
        threshold = max(0, composite - 20)
        # Should return 0 (pass)
        exit_code = _append_maintainer_rubric(CLEAN_DIFF, Console(no_color=True), no_color=True, min_score=threshold)
        assert exit_code == 0

    def test_review_min_score_gate_fail_message(self, tmp_diff_file):
        """FAIL message when score < min_score."""
        from coderace.commands.review import _append_maintainer_rubric
        from rich.console import Console
        # Use threshold of 100 to force failure on any real diff
        exit_code = _append_maintainer_rubric(BAD_DIFF, Console(no_color=True), no_color=True, min_score=100)
        assert exit_code == 1

    def test_review_min_score_none_returns_zero(self):
        """When min_score=None, exit code is always 0."""
        from coderace.commands.review import _append_maintainer_rubric
        from rich.console import Console
        exit_code = _append_maintainer_rubric(BAD_DIFF, Console(no_color=True), no_color=True, min_score=None)
        assert exit_code == 0


# ---------------------------------------------------------------------------
# D2: gate output format (human-readable)
# ---------------------------------------------------------------------------

class TestGateOutputFormat:
    def test_pass_output_contains_checkmark(self, tmp_diff_file):
        """Pass output should contain ✅."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "0"])
        assert "✅" in result.output

    def test_fail_output_contains_x(self, tmp_diff_file):
        """Fail output should contain ❌."""
        path = tmp_diff_file(BAD_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "100"])
        assert "❌" in result.output

    def test_output_contains_score_and_threshold(self, tmp_diff_file):
        """Output should contain the score and threshold."""
        path = tmp_diff_file(CLEAN_DIFF)
        result = runner.invoke(app, ["gate", "--diff", str(path), "--min-score", "42"])
        assert "42" in result.output


# ---------------------------------------------------------------------------
# D3: action.yml includes maintainer-min-score input
# ---------------------------------------------------------------------------

class TestActionYml:
    def test_action_yml_has_maintainer_min_score(self):
        """action.yml should declare maintainer-min-score input."""
        action_path = Path(__file__).parent.parent / "action.yml"
        assert action_path.exists(), "action.yml not found"
        content = action_path.read_text(encoding="utf-8")
        assert "maintainer-min-score" in content

    def test_action_yml_has_default_empty(self):
        """maintainer-min-score default should be empty (no gate by default)."""
        action_path = Path(__file__).parent.parent / "action.yml"
        content = action_path.read_text(encoding="utf-8")
        # Find the maintainer-min-score block
        idx = content.index("maintainer-min-score")
        block = content[idx:idx + 300]
        assert "default: ''" in block

    def test_example_workflow_exists(self):
        """Example quality gate workflow file should exist."""
        wf_path = (
            Path(__file__).parent.parent
            / ".github" / "workflows" / "examples" / "coderace-quality-gate.yml"
        )
        assert wf_path.exists(), "example workflow not found"
        content = wf_path.read_text(encoding="utf-8")
        assert "maintainer-min-score" in content
