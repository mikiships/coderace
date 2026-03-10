"""Core review engine for multi-lane agent review."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Callable, Iterable

from coderace.adapters import ADAPTERS, instantiate_adapter, parse_agent_spec
from coderace.commands.diff import parse_diff_summary
from coderace.types import AgentResult, LaneFinding, ReviewResult

DEFAULT_REVIEW_LANES = [
    "null-safety",
    "type-safety",
    "error-handling",
    "contracts",
]

DEFAULT_REVIEW_AGENTS = ["claude", "codex"]

SEVERITY_LEVELS = ("critical", "warning", "info")
SEVERITY_ORDER = {name: index for index, name in enumerate(SEVERITY_LEVELS)}

LANE_DEFINITIONS: dict[str, str] = {
    "null-safety": (
        "Focus on null or None dereferences, missing guards, "
        "and unchecked optional values."
    ),
    "type-safety": (
        "Focus on type mismatches, coercion bugs, invalid assumptions, "
        "and missing annotations."
    ),
    "error-handling": (
        "Focus on uncaught exceptions, missing failure paths, "
        "swallowed errors, and incomplete recovery."
    ),
    "contracts": (
        "Focus on API contracts, preconditions, postconditions, "
        "invariants, and interface mismatches."
    ),
    "security": (
        "Focus on injection, auth bypass, unsafe deserialization, "
        "privilege mistakes, and secrets exposure."
    ),
    "performance": (
        "Focus on avoidable O(n^2) work, blocking calls, hot-path allocations, "
        "and needless repeated work."
    ),
}

_LOCATION_PATTERN = re.compile(r"(?P<location>[A-Za-z0-9_./-]+:\d+)")
_FINDINGS_JSON_PATTERN = re.compile(r"\{[\s\S]*\}")


def build_lane_prompt(diff: str, lane: str) -> str:
    """Build the deterministic prompt for a single review lane."""
    lane_prompt = LANE_DEFINITIONS.get(lane)
    if lane_prompt is None:
        raise ValueError(f"Unknown review lane: {lane}")

    return (
        "You are performing a code review on a git diff.\n"
        f"Lane: {lane}\n"
        f"Focus: {lane_prompt}\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        '{\n  "findings": [\n    {\n      "severity": "critical|warning|info",\n'
        '      "location": "path/to/file.py:123 or null",\n'
        '      "finding": "single concise finding"\n'
        "    }\n  ]\n}\n\n"
        "Rules:\n"
        "- Review only the provided diff.\n"
        "- Report concrete issues only. If there are no issues, return {\"findings\": []}.\n"
        "- Keep findings concise and deterministic.\n"
        "- Do not propose code changes outside the finding text.\n\n"
        f"Diff:\n```diff\n{diff}\n```"
    )


def build_cross_review_prompt(diff: str, phase1_findings: list[LaneFinding]) -> str:
    """Build the cross-review prompt used in phase 2."""
    findings_payload = json.dumps(
        [asdict(finding) for finding in phase1_findings],
        indent=2,
        sort_keys=True,
    )
    return (
        "You are performing a cross-review of prior code review findings.\n"
        "Identify missing issues, weak claims, or disagreements across lanes.\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        '{\n  "findings": [\n    {\n      "severity": "critical|warning|info",\n'
        '      "location": "path/to/file.py:123 or null",\n'
        '      "finding": "gap, disagreement, or synthesis note"\n'
        "    }\n  ]\n}\n\n"
        "Rules:\n"
        "- Use severity=critical only when a missed issue is release-blocking.\n"
        "- Reference a location when possible.\n"
        "- If Phase 1 is complete and consistent, return {\"findings\": []}.\n\n"
        f"Phase 1 findings:\n```json\n{findings_payload}\n```\n\n"
        f"Diff:\n```diff\n{diff}\n```"
    )


def parse_agent_output_for_findings(
    output: str,
    lane: str,
    agent: str = "",
) -> list[LaneFinding]:
    """Parse agent output into structured findings."""
    json_findings = _parse_json_findings(output, lane, agent)
    if json_findings is not None:
        return json_findings

    text_findings = _parse_text_findings(output, lane, agent)
    return text_findings


def run_review(
    diff: str,
    lanes: list[str],
    agents: list[str],
    cross_review: bool = False,
    workdir: Path | None = None,
    timeout: int = 300,
    runner: Callable[[str, str, Path, int], AgentResult] | None = None,
) -> ReviewResult:
    """Run a multi-lane review and return the consolidated result."""
    resolved_lanes = _normalize_lanes(lanes)
    if not agents:
        raise ValueError("At least one review agent is required")

    resolved_workdir = workdir or Path.cwd()
    review_runner = runner or _run_adapter_review
    started_at = monotonic()

    phase1_assignments = [
        (lane, agents[index % len(agents)])
        for index, lane in enumerate(resolved_lanes)
    ]

    phase1_results: list[tuple[str, str, AgentResult]] = []
    with ThreadPoolExecutor(max_workers=max(1, len(phase1_assignments))) as executor:
        futures = [
            executor.submit(
                review_runner,
                agent_spec,
                build_lane_prompt(diff, lane),
                resolved_workdir,
                timeout,
            )
            for lane, agent_spec in phase1_assignments
        ]
        for (lane, agent_spec), future in zip(phase1_assignments, futures):
            phase1_results.append((lane, agent_spec, future.result()))

    phase1_findings: list[LaneFinding] = []
    ordered_agents: list[str] = []
    for lane, agent_spec, result in phase1_results:
        ordered_agents.append(result.agent or agent_spec)
        findings = parse_agent_output_for_findings(
            result.stdout,
            lane,
            agent=result.agent or agent_spec,
        )
        if not findings and (result.exit_code != 0 or result.timed_out):
            failure_reason = "timed out" if result.timed_out else f"exit code {result.exit_code}"
            findings = [
                LaneFinding(
                    lane=lane,
                    agent=result.agent or agent_spec,
                    severity="warning",
                    finding=f"Review agent failed to return findings ({failure_reason}).",
                    location=None,
                )
            ]
        phase1_findings.extend(findings)

    phase2_findings: list[LaneFinding] = []
    if cross_review:
        phase2_assignments = [agents[index % len(agents)] for index in range(2)]
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    review_runner,
                    agent_spec,
                    build_cross_review_prompt(diff, phase1_findings),
                    resolved_workdir,
                    timeout,
                )
                for agent_spec in phase2_assignments
            ]
            for agent_spec, future in zip(phase2_assignments, futures):
                result = future.result()
                ordered_agents.append(result.agent or agent_spec)
                findings = parse_agent_output_for_findings(
                    result.stdout,
                    "cross-review",
                    agent=result.agent or agent_spec,
                )
                if not findings and (result.exit_code != 0 or result.timed_out):
                    failure_reason = (
                        "timed out" if result.timed_out else f"exit code {result.exit_code}"
                    )
                    findings = [
                        LaneFinding(
                            lane="cross-review",
                            agent=result.agent or agent_spec,
                            severity="warning",
                            finding=(
                                "Cross-review agent failed to return findings "
                                f"({failure_reason})."
                            ),
                            location=None,
                        )
                    ]
                phase2_findings.extend(findings)

    return ReviewResult(
        diff_summary=parse_diff_summary(diff),
        lanes=resolved_lanes,
        phase1_findings=phase1_findings,
        phase2_findings=phase2_findings,
        agents_used=_ordered_unique(ordered_agents),
        elapsed_seconds=monotonic() - started_at,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _normalize_lanes(lanes: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for lane in lanes:
        lane_name = lane.strip()
        if not lane_name:
            continue
        if lane_name not in LANE_DEFINITIONS:
            raise ValueError(f"Unknown review lane: {lane_name}")
        if lane_name not in seen:
            normalized.append(lane_name)
            seen.add(lane_name)
    if not normalized:
        raise ValueError("At least one review lane is required")
    return normalized


def _ordered_unique(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _run_adapter_review(agent_spec: str, prompt: str, workdir: Path, timeout: int) -> AgentResult:
    agent_name, _ = parse_agent_spec(agent_spec)
    if agent_name not in ADAPTERS:
        raise ValueError(f"Unknown agent: {agent_spec}")
    adapter = instantiate_adapter(agent_spec)
    return adapter.run(prompt, workdir, timeout, no_cost=True)


def _parse_json_findings(output: str, lane: str, agent: str) -> list[LaneFinding] | None:
    text = output.strip()
    if not text:
        return []

    candidates = [text]
    fenced_json = re.findall(r"```json\s*([\s\S]*?)```", output, flags=re.IGNORECASE)
    candidates.extend(item.strip() for item in fenced_json if item.strip())
    generic_match = _FINDINGS_JSON_PATTERN.search(output)
    if generic_match is not None:
        candidates.append(generic_match.group(0).strip())

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict):
            raw_findings = payload.get("findings", [])
        elif isinstance(payload, list):
            raw_findings = payload
        else:
            continue

        findings: list[LaneFinding] = []
        if not isinstance(raw_findings, list):
            return []
        for item in raw_findings:
            if not isinstance(item, dict):
                continue
            severity = _normalize_severity(str(item.get("severity", "info")))
            finding_text = str(item.get("finding", "")).strip()
            location = _normalize_location(item.get("location"))
            if not finding_text:
                continue
            findings.append(
                LaneFinding(
                    lane=lane,
                    agent=agent,
                    severity=severity,
                    finding=finding_text,
                    location=location,
                )
            )
        return findings

    return None


def _parse_text_findings(output: str, lane: str, agent: str) -> list[LaneFinding]:
    findings: list[LaneFinding] = []
    current_severity = "warning"

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lowered = line.strip("*").strip().lower().rstrip(":")
        if lowered in SEVERITY_LEVELS:
            current_severity = lowered
            continue

        line_is_structured = False
        prefixed = re.match(r"^(critical|warning|info)\s*[:|-]\s*(.+)$", line, flags=re.IGNORECASE)
        if prefixed:
            current_severity = _normalize_severity(prefixed.group(1))
            line = prefixed.group(2).strip().lstrip("|").strip()
            line_is_structured = True

        bullet = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", line)
        if bullet:
            line = bullet.group(1).strip()
            line_is_structured = True

        if not line:
            continue

        location = None
        finding_text = line

        pipe_parts = [part.strip(" `") for part in line.split("|")]
        if len(pipe_parts) >= 3 and _looks_like_location(pipe_parts[1]):
            current_severity = _normalize_severity(pipe_parts[0])
            location = _normalize_location(pipe_parts[1])
            finding_text = pipe_parts[2]
            line_is_structured = True
        elif len(pipe_parts) >= 2 and line_is_structured and _looks_like_location(pipe_parts[0]):
            location = _normalize_location(pipe_parts[0])
            finding_text = pipe_parts[1]
        else:
            match = _LOCATION_PATTERN.search(line)
            if match:
                location = match.group("location")
                finding_text = line[match.end():].strip(" -:\u2014")
                line_is_structured = True
            else:
                finding_text = line.strip(" -:\u2014")

        if not line_is_structured or not finding_text:
            continue
        findings.append(
            LaneFinding(
                lane=lane,
                agent=agent,
                severity=current_severity,
                finding=finding_text,
                location=location,
            )
        )

    return findings


def _normalize_severity(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in SEVERITY_ORDER:
        return lowered
    return "info"


def _looks_like_location(value: str) -> bool:
    return _LOCATION_PATTERN.fullmatch(value.strip()) is not None


def _normalize_location(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip("`")
    if not text or text.lower() == "null":
        return None
    if _looks_like_location(text):
        return text
    return None
