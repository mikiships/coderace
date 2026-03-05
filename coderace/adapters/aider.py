"""Aider adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_aider_cost

DEFAULT_AIDER_MODEL = "aider-default"


class AiderAdapter(BaseAdapter):
    """Adapter for Aider coding assistant."""

    name = "aider"

    def build_command(self, task_description: str, model: Optional[str] = None) -> list[str]:
        cmd = [
            "aider",
            "--message",
            task_description,
            "--yes",
            "--no-auto-commits",
        ]
        effective_model = model or self.model
        if effective_model:
            cmd += ["--model", effective_model]
        return cmd

    def parse_cost(
        self,
        stdout: str,
        stderr: str,
        model_name: str = "",
        custom_pricing: dict[str, tuple[float, float]] | None = None,
    ) -> Optional[CostResult]:
        """Parse cost data from Aider output."""
        effective_model = model_name or self.model or DEFAULT_AIDER_MODEL
        return parse_aider_cost(stdout, stderr, effective_model, custom_pricing)
