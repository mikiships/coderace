"""Tests for agent adapters."""

from __future__ import annotations

from coderace.adapters import ADAPTERS
from coderace.adapters.aider import AiderAdapter
from coderace.adapters.claude import ClaudeAdapter
from coderace.adapters.codex import CodexAdapter
from coderace.adapters.gemini import GeminiAdapter
from coderace.adapters.opencode import OpenCodeAdapter


def test_claude_command() -> None:
    adapter = ClaudeAdapter()
    cmd = adapter.build_command("Fix the bug")
    assert cmd[0] == "claude"
    assert "--print" in cmd
    assert "Fix the bug" in cmd


def test_codex_command() -> None:
    adapter = CodexAdapter()
    cmd = adapter.build_command("Fix the bug")
    assert cmd[0] == "codex"
    assert "--quiet" in cmd
    assert "Fix the bug" in cmd


def test_aider_command() -> None:
    adapter = AiderAdapter()
    cmd = adapter.build_command("Fix the bug")
    assert cmd[0] == "aider"
    assert "--message" in cmd
    assert "--yes" in cmd
    assert "--no-auto-commits" in cmd
    assert "Fix the bug" in cmd


def test_gemini_command() -> None:
    adapter = GeminiAdapter()
    cmd = adapter.build_command("Fix the bug")
    assert cmd[0] == "gemini"
    assert "--non-interactive" in cmd
    assert "Fix the bug" in cmd


def test_opencode_command() -> None:
    adapter = OpenCodeAdapter()
    cmd = adapter.build_command("Fix the bug")
    assert cmd[0] == "opencode"
    assert "run" in cmd
    assert "Fix the bug" in cmd


def test_adapters_registry() -> None:
    assert "claude" in ADAPTERS
    assert "codex" in ADAPTERS
    assert "aider" in ADAPTERS
    assert "gemini" in ADAPTERS
    assert "opencode" in ADAPTERS
    assert len(ADAPTERS) == 5


def test_adapter_names() -> None:
    assert ClaudeAdapter().name == "claude"
    assert CodexAdapter().name == "codex"
    assert AiderAdapter().name == "aider"
    assert GeminiAdapter().name == "gemini"
    assert OpenCodeAdapter().name == "opencode"
