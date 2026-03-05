"""Claude Code adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_claude_cost

DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"


class ClaudeAdapter(BaseAdapter):
    """Adapter for Claude Code CLI."""

    name = "claude"

    def build_command(self, task_description: str, model: Optional[str] = None) -> list[str]:
        cmd = [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]
        effective_model = model or self.model
        if effective_model:
            cmd += ["--model", effective_model]
        cmd += ["-p", task_description]
        return cmd

    def parse_cost(
        self,
        stdout: str,
        stderr: str,
        model_name: str = "",
        custom_pricing: dict[str, tuple[float, float]] | None = None,
    ) -> Optional[CostResult]:
        """Parse cost data from Claude Code output."""
        effective_model = model_name or self.model or DEFAULT_CLAUDE_MODEL
        return parse_claude_cost(stdout, stderr, effective_model, custom_pricing)
