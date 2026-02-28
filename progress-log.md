# Benchmark Suite Build Progress Log

## Date: 2026-02-27

### D1: Benchmark Runner Core ✅

**Built:**
- `coderace/benchmark.py` — `BenchmarkResult`, `TaskAgentResult` dataclasses, `run_benchmark()` orchestrator, sequential + parallel execution, `list_benchmark_tasks()` with difficulty filtering
- `coderace/commands/benchmark.py` — CLI with `--agents`, `--tasks`, `--difficulty`, `--timeout`, `--parallel`, `--dry-run`, `--format`, `--output`, `--no-save`; also `benchmark history` and `benchmark show` subcommands
- Updated `coderace/cli.py` to register `benchmark_app`

**Tests:** Covered in D5 (test_benchmark.py)
**Commit:** `063161c` feat(D1)

---

### D2: Aggregate Statistics ✅

**Built:**
- `coderace/benchmark_stats.py` — `compute_benchmark_stats()` producing `BenchmarkStats` with:
  - Per-agent: total_score, avg_score, pass_rate, avg_time, total_cost, cost_efficiency, win_count
  - Per-task: best_agent, best_score, avg_score, fastest_agent, fastest_time
  - Win matrix: `win_matrix[task][agent]` = 1 if agent won that task

**Commit:** `343a6ab` feat(D2)

---

### D3: Benchmark Report Formats ✅

**Built:**
- `coderace/benchmark_report.py`:
  - `render_benchmark_terminal()` — Rich table (tasks as rows, agents as columns), summary rows (TOTAL, Win Rate, Avg Time, Total Cost), winner callout
  - `render_benchmark_markdown()` — GitHub-flavored pipe table with Task Insights section
  - `render_benchmark_html()` — self-contained HTML with dark theme matching existing html_report.py style

**Commit:** `a951338` feat(D3)

---

### D4: Benchmark Result Storage ✅

**Built:**
- Updated `coderace/store.py`:
  - New SQLite tables: `benchmarks`, `benchmark_results`
  - `ResultStore.save_benchmark()` — persists full benchmark run + results
  - `ResultStore.get_benchmarks()` — lists past runs newest first
  - `ResultStore.get_benchmark()` — retrieves full detail by ID
- CLI commands `benchmark history` and `benchmark show` wired to store

**Commit:** `f37bb0c` feat(D4)

---

### D5: Documentation + Tests ✅

**Built:**
- `tests/test_benchmark.py` — 41 new tests covering:
  - D1: BenchmarkResult dataclass, TaskAgentResult, list_benchmark_tasks, difficulty filtering
  - D2: All aggregate stat fields, win matrix, edge cases (zero score, no cost, single agent)
  - D3: Terminal output (no crash), markdown structure, HTML structure, timeout/error rendering
  - D4: Save/retrieve, not-found, empty store, result detail accuracy
  - Integration: dry-run combinations, count display, empty filter
- Updated `README.md` with Benchmarking section (usage, example output, all flags table, history commands)

**Commit:** `ef175e5` feat(D5)

---

### Final Test Count

- Existing: 351
- New: 41
- **Total: 392 passing** ✅

### Build Status: COMPLETE

All deliverables checked. All tests passing. Committed after each deliverable.

---

## Date: 2026-02-27 (Verification Tests Contract)

### D1: Verification Test Runner (core engine) ✅

**Built:**
- `coderace/types.py`
  - Added task fields: `verify_command`, `verify_files`
  - Added score fields: `verify_passed`, `verify_score`, `verify_output`
  - Added validation for `verify_command` and `verify_files` path/content shape
- `coderace/task.py`
  - Parse `verify_command` and `verify_files` from YAML with type validation
  - Included verification fields in task template comments
- `coderace/scorer.py`
  - Added verification file writer that writes into workspace and overwrites existing files
  - Added safe path resolution to block verify file paths escaping workspace
  - Runs verification command after `test_command` when `verify_command` and `verify_files` are present
  - Captures verification pass/fail/output and stores `verify_score` (100/0)
- `coderace/cli.py` and `coderace/benchmark.py`
  - Pass task verification settings into `compute_score(...)`
- `coderace/reporter.py`
  - Persist `verify_passed`, `verify_score`, `verify_output` in JSON results payload

**Tests:**
- Added D1 coverage:
  - `tests/test_task.py`: verification YAML parsing + invalid `verify_files` shape
  - `tests/test_scorer.py`: verify file overwrite behavior, verify command pass/fail output capture, skip behavior when `verify_files` absent, workspace-escape path rejection
- Validation run:
  - `./.venv/bin/pytest -q tests/test_task.py tests/test_scorer.py`
  - `./.venv/bin/pytest -q`
- Current suite status: **398 passed**

**Commit:**
- Blocked in this execution environment: `git commit` failed with permission error creating `.git/index.lock`.

**Next:**
- D2 Scoring Engine Update: add `verify` metric weighting and verify-aware default distribution with backward compatibility.

**Blockers:**
- Environment restriction on writing `.git/index.lock` prevents committing from this session.

---

### D2: Scoring Engine Update ✅

**Built:**
- `coderace/types.py`
  - Added verify-aware default scoring profile: tests=25%, verify=30%, exit=20%, lint=15%, time=5%, lines=5%
  - Added `verify` alias support in scoring config (`verify -> verify_passed`)
  - `Task.get_weights()` now selects verify-aware defaults when `verify_command` is present
  - Added `verify_passed` to `ScoreBreakdown`
- `coderace/scorer.py`
  - Composite score now includes weighted verification contribution
  - Maintains old default behavior for tasks without `verify_command`
  - Uses missing-key-safe weight access for backward-compatible custom maps
- `tests/test_scorer.py`
  - Added tests for verify alias normalization, verify-aware default behavior, and no-verify legacy behavior
- `tests/test_task.py`
  - Added assertion that verify tasks pick verify-aware defaults when no custom scoring is provided

**Tests:**
- `./.venv/bin/pytest -q tests/test_scorer.py tests/test_task.py`
- Result: **32 passed**

**Next:**
- D3 Benchmark report update: add conditional Verify column/output rendering across terminal, markdown, and HTML.

**Blockers:**
- None.

---

### D3: Benchmark Report Update ✅

**Built:**
- `coderace/benchmark.py`
  - Extended `TaskAgentResult` with verification fields: `verify_applicable`, `verify_passed`, `verify_score`, `verify_output`
  - Propagated verification results from `compute_score(...)` into benchmark run results (sequential + parallel paths)
- `coderace/benchmark_report.py`
  - Added conditional `Verify` column in terminal/markdown/HTML benchmark results tables when verification is present
  - Added verification details sections in terminal/markdown/HTML
  - Added output truncation to 20 lines for verification output details
- `coderace/store.py`
  - Extended `benchmark_results` persistence with verification fields
  - Added migration-safe column backfill for existing databases (`ALTER TABLE` when needed)
- `coderace/commands/benchmark.py`
  - `benchmark show` now reconstructs verification fields from stored benchmark results
- `tests/test_benchmark.py`
  - Added report tests for Verify column visibility, details sections, and 20-line truncation
  - Added storage roundtrip test for verification fields

**Tests:**
- `./.venv/bin/pytest -q tests/test_benchmark.py`
- `./.venv/bin/pytest -q tests/test_store.py`
- `./.venv/bin/pytest -q tests/test_cli_store_integration.py`
- Result: **80 passed**

**Next:**
- D4 built-in tasks: add 6 new hard tasks with embedded verification suites and verify-aware scoring.

**Blockers:**
- Commit still blocked in this session due inability to write under `.git/`.

---

### D4: Six Hard Built-in Tasks with Verification Tests ✅

**Built:**
- Added six new built-in tasks under `coderace/builtins/tasks/`:
  - `regex-engine.yaml`
  - `lru-cache.yaml`
  - `expression-evaluator.yaml`
  - `url-router.yaml`
  - `diff-algorithm.yaml`
  - `task-scheduler.yaml`
- Each task includes:
  - `difficulty: hard`
  - `test_command` for agent-authored tests
  - `verify_command` + embedded `verify_files` suite
  - verify-aware scoring weights (`tests=25, verify=30, exit=20, lint=15, time=5, lines=5`)
- Updated `coderace/benchmark.py` difficulty filtering to read `difficulty` from built-in YAML with legacy fallback behavior.
- Updated tests:
  - `tests/test_builtins.py` expected built-ins list now includes all six new tasks
  - `tests/test_benchmark.py` now asserts `--difficulty hard` includes all new verification tasks

**Tests:**
- `./.venv/bin/pytest -q tests/test_builtins.py`
- `./.venv/bin/pytest -q tests/test_benchmark.py`
- `./.venv/bin/pytest -q tests/test_tasks_cli.py`
- Result: **62 passed**

**Next:**
- D5 docs + integration: README verification section, `tasks list` verification indicator, and end-to-end verify scoring integration tests.

**Blockers:**
- Commit still blocked in this session due inability to write under `.git/`.

---

### D5: Documentation + Final Tests ✅

**Built:**
- `README.md`
  - Added a dedicated **Verification Tests** section with YAML examples and execution flow
  - Documented verify-aware default scoring distribution
  - Expanded built-in task table with all six new verification-backed tasks
  - Added note that `coderace tasks list` exposes verification availability
- `coderace/commands/tasks.py`
  - `tasks list` now includes a `Verify` column (`yes` when `verify_command` exists)
- New integration test coverage:
  - `tests/test_verification_integration.py`
    - End-to-end verify/no-verify scoring difference check
    - End-to-end verify file overwrite behavior check
- Updated CLI tests:
  - `tests/test_tasks_cli.py` now asserts Verify column and verification-enabled built-ins appear in list output

**Tests:**
- `./.venv/bin/pytest -q tests/test_tasks_cli.py`
- `./.venv/bin/pytest -q tests/test_verification_integration.py`
- `./.venv/bin/pytest -q`
- Result: **411 passed**

**Next:**
- No remaining contract deliverables for this pass.

**Blockers:**
- Commit still blocked in this session due inability to write under `.git/`.

---

### Verification Contract Summary (D1-D5)

- Deliverables completed in this pass: **D2, D3, D4, D5**
- D1 was already complete on branch (`560328b`)
- Full test suite status after all changes: **411 passed**
- Remaining blocker: this execution environment still cannot write under `.git/`, so per-deliverable commits could not be created from this session.

---

## Date: 2026-02-28 (v0.9.0 Verification + New Tasks Contract)

### D1: Fibonacci Verification Suite ✅

**Built:**
- Updated `coderace/builtins/tasks/fibonacci.yaml` with `verify_command` and embedded `verify_files`.
- Added `verify_fibonacci.py` coverage for `fib(50)` and `fib(100)` exact values, `int` return types, explicit `fib(0)`/`fib(1)` edge cases, performance checks, and `fibonacci_sequence` list typing.
- Updated scoring weights to include verification scoring.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**

**Next:**
- D2 (`json-parser.yaml`) verification suite.

**Blockers:**
- `uv run` panics in this sandbox unless `--offline --no-sync` is used.

### D2: JSON Parser Verification Suite ✅

**Built:**
- Updated `coderace/builtins/tasks/json-parser.yaml` with `verify_command` and embedded `verify_files`.
- Added `verify_json_parser.py` coverage for malformed JSON variants, deeply nested arrays, nested mixed structures, and unicode handling (literal + `\\u` escape decoding).
- Updated scoring weights to include verification scoring.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**

**Next:**
- D3 (`csv-analyzer.yaml`) verification suite.

**Blockers:**
- Git commit is blocked by sandbox permissions (`.git/index.lock` cannot be created).

### D3: CSV Analyzer Verification Suite ✅

**Built:**
- Updated `coderace/builtins/tasks/csv-analyzer.yaml` with `verify_command` and embedded `verify_files`.
- Added `verify_csv_analyzer.py` subprocess-based verification for header-only CSVs, quoted fields containing commas/newlines, and large dataset numeric/text aggregation.
- Updated scoring weights to include verification scoring.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**

**Next:**
- D4 (`markdown-to-html.yaml`) verification suite.

**Blockers:**
- Git commit is blocked by sandbox permissions (`.git/index.lock` cannot be created).

### D4: Markdown-to-HTML Verification Suite ✅

**Built:**
- Updated `coderace/builtins/tasks/markdown-to-html.yaml` with `verify_command` and embedded `verify_files`.
- Added `verify_md2html.py` verification for nested formatting, whitespace-only input behavior, and HTML entity escaping in text/code contexts.
- Updated scoring weights to include verification scoring.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**

**Next:**
- D5 (`http-server.yaml`) verification suite.

**Blockers:**
- Git commit is blocked by sandbox permissions (`.git/index.lock` cannot be created).

### D5: HTTP Server Verification Suite ✅

**Built:**
- Updated `coderace/builtins/tasks/http-server.yaml` with `verify_command` and embedded `verify_files`.
- Added `verify_http_server.py` verification for concurrent request handling, required response headers, 404/405 error responses, and extension-based content-type mapping.
- Updated scoring weights to include verification scoring.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**

**Next:**
- D6 (`binary-search-tree.yaml`) verification suite.

**Blockers:**
- Git commit is blocked by sandbox permissions (`.git/index.lock` cannot be created).

### D6: Binary Search Tree Verification Suite ✅

**Built:**
- Updated `coderace/builtins/tasks/binary-search-tree.yaml` with `verify_command` and embedded `verify_files`.
- Added `verify_bst.py` verification for AVL invariants, large sequential insert balancing, deletion edge cases (leaf/one-child/two-children), and repeated root deletion rebalancing.
- Updated scoring weights to include verification scoring.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**

**Next:**
- D7 (`file-watcher.yaml`) new built-in task with verification.

**Blockers:**
- Git commit is blocked by sandbox permissions (`.git/index.lock` cannot be created).

### D7: New Built-in Task `file-watcher` ✅

**Built:**
- Added `coderace/builtins/tasks/file-watcher.yaml` with full medium-difficulty task spec and embedded verification tests.
- Verification suite (`verify_file_watcher.py`) covers nested directory scanning, MD5 metadata, and `added`/`modified`/`deleted` diff behavior.
- Added `list_builtin_tasks()` alias in `coderace/builtins/__init__.py` so loader validation command works.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**
- Loader check:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -c "from coderace.builtins import list_builtin_tasks; print(list_builtin_tasks())"`
  - Includes `file-watcher`.

**Next:**
- D8 (`cli-args-parser.yaml`) new built-in task with verification.

**Blockers:**
- Git commit is blocked by sandbox permissions (`.git/index.lock` cannot be created).

### D8: New Built-in Task `cli-args-parser` ✅

**Built:**
- Added `coderace/builtins/tasks/cli-args-parser.yaml` with full medium-difficulty task spec and embedded verification tests.
- Verification suite (`verify_cli_parser.py`) covers positional args, `--key=value` and `--key value`, short/bundled flags, `--no-flag` negation, attribute normalization, and error clarity.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**

**Next:**
- D9 (`data-pipeline.yaml`) new built-in task with verification.

**Blockers:**
- Git commit is blocked by sandbox permissions (`.git/index.lock` cannot be created).

### D9: New Built-in Task `data-pipeline` ✅

**Built:**
- Added `coderace/builtins/tasks/data-pipeline.yaml` with full hard-difficulty task spec and embedded verification tests.
- Verification suite (`verify_pipeline.py`) covers lazy execution, chained map/filter/sort/skip/take/batch behavior, lazy reduce semantics, `first()`, and `pipe1 | pipe2` composition.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**

**Next:**
- D10 (`state-machine.yaml`) new built-in task with verification.

**Blockers:**
- Git commit is blocked by sandbox permissions (`.git/index.lock` cannot be created).

### D10: New Built-in Task `state-machine` ✅

**Built:**
- Added `coderace/builtins/tasks/state-machine.yaml` with full medium-hard task spec and embedded verification tests.
- Verification suite (`verify_state_machine.py`) covers guarded transitions, invalid transitions, transition ordering, and state hook/action callback behavior.

**Tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q`
- Result: **411 passed**

**Next:**
- Final contract validation checks (task loader output + verify coverage/count validation).

**Blockers:**
- Git commit is blocked by sandbox permissions (`.git/index.lock` cannot be created).

### v0.9.0 Contract Final Summary

**Deliverables Completed:**
- D1 through D10 completed in sequence.

**Validation Gates:**
- Full suite: `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --no-sync python -m pytest tests/ -q` -> **411 passed**.
- Loader command: `from coderace.builtins import list_builtin_tasks` succeeds and lists built-ins.
- Built-in count: **16**.
- Verification coverage: all 16 built-ins include both `verify_command` and `verify_files`.

**Blockers:**
- Per-deliverable commits could not be created because this sandbox denies writes under `.git/` (`.git/index.lock: Operation not permitted`).

---

## Date: 2026-02-28 (v1.0 Statistical Benchmarking & ELO Contract)

### D1: Trials Mode (`--trials N`) ✅

**Built:**
- `coderace/benchmark.py`
  - Added `trials` support to `run_benchmark(...)` (default `1`, validated `>=1`).
  - Added `trial_number` to `TaskAgentResult` and `trials` to `BenchmarkResult`.
  - Updated sequential/parallel execution paths to run each `(task, agent)` pair for every trial.
  - Added trial-aware progress status formatting (`Trial X/N | ...`).
- `coderace/commands/benchmark.py`
  - Added `--trials` CLI flag.
  - Updated dry-run counts and table expansion for multi-trial runs.
  - Passed `trials` through to benchmark core execution.
- `coderace/store.py`
  - Added `trial_number` column to `benchmark_results` schema with migration-safe backfill.
  - Persisted and loaded `trial_number` in benchmark save/show flows.

**Tests:**
- Added `tests/test_benchmark_trials.py` with D1 coverage:
  - single-trial backward compatibility
  - multi-trial execution fanout
  - trial progress status formatting
  - CLI `--trials` forwarding
  - dry-run trial-inclusive run counts
  - store roundtrip for `trial_number`
- Full suite validation:
  - `python3 -m pytest`
  - Result: **417 passed**

**Next:**
- D2: implement `coderace/statistics.py` (trial + aggregate stats with CI and edge-case handling).

**Blockers:**
- None.

### D2: Statistical Analysis Module (`coderace/statistics.py`) ✅

**Built:**
- Added new module `coderace/statistics.py` using stdlib-only math/statistics:
  - `TrialStats` dataclass for per `(task, agent)` multi-trial metrics.
  - `AgentAggregateStats` dataclass for per-agent cross-task aggregates.
  - `compute_trial_stats(...)`:
    - mean/stddev score
    - 95% CI (t-critical lookup for small samples, normal approx fallback)
    - mean/stddev wall time
    - mean/stddev cost
    - pass rate (`score > 0`)
    - consistency score (`1 - coefficient of variation`, clamped to `>=0`)
  - `compute_aggregate_stats(...)`:
    - aggregate mean score with CI
    - win rate by per-task mean-score winners
    - cost efficiency (`mean_score / mean_cost`)
    - reliability (`not timed_out` and no `error`)

**Tests:**
- Added `tests/test_statistics.py` with 9 tests covering:
  - 1-trial behavior
  - 3-trial behavior
  - 10-trial behavior
  - all-zero score edge case
  - single-agent aggregate edge case
  - multi-agent task-level win rate
  - reliability with timeout/error rows
  - cost efficiency calculation
  - CI width shrink check with more trials
- Full suite validation:
  - `python3 -m pytest`
  - Result: **426 passed**

**Next:**
- D3: persistent ELO ratings + `coderace ratings` CLI + benchmark integration.

**Blockers:**
- None.

### D3: Persistent ELO Ratings (`coderace/elo.py` + CLI/store integration) ✅

**Built:**
- Added `coderace/elo.py`:
  - Standard ELO functions with `K=32` (`expected_score`, `update_pair_ratings`)
  - `update_ratings(...)` benchmark integration:
    - per-task round-robin pairwise matches
    - mean trial score comparison per `(task, agent)`
    - draw handling for score differences within `1.0`
  - `RatingUpdate` snapshot dataclass (`before`/`after`/`deltas`)
- Updated `coderace/store.py`:
  - Added `elo_ratings` table (`agent`, `rating`, `updated_at`)
  - Added `get_elo_ratings()`, `upsert_elo_ratings(...)`, `reset_elo_ratings(...)`
  - Migration compatibility retained for existing DBs
- Updated benchmark flow in `coderace/commands/benchmark.py`:
  - Auto-updates persistent ELO ratings after each benchmark run
  - Prints ELO before/after/delta summary table for participating agents
- Added top-level CLI command in `coderace/cli.py`:
  - `coderace ratings`
  - `coderace ratings --json`
  - `coderace ratings --reset`

**Tests:**
- Added `tests/test_elo.py` with 11 tests covering:
  - initial/equal expected score
  - single-match update
  - missing-agent initialization to 1500
  - draw handling within 1-point margin
  - multi-task update behavior
  - repeated-win convergence
  - rating reset
  - `coderace ratings --json`
  - `coderace ratings --reset`
  - backward-compatible migration from legacy DB schema
  - benchmark integration persistence path
- Full suite validation:
  - `python3 -m pytest`
  - Result: **437 passed**

**Next:**
- D4: standardized export JSON + benchmark report statistical enhancements + ELO display.

**Blockers:**
- None.

### D4: Standardized Export Format + Enhanced Report ✅

**Built:**
- Added `coderace/export.py`:
  - `collect_system_info()` for `os`, `python`, `cpu`
  - `export_benchmark_json(...)` writer for standardized JSON payload:
    - metadata (`coderace_version`, benchmark id, timestamp)
    - config (`trials`, `timeout`, `tasks`, `agents`)
    - per `(task, agent)` statistical rows with CI, pass rate, consistency, and per-trial details
    - current ELO ratings
    - aggregate summary block
- Updated `coderace/commands/benchmark.py`:
  - Added `--export` flag to write standardized benchmark JSON output
  - Wired export generation after benchmark completion
  - Passed ELO ratings into report renderers
- Enhanced `coderace/benchmark_report.py`:
  - Added multi-trial statistical report mode (mean score +/- stddev in task grid)
  - Added CI, consistency, and reliability columns for multi-trial reports
  - Added ELO ratings section at the bottom (terminal/markdown/html)
  - Preserved single-trial backward-compatible rendering path

**Tests:**
- Added `tests/test_export.py` with 6 tests covering:
  - export JSON schema/structure
  - system info collection
  - statistical report columns for multi-trial mode
  - single-trial report backward compatibility
  - ELO ratings rendering in markdown/html
  - CLI `--export` integration output
- Full suite validation:
  - `python3 -m pytest`
  - Result: **443 passed**

**Next:**
- D5: version bump to `1.0.0`, README + changelog updates, final integration checks.

**Blockers:**
- None.

### D5: Version Bump + README + Changelog ✅

**Built:**
- Version updates:
  - `pyproject.toml` -> `1.0.0`
  - `coderace/__init__.py` -> `1.0.0`
- Documentation updates:
  - `README.md`:
    - added `--trials` and `--export` benchmark usage
    - added statistical report behavior (`CI`, consistency, reliability)
    - added ELO ratings command usage (`coderace ratings`, `--json`, `--reset`)
    - added standardized export JSON schema example
  - `CHANGELOG.md`:
    - added `1.0.0` release entry covering D1-D4 capabilities and integration coverage
- Added additional integration/edge validation tests in `tests/test_benchmark_v1_integration.py`:
  - full `--trials 3` + two-task + export + ELO persistence flow
  - single-agent ELO edge case
  - single-task/single-trial export edge case
  - always-failing agent reliability edge case

**Tests:**
- Full suite validation:
  - `python3 -m pytest`
  - Result: **447 passed**
- New tests added in this contract:
  - `tests/test_benchmark_trials.py` (6)
  - `tests/test_statistics.py` (9)
  - `tests/test_elo.py` (11)
  - `tests/test_export.py` (6)
  - `tests/test_benchmark_v1_integration.py` (4)
  - **Total new tests: 36**

**Next:**
- Contract complete.

**Blockers:**
- None.

### v1.0 Contract Summary (D1-D5)

- Deliverables completed in order: **D1, D2, D3, D4, D5**
- Full test suite after each deliverable: passed
- Final full suite status: **447 passed**
- Version now: **1.0.0**
