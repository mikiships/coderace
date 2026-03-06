# All-Day Build Contract: Model Selection for Adapters

Status: In Progress
Date: 2026-03-05
Owner: Codex execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add per-agent model selection to coderace so users can benchmark different models within the same agent CLI. For example: `coderace run task.yaml --agents codex:gpt-5.4,codex:gpt-5.3-codex,claude:opus-4-6,claude:sonnet-4-6` to compare models head-to-head on the same tasks.

This enables the "which model is actually best for coding" benchmark content that vibes-based blog posts can't provide.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end.
4. New features must ship with docs and report addendum updates in the same pass.
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside the project directory.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing tests and docs before writing new code.

## 3. Feature Deliverables

### D1. Base Adapter Model Support (core)

Add optional `model` parameter to BaseAdapter so subclasses can receive a model override.

Required files:
- `coderace/adapters/base.py`

- [ ] Add `model: Optional[str] = None` to `__init__` (or as class attribute)
- [ ] Pass `model` through to `build_command` signature: `build_command(self, task_description: str, model: Optional[str] = None) -> list[str]`
- [ ] Update `run()` to pass model to `build_command`
- [ ] Update `parse_cost` calls to use the model override when provided
- [ ] Tests for D1

### D2. Codex and Claude Adapter Model Flags

Update the two main adapters to pass `--model` when a model is specified.

Required files:
- `coderace/adapters/codex.py`
- `coderace/adapters/claude.py`

- [ ] CodexAdapter.build_command: append `--model`, model_name when model is not None
- [ ] ClaudeAdapter.build_command: append `--model`, model_name when model is not None
- [ ] Update parse_cost to use the provided model name for accurate pricing
- [ ] Also update aider.py, gemini.py, opencode.py adapters if they support model flags (check their --help)
- [ ] Tests for D2

### D3. Agent:Model CLI Syntax

Parse `agent:model` syntax in the CLI so users can specify models per agent.

Required files:
- `coderace/cli.py` (or wherever `--agents` is parsed)
- `coderace/adapters/__init__.py` (adapter registry/factory)

The syntax: `--agents codex:gpt-5.4,claude:opus-4-6`
- If no `:model` suffix, use the adapter's default (current behavior)
- If `:model` suffix, pass it through to the adapter
- The same agent can appear multiple times with different models
- Agent display name in results should include the model: `codex (gpt-5.4)` vs `codex (gpt-5.3-codex)`

- [ ] Parse `agent:model` in CLI --agents flag
- [ ] Support duplicate agents with different models in the same run
- [ ] Display agent+model in result tables and reports
- [ ] Works with `run`, `benchmark`, and `race` commands
- [ ] Tests for D3

### D4. Benchmark and Race Command Integration

Ensure `benchmark` and `race` commands correctly handle model-specific agents.

Required files:
- `coderace/benchmark.py`
- `coderace/commands/` (race command if separate)
- `coderace/store.py` (results storage)

- [ ] Benchmark results store agent+model as the identifier (not just agent name)
- [ ] ELO ratings track agent+model combinations separately
- [ ] Leaderboard shows model variants as separate entries
- [ ] Dashboard HTML includes model information
- [ ] Tests for D4

### D5. Documentation and Version Bump

- [ ] Update README.md with model selection examples
- [ ] Add model selection section to examples/
- [ ] Update CHANGELOG.md
- [ ] Bump version to 1.3.0 in pyproject.toml
- [ ] All existing 526 tests still pass
- [ ] New tests bring total to 550+

## 4. Test Requirements

- [ ] Unit tests for each adapter with model override
- [ ] Unit tests for agent:model parsing
- [ ] Integration test: dry-run benchmark with model variants
- [ ] Edge cases: invalid model name, empty model, agent without model support
- [ ] All existing 526 tests must still pass

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
