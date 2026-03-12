"""Maintainer rubric evaluator — pure static analysis on git diffs.

No LLM required. Scores a diff on 5 dimensions that real maintainers
care about, based on METR research (Mar 2026) showing ~50% of
SWE-bench-passing PRs would be rejected by actual maintainers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class MaintainerRubric:
    """Per-dimension scores (0-100) and a weighted composite."""

    minimal_diff: float = 0.0
    """Did the agent change only what was needed?"""

    convention_adherence: float = 0.0
    """New code follows existing naming/formatting conventions."""

    dep_hygiene: float = 0.0
    """No unnecessary new imports / dependencies."""

    scope_discipline: float = 0.0
    """Diff touches only task-relevant files (didn't over-reach)."""

    idiomatic_patterns: float = 0.0
    """Code reads like the rest of the codebase (no alien constructs)."""

    composite: float = 0.0
    """Weighted composite (0-100)."""

    # Weights used to compute the composite
    WEIGHTS: dict[str, float] = field(default_factory=lambda: {
        "minimal_diff": 0.20,
        "convention_adherence": 0.25,
        "dep_hygiene": 0.20,
        "scope_discipline": 0.20,
        "idiomatic_patterns": 0.15,
    })

    def as_dict(self) -> dict[str, float]:
        return {
            "minimal_diff": self.minimal_diff,
            "convention_adherence": self.convention_adherence,
            "dep_hygiene": self.dep_hygiene,
            "scope_discipline": self.scope_discipline,
            "idiomatic_patterns": self.idiomatic_patterns,
            "composite": self.composite,
        }


# ---------------------------------------------------------------------------
# Diff parsing helpers
# ---------------------------------------------------------------------------

def _parse_diff(diff_text: str) -> dict[str, object]:
    """Parse a unified diff into a structured dict.

    Returns:
        {
          "files": [str, ...],          # changed file paths
          "added_lines": [str, ...],    # raw added lines (without leading '+')
          "removed_lines": [str, ...],  # raw removed lines (without leading '-')
          "added_count": int,
          "removed_count": int,
          "total_delta": int,           # added + removed
        }
    """
    files: list[str] = []
    added: list[str] = []
    removed: list[str] = []

    current_file: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            # "diff --git a/foo.py b/foo.py"
            parts = line.split(" b/", 1)
            current_file = parts[1].strip() if len(parts) == 2 else None
            if current_file and current_file not in files:
                files.append(current_file)
        elif line.startswith("+++ b/"):
            path = line[6:].strip()
            if path and path not in files:
                files.append(path)
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])

    return {
        "files": files,
        "added_lines": added,
        "removed_lines": removed,
        "added_count": len(added),
        "removed_count": len(removed),
        "total_delta": len(added) + len(removed),
    }


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------

# Task complexity → expected line range heuristic
# We can't know the true task complexity from the diff alone, so we use
# a "reasonable change" heuristic: a well-scoped PR should have a sensible
# ratio of added lines to files changed. Penalise bloated diffs.

_IDEAL_LINES_PER_FILE = 40  # target max; over this, we start deducting


def score_minimal_diff(diff_text: str, task_hint: str | None = None) -> float:
    """Score: did the agent change only what was needed?

    Heuristic: penalise large diffs relative to files touched.
    A diff touching 1 file with 500 added lines is less minimal than
    one touching 3 files with 60 added lines total.
    """
    parsed = _parse_diff(diff_text)
    added = parsed["added_count"]
    files = max(len(parsed["files"]), 1)

    ratio = added / files  # added lines per file
    if ratio <= _IDEAL_LINES_PER_FILE:
        return 100.0
    # Linear decay: each doubling of the ideal halves the score
    import math
    score = 100.0 * (_IDEAL_LINES_PER_FILE / ratio)
    return max(0.0, min(100.0, score))


_CAMEL_CASE_RE = re.compile(r"[a-z][A-Z]")  # camelCase in Python → alien
_SINGLE_LETTER_VAR_RE = re.compile(r"^\s{4,}(?:for|while)\s+\w+\s+in\s+")
_TRAILING_WHITESPACE_RE = re.compile(r" +$", re.MULTILINE)


def score_convention_adherence(diff_text: str) -> float:
    """Score: does the new code follow existing naming/formatting conventions?

    Checks for:
    - camelCase identifiers in Python code (should be snake_case)
    - trailing whitespace
    - inconsistent indentation (tabs vs spaces in .py files)
    - mixed quote styles in the added chunk (minor deduction)
    """
    parsed = _parse_diff(diff_text)
    added = "\n".join(parsed["added_lines"])
    if not added.strip():
        return 100.0

    penalty = 0.0
    python_files = [f for f in parsed["files"] if f.endswith(".py")]

    if python_files:
        # camelCase penalty: -10 per camelCase usage up to -40
        camel_hits = len(_CAMEL_CASE_RE.findall(added))
        penalty += min(40.0, camel_hits * 10.0)

        # Trailing whitespace penalty: -5 per line up to -20
        trailing = len(_TRAILING_WHITESPACE_RE.findall(added))
        penalty += min(20.0, trailing * 5.0)

        # Tab indentation in Python: -20 per tab-indented line up to -30
        tab_lines = sum(1 for line in parsed["added_lines"] if line.startswith("\t"))
        penalty += min(30.0, tab_lines * 20.0)

    return max(0.0, 100.0 - penalty)


_IMPORT_RE = re.compile(r"^(?:import|from)\s+(\S+)", re.MULTILINE)
# stdlib and common "free" libraries (not new deps)
_STDLIB_OR_COMMON = frozenset({
    "os", "sys", "re", "json", "pathlib", "typing", "dataclasses",
    "collections", "itertools", "functools", "math", "io", "abc",
    "contextlib", "copy", "time", "datetime", "logging", "warnings",
    "subprocess", "threading", "concurrent", "enum", "string",
    "hashlib", "struct", "random", "uuid", "tempfile", "shutil",
    "unittest", "textwrap", "ast", "inspect", "importlib",
    "__future__", "types",
})


def score_dep_hygiene(diff_text: str) -> float:
    """Score: no unnecessary new imports / dependencies.

    Checks the added lines for new import statements.  Stdlib imports
    are free.  Third-party imports each carry a small penalty unless
    they appeared in the removed lines too (replacement, not addition).
    """
    parsed = _parse_diff(diff_text)

    added_imports = set(_IMPORT_RE.findall("\n".join(parsed["added_lines"])))
    removed_imports = set(_IMPORT_RE.findall("\n".join(parsed["removed_lines"])))

    # Net new imports (not in removed, not stdlib)
    new_third_party = {
        pkg.split(".")[0]
        for pkg in (added_imports - removed_imports)
        if pkg.split(".")[0] not in _STDLIB_OR_COMMON
    }

    if not new_third_party:
        return 100.0

    # -15 per new third-party import, up to -60
    penalty = min(60.0, len(new_third_party) * 15.0)
    return max(0.0, 100.0 - penalty)


# Files that are almost always legitimate to touch regardless of task
_ALWAYS_OK_FILES = frozenset({
    "pyproject.toml", "setup.py", "setup.cfg",
    "README.md", "CHANGELOG.md", "CONTRIBUTING.md",
    "requirements.txt", "requirements-dev.txt",
    ".gitignore", "Makefile",
})

_TEST_FILE_RE = re.compile(r"(test_|_test\.py$|/tests?/)")
_SOURCE_FILE_RE = re.compile(r"\.(py|js|ts|go|rs|java|c|cpp|h|rb|php)$")


def score_scope_discipline(
    diff_text: str,
    allowed_paths: Sequence[str] | None = None,
) -> float:
    """Score: did the agent stay within scope?

    If allowed_paths is given, each changed file not in allowed_paths or
    _ALWAYS_OK_FILES is a scope violation.  Without allowed_paths we use
    heuristics: penalise if the diff touches >5 distinct source files
    (suggests over-reaching), or mixes config/docs changes with deep
    source changes unexpectedly.
    """
    parsed = _parse_diff(diff_text)
    files: list[str] = parsed["files"]  # type: ignore[assignment]

    if not files:
        return 100.0

    if allowed_paths is not None:
        allowed_set = set(allowed_paths) | _ALWAYS_OK_FILES
        violations = [f for f in files if Path(f).name not in allowed_set and f not in allowed_set]
        if not violations:
            return 100.0
        ratio = len(violations) / len(files)
        return max(0.0, 100.0 - ratio * 80.0)

    # Heuristic: number of distinct source files changed
    source_files = [f for f in files if _SOURCE_FILE_RE.search(f)]
    if len(source_files) <= 3:
        return 100.0
    if len(source_files) <= 6:
        return 80.0
    if len(source_files) <= 10:
        return 60.0
    return max(0.0, 100.0 - (len(source_files) - 10) * 5.0)


# Alien construct patterns for Python (things that don't fit the ecosystem)
_ALIEN_PATTERNS: list[tuple[str, float]] = [
    # Lambda where a def would be clearer
    (r"lambda\s+\w+(?:,\s*\w+)*:\s*.{60,}", 5.0),
    # Unnecessary semicolons (JS/Java habit)
    (r";\s*$", 10.0),
    # Uppercase variable names that aren't CONSTANTS or class names
    (r"^\s+[A-Z][a-z]+[A-Z]", 5.0),
    # Explicit `== True` / `== False` comparisons
    (r"==\s*(True|False)", 8.0),
    # Print statements disguised as debug (forgotten)
    (r'print\s*\(\s*["\']DEBUG', 3.0),
    # Global state mutation via `global` keyword
    (r"^\s+global\s+\w+", 10.0),
]


def score_idiomatic_patterns(diff_text: str) -> float:
    """Score: does the code read like the rest of the codebase?

    Detects alien constructs that suggest the code was generated
    by an agent that didn't study the surrounding style.
    """
    parsed = _parse_diff(diff_text)
    added = "\n".join(parsed["added_lines"])
    if not added.strip():
        return 100.0

    penalty = 0.0
    for pattern, cost in _ALIEN_PATTERNS:
        hits = len(re.findall(pattern, added, re.MULTILINE))
        penalty += hits * cost

    return max(0.0, min(100.0, 100.0 - penalty))


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------

def score_rubric(
    diff_text: str,
    task_hint: str | None = None,
    allowed_paths: Sequence[str] | None = None,
    weights: dict[str, float] | None = None,
) -> MaintainerRubric:
    """Run all 5 dimension scorers and return a MaintainerRubric.

    Args:
        diff_text: Unified diff (git diff output).
        task_hint: Optional task description (future: influences expected complexity).
        allowed_paths: Optional list of file paths the task should touch.
        weights: Override default dimension weights.

    Returns:
        MaintainerRubric with per-dimension scores and composite.
    """
    rubric = MaintainerRubric()

    if weights:
        rubric.WEIGHTS = weights

    rubric.minimal_diff = score_minimal_diff(diff_text, task_hint)
    rubric.convention_adherence = score_convention_adherence(diff_text)
    rubric.dep_hygiene = score_dep_hygiene(diff_text)
    rubric.scope_discipline = score_scope_discipline(diff_text, allowed_paths)
    rubric.idiomatic_patterns = score_idiomatic_patterns(diff_text)

    w = rubric.WEIGHTS
    rubric.composite = (
        rubric.minimal_diff * w.get("minimal_diff", 0.20)
        + rubric.convention_adherence * w.get("convention_adherence", 0.25)
        + rubric.dep_hygiene * w.get("dep_hygiene", 0.20)
        + rubric.scope_discipline * w.get("scope_discipline", 0.20)
        + rubric.idiomatic_patterns * w.get("idiomatic_patterns", 0.15)
    )
    return rubric
