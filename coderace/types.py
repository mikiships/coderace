"""Shared types for coderace."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from coderace.cost import CostResult

DEFAULT_WEIGHTS: dict[str, float] = {
    "tests_pass": 0.40,
    "exit_clean": 0.20,
    "lint_clean": 0.15,
    "wall_time": 0.15,
    "lines_changed": 0.10,
}

VALID_WEIGHT_KEYS = frozenset(DEFAULT_WEIGHTS.keys())

# Aliases for YAML convenience (short name -> canonical name)
WEIGHT_ALIASES: dict[str, str] = {
    "tests": "tests_pass",
    "exit": "exit_clean",
    "lint": "lint_clean",
    "time": "wall_time",
    "lines": "lines_changed",
}


def normalize_weights(raw: dict[str, float]) -> dict[str, float]:
    """Normalize scoring weights: resolve aliases, validate keys, scale to sum=1.0."""
    resolved: dict[str, float] = {}
    for key, value in raw.items():
        canonical = WEIGHT_ALIASES.get(key, key)
        if canonical not in VALID_WEIGHT_KEYS:
            raise ValueError(
                f"Unknown scoring key: {key!r} "
                f"(valid: {', '.join(sorted(VALID_WEIGHT_KEYS | set(WEIGHT_ALIASES.keys())))})"
            )
        if value < 0:
            raise ValueError(f"Scoring weight for {key!r} must be >= 0, got {value}")
        resolved[canonical] = value

    # Fill missing keys with 0
    for key in VALID_WEIGHT_KEYS:
        resolved.setdefault(key, 0.0)

    total = sum(resolved.values())
    if total == 0:
        raise ValueError("Scoring weights must not all be zero")

    # Normalize to sum=1.0
    return {k: v / total for k, v in resolved.items()}


@dataclass
class Task:
    """A task definition loaded from YAML."""

    name: str
    description: str
    repo: Path
    test_command: str
    agents: list[str]
    lint_command: str | None = None
    verify_command: str | None = None
    verify_files: dict[str, str] | None = None
    timeout: int = 300
    scoring: dict[str, float] | None = None
    # Per-agent or per-model pricing overrides: name -> (input_usd_per_1m, output_usd_per_1m)
    pricing: dict[str, tuple[float, float]] | None = None

    def validate(self) -> list[str]:
        """Return list of validation errors, empty if valid."""
        errors: list[str] = []
        if not self.name:
            errors.append("Task name is required")
        if not self.description:
            errors.append("Task description is required")
        if not self.test_command:
            errors.append("test_command is required")
        if self.verify_command is not None and not self.verify_command.strip():
            errors.append("verify_command must not be empty")
        if self.verify_files is not None:
            for rel_path, content in self.verify_files.items():
                if not isinstance(rel_path, str) or not rel_path:
                    errors.append("verify_files keys must be non-empty strings")
                    break
                if Path(rel_path).is_absolute():
                    errors.append(f"verify_files path must be relative: {rel_path!r}")
                    break
                if not isinstance(content, str):
                    errors.append(f"verify_files[{rel_path!r}] content must be a string")
                    break
        if not self.agents:
            errors.append("At least one agent is required")
        known = {"claude", "codex", "aider", "gemini", "opencode"}
        for agent in self.agents:
            if agent not in known:
                errors.append(f"Unknown agent: {agent!r} (known: {', '.join(sorted(known))})")
        if self.timeout < 1:
            errors.append("timeout must be positive")
        if self.scoring is not None:
            try:
                normalize_weights(self.scoring)
            except ValueError as e:
                errors.append(str(e))
        return errors

    def get_weights(self) -> dict[str, float]:
        """Return normalized scoring weights (custom or defaults)."""
        if self.scoring is not None:
            return normalize_weights(self.scoring)
        return dict(DEFAULT_WEIGHTS)


@dataclass
class AgentResult:
    """Raw result from running an agent on a task."""

    agent: str
    exit_code: int
    stdout: str
    stderr: str
    wall_time: float
    timed_out: bool = False
    cost_result: Optional[CostResult] = None


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
    verify_passed: bool = False
    verify_score: float = 0.0
    verify_output: str = ""
    lint_output: str = ""
    diff_stat: str = ""
    cost_result: Optional[CostResult] = None
