#!/usr/bin/env python3
"""format-review-comment.py — Format coderace review JSON as a GitHub PR comment.

Usage:
    python format-review-comment.py --json-file /tmp/coderace-review.json \\
                                    --output /tmp/review-comment.md

Reads the JSON produced by `coderace review --format json` and writes a markdown
comment body suitable for posting to a GitHub PR.  The output includes:
  - Header with agent/lane counts
  - Summary: total issues, severity breakdown, top findings
  - Per-lane section showing what each agent found
  - Cross-review section (Phase 2) if present
  - Collapsible raw JSON

The comment body includes <!-- coderace-review --> for find-and-update in action.yml.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SEVERITY_ORDER = ["critical", "error", "warning", "info", "suggestion"]
SEVERITY_EMOJI = {
    "critical": "🔴",
    "error": "🟠",
    "warning": "🟡",
    "info": "🔵",
    "suggestion": "⚪",
}


def _display(value: str) -> str:
    """Convert kebab-case to Title Case for display."""
    return value.replace("-", " ").title()


def format_header(data: dict) -> str:
    """Build the comment header line."""
    agents = data.get("agents_used", [])
    lanes = data.get("lanes", [])
    n_agents = len(agents)
    n_lanes = len(lanes)
    elapsed = data.get("elapsed_seconds", 0.0)
    return (
        f"## coderace review — {n_agents} agent(s), {n_lanes} lane(s) "
        f"| {elapsed:.1f}s\n"
    )


def _count_findings(findings: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def format_summary(data: dict) -> str:
    """Build the summary section."""
    p1 = data.get("phase1_findings", [])
    p2 = data.get("phase2_findings", [])
    all_findings = p1 + p2
    counts = _count_findings(all_findings)

    if not all_findings:
        return "**No issues found.** ✅\n"

    total = len(all_findings)
    parts: list[str] = [f"**{total} finding(s)** across all lanes and phases."]
    sev_parts: list[str] = []
    for sev in SEVERITY_ORDER:
        if counts.get(sev, 0) > 0:
            emoji = SEVERITY_EMOJI.get(sev, "")
            sev_parts.append(f"{emoji} {counts[sev]} {_display(sev)}")
    if sev_parts:
        parts.append("  ".join(sev_parts))

    # Top critical/error findings (up to 3)
    top = [
        f
        for f in all_findings
        if f.get("severity") in ("critical", "error")
    ][:3]
    if top:
        parts.append("\n**Top findings:**")
        for f in top:
            loc = f.get("location") or ""
            finding = f.get("finding", "")
            sev = f.get("severity", "")
            emoji = SEVERITY_EMOJI.get(sev, "")
            if loc:
                parts.append(f"- {emoji} `{loc}` — {finding}")
            else:
                parts.append(f"- {emoji} {finding}")

    return "\n".join(parts) + "\n"


def format_lane_section(data: dict) -> str:
    """Build the Phase 1 per-lane findings section."""
    lanes = data.get("lanes", [])
    p1 = data.get("phase1_findings", [])

    if not lanes:
        return ""

    lines = ["## Phase 1: Lane Findings\n"]
    for lane in lanes:
        lane_findings = [f for f in p1 if f.get("lane") == lane]
        agent = lane_findings[0].get("agent", "") if lane_findings else ""
        heading = f"### {_display(lane)}"
        if agent:
            heading += f" ({agent})"
        lines.append(heading)

        if not lane_findings:
            lines.append("_No findings._\n")
            continue

        for sev in SEVERITY_ORDER:
            grouped = [f for f in lane_findings if f.get("severity") == sev]
            if not grouped:
                continue
            emoji = SEVERITY_EMOJI.get(sev, "")
            lines.append(f"**{emoji} {_display(sev)}**")
            for f in grouped:
                loc = f.get("location") or ""
                finding = f.get("finding", "")
                if loc:
                    lines.append(f"- `{loc}` — {finding}")
                else:
                    lines.append(f"- {finding}")
            lines.append("")

    return "\n".join(lines)


def format_cross_review_section(data: dict) -> str:
    """Build the Phase 2 cross-review section."""
    p2 = data.get("phase2_findings", [])
    if not p2:
        return ""

    # Group by agent
    agents_ordered: list[str] = []
    seen: set[str] = set()
    for f in p2:
        agent = f.get("agent", "")
        if agent not in seen:
            agents_ordered.append(agent)
            seen.add(agent)

    lines = ["## Phase 2: Cross-Review Synthesis\n"]
    for agent in agents_ordered:
        agent_findings = [f for f in p2 if f.get("agent") == agent]
        lines.append(f"### {agent}")
        for sev in SEVERITY_ORDER:
            grouped = [f for f in agent_findings if f.get("severity") == sev]
            if not grouped:
                continue
            emoji = SEVERITY_EMOJI.get(sev, "")
            lines.append(f"**{emoji} {_display(sev)}**")
            for f in grouped:
                loc = f.get("location") or ""
                finding = f.get("finding", "")
                if loc:
                    lines.append(f"- `{loc}` — {finding}")
                else:
                    lines.append(f"- {finding}")
            lines.append("")

    return "\n".join(lines)


def format_diff_summary(data: dict) -> str:
    """Format the diff summary line."""
    ds = data.get("diff_summary", {})
    files = ds.get("files", [])
    added = ds.get("added", 0)
    removed = ds.get("removed", 0)
    if not files and added == 0 and removed == 0:
        return ""
    return (
        f"**Diff:** {len(files)} file(s)  "
        f"+{added} / -{removed} lines\n"
    )


def format_review_comment(data: dict, json_raw: str = "") -> str:
    """Produce the full markdown comment body for a review result.

    Args:
        data: Parsed review JSON (dict matching ReviewResult schema).
        json_raw: Raw JSON string for the collapsible details section.

    Returns:
        Markdown string ready to POST to GitHub API.
    """
    parts: list[str] = [
        "<!-- coderace-review -->",
        "",
        format_header(data),
        format_diff_summary(data),
        "---",
        "",
        format_summary(data),
        "",
    ]

    lane_section = format_lane_section(data)
    if lane_section:
        parts += [lane_section, ""]

    cross_section = format_cross_review_section(data)
    if cross_section:
        parts += [cross_section, ""]

    if json_raw:
        parts += [
            "---",
            "",
            "<details>",
            "<summary>Raw JSON</summary>",
            "",
            "```json",
            json_raw.strip(),
            "```",
            "",
            "</details>",
            "",
        ]

    parts += [
        "---",
        "_Generated by [coderace](https://github.com/mikiships/coderace)_",
    ]

    return "\n".join(parts)


def format_empty_comment(reason: str = "") -> str:
    """Return a placeholder comment when no review data is available."""
    msg = f"**coderace review**: {reason}" if reason else "**coderace review**: no results."
    return f"<!-- coderace-review -->\n\n{msg}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Format coderace review JSON as a GitHub PR comment."
    )
    parser.add_argument(
        "--json-file",
        required=True,
        help="Path to the coderace review JSON file.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output file path (default: stdout).",
    )
    args = parser.parse_args(argv)

    json_path = Path(args.json_file)

    if not json_path.exists():
        comment = format_empty_comment("JSON file not found.")
    else:
        raw = json_path.read_text(encoding="utf-8").strip()
        if not raw:
            comment = format_empty_comment("Empty results file.")
        else:
            try:
                data = json.loads(raw)
                comment = format_review_comment(data, json_raw=raw)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                print(f"Warning: could not parse review JSON: {exc}", file=sys.stderr)
                comment = format_empty_comment(f"Could not parse results: {exc}")

    if args.output == "-":
        sys.stdout.write(comment + "\n")
    else:
        Path(args.output).write_text(comment + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
