# Progress Log: Cost Tracking (v0.4.0)

Date: 2026-02-24
Contract: all-day-build-contract-cost-tracking.md

---

## D1: Cost Estimation Engine ✅

**What was built:**
- `coderace/cost.py` — pricing table (dict), `CostResult` dataclass, `calculate_cost()`, `get_pricing()`, `estimate_from_sizes()`, per-parser functions for all 5 adapters
- Pricing table covers: claude-sonnet-4-6, claude-opus-4-6, gpt-5.3-codex, gemini-2.5-pro, gemini-3.1-pro, aider-default, opencode-default
- Each adapter (`claude.py`, `codex.py`, `gemini.py`, `aider.py`, `opencode.py`) got a `parse_cost()` method delegating to the appropriate parser
- Fallback: `estimate_from_sizes()` estimates from input/output byte counts when token data unavailable
- `CostResult`: `input_tokens`, `output_tokens`, `estimated_cost_usd`, `model_name`, `pricing_source`

**Tests:** 45 new tests in `tests/test_cost.py` — all pass
- Unit tests for pricing table, get_pricing, calculate_cost, CostResult validation
- Per-parser tests: JSON usage, cost lines, token lines, edge cases (missing output, partial tokens, comma numbers)
- All-adapters-return-None-on-empty-output test

**Commit:** `fd0ad27` — D1: cost estimation engine

---

## D2: Results Integration ✅

**What was built:**
- `coderace/types.py` — `AgentResult.cost_result: Optional[CostResult]` and `Score.cost_result: Optional[CostResult]`
- `coderace/adapters/base.py` — default `parse_cost()` returning None; `run()` calls `self.parse_cost()` and stores result on `AgentResult`; fails gracefully (try/except)
- `coderace/scorer.py` — propagates `cost_result` from `AgentResult` to `Score`
- `coderace/reporter.py` — "Cost (USD)" column in terminal table; `save_results_json()` includes `cost` object (or `null`); stats table also has Cost column
- `coderace/commands/results.py` — Cost column in both `format_markdown_results()` and `format_markdown_from_json()`
- `coderace/html_report.py` — Cost (USD) column + $/score ratio column
- `coderace/stats.py` — `AgentStats.cost_mean`, `AgentStats.cost_stddev`; `aggregate_runs()` collects cost values from runs
- `coderace/cli.py` — terminal `results` table shows Cost column; `_save_stats_json` includes `cost_mean`/`cost_stddev`

**Tests:** 21 new tests in `tests/test_cost_integration.py` — all pass
- AgentResult/Score field presence
- Scorer propagation (with and without cost)
- Terminal table shows cost / dash
- JSON round-trip
- Markdown output
- HTML report
- Stats aggregation

**Commit:** `fa5c2b9` — D2: cost integration

---

## D3: Cost Configuration ✅

**What was built:**
- `coderace/types.py` — `Task.pricing: dict[str, tuple[float, float]] | None = None`
- `coderace/task.py` — parses `pricing:` section from YAML; validates structure (mapping, required fields, non-negative values); converts to `dict[str, (float, float)]`
- `coderace/task.py` — `create_template()` includes commented `pricing:` example
- `coderace/adapters/base.py` — `run()` accepts `no_cost: bool = False` and `custom_pricing: dict | None = None`; passes `custom_pricing` to `parse_cost()`; skips parsing when `no_cost=True`
- `coderace/cli.py` — `run` command has `--no-cost` flag; `_run_agent_sequential` and `_run_agent_worktree` accept and pass `no_cost`/`custom_pricing`; both call sites updated to pass `task.pricing`

**Tests:** 18 new tests in `tests/test_cost_config.py` — all pass
- YAML parsing: valid, multiple agents, model-name key, zero prices
- YAML error cases: invalid type, missing field, negative value
- Custom pricing affects cost calculation
- `--no-cost` disables parsing; cost enabled by default
- init template has pricing comment (commented out)
- CLI help includes `--no-cost`

**Commit:** `7633359` — D3: cost configuration

---

## D4: Documentation ✅

**What was built:**
- `README.md` — "Cost Tracking" section: example terminal table, per-adapter source table, `--no-cost` usage
- `README.md` — "Custom Pricing" section: YAML config example, default pricing table
- `CHANGELOG.md` — v0.4.0 entry listing all new features
- `examples/example-task.yaml`, `add-type-hints.yaml`, `fix-edge-case.yaml`, `write-tests.yaml` — all updated with commented `pricing:` section

**Commit:** `afc9c42` — D4: documentation

---

## Final Status

- All 4 deliverables complete ✅
- All checklist items checked ✅
- Test count: 130 (pre-existing) → 214 (final) = 84 new tests added
- All 214 tests pass ✅
- Version left at 0.3.0 (no PyPI publish) ✅
- No scope creep, no refactoring outside deliverables ✅
- Committed after each deliverable ✅
