"""Codex CLI adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_codex_cost


class CodexAdapter(BaseAdapter):
    """Adapter for OpenAI Codex CLI."""

    name = "codex"

    def build_command(self, task_description: str) -> list[str]:
        return [
            "codex",
            "exec",
            "--full-auto",
            task_description,
        ]

    def parse_cost(
        self,
        stdout: str,
        stderr: str,
        model_name: str = "gpt-5.3-codex",
        custom_pricing: dict[str, tuple[float, float]] | None = None,
    ) -> Optional[CostResult]:
        """Parse cost data from Codex CLI output."""
        return parse_codex_cost(stdout, stderr, model_name, custom_pricing)
