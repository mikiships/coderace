# Progress Log: Leaderboard & Result History (v0.5.0)

Date: 2026-02-24
Contract: all-day-build-contract-leaderboard.md

---

## D1: Result Store ✅

**What was built:**
- `coderace/store.py` — `ResultStore` class with SQLite backend at `~/.coderace/results.db`
- Schema: `runs` table (task_name, timestamp, git_ref, config_hash, agent_count) + `agent_results` table (score, time, cost, lines, pass/fail, model, winner flag)
- Methods: `save_run()`, `get_runs()`, `get_agent_stats()`
- Auto-create DB and tables on first use (no init step)
- WAL mode, proper indexes, foreign keys, concurrent write support
- Configurable via `CODERACE_DB` env var

**Tests:** 25 new tests in `tests/test_store.py` — all pass
- Save/query/filter, empty DB, concurrent writes, field round-trip, env var

**Commit:** `13b5cf4` — D1: result store

---

## D2: Auto-Save on Run ✅

**What was built:**
- `coderace/cli.py` — `_auto_save_to_store()` helper called after scoring
- `--no-save` flag to disable persistence
- Graceful fallback: DB errors don't crash the run (try/except with pass)
- Scores mapped to store format including cost and model data

**Tests:** 8 new tests in `tests/test_cli_store_integration.py` — all pass
- Normal save, multi-run, cost propagation, graceful error, field mapping, winner detection

**Commit:** `37d4f65` — D2: auto-save on run

---

## D3: `coderace leaderboard` Command ✅

**What was built:**
- `coderace/commands/leaderboard.py` — formatting functions (terminal, markdown, json, html)
- `coderace/cli.py` — `leaderboard` command with `--task`, `--since`, `--min-runs`, `--format` options
- Columns: Agent | Wins | Races | Win% | Avg Score | Avg Cost | Avg Time
- Ranking by win rate (descending), then avg score

**Tests:** 19 new tests in `tests/test_leaderboard.py` — all pass
- Empty DB, format functions (terminal/markdown/json/html), CLI filters, ranking logic, help text

**Commit:** `3745037` — D3: coderace leaderboard command

---

## D4: `coderace history` Command ✅

**What was built:**
- `coderace/commands/history.py` — formatting functions (terminal, markdown, json)
- `coderace/cli.py` — `history` command with `--task`, `--agent`, `--limit`, `--format` options
- Columns: Run ID | Date | Task | Agents | Winner | Best Score
- Newest first ordering

**Tests:** 16 new tests in `tests/test_history.py` — all pass
- Empty DB, format functions, CLI filters, JSON structure, ordering, help text

**Commit:** `2095bcc` — D4: coderace history command

---

## D5: Documentation & README Update ✅

**What was built:**
- `README.md` — "Leaderboard & History" section with usage examples and example output tables
- `CHANGELOG.md` — v0.5.0 entry listing all new features
- Version bumped to 0.5.0 in `pyproject.toml` and `coderace/__init__.py`
- `coderace leaderboard --help` and `coderace history --help` show clear usage

**Tests:** 4 new integration tests in `tests/test_full_workflow.py` — all pass
- Full workflow: save → leaderboard → history roundtrip
- Corrupted DB graceful handling
- Single-agent race
- Auto-save → query roundtrip

**Commit:** `b4b4ee8` — D5: documentation

---

## Final Status

- All 5 deliverables complete ✅
- All checklist items checked ✅
- Test count: 214 (pre-existing) → 286 (final) = 72 new tests added (target was 40+) ✅
- All 286 tests pass ✅
- Version bumped to 0.5.0 ✅
- No scope creep, no refactoring outside deliverables ✅
- Committed after each deliverable ✅
