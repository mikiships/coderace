"""Tests for the coderace diff command."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from coderace.cli import app
from coderace.commands.diff import (
    MODES,
    generate_task_yaml,
    parse_diff_summary,
    read_diff,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Sample diffs
# ---------------------------------------------------------------------------

SIMPLE_DIFF = """\
diff --git a/foo/bar.py b/foo/bar.py
index 123..456 100644
--- a/foo/bar.py
+++ b/foo/bar.py
@@ -1,3 +1,4 @@
 def hello():
-    pass
+    print("hello")
+    return True
"""

EMPTY_DIFF = ""

BINARY_DIFF = """\
diff --git a/assets/logo.png b/assets/logo.png
index 000..111 100644
Binary files a/assets/logo.png and b/assets/logo.png differ
"""

LARGE_DIFF = "diff --git a/big.py b/big.py\n" + "+" * 4000


# ---------------------------------------------------------------------------
# parse_diff_summary
# ---------------------------------------------------------------------------


def test_parse_diff_summary_basic() -> None:
    summary = parse_diff_summary(SIMPLE_DIFF)
    assert "foo/bar.py" in summary["files"]
    assert summary["added"] >= 2
    assert summary["removed"] >= 1


def test_parse_diff_summary_empty() -> None:
    summary = parse_diff_summary(EMPTY_DIFF)
    assert summary["files"] == []
    assert summary["added"] == 0
    assert summary["removed"] == 0


def test_parse_diff_summary_binary() -> None:
    summary = parse_diff_summary(BINARY_DIFF)
    assert "assets/logo.png" in summary["binary"]


# ---------------------------------------------------------------------------
# generate_task_yaml -- mode coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", sorted(MODES))
def test_generate_task_yaml_all_modes(mode: str) -> None:
    result = generate_task_yaml(diff=SIMPLE_DIFF, mode=mode)
    parsed = yaml.safe_load(result)
    assert isinstance(parsed, dict)
    # Must be a valid coderace task skeleton
    assert "name" in parsed
    assert "description" in parsed
    assert "agents" in parsed
    assert "test_command" in parsed
    # Description should mention mode intent
    desc_lower = parsed["description"].lower()
    if mode == "review":
        assert "review" in desc_lower
    elif mode == "fix":
        assert "fix" in desc_lower
    elif mode == "improve":
        assert "improve" in desc_lower


def test_generate_task_yaml_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unknown mode"):
        generate_task_yaml(diff=SIMPLE_DIFF, mode="bogus")


def test_generate_task_yaml_custom_agents() -> None:
    result = generate_task_yaml(diff=SIMPLE_DIFF, mode="fix", agents=["claude", "gemini"])
    parsed = yaml.safe_load(result)
    assert parsed["agents"] == ["claude", "gemini"]


def test_generate_task_yaml_default_agents() -> None:
    result = generate_task_yaml(diff=SIMPLE_DIFF, mode="review")
    parsed = yaml.safe_load(result)
    assert len(parsed["agents"]) > 0


def test_generate_task_yaml_empty_diff() -> None:
    result = generate_task_yaml(diff=EMPTY_DIFF, mode="review")
    parsed = yaml.safe_load(result)
    assert "description" in parsed
    # Empty diff → no files listed
    assert "Affected files:" not in parsed["description"]


def test_generate_task_yaml_large_diff_truncated() -> None:
    result = generate_task_yaml(diff=LARGE_DIFF, mode="review")
    parsed = yaml.safe_load(result)
    desc = parsed["description"]
    assert "truncated" in desc.lower()


# ---------------------------------------------------------------------------
# read_diff
# ---------------------------------------------------------------------------


def test_read_diff_from_file(tmp_path: Path) -> None:
    patch = tmp_path / "my.patch"
    patch.write_text(SIMPLE_DIFF)
    content = read_diff(patch)
    assert content == SIMPLE_DIFF


def test_read_diff_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_diff(tmp_path / "nonexistent.patch")


def test_read_diff_no_file_no_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """When stdin is a TTY and no file given, returns empty string."""
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    # Simulate TTY by setting isatty
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    result = read_diff(None)
    assert result == ""


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_diff_from_file(tmp_path: Path) -> None:
    patch = tmp_path / "test.patch"
    patch.write_text(SIMPLE_DIFF)
    result = runner.invoke(app, ["diff", "--file", str(patch), "--mode", "review"])
    assert result.exit_code == 0
    # Output should be parseable YAML
    parsed = yaml.safe_load(result.output)
    assert "description" in parsed


def test_cli_diff_output_file(tmp_path: Path) -> None:
    patch = tmp_path / "test.patch"
    patch.write_text(SIMPLE_DIFF)
    out = tmp_path / "task.yaml"
    result = runner.invoke(
        app, ["diff", "--file", str(patch), "--mode", "fix", "--output", str(out)]
    )
    assert result.exit_code == 0
    assert out.exists()
    parsed = yaml.safe_load(out.read_text())
    assert "description" in parsed


def test_cli_diff_mode_fix(tmp_path: Path) -> None:
    patch = tmp_path / "test.patch"
    patch.write_text(SIMPLE_DIFF)
    result = runner.invoke(app, ["diff", "--file", str(patch), "--mode", "fix"])
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert "fix" in parsed["description"].lower()


def test_cli_diff_mode_improve(tmp_path: Path) -> None:
    patch = tmp_path / "test.patch"
    patch.write_text(SIMPLE_DIFF)
    result = runner.invoke(app, ["diff", "--file", str(patch), "--mode", "improve"])
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert "improve" in parsed["description"].lower()


def test_cli_diff_unknown_mode(tmp_path: Path) -> None:
    patch = tmp_path / "test.patch"
    patch.write_text(SIMPLE_DIFF)
    result = runner.invoke(app, ["diff", "--file", str(patch), "--mode", "bogus"])
    assert result.exit_code != 0


def test_cli_diff_with_agents(tmp_path: Path) -> None:
    patch = tmp_path / "test.patch"
    patch.write_text(SIMPLE_DIFF)
    result = runner.invoke(
        app, ["diff", "--file", str(patch), "--agents", "claude", "--agents", "aider"]
    )
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert "claude" in parsed["agents"]
    assert "aider" in parsed["agents"]


def test_cli_diff_missing_file() -> None:
    result = runner.invoke(app, ["diff", "--file", "/nonexistent/path.patch"])
    assert result.exit_code != 0


def test_cli_diff_custom_name(tmp_path: Path) -> None:
    patch = tmp_path / "test.patch"
    patch.write_text(SIMPLE_DIFF)
    result = runner.invoke(app, ["diff", "--file", str(patch), "--name", "my-custom-task"])
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert parsed["name"] == "my-custom-task"
