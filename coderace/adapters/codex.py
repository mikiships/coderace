"""Codex CLI adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_codex_cost

DEFAULT_CODEX_MODEL = "gpt-5.3-codex"


class CodexAdapter(BaseAdapter):
    """Adapter for OpenAI Codex CLI."""

    name = "codex"

    def build_command(self, task_description: str, model: Optional[str] = None) -> list[str]:
        cmd = [
            "codex",
            "exec",
            "--full-auto",
        ]
        effective_model = model or self.model
        if effective_model:
            cmd += ["--model", effective_model]
        cmd.append(task_description)
        return cmd

    def parse_cost(
        self,
        stdout: str,
        stderr: str,
        model_name: str = "",
        custom_pricing: dict[str, tuple[float, float]] | None = None,
    ) -> Optional[CostResult]:
        """Parse cost data from Codex CLI output."""
        effective_model = model_name or self.model or DEFAULT_CODEX_MODEL
        return parse_codex_cost(stdout, stderr, effective_model, custom_pricing)
