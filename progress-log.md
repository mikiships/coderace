# Model Selection Build Progress Log

**Date:** 2026-03-05
**Contract:** all-day-build-contract-model-selection.md

## D1: Base Adapter Model Support ✅

**Built:**
- `BaseAdapter.__init__(model=None)` — all adapters accept optional model at construction
- `build_command(task_description, model=None)` — model parameter in abstract method signature
- `run()` passes `self.model` to `build_command` and `parse_cost`

**Tests:** 18 new tests in `test_model_selection_d1_d2.py`
**Commit:** f54db60

## D2: Codex and Claude Adapter Model Flags ✅

**Built:**
- CodexAdapter: appends `--model <name>` when model provided (via init or build_command param)
- ClaudeAdapter: same pattern
- AiderAdapter, GeminiAdapter, OpenCodeAdapter: same pattern (all support --model flag)
- `parse_cost()` uses `model_name or self.model or DEFAULT_*_MODEL` for accurate pricing

**Tests:** Included in D1 commit (18 tests cover both)
**Commit:** f54db60

## D3: Agent:Model CLI Syntax ✅

**Built:**
- `parse_agent_spec(spec) -> (agent_name, model_or_None)` — parses "codex:gpt-5.4"
- `make_display_name(agent_name, model) -> str` — "codex (gpt-5.4)" or "codex"
- `instantiate_adapter(spec) -> BaseAdapter` — factory that sets adapter.name to display name
- CLI `run` command: uses `parse_agent_spec` + `instantiate_adapter` for all adapter creation
- Display names flow through `AgentResult.agent`
- Branch names sanitized (colons → dashes) for git compatibility
- Duplicate agents with different models fully supported
- Task YAML validation accepts `agent:model` syntax

**Tests:** 18 new tests in `test_model_selection_d3.py`
**Commit:** e6d910d

## D4: Benchmark and Race Command Integration ✅

**Built:**
- `benchmark.py`: all three adapter instantiation sites use `instantiate_adapter()`
- Sequential and worktree paths: `TaskAgentResult.agent` uses display name from `agent_result.agent`
- Branch names sanitized for benchmark runs
- `race.py`: `parse_agent_spec`-based validation accepts `agent:model` specs
- ELO ratings track model variants as separate entries (no schema change — names are distinct)
- Store, dashboard, leaderboard: model-qualified names flow through transparently

**Tests:** 8 new tests in `test_model_selection_d4.py`
**Commit:** 735e105

## D5: Documentation and Version Bump ✅

**Built:**
- Version bumped to 1.3.0 in `pyproject.toml` and `coderace/__init__.py`
- CHANGELOG.md: full 1.3.0 entry with Added/Changed sections
- README.md: "Model Selection" section with examples, YAML syntax, how-it-works
- `examples/model-selection.yaml`: complete working example file
- `tests/test_examples.py`: updated agent validation to accept `agent:model` syntax

**Tests:** 574 passing total (started with 525)
**Commit:** D5 commit pending

## Summary

All 5 deliverables complete. 49 new tests added (574 total vs 525 baseline).
Pre-existing intermittent failure: `test_store.py::TestEdgeCases::test_concurrent_writes` (race condition, unrelated to this feature).
