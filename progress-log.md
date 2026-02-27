# Progress Log: Built-in Task Library (v0.7.0)

Date: 2026-02-26
Contract: all-day-build-contract-builtin-tasks.md

---

## D1: Built-in Task Package (core) ✅

**What was built:**
- `coderace/builtins/__init__.py` — `list_builtins()`, `load_builtin()`, `get_builtin_path()` API
- Uses `importlib.resources` for package data resolution
- `coderace/builtins/tasks/` directory
- Updated `pyproject.toml` with hatch build config for YAML file inclusion

**Tests:** 7 tests in `tests/test_builtins.py` — all pass

**Commit:** `2356071`

---

## D2: Curated Task Library (6 tasks) ✅

**What was built:**
- `fibonacci.yaml` — Easy: Fibonacci with memoization + tests
- `json-parser.yaml` — Medium: JSON parser from scratch
- `markdown-to-html.yaml` — Medium: Markdown subset to HTML converter
- `csv-analyzer.yaml` — Medium: CLI CSV summary statistics tool
- `http-server.yaml` — Medium-Hard: HTTP/1.1 server with stdlib socket
- `binary-search-tree.yaml` — Hard: AVL tree with full operations

**Tests:** Added validation test for all 6 tasks

**Commit:** `51e3d86`

---

## D3: CLI Integration ✅

**What was built:**
- `coderace/commands/tasks.py` — `list` and `show` subcommands
- Registered `tasks` command group in `cli.py`
- `--builtin` flag on `run` command with mutual exclusion from file path

**Tests:** 6 tests in `tests/test_tasks_cli.py` — all pass

**Commit:** `20b9cfe`

---

## D4: Documentation ✅

**What was built:**
- README: Quick Start with `--builtin`, "Built-in Tasks" section with difficulty table
- CHANGELOG: v0.7.0 entry
- Version bumped to 0.7.0 in `pyproject.toml` and `coderace/__init__.py`

**Commit:** `93921d0`

---

## Final Status (v0.7.0)

- All 4 deliverables complete ✅
- Test count: 337 → 351 = 14 new tests added ✅
- All 351 tests pass ✅
- Version bumped to 0.7.0 ✅
- Committed after each deliverable ✅

---
---

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

## Final Status (v0.5.0)

- All 5 deliverables complete ✅
- All checklist items checked ✅
- Test count: 214 (pre-existing) → 286 (final) = 72 new tests added (target was 40+) ✅
- All 286 tests pass ✅
- Version bumped to 0.5.0 ✅
- No scope creep, no refactoring outside deliverables ✅
- Committed after each deliverable ✅

---
---

# Progress Log: Web Dashboard Export (v0.6.0)

Date: 2026-02-25
Contract: all-day-build-contract-dashboard.md

---

## D1: Dashboard Generator Core ✅

**What was built:**
- `coderace/dashboard.py` — `generate_dashboard()` reads from ResultStore, produces self-contained HTML
- Sections: hero header, aggregate leaderboard, race history (expandable), agent performance cards, CSS-only cost bar chart
- Responsive CSS with dark/light theme toggle (CSS variables + JS)
- No external dependencies (all CSS/JS inline)

**Tests:** 29 tests in `tests/test_dashboard.py` — all pass

**Commit:** `23de12d` — D1: dashboard generator core

---

## D2: CLI Command (`coderace dashboard`) ✅

**What was built:**
- `coderace/commands/dashboard.py` — command module
- `coderace/cli.py` — `dashboard` command with `--output/-o`, `--task`, `--last`, `--title`, `--open` flags
- `--open` uses `webbrowser.open()` to open in browser
- Empty database produces valid "No races yet" page with instructions

**Tests:** 10 tests in `tests/test_dashboard_cli.py` — all pass

**Commit:** `c6781c7` — D2: dashboard CLI command

---

## D3: Publish Integration (`--publish`) ✅

**What was built:**
- `coderace/publish.py` — here.now API client: 3-step flow (POST /publish → PUT upload → POST finalize)
- Anonymous publish (24h expiry) and authenticated publish (persistent URL via `--here-now-key` or `HERENOW_API_KEY` env var)
- `--publish` and `--here-now-key` flags added to dashboard command
- Uses only stdlib `urllib` (no requests dependency)

**Tests:** 12 tests in `tests/test_publish.py` — all pass

**Commit:** `222d858` — D3: publish integration

---

## D4: Documentation + CHANGELOG ✅

**What was built:**
- README: "Dashboard & Publishing" section with usage examples and feature list
- CHANGELOG: v0.6.0 entry listing all new features
- Version bumped to 0.6.0 in `pyproject.toml` and `coderace/__init__.py`
- `coderace dashboard --help` shows clear usage with all flags

**Tests:** All 337 tests pass (315 pre-existing + 22 new from D2/D3)

---

## Final Status (v0.6.0)

- All 4 deliverables complete ✅ (D1 was pre-committed)
- Test count: 315 → 337 = 22 new tests added (D1 had 29 already, total 51 new for dashboard feature) ✅
- All 337 tests pass ✅
- Version bumped to 0.6.0 ✅
- Committed after each deliverable ✅
