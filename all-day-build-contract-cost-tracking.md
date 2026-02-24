# All-Day Build Contract: Cost Tracking (v0.4.0)

Status: In Progress
Date: 2026-02-24
Owner: Sub-agent execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add cost tracking to coderace so users can compare coding agents on quality-per-dollar, not just quality alone. When a race finishes, each agent's result includes estimated API cost. The results table shows a $/score column. This is the #1 missing comparison axis: everyone benchmarks speed and quality, nobody automates cost comparison.

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

### D1. Cost estimation engine (core)

Build a cost estimation module that maps agent CLI output to dollar costs. Each agent adapter gets a `parse_cost()` method that extracts token counts or cost info from the agent's stdout/stderr.

Required:
- `coderace/cost.py` — pricing tables, cost calculation logic
- `coderace/adapters/*.py` — updated with parse_cost() methods

- [ ] Pricing table for: Claude Code (Sonnet 4.6, Opus 4.6), Codex (GPT-5.3), Gemini CLI (Gemini 2.5 Pro, Gemini 3.1 Pro), Aider (configurable model), OpenCode (configurable model)
- [ ] Parse token counts from each agent's output (Claude Code prints session summary, Codex prints usage, etc.)
- [ ] Fallback: if token counts unavailable, estimate from input file size + output diff size using per-model pricing
- [ ] CostResult dataclass: input_tokens, output_tokens, estimated_cost_usd, model_name, pricing_source
- [ ] Tests for D1: unit tests for each parser, edge cases (missing output, unknown model)

### D2. Results integration

Integrate cost data into the race results pipeline. Show cost alongside score in all output formats.

Required:
- `coderace/results.py` — updated
- `coderace/cli.py` — updated

- [ ] Race results include cost_usd field per agent
- [ ] `coderace results` terminal output shows Cost column
- [ ] `--format markdown` includes cost column
- [ ] `--format json` includes cost object
- [ ] HTML report includes cost column with $/score ratio
- [ ] Statistical mode (`--runs N`) aggregates cost: mean ± stddev
- [ ] Tests for D2

### D3. Cost configuration

Allow users to override pricing in task YAML (for custom models, negotiated rates, etc).

Required:
- `coderace/config.py` or extend task YAML schema

- [ ] `pricing:` section in task YAML: per-agent or per-model overrides
- [ ] `coderace init` template includes commented pricing example
- [ ] `--no-cost` flag to disable cost tracking entirely
- [ ] Tests for D3

### D4. Documentation

- [ ] README section: "Cost Tracking" with example output
- [ ] README section: "Custom Pricing" showing YAML config
- [ ] CHANGELOG entry for v0.4.0
- [ ] Update example task YAMLs with pricing comments

## 4. Test Requirements

- [ ] Unit tests for cost parsing (each adapter)
- [ ] Unit tests for pricing calculation
- [ ] Integration test: full race with cost output
- [ ] Edge cases: agent crashes (no cost data), unknown model, zero tokens
- [ ] All existing 130 tests must still pass

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
