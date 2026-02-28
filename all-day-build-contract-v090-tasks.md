# All-Day Build Contract: v0.9.0 — Verification Tests + New Tasks

Status: In Progress
Date: 2026-02-28
Owner: Codex execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add verification tests to all 6 built-in tasks that lack them, and add 4 new built-in tasks that test different programming skills. The verification test runner (verify_command + verify_files) landed in v0.8.1 but only 6/12 tasks use it. Every task should have independent verification tests — tests the agent can't see, that validate the agent's implementation against a known-good spec. This is the feature that separates coderace from "run pytest and hope."

New tasks should cover skills the current suite doesn't: file I/O, CLI argument parsing, data transformation pipeline, and a state machine. These are practical programming tasks that real developers encounter, not academic exercises.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end (`uv run python -m pytest`).
4. New tasks must follow the exact YAML schema used by existing tasks.
5. Never modify files outside the project directory.
6. Commit after each completed deliverable (not at the end).
7. If stuck on same issue for 3 attempts, stop and write a blocker report.
8. Do NOT refactor, restyle, or "improve" code outside the deliverables.
9. Read existing tasks and tests before writing new ones. Match style exactly.
10. Every verify_files test must be self-contained (no imports from the task description that aren't part of the standard library + pytest).
11. verify_command tests must be meaningfully different from test_command tests — they should test edge cases, integration behavior, or correctness properties the agent's own tests might miss.

## 3. Feature Deliverables

### D1. Add verify_command + verify_files to fibonacci.yaml

The fibonacci task currently has no verification tests. Add verify_files with a verify test file that tests:
- Large fibonacci numbers (fib(50), fib(100)) to ensure memoization actually works (not just that it doesn't crash)
- Type checking: verify return types are int, not float
- Edge case: fib(0) and fib(1) specifically
- Performance: fib(100) should complete in under 1 second (verify memoization)
- fibonacci_sequence returns a list, not a generator

Required files to modify:
- `coderace/builtins/tasks/fibonacci.yaml`

- [ ] Add verify_command and verify_files to fibonacci.yaml
- [ ] Verify tests are meaningfully different from the task's test_command expectations
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

### D2. Add verify_command + verify_files to json-parser.yaml

- [ ] Add verification tests that test malformed JSON edge cases, nested structures, unicode handling
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

### D3. Add verify_command + verify_files to csv-analyzer.yaml

- [ ] Add verification tests for empty CSVs, CSVs with quoted fields containing commas/newlines, large datasets
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

### D4. Add verify_command + verify_files to markdown-to-html.yaml

- [ ] Add verification tests for nested formatting, edge cases (empty input, only whitespace), HTML entity escaping
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

### D5. Add verify_command + verify_files to http-server.yaml

- [ ] Add verification tests for concurrent requests, proper HTTP headers, error responses, content-type handling
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

### D6. Add verify_command + verify_files to binary-search-tree.yaml

- [ ] Add verification tests for AVL balance property, deletion edge cases, large sequential inserts
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

### D7. New task: file-watcher (medium)

Create `coderace/builtins/tasks/file-watcher.yaml`:
A CLI tool that watches a directory for file changes and logs them. Tests file I/O, directory traversal, and event handling.

Requirements for the task description:
- Implement `file_watcher.py` with a `FileWatcher` class
- Methods: `scan(directory) -> dict[str, FileInfo]`, `diff(old_scan, new_scan) -> list[Change]`
- FileInfo: path, size, modified_time, hash (md5)
- Change types: added, modified, deleted
- Must handle nested directories
- Agent writes their own tests in `test_file_watcher.py`

Include verify_command + verify_files from the start.

- [ ] Create file-watcher.yaml with full task spec + verification tests
- [ ] Register in builtins __init__.py if needed
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

### D8. New task: cli-args-parser (medium)

Create `coderace/builtins/tasks/cli-args-parser.yaml`:
Build a lightweight CLI argument parser (like a mini argparse). Tests string parsing, API design, error handling.

Requirements:
- Implement `cli_parser.py` with an `ArgumentParser` class
- Support: positional args, --flags, --key=value, --key value, -short flags, --no-flag (boolean negation)
- Methods: `add_argument(name, type, default, required, help)`, `parse(args: list[str]) -> Namespace`
- Proper error messages for missing required args, type conversion failures
- Agent writes tests in `test_cli_parser.py`

Include verify_command + verify_files.

- [ ] Create cli-args-parser.yaml with full task spec + verification tests
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

### D9. New task: data-pipeline (hard)

Create `coderace/builtins/tasks/data-pipeline.yaml`:
Build a composable data transformation pipeline. Tests functional programming patterns, method chaining, lazy evaluation.

Requirements:
- Implement `pipeline.py` with a `Pipeline` class
- Methods: `map(fn)`, `filter(fn)`, `reduce(fn, initial)`, `sort(key)`, `take(n)`, `skip(n)`, `batch(size)`
- Pipelines are lazy (don't execute until `.collect()` or `.first()`)
- Pipelines are composable: `pipe1 | pipe2` creates a combined pipeline
- Agent writes tests in `test_pipeline.py`

Include verify_command + verify_files.

- [ ] Create data-pipeline.yaml with full task spec + verification tests
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

### D10. New task: state-machine (medium-hard)

Create `coderace/builtins/tasks/state-machine.yaml`:
Implement a finite state machine with transition guards and event handling. Tests OOP design, state management.

Requirements:
- Implement `state_machine.py` with `StateMachine`, `State`, `Transition` classes
- Define states, transitions with guards (conditions), and actions (callbacks)
- Methods: `add_state(name, on_enter, on_exit)`, `add_transition(from, to, event, guard)`, `trigger(event)`, `current_state`
- Raise `InvalidTransition` for illegal transitions
- Support `on_enter`/`on_exit` hooks for states
- Agent writes tests in `test_state_machine.py`

Include verify_command + verify_files.

- [ ] Create state-machine.yaml with full task spec + verification tests
- [ ] Run `uv run python -m pytest tests/ -q` — all tests pass

## 4. Test Requirements

- [ ] All existing 411 tests must still pass
- [ ] New YAML tasks must be loadable by the task loader (test with `uv run python -c "from coderace.builtins import list_builtin_tasks; print(list_builtin_tasks())"`)
- [ ] All new tasks must have valid YAML that passes task schema validation
- [ ] verify_files content must be valid Python that would actually pass if a correct implementation existed
- [ ] Final count: 16 built-in tasks, all with verify_command + verify_files

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
