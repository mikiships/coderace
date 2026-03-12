"""Rich display helpers for coderace output."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from coderace.maintainer_rubric import MaintainerRubric


def _score_style(score: float) -> str:
    """Return a Rich style string based on the score value."""
    if score >= 80:
        return "bold green"
    if score >= 50:
        return "bold yellow"
    return "bold red"


def _score_verdict(score: float) -> str:
    if score >= 80:
        return "pass"
    if score >= 50:
        return "warn"
    return "fail"


class MaintainerRubricDisplay:
    """Render a MaintainerRubric as a Rich table."""

    DIMENSION_LABELS: dict[str, str] = {
        "minimal_diff": "Minimal Diff",
        "convention_adherence": "Convention Adherence",
        "dep_hygiene": "Dep Hygiene",
        "scope_discipline": "Scope Discipline",
        "idiomatic_patterns": "Idiomatic Patterns",
    }

    DIMENSION_DESCRIPTIONS: dict[str, str] = {
        "minimal_diff": "Changed only what was needed",
        "convention_adherence": "Follows existing naming/formatting",
        "dep_hygiene": "No unnecessary new imports",
        "scope_discipline": "Stayed within task scope",
        "idiomatic_patterns": "Code fits the existing style",
    }

    def build_table(self, rubric: MaintainerRubric) -> Table:
        """Build and return a Rich Table for the rubric."""
        table = Table(
            title="Maintainer Rubric",
            show_lines=True,
            title_style="bold cyan",
        )
        table.add_column("Dimension", style="cyan", no_wrap=True)
        table.add_column("Score", justify="right", no_wrap=True)
        table.add_column("Verdict", justify="center", no_wrap=True)
        table.add_column("Description")

        dimensions = [
            ("minimal_diff", rubric.minimal_diff),
            ("convention_adherence", rubric.convention_adherence),
            ("dep_hygiene", rubric.dep_hygiene),
            ("scope_discipline", rubric.scope_discipline),
            ("idiomatic_patterns", rubric.idiomatic_patterns),
        ]

        for key, score in dimensions:
            label = self.DIMENSION_LABELS[key]
            desc = self.DIMENSION_DESCRIPTIONS[key]
            style = _score_style(score)
            verdict = _score_verdict(score)
            table.add_row(
                label,
                Text(f"{score:.1f}", style=style),
                Text(verdict, style=style),
                desc,
            )

        # Composite row
        comp_style = _score_style(rubric.composite)
        table.add_row(
            Text("COMPOSITE", style="bold"),
            Text(f"{rubric.composite:.1f}", style=comp_style),
            Text(_score_verdict(rubric.composite), style=comp_style),
            "Weighted overall score",
        )

        return table

    def print(self, rubric: MaintainerRubric, console: Console | None = None) -> None:
        """Print the rubric table to a Rich console."""
        console = console or Console()
        console.print(self.build_table(rubric))
