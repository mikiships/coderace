"""Integration tests for verification scoring flow."""

from __future__ import annotations

import sys
from pathlib import Path

from coderace.scorer import compute_score
from coderace.task import load_task
from coderace.types import AgentResult


def _agent_result() -> AgentResult:
    return AgentResult(
        agent="claude",
        exit_code=0,
        stdout="",
        stderr="",
        wall_time=1.0,
    )


def _write_test_and_verify_scripts(workdir: Path) -> None:
    (workdir / "set_target.py").write_text(
        "from pathlib import Path\n"
        "Path('target.txt').write_text('from-tests\\n')\n",
        encoding="utf-8",
    )
    (workdir / "verify_target.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "expected = sys.argv[1]\n"
        "actual = Path('target.txt').read_text().strip()\n"
        "print(actual)\n"
        "raise SystemExit(0 if actual == expected else 1)\n",
        encoding="utf-8",
    )


def _write_task_yaml(path: Path, repo: Path, verify_enabled: bool) -> None:
    verify_block = ""
    if verify_enabled:
        verify_block = f"""
verify_command: {sys.executable} verify_target.py expected-from-verify
verify_files:
  target.txt: |
    from-verify
"""
    path.write_text(
        f"""name: integration-verify
description: integration test
repo: {repo}
test_command: {sys.executable} set_target.py
{verify_block}agents:
  - claude
""",
        encoding="utf-8",
    )


def test_verify_command_changes_score_distribution_end_to_end(tmp_path: Path) -> None:
    _write_test_and_verify_scripts(tmp_path)

    no_verify_yaml = tmp_path / "task-no-verify.yaml"
    with_verify_yaml = tmp_path / "task-with-verify.yaml"
    _write_task_yaml(no_verify_yaml, tmp_path, verify_enabled=False)
    _write_task_yaml(with_verify_yaml, tmp_path, verify_enabled=True)

    no_verify_task = load_task(no_verify_yaml)
    with_verify_task = load_task(with_verify_yaml)

    no_verify_score = compute_score(
        result=_agent_result(),
        test_command=no_verify_task.test_command,
        lint_command=None,
        workdir=tmp_path,
        diff_lines=1,
        all_wall_times=[1.0],
        all_diff_lines=[1],
        weights=no_verify_task.get_weights(),
        verify_command=no_verify_task.verify_command,
        verify_files=no_verify_task.verify_files,
    )
    with_verify_score = compute_score(
        result=_agent_result(),
        test_command=with_verify_task.test_command,
        lint_command=None,
        workdir=tmp_path,
        diff_lines=1,
        all_wall_times=[1.0],
        all_diff_lines=[1],
        weights=with_verify_task.get_weights(),
        verify_command=with_verify_task.verify_command,
        verify_files=with_verify_task.verify_files,
    )

    # No-verify task has no verification penalty.
    assert no_verify_score.composite == 100.0
    # Verify-enabled task fails verification and pays the 30-point verify weight penalty.
    assert with_verify_score.composite == 70.0
    assert with_verify_score.verify_passed is False


def test_verify_files_overwrite_workspace_files_end_to_end(tmp_path: Path) -> None:
    _write_test_and_verify_scripts(tmp_path)
    task_yaml = tmp_path / "task.yaml"
    task_yaml.write_text(
        f"""name: integration-overwrite
description: integration test
repo: {tmp_path}
test_command: {sys.executable} set_target.py
verify_command: {sys.executable} verify_target.py from-verify
verify_files:
  target.txt: |
    from-verify
agents:
  - claude
""",
        encoding="utf-8",
    )

    task = load_task(task_yaml)
    score = compute_score(
        result=_agent_result(),
        test_command=task.test_command,
        lint_command=None,
        workdir=tmp_path,
        diff_lines=1,
        all_wall_times=[1.0],
        all_diff_lines=[1],
        weights=task.get_weights(),
        verify_command=task.verify_command,
        verify_files=task.verify_files,
    )

    assert score.verify_passed is True
    assert (tmp_path / "target.txt").read_text(encoding="utf-8") == "from-verify\n"
