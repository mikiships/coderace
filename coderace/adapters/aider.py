"""Aider adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_aider_cost


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

    def parse_cost(
        self,
        stdout: str,
        stderr: str,
        model_name: str = "aider-default",
        custom_pricing: dict[str, tuple[float, float]] | None = None,
    ) -> Optional[CostResult]:
        """Parse cost data from Aider output."""
        return parse_aider_cost(stdout, stderr, model_name, custom_pricing)
