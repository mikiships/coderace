"""OpenCode adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_opencode_cost


class OpenCodeAdapter(BaseAdapter):
    """Adapter for OpenCode CLI (terminal-first AI coding agent)."""

    name = "opencode"

    def build_command(self, task_description: str) -> list[str]:
        return [
            "opencode",
            "run",
            task_description,
        ]

    def parse_cost(
        self,
        stdout: str,
        stderr: str,
        model_name: str = "opencode-default",
        custom_pricing: dict[str, tuple[float, float]] | None = None,
    ) -> Optional[CostResult]:
        """Parse cost data from OpenCode output."""
        return parse_opencode_cost(stdout, stderr, model_name, custom_pricing)
