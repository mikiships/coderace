# All-Day Build Contract: Verification Tests (v0.9.0)

Status: In Progress
Date: 2026-02-27
Owner: Codex execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add "verification tests" to coderace: pre-written test suites that run AFTER an agent completes a task, validating the agent's implementation against a known standard. Currently agents score 100% because they write their own tests and naturally make them pass. Verification tests solve this by providing an independent quality check the agent doesn't control.

New YAML fields:
- `verify_command`: command to run verification tests (e.g., `python3 -m pytest verify_fibonacci.py -x -q`)
- `verify_files`: dict of `{filename: content}` that get written into the task workspace BEFORE `verify_command` runs

Scoring changes:
- If task has `verify_command`: tests=25, verify=30, exit=20, lint=15, time=5, lines=5
- If task has NO `verify_command`: scoring unchanged (backward compatible)

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

### D1. Verification Test Runner (core engine)

Add verification test support to the coderace runner. After an agent completes a task and the normal `test_command` runs, if the task has `verify_command` and `verify_files`:
1. Write each file from `verify_files` into the task workspace (overwriting any agent-written file with the same name is OK — that's the point)
2. Run `verify_command` in the workspace
3. Capture pass/fail/output the same way `test_command` is captured
4. Add `verify_score`, `verify_output`, `verify_passed` to the result

Required files to modify:
- `coderace/runner.py` (or wherever task execution happens)
- `coderace/models.py` or result dataclasses

Read the existing runner code first to understand the execution flow.

- [ ] Parse `verify_command` and `verify_files` from task YAML
- [ ] Write verify_files to workspace after agent completes
- [ ] Run verify_command and capture results
- [ ] Add verify fields to result model
- [ ] Tests for D1

### D2. Scoring Engine Update

Update the scoring engine to incorporate verification test results.

When a task has `verify_command`:
- `tests` weight: 25 (agent's own tests)
- `verify` weight: 30 (verification tests)
- `exit` weight: 20
- `lint` weight: 15
- `time` weight: 5
- `lines` weight: 5

When a task does NOT have `verify_command`:
- Keep existing scoring unchanged (backward compatible)

The task YAML can also override these weights with a `scoring:` section as it already does.

Required files to modify:
- `coderace/scoring.py` (or wherever scoring happens)

- [ ] Add verify score calculation
- [ ] Update weight distribution when verify_command present
- [ ] Backward compatibility: no verify_command = old scoring
- [ ] Tests for D2

### D3. Benchmark Report Update

Update the benchmark report (terminal, markdown, HTML) to show verification scores separately.

In the results table, when any task has verification tests:
- Add a "Verify" column showing verification pass/fail percentage
- In task details, show verification output (truncated to 20 lines)

Required files to modify:
- `coderace/benchmark_report.py`
- `coderace/commands/benchmark.py` (if CLI output changes)

- [ ] Terminal report shows Verify column
- [ ] Markdown report shows Verify column
- [ ] HTML report shows Verify column
- [ ] Verification output in task details
- [ ] Tests for D3

### D4. Six Hard Built-in Tasks with Verification Tests

Create 6 new built-in tasks with embedded verification tests. These must be tasks where coding agents are likely to make mistakes. Each task YAML includes both a `test_command` (agents write their own tests) and `verify_command` + `verify_files` (our verification suite).

Tasks to create in `coderace/builtins/tasks/`:

1. **regex-engine** (hard): Implement a basic regex engine supporting `.`, `*`, `+`, `?`, `^`, `$`, character classes `[abc]`, `[a-z]`, `[^abc]`, and alternation `a|b`. Must handle backtracking correctly. Verification tests: catastrophic backtracking detection (must complete in <2s), nested quantifier edge cases, empty string matching.

2. **lru-cache** (medium-hard): Implement an LRU cache with O(1) get/put, max capacity, TTL expiry, and thread safety. Verification tests: concurrent access correctness, TTL precision, capacity overflow ordering.

3. **expression-evaluator** (hard): Implement a math expression parser and evaluator supporting +, -, *, /, **, parentheses, unary minus, variables, and functions (sin, cos, sqrt, abs). Must handle operator precedence correctly. Verification tests: deeply nested expressions, operator precedence edge cases, floating point precision, error handling for division by zero and undefined variables.

4. **url-router** (medium-hard): Implement an HTTP URL router with path parameters (`/users/:id`), wildcards (`/files/*path`), middleware support, and method matching. Verification tests: ambiguous route resolution, parameter extraction, middleware ordering, 405 vs 404 distinction.

5. **diff-algorithm** (hard): Implement Myers diff algorithm producing unified diff output. Must handle insertions, deletions, modifications, and generate minimal edit distance patches. Verification tests: large file diffs (1000+ lines), binary-like content, all-insert/all-delete edge cases, patch application roundtrip.

6. **task-scheduler** (hard): Implement a priority-based task scheduler with dependencies (DAG), cycle detection, parallel execution slots, and timeout handling. Verification tests: diamond dependencies, cycle detection accuracy, priority inversion scenarios, timeout edge cases.

Each task YAML must include:
- Clear description (what to build)
- `verify_files` with a comprehensive test file (30-50 test cases each)
- `verify_command` pointing to the verification test file
- Difficulty rating: hard
- Scoring weights using the new verify-aware distribution

- [ ] regex-engine.yaml with verify_files
- [ ] lru-cache.yaml with verify_files
- [ ] expression-evaluator.yaml with verify_files
- [ ] url-router.yaml with verify_files
- [ ] diff-algorithm.yaml with verify_files
- [ ] task-scheduler.yaml with verify_files

### D5. Documentation + Final Tests

- Update README.md: Verification Tests section explaining the feature
- Update `coderace tasks list` output to show which tasks have verification tests
- Integration tests: run a mock task with verify_command, confirm scoring works end-to-end

- [ ] README updated with Verification Tests section
- [ ] `tasks list` shows verification badge
- [ ] Integration test for full verify flow
- [ ] All existing tests still pass

## 4. Test Requirements

- [ ] Unit tests for verify file writing
- [ ] Unit tests for verify command execution
- [ ] Unit tests for scoring with/without verify
- [ ] Unit tests for report generation with verify columns
- [ ] Integration test: task with verify_command scores differently than without
- [ ] Integration test: verify_files correctly overwrite workspace files
- [ ] Edge cases: verify_command fails, verify_files empty, task has verify but agent breaks the interface
- [ ] All 392 existing tests must still pass

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
