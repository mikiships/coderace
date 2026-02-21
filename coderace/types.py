"""Shared types for coderace."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Task:
    """A task definition loaded from YAML."""

    name: str
    description: str
    repo: Path
    test_command: str
    agents: list[str]
    lint_command: str | None = None
    timeout: int = 300

    def validate(self) -> list[str]:
        """Return list of validation errors, empty if valid."""
        errors: list[str] = []
        if not self.name:
            errors.append("Task name is required")
        if not self.description:
            errors.append("Task description is required")
        if not self.test_command:
            errors.append("test_command is required")
        if not self.agents:
            errors.append("At least one agent is required")
        known = {"claude", "codex", "aider", "gemini"}
        for agent in self.agents:
            if agent not in known:
                errors.append(f"Unknown agent: {agent!r} (known: {', '.join(sorted(known))})")
        if self.timeout < 1:
            errors.append("timeout must be positive")
        return errors


@dataclass
class AgentResult:
    """Raw result from running an agent on a task."""

    agent: str
    exit_code: int
    stdout: str
    stderr: str
    wall_time: float
    timed_out: bool = False


@dataclass
class ScoreBreakdown:
    """Per-metric scores before weighting."""

    tests_pass: bool = False
    exit_clean: bool = False
    lint_clean: bool = False
    wall_time: float = 0.0
    lines_changed: int = 0


@dataclass
class Score:
    """Final computed score for an agent run."""

    agent: str
    composite: float
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    tests_output: str = ""
    lint_output: str = ""
    diff_stat: str = ""
