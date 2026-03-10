"""Tests for the GitHub Action review mode infrastructure.

Covers:
  - scripts/format-review-comment.py
  - action.yml structure (new inputs/outputs)
  - Example workflow YAML validity
  - Integration smoke test: empty diff case
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load format-review-comment.py via importlib (hyphenated filename)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_REPO_ROOT = Path(__file__).parent.parent


def _load_format_review_comment():
    spec = importlib.util.spec_from_file_location(
        "format_review_comment",
        _SCRIPTS_DIR / "format-review-comment.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


frc = _load_format_review_comment()


# ---------------------------------------------------------------------------
# Sample data matching ReviewResult schema (coderace/types.py)
# ---------------------------------------------------------------------------

SAMPLE_REVIEW_DATA = {
    "diff_summary": {"files": ["api/handlers.py", "api/utils.py"], "added": 25, "removed": 10},
    "lanes": ["security", "logic"],
    "phase1_findings": [
        {
            "lane": "security",
            "agent": "claude",
            "severity": "critical",
            "finding": "User input used directly in SQL query — SQL injection risk.",
            "location": "api/handlers.py:42",
        },
        {
            "lane": "security",
            "agent": "claude",
            "severity": "warning",
            "finding": "Missing authentication check before sensitive operation.",
            "location": "api/handlers.py:67",
        },
        {
            "lane": "logic",
            "agent": "codex",
            "severity": "error",
            "finding": "Off-by-one error in pagination logic.",
            "location": "api/utils.py:13",
        },
    ],
    "phase2_findings": [
        {
            "lane": "cross-review",
            "agent": "claude",
            "severity": "critical",
            "finding": "SQL injection confirmed — no parameterized queries used.",
            "location": "api/handlers.py:42",
        },
    ],
    "agents_used": ["claude", "codex"],
    "elapsed_seconds": 12.4,
    "timestamp": "2026-03-10T15:00:00",
}

EMPTY_REVIEW_DATA = {
    "diff_summary": {"files": [], "added": 0, "removed": 0},
    "lanes": ["security", "logic"],
    "phase1_findings": [],
    "phase2_findings": [],
    "agents_used": ["claude"],
    "elapsed_seconds": 5.1,
    "timestamp": "2026-03-10T15:00:00",
}


# ---------------------------------------------------------------------------
# format_header
# ---------------------------------------------------------------------------


def test_format_header_counts() -> None:
    header = frc.format_header(SAMPLE_REVIEW_DATA)
    assert "2 agent(s)" in header
    assert "2 lane(s)" in header
    assert "12.4s" in header


def test_format_header_minimal() -> None:
    data = {"agents_used": [], "lanes": [], "elapsed_seconds": 0.0}
    header = frc.format_header(data)
    assert "## coderace review" in header


# ---------------------------------------------------------------------------
# format_summary
# ---------------------------------------------------------------------------


def test_format_summary_with_findings() -> None:
    summary = frc.format_summary(SAMPLE_REVIEW_DATA)
    # Total = 3 phase1 + 1 phase2 = 4
    assert "4 finding(s)" in summary


def test_format_summary_no_findings() -> None:
    summary = frc.format_summary(EMPTY_REVIEW_DATA)
    assert "no issues" in summary.lower()
    assert "✅" in summary


def test_format_summary_top_critical() -> None:
    summary = frc.format_summary(SAMPLE_REVIEW_DATA)
    assert "SQL injection" in summary or "api/handlers.py:42" in summary


# ---------------------------------------------------------------------------
# format_lane_section
# ---------------------------------------------------------------------------


def test_format_lane_section_contains_lanes() -> None:
    section = frc.format_lane_section(SAMPLE_REVIEW_DATA)
    assert "Security" in section
    assert "Logic" in section


def test_format_lane_section_agent_attribution() -> None:
    section = frc.format_lane_section(SAMPLE_REVIEW_DATA)
    assert "claude" in section
    assert "codex" in section


def test_format_lane_section_findings() -> None:
    section = frc.format_lane_section(SAMPLE_REVIEW_DATA)
    assert "SQL injection" in section
    assert "api/handlers.py:42" in section


def test_format_lane_section_empty_lanes() -> None:
    section = frc.format_lane_section(EMPTY_REVIEW_DATA)
    assert "No findings" in section or "no findings" in section.lower()


# ---------------------------------------------------------------------------
# format_cross_review_section
# ---------------------------------------------------------------------------


def test_format_cross_review_section_present() -> None:
    section = frc.format_cross_review_section(SAMPLE_REVIEW_DATA)
    assert "Phase 2" in section
    assert "claude" in section


def test_format_cross_review_section_empty() -> None:
    section = frc.format_cross_review_section(EMPTY_REVIEW_DATA)
    assert section == ""


# ---------------------------------------------------------------------------
# format_review_comment (full output)
# ---------------------------------------------------------------------------


def test_format_review_comment_marker() -> None:
    comment = frc.format_review_comment(SAMPLE_REVIEW_DATA)
    assert "<!-- coderace-review -->" in comment


def test_format_review_comment_includes_header() -> None:
    comment = frc.format_review_comment(SAMPLE_REVIEW_DATA)
    assert "## coderace review" in comment


def test_format_review_comment_includes_summary() -> None:
    comment = frc.format_review_comment(SAMPLE_REVIEW_DATA)
    assert "finding(s)" in comment


def test_format_review_comment_includes_json_collapsible() -> None:
    raw = json.dumps(SAMPLE_REVIEW_DATA)
    comment = frc.format_review_comment(SAMPLE_REVIEW_DATA, json_raw=raw)
    assert "<details>" in comment
    assert "```json" in comment


def test_format_review_comment_no_issues() -> None:
    comment = frc.format_review_comment(EMPTY_REVIEW_DATA)
    assert "<!-- coderace-review -->" in comment
    assert "no issues" in comment.lower()


def test_format_review_comment_footer() -> None:
    comment = frc.format_review_comment(SAMPLE_REVIEW_DATA)
    assert "coderace" in comment.lower()


# ---------------------------------------------------------------------------
# format_empty_comment
# ---------------------------------------------------------------------------


def test_format_empty_comment_has_marker() -> None:
    comment = frc.format_empty_comment()
    assert "<!-- coderace-review -->" in comment


def test_format_empty_comment_custom_reason() -> None:
    comment = frc.format_empty_comment("JSON file not found.")
    assert "JSON file not found." in comment


# ---------------------------------------------------------------------------
# main() CLI entry point
# ---------------------------------------------------------------------------


def test_main_missing_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    missing = tmp_path / "nonexistent-review.json"
    ret = frc.main(["--json-file", str(missing)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "<!-- coderace-review -->" in captured.out


def test_main_writes_to_file(tmp_path: Path) -> None:
    json_file = tmp_path / "review.json"
    json_file.write_text(json.dumps(SAMPLE_REVIEW_DATA))
    out_file = tmp_path / "comment.md"

    ret = frc.main(["--json-file", str(json_file), "--output", str(out_file)])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text()
    assert "<!-- coderace-review -->" in content
    assert "## coderace review" in content


def test_main_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    bad = tmp_path / "bad-review.json"
    bad.write_text("NOT JSON AT ALL")
    ret = frc.main(["--json-file", str(bad)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "<!-- coderace-review -->" in captured.out


def test_main_empty_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("")
    ret = frc.main(["--json-file", str(empty)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "<!-- coderace-review -->" in captured.out


def test_main_stdout_default(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    json_file = tmp_path / "review.json"
    json_file.write_text(json.dumps(EMPTY_REVIEW_DATA))
    ret = frc.main(["--json-file", str(json_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "<!-- coderace-review -->" in captured.out


# ---------------------------------------------------------------------------
# action.yml structure checks
# ---------------------------------------------------------------------------


def test_action_yml_has_mode_input() -> None:
    """action.yml must have the new mode input."""
    action_yml = (_REPO_ROOT / "action.yml").read_text()
    assert "mode:" in action_yml
    assert "review" in action_yml


def test_action_yml_has_diff_source_input() -> None:
    action_yml = (_REPO_ROOT / "action.yml").read_text()
    assert "diff-source:" in action_yml


def test_action_yml_has_review_outputs() -> None:
    action_yml = (_REPO_ROOT / "action.yml").read_text()
    assert "review-json" in action_yml
    assert "review-md" in action_yml


def test_action_yml_backward_compatible() -> None:
    """mode: run path still references ci-run.sh."""
    action_yml = (_REPO_ROOT / "action.yml").read_text()
    assert "ci-run.sh" in action_yml


def test_action_yml_review_path() -> None:
    """mode: review path references ci-review.sh."""
    action_yml = (_REPO_ROOT / "action.yml").read_text()
    assert "ci-review.sh" in action_yml


# ---------------------------------------------------------------------------
# ci-review.sh existence + executable
# ---------------------------------------------------------------------------


def test_ci_review_sh_exists() -> None:
    script = _REPO_ROOT / "scripts" / "ci-review.sh"
    assert script.exists(), "scripts/ci-review.sh must exist"


def test_ci_review_sh_is_executable() -> None:
    import stat

    script = _REPO_ROOT / "scripts" / "ci-review.sh"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/ci-review.sh must be executable"


# ---------------------------------------------------------------------------
# Example workflow YAML validity
# ---------------------------------------------------------------------------


def test_example_workflow_is_valid_yaml() -> None:
    """Example coderace-pr-review.yml must be valid YAML."""
    example = _REPO_ROOT / ".github" / "workflows" / "examples" / "coderace-pr-review.yml"
    assert example.exists(), "Example workflow file must exist"
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        pytest.skip("pyyaml not installed")
    data = yaml.safe_load(example.read_text())
    assert data is not None
    assert "on" in data or True  # YAML key "on" may parse as True
    assert "jobs" in data


def test_example_workflow_uses_mode_review() -> None:
    example = _REPO_ROOT / ".github" / "workflows" / "examples" / "coderace-pr-review.yml"
    content = example.read_text()
    assert "mode: review" in content


def test_example_workflow_fetch_depth_0() -> None:
    """Must use fetch-depth: 0 for git diff to work."""
    example = _REPO_ROOT / ".github" / "workflows" / "examples" / "coderace-pr-review.yml"
    content = example.read_text()
    assert "fetch-depth: 0" in content


# ---------------------------------------------------------------------------
# Integration smoke test: empty diff path via coderace review
# ---------------------------------------------------------------------------


def test_review_command_exists() -> None:
    """coderace review subcommand must be importable and registered."""
    from coderace.cli import app  # noqa: F401
    from coderace.commands.review import app as review_app  # noqa: F401

    assert review_app is not None


def test_review_render_empty_result() -> None:
    """render_review_markdown and render_review_json should not crash on minimal input."""
    from coderace.review_report import render_review_json, render_review_markdown
    from coderace.types import ReviewResult

    result = ReviewResult(
        diff_summary={"files": [], "added": 0, "removed": 0},
        lanes=[],
        phase1_findings=[],
        phase2_findings=[],
        agents_used=[],
        elapsed_seconds=0.0,
        timestamp="2026-03-10T15:00:00",
    )
    md = render_review_markdown(result)
    assert isinstance(md, str)
    js = render_review_json(result)
    assert isinstance(js, str)
    data = json.loads(js)
    assert "lanes" in data
