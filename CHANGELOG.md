# Changelog

## [1.8.0] - 2026-03-12

### Added
- **Maintainer Rubric Mode** (`--maintainer-mode`): Score PRs on the same criteria real maintainers use to accept/reject — inspired by METR research (Mar 2026) showing ~50% of SWE-bench-passing PRs would be rejected by actual maintainers
  - `coderace review --maintainer-mode`: Appends a maintainer rubric section to review output
  - `coderace benchmark --maintainer-mode`: Adds maintainer rubric context to benchmark output
  - 5 scoring dimensions (each 0-100): **Minimal Diff**, **Convention Adherence**, **Dep Hygiene**, **Scope Discipline**, **Idiomatic Patterns**
  - Weighted composite score with Green/Yellow/Red verdicts (≥80 pass, 50-79 warn, <50 fail)
  - Pure static analysis — no LLM required, works on any git diff
  - Rich terminal table via `MaintainerRubricDisplay` in `coderace/display.py`
  - JSON output includes `maintainer_rubric` key with all dimension scores + composite
  - Markdown report output includes a "Maintainer Rubric" section with METR research context

## [1.7.0] - 2026-03-10

### Added
- **`coderace context-eval`**: A/B test whether a context file (CLAUDE.md, AGENTS.md, .cursorrules, etc.) actually improves agent performance
  - Runs N trials per condition: baseline (no context file) vs treatment (with context file)
  - Produces statistical comparison with 95% confidence intervals, Cohen's d effect size, and per-task breakdown
  - Summary verdict: "Context file improved performance by X% (CI: [lo, hi])" or "No significant improvement detected"
  - Output formats: Rich terminal table (default) and JSON (`--output`)
  - Backup/restore logic for pre-existing context files in the task directory
- **Dashboard integration**: `coderace dashboard --context-eval <json>` embeds A/B comparison section with bar charts and delta table
- **`examples/context-eval-demo.sh`**: end-to-end demo script (create context file → run A/B eval → generate dashboard)
- Reuses existing agent execution, task loading, and statistical infrastructure for consistency

## [1.6.0] - 2026-03-10

### Added
- **GitHub Action `mode: review`**: First-class PR review support in the GitHub Action — auto-extracts the PR diff and runs `coderace review` on it, posting results as a PR comment
- New action inputs: `mode`, `diff-source`, `lanes`, `cross-reviewers`, `json-out`, `md-out`
- New action outputs: `review-json`, `review-md`
- **`scripts/ci-review.sh`**: CI script handling diff extraction for `pr`, `commit:<sha>`, `branch:<base>...<head>`, and `file:<path>` sources; emits `GITHUB_OUTPUT` compatible outputs
- **`scripts/format-review-comment.py`**: Formats review JSON as a GitHub PR comment with per-lane findings, cross-review synthesis section, severity breakdown, and collapsible raw JSON
- **`.github/workflows/examples/coderace-pr-review.yml`**: Copy-pasteable example workflow for enabling PR review in any repo
- PR comment includes `<!-- coderace-review -->` marker for find-and-update across PR syncs
- Backward compatible: existing `mode: run` (or no `mode` input) continues to work exactly as v1.5.0

## [1.5.0] - 2026-03-10

### Added
- **`coderace review`**: Run multi-lane parallel code review directly on a diff without generating a task YAML first
- Built-in review lanes: `null-safety`, `type-safety`, `error-handling`, `contracts`, `security`, and `performance`
- Optional **Phase 2 cross-review** (`--cross-review`) to identify missed issues, weak claims, and disagreements across first-pass findings
- `coderace/review.py`: deterministic prompt generation, structured finding parsing, parallel review execution, and consolidated `ReviewResult`
- `coderace/review_report.py`: markdown and JSON report rendering with lane grouping and severity summary table
- Review-mode test coverage: unit, renderer, CLI, and end-to-end mocked-adapter integration with a canned 3-file patch fixture

## [1.4.0] - 2026-03-05

### Added
- **4 new benchmark tasks** testing real-world coding skills beyond "build from scratch":
  - `bug-hunt`: Find and fix 5 planted bugs in a calculator module (debugging)
  - `refactor`: Improve messy code while keeping existing tests passing (refactoring)
  - `concurrent-queue`: Thread-safe priority queue with producer/consumer pattern (concurrency)
  - `api-client`: HTTP client with retry, rate limiting, and circuit breaker (API design)
- Total built-in tasks: 20 (up from 16)

## [1.3.0] - 2026-03-05

### Added
- **Model selection**: Per-agent model override via `agent:model` syntax in `--agents` / `--agent` flags
  - Example: `coderace run task.yaml --agent codex:gpt-5.4 --agent codex:gpt-5.3-codex`
  - Example: `coderace benchmark --agents claude:opus-4-6,claude:sonnet-4-6`
- `BaseAdapter.__init__(model=None)`: all adapters accept optional model at construction
- `BaseAdapter.build_command(task, model=None)`: model parameter flows to CLI flag
- `parse_agent_spec()`, `make_display_name()`, `instantiate_adapter()` in `coderace.adapters`
- All adapters (codex, claude, aider, gemini, opencode) append `--model <name>` when specified
- Benchmark and race commands handle model-specific agents; display names flow to results, store, ELO, dashboard
- Task YAML: `agents` list accepts `agent:model` entries (e.g. `- codex:gpt-5.4`)

### Changed
- `AgentResult.agent` is now the display name (`codex (gpt-5.4)`) when a model is specified
- ELO ratings, leaderboard, and dashboard automatically track model variants as separate entries
- Branch names sanitized to be git-compatible (colons replaced with dashes)

## [1.2.0] - 2026-03-03

### Added

- **`coderace race` command** - New first-to-pass race mode with early-stop semantics. Agents run in parallel worktrees and the race ends when the first winner is found.
- **Live race UI** - Rich `Live` panel with per-agent status and timers:
  - `🔨 coding...`
  - `🧪 testing...`
  - `✅ WINNER!`
  - `❌ failed`
  - `⏰ timed out`
  - `🛑 stopped`
- **Winner announcement and runner-up delta** - Prints race winner and optional runner-up timing delta after the live panel closes.
- **Race result persistence (JSON fallback)** - Saves race summaries to `.coderace/race-results.json` including `race_id`, winner metadata, participant statuses, exit codes, and wall times. Supports `--no-save`.
- **Race test suite** - Added 21 race-focused tests (`tests/test_race.py`) covering winner logic, cancellation, timeout/no-winner paths, verification modes, live updates, serialization, and Ctrl+C cleanup.

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
