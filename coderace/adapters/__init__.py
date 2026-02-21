"""Agent adapters for coderace."""

from coderace.adapters.aider import AiderAdapter
from coderace.adapters.base import BaseAdapter
from coderace.adapters.claude import ClaudeAdapter
from coderace.adapters.codex import CodexAdapter
from coderace.adapters.gemini import GeminiAdapter

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "aider": AiderAdapter,
    "gemini": GeminiAdapter,
}

__all__ = [
    "ADAPTERS",
    "BaseAdapter",
    "ClaudeAdapter",
    "CodexAdapter",
    "AiderAdapter",
    "GeminiAdapter",
]
