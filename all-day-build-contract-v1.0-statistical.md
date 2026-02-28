# All-Day Build Contract: v1.0 — Statistical Benchmarking & ELO Ratings

Status: In Progress
Date: 2026-02-28
Owner: Codex execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add statistical rigor to coderace benchmarks. Currently each (task, agent) pair runs once. v1.0 adds repeat trials with statistical analysis (mean, stddev, confidence intervals), a persistent ELO rating system that updates with every benchmark, and a standardized JSON export format for sharing results. This positions coderace as the METR-grade tool for agent benchmarking.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end (currently 411 tests).
4. New features must ship with docs and report addendum updates in the same pass.
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside the project directory.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing tests and docs before writing new code.
11. Use python3 (not python) for all commands. Use pip3 install --break-system-packages if pip installs are needed.
12. Run the FULL test suite (python3 -m pytest) after each deliverable, not just new tests.

## 3. Feature Deliverables

### D1. Trials Mode (--trials N) (core + CLI)

Add --trials flag to coderace benchmark run that runs each (task, agent) pair N times. Collect all results. Store per-trial results in the existing SQLite store.

The benchmark runner (coderace/benchmark.py) currently loops tasks x agents once. Modify it to loop N times per pair when trials > 1.

Required files:
- coderace/benchmark.py (modify run_benchmark to support trials)
- coderace/commands/benchmark.py (add --trials CLI flag)
- coderace/store.py (store per-trial results, add trial_number column or equivalent)

- [ ] Add --trials N flag to benchmark run command (default 1 for backward compat)
- [ ] Modify run_benchmark to repeat each (task, agent) pair N times
- [ ] Store each trial as a separate result row with trial_number
- [ ] Progress callback reports trial number (e.g., "Task: fibonacci | Agent: claude | Trial 2/5")
- [ ] Tests for D1 (at least 5 tests covering: single trial backward compat, multi-trial execution, storage, progress reporting)

### D2. Statistical Analysis Module (core)

New module coderace/statistics.py that computes aggregate statistics from multi-trial benchmark results.

Required files:
- coderace/statistics.py (new file)

Compute per (task, agent) pair:
- Mean score, stddev, 95% confidence interval
- Mean wall_time, stddev
- Mean cost, stddev
- Pass rate (fraction of trials with score > 0)
- Consistency score (1 - coefficient of variation of scores)

Compute per agent (across all tasks):
- Aggregate mean score with CI
- Win rate (fraction of tasks where this agent has highest mean score)
- Cost efficiency (mean score / mean cost)
- Reliability (fraction of trials that didn't error/timeout)

Use only Python stdlib (math, statistics module). No numpy/scipy dependency.

- [ ] Implement TrialStats dataclass (per task-agent pair stats)
- [ ] Implement AgentAggregateStats dataclass
- [ ] Implement compute_trial_stats function
- [ ] Implement compute_aggregate_stats function
- [ ] 95% CI calculation using t-distribution approximation (small sample safe)
- [ ] Tests for D2 (at least 8 tests: stats with 1 trial, 3 trials, 10 trials, edge cases like all-zero scores, single agent, CI width shrinks with more trials)

### D3. ELO Rating System (core + CLI + storage)

Persistent ELO ratings for agents, updated after each benchmark. Stored in SQLite alongside existing data.

Required files:
- coderace/elo.py (new file)
- coderace/store.py (add elo_ratings table)
- coderace/cli.py or coderace/commands/ (add coderace ratings command)

ELO implementation:
- Standard ELO with K=32
- After a benchmark, each task is treated as a "match" between all participating agents
- For each pair of agents on each task: higher mean score wins, draw if within 1 point
- Initial rating: 1500
- Ratings persist across benchmark runs (accumulate over time)

CLI:
- coderace ratings — show current ELO ratings table
- coderace ratings --reset — reset all ratings to 1500
- coderace ratings --json — JSON output

Integration:
- After coderace benchmark run completes, automatically update ELO ratings
- Print rating changes in the benchmark summary

- [ ] Implement ELO calculation (expected score, rating update)
- [ ] Create elo_ratings table in SQLite store
- [ ] Implement update_ratings(benchmark_result) function
- [ ] Add coderace ratings command with table/json output
- [ ] Add --reset flag
- [ ] Auto-update ratings after benchmark run
- [ ] Print rating deltas in benchmark summary output
- [ ] Tests for D3 (at least 8 tests: initial ratings, single match update, multi-task update, rating convergence, reset, JSON output, backward compat with existing DB)

### D4. Standardized Export Format + Enhanced Report (CLI + report)

Add --export flag to benchmark run that outputs a standardized JSON file for sharing benchmark results. Also enhance the existing benchmark report to include statistical data when trials > 1.

Required files:
- coderace/export.py (new file)
- coderace/benchmark_report.py (enhance with stats)
- coderace/commands/benchmark.py (add --export flag)

Export format (JSON):
{
  "coderace_version": "1.0.0",
  "benchmark_id": "bench-20260228-133000",
  "timestamp": "2026-02-28T13:30:00Z",
  "system": {"os": "...", "python": "...", "cpu": "..."},
  "config": {"trials": 5, "timeout": 300, "tasks": [...], "agents": [...]},
  "results": [
    {
      "task": "fibonacci",
      "agent": "claude",
      "trials": 5,
      "mean_score": 87.5,
      "stddev_score": 3.2,
      "ci_95": [83.1, 91.9],
      "mean_time": 45.2,
      "mean_cost": 0.03,
      "pass_rate": 1.0,
      "per_trial": [...]
    }
  ],
  "elo_ratings": {"claude": 1523, "codex": 1488},
  "summary": {}
}

Report enhancements:
- When trials > 1, show mean +/- stddev in the benchmark table
- Show CI range
- Show consistency/reliability column
- Show ELO ratings at the bottom

- [ ] Implement export_benchmark_json function
- [ ] Collect system info (os, python version, cpu)
- [ ] Add --export flag to benchmark run command
- [ ] Enhance benchmark report table with stats columns when trials > 1
- [ ] Include ELO ratings in report
- [ ] Tests for D4 (at least 6 tests: export JSON structure, system info collection, report with stats, report without stats backward compat, ELO in report)

### D5. Version Bump + README + Changelog

- [ ] Bump version to 1.0.0 in pyproject.toml and __init__.py
- [ ] Update README.md with: trials mode usage, ELO ratings, export format
- [ ] Add CHANGELOG.md entry for v1.0.0
- [ ] Ensure coderace version shows 1.0.0

## 4. Test Requirements

- [ ] Unit tests for each deliverable (see per-deliverable test counts above)
- [ ] Integration test: run benchmark with --trials 3 on 2 built-in tasks (mock agents), verify stats + ELO + export all work together
- [ ] Edge cases: 1 trial (backward compat), 1 agent, 1 task, agent that always fails
- [ ] All existing 411 tests must still pass
- [ ] Total new tests: minimum 35

## 5. Reports

- Write progress to progress-log.md after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
