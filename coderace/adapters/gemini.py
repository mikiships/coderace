"""Gemini CLI adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_gemini_cost

DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"


class GeminiAdapter(BaseAdapter):
    """Adapter for Google Gemini CLI."""

    name = "gemini"

    def build_command(self, task_description: str, model: Optional[str] = None) -> list[str]:
        cmd = ["gemini"]
        effective_model = model or self.model
        if effective_model:
            cmd += ["--model", effective_model]
        cmd += ["-p", task_description]
        return cmd

    def parse_cost(
        self,
        stdout: str,
        stderr: str,
        model_name: str = "",
        custom_pricing: dict[str, tuple[float, float]] | None = None,
    ) -> Optional[CostResult]:
        """Parse cost data from Gemini CLI output."""
        effective_model = model_name or self.model or DEFAULT_GEMINI_MODEL
        return parse_gemini_cost(stdout, stderr, effective_model, custom_pricing)
