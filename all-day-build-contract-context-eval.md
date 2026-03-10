# All-Day Build Contract: Context Eval

Status: COMPLETE
Date: 2026-03-02
Owner: Codex execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add a `coderace context-eval` command that measures whether context files (CLAUDE.md, AGENTS.md, .cursorrules, etc.) actually improve agent performance on coding tasks. Runs A/B trials: baseline (no context file) vs treatment (with context file), produces statistical comparison with confidence intervals. This is the first tool that lets developers empirically measure context engineering impact.

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

### D1. `context-eval` CLI Command (core + CLI)

Add a new `context-eval` subcommand to the coderace CLI that:
- Accepts `--context-file PATH` (the file to evaluate, e.g., CLAUDE.md)
- Accepts `--task PATH` (a single task YAML) or `--benchmark` (run built-in tasks)
- Accepts `--agents AGENT1,AGENT2` (which agents to test, default: all configured)
- Accepts `--trials N` (number of trials per condition, default: 3, min: 2)
- Accepts `--output PATH` (optional JSON output path)
- Accepts `--task-dir PATH` (optional, custom task directory for benchmark mode)

Workflow:
1. For each agent × task combination:
   a. Run N trials WITHOUT the context file present (baseline condition)
   b. Run N trials WITH the context file placed in the task working directory (treatment condition)
2. Collect pass/fail + timing for each trial
3. Produce comparison report

The context file placement: copy the file to the task's working directory before treatment trials, remove it after. If a context file already exists in the task dir, back it up and restore after.

Required files:
- `coderace/context_eval.py` (core logic)
- `coderace/cli.py` (add subcommand)

- [ ] CLI argument parsing with validation
- [ ] Baseline runner (strips context files from task dir)
- [ ] Treatment runner (places context file in task dir)
- [ ] Backup/restore logic for pre-existing context files
- [ ] Integration with existing `run` infrastructure (reuse task loading, agent execution, scoring)
- [ ] Tests for D1

### D2. Statistical Comparison Report

After running both conditions, produce a comparison report that includes:
- Per-agent: baseline pass rate vs treatment pass rate
- Delta (treatment - baseline) with 95% confidence interval
- Effect size (Cohen's d or similar)
- Per-task breakdown: which tasks improved, which degraded
- Summary verdict: "Context file improved performance by X% (CI: [lo, hi])" or "No significant improvement detected"

Output formats:
- Rich terminal table (default, using existing table formatting)
- JSON (with `--output`)

Reuse existing statistical infrastructure from `benchmark` command where possible (confidence intervals, etc.).

- [ ] Statistical comparison logic (delta, CI, effect size)
- [ ] Terminal table report
- [ ] JSON output
- [ ] Summary verdict logic
- [ ] Tests for D2

### D3. Dashboard Integration

Extend the existing `dashboard` command to include context-eval results when available:
- New section in HTML dashboard showing A/B comparison
- Bar chart: baseline vs treatment pass rates per agent
- Delta chart with confidence intervals

Reuse existing dashboard infrastructure (Jinja templates, chart generation).

- [ ] Dashboard data model for context-eval results
- [ ] HTML template section for A/B comparison
- [ ] Charts (bar chart + delta chart)
- [ ] Tests for D3

### D4. Documentation + Examples

- [ ] Update README.md with context-eval section (usage, examples, interpretation guide)
- [ ] Add example in `examples/` directory: `context-eval-demo.yaml` or script
- [ ] Update `coderace --help` / `coderace context-eval --help` with clear descriptions
- [ ] Add a section on "Measuring Context Engineering Impact" to README

## 4. Test Requirements

- [ ] Unit tests for context file placement/removal/backup logic
- [ ] Unit tests for statistical comparison (known inputs → known outputs)
- [ ] Integration test: mock agent that passes more with context vs without
- [ ] Edge cases: no agents configured, context file doesn't exist, task dir already has context file, trials=1 (should error), 0 tasks selected
- [ ] All existing tests (447) must still pass

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing → DONE
- 3 consecutive failed attempts on same issue → STOP, write blocker report
- Scope creep detected (new requirements discovered) → STOP, report what's new
- All tests passing but deliverables remain → continue to next deliverable
