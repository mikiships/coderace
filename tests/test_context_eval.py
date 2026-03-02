"""Tests for context-eval: D1 (core + CLI) and D2 (statistical comparison)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coderace.context_eval import (
    KNOWN_CONTEXT_FILES,
    ContextEvalResult,
    TrialResult,
    _backup_context_files,
    _place_context_file,
    _remove_context_files,
    _remove_placed_context_file,
    _restore_context_files,
)
from coderace.context_eval_report import (
    _cohens_d,
    _delta_ci_95,
    _mean_score,
    _pass_rate,
    _verdict,
    render_context_eval_json,
    render_context_eval_terminal,
)


# ---------------------------------------------------------------------------
# D1: Context file placement/removal/backup logic
# ---------------------------------------------------------------------------


class TestContextFilePlacement:
    def test_place_context_file(self, tmp_path: Path) -> None:
        ctx = tmp_path / "CLAUDE.md"
        ctx.write_text("# Instructions\nBe helpful.")
        workdir = tmp_path / "workdir"
        workdir.mkdir()

        placed = _place_context_file(ctx, workdir)
        assert placed == workdir / "CLAUDE.md"
        assert placed.read_text() == "# Instructions\nBe helpful."

    def test_remove_placed_context_file(self, tmp_path: Path) -> None:
        placed = tmp_path / "CLAUDE.md"
        placed.write_text("content")
        _remove_placed_context_file(placed)
        assert not placed.exists()

    def test_remove_nonexistent_context_file(self, tmp_path: Path) -> None:
        # Should not raise
        _remove_placed_context_file(tmp_path / "nonexistent.md")


class TestContextFileBackup:
    def test_backup_and_restore(self, tmp_path: Path) -> None:
        workdir = tmp_path / "workdir"
        workdir.mkdir()
        claude_md = workdir / "CLAUDE.md"
        claude_md.write_text("original content")

        backups = _backup_context_files(workdir)
        assert len(backups) == 1
        assert claude_md in backups
        assert backups[claude_md].exists()

        # Modify the original
        claude_md.write_text("modified content")

        # Restore
        _restore_context_files(backups)
        assert claude_md.read_text() == "original content"
        assert not backups[claude_md].exists()  # backup removed

    def test_backup_no_context_files(self, tmp_path: Path) -> None:
        workdir = tmp_path / "empty"
        workdir.mkdir()
        backups = _backup_context_files(workdir)
        assert len(backups) == 0

    def test_backup_multiple_context_files(self, tmp_path: Path) -> None:
        workdir = tmp_path / "workdir"
        workdir.mkdir()
        (workdir / "CLAUDE.md").write_text("claude")
        (workdir / "AGENTS.md").write_text("agents")

        backups = _backup_context_files(workdir)
        assert len(backups) == 2

        _restore_context_files(backups)
        assert (workdir / "CLAUDE.md").read_text() == "claude"
        assert (workdir / "AGENTS.md").read_text() == "agents"


class TestRemoveContextFiles:
    def test_removes_existing_context_files(self, tmp_path: Path) -> None:
        workdir = tmp_path / "workdir"
        workdir.mkdir()
        (workdir / "CLAUDE.md").write_text("content")
        (workdir / "AGENTS.md").write_text("content")

        removed = _remove_context_files(workdir)
        assert len(removed) == 2
        assert not (workdir / "CLAUDE.md").exists()
        assert not (workdir / "AGENTS.md").exists()

    def test_removes_nothing_when_empty(self, tmp_path: Path) -> None:
        workdir = tmp_path / "empty"
        workdir.mkdir()
        removed = _remove_context_files(workdir)
        assert removed == []

    def test_removes_nested_context_file(self, tmp_path: Path) -> None:
        workdir = tmp_path / "workdir"
        workdir.mkdir()
        gh_dir = workdir / ".github"
        gh_dir.mkdir()
        (gh_dir / "copilot-instructions.md").write_text("copilot")

        removed = _remove_context_files(workdir)
        assert len(removed) == 1
        assert not (gh_dir / "copilot-instructions.md").exists()


# ---------------------------------------------------------------------------
# D1: ContextEvalResult dataclass
# ---------------------------------------------------------------------------


class TestContextEvalResult:
    def test_defaults(self) -> None:
        r = ContextEvalResult(
            context_file="CLAUDE.md",
            agents=["claude"],
            tasks=["fibonacci"],
            trials_per_condition=3,
        )
        assert r.results == []
        assert r.finished_at is None

    def test_finish(self) -> None:
        r = ContextEvalResult(
            context_file="CLAUDE.md",
            agents=["claude"],
            tasks=["fibonacci"],
            trials_per_condition=3,
        )
        r.finish()
        assert r.finished_at is not None
        assert r.elapsed >= 0

    def test_get_results_filters(self) -> None:
        results = [
            TrialResult("claude", "fibonacci", "baseline", 1, True, 5.0, 80.0),
            TrialResult("claude", "fibonacci", "treatment", 1, True, 4.0, 90.0),
            TrialResult("codex", "fibonacci", "baseline", 1, False, 6.0, 40.0),
        ]
        r = ContextEvalResult(
            context_file="CLAUDE.md",
            agents=["claude", "codex"],
            tasks=["fibonacci"],
            trials_per_condition=1,
            results=results,
        )
        assert len(r.get_results(agent="claude")) == 2
        assert len(r.get_results(condition="baseline")) == 2
        assert len(r.get_results(agent="claude", condition="treatment")) == 1
        assert len(r.get_results(task_name="fibonacci")) == 3


# ---------------------------------------------------------------------------
# D1: CLI argument validation
# ---------------------------------------------------------------------------


class TestContextEvalCLI:
    def test_missing_context_file(self) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "context-eval",
            "--context-file", "/nonexistent/CLAUDE.md",
            "--task", "task.yaml",
            "--agents", "claude",
        ])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_no_task_or_benchmark(self) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"# Context")
            f.flush()
            result = runner.invoke(app, [
                "context-eval",
                "--context-file", f.name,
                "--agents", "claude",
            ])
        assert result.exit_code != 0
        assert "--task" in result.output or "--benchmark" in result.output

    def test_both_task_and_benchmark(self) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"# Context")
            f.flush()
            result = runner.invoke(app, [
                "context-eval",
                "--context-file", f.name,
                "--task", "task.yaml",
                "--benchmark",
                "--agents", "claude",
            ])
        assert result.exit_code != 0
        assert "Cannot use both" in result.output

    def test_trials_less_than_2(self) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"# Context")
            f.flush()
            result = runner.invoke(app, [
                "context-eval",
                "--context-file", f.name,
                "--task", "task.yaml",
                "--agents", "claude",
                "--trials", "1",
            ])
        assert result.exit_code != 0
        assert ">= 2" in result.output

    def test_no_agents(self) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"# Context")
            f.flush()
            result = runner.invoke(app, [
                "context-eval",
                "--context-file", f.name,
                "--task", "task.yaml",
            ])
        assert result.exit_code != 0

    def test_no_valid_agents(self) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"# Context")
            f.flush()
            result = runner.invoke(app, [
                "context-eval",
                "--context-file", f.name,
                "--task", "task.yaml",
                "--agents", "fake_agent_xyz",
            ])
        assert result.exit_code != 0
        assert "Unknown agent" in result.output or "No valid agents" in result.output

    def test_zero_tasks_selected(self) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as ctx_f:
            ctx_f.write(b"# Context")
            ctx_f.flush()
            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(app, [
                    "context-eval",
                    "--context-file", ctx_f.name,
                    "--benchmark",
                    "--task-dir", tmpdir,
                    "--agents", "claude",
                ])
        assert result.exit_code != 0

    def test_task_file_not_found(self) -> None:
        from typer.testing import CliRunner
        from coderace.cli import app

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"# Context")
            f.flush()
            result = runner.invoke(app, [
                "context-eval",
                "--context-file", f.name,
                "--task", "/nonexistent/task.yaml",
                "--agents", "claude",
            ])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# D2: Statistical comparison logic
# ---------------------------------------------------------------------------


class TestStatisticalComparison:
    def test_pass_rate(self) -> None:
        results = [
            TrialResult("claude", "fib", "baseline", 1, True, 5.0, 80.0),
            TrialResult("claude", "fib", "baseline", 2, False, 6.0, 0.0),
            TrialResult("claude", "fib", "baseline", 3, True, 4.0, 90.0),
        ]
        assert _pass_rate(results) == pytest.approx(2 / 3)

    def test_pass_rate_empty(self) -> None:
        assert _pass_rate([]) == 0.0

    def test_mean_score(self) -> None:
        results = [
            TrialResult("claude", "fib", "baseline", 1, True, 5.0, 80.0),
            TrialResult("claude", "fib", "baseline", 2, True, 4.0, 90.0),
        ]
        assert _mean_score(results) == pytest.approx(85.0)

    def test_cohens_d_positive_effect(self) -> None:
        baseline = [50.0, 55.0, 52.0, 48.0]
        treatment = [70.0, 75.0, 72.0, 68.0]
        d = _cohens_d(baseline, treatment)
        assert d > 1.0  # Large effect

    def test_cohens_d_no_effect(self) -> None:
        baseline = [50.0, 50.0, 50.0]
        treatment = [50.0, 50.0, 50.0]
        d = _cohens_d(baseline, treatment)
        assert d == pytest.approx(0.0)

    def test_cohens_d_empty(self) -> None:
        assert _cohens_d([], [50.0]) == 0.0
        assert _cohens_d([50.0], []) == 0.0

    def test_delta_ci_95_positive(self) -> None:
        baseline = [50.0, 52.0, 48.0, 51.0]
        treatment = [80.0, 82.0, 78.0, 81.0]
        delta, ci_lo, ci_hi = _delta_ci_95(baseline, treatment)
        assert delta == pytest.approx(30.0, abs=1.0)
        assert ci_lo > 0  # Significantly positive
        assert ci_hi > ci_lo

    def test_delta_ci_95_no_difference(self) -> None:
        baseline = [50.0, 50.0, 50.0]
        treatment = [50.0, 50.0, 50.0]
        delta, ci_lo, ci_hi = _delta_ci_95(baseline, treatment)
        assert delta == pytest.approx(0.0)
        assert ci_lo == pytest.approx(0.0)
        assert ci_hi == pytest.approx(0.0)

    def test_delta_ci_95_empty(self) -> None:
        delta, ci_lo, ci_hi = _delta_ci_95([], [])
        assert delta == 0.0


class TestVerdict:
    def test_improved(self) -> None:
        v = _verdict(15.0, 5.0, 25.0)
        assert "improved" in v.lower()

    def test_degraded(self) -> None:
        v = _verdict(-10.0, -20.0, -5.0)
        assert "degraded" in v.lower()

    def test_no_significant(self) -> None:
        v = _verdict(2.0, -5.0, 9.0)
        assert "no significant" in v.lower()


# ---------------------------------------------------------------------------
# D2: Report outputs
# ---------------------------------------------------------------------------


def _make_eval_result() -> ContextEvalResult:
    """Create a sample ContextEvalResult with known data."""
    results = [
        # Claude baseline: lower scores
        TrialResult("claude", "fibonacci", "baseline", 1, True, 5.0, 60.0),
        TrialResult("claude", "fibonacci", "baseline", 2, True, 4.5, 65.0),
        TrialResult("claude", "fibonacci", "baseline", 3, False, 6.0, 40.0),
        # Claude treatment: higher scores
        TrialResult("claude", "fibonacci", "treatment", 1, True, 4.0, 80.0),
        TrialResult("claude", "fibonacci", "treatment", 2, True, 3.5, 85.0),
        TrialResult("claude", "fibonacci", "treatment", 3, True, 4.2, 78.0),
        # Codex baseline
        TrialResult("codex", "fibonacci", "baseline", 1, True, 7.0, 50.0),
        TrialResult("codex", "fibonacci", "baseline", 2, False, 8.0, 30.0),
        TrialResult("codex", "fibonacci", "baseline", 3, True, 7.5, 55.0),
        # Codex treatment
        TrialResult("codex", "fibonacci", "treatment", 1, True, 6.0, 70.0),
        TrialResult("codex", "fibonacci", "treatment", 2, True, 5.5, 75.0),
        TrialResult("codex", "fibonacci", "treatment", 3, True, 6.5, 65.0),
    ]
    return ContextEvalResult(
        context_file="CLAUDE.md",
        agents=["claude", "codex"],
        tasks=["fibonacci"],
        trials_per_condition=3,
        results=results,
    )


class TestTerminalReport:
    def test_renders_without_crash(self) -> None:
        from rich.console import Console
        console = Console(no_color=True, record=True)
        result = _make_eval_result()
        render_context_eval_terminal(result, console)
        output = console.export_text()
        assert "claude" in output
        assert "codex" in output
        assert "fibonacci" in output

    def test_shows_delta(self) -> None:
        from rich.console import Console
        console = Console(no_color=True, record=True)
        result = _make_eval_result()
        render_context_eval_terminal(result, console)
        output = console.export_text()
        # Delta should be positive (treatment > baseline)
        assert "+" in output

    def test_shows_verdict(self) -> None:
        from rich.console import Console
        console = Console(no_color=True, record=True)
        result = _make_eval_result()
        render_context_eval_terminal(result, console)
        output = console.export_text()
        assert "improved" in output.lower() or "no significant" in output.lower() or "degraded" in output.lower()


class TestJSONReport:
    def test_json_structure(self) -> None:
        result = _make_eval_result()
        data = render_context_eval_json(result)
        assert data["type"] == "context-eval"
        assert data["context_file"] == "CLAUDE.md"
        assert data["trials_per_condition"] == 3
        assert len(data["agents"]) == 2
        assert len(data["tasks"]) == 2  # 2 agents x 1 task
        assert "summary" in data
        assert "verdict" in data["summary"]

    def test_json_agent_data(self) -> None:
        result = _make_eval_result()
        data = render_context_eval_json(result)
        agent_data = {a["agent"]: a for a in data["agents"]}

        claude = agent_data["claude"]
        assert claude["treatment_mean_score"] > claude["baseline_mean_score"]
        assert claude["delta"] > 0
        assert len(claude["ci_95"]) == 2

    def test_json_trials_list(self) -> None:
        result = _make_eval_result()
        data = render_context_eval_json(result)
        assert len(data["trials"]) == 12  # 2 agents x 1 task x 2 conditions x 3 trials

    def test_json_is_serializable(self) -> None:
        result = _make_eval_result()
        data = render_context_eval_json(result)
        # Should not raise
        json.dumps(data)

    def test_json_summary_verdict(self) -> None:
        result = _make_eval_result()
        data = render_context_eval_json(result)
        assert isinstance(data["summary"]["verdict"], str)
        assert len(data["summary"]["verdict"]) > 0


# ---------------------------------------------------------------------------
# Integration: mock agent that performs differently with/without context
# ---------------------------------------------------------------------------


class TestMockAgentIntegration:
    """Integration test using a mock agent adapter."""

    def test_mock_agent_better_with_context(self, tmp_path: Path) -> None:
        """Mock agent that scores higher when a CLAUDE.md file is present."""
        # This test constructs TrialResults directly to validate
        # the statistical pipeline, since running real agents requires
        # actual CLI installations.

        # Baseline: agent scores ~50
        baseline_results = [
            TrialResult("mock", "test-task", "baseline", i, False, 10.0, 50.0 + i)
            for i in range(1, 4)
        ]
        # Treatment: agent scores ~80
        treatment_results = [
            TrialResult("mock", "test-task", "treatment", i, True, 8.0, 80.0 + i)
            for i in range(1, 4)
        ]

        eval_result = ContextEvalResult(
            context_file="CLAUDE.md",
            agents=["mock"],
            tasks=["test-task"],
            trials_per_condition=3,
            results=baseline_results + treatment_results,
        )

        data = render_context_eval_json(eval_result)
        agent = data["agents"][0]
        assert agent["delta"] > 20.0  # Significant improvement
        assert agent["treatment_mean_score"] > agent["baseline_mean_score"]
        assert agent["effect_size"] > 0.0  # Positive effect
        assert "improved" in data["summary"]["verdict"].lower()
