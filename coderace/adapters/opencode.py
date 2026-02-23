"""OpenCode adapter."""

from __future__ import annotations

from coderace.adapters.base import BaseAdapter


class OpenCodeAdapter(BaseAdapter):
    """Adapter for OpenCode CLI (terminal-first AI coding agent)."""

    name = "opencode"

    def build_command(self, task_description: str) -> list[str]:
        return [
            "opencode",
            "run",
            task_description,
        ]
