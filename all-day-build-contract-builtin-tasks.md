# All-Day Build Contract: Built-in Task Library (v0.7.0)

Status: In Progress
Date: 2026-02-26
Owner: Claude Code execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add a built-in task library to coderace so users can run benchmark races without writing their own YAML files. This is the #1 friction reducer for new users: `pip install coderace && coderace run --builtin fibonacci` should Just Work.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end (`uv run pytest -x -q`).
4. New features must ship with docs and report addendum updates in the same pass.
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside the project directory.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing tests and docs before writing new code.

## 3. Feature Deliverables

### D1. Built-in Task Package (core)

Create `coderace/builtins/` package that bundles YAML task files as package data. Provide a Python API to list, load, and resolve built-in tasks.

Required files:
- `coderace/builtins/__init__.py` — API: `list_builtins() -> list[str]`, `load_builtin(name: str) -> dict`, `get_builtin_path(name: str) -> Path`
- `coderace/builtins/tasks/` — directory of YAML task files (at least 6 tasks, see D2)

Implementation notes:
- Use `importlib.resources` (Python 3.10+) to locate bundled YAML files
- Each task YAML follows the existing task format (name, description, repo, test_command, lint_command, timeout, agents, scoring)
- Tasks should use `repo: .` (works in any directory — the agent creates files in the working directory)

- [ ] Create `coderace/builtins/__init__.py` with list/load/get API
- [ ] Create `coderace/builtins/tasks/` directory
- [ ] Ensure builtins are included in package data (update pyproject.toml if needed)
- [ ] Tests for D1 (test list, load, missing task error)

### D2. Curated Task Library (6 tasks minimum)

Create 6+ well-designed benchmark tasks that test different coding skills. Each must be self-contained (agent creates all files from scratch, `repo: .`).

Tasks to create (all in `coderace/builtins/tasks/`):

1. **fibonacci.yaml** — Implement fibonacci with memoization + tests. Easy warmup task.
2. **json-parser.yaml** — Build a simple JSON parser from scratch (subset: strings, numbers, arrays, objects, booleans, null). Medium difficulty.
3. **markdown-to-html.yaml** — Convert markdown subset (headers, bold, italic, links, code blocks) to HTML. Medium.
4. **csv-analyzer.yaml** — CLI tool that reads CSV from stdin, outputs summary stats (row count, column types, min/max/mean for numeric columns). Medium.
5. **http-server.yaml** — Minimal HTTP/1.1 server using only stdlib (socket). Serve static files from a directory. Must handle GET, return 404, Content-Type headers. Medium-hard.
6. **binary-search-tree.yaml** — BST with insert, search, delete, in-order traversal, and balancing (AVL or red-black). Include comprehensive tests. Hard.

Each task YAML must include:
- Clear description with exact function signatures or CLI interface
- test_command that runs the task's tests
- lint_command (ruff check)
- Reasonable timeout (300-600s)
- scoring weights
- agents list: [claude, codex, gemini, aider, opencode]

- [ ] fibonacci.yaml
- [ ] json-parser.yaml
- [ ] markdown-to-html.yaml
- [ ] csv-analyzer.yaml
- [ ] http-server.yaml
- [ ] binary-search-tree.yaml
- [ ] Each task is valid YAML and loadable via D1 API

### D3. CLI Integration (`coderace tasks` command group)

Add a `tasks` command group to the CLI for discovering built-in tasks.

Commands:
- `coderace tasks list` — show all built-in tasks with name and one-line description
- `coderace tasks show <name>` — print full task YAML to stdout

Modify `coderace run` to accept:
- `--builtin <name>` flag as alternative to positional task file path
- When `--builtin` is used, resolve the task from the builtins package instead of the filesystem

Required files to modify:
- `coderace/cli.py` — add tasks command group, modify run to accept --builtin
- `coderace/commands/tasks.py` (new) — implement list and show commands

- [ ] `coderace/commands/tasks.py` with list and show
- [ ] Register tasks command group in cli.py
- [ ] Add `--builtin` flag to `run` command
- [ ] Tests for tasks list, tasks show, run --builtin

### D4. Documentation

Update README.md with:
- "Quick Start" section showing `coderace run --builtin fibonacci`
- "Built-in Tasks" section listing all available tasks with difficulty ratings
- Update the existing CLI reference table

Update CHANGELOG.md with v0.7.0 entry.

- [ ] README.md updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped to 0.7.0 in pyproject.toml

## 4. Test Requirements

- [ ] Unit tests for builtins API (list, load, error handling)
- [ ] Unit tests for tasks CLI commands (list, show, show-missing)
- [ ] Unit tests for `run --builtin` flag resolution
- [ ] All 6 task YAML files validate (loadable, required fields present)
- [ ] All existing tests (337) must still pass
- [ ] Run full suite: `uv run pytest -x -q` — all green

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
