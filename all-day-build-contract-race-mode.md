# All-Day Build Contract: coderace v1.2.0 — Race Mode

Status: In Progress
Date: 2026-03-03
Owner: Codex execution pass
Scope type: Deliverable-gated (no hour promises)
Target version: 1.2.0

## 1. Objective

Add a `coderace race` command that runs multiple agents simultaneously in git worktrees and declares a winner as soon as the first agent passes all verification tests. Unlike the existing `--parallel` mode which waits for all agents to complete then scores them, race mode terminates remaining agents immediately when a winner is found. The UX shows a live Rich progress panel with per-agent status, real-time timers, and a winner announcement.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end (all 505 existing + new tests).
4. New features must ship with docs and README updates in the same pass.
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside ~/repos/coderace/.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report to progress-log.md.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing tests and docs before writing new code. Read coderace/cli.py fully before touching it.
11. Current pyproject.toml version is 1.0.0 — bump to 1.2.0 only in the version bump deliverable (D5).

## 3. Architecture Notes (read before coding)

- Existing parallel mode: `cli.py` run command with `--parallel` flag, uses `ThreadPoolExecutor` + `_run_agent_worktree`. Runs ALL agents, waits for all to complete, then scores.
- Verification: `scorer.py` `run_command()` runs verify commands. Task YAML has `verify:` section with commands.
- Worktrees: `git_ops.py` `add_worktree()` / `remove_worktree()` / `prune_worktrees()`
- Types: `types.py` has `AgentResult`, `Score`, etc.
- Commands are in `coderace/commands/` as separate Typer sub-apps.
- Add race command as `coderace/commands/race.py` and register it in `cli.py`.

## 4. Feature Deliverables

### D1. Race mode core logic (`coderace/commands/race.py`)

Implement the `coderace race` command with first-to-pass semantics.

Required files:
- `coderace/commands/race.py`

Logic:
- Accept same task file / --builtin / --agent flags as `run` command
- Run all agents simultaneously using `_run_agent_worktree` in ThreadPoolExecutor
- Poll each agent's worktree for verification pass DURING execution (every 5s interval)
- When a task has `verify:` commands: after agent `exit_code == 0`, run verify commands against the worktree
- **Race winner = first agent whose verify commands all return exit code 0**
- **If no verify commands**: winner = first agent to exit with `exit_code == 0`
- Cancel remaining futures (via Event/flag) when winner found. Allow 10s graceful shutdown.
- If all agents fail or time out with no winner: "no winner" result
- `--timeout N` override (default: use task timeout)
- `--no-cost` flag passthrough
- `--builtin NAME` flag passthrough
- `--agent NAME` flag (repeatable) to override agent list

- [ ] Command registered in cli.py (`app.add_typer(race_app, name="race")`)
- [ ] Accepts task file arg and --builtin
- [ ] Runs agents in parallel worktrees
- [ ] Polls for first-pass win condition every 5s
- [ ] Cancels remaining agents when winner found (uses threading.Event stop_event)
- [ ] Handles "no winner" case gracefully
- [ ] Cleans up worktrees (prune_worktrees) on exit
- [ ] Unit tests for D1 in tests/test_race.py

### D2. Live race UI (Rich Live panel)

Show a live progress display while the race is running.

Required files:
- Updates to `coderace/commands/race.py` (UI component)

UI layout (Rich Live):
```
🏁 coderace race — fix-auth-bug
Running 3 agents in parallel...

Agent         Status          Time       
──────────────────────────────────────────
claude        🔨 coding...    0:00:23
codex         🧪 testing...   0:00:31
aider         🔨 coding...    0:00:18

Press Ctrl+C to abort
```

Status stages (in order):
1. `🔨 coding...` — agent running, not yet exited
2. `🧪 testing...` — agent exited 0, running verify commands
3. `✅ WINNER! (0:01:23)` — passed verify, race won
4. `❌ failed (exit N)` — exited non-zero
5. `⏰ timed out` — exceeded timeout
6. `🛑 stopped` — cancelled after winner found

Winner announcement (printed after Live panel closes):
```
🏆 Winner: claude — completed in 1:23 (first to pass verification)
Runner-up: codex — finished 0:12 later
```

- [ ] Rich Live panel updates every 1s
- [ ] Per-agent status transitions correctly
- [ ] Winner announcement printed after race ends
- [ ] Works with Rich Console (no double-output issues)
- [ ] Tests for status transitions (can use mocked Live)

### D3. Race results storage

Save race results to the same SQLite store as regular runs.

Required files:
- `coderace/commands/race.py` (storage calls)

Race result record (extends existing store):
- `race_id`: UUID
- `task_name`
- `winner_agent`: agent name or null
- `winner_time`: float seconds or null
- `participant_results`: list of AgentResult (existing type) 
- `timestamp`

Use existing `store.py` if possible. If not, write `race_results` to a separate JSON file at `{repo}/.coderace/race-results.json` (append mode). JSON is fine for v1.2.0.

- [ ] Race results saved with winner + all participant times
- [ ] `--no-save` flag skips saving
- [ ] Results include: winner, winner_time, all agents' exit codes, wall times
- [ ] Tests for result serialization

### D4. Tests (comprehensive)

- [ ] `tests/test_race.py`: unit tests for race mode
  - test winner detection (first-pass-wins logic)
  - test no-winner scenario (all fail)
  - test cancellation after winner found
  - test CLI invocation with mock adapters
  - test result serialization
  - test status transitions in UI
  - test --no-winner with all timeouts
  - test integration with task YAML (with and without verify: section)
- [ ] All 505 existing tests still pass (`uv run pytest`)
- [ ] At least 20 new tests for race mode
- [ ] No test relies on real LLM calls (use existing mock adapter patterns)

### D5. Docs + version bump

- [ ] Add "Race Mode" section to README.md (after "Parallel Mode" section or Context Eval)
  - What it is (first-to-pass, not all-complete-then-score)
  - Example command: `coderace race task.yaml --agent claude --agent codex`
  - Example output (text representation of the live UI)
  - When to use race mode vs parallel mode
- [ ] Add CHANGELOG.md entry for v1.2.0
- [ ] Update pyproject.toml version to `1.2.0`
- [ ] Commit: `feat: add race mode (v1.2.0)` with all files

## 5. Test Requirements

- [ ] All 505 existing tests pass (no regressions)
- [ ] `uv run pytest tests/test_race.py` — all new tests pass
- [ ] `uv run pytest` — full suite green
- [ ] Edge cases covered:
  - Task with no verify: commands (winner = first clean exit)
  - All agents fail (no winner)
  - All agents time out (no winner)
  - Single agent race (still works)
  - Winner found before all agents finish (cancellation works)
  - Ctrl+C during race (graceful cleanup)

## 6. Reports

- Write progress to `progress-log.md` after each deliverable
- Format: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done

## 7. Stop Conditions

- All deliverables checked and all tests passing → DONE
- 3 consecutive failed attempts on same issue → STOP, write blocker report to progress-log.md
- Scope creep detected → STOP, report
- All tests passing but deliverables remain → continue to next deliverable
