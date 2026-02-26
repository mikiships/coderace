"""Claude Code adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_claude_cost


class ClaudeAdapter(BaseAdapter):
    """Adapter for Claude Code CLI."""

    name = "claude"

    def build_command(self, task_description: str) -> list[str]:
        return [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
            "-p",
            task_description,
        ]

    def parse_cost(
        self,
        stdout: str,
        stderr: str,
        model_name: str = "claude-sonnet-4-6",
        custom_pricing: dict[str, tuple[float, float]] | None = None,
    ) -> Optional[CostResult]:
        """Parse cost data from Claude Code output."""
        return parse_claude_cost(stdout, stderr, model_name, custom_pricing)
