"""Gemini CLI adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_gemini_cost


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

    def parse_cost(
        self,
        stdout: str,
        stderr: str,
        model_name: str = "gemini-2.5-pro",
        custom_pricing: dict[str, tuple[float, float]] | None = None,
    ) -> Optional[CostResult]:
        """Parse cost data from Gemini CLI output."""
        return parse_gemini_cost(stdout, stderr, model_name, custom_pricing)
