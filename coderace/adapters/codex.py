"""Codex CLI adapter."""

from __future__ import annotations

from coderace.adapters.base import BaseAdapter


class CodexAdapter(BaseAdapter):
    """Adapter for OpenAI Codex CLI."""

    name = "codex"

    def build_command(self, task_description: str) -> list[str]:
        return [
            "codex",
            "--quiet",
            "--full-auto",
            "-p",
            task_description,
        ]
