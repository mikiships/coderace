"""coderace diff: generate a task YAML from a git diff."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

MODES = frozenset({"review", "fix", "improve"})

DEFAULT_AGENTS = ["claude", "codex", "aider"]

_MODE_PREFIX: dict[str, str] = {
    "review": (
        "Review the following changes and provide feedback on correctness, "
        "style, and potential issues."
    ),
    "fix": (
        "Fix the issues in the following diff. "
        "Address any bugs, errors, or problems introduced by these changes."
    ),
    "improve": (
        "Improve the following code changes. "
        "Enhance performance, readability, or robustness."
    ),
}


def parse_diff_summary(diff: str) -> dict[str, object]:
    """Extract changed file names and line-count stats from a unified git diff.

    Returns a dict with keys:
        files: list[str]  -- changed file paths (b-side names)
        added: int        -- lines added
        removed: int      -- lines removed
        binary: list[str] -- binary file paths detected
    """
    if not diff.strip():
        return {"files": [], "added": 0, "removed": 0, "binary": []}

    files: list[str] = []
    binary: list[str] = []
    added = 0
    removed = 0

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            match = re.search(r"diff --git a/(.+) b/(.+)", line)
            if match:
                files.append(match.group(2))
        elif line.startswith("Binary files"):
            # e.g. "Binary files a/foo.png and b/foo.png differ"
            bm = re.search(r"Binary files .+ and b/(.+) differ", line)
            if bm:
                binary.append(bm.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1

    return {"files": files, "added": added, "removed": removed, "binary": binary}


def build_description(diff: str, mode: str) -> str:
    """Build a human-readable task description from a diff and mode."""
    mode = mode if mode in MODES else "review"
    prefix = _MODE_PREFIX[mode]

    summary = parse_diff_summary(diff)
    files: list[str] = summary["files"]  # type: ignore[assignment]
    binary: list[str] = summary["binary"]  # type: ignore[assignment]
    added: int = summary["added"]  # type: ignore[assignment]
    removed: int = summary["removed"]  # type: ignore[assignment]

    parts: list[str] = [prefix]

    if files:
        shown = files[:5]
        file_str = ", ".join(shown)
        if len(files) > 5:
            file_str += f" and {len(files) - 5} more"
        parts.append(f"\nAffected files: {file_str}")

    if binary:
        parts.append(f"\nBinary files (skipped in diff): {', '.join(binary[:3])}")

    parts.append(f"\nChanges: +{added} -{removed} lines")

    # Include diff text, truncated if large
    max_diff_chars = 3000
    diff_text = diff
    truncated = False
    if len(diff_text) > max_diff_chars:
        diff_text = diff_text[:max_diff_chars]
        truncated = True

    parts.append(f"\n\nDiff:\n```diff\n{diff_text}")
    if truncated:
        parts.append("... (diff truncated, showing first 3000 chars)")
    parts.append("```")

    return "".join(parts)


def generate_task_yaml(
    diff: str,
    mode: str = "review",
    agents: list[str] | None = None,
    name: str = "diff-task",
    test_command: str = "pytest tests/ -x",
    lint_command: str | None = "ruff check .",
) -> str:
    """Generate a coderace task YAML from a git diff string.

    Args:
        diff: The unified diff text (may be empty).
        mode: One of ``review``, ``fix``, ``improve``.
        agents: Agent names to include; defaults to claude, codex, aider.
        name: Task name written into the YAML.
        test_command: Shell command to run tests.
        lint_command: Shell command to run linter (optional).

    Returns:
        YAML string representing a valid coderace task.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}. Choose from: {', '.join(sorted(MODES))}")

    resolved_agents = agents if agents else list(DEFAULT_AGENTS)
    description = build_description(diff, mode)

    task: dict[str, object] = {
        "name": name,
        "description": description,
        "repo": ".",
        "test_command": test_command,
        "agents": resolved_agents,
    }
    if lint_command:
        task["lint_command"] = lint_command
    task["timeout"] = 300

    return yaml.dump(task, default_flow_style=False, allow_unicode=True, sort_keys=False)


def read_diff(file: Path | None) -> str:
    """Read diff from a file or stdin. Returns empty string if nothing available."""
    if file is not None:
        if not file.exists():
            raise FileNotFoundError(f"Diff file not found: {file}")
        return file.read_text(encoding="utf-8")

    # Read from stdin (non-blocking: only if data is actually piped)
    if not sys.stdin.isatty():
        return sys.stdin.read()

    return ""
