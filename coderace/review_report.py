"""Render review results as markdown or JSON."""

from __future__ import annotations

from dataclasses import asdict
import json

from coderace.review import SEVERITY_LEVELS
from coderace.types import LaneFinding, ReviewResult


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
