"""CLI command: coderace race"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Event, Lock
from time import monotonic, sleep
from typing import Any, Callable, Optional
from uuid import uuid4

import typer
import yaml
from rich.console import Group
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from coderace.adapters import ADAPTERS, parse_agent_spec
from coderace.git_ops import (
    branch_name_for,
    get_current_ref,
    has_uncommitted_changes,
    prune_worktrees,
)
from coderace.task import load_task
from coderace.types import AgentResult, Task

app = typer.Typer(
    help="Run agents in race mode (first to pass wins).",
    context_settings={"allow_interspersed_args": True},
)
console = Console()

POLL_INTERVAL_SECONDS = 5.0
REFRESH_INTERVAL_SECONDS = 1.0
GRACEFUL_SHUTDOWN_SECONDS = 10.0

STATUS_CODING = "coding"
STATUS_TESTING = "testing"
STATUS_WINNER = "winner"
STATUS_FAILED = "failed"
STATUS_TIMED_OUT = "timed_out"
STATUS_STOPPED = "stopped"
STATUS_FAILED_VERIFY = "failed_verify"


@dataclass
class RaceParticipant:
    """Runtime and final state for a participant in race mode."""

    agent: str
    status: str = STATUS_CODING
    started_at: float = 0.0
    finished_at: float | None = None
    total_time: float = 0.0
    lines_changed: int = 0
    result: AgentResult | None = None
    verify_passed: bool | None = None
    verify_exit_codes: list[int] = field(default_factory=list)
    verify_outputs: list[str] = field(default_factory=list)


@dataclass
class RaceSummary:
    """Race outcome payload."""

    race_id: str
    task_name: str
    winner_agent: str | None
    winner_time: float | None
    participants: list[RaceParticipant]
    timestamp: str


def _invoke_worktree_runner(**kwargs: Any) -> Any:
    """Resolve late import to avoid circular imports with coderace.cli."""
    from coderace.cli import _run_agent_worktree

    return _run_agent_worktree(**kwargs)


def _resolve_task_file(task_file: Path | None, builtin: str | None) -> Path:
    if builtin and task_file:
        console.print("[red]Cannot use both --builtin and a task file path.[/red]")
        raise typer.Exit(1)

    if builtin:
        from coderace.builtins import get_builtin_path

        try:
            return get_builtin_path(builtin)
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

    if task_file is None:
        console.print("[red]Provide a task file path or use --builtin <name>.[/red]")
        raise typer.Exit(1)

    return task_file


def _resolve_verify_commands(task_file: Path, task: Task) -> list[str]:
    commands: list[str] = []

    if task.verify_command:
        commands.append(task.verify_command.strip())

    try:
        data = yaml.safe_load(task_file.read_text(encoding="utf-8"))
    except Exception:
        data = None

    if isinstance(data, dict):
        verify_section = data.get("verify")
        if isinstance(verify_section, str) and verify_section.strip():
            commands.append(verify_section.strip())
        elif isinstance(verify_section, list):
            for entry in verify_section:
                if isinstance(entry, str) and entry.strip():
                    commands.append(entry.strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for cmd in commands:
        if cmd not in seen:
            deduped.append(cmd)
            seen.add(cmd)
    return deduped


def _format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    if minutes:
        return f"{minutes}:{secs:02d}"
    return f"0:{secs:02d}"


def _format_clock(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def _status_label(participant: RaceParticipant, live_mode: bool = False) -> str:
    if participant.status == STATUS_CODING:
        return "🔨 coding..."
    if participant.status == STATUS_TESTING:
        return "🧪 testing..."
    if participant.status == STATUS_WINNER:
        winner_time = _format_clock(participant.total_time) if live_mode else _format_duration(
            participant.total_time
        )
        return f"✅ WINNER! ({winner_time})"
    if participant.status == STATUS_TIMED_OUT:
        return "⏰ timed out"
    if participant.status == STATUS_STOPPED:
        return "🛑 stopped"
    if participant.status == STATUS_FAILED_VERIFY:
        return "❌ failed (verify)"
    if participant.status == STATUS_FAILED and participant.result is not None:
        return f"❌ failed (exit {participant.result.exit_code})"
    if participant.status == STATUS_FAILED:
        return "❌ failed"
    return "🔨 coding..."


def _participant_table(summary: RaceSummary) -> Table:
    table = Table(title=f"coderace race — {summary.task_name}", show_lines=True)
    table.add_column("Agent", style="cyan")
    table.add_column("Status")
    table.add_column("Time", justify="right")
    for p in summary.participants:
        table.add_row(
            p.agent,
            _status_label(p, live_mode=False),
            _format_duration(p.total_time),
        )
    return table


def _build_live_panel(task_name: str, participants: list[RaceParticipant]) -> Panel:
    table = Table(show_lines=False, pad_edge=False)
    table.add_column("Agent", style="cyan")
    table.add_column("Status")
    table.add_column("Time", justify="right")
    now = monotonic()
    for participant in participants:
        elapsed = (
            participant.total_time
            if participant.finished_at is not None
            else max(0.0, now - participant.started_at)
        )
        table.add_row(
            participant.agent,
            _status_label(participant, live_mode=True),
            _format_clock(elapsed),
        )

    header = Text(f"🏁 coderace race - {task_name}", style="bold")
    subhead = Text(f"Running {len(participants)} agents in parallel...", style="dim")
    footer = Text("Press Ctrl+C to abort", style="dim")
    return Panel(Group(header, subhead, Text(""), table, Text(""), footer), border_style="cyan")


def _winner_announcement(summary: RaceSummary, verify_commands: list[str]) -> list[str]:
    if summary.winner_agent is None or summary.winner_time is None:
        return ["No winner: all agents failed or timed out."]

    reason = (
        "first to pass verification"
        if verify_commands
        else "first clean exit"
    )
    lines = [
        f"🏆 Winner: {summary.winner_agent} - completed in {_format_duration(summary.winner_time)} ({reason})"
    ]

    winner = next((p for p in summary.participants if p.agent == summary.winner_agent), None)
    if winner is None:
        return lines

    valid_runner_ups = [
        p
        for p in summary.participants
        if p.agent != summary.winner_agent
        and p.finished_at is not None
        and p.result is not None
        and not p.result.timed_out
    ]
    if not valid_runner_ups:
        return lines

    runner_up = min(valid_runner_ups, key=lambda p: p.total_time)
    delta = max(0.0, runner_up.total_time - winner.total_time)
    lines.append(
        f"Runner-up: {runner_up.agent} - finished {_format_duration(delta)} later"
    )
    return lines


def _participant_record(participant: RaceParticipant) -> dict[str, Any]:
    result = participant.result
    record: dict[str, Any] = {
        "agent": participant.agent,
        "status": participant.status,
        "exit_code": result.exit_code if result is not None else None,
        "wall_time": participant.total_time,
        "timed_out": result.timed_out if result is not None else False,
        "lines_changed": participant.lines_changed,
        "verify_passed": participant.verify_passed,
    }
    if result is not None and result.cost_result is not None:
        record["cost_usd"] = result.cost_result.estimated_cost_usd
        record["model_name"] = result.cost_result.model_name
    return record


def _summary_record(summary: RaceSummary) -> dict[str, Any]:
    return {
        "race_id": summary.race_id,
        "task_name": summary.task_name,
        "winner_agent": summary.winner_agent,
        "winner_time": summary.winner_time,
        "participant_results": [
            _participant_record(participant)
            for participant in summary.participants
        ],
        "timestamp": summary.timestamp,
    }


def _save_race_summary(summary: RaceSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload: list[dict[str, Any]]
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
            payload = existing if isinstance(existing, list) else []
        except Exception:
            payload = []
    else:
        payload = []

    payload.append(_summary_record(summary))
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_race(
    task: Task,
    base_ref: str,
    timeout: int,
    no_cost: bool,
    verify_commands: list[str],
    update_callback: Callable[[list[RaceParticipant]], None] | None = None,
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
    refresh_interval_seconds: float = REFRESH_INTERVAL_SECONDS,
    graceful_shutdown_seconds: float = GRACEFUL_SHUTDOWN_SECONDS,
) -> RaceSummary:
    """Execute race mode and return winner + participant outcomes."""
    stop_event = Event()
    status_lock = Lock()
    participants: dict[str, RaceParticipant] = {}

    def _ordered_snapshot() -> list[RaceParticipant]:
        return [replace(participants[name]) for name in task.agents]

    def _emit_update() -> None:
        if update_callback is None:
            return
        update_callback(_ordered_snapshot())

    def _set_stage(agent: str, stage: str) -> None:
        changed = False
        with status_lock:
            participant = participants.get(agent)
            if participant is None:
                return
            if participant.finished_at is not None:
                return
            if stage == STATUS_TESTING:
                if participant.status != STATUS_TESTING:
                    participant.status = STATUS_TESTING
                    changed = True
            elif stage == STATUS_CODING:
                if participant.status != STATUS_CODING:
                    participant.status = STATUS_CODING
                    changed = True
        if changed:
            _emit_update()

    for agent_name in task.agents:
        participants[agent_name] = RaceParticipant(
            agent=agent_name,
            status=STATUS_CODING,
            started_at=monotonic(),
        )
    _emit_update()

    futures: dict[Future[Any], str] = {}
    processed: set[Future[Any]] = set()
    winner_agent: str | None = None
    winner_time: float | None = None
    winner_found_at: float | None = None

    executor = ThreadPoolExecutor(max_workers=max(1, len(task.agents)))
    try:
        for agent_name in task.agents:
            branch = branch_name_for(task.name, agent_name)
            future = executor.submit(
                _invoke_worktree_runner,
                agent_name=agent_name,
                task_description=task.description,
                repo=task.repo,
                branch=branch,
                base_ref=base_ref,
                timeout=timeout,
                no_cost=no_cost,
                custom_pricing=task.pricing,
                stop_event=stop_event,
                status_callback=lambda stage, a=agent_name: _set_stage(a, stage),
                verify_commands=verify_commands,
                verify_files=task.verify_files,
                return_metadata=True,
            )
            futures[future] = agent_name

        last_poll = monotonic() - poll_interval_seconds
        last_refresh = monotonic() - refresh_interval_seconds
        while True:
            now = monotonic()

            if now - last_poll >= poll_interval_seconds:
                last_poll = now
                candidates: list[RaceParticipant] = []
                for future, agent_name in futures.items():
                    if future in processed or not future.done():
                        continue

                    participant = participants[agent_name]
                    try:
                        raw = future.result()
                    except Exception:
                        raw = (None, 0, {})

                    if (
                        isinstance(raw, tuple)
                        and len(raw) == 3
                        and isinstance(raw[2], dict)
                    ):
                        result = raw[0]
                        lines_changed = int(raw[1])
                        metadata = raw[2]
                    elif isinstance(raw, tuple) and len(raw) >= 2:
                        result = raw[0]
                        lines_changed = int(raw[1])
                        metadata = {}
                    else:
                        result = None
                        lines_changed = 0
                        metadata = {}

                    total_time = float(
                        metadata.get(
                            "total_wall_time",
                            result.wall_time if isinstance(result, AgentResult) else 0.0,
                        )
                    )
                    participant.result = result if isinstance(result, AgentResult) else None
                    participant.lines_changed = lines_changed
                    participant.verify_passed = (
                        bool(metadata.get("verify_passed"))
                        if metadata.get("verify_passed") is not None
                        else None
                    )
                    participant.verify_exit_codes = [
                        int(x) for x in metadata.get("verify_exit_codes", [])
                    ]
                    participant.verify_outputs = [
                        str(x) for x in metadata.get("verify_outputs", [])
                    ]
                    participant.total_time = max(total_time, 0.0)
                    participant.finished_at = participant.started_at + participant.total_time

                    stopped = bool(metadata.get("stopped", False))
                    if stopped:
                        participant.status = STATUS_STOPPED
                    elif participant.result is None:
                        participant.status = STATUS_FAILED
                    elif participant.result.timed_out:
                        participant.status = STATUS_TIMED_OUT
                    elif participant.result.exit_code != 0:
                        participant.status = STATUS_FAILED
                    elif verify_commands and participant.verify_passed is not True:
                        participant.status = STATUS_FAILED_VERIFY
                    else:
                        if winner_agent is None:
                            participant.status = STATUS_CODING
                            candidates.append(participant)
                        else:
                            participant.status = STATUS_STOPPED

                    processed.add(future)

                if winner_agent is None and candidates:
                    candidates.sort(
                        key=lambda p: (
                            p.finished_at if p.finished_at is not None else float("inf")
                        )
                    )
                    winner = candidates[0]
                    winner.status = STATUS_WINNER
                    for candidate in candidates[1:]:
                        if candidate.status != STATUS_WINNER:
                            candidate.status = STATUS_STOPPED
                    winner_agent = winner.agent
                    winner_time = winner.total_time
                    winner_found_at = monotonic()
                    stop_event.set()
                _emit_update()

            if now - last_refresh >= refresh_interval_seconds:
                last_refresh = now
                _emit_update()

            if winner_agent is not None and winner_found_at is not None:
                if len(processed) == len(futures):
                    break
                if monotonic() - winner_found_at >= graceful_shutdown_seconds:
                    stop_event.set()
                    for future, agent_name in futures.items():
                        if future in processed:
                            continue
                        future.cancel()
                        participant = participants[agent_name]
                        elapsed = monotonic() - participant.started_at
                        participant.total_time = max(elapsed, 0.0)
                        participant.finished_at = participant.started_at + participant.total_time
                        participant.status = STATUS_STOPPED
                        participant.result = AgentResult(
                            agent=agent_name,
                            exit_code=130,
                            stdout="",
                            stderr="Stopped due to race winner.",
                            wall_time=participant.total_time,
                            timed_out=False,
                        )
                        processed.add(future)
                    _emit_update()
                    break

            if winner_agent is None and len(processed) == len(futures):
                break

            sleep(max(0.05, refresh_interval_seconds / 4))
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    _emit_update()

    ordered_participants = [participants[name] for name in task.agents]
    return RaceSummary(
        race_id=str(uuid4()),
        task_name=task.name,
        winner_agent=winner_agent,
        winner_time=winner_time,
        participants=ordered_participants,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.callback(invoke_without_command=True)
def race_main(
    ctx: typer.Context,
    task_file: Path = typer.Argument(None, help="Path to task YAML file"),
    agents: list[str] | None = typer.Option(
        None,
        "--agent",
        "-a",
        help="Override agent list",
    ),
    timeout: Optional[int] = typer.Option(
        None,
        "--timeout",
        help="Per-agent timeout override (seconds)",
    ),
    no_cost: bool = typer.Option(
        False,
        "--no-cost",
        help="Disable cost tracking",
    ),
    no_save: bool = typer.Option(
        False,
        "--no-save",
        help="Skip saving race results",
    ),
    builtin: str | None = typer.Option(
        None,
        "--builtin",
        help="Use a built-in task instead of a file",
    ),
) -> None:
    """Run agents in race mode and stop at the first passing result."""
    if ctx.invoked_subcommand is not None:
        return

    resolved_task_file = _resolve_task_file(task_file, builtin)
    task = load_task(resolved_task_file)
    if agents:
        task.agents = agents
    if timeout is not None:
        task.timeout = timeout

    repo = task.repo
    if not repo.exists():
        console.print(f"[red]Repo not found:[/red] {repo}")
        raise typer.Exit(1)

    if has_uncommitted_changes(repo):
        console.print("[red]Repo has uncommitted changes. Commit or stash first.[/red]")
        raise typer.Exit(1)

    valid_agents = [a for a in task.agents if parse_agent_spec(a)[0] in ADAPTERS]
    invalid_agents = set(task.agents) - set(valid_agents)
    for name in invalid_agents:
        console.print(f"[red]Unknown agent: {name}[/red]")
    if not valid_agents:
        console.print("[red]No valid agents to run.[/red]")
        raise typer.Exit(1)
    task.agents = valid_agents

    verify_commands = _resolve_verify_commands(resolved_task_file, task)
    base_ref = get_current_ref(repo)

    console.print(f"[dim]Base ref: {base_ref[:8]} | Mode: race[/dim]")
    console.print(f"[dim]Task: {task.name}[/dim]")
    console.print(f"[dim]Agents: {', '.join(task.agents)}[/dim]")
    console.print(
        f"[dim]Verify commands: {len(verify_commands)} | Timeout: {task.timeout}s[/dim]"
    )
    console.print()

    summary: RaceSummary | None = None
    try:
        with Live(
            _build_live_panel(task.name, [RaceParticipant(agent=a, started_at=monotonic()) for a in task.agents]),
            console=console,
            refresh_per_second=4,
            transient=True,
        ) as live:
            summary = run_race(
                task=task,
                base_ref=base_ref,
                timeout=task.timeout,
                no_cost=no_cost,
                verify_commands=verify_commands,
                update_callback=lambda participants: live.update(
                    _build_live_panel(task.name, participants)
                ),
            )
    except KeyboardInterrupt:
        console.print("[yellow]Race aborted by user.[/yellow]")
        raise typer.Exit(130)
    finally:
        prune_worktrees(repo)

    if summary is None:
        return

    for line in _winner_announcement(summary, verify_commands):
        style = "yellow" if line.startswith("No winner") else "bold green"
        console.print(f"[{style}]{line}[/{style}]")

    if no_save:
        return
    output_path = resolved_task_file.parent / ".coderace" / "race-results.json"
    _save_race_summary(summary, output_path)
    console.print(f"[dim]Race results saved to {output_path}[/dim]")
