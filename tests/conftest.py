"""Shared test fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temporary git repo with an initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
    (repo / "README.md").write_text("# Test repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
    return repo


@pytest.fixture
def task_yaml(tmp_path: Path) -> Path:
    """Create a sample task YAML file."""
    yaml_content = """name: test-task
description: Fix the bug in main.py
repo: .
test_command: echo "tests pass"
lint_command: echo "lint clean"
timeout: 60
agents:
  - claude
  - codex
"""
    path = tmp_path / "task.yaml"
    path.write_text(yaml_content)
    return path
