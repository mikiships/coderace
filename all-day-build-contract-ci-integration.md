# All-Day Build Contract: CI Integration (v0.3.0)

Status: In Progress
Date: 2026-02-24
Owner: Sub-agent execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add GitHub Actions integration to coderace so users can race coding agents in CI and see results as PR comments. Also add a `coderace diff` command that auto-generates a task YAML from a git diff, making it trivial to race agents on real PR changes. This makes coderace useful beyond local development -- teams can benchmark agents as part of their workflow.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end.
4. New features must ship with docs and report addendum updates in the same pass.
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside the project directory.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing tests and docs before writing new code.

## 3. Feature Deliverables

### D1. `coderace diff` command (core + CLI)

Generate a task YAML from a git diff. Takes a diff (stdin or file) and produces a coderace task that describes the changes and asks agents to review/fix/improve them.

Required files:
- `coderace/commands/diff.py`
- `tests/test_diff.py`

- [ ] `coderace diff` reads git diff from stdin or `--file`
- [ ] Generates valid task YAML with description derived from diff
- [ ] Supports `--mode review` (review the changes), `--mode fix` (fix issues in the diff), `--mode improve` (improve the code)
- [ ] Supports `--agents` flag to specify which agents to include
- [ ] Output goes to stdout or `--output` file
- [ ] Tests for D1 (at least 5 tests covering modes, input sources, edge cases)

### D2. GitHub Action definition

Create `.github/action.yml` and supporting script that runs coderace in CI and posts results as a PR comment.

Required files:
- `action.yml` (root of repo, GitHub composite action)
- `scripts/ci-run.sh` (entrypoint script)
- `scripts/format-comment.py` (format results as markdown PR comment)

- [ ] `action.yml` composite action definition with inputs: task, agents, parallel, github-token
- [ ] `ci-run.sh` installs coderace, runs the task, captures results
- [ ] `format-comment.py` reads JSON results and produces markdown table + summary
- [ ] Posts results as PR comment via GitHub API (using github-token)
- [ ] Updates existing comment on re-run (doesn't spam new comments)
- [ ] Tests for D2 (format-comment output tests, at least 3)

### D3. Example CI workflow

A ready-to-copy workflow file that users drop into their repo.

Required files:
- `examples/ci-race-on-pr.yml`
- Updated `README.md` with CI section

- [ ] Example workflow: triggered on `pull_request`, uses the action
- [ ] Example workflow: triggered on label `race-agents`, uses the action
- [ ] README.md updated with "CI Integration" section showing both workflows
- [ ] README.md updated with `coderace diff` usage

### D4. Markdown/JSON output format for `coderace results`

Add `--format markdown` flag to `coderace results` for CI-friendly output.

Required files:
- Modified `coderace/commands/results.py`
- `tests/test_results_format.py`

- [ ] `coderace results task.yaml --format markdown` produces clean markdown table
- [ ] `coderace results task.yaml --format json` already works (verify)
- [ ] Markdown output includes: rank, agent, score, test/lint/exit status, time, lines
- [ ] Tests for D4 (at least 3 tests)

## 4. Test Requirements

- [ ] Unit tests for each deliverable
- [ ] All existing 77 tests must still pass
- [ ] Edge cases: empty diff, binary files in diff, no agents specified, missing github-token
- [ ] `ruff check .` passes clean

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
