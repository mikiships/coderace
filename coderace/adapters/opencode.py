"""OpenCode adapter."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.base import BaseAdapter
from coderace.cost import CostResult, parse_opencode_cost

DEFAULT_OPENCODE_MODEL = "opencode-default"


class OpenCodeAdapter(BaseAdapter):
    """Adapter for OpenCode CLI (terminal-first AI coding agent)."""

    name = "opencode"

    def build_command(self, task_description: str, model: Optional[str] = None) -> list[str]:
        cmd = ["opencode", "run"]
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
        """Parse cost data from OpenCode output."""
        effective_model = model_name or self.model or DEFAULT_OPENCODE_MODEL
        return parse_opencode_cost(stdout, stderr, effective_model, custom_pricing)
