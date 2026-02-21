"""Base adapter interface."""

from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path

from coderace.types import AgentResult


class BaseAdapter(ABC):
    """Abstract base class for coding agent adapters."""

    name: str = "base"

    @abstractmethod
    def build_command(self, task_description: str) -> list[str]:
        """Build the CLI command to invoke this agent."""
        ...

    def run(self, task_description: str, workdir: Path, timeout: int) -> AgentResult:
        """Run the agent on a task and capture results."""
        cmd = self.build_command(task_description)
        start = time.monotonic()
        timed_out = False

        try:
            proc = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as e:
            timed_out = True
            exit_code = -1
            stdout = (e.stdout or b"").decode("utf-8", errors="replace") if e.stdout else ""
            stderr = (e.stderr or b"").decode("utf-8", errors="replace") if e.stderr else ""
        except FileNotFoundError:
            timed_out = False
            exit_code = 127
            stdout = ""
            stderr = f"Command not found: {cmd[0]}"

        wall_time = time.monotonic() - start

        return AgentResult(
            agent=self.name,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            wall_time=wall_time,
            timed_out=timed_out,
        )
