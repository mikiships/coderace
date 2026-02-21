"""Tests for git operations."""

from __future__ import annotations

from pathlib import Path

from coderace.git_ops import (
    branch_name_for,
    checkout,
    create_branch,
    get_current_ref,
    get_diff_stat,
    has_uncommitted_changes,
)


def test_get_current_ref(tmp_repo: Path) -> None:
    ref = get_current_ref(tmp_repo)
    assert len(ref) == 40  # full SHA


def test_create_and_checkout_branch(tmp_repo: Path) -> None:
    base = get_current_ref(tmp_repo)
    create_branch(tmp_repo, "test-branch", base)
    # Should now be on test-branch
    import subprocess

    result = subprocess.run(
        ["git", "branch", "--show-current"], cwd=tmp_repo, capture_output=True, text=True
    )
    assert result.stdout.strip() == "test-branch"


def test_checkout_back(tmp_repo: Path) -> None:
    base = get_current_ref(tmp_repo)
    create_branch(tmp_repo, "feature", base)
    checkout(tmp_repo, "main")
    import subprocess

    result = subprocess.run(
        ["git", "branch", "--show-current"], cwd=tmp_repo, capture_output=True, text=True
    )
    assert result.stdout.strip() == "main"


def test_diff_stat_no_changes(tmp_repo: Path) -> None:
    base = get_current_ref(tmp_repo)
    stat, lines = get_diff_stat(tmp_repo, base)
    assert lines == 0


def test_diff_stat_with_changes(tmp_repo: Path) -> None:
    base = get_current_ref(tmp_repo)
    create_branch(tmp_repo, "changes", base)
    (tmp_repo / "new_file.py").write_text("print('hello')\n")
    import subprocess

    subprocess.run(["git", "add", "."], cwd=tmp_repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add file"], cwd=tmp_repo, capture_output=True)
    _, lines = get_diff_stat(tmp_repo, base)
    assert lines > 0


def test_branch_name_for() -> None:
    assert branch_name_for("fix-bug", "claude") == "coderace/claude-fix-bug"
    assert branch_name_for("my-task", "codex") == "coderace/codex-my-task"


def test_has_uncommitted_changes(tmp_repo: Path) -> None:
    assert not has_uncommitted_changes(tmp_repo)
    (tmp_repo / "dirty.txt").write_text("dirty")
    assert has_uncommitted_changes(tmp_repo)
