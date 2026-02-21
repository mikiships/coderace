"""Claude Code adapter."""

from __future__ import annotations

from coderace.adapters.base import BaseAdapter


class ClaudeAdapter(BaseAdapter):
    """Adapter for Claude Code CLI."""

    name = "claude"

    def build_command(self, task_description: str) -> list[str]:
        return [
            "claude",
            "--print",
            "--output-format",
            "json",
            "-p",
            task_description,
        ]
