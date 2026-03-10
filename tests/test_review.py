"""Tests for review mode core engine and renderers."""

from __future__ import annotations

import json
import io
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from coderace.cli import app
from coderace.commands.review import _read_stdin_diff
from coderace.review import (
    DEFAULT_REVIEW_LANES,
    LANE_DEFINITIONS,
    build_cross_review_prompt,
    build_lane_prompt,
    parse_agent_output_for_findings,
    run_review,
)
from coderace.review_report import render_review_json, render_review_markdown
from coderace.types import AgentResult, LaneFinding, ReviewResult

runner = CliRunner()

SAMPLE_DIFF = """\
diff --git a/api/handlers.py b/api/handlers.py
index 1111111..2222222 100644
--- a/api/handlers.py
+++ b/api/handlers.py
@@ -10,6 +10,10 @@ def handle(request):
-    user = get_user(request.user_id)
+    user = get_user(request.user_id)
+    email = user.email
+    user_id = int(request.data["id"])
+    return {"email": email, "user_id": user_id}
"""


CRITICAL_JSON = (
    '{"findings":[{"severity":"critical","location":"api/handlers.py:12",'
    '"finding":"missing None guard"}]}'
)
WARNING_JSON = (
    '{"findings":[{"severity":"warning","location":"api/handlers.py:13",'
    '"finding":"uncaught ValueError"}]}'
)
PHASE2_JSON = (
    '{"findings":[{"severity":"info","location":"api/handlers.py:12",'
    '"finding":"phase 1 missed that contract ambiguity affects null handling"}]}'
)


def _agent_result(
    agent: str,
    stdout: str,
    exit_code: int = 0,
    timed_out: bool = False,
) -> AgentResult:
    return AgentResult(
        agent=agent,
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        wall_time=0.01,
        timed_out=timed_out,
    )


def _review_result() -> ReviewResult:
    return ReviewResult(
        diff_summary={"files": ["api/handlers.py"], "added": 4, "removed": 1, "binary": []},
        lanes=["null-safety", "type-safety"],
        phase1_findings=[
            LaneFinding(
                lane="null-safety",
                agent="claude",
                severity="critical",
                finding="missing None guard",
                location="api/handlers.py:12",
            )
        ],
        phase2_findings=[],
        agents_used=["claude", "codex"],
        elapsed_seconds=0.42,
        timestamp="2026-03-10T12:00:00+00:00",
    )


def _review_result_with_phase2() -> ReviewResult:
    result = _review_result()
    result.phase1_findings.append(
        LaneFinding(
            lane="contracts",
            agent="codex",
            severity="info",
            finding="public contract is not documented",
            location="api/handlers.py:10",
        )
    )
    result.lanes.append("contracts")
    result.phase2_findings = [
        LaneFinding(
            lane="cross-review",
            agent="claude",
            severity="warning",
            finding="phase 1 missed how the contract ambiguity amplifies the null-safety risk",
            location="api/handlers.py:12",
        )
    ]
    return result


def test_lane_definitions_cover_default_lanes() -> None:
    assert set(DEFAULT_REVIEW_LANES).issubset(LANE_DEFINITIONS)


def test_build_lane_prompt_includes_lane_and_json_contract() -> None:
    prompt = build_lane_prompt(SAMPLE_DIFF, "null-safety")
    assert "Lane: null-safety" in prompt
    assert "Return ONLY valid JSON" in prompt
    assert '"findings"' in prompt
    assert SAMPLE_DIFF in prompt


def test_build_cross_review_prompt_includes_phase1_findings() -> None:
    findings = [
        LaneFinding(
            lane="null-safety",
            agent="claude",
            severity="warning",
            finding="email may be None",
            location="api/handlers.py:12",
        )
    ]
    prompt = build_cross_review_prompt(SAMPLE_DIFF, findings)
    assert "cross-review" in prompt.lower()
    assert "email may be None" in prompt
    assert SAMPLE_DIFF in prompt


def test_parse_agent_output_for_findings_from_json() -> None:
    output = """
    {
      "findings": [
        {
          "severity": "critical",
          "location": "api/handlers.py:12",
          "finding": "user.email is dereferenced without a None guard"
        }
      ]
    }
    """
    findings = parse_agent_output_for_findings(output, "null-safety", agent="claude")
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert findings[0].location == "api/handlers.py:12"


def test_parse_agent_output_for_findings_from_markdown_severity_sections() -> None:
    output = """
    **Critical**
    - `api/handlers.py:12` - user.email is dereferenced without a None guard

    **Warning**
    - `api/handlers.py:13` - int(request.data["id"]) can raise ValueError
    """
    findings = parse_agent_output_for_findings(output, "error-handling", agent="codex")
    assert [finding.severity for finding in findings] == ["critical", "warning"]
    assert findings[1].location == "api/handlers.py:13"


def test_parse_agent_output_for_findings_from_pipe_format() -> None:
    output = """
    critical | api/handlers.py:12 | user.email is dereferenced without a None guard
    info | api/handlers.py:14 | endpoint contract is implicit
    """
    findings = parse_agent_output_for_findings(output, "contracts", agent="claude")
    assert [finding.severity for finding in findings] == ["critical", "info"]
    assert findings[0].finding == "user.email is dereferenced without a None guard"


def test_parse_agent_output_for_findings_empty_json_means_no_findings() -> None:
    assert parse_agent_output_for_findings('{"findings": []}', "type-safety", agent="codex") == []


def test_run_review_round_robins_agents_and_collects_phase1_findings(tmp_path: Path) -> None:
    def fake_runner(agent_spec: str, prompt: str, workdir: Path, timeout: int) -> AgentResult:
        assert workdir == tmp_path
        assert timeout == 12
        if "Lane: null-safety" in prompt:
            return _agent_result(agent_spec, CRITICAL_JSON)
        if "Lane: type-safety" in prompt:
            return _agent_result(agent_spec, '{"findings":[]}')
        return _agent_result(agent_spec, WARNING_JSON)

    result = run_review(
        SAMPLE_DIFF,
        ["null-safety", "type-safety", "error-handling"],
        ["claude", "codex"],
        workdir=tmp_path,
        timeout=12,
        runner=fake_runner,
    )

    assert result.lanes == ["null-safety", "type-safety", "error-handling"]
    assert len(result.phase1_findings) == 2
    assert result.phase1_findings[0].agent == "claude"
    assert result.phase1_findings[1].agent == "claude"
    assert result.phase2_findings == []
    assert result.agents_used == ["claude", "codex"]
    assert result.diff_summary["files"] == ["api/handlers.py"]


def test_run_review_cross_review_collects_phase2_findings(tmp_path: Path) -> None:
    def fake_runner(agent_spec: str, prompt: str, workdir: Path, timeout: int) -> AgentResult:
        if "cross-review" in prompt.lower():
            return _agent_result(agent_spec, PHASE2_JSON)
        return _agent_result(agent_spec, CRITICAL_JSON)

    result = run_review(
        SAMPLE_DIFF,
        ["null-safety", "contracts"],
        ["claude", "codex"],
        cross_review=True,
        workdir=tmp_path,
        runner=fake_runner,
    )

    assert len(result.phase1_findings) == 2
    assert len(result.phase2_findings) == 2
    assert all(finding.lane == "cross-review" for finding in result.phase2_findings)


def test_run_review_unknown_lane_raises() -> None:
    with pytest.raises(ValueError, match="Unknown review lane"):
        run_review(
            SAMPLE_DIFF,
            ["bogus"],
            ["claude"],
            runner=lambda *args: _agent_result("claude", ""),
        )


def test_run_review_requires_agents() -> None:
    with pytest.raises(ValueError, match="At least one review agent"):
        run_review(
            SAMPLE_DIFF,
            ["null-safety"],
            [],
            runner=lambda *args: _agent_result("claude", ""),
        )


def test_run_review_turns_failed_agent_into_warning_finding(tmp_path: Path) -> None:
    def fake_runner(agent_spec: str, prompt: str, workdir: Path, timeout: int) -> AgentResult:
        return _agent_result(agent_spec, "nonsense output", exit_code=1)

    result = run_review(
        SAMPLE_DIFF,
        ["null-safety"],
        ["claude"],
        workdir=tmp_path,
        runner=fake_runner,
    )

    assert len(result.phase1_findings) == 1
    assert result.phase1_findings[0].severity == "warning"
    assert "failed to return findings" in result.phase1_findings[0].finding


def test_review_command_is_registered() -> None:
    result = runner.invoke(app, ["review", "--help"])
    assert result.exit_code == 0
    assert "--diff" in result.output
    assert "--cross-review" in result.output


def test_review_cli_reads_diff_from_stdin() -> None:
    with patch("coderace.commands.review.run_review", return_value=_review_result()) as mock_run:
        result = runner.invoke(app, ["review"], input=SAMPLE_DIFF)

    assert result.exit_code == 0
    assert "# Code Review Report" in result.output
    mock_run.assert_called_once()
    assert mock_run.call_args.args[0] == SAMPLE_DIFF


def test_review_cli_reads_diff_from_file(tmp_path: Path) -> None:
    diff_path = tmp_path / "sample.patch"
    diff_path.write_text(SAMPLE_DIFF, encoding="utf-8")

    with patch("coderace.commands.review.run_review", return_value=_review_result()) as mock_run:
        result = runner.invoke(app, ["review", "--diff", str(diff_path)])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args.args[0] == SAMPLE_DIFF


def test_review_cli_reads_diff_from_commit() -> None:
    def fake_subprocess_run(*args, **kwargs):
        assert args[0] == ["git", "diff", "HEAD~1~1", "HEAD~1"]
        return subprocess.CompletedProcess(args[0], 0, stdout=SAMPLE_DIFF, stderr="")

    with patch("coderace.commands.review.subprocess.run", side_effect=fake_subprocess_run), patch(
        "coderace.commands.review.run_review", return_value=_review_result()
    ) as mock_run:
        result = runner.invoke(app, ["review", "--commit", "HEAD~1"])

    assert result.exit_code == 0
    assert mock_run.call_args.args[0] == SAMPLE_DIFF


def test_review_cli_reads_diff_from_branch_range() -> None:
    def fake_subprocess_run(*args, **kwargs):
        assert args[0] == ["git", "diff", "main...feature"]
        return subprocess.CompletedProcess(args[0], 0, stdout=SAMPLE_DIFF, stderr="")

    with patch("coderace.commands.review.subprocess.run", side_effect=fake_subprocess_run), patch(
        "coderace.commands.review.run_review", return_value=_review_result()
    ) as mock_run:
        result = runner.invoke(app, ["review", "--branch", "main...feature"])

    assert result.exit_code == 0
    assert mock_run.call_args.args[0] == SAMPLE_DIFF


def test_read_stdin_diff_requires_non_tty_input(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_stdin = io.StringIO("")
    monkeypatch.setattr(fake_stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr("coderace.commands.review.sys.stdin", fake_stdin)

    with pytest.raises(ValueError, match="No diff provided"):
        _read_stdin_diff()


def test_review_cli_json_output_is_valid() -> None:
    with patch("coderace.commands.review.run_review", return_value=_review_result()):
        result = runner.invoke(app, ["review", "--format", "json"], input=SAMPLE_DIFF)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["lanes"] == ["null-safety", "type-safety"]
    assert payload["phase1_findings"][0]["severity"] == "critical"


def test_review_cli_output_file_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "review.md"
    with patch("coderace.commands.review.run_review", return_value=_review_result()):
        result = runner.invoke(
            app,
            ["review", "--output", str(output_path)],
            input=SAMPLE_DIFF,
        )

    assert result.exit_code == 0
    assert output_path.exists()
    assert "# Code Review Report" in output_path.read_text(encoding="utf-8")


def test_review_cli_rejects_unknown_agent() -> None:
    result = runner.invoke(app, ["review", "--agents", "bogus"], input=SAMPLE_DIFF)
    assert result.exit_code != 0
    assert "Unknown agent" in result.output


def test_render_review_markdown_contains_key_sections() -> None:
    rendered = render_review_markdown(_review_result())
    assert "# Code Review Report" in rendered
    assert "## Phase 1: Lane Findings" in rendered
    assert "### Null Safety (claude)" in rendered
    assert "*No findings.*" in rendered
    assert "| Critical | 1 |" in rendered


def test_render_review_markdown_renders_phase2_when_present() -> None:
    rendered = render_review_markdown(_review_result_with_phase2())
    assert "## Phase 2: Cross-Review Synthesis" in rendered
    assert "### claude" in rendered
    assert "contract ambiguity amplifies the null-safety risk" in rendered


def test_render_review_markdown_omits_phase2_when_empty() -> None:
    rendered = render_review_markdown(_review_result())
    assert "## Phase 2: Cross-Review Synthesis" not in rendered


def test_render_review_json_is_valid() -> None:
    rendered = render_review_json(_review_result_with_phase2())
    payload = json.loads(rendered)
    assert payload["phase2_findings"][0]["lane"] == "cross-review"
    assert payload["phase1_findings"][0]["location"] == "api/handlers.py:12"


def test_review_pipeline_with_mocked_adapters_returns_expected_structure(tmp_path: Path) -> None:
    class FakeAdapter:
        def __init__(self, agent_name: str) -> None:
            self.name = agent_name

        def run(
            self,
            task_description: str,
            workdir: Path,
            timeout: int,
            no_cost: bool = False,
            custom_pricing: dict | None = None,
        ) -> AgentResult:
            if "cross-review of prior code review findings" in task_description:
                stdout = (
                    '{"findings":[{"severity":"warning","location":"api/handlers.py:13",'
                    '"finding":"phase 1 should connect the ValueError path to the endpoint contract"}]}'
                )
            elif "Lane: null-safety" in task_description:
                stdout = (
                    '{"findings":[{"severity":"critical","location":"auth/validators.py:42",'
                    '"finding":"user.profile can be None before name is accessed"}]}'
                )
            elif "Lane: type-safety" in task_description:
                stdout = (
                    '{"findings":[{"severity":"warning","location":"api/handlers.py:13",'
                    '"finding":"int(request.data[\\"id\\"]) can raise ValueError on non-numeric input"}]}'
                )
            elif "Lane: error-handling" in task_description:
                stdout = (
                    '{"findings":[{"severity":"warning","location":"cache/client.py:6",'
                    '"finding":"cache.get(key) can return None before strip() is called"}]}'
                )
            else:
                stdout = '{"findings":[]}'
            return _agent_result(self.name, stdout)

    sample_patch = Path("tests/fixtures/sample.patch").read_text(encoding="utf-8")

    with patch("coderace.review.instantiate_adapter", side_effect=lambda spec: FakeAdapter(spec)):
        result = run_review(
            sample_patch,
            ["null-safety", "type-safety", "error-handling", "contracts"],
            ["claude", "codex"],
            cross_review=True,
            workdir=tmp_path,
        )

    assert result.diff_summary["files"] == [
        "api/handlers.py",
        "auth/validators.py",
        "cache/client.py",
    ]
    assert len(result.phase1_findings) == 3
    assert len(result.phase2_findings) == 2
    assert result.phase1_findings[0].severity == "critical"
    assert result.phase2_findings[0].lane == "cross-review"


def test_review_pipeline_markdown_contains_expected_sections(tmp_path: Path) -> None:
    class FakeAdapter:
        def __init__(self, agent_name: str) -> None:
            self.name = agent_name

        def run(
            self,
            task_description: str,
            workdir: Path,
            timeout: int,
            no_cost: bool = False,
            custom_pricing: dict | None = None,
        ) -> AgentResult:
            if "Lane: null-safety" in task_description:
                return _agent_result(
                    self.name,
                    '{"findings":[{"severity":"critical","location":"auth/validators.py:42","finding":"user.profile can be None before name is accessed"}]}',
                )
            return _agent_result(self.name, '{"findings":[]}')

    sample_patch = Path("tests/fixtures/sample.patch").read_text(encoding="utf-8")
    with patch("coderace.review.instantiate_adapter", side_effect=lambda spec: FakeAdapter(spec)):
        result = run_review(
            sample_patch,
            ["null-safety", "type-safety"],
            ["claude", "codex"],
            workdir=tmp_path,
        )

    rendered = render_review_markdown(result)
    assert "**Diff:** 3 files, +8 lines, -4 lines" in rendered
    assert "### Null Safety (claude)" in rendered
    assert "### Type Safety" in rendered
    assert "| Critical | 1 |" in rendered


def test_review_pipeline_json_matches_schema_shape(tmp_path: Path) -> None:
    class FakeAdapter:
        def __init__(self, agent_name: str) -> None:
            self.name = agent_name

        def run(
            self,
            task_description: str,
            workdir: Path,
            timeout: int,
            no_cost: bool = False,
            custom_pricing: dict | None = None,
        ) -> AgentResult:
            return _agent_result(
                self.name,
                '{"findings":[{"severity":"info","location":"api/handlers.py:13","finding":"contract is implicit"}]}',
            )

    sample_patch = Path("tests/fixtures/sample.patch").read_text(encoding="utf-8")
    with patch("coderace.review.instantiate_adapter", side_effect=lambda spec: FakeAdapter(spec)):
        result = run_review(
            sample_patch,
            ["contracts"],
            ["claude"],
            workdir=tmp_path,
        )

    payload = json.loads(render_review_json(result))
    assert sorted(payload.keys()) == [
        "agents_used",
        "diff_summary",
        "elapsed_seconds",
        "lanes",
        "phase1_findings",
        "phase2_findings",
        "timestamp",
    ]
    assert payload["phase1_findings"][0]["severity"] == "info"


def test_review_cli_with_sample_patch_uses_real_pipeline() -> None:
    class FakeAdapter:
        def __init__(self, agent_name: str) -> None:
            self.name = agent_name

        def run(
            self,
            task_description: str,
            workdir: Path,
            timeout: int,
            no_cost: bool = False,
            custom_pricing: dict | None = None,
        ) -> AgentResult:
            if "Lane: null-safety" in task_description:
                return _agent_result(
                    self.name,
                    '{"findings":[{"severity":"critical","location":"auth/validators.py:42","finding":"user.profile can be None before name is accessed"}]}',
                )
            return _agent_result(self.name, '{"findings":[]}')

    with patch("coderace.review.instantiate_adapter", side_effect=lambda spec: FakeAdapter(spec)):
        result = runner.invoke(
            app,
            ["review", "--diff", "tests/fixtures/sample.patch", "--lanes", "null-safety,type-safety"],
        )

    assert result.exit_code == 0
    assert "# Code Review Report" in result.output
    assert "### Null Safety (claude)" in result.output
    assert "### Type Safety" in result.output
