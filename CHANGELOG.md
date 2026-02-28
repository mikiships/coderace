# Changelog

## [1.0.0] - 2026-02-28

### Added

- **Benchmark trials mode** — `coderace benchmark --trials N` now runs each `(task, agent)` pair repeatedly and stores each trial with `trial_number` in SQLite.
- **Statistical benchmarking module** — New `coderace/statistics.py` computes per-pair and per-agent aggregates: mean/stddev, 95% confidence intervals, pass rate, consistency, win rate, cost efficiency, and reliability.
- **Persistent ELO ratings** — New `coderace/elo.py` plus `elo_ratings` store table. Ratings update automatically after each benchmark using pairwise task outcomes and persist across runs.
- **`coderace ratings` command** — View persistent ELO rankings, output as JSON (`--json`), and reset all ratings (`--reset`).
- **Standardized benchmark export** — `coderace benchmark --export <path>` writes shareable JSON with run metadata, system info, per-trial details, aggregate stats, and current ELO ratings.
- **Enhanced benchmark report rendering** — Multi-trial reports now show statistical columns (`mean +/- stddev`, CI, consistency, reliability) and include ELO ratings in terminal/markdown/html output.
- **Integration and edge-case coverage for v1.0 flow** — Added tests for full `--trials 3` benchmark + export + ELO pipeline and edge cases (single trial/agent/task and always-failing agent).

## [0.7.0] - 2026-02-26

### Added

- **Built-in task library** — coderace ships with 6 curated benchmark tasks. Run `coderace run --builtin fibonacci` with zero setup. No YAML file needed.
- **`coderace tasks list`** — List all available built-in tasks with descriptions.
- **`coderace tasks show <name>`** — Print the full YAML of a built-in task.
- **`--builtin` flag for `coderace run`** — Run a built-in task by name instead of providing a file path.
- **6 benchmark tasks** — fibonacci (easy), json-parser (medium), markdown-to-html (medium), csv-analyzer (medium), http-server (medium-hard), binary-search-tree (hard).
- **`coderace/builtins/`** — Python API: `list_builtins()`, `load_builtin()`, `get_builtin_path()` for programmatic access to built-in tasks.

## [0.6.0] - 2026-02-25

### Added

- **`coderace dashboard`** — New command that generates a self-contained, single-file HTML dashboard from the SQLite results database. Includes aggregate leaderboard, race history with expandable details, per-agent performance cards, and CSS-only cost efficiency charts. Dark mode default with light/dark toggle. No external dependencies.
- **Dashboard CLI flags** — `--output`/`-o` (custom path), `--task` (filter by task), `--last N` (limit races), `--title` (custom title), `--open` (open in browser).
- **`--publish` flag** — Upload the generated dashboard to here.now for sharing. Anonymous publish (24h expiry) or persistent publish with `--here-now-key` / `HERENOW_API_KEY` env var.
- **`coderace/publish.py`** — here.now API client implementing the 3-step publish flow (create → upload → finalize) using only stdlib `urllib`.
- **`coderace/dashboard.py`** — Dashboard HTML generator with responsive CSS, dark/light theme toggle, and expandable race history rows.

## [0.5.0] - 2026-02-24

### Added

- **Persistent result storage** — Every `coderace run` now automatically saves results to a local SQLite database at `~/.coderace/results.db`. Configurable via `CODERACE_DB` env var.
- **`coderace leaderboard`** — New command showing aggregate rankings across all runs. Columns: Agent, Wins, Races, Win%, Avg Score, Avg Cost, Avg Time. Supports `--task`, `--since`, `--min-runs` filters and `--format terminal|markdown|json|html` output.
- **`coderace history`** — New command showing past runs (newest first). Columns: Run ID, Date, Task, Agents, Winner, Best Score. Supports `--task`, `--agent`, `--limit` filters and `--format terminal|markdown|json` output.
- **`--no-save` flag** — `coderace run task.yaml --no-save` skips persisting results to the database.
- **`coderace/store.py`** — `ResultStore` class with `save_run()`, `get_runs()`, `get_agent_stats()`. Auto-creates DB and tables on first use. WAL mode, proper indexes, concurrent write support.
- **Integration test** — Full workflow test: run -> save -> leaderboard -> history.

## [0.4.0] - 2026-02-24

### Added

- **Cost tracking** — Each agent run now includes an estimated API cost. The results table shows a `Cost (USD)` column in terminal, markdown, JSON, and HTML output.
- **`coderace/cost.py`** — Pricing engine: pricing table for Claude Code (Sonnet 4.6, Opus 4.6), Codex (GPT-5.3), Gemini CLI (2.5 Pro, 3.1 Pro), Aider, and OpenCode. `CostResult` dataclass with `input_tokens`, `output_tokens`, `estimated_cost_usd`, `model_name`, `pricing_source`.
- **Per-adapter `parse_cost()` methods** — Each adapter extracts token counts or cost info from the agent's stdout/stderr. Falls back to file-size estimation when tokens are unavailable.
- **`pricing:` section in task YAML** — Override pricing per-agent or per-model with `input_per_1m` / `output_per_1m` (USD per 1M tokens).
- **`--no-cost` flag** — `coderace run task.yaml --no-cost` disables cost tracking entirely.
- **HTML report $/score column** — The HTML report now shows cost and cost-per-point for direct efficiency comparison.
- **Statistical mode cost aggregation** — `--runs N` shows mean ± stddev for cost alongside score and time.
- **`coderace init` template** — Now includes a commented `pricing:` example section.

## [0.3.0] - 2026-02-24

### Added

- **`coderace diff`** - Generate task YAML from a git diff. Three modes: `review` (find bugs), `fix` (apply fixes), `improve` (refactor). Pipe any diff in, get a ready-to-race task out.
- **GitHub Action** - `uses: mikiships/coderace@main` drops into any workflow. Races agents on your task and posts a results table as a PR comment. Re-runs update the same comment.
- **Example CI workflows** - Two drop-in configs: PR trigger and label trigger (`race-agents`).
- **`--format` flag for results** - `coderace results task.yaml -F markdown|json|terminal` for CI-friendly output.

## [0.2.0] - 2026-02-23

### Added

- **OpenCode adapter** - OpenCode (terminal-first open-source coding agent) is now a supported agent (`opencode` in task YAML)
- **Custom scoring weights** - Override default weights in task YAML via `scoring:` section; weights are auto-normalized; supports short aliases (`tests`, `exit`, `lint`, `time`, `lines`)
- **HTML reports** - Self-contained single-file HTML report auto-generated on every run at `.coderace/<task>-results.html`; also `coderace results --html report.html` for manual export; sortable columns, dark theme
- **Statistical mode** - `coderace run task.yaml --runs N` for multi-run comparison; shows mean ± stddev for score, time, and lines changed; saves per-run and aggregated JSON
- **Example tasks** - `examples/` directory with 3 ready-to-use templates: `add-type-hints.yaml`, `fix-edge-case.yaml`, `write-tests.yaml`

### Changed

- `coderace init` template now includes OpenCode in default agent list
- `coderace init` template includes commented scoring example
- README: "Try it now" section, statistical mode docs, HTML report docs, custom scoring docs, updated agent table

### Fixed

- `opencode` now accepted as a valid agent name in task validation

## [0.1.0] - 2026-02-22

### Added

- Initial release
- CLI: `init`, `run`, `results`, `version` commands
- 4 agent adapters: Claude Code, Codex, Aider, Gemini CLI
- Sequential and parallel (git worktrees) run modes
- Composite scoring: tests (40%), exit (20%), lint (15%), time (15%), lines (10%)
- JSON results output
- Rich terminal table output
- `coderace run --parallel` using git worktrees
