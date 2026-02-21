"""Aider adapter."""

from __future__ import annotations

from coderace.adapters.base import BaseAdapter


class AiderAdapter(BaseAdapter):
    """Adapter for Aider coding assistant."""

    name = "aider"

    def build_command(self, task_description: str) -> list[str]:
        return [
            "aider",
            "--message",
            task_description,
            "--yes",
            "--no-auto-commits",
        ]
