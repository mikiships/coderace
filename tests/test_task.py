"""Tests for task loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderace.task import create_template, load_task
from coderace.types import Task, VERIFY_AWARE_DEFAULT_WEIGHTS


def test_load_valid_task(task_yaml: Path) -> None:
    task = load_task(task_yaml)
    assert task.name == "test-task"
    assert task.description == "Fix the bug in main.py"
    assert task.test_command == 'echo "tests pass"'
    assert task.agents == ["claude", "codex"]
    assert task.timeout == 60


def test_load_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_task("/nonexistent/path.yaml")


def test_load_missing_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("name: test\n")
    with pytest.raises(ValueError, match="Missing required fields"):
        load_task(path)


def test_load_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("just a string\n")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_task(path)


def test_load_unknown_agent(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("""name: t
description: d
test_command: echo ok
agents:
  - unknown_agent
""")
    with pytest.raises(ValueError, match="Unknown agent"):
        load_task(path)


def test_load_default_timeout(tmp_path: Path) -> None:
    path = tmp_path / "task.yaml"
    path.write_text("""name: t
description: d
test_command: echo ok
agents:
  - claude
""")
    task = load_task(path)
    assert task.timeout == 300


def test_create_template(tmp_path: Path) -> None:
    path = create_template("my-task", tmp_path)
    assert path.exists()
    assert path.name == "my-task.yaml"
    content = path.read_text()
    assert "my-task" in content
    assert "agents:" in content


def test_task_validate_empty_name() -> None:
    task = Task(name="", description="d", repo=Path("."), test_command="echo", agents=["claude"])
    errors = task.validate()
    assert any("name" in e for e in errors)


def test_task_validate_no_agents() -> None:
    task = Task(name="t", description="d", repo=Path("."), test_command="echo", agents=[])
    errors = task.validate()
    assert any("agent" in e.lower() for e in errors)


def test_load_task_with_verification_fields(tmp_path: Path) -> None:
    path = tmp_path / "task.yaml"
    path.write_text("""name: t
description: d
test_command: echo ok
verify_command: python3 -m pytest verify_tests.py -x -q
verify_files:
  verify_tests.py: |
    def test_ok():
      assert True
agents:
  - claude
""")
    task = load_task(path)
    assert task.verify_command == "python3 -m pytest verify_tests.py -x -q"
    assert task.verify_files == {
        "verify_tests.py": "def test_ok():\n  assert True\n"
    }
    assert task.get_weights() == VERIFY_AWARE_DEFAULT_WEIGHTS


def test_load_task_rejects_non_mapping_verify_files(tmp_path: Path) -> None:
    path = tmp_path / "task.yaml"
    path.write_text("""name: t
description: d
test_command: echo ok
verify_command: echo ok
verify_files:
  - bad
agents:
  - claude
""")
    with pytest.raises(ValueError, match="verify_files must be a mapping"):
        load_task(path)
