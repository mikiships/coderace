# All-Day Build Contract: Leaderboard & Result History

Status: In Progress
Date: 2026-02-24
Owner: Claude Code execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add persistent result tracking and a leaderboard system to coderace. Every `coderace run` saves its results to a local SQLite database. A new `coderace leaderboard` command aggregates rankings across all runs, showing which agents consistently win. A `coderace history` command shows past runs. This transforms coderace from a one-shot comparison tool into a persistent benchmarking system with accumulated data.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end (existing 214 tests + new tests).
4. New features must ship with docs and report addendum updates in the same pass.
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside the project directory.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing tests and docs before writing new code.

## 3. Feature Deliverables

### D1. Result Store (`coderace/store.py`)

SQLite-backed persistent storage for race results. Database lives at `~/.coderace/results.db` by default (configurable via `CODERACE_DB` env var). Schema stores: run metadata (task name, timestamp, git ref, config hash), per-agent results (score, time, cost, lines changed, pass/fail, model name), and aggregate stats.

Required files:
- `coderace/store.py` — ResultStore class with save_run(), get_runs(), get_agent_stats()
- `tests/test_store.py` — Full unit test coverage

- [ ] SQLite schema design with proper indexes
- [ ] `ResultStore` class: `save_run(task_name, results: list[AgentResult])` 
- [ ] `ResultStore.get_runs(task_name=None, agent=None, limit=50)` — query past runs
- [ ] `ResultStore.get_agent_stats(agent=None)` — aggregate win rate, avg score, avg cost
- [ ] Auto-create DB and tables on first use (no separate init step)
- [ ] Tests for D1 (at least 10 test cases: save, query, filter, empty DB, concurrent access)

### D2. Auto-Save on Run

Integrate the result store into the existing `coderace run` flow. After scoring completes, automatically save results to the DB. Add `--no-save` flag to skip persistence.

Required files:
- `coderace/cli.py` — modifications to run command
- `tests/test_cli_store_integration.py` — integration tests

- [ ] `coderace run` auto-saves results after scoring
- [ ] `--no-save` flag to disable persistence
- [ ] Existing run behavior unchanged when store is unavailable (graceful fallback)
- [ ] Tests for D2 (at least 5 cases: normal save, --no-save, DB error graceful fallback)

### D3. `coderace leaderboard` Command

New CLI command showing aggregate rankings. Default: all agents across all tasks. Filterable by task, time range, min runs.

Output columns: Agent | Wins | Races | Win% | Avg Score | Avg Cost | Avg Time
Supports `--format terminal|markdown|json|html` (same pattern as `coderace results`).

Required files:
- `coderace/commands/leaderboard.py`
- `tests/test_leaderboard.py`

- [ ] `coderace leaderboard` — default view, all agents, all tasks
- [ ] `--task <name>` filter by task
- [ ] `--since <date>` filter by time (ISO date or "7d", "30d" shorthand)
- [ ] `--min-runs N` exclude agents with fewer than N races
- [ ] `--format terminal|markdown|json|html` output formats
- [ ] Proper ranking logic (win = highest score in a race; ties split)
- [ ] Tests for D3 (at least 8 cases: empty, single run, multi-run ranking, filters, formats)

### D4. `coderace history` Command

New CLI command showing past runs. Similar to `git log` but for races.

Output: Run ID | Date | Task | Agents | Winner | Best Score
Supports `--format terminal|markdown|json`.

Required files:
- `coderace/commands/history.py`
- `tests/test_history.py`

- [ ] `coderace history` — list past runs, newest first
- [ ] `--task <name>` filter
- [ ] `--agent <name>` filter (show only runs including this agent)
- [ ] `--limit N` (default 20)
- [ ] `--format terminal|markdown|json`
- [ ] Tests for D4 (at least 5 cases)

### D5. Documentation & README Update

- [ ] README section: "Leaderboard & History" with usage examples
- [ ] CHANGELOG entry for v0.5.0
- [ ] `coderace leaderboard --help` and `coderace history --help` show clear usage
- [ ] Example output in README (terminal format)

## 4. Test Requirements

- [ ] Unit tests for each deliverable (see per-deliverable counts above)
- [ ] Integration test: run -> save -> leaderboard -> history full workflow
- [ ] Edge cases: empty DB, single agent race, --no-save, corrupted DB file, concurrent writes
- [ ] All existing 214 tests must still pass
- [ ] Target: 40+ new tests (total 254+)

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
