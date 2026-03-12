"""CLI command: coderace gate — CI quality gate for diffs.

Pure static analysis via maintainer rubric. No LLM required.
Exits 0 (pass) or 1 (fail) based on composite rubric score.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console

from coderace.maintainer_rubric import score_rubric

app = typer.Typer(help="Run a CI quality gate on a diff using the maintainer rubric.")


@app.callback(invoke_without_command=True)
def gate_main(
    ctx: typer.Context,
    diff: str = typer.Option(
        ...,
        "--diff",
        help="Diff file path or '-' to read from stdin",
    ),
    min_score: int = typer.Option(
        ...,
        "--min-score",
        help="Minimum composite score (0-100). Exit 1 if score < min-score.",
        min=0,
        max=100,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output result as JSON (for CI log parsing)",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Plain output (no rich markup)",
    ),
) -> None:
    """Run a CI quality gate on a diff.

    Reads a unified diff from a file or stdin, scores it with the
    maintainer rubric, and exits 0 (pass) or 1 (fail).

    Examples:

      coderace gate --diff changes.patch --min-score 80

      git diff HEAD~1 | coderace gate --diff - --min-score 75 --json
    """
    if ctx.invoked_subcommand is not None:
        return

    console = Console(stderr=True, no_color=no_color)

    # Read diff
    if diff == "-":
        if sys.stdin.isatty():
            console.print("[red]No diff on stdin. Pipe a diff or use --diff <file>.[/red]")
            raise typer.Exit(2)
        diff_text = sys.stdin.read()
    else:
        diff_path = Path(diff)
        if not diff_path.exists():
            console.print(f"[red]Diff file not found: {diff_path}[/red]")
            raise typer.Exit(2)
        diff_text = diff_path.read_text(encoding="utf-8")

    if not diff_text.strip():
        # Empty diff — perfect score, always passes
        composite = 100.0
        rubric_dict = {
            "minimal_diff": 100.0,
            "convention_adherence": 100.0,
            "dep_hygiene": 100.0,
            "scope_discipline": 100.0,
            "idiomatic_patterns": 100.0,
            "composite": 100.0,
        }
        passed = composite >= min_score
        _output_result(
            composite=composite,
            min_score=min_score,
            passed=passed,
            rubric_dict=rubric_dict,
            as_json=as_json,
            no_color=no_color,
        )
        raise typer.Exit(0 if passed else 1)

    rubric = score_rubric(diff_text)
    composite = rubric.composite
    passed = composite >= min_score

    _output_result(
        composite=composite,
        min_score=min_score,
        passed=passed,
        rubric_dict=rubric.as_dict(),
        as_json=as_json,
        no_color=no_color,
    )
    raise typer.Exit(0 if passed else 1)


def _output_result(
    composite: float,
    min_score: int,
    passed: bool,
    rubric_dict: dict[str, float],
    as_json: bool,
    no_color: bool,
) -> None:
    """Print gate result to stdout."""
    score_int = round(composite)
    if as_json:
        result = {
            "gate": "PASS" if passed else "FAIL",
            "score": score_int,
            "min_score": min_score,
            "passed": passed,
            "dimensions": {k: round(v) for k, v in rubric_dict.items() if k != "composite"},
        }
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return

    # Human-readable output
    if passed:
        icon = "✅"
        verdict = "PASS"
    else:
        icon = "❌"
        verdict = "FAIL"

    op = "≥" if passed else "<"
    line = f"{icon} Maintainer score {score_int} {op} {min_score} (gate: {verdict})"
    sys.stdout.write(line + "\n")
