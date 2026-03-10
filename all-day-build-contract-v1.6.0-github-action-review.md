# All-Day Build Contract: coderace v1.6.0 — GitHub Action PR Review Mode

Status: In Progress
Date: 2026-03-10
Owner: Codex execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

coderace v1.5.0 ships `coderace review` — a multi-lane, cross-reviewing cooperative code review subcommand. The GitHub Action (action.yml) still only exposes `coderace run` (task mode). No CI integration for review mode exists.

This contract adds first-class PR review support to the GitHub Action: a new `mode: review` input that auto-extracts the PR diff from GitHub context and runs `coderace review` on it, posting results as a PR comment.

The differentiated angle: instead of a single AI reviewer, coderace races multiple agents (Claude Code, Codex, Gemini) reviewing in parallel lanes, then cross-reviews for confidence. The comment shows which reviewer found which issues, with agreement scoring.

This contract is complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end: `pytest tests/ -x -q`
4. New features must ship with docs and CHANGELOG in the same pass.
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside the project directory: ~/repos/coderace/
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing tests and docs before writing new code.

## 3. Context (read before coding)

- Repo: ~/repos/coderace/
- Existing action.yml: handles `coderace run` (task file → score table)
- New in v1.5.0: `coderace review` subcommand with `--diff`, `--commit`, `--branch` inputs
- Review command output: JSON (via `--json-out`) and markdown (via `--md-out`) 
- Review JSON schema: see `coderace/review_report.py` for exact structure
- Existing CI scripts: `scripts/ci-run.sh`, `scripts/format-comment.py`
- Existing tests: `tests/` (run `pytest tests/ -x -q` to verify)
- Current version: 1.5.0 in `pyproject.toml` and `coderace/__init__.py`

## 4. Feature Deliverables

### D1. Add `mode` input to action.yml + new review-mode inputs

Update `action.yml` to support a new `mode: review` operation alongside the existing task-run mode.

New inputs to add:
- `mode`: `run` (default, existing behavior) | `review` (new)
- `diff-source`: `pr` (default for review, uses GitHub PR context) | `commit:<sha>` | `branch:<base>...<head>` | `file:<path>`
- `agents`: already exists — applies to both modes
- `lanes`: comma-separated lane names for review (optional, uses coderace defaults)
- `cross-reviewers`: number of cross-review agents (optional, default 2)
- `json-out`: path for review JSON output (optional)
- `md-out`: path for review markdown output (optional)

The `runs:` section should call different scripts based on `mode` input:
- `mode: run` → existing `scripts/ci-run.sh` (unchanged)
- `mode: review` → new `scripts/ci-review.sh`

Required file changes:
- `action.yml` — add inputs, add conditional step based on mode
- `scripts/ci-review.sh` — new script (see D2)

- [ ] New inputs added with correct defaults and descriptions
- [ ] `run: using: composite` section updated with conditional steps
- [ ] `mode: run` path still works exactly as before (no regression)
- [ ] `outputs` section updated to include `review-json` and `review-md` outputs

### D2. New script: scripts/ci-review.sh

New bash script that handles `coderace review` in CI context.

Logic:
1. Determine diff source from `CODERACE_DIFF_SOURCE` env var (set by action.yml)
2. For `pr` source: extract diff using `git diff origin/${{ github.base_ref }}...HEAD` (available in PR checkout context)
3. Build `coderace review` command with appropriate flags
4. Run it, capture JSON output to a predictable path
5. Emit `review-json` and `review-md` outputs to `$GITHUB_OUTPUT`

Required:
- `scripts/ci-review.sh`

- [ ] Handles `CODERACE_DIFF_SOURCE=pr` (auto from PR context)
- [ ] Handles `CODERACE_DIFF_SOURCE=commit:<sha>`
- [ ] Handles `CODERACE_DIFF_SOURCE=branch:<base>...<head>`
- [ ] Handles `CODERACE_DIFF_SOURCE=file:<path>` (reads file)
- [ ] Exits non-zero on `coderace review` failure
- [ ] Emits `review-json` and `review-md` to GITHUB_OUTPUT
- [ ] Handles empty diff gracefully (no agents to run, informational message)

### D3. New script: scripts/format-review-comment.py

A Python script that takes the review JSON and formats it as a GitHub PR comment (separate from the existing `format-comment.py` which handles task-run results).

The review JSON schema is different from run results — check `coderace/review_report.py` to understand the structure before writing this.

The comment should include:
- Header: "## coderace review — [N agents, M lanes]"
- Summary: issues found, agreement score, top findings
- Per-lane section: which agent ran which lane, what they found
- Cross-review section: which issues were confirmed by cross-reviewers
- Collapsible raw JSON section

Required:
- `scripts/format-review-comment.py`

- [ ] Reads review JSON from `--json-file` argument
- [ ] Outputs markdown to `--output` argument  
- [ ] Handles missing/empty JSON gracefully
- [ ] Correctly renders both "issues found" and "no issues found" cases
- [ ] Comment body includes `<!-- coderace-review -->` marker (for find-and-update in action.yml)

### D4. Example workflow for users

Add an example GitHub Actions workflow that users can copy to enable coderace review on their PRs.

Required:
- `.github/workflows/examples/coderace-pr-review.yml`

The example should:
- Trigger on `pull_request` events
- Checkout with `fetch-depth: 0` (needed for git diff)
- Use `mode: review` with `diff-source: pr`
- Show how to configure agents and pass API keys as secrets

- [ ] Example workflow is valid YAML
- [ ] Comments in the example explain each non-obvious step
- [ ] Example is minimal but complete (runnable with secrets configured)

### D5. Docs, CHANGELOG, version bump, tests

Update README with a "PR Review" section, update CHANGELOG, bump version to 1.6.0, add tests.

README section to add (after the existing GitHub Action section):
- "### Automated PR Review" subsection
- Explains the mode: review differentiation (multiple agents, cross-review)  
- Copy-pasteable minimal workflow
- Table showing what the PR comment looks like

Tests to add:
- `tests/test_github_action_review.py` or additions to existing GitHub Action test file if one exists
- Unit tests for `format-review-comment.py` (test with sample review JSON from `coderace/review_report.py`)
- Integration smoke test: `coderace review --diff /dev/null --json-out /tmp/test.json` exits without error (empty diff case)

Required changes:
- `README.md` — add PR Review section
- `CHANGELOG.md` — add v1.6.0 section
- `pyproject.toml` — bump version to 1.6.0
- `coderace/__init__.py` — bump `__version__` to "1.6.0"
- `tests/test_github_action_review.py` (or equivalent)

- [ ] README updated with PR review section + minimal workflow example
- [ ] CHANGELOG updated
- [ ] Version bumped to 1.6.0 in both pyproject.toml and __init__.py
- [ ] Tests for format-review-comment.py pass
- [ ] Integration smoke test passes
- [ ] All 633 existing tests still pass

## 5. Test Requirements

- [ ] All existing tests pass: `pytest tests/ -x -q` (baseline: 633 tests)
- [ ] New tests added for D3 (format-review-comment.py)
- [ ] Empty diff case doesn't crash the review pipeline
- [ ] `mode: run` backward compatibility: action.yml with no `mode` input still works as v1.5.0

## 6. Reports

Write progress to `progress-log.md` in the repo root after each deliverable.
Include: what was built, what tests pass, what's next, any blockers.
Final summary when all deliverables done or stopped.

## 7. Stop Conditions

- All deliverables checked and all tests passing → DONE. Write final progress-log entry.
- 3 consecutive failed attempts on same issue → STOP, write blocker report to progress-log.md
- Scope creep detected → STOP, note what's new in progress-log.md
- All tests passing but deliverables remain → continue to next deliverable

## 8. Final Deliverable Checklist

- [ ] D1: action.yml updated with mode + review inputs
- [ ] D2: scripts/ci-review.sh created and working
- [ ] D3: scripts/format-review-comment.py created and working  
- [ ] D4: .github/workflows/examples/coderace-pr-review.yml created
- [ ] D5: README, CHANGELOG, version 1.6.0, tests
- [ ] All 633+ tests pass
- [ ] Git committed (one commit per deliverable)
- [ ] `git push origin main` executed
