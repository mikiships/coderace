"""Git operations for branch isolation."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when a git operation fails."""


def get_current_ref(repo: Path) -> str:
    """Get the current HEAD commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to get HEAD: {result.stderr.strip()}")
    return result.stdout.strip()


def create_branch(repo: Path, branch_name: str, base_ref: str) -> None:
    """Create and checkout a new branch from base_ref."""
    result = subprocess.run(
        ["git", "checkout", "-b", branch_name, base_ref],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to create branch {branch_name}: {result.stderr.strip()}")


def checkout(repo: Path, ref: str) -> None:
    """Checkout a ref (branch name or commit hash)."""
    result = subprocess.run(
        ["git", "checkout", ref],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to checkout {ref}: {result.stderr.strip()}")


def get_diff_stat(repo: Path, base_ref: str) -> tuple[str, int]:
    """Get diff stat and total lines changed against base_ref.

    Returns (diff_stat_text, total_lines_changed).
    """
    stat_result = subprocess.run(
        ["git", "diff", "--stat", base_ref],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    numstat_result = subprocess.run(
        ["git", "diff", "--numstat", base_ref],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    total_lines = 0
    for line in numstat_result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                added = int(parts[0]) if parts[0] != "-" else 0
                removed = int(parts[1]) if parts[1] != "-" else 0
                total_lines += added + removed
            except ValueError:
                continue

    return stat_result.stdout.strip(), total_lines


def branch_name_for(task_name: str, agent_name: str) -> str:
    """Generate a branch name for a task/agent combo."""
    return f"coderace/{agent_name}-{task_name}"


def has_uncommitted_changes(repo: Path) -> bool:
    """Check if the repo has uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def stash_changes(repo: Path) -> bool:
    """Stash uncommitted changes. Returns True if something was stashed."""
    if not has_uncommitted_changes(repo):
        return False
    result = subprocess.run(
        ["git", "stash", "push", "-m", "coderace: auto-stash"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def stash_pop(repo: Path) -> None:
    """Pop the most recent stash."""
    subprocess.run(
        ["git", "stash", "pop"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
