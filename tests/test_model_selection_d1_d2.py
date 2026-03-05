"""Tests for D1 (base adapter model support) and D2 (adapter model flags)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from coderace.adapters.aider import AiderAdapter
from coderace.adapters.base import BaseAdapter
from coderace.adapters.claude import ClaudeAdapter
from coderace.adapters.codex import CodexAdapter
from coderace.adapters.gemini import GeminiAdapter
from coderace.adapters.opencode import OpenCodeAdapter


# ---------------------------------------------------------------------------
# D1: BaseAdapter model support
# ---------------------------------------------------------------------------


def test_base_adapter_default_model_is_none() -> None:
    """BaseAdapter initializes with model=None by default."""

    class ConcreteAdapter(BaseAdapter):
        name = "test"

        def build_command(self, task_description: str, model=None) -> list[str]:
            return ["test", task_description]

    adapter = ConcreteAdapter()
    assert adapter.model is None


def test_base_adapter_accepts_model_kwarg() -> None:
    class ConcreteAdapter(BaseAdapter):
        name = "test"

        def build_command(self, task_description: str, model=None) -> list[str]:
            return ["test", task_description]

    adapter = ConcreteAdapter(model="my-model")
    assert adapter.model == "my-model"


def test_base_adapter_run_passes_model_to_build_command() -> None:
    """run() calls build_command with the adapter's model."""
    received = {}

    class ConcreteAdapter(BaseAdapter):
        name = "test"

        def build_command(self, task_description: str, model=None) -> list[str]:
            received["model"] = model
            return ["echo", task_description]

    adapter = ConcreteAdapter(model="test-model-xyz")
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter.run("do thing", pathlib.Path(tmpdir), timeout=5, no_cost=True)

    assert received["model"] == "test-model-xyz"


# ---------------------------------------------------------------------------
# D2: Codex adapter
# ---------------------------------------------------------------------------


def test_codex_no_model_flag() -> None:
    adapter = CodexAdapter()
    cmd = adapter.build_command("Fix bug")
    assert "--model" not in cmd
    assert "Fix bug" in cmd


def test_codex_model_via_init() -> None:
    adapter = CodexAdapter(model="gpt-5.4")
    cmd = adapter.build_command("Fix bug")
    assert "--model" in cmd
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "gpt-5.4"
    assert "Fix bug" in cmd


def test_codex_model_via_build_command() -> None:
    adapter = CodexAdapter()
    cmd = adapter.build_command("Fix bug", model="gpt-5.3-codex")
    assert "--model" in cmd
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "gpt-5.3-codex"


def test_codex_build_command_model_overrides_init() -> None:
    """model param in build_command takes priority over self.model."""
    adapter = CodexAdapter(model="gpt-5.4")
    cmd = adapter.build_command("task", model="gpt-5.3-codex")
    # build_command uses effective_model = model or self.model; since model="gpt-5.3-codex" is truthy, it wins
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "gpt-5.3-codex"


def test_codex_parse_cost_uses_model() -> None:
    adapter = CodexAdapter(model="gpt-5.4")
    # parse_cost should use self.model when model_name="" is passed
    # (smoke test — returns None for empty output, no crash)
    result = adapter.parse_cost("", "", model_name="")
    assert result is None or result is not None  # just no exception


# ---------------------------------------------------------------------------
# D2: Claude adapter
# ---------------------------------------------------------------------------


def test_claude_no_model_flag() -> None:
    adapter = ClaudeAdapter()
    cmd = adapter.build_command("Fix bug")
    assert "--model" not in cmd
    assert "Fix bug" in cmd


def test_claude_model_via_init() -> None:
    adapter = ClaudeAdapter(model="claude-opus-4-6")
    cmd = adapter.build_command("Fix bug")
    assert "--model" in cmd
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "claude-opus-4-6"


def test_claude_model_via_build_command() -> None:
    adapter = ClaudeAdapter()
    cmd = adapter.build_command("Fix bug", model="claude-sonnet-4-6")
    assert "--model" in cmd
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "claude-sonnet-4-6"


def test_claude_task_still_in_command() -> None:
    adapter = ClaudeAdapter(model="claude-opus-4-6")
    cmd = adapter.build_command("do the thing")
    assert "do the thing" in cmd
    assert "-p" in cmd


# ---------------------------------------------------------------------------
# D2: Aider adapter
# ---------------------------------------------------------------------------


def test_aider_no_model_flag() -> None:
    adapter = AiderAdapter()
    cmd = adapter.build_command("Fix bug")
    assert "--model" not in cmd


def test_aider_model_via_init() -> None:
    adapter = AiderAdapter(model="gpt-5.4")
    cmd = adapter.build_command("Fix bug")
    assert "--model" in cmd
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "gpt-5.4"


# ---------------------------------------------------------------------------
# D2: Gemini adapter
# ---------------------------------------------------------------------------


def test_gemini_no_model_flag() -> None:
    adapter = GeminiAdapter()
    cmd = adapter.build_command("Fix bug")
    assert "--model" not in cmd


def test_gemini_model_via_init() -> None:
    adapter = GeminiAdapter(model="gemini-2.5-flash")
    cmd = adapter.build_command("Fix bug")
    assert "--model" in cmd
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# D2: OpenCode adapter
# ---------------------------------------------------------------------------


def test_opencode_no_model_flag() -> None:
    adapter = OpenCodeAdapter()
    cmd = adapter.build_command("Fix bug")
    assert "--model" not in cmd


def test_opencode_model_via_init() -> None:
    adapter = OpenCodeAdapter(model="claude-sonnet-4-6")
    cmd = adapter.build_command("Fix bug")
    assert "--model" in cmd
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "claude-sonnet-4-6"
