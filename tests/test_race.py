"""Tests for coderace race mode."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from coderace.cli import app
from coderace.commands.race import (
    RaceParticipant,
    RaceSummary,
    _build_live_panel,
    _resolve_verify_commands,
    _save_race_summary,
    _summary_record,
    _winner_announcement,
    run_race,
)
from coderace.types import AgentResult, Task

runner = CliRunner()


def _make_task(tmp_repo: Path, agents: list[str]) -> Task:
    return Task(
        name="race-task",
        description="Fix race task",
        repo=tmp_repo,
        test_command="echo ok",
        agents=agents,
        timeout=60,
    )


def test_run_race_first_verify_pass_wins(tmp_repo: Path) -> None:
    task = _make_task(tmp_repo, ["claude", "codex"])

    plans = {
        "claude": {"duration": 0.04, "verify_passed": True},
        "codex": {"duration": 0.20, "verify_passed": True},
    }

    def fake_runner(**kwargs):
        agent = kwargs["agent_name"]
        stop_event = kwargs["stop_event"]
        status_callback = kwargs["status_callback"]
        status_callback("coding")
        deadline = time.monotonic() + plans[agent]["duration"]
        while time.monotonic() < deadline:
            if stop_event.is_set():
                return (
                    AgentResult(
                        agent=agent,
                        exit_code=130,
                        stdout="",
                        stderr="stopped",
                        wall_time=0.01,
                        timed_out=False,
                    ),
                    0,
                    {"stopped": True, "total_wall_time": 0.01},
                )
            time.sleep(0.005)
        status_callback("testing")
        return (
            AgentResult(
                agent=agent,
                exit_code=0,
                stdout="",
                stderr="",
                wall_time=plans[agent]["duration"],
                timed_out=False,
            ),
            10,
            {
                "verify_passed": plans[agent]["verify_passed"],
                "verify_exit_codes": [0],
                "verify_outputs": ["ok"],
                "stopped": False,
                "total_wall_time": plans[agent]["duration"] + 0.01,
            },
        )

    with patch("coderace.commands.race._invoke_worktree_runner", side_effect=fake_runner):
        summary = run_race(
            task=task,
            base_ref="abc123",
            timeout=60,
            no_cost=True,
            verify_commands=["pytest verify.py -q"],
            poll_interval_seconds=0.01,
            refresh_interval_seconds=0.01,
            graceful_shutdown_seconds=0.10,
        )

    assert summary.winner_agent == "claude"
    winner = next(p for p in summary.participants if p.agent == "claude")
    assert winner.status == "winner"
    assert winner.verify_passed is True
    loser = next(p for p in summary.participants if p.agent == "codex")
    assert loser.status in {"stopped", "winner"}


def test_run_race_no_winner_when_all_agents_fail(tmp_repo: Path) -> None:
    task = _make_task(tmp_repo, ["claude", "codex"])

    def fake_runner(**kwargs):
        agent = kwargs["agent_name"]
        return (
            AgentResult(
                agent=agent,
                exit_code=1,
                stdout="",
                stderr="failed",
                wall_time=0.01,
                timed_out=False,
            ),
            0,
            {
                "verify_passed": False,
                "verify_exit_codes": [1],
                "verify_outputs": ["failed"],
                "stopped": False,
                "total_wall_time": 0.01,
            },
        )

    with patch("coderace.commands.race._invoke_worktree_runner", side_effect=fake_runner):
        summary = run_race(
            task=task,
            base_ref="abc123",
            timeout=60,
            no_cost=True,
            verify_commands=["pytest verify.py -q"],
            poll_interval_seconds=0.01,
            refresh_interval_seconds=0.01,
            graceful_shutdown_seconds=0.05,
        )

    assert summary.winner_agent is None
    assert all(p.status in {"failed", "failed_verify"} for p in summary.participants)


def test_run_race_cancels_remaining_agents_after_winner(tmp_repo: Path) -> None:
    task = _make_task(tmp_repo, ["claude", "codex", "aider"])

    plans = {
        "claude": {"duration": 0.03, "exit_code": 0},
        "codex": {"duration": 0.30, "exit_code": 0},
        "aider": {"duration": 0.30, "exit_code": 0},
    }

    def fake_runner(**kwargs):
        agent = kwargs["agent_name"]
        stop_event = kwargs["stop_event"]
        deadline = time.monotonic() + plans[agent]["duration"]
        while time.monotonic() < deadline:
            if stop_event.is_set():
                return (
                    AgentResult(
                        agent=agent,
                        exit_code=130,
                        stdout="",
                        stderr="stopped",
                        wall_time=0.02,
                        timed_out=False,
                    ),
                    0,
                    {"stopped": True, "total_wall_time": 0.02},
                )
            time.sleep(0.005)

        return (
            AgentResult(
                agent=agent,
                exit_code=plans[agent]["exit_code"],
                stdout="",
                stderr="",
                wall_time=plans[agent]["duration"],
                timed_out=False,
            ),
            3,
            {
                "verify_passed": True,
                "verify_exit_codes": [0],
                "verify_outputs": ["ok"],
                "stopped": False,
                "total_wall_time": plans[agent]["duration"],
            },
        )

    with patch("coderace.commands.race._invoke_worktree_runner", side_effect=fake_runner):
        summary = run_race(
            task=task,
            base_ref="abc123",
            timeout=60,
            no_cost=True,
            verify_commands=[],
            poll_interval_seconds=0.01,
            refresh_interval_seconds=0.01,
            graceful_shutdown_seconds=0.10,
        )

    assert summary.winner_agent == "claude"
    statuses = {p.agent: p.status for p in summary.participants}
    assert statuses["claude"] == "winner"
    assert "stopped" in {statuses["codex"], statuses["aider"]}


def test_run_race_without_verify_uses_first_clean_exit(tmp_repo: Path) -> None:
    task = _make_task(tmp_repo, ["claude", "codex"])

    plans = {"claude": 0.35, "codex": 0.02}

    def fake_runner(**kwargs):
        agent = kwargs["agent_name"]
        time.sleep(plans[agent])
        return (
            AgentResult(
                agent=agent,
                exit_code=0,
                stdout="",
                stderr="",
                wall_time=plans[agent],
                timed_out=False,
            ),
            1,
            {"stopped": False, "total_wall_time": plans[agent]},
        )

    with patch("coderace.commands.race._invoke_worktree_runner", side_effect=fake_runner):
        summary = run_race(
            task=task,
            base_ref="abc123",
            timeout=60,
            no_cost=True,
            verify_commands=[],
            poll_interval_seconds=0.01,
            refresh_interval_seconds=0.01,
            graceful_shutdown_seconds=0.40,
        )

    assert summary.winner_agent == "codex"


def test_run_race_all_timeouts_produces_no_winner(tmp_repo: Path) -> None:
    task = _make_task(tmp_repo, ["claude", "codex"])

    def fake_runner(**kwargs):
        agent = kwargs["agent_name"]
        return (
            AgentResult(
                agent=agent,
                exit_code=-1,
                stdout="",
                stderr="timed out",
                wall_time=0.02,
                timed_out=True,
            ),
            0,
            {"stopped": False, "total_wall_time": 0.02},
        )

    with patch("coderace.commands.race._invoke_worktree_runner", side_effect=fake_runner):
        summary = run_race(
            task=task,
            base_ref="abc123",
            timeout=60,
            no_cost=True,
            verify_commands=[],
            poll_interval_seconds=0.01,
            refresh_interval_seconds=0.01,
            graceful_shutdown_seconds=0.05,
        )

    assert summary.winner_agent is None
    assert all(p.status == "timed_out" for p in summary.participants)


def test_race_command_is_registered() -> None:
    result = runner.invoke(app, ["race", "--help"])
    assert result.exit_code == 0
    assert "--builtin" in result.output
    assert "--agent" in result.output


def test_race_cli_invocation_with_mock_runner(tmp_repo: Path, tmp_path: Path) -> None:
    task_yaml = tmp_path / "race-task.yaml"
    task_yaml.write_text(
        f"""name: race-task
description: test race
repo: {tmp_repo}
test_command: echo ok
agents:
  - claude
  - codex
""",
        encoding="utf-8",
    )

    summary = RaceSummary(
        race_id="rid",
        task_name="race-task",
        winner_agent="claude",
        winner_time=12.3,
        participants=[],
        timestamp="2026-03-03T00:00:00+00:00",
    )

    with patch("coderace.commands.race.has_uncommitted_changes", return_value=False), patch(
        "coderace.commands.race.get_current_ref", return_value="abc12345"
    ), patch("coderace.commands.race.run_race", return_value=summary), patch(
        "coderace.commands.race.prune_worktrees"
    ):
        result = runner.invoke(
            app,
            ["race", str(task_yaml), "--agent", "claude", "--agent", "codex", "--no-save"],
        )

    assert result.exit_code == 0
    assert "Winner:" in result.output
    assert "claude" in result.output


def test_run_race_emits_status_transitions_to_callback(tmp_repo: Path) -> None:
    task = _make_task(tmp_repo, ["claude"])
    snapshots: list[list[str]] = []

    def fake_runner(**kwargs):
        status_callback = kwargs["status_callback"]
        status_callback("coding")
        time.sleep(0.01)
        status_callback("testing")
        time.sleep(0.01)
        return (
            AgentResult(
                agent="claude",
                exit_code=0,
                stdout="",
                stderr="",
                wall_time=0.02,
                timed_out=False,
            ),
            1,
            {
                "verify_passed": True,
                "verify_exit_codes": [0],
                "verify_outputs": ["ok"],
                "stopped": False,
                "total_wall_time": 0.03,
            },
        )

    def update_callback(participants: list[RaceParticipant]) -> None:
        snapshots.append([p.status for p in participants])

    with patch("coderace.commands.race._invoke_worktree_runner", side_effect=fake_runner):
        summary = run_race(
            task=task,
            base_ref="abc123",
            timeout=60,
            no_cost=True,
            verify_commands=["pytest verify.py -q"],
            update_callback=update_callback,
            poll_interval_seconds=0.01,
            refresh_interval_seconds=0.01,
            graceful_shutdown_seconds=0.10,
        )

    assert summary.winner_agent == "claude"
    flattened = [status for snap in snapshots for status in snap]
    assert "coding" in flattened
    assert "testing" in flattened
    assert "winner" in flattened


def test_race_cli_updates_live_panel_with_mocked_live(tmp_repo: Path, tmp_path: Path) -> None:
    task_yaml = tmp_path / "race-live.yaml"
    task_yaml.write_text(
        f"""name: race-live
description: test live
repo: {tmp_repo}
test_command: echo ok
agents:
  - claude
  - codex
""",
        encoding="utf-8",
    )

    summary = RaceSummary(
        race_id="rid",
        task_name="race-live",
        winner_agent="claude",
        winner_time=0.5,
        participants=[
            RaceParticipant(
                agent="claude",
                status="winner",
                started_at=0.0,
                finished_at=0.5,
                total_time=0.5,
                result=AgentResult(
                    agent="claude",
                    exit_code=0,
                    stdout="",
                    stderr="",
                    wall_time=0.5,
                    timed_out=False,
                ),
            ),
            RaceParticipant(
                agent="codex",
                status="stopped",
                started_at=0.0,
                finished_at=0.8,
                total_time=0.8,
                result=AgentResult(
                    agent="codex",
                    exit_code=130,
                    stdout="",
                    stderr="stopped",
                    wall_time=0.8,
                    timed_out=False,
                ),
            ),
        ],
        timestamp="2026-03-03T00:00:00+00:00",
    )

    live_updates: list[object] = []

    class FakeLive:
        def __init__(self, *args, **kwargs):
            self.initial = args[0] if args else None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, renderable):
            live_updates.append(renderable)

    def fake_run_race(**kwargs):
        update = kwargs["update_callback"]
        update(
            [
                RaceParticipant(agent="claude", status="coding", started_at=0.0),
                RaceParticipant(agent="codex", status="testing", started_at=0.0),
            ]
        )
        update(
            [
                RaceParticipant(agent="claude", status="winner", started_at=0.0, total_time=0.5),
                RaceParticipant(agent="codex", status="stopped", started_at=0.0, total_time=0.8),
            ]
        )
        return summary

    with patch("coderace.commands.race.has_uncommitted_changes", return_value=False), patch(
        "coderace.commands.race.get_current_ref", return_value="abc12345"
    ), patch("coderace.commands.race.prune_worktrees"), patch(
        "coderace.commands.race.Live", FakeLive
    ), patch("coderace.commands.race.run_race", side_effect=fake_run_race):
        result = runner.invoke(app, ["race", str(task_yaml), "--no-save"])

    assert result.exit_code == 0
    assert "Winner:" in result.output
    assert "Runner-up:" in result.output
    assert len(live_updates) >= 2


def test_summary_record_contains_winner_and_participant_fields() -> None:
    summary = RaceSummary(
        race_id="race-1",
        task_name="task-a",
        winner_agent="claude",
        winner_time=1.23,
        participants=[
            RaceParticipant(
                agent="claude",
                status="winner",
                total_time=1.23,
                lines_changed=7,
                result=AgentResult(
                    agent="claude",
                    exit_code=0,
                    stdout="ok",
                    stderr="",
                    wall_time=1.23,
                    timed_out=False,
                ),
                verify_passed=True,
            ),
            RaceParticipant(
                agent="codex",
                status="stopped",
                total_time=1.50,
                lines_changed=2,
                result=AgentResult(
                    agent="codex",
                    exit_code=130,
                    stdout="",
                    stderr="stopped",
                    wall_time=1.50,
                    timed_out=False,
                ),
                verify_passed=None,
            ),
        ],
        timestamp="2026-03-03T00:00:00+00:00",
    )

    record = _summary_record(summary)
    assert record["winner_agent"] == "claude"
    assert record["winner_time"] == 1.23
    assert len(record["participant_results"]) == 2
    first = record["participant_results"][0]
    assert first["agent"] == "claude"
    assert first["exit_code"] == 0
    assert first["wall_time"] == 1.23


def test_save_race_summary_appends_records(tmp_path: Path) -> None:
    output = tmp_path / ".coderace" / "race-results.json"
    s1 = RaceSummary(
        race_id="r1",
        task_name="t",
        winner_agent="claude",
        winner_time=1.0,
        participants=[],
        timestamp="2026-03-03T00:00:00+00:00",
    )
    s2 = RaceSummary(
        race_id="r2",
        task_name="t",
        winner_agent=None,
        winner_time=None,
        participants=[],
        timestamp="2026-03-03T00:01:00+00:00",
    )
    _save_race_summary(s1, output)
    _save_race_summary(s2, output)
    data = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert [item["race_id"] for item in data] == ["r1", "r2"]


def test_race_cli_no_save_skips_race_results_file(tmp_repo: Path, tmp_path: Path) -> None:
    task_yaml = tmp_path / "race-nosave.yaml"
    task_yaml.write_text(
        f"""name: race-nosave
description: test no-save
repo: {tmp_repo}
test_command: echo ok
agents:
  - claude
""",
        encoding="utf-8",
    )

    summary = RaceSummary(
        race_id="rid",
        task_name="race-nosave",
        winner_agent="claude",
        winner_time=0.5,
        participants=[],
        timestamp="2026-03-03T00:00:00+00:00",
    )

    class FakeLive:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, renderable):
            return None

    with patch("coderace.commands.race.has_uncommitted_changes", return_value=False), patch(
        "coderace.commands.race.get_current_ref", return_value="abc12345"
    ), patch("coderace.commands.race.prune_worktrees"), patch(
        "coderace.commands.race.Live", FakeLive
    ), patch("coderace.commands.race.run_race", return_value=summary):
        result = runner.invoke(app, ["race", str(task_yaml), "--no-save"])

    assert result.exit_code == 0
    assert not (tmp_path / ".coderace" / "race-results.json").exists()


def test_race_cli_saves_race_results_file(tmp_repo: Path, tmp_path: Path) -> None:
    task_yaml = tmp_path / "race-save.yaml"
    task_yaml.write_text(
        f"""name: race-save
description: test save
repo: {tmp_repo}
test_command: echo ok
agents:
  - claude
""",
        encoding="utf-8",
    )

    summary = RaceSummary(
        race_id="rid",
        task_name="race-save",
        winner_agent="claude",
        winner_time=0.5,
        participants=[
            RaceParticipant(
                agent="claude",
                status="winner",
                total_time=0.5,
                result=AgentResult(
                    agent="claude",
                    exit_code=0,
                    stdout="",
                    stderr="",
                    wall_time=0.5,
                    timed_out=False,
                ),
            )
        ],
        timestamp="2026-03-03T00:00:00+00:00",
    )

    class FakeLive:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, renderable):
            return None

    with patch("coderace.commands.race.has_uncommitted_changes", return_value=False), patch(
        "coderace.commands.race.get_current_ref", return_value="abc12345"
    ), patch("coderace.commands.race.prune_worktrees"), patch(
        "coderace.commands.race.Live", FakeLive
    ), patch("coderace.commands.race.run_race", return_value=summary):
        result = runner.invoke(app, ["race", str(task_yaml)])

    assert result.exit_code == 0
    output = tmp_path / ".coderace" / "race-results.json"
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data[-1]["winner_agent"] == "claude"


def test_resolve_verify_commands_from_verify_command_field(tmp_path: Path) -> None:
    task_yaml = tmp_path / "task.yaml"
    task_yaml.write_text(
        """name: t
description: d
repo: .
test_command: echo ok
verify_command: pytest verify_contract.py -q
agents:
  - claude
""",
        encoding="utf-8",
    )
    task = Task(
        name="t",
        description="d",
        repo=tmp_path,
        test_command="echo ok",
        agents=["claude"],
        verify_command="pytest verify_contract.py -q",
    )
    commands = _resolve_verify_commands(task_yaml, task)
    assert commands == ["pytest verify_contract.py -q"]


def test_resolve_verify_commands_from_verify_string_section(tmp_path: Path) -> None:
    task_yaml = tmp_path / "task.yaml"
    task_yaml.write_text(
        """name: t
description: d
repo: .
test_command: echo ok
verify: pytest verify_a.py -q
agents:
  - claude
""",
        encoding="utf-8",
    )
    task = Task(
        name="t",
        description="d",
        repo=tmp_path,
        test_command="echo ok",
        agents=["claude"],
    )
    commands = _resolve_verify_commands(task_yaml, task)
    assert commands == ["pytest verify_a.py -q"]


def test_resolve_verify_commands_from_verify_list_dedupes(tmp_path: Path) -> None:
    task_yaml = tmp_path / "task.yaml"
    task_yaml.write_text(
        """name: t
description: d
repo: .
test_command: echo ok
verify:
  - pytest verify_a.py -q
  - pytest verify_b.py -q
agents:
  - claude
""",
        encoding="utf-8",
    )
    task = Task(
        name="t",
        description="d",
        repo=tmp_path,
        test_command="echo ok",
        agents=["claude"],
        verify_command="pytest verify_a.py -q",
    )
    commands = _resolve_verify_commands(task_yaml, task)
    assert commands == ["pytest verify_a.py -q", "pytest verify_b.py -q"]


def test_run_race_single_agent_still_works(tmp_repo: Path) -> None:
    task = _make_task(tmp_repo, ["claude"])

    def fake_runner(**kwargs):
        return (
            AgentResult(
                agent="claude",
                exit_code=0,
                stdout="",
                stderr="",
                wall_time=0.01,
                timed_out=False,
            ),
            1,
            {"stopped": False, "total_wall_time": 0.01},
        )

    with patch("coderace.commands.race._invoke_worktree_runner", side_effect=fake_runner):
        summary = run_race(
            task=task,
            base_ref="abc123",
            timeout=60,
            no_cost=True,
            verify_commands=[],
            poll_interval_seconds=0.01,
            refresh_interval_seconds=0.01,
            graceful_shutdown_seconds=0.05,
        )

    assert summary.winner_agent == "claude"
    assert summary.participants[0].status == "winner"


def test_winner_announcement_no_winner_message() -> None:
    summary = RaceSummary(
        race_id="rid",
        task_name="t",
        winner_agent=None,
        winner_time=None,
        participants=[],
        timestamp="2026-03-03T00:00:00+00:00",
    )
    lines = _winner_announcement(summary, verify_commands=[])
    assert lines == ["No winner: all agents failed or timed out."]


def test_winner_announcement_includes_runner_up_delta() -> None:
    summary = RaceSummary(
        race_id="rid",
        task_name="t",
        winner_agent="claude",
        winner_time=1.0,
        participants=[
            RaceParticipant(
                agent="claude",
                status="winner",
                finished_at=1.0,
                total_time=1.0,
                result=AgentResult(
                    agent="claude",
                    exit_code=0,
                    stdout="",
                    stderr="",
                    wall_time=1.0,
                    timed_out=False,
                ),
            ),
            RaceParticipant(
                agent="codex",
                status="stopped",
                finished_at=1.5,
                total_time=1.5,
                result=AgentResult(
                    agent="codex",
                    exit_code=0,
                    stdout="",
                    stderr="",
                    wall_time=1.5,
                    timed_out=False,
                ),
            ),
        ],
        timestamp="2026-03-03T00:00:00+00:00",
    )
    lines = _winner_announcement(summary, verify_commands=["pytest verify.py -q"])
    assert lines[0].startswith("🏆 Winner: claude")
    assert lines[1] == "Runner-up: codex - finished 0:00 later"


def test_build_live_panel_contains_core_labels() -> None:
    panel = _build_live_panel(
        "task-x",
        [
            RaceParticipant(agent="claude", status="coding", started_at=0.0),
            RaceParticipant(agent="codex", status="testing", started_at=0.0),
        ],
    )
    from rich.console import Console

    console = Console(record=True, no_color=True)
    console.print(panel)
    out = console.export_text()
    assert "coderace race - task-x" in out
    assert "Press Ctrl+C to abort" in out
    assert "coding" in out
    assert "testing" in out


def test_race_cli_handles_ctrl_c_and_prunes_worktrees(tmp_repo: Path, tmp_path: Path) -> None:
    task_yaml = tmp_path / "race-interrupt.yaml"
    task_yaml.write_text(
        f"""name: race-interrupt
description: test interrupt
repo: {tmp_repo}
test_command: echo ok
agents:
  - claude
""",
        encoding="utf-8",
    )

    class FakeLive:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, renderable):
            return None

    with patch("coderace.commands.race.has_uncommitted_changes", return_value=False), patch(
        "coderace.commands.race.get_current_ref", return_value="abc12345"
    ), patch("coderace.commands.race.Live", FakeLive), patch(
        "coderace.commands.race.run_race", side_effect=KeyboardInterrupt()
    ), patch("coderace.commands.race.prune_worktrees") as prune_mock:
        result = runner.invoke(app, ["race", str(task_yaml), "--no-save"])

    assert result.exit_code == 130
    assert "Race aborted by user." in result.output
    prune_mock.assert_called_once()
