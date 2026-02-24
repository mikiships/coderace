# Changelog

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
