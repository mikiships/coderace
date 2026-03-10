# All-Day Build Contract: coderace review mode

Status: In Progress
Date: 2026-03-10
Owner: Claude Code sub-agent
Scope type: Deliverable-gated

## 1. Objective

Add `coderace review` — a multi-agent, lane-isolated code review command that productizes the @doodlestein multi-agent review pattern. Unlike `coderace diff` (which generates a task YAML), `coderace review` runs agents directly, each focused on a distinct review lane (e.g. null-safety, type-safety, error-handling, contracts), aggregates their findings, and optionally runs a Phase 2 cross-review where additional agents critique Phase 1 output.

Distribution angle: r/ClaudeCode thread "How can I make agents challenge each other instead of agreeing?" — this answers that question as a first-class CLI command.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end (604 baseline + new tests).
4. New features must ship with docs and CHANGELOG in the same pass.
5. CLI outputs must be deterministic and schema-backed.
6. Never modify files outside the project directory.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report to `progress-log.md`.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing code (diff.py, race.py, cli.py, types.py, adapters/) before writing.

## 3. Feature Deliverables

### D1. Core review engine (`coderace/review.py`)

Build the review execution engine. This is NOT a task YAML generator — it runs agents directly.

A "lane" is a named review focus. Built-in lanes:
- `null-safety`: null/None dereferences, missing guards
- `type-safety`: type mismatches, coercion bugs, missing annotations
- `error-handling`: uncaught exceptions, missing error paths, swallowed errors
- `contracts`: API contracts, pre/post-conditions, interface violations
- `security`: injection, auth bypass, unsafe deserialization, secrets in code
- `performance`: O(n²) loops, unnecessary allocations, blocking calls

Review flow:
1. **Phase 1 (parallel):** N agents, one per lane, each receives the diff + lane-specific prompt. Runs concurrently. Collects findings per lane.
2. **Phase 2 (optional, `--cross-review`):** 2 agents receive Phase 1 output + diff, asked to identify gaps and disagreements.
3. Output: consolidated `ReviewResult` with per-lane findings + Phase 2 synthesis.

Data structures (add to `types.py`):
```python
@dataclass
class LaneFinding:
    lane: str
    agent: str
    severity: str  # "critical" | "warning" | "info"
    finding: str
    location: str | None  # file:line if parseable

@dataclass  
class ReviewResult:
    diff_summary: dict[str, object]   # reuse parse_diff_summary
    lanes: list[str]
    phase1_findings: list[LaneFinding]
    phase2_findings: list[LaneFinding]  # empty if no cross-review
    agents_used: list[str]
    elapsed_seconds: float
    timestamp: str
```

Required files:
- `coderace/review.py` — engine
- `coderace/types.py` — extend with above dataclasses
- `coderace/review_report.py` — rendering (see D3)

- [ ] LaneFinding and ReviewResult dataclasses in types.py
- [ ] Lane definitions dict with per-lane prompts
- [ ] run_review(diff, lanes, agents, cross_review=False) -> ReviewResult
- [ ] Phase 1: parallel execution via ThreadPoolExecutor (mirror race.py pattern)
- [ ] Phase 2: cross-review execution (optional)
- [ ] parse_agent_output_for_findings(output, lane) — extract structured findings
- [ ] Tests for D1

### D2. CLI command (`coderace/commands/review.py` + cli.py integration)

New command: `coderace review`

```
Usage: coderace review [OPTIONS]

  Run multi-lane parallel agent review on a diff.

Options:
  --diff FILE         Read diff from file (default: stdin)
  --commit TEXT       Generate diff from commit ref (e.g. HEAD~1, abc123)
  --branch TEXT       Generate diff from branch range (e.g. main...my-branch)
  --lanes TEXT        Comma-separated lanes [default: null-safety,type-safety,error-handling,contracts]
  --agents TEXT       Comma-separated agents [default: claude,codex]
  --cross-review      Run Phase 2 cross-review after Phase 1
  --output FILE       Write report to file (default: stdout)
  --format TEXT       Output format: markdown|json [default: markdown]
  --no-color          Plain output (no rich markup)
  --help              Show this message and exit.
```

Input sources (pick first that's provided):
1. `--diff FILE` — read diff from file
2. `--commit TEXT` — run `git diff <ref>~1 <ref>` in cwd
3. `--branch TEXT` — run `git diff <base>...<head>` in cwd
4. stdin — if no option, read diff from stdin (with helpful error if stdin is TTY)

Required files:
- `coderace/commands/review.py`
- `coderace/cli.py` — add `from coderace.commands.review import app as review_app` + `app.add_typer(review_app, name="review")`

- [ ] review.py command module with typer app
- [ ] All 4 input sources working
- [ ] --format json outputs ReviewResult as JSON
- [ ] --output writes to file
- [ ] cli.py integration (review subcommand registered)
- [ ] Tests for D2

### D3. Report renderer (`coderace/review_report.py`)

Markdown report format:

```markdown
# Code Review Report

**Diff:** 3 files, +45 lines, -12 lines
**Agents:** claude, codex  
**Lanes:** null-safety, type-safety, error-handling, contracts
**Duration:** 23.4s

---

## Phase 1: Lane Findings

### Null Safety (claude)
**Critical**
- `auth/validators.py:42` — `user.email` accessed without None check after optional query

**Warning**  
- `api/handlers.py:87` — return value of `cache.get()` used without None guard

### Type Safety (codex)
*No findings.*

### Error Handling (claude)
**Warning**
- `api/handlers.py:102` — `ValueError` from `int(request.data['id'])` not caught

### Contracts (codex)
**Info**
- `api/handlers.py:15` — missing docstring on public endpoint, contract unclear

---

## Phase 2: Cross-Review Synthesis

**Agent:** claude (reviewing all Phase 1 findings)

The null-safety finding at `auth/validators.py:42` interacts with the contracts finding — 
the missing docstring makes it unclear whether `None` is a valid input...

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 1 |
| Warning  | 2 |
| Info     | 1 |
```

Required files:
- `coderace/review_report.py`

- [ ] render_review_markdown(result: ReviewResult) -> str
- [ ] render_review_json(result: ReviewResult) -> str
- [ ] Severity grouping within each lane section
- [ ] Summary table at end
- [ ] Phase 2 section only rendered if phase2_findings non-empty
- [ ] Tests for D3 (snapshot-style: render known ReviewResult, assert key strings present)

### D4. Integration test

End-to-end test using a canned diff string (no real agent needed — mock the agent runner).

- [ ] `tests/test_review.py` — full integration test
- [ ] Mock adapters that return canned review text per lane
- [ ] Assert ReviewResult structure is correct
- [ ] Assert markdown report contains expected sections
- [ ] Assert JSON output is valid and matches schema
- [ ] Assert CLI via typer test client (CliRunner): `coderace review --diff tests/fixtures/sample.patch`
- [ ] Add `tests/fixtures/sample.patch` — a small 3-file realistic diff
- [ ] All 604 existing tests still pass
- [ ] New test count: 604 + at least 25 new tests

### D5. Documentation, CHANGELOG, version bump

- [ ] README.md: add `coderace review` section after the `coderace diff` section
  - One-liner description
  - Quick examples (stdin pipe, --commit, --branch, --cross-review)
  - Lane reference table
- [ ] CHANGELOG.md: v1.5.0 entry with Added section
- [ ] Version bump: `1.4.1` → `1.5.0` in `pyproject.toml` and `coderace/__init__.py`
- [ ] Commit: "D5: Docs, CHANGELOG, v1.5.0 bump"

## 4. Test Requirements

- [ ] Unit tests for lane prompt generation
- [ ] Unit tests for parse_agent_output_for_findings (3+ input formats)
- [ ] Unit tests for ReviewResult → markdown rendering
- [ ] Unit tests for ReviewResult → JSON rendering
- [ ] Integration test: full review pipeline with mocked agents
- [ ] CLI test via CliRunner: stdin, --diff file, --commit, --format json
- [ ] All 604 existing tests still pass
- [ ] Final count: 604 + ≥25 new tests

## 5. Reports

Write progress to `progress-log.md` after each deliverable. Include:
- What was built
- Test count
- Any blockers
Final summary when all deliverables done.

## 6. Stop Conditions

- All deliverables checked and all tests passing → DONE, write final summary to progress-log.md
- 3 consecutive failed attempts on same issue → STOP, write blocker report
- Scope creep detected → STOP, report what's new
- Tests fail persistently after 3 fix attempts → STOP with report
