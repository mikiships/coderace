"""Gemini CLI adapter."""

from __future__ import annotations

from coderace.adapters.base import BaseAdapter


class GeminiAdapter(BaseAdapter):
    """Adapter for Google Gemini CLI."""

    name = "gemini"

    def build_command(self, task_description: str) -> list[str]:
        return [
            "gemini",
            "--non-interactive",
            "-p",
            task_description,
        ]
