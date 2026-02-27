# All-Day Build Contract: Benchmark Suite (v0.8.0)

Status: In Progress
Date: 2026-02-27
Owner: Codex/Claude execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add a `coderace benchmark` command that runs all (or selected) built-in tasks against one or more agents and produces a comprehensive comparison report. This is the killer distribution feature: users run `coderace benchmark --agents claude,codex` and get a shareable report comparing agent performance across standardized tasks.

The benchmark command orchestrates multiple `coderace run` invocations, collects results, computes aggregate statistics, and outputs a rich comparison in multiple formats (terminal table, markdown, HTML dashboard).

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end (existing 351 + new tests).
4. New features must ship with docs and report addendum updates in the same pass.
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside the project directory.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing tests and docs before writing new code.

## 3. Feature Deliverables

### D1. Benchmark Runner Core (`coderace/benchmark.py`)

The engine that orchestrates running multiple tasks against multiple agents sequentially. Each (task, agent) pair is a single `coderace run` invocation internally.

Required files:
- `coderace/benchmark.py` (new)
- `coderace/commands/benchmark.py` (new CLI command)
- Update `coderace/cli.py` to register the benchmark command

Behavior:
- `coderace benchmark --agents claude,codex,aider` runs ALL built-in tasks against each agent
- `coderace benchmark --agents claude --tasks fibonacci,json-parser` runs selected tasks only
- `coderace benchmark --agents claude --difficulty easy,medium` filter by difficulty
- Each run uses the same task definition and validation criteria
- Results are collected into a BenchmarkResult data structure
- Progress is shown in terminal during execution (which task, which agent, running...)
- `--dry-run` flag lists what would be run without executing
- `--timeout` per-task timeout (default: 300s)
- `--parallel N` to run N agents in parallel (default: 1, sequential)

- [ ] BenchmarkResult dataclass with per-task-per-agent results
- [ ] Benchmark runner that iterates tasks x agents
- [ ] CLI command with all flags above
- [ ] Dry-run mode
- [ ] Progress display during execution
- [ ] Tests for D1

### D2. Aggregate Statistics (`coderace/benchmark_stats.py`)

Compute aggregate metrics from benchmark results.

Required files:
- `coderace/benchmark_stats.py` (new)

Metrics to compute per agent:
- Total score (sum of task scores)
- Average score
- Pass rate (% of tasks with score > 0)
- Average time per task
- Total cost
- Cost efficiency (score per dollar)
- Win count (# of tasks where this agent scored highest)

Metrics to compute per task:
- Best agent (highest score)
- Hardest task (lowest average score)
- Fastest agent per task

- [ ] Per-agent aggregate stats
- [ ] Per-task aggregate stats
- [ ] Win/loss matrix
- [ ] Tests for D2

### D3. Benchmark Report Formats

Three output formats for benchmark results.

Required files:
- Update `coderace/reporter.py` or new `coderace/benchmark_report.py`
- Update `coderace/html_report.py` for HTML benchmark output

Formats:
1. **Terminal** (default): Rich table with agents as columns, tasks as rows, scores in cells. Summary row at bottom.
2. **Markdown** (`--format markdown`): Pipe-delimited table suitable for GitHub/README.
3. **HTML** (`--format html`): Self-contained HTML with the existing dashboard style, extended for benchmark comparison view.

The terminal output should look roughly like:
```
╔══════════════════╦════════════╦════════════╦════════════╗
║ Task             ║ Claude     ║ Codex      ║ Aider      ║
╠══════════════════╬════════════╬════════════╬════════════╣
║ fibonacci        ║ 100.0 (3s) ║  95.0 (5s) ║ 100.0 (8s) ║
║ json-parser      ║  85.0 (12s)║ 100.0 (9s) ║  70.0 (15s)║
║ ...              ║            ║            ║            ║
╠══════════════════╬════════════╬════════════╬════════════╣
║ TOTAL            ║ 185.0      ║ 195.0      ║ 170.0      ║
║ Win Rate         ║ 33%        ║ 50%        ║ 17%        ║
║ Avg Time         ║ 7.5s       ║ 7.0s       ║ 11.5s      ║
║ Total Cost       ║ $0.05      ║ $0.03      ║ $0.02      ║
╚══════════════════╩════════════╩════════════╩════════════╝
```

- [ ] Terminal table output with Rich
- [ ] Markdown table output
- [ ] HTML benchmark report
- [ ] Tests for D3

### D4. Benchmark Result Storage

Store benchmark results in the existing SQLite store for history tracking.

Required files:
- Update `coderace/store.py` to add benchmark result storage/retrieval
- `coderace benchmark history` subcommand

Behavior:
- Each benchmark run gets a unique ID (timestamp-based)
- `coderace benchmark history` lists past benchmark runs
- `coderace benchmark show <id>` displays a past benchmark result
- Results integrate with existing leaderboard data

- [ ] SQLite schema for benchmark runs
- [ ] Store/retrieve benchmark results
- [ ] `benchmark history` and `benchmark show` CLI commands
- [ ] Tests for D4

### D5. README and Documentation

Update README.md with benchmark usage and example output.

- [ ] Add "Benchmarking" section to README with usage examples
- [ ] Include example terminal output
- [ ] Document all benchmark CLI flags

## 4. Test Requirements

- [ ] Unit tests for BenchmarkResult dataclass
- [ ] Unit tests for aggregate statistics computation
- [ ] Unit tests for each report format (terminal, markdown, HTML)
- [ ] Unit tests for benchmark storage
- [ ] Integration test: dry-run mode lists correct task/agent combinations
- [ ] Integration test: benchmark with mock agent adapter produces correct results
- [ ] Edge cases: single agent, single task, no tasks match filter, agent timeout
- [ ] All existing 351 tests must still pass

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
