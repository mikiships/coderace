"""Agent adapters for coderace."""

from __future__ import annotations

from typing import Optional

from coderace.adapters.aider import AiderAdapter
from coderace.adapters.base import BaseAdapter
from coderace.adapters.claude import ClaudeAdapter
from coderace.adapters.codex import CodexAdapter
from coderace.adapters.gemini import GeminiAdapter
from coderace.adapters.opencode import OpenCodeAdapter

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "aider": AiderAdapter,
    "gemini": GeminiAdapter,
    "opencode": OpenCodeAdapter,
}


def parse_agent_spec(spec: str) -> tuple[str, Optional[str]]:
    """Parse an agent spec string into (agent_name, model_or_None).

    Examples:
        "codex"           -> ("codex", None)
        "codex:gpt-5.4"  -> ("codex", "gpt-5.4")
        "claude:opus-4-6" -> ("claude", "opus-4-6")
    """
    if ":" in spec:
        agent_name, model = spec.split(":", 1)
        return agent_name.strip(), model.strip() or None
    return spec.strip(), None


def make_display_name(agent_name: str, model: Optional[str]) -> str:
    """Return display name for agent+model combo.

    Examples:
        ("codex", None)       -> "codex"
        ("codex", "gpt-5.4") -> "codex (gpt-5.4)"
    """
    if model:
        return f"{agent_name} ({model})"
    return agent_name


def instantiate_adapter(spec: str) -> BaseAdapter:
    """Instantiate an adapter from an agent spec string (e.g. 'codex:gpt-5.4').

    The returned adapter has:
    - adapter.model set to the parsed model (or None)
    - adapter.name set to the display name (e.g. 'codex (gpt-5.4)')

    Raises KeyError if the agent name is not in ADAPTERS.
    """
    agent_name, model = parse_agent_spec(spec)
    adapter_cls = ADAPTERS[agent_name]
    adapter = adapter_cls(model=model)
    # Override the instance name to be the display name
    adapter.name = make_display_name(agent_name, model)
    return adapter


__all__ = [
    "ADAPTERS",
    "BaseAdapter",
    "ClaudeAdapter",
    "CodexAdapter",
    "AiderAdapter",
    "GeminiAdapter",
    "OpenCodeAdapter",
    "parse_agent_spec",
    "make_display_name",
    "instantiate_adapter",
]
