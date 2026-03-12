"""Render review results as markdown or JSON."""

from __future__ import annotations

from dataclasses import asdict
import json

from coderace.review import SEVERITY_LEVELS
from coderace.types import LaneFinding, ReviewResult
from coderace.maintainer_rubric import MaintainerRubric, score_rubric


def render_review_markdown(result: ReviewResult) -> str:
    """Render a ReviewResult as markdown."""
    lines = [
        "# Code Review Report",
        "",
        (
            f"**Diff:** {len(result.diff_summary['files'])} files, "
            f"+{result.diff_summary['added']} lines, "
            f"-{result.diff_summary['removed']} lines"
        ),
        f"**Agents:** {', '.join(result.agents_used)}  ",
        f"**Lanes:** {', '.join(result.lanes)}",
        f"**Duration:** {result.elapsed_seconds:.1f}s",
        "",
        "---",
        "",
        "## Phase 1: Lane Findings",
        "",
    ]

    for lane in result.lanes:
        lane_findings = [finding for finding in result.phase1_findings if finding.lane == lane]
        agent = lane_findings[0].agent if lane_findings else None
        heading = f"### {_display_lane_name(lane)}"
        if agent:
            heading += f" ({agent})"
        lines.append(heading)
        if not lane_findings:
            lines.extend(["*No findings.*", ""])
            continue
        lines.extend(_render_grouped_findings(lane_findings))
        lines.append("")

    if result.phase2_findings:
        lines.extend(["---", "", "## Phase 2: Cross-Review Synthesis", ""])
        for agent in _ordered_agents(result.phase2_findings):
            agent_findings = [finding for finding in result.phase2_findings if finding.agent == agent]
            lines.append(f"### {agent}")
            lines.extend(_render_grouped_findings(agent_findings))
            lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## Summary",
            "",
            "| Severity | Count |",
            "|----------|-------|",
        ]
    )
    for severity in SEVERITY_LEVELS:
        count = sum(
            1
            for finding in [*result.phase1_findings, *result.phase2_findings]
            if finding.severity == severity
        )
        lines.append(f"| {_display_lane_name(severity)} | {count} |")

    return "\n".join(lines) + "\n"


def render_review_markdown_with_rubric(result: ReviewResult, diff_text: str) -> str:
    """Render a ReviewResult as markdown with an appended Maintainer Rubric section."""
    base = render_review_markdown(result)
    rubric = score_rubric(diff_text)
    rubric_section = _render_rubric_markdown(rubric)
    return base + "\n" + rubric_section


def render_review_json_with_rubric(result: ReviewResult, diff_text: str) -> str:
    """Render a ReviewResult as JSON with a maintainer_rubric key added."""
    data = asdict(result)
    rubric = score_rubric(diff_text)
    data["maintainer_rubric"] = rubric.as_dict()
    return json.dumps(data, indent=2) + "\n"


def _render_rubric_markdown(rubric: MaintainerRubric) -> str:
    """Render a MaintainerRubric as a markdown section."""
    verdict = "✅ Likely accepted" if rubric.composite >= 80 else (
        "⚠️ Review needed" if rubric.composite >= 50 else "❌ Likely rejected"
    )
    lines = [
        "---",
        "",
        "## Maintainer Rubric",
        "",
        f"> METR research (Mar 2026): ~50% of SWE-bench-passing PRs would be rejected by real maintainers.",
        "",
        f"**Composite score:** {rubric.composite:.1f} / 100  {verdict}",
        "",
        "| Dimension | Score | Verdict |",
        "|-----------|------:|---------|",
        f"| Minimal Diff | {rubric.minimal_diff:.1f} | {'✅' if rubric.minimal_diff >= 80 else ('⚠️' if rubric.minimal_diff >= 50 else '❌')} |",
        f"| Convention Adherence | {rubric.convention_adherence:.1f} | {'✅' if rubric.convention_adherence >= 80 else ('⚠️' if rubric.convention_adherence >= 50 else '❌')} |",
        f"| Dep Hygiene | {rubric.dep_hygiene:.1f} | {'✅' if rubric.dep_hygiene >= 80 else ('⚠️' if rubric.dep_hygiene >= 50 else '❌')} |",
        f"| Scope Discipline | {rubric.scope_discipline:.1f} | {'✅' if rubric.scope_discipline >= 80 else ('⚠️' if rubric.scope_discipline >= 50 else '❌')} |",
        f"| Idiomatic Patterns | {rubric.idiomatic_patterns:.1f} | {'✅' if rubric.idiomatic_patterns >= 80 else ('⚠️' if rubric.idiomatic_patterns >= 50 else '❌')} |",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_review_json(result: ReviewResult) -> str:
    """Render a ReviewResult as JSON."""
    return json.dumps(asdict(result), indent=2) + "\n"


def _render_grouped_findings(findings: list[LaneFinding]) -> list[str]:
    lines: list[str] = []
    for severity in SEVERITY_LEVELS:
        grouped = [finding for finding in findings if finding.severity == severity]
        if not grouped:
            continue
        lines.append(f"**{_display_lane_name(severity)}**")
        for finding in grouped:
            if finding.location:
                lines.append(f"- `{finding.location}` - {finding.finding}")
            else:
                lines.append(f"- {finding.finding}")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _ordered_agents(findings: list[LaneFinding]) -> list[str]:
    agents: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        if finding.agent not in seen:
            agents.append(finding.agent)
            seen.add(finding.agent)
    return agents


def _display_lane_name(value: str) -> str:
    return value.replace("-", " ").title()
