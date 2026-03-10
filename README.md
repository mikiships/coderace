# coderace

[![PyPI](https://img.shields.io/pypi/v/coderace)](https://pypi.org/project/coderace/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#install)
[![Tests](https://img.shields.io/badge/tests-526%20passing-brightgreen)](#)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#license)

Stop reading blog comparisons. Race coding agents against each other on real tasks in *your* repo with *your* code.

Every week there's a new "Claude Code vs Codex vs Cursor" post. They test on toy problems with cherry-picked examples. coderace gives you automated, reproducible, scored comparisons on the tasks you actually care about.

Define a task. Run it against Claude Code, Codex, Aider, Gemini CLI, and OpenCode. Get a scored comparison table.

## Install

```bash
pip install coderace
```

## Quick Start

```bash
# Race agents on a built-in task (no setup required):
coderace run --builtin fibonacci

# Or create your own task:
coderace init fix-auth-bug

# Edit the task file (describe the bug, set test command)
# Then race the agents:
coderace run fix-auth-bug.yaml

# Or race them in parallel (uses git worktrees):
coderace run fix-auth-bug.yaml --parallel

# View results from the last run
coderace results fix-auth-bug.yaml
```

## `coderace diff` — Race Agents on a Real PR Diff

Turn any git diff into a coderace task with one command:

```bash
# Race agents to review the latest commit
git diff HEAD~1 | coderace diff --mode review | coderace run /dev/stdin

# Generate a task YAML from a patch file, then run it
git diff main...my-branch > my-pr.patch
coderace diff --file my-pr.patch --mode fix --output task.yaml
coderace run task.yaml
```

### Modes

| Mode | What agents are asked to do |
|------|-----------------------------|
| `review` | Review the changes and provide feedback on correctness, style, and potential issues |
| `fix` | Fix bugs or problems introduced by the diff |
| `improve` | Enhance performance, readability, or robustness of the changed code |

### Flags

```
--file PATH       Read diff from file instead of stdin
--mode TEXT       review | fix | improve  (default: review)
--agents TEXT     Override agent list (repeatable: --agents claude --agents aider)
--name TEXT       Task name in generated YAML  (default: diff-task)
--output PATH     Write YAML to file instead of stdout
--test-command    Test command to embed in the task (default: pytest tests/ -x)
--lint-command    Lint command to embed in the task (default: ruff check .)
```

## `coderace review` — Run Multi-Lane PR Review Directly

Run parallel review agents against a diff without generating an intermediate task YAML. Each lane isolates a specific review focus, and `--cross-review` adds a second phase that challenges the first-pass findings.

```bash
# Pipe a diff from stdin
git diff HEAD~1 | coderace review

# Review a specific commit
coderace review --commit HEAD

# Review a branch range
coderace review --branch main...my-branch

# Add phase 2 cross-review and write the report to disk
coderace review --diff my-pr.patch --cross-review --output review.md
```

### Review Lanes

| Lane | Focus |
|------|-------|
| `null-safety` | Null / `None` dereferences and missing guards |
| `type-safety` | Type mismatches, coercion bugs, missing annotations |
| `error-handling` | Uncaught exceptions, missing error paths, swallowed failures |
| `contracts` | API contracts, preconditions, postconditions, interface mismatches |
| `security` | Injection, auth bypass, unsafe deserialization, secrets exposure |
| `performance` | O(n²) work, blocking calls, avoidable allocations |

### Review Flags

```
--diff PATH        Read diff from file
--commit TEXT      Generate diff from commit ref (git diff <ref>~1 <ref>)
--branch TEXT      Generate diff from branch range (git diff <base>...<head>)
--lanes TEXT       Comma-separated lanes
--agents TEXT      Comma-separated agents
--cross-review     Run a second review phase to find gaps and disagreements
--format TEXT      markdown | json
--output PATH      Write report to file instead of stdout
--no-color         Plain stderr/status output
```

## Task Format

```yaml
name: fix-auth-bug
description: |
  The login endpoint returns 500 when email contains a plus sign.
  Fix the email validation in auth/validators.py.
repo: .
test_command: pytest tests/test_auth.py -x
lint_command: ruff check .
# Optional: independent verification suite written after agent completes
# verify_command: python3 -m pytest verify_auth.py -x -q
# verify_files:
#   verify_auth.py: |
#     def test_real_contract():
#       assert True
timeout: 300
agents:
  - claude
  - codex
  - aider
```

## What It Does

For each agent in the task:

1. Creates a fresh git branch (`coderace/<agent>-<task>`)
2. Invokes the agent CLI with the task description
3. Runs your test command
4. Runs your lint command (optional)
5. Computes a composite score

## Scoring

| Metric | Weight | Description |
|--------|--------|-------------|
| Tests pass | 40% | Did the test command exit 0? |
| Exit clean | 20% | Did the agent itself exit 0 without timeout? |
| Lint clean | 15% | Did the lint command exit 0? |
| Wall time | 15% | Faster is better (normalized across agents) |
| Lines changed | 10% | Fewer is better (normalized across agents) |

## Verification Tests

For stronger evaluation, tasks can define an independent verification suite that the agent does not control.

```yaml
verify_command: python3 -m pytest verify_api_contract.py -x -q
verify_files:
  verify_api_contract.py: |
    def test_contract_behavior():
      assert True
```

Flow for verification-enabled tasks:
1. Agent completes implementation.
2. `test_command` runs (agent-authored tests).
3. `verify_files` are written into the workspace (overwriting same-path files).
4. `verify_command` runs.

Default scoring when `verify_command` is present:
- tests: 25%
- verify: 30%
- exit: 20%
- lint: 15%
- time: 5%
- lines: 5%

Tasks without `verify_command` keep the legacy default scoring (40/20/15/15/10).

## Output

Terminal table with Rich formatting:

```
┌──────┬────────┬───────┬───────┬──────┬──────┬──────────┬───────┐
│ Rank │ Agent  │ Score │ Tests │ Exit │ Lint │ Time (s) │ Lines │
├──────┼────────┼───────┼───────┼──────┼──────┼──────────┼───────┤
│  1   │ claude │  85.0 │ PASS  │ PASS │ PASS │     10.5 │    42 │
│  2   │ codex  │  70.0 │ PASS  │ PASS │ FAIL │     15.2 │    98 │
│  3   │ aider  │  55.0 │ FAIL  │ PASS │ PASS │      8.1 │    31 │
└──────┴────────┴───────┴───────┴──────┴──────┴──────────┴───────┘
```

Results also saved as JSON in `.coderace/<task>-results.json` and as a self-contained HTML report in `.coderace/<task>-results.html`.

## Built-in Tasks

coderace ships with benchmark tasks you can run immediately — no YAML file needed:

```bash
# List available tasks
coderace tasks list

# Show a task's full YAML
coderace tasks show fibonacci

# Run a built-in task
coderace run --builtin fibonacci
```

| Task | Difficulty | Description |
|------|-----------|-------------|
| `fibonacci` | Easy | Fibonacci with memoization + tests |
| `json-parser` | Medium | JSON parser from scratch (no json module) |
| `markdown-to-html` | Medium | Markdown subset to HTML converter |
| `csv-analyzer` | Medium | CLI tool for CSV summary statistics |
| `http-server` | Medium-Hard | HTTP/1.1 server using only stdlib socket |
| `binary-search-tree` | Hard | AVL tree with insert, delete, search, and balancing |
| `regex-engine` | Hard | Regex engine with custom matcher + verification suite |
| `lru-cache` | Hard | Thread-safe LRU + TTL correctness verification |
| `expression-evaluator` | Hard | Expression parser/evaluator with precedence and functions |
| `url-router` | Hard | HTTP-style router with params, wildcard, and 405/404 logic |
| `diff-algorithm` | Hard | Unified diff + patch application roundtrip checks |
| `task-scheduler` | Hard | Dependency-aware priority scheduler with timeout handling |
| `bug-hunt` | Hard | Find and fix 5 planted bugs in a calculator module |
| `refactor` | Hard | Refactor messy code while keeping tests passing |
| `concurrent-queue` | Hard | Thread-safe priority queue with producer/consumer |
| `api-client` | Hard | HTTP client with retry, rate limiting, circuit breaker |

`coderace tasks list` now includes a `Verify` column so you can see which built-ins ship with verification suites.

## Try It Now

The `examples/` directory has ready-to-use task templates:

```bash
# Race agents on adding type hints to your project
coderace run examples/add-type-hints.yaml

# Race agents on fixing an edge case bug
coderace run examples/fix-edge-case.yaml

# Race agents on writing new tests
coderace run examples/write-tests.yaml
```

Edit the `repo` and `description` fields to point at your actual project and describe your real task.

## Statistical Mode

Run each agent multiple times and get mean ± stddev:

```bash
coderace run task.yaml --runs 5
```

Useful for tasks with variable outcomes (LLM nondeterminism is real).

## HTML Reports

Export results as a shareable single-file HTML report:

```bash
# Auto-generated on every run at .coderace/<task>-results.html
# Or export manually:
coderace results task.yaml --html report.html
```

The HTML report has sortable columns and a dark theme. Drop it in a blog post or Slack.

## Custom Scoring

Override the default weights in your task YAML:

```yaml
scoring:
  tests: 60   # tests passing (default 40)
  exit: 20    # clean exit (default 20)
  lint: 10    # lint clean (default 15)
  time: 5     # wall time (default 15)
  lines: 5    # lines changed (default 10)
```

Weights are normalized automatically (don't need to sum to 100).

## Cost Tracking

coderace automatically estimates API cost for each agent run. After every race, the results table includes a **Cost (USD)** column so you can compare quality-per-dollar, not just quality alone.

```
┌──────┬────────┬───────┬───────┬──────┬──────┬──────────┬───────┬────────────┐
│ Rank │ Agent  │ Score │ Tests │ Exit │ Lint │ Time (s) │ Lines │ Cost (USD) │
├──────┼────────┼───────┼───────┼──────┼──────┼──────────┼───────┼────────────┤
│  1   │ claude │  85.0 │ PASS  │ PASS │ PASS │     10.5 │    42 │    $0.0063 │
│  2   │ codex  │  70.0 │ PASS  │ PASS │ FAIL │     15.2 │    98 │    $0.0041 │
│  3   │ aider  │  55.0 │ FAIL  │ PASS │ PASS │      8.1 │    31 │          - │
└──────┴────────┴───────┴───────┴──────┴──────┴──────────┴───────┴────────────┘
```

Cost appears in all output formats:
- **Terminal** — `Cost (USD)` column (shows `-` when unavailable)
- **Markdown** — `--format markdown` includes the column
- **JSON** — `cost` object per agent result with `input_tokens`, `output_tokens`, `estimated_cost_usd`, `model_name`, `pricing_source`
- **HTML report** — Cost column plus `$/score` ratio column for direct efficiency comparison

### How it works

Each agent adapter parses token counts or cost lines from the agent's CLI output:

| Agent | Source |
|-------|--------|
| Claude Code | `usage.input_tokens` / `usage.output_tokens` from JSON output; or "Total cost: $N" lines |
| Codex | `prompt_tokens=N, completion_tokens=N` usage summary |
| Gemini CLI | `inputTokenCount=N, outputTokenCount=N` lines |
| Aider | "Tokens: N sent, N received. Cost: $N message" lines |
| OpenCode | "Total cost: $N" or generic token lines |

If token counts are unavailable, cost is estimated from input file size + output diff size (marked as `pricing_source: "estimated"`).

### Disable cost tracking

```bash
coderace run task.yaml --no-cost
```

## Custom Pricing

Override the default pricing table in your task YAML — useful for custom models, negotiated rates, or open-source deployments.

```yaml
# pricing: per-agent or per-model overrides (USD per 1M tokens)
pricing:
  claude:
    input_per_1m: 3.00    # default for claude-sonnet-4-6
    output_per_1m: 15.00
  codex:
    input_per_1m: 3.00
    output_per_1m: 15.00
  # Or use the model name directly:
  claude-opus-4-6:
    input_per_1m: 15.00
    output_per_1m: 75.00
```

Keys can be agent names (`claude`, `codex`, `aider`, `gemini`, `opencode`) or model names (`claude-sonnet-4-6`, `gpt-5.3-codex`, `gemini-2.5-pro`). The default pricing table covers:

| Model | Input ($/1M) | Output ($/1M) |
|-------|-------------|--------------|
| claude-sonnet-4-6 | $3.00 | $15.00 |
| claude-opus-4-6 | $15.00 | $75.00 |
| gpt-5.3-codex | $3.00 | $15.00 |
| gemini-2.5-pro | $1.25 | $10.00 |
| gemini-3.1-pro | $1.25 | $10.00 |

Pricing is easy to update: the table lives in `coderace/cost.py` as a plain dict.

## Model Selection

Compare different models of the same agent head-to-head using the `agent:model` syntax:

```bash
# Compare two Codex models on the same task
coderace run task.yaml --agent codex:gpt-5.4 --agent codex:gpt-5.3-codex

# Mix agents and models
coderace run task.yaml --agent codex:gpt-5.4 --agent claude:opus-4-6 --agent claude:sonnet-4-6

# Benchmark multiple model variants across built-in tasks
coderace benchmark --agents codex:gpt-5.4,codex:gpt-5.3-codex,claude:opus-4-6

# Race with model variants (parallel)
coderace race task.yaml
```

In task YAML files:

```yaml
agents:
  - codex:gpt-5.4
  - codex:gpt-5.3-codex
  - claude:opus-4-6
  - claude:sonnet-4-6
```

**How it works:**
- `agent:model` splits on the first colon: `codex:gpt-5.4` → agent `codex`, model `gpt-5.4`
- The model is passed via `--model <name>` to the underlying CLI
- Results display as `codex (gpt-5.4)` vs `codex (gpt-5.3-codex)` for easy comparison
- ELO ratings, leaderboard, and dashboard track each model variant separately
- The same agent can appear multiple times with different models in one run

## Leaderboard & History

Every `coderace run` automatically saves results to a local SQLite database (`~/.coderace/results.db`). Two new commands aggregate this data.

### Leaderboard

```bash
# Show all-time rankings across all tasks
coderace leaderboard

# Filter by task
coderace leaderboard --task fix-auth-bug

# Only agents with 5+ races
coderace leaderboard --min-runs 5

# Filter by time
coderace leaderboard --since 7d
coderace leaderboard --since 2026-01-01

# Output formats
coderace leaderboard --format json
coderace leaderboard --format markdown
```

Example output:

```
┌──────┬────────┬──────┬───────┬──────┬───────────┬──────────┬──────────┐
│ Rank │ Agent  │ Wins │ Races │ Win% │ Avg Score │ Avg Cost │ Avg Time │
├──────┼────────┼──────┼───────┼──────┼───────────┼──────────┼──────────┤
│  1   │ claude │    5 │     8 │  63% │      82.3 │  $0.0055 │     10.2 │
│  2   │ codex  │    2 │     8 │  25% │      71.1 │  $0.0038 │     14.5 │
│  3   │ aider  │    1 │     6 │  17% │      65.4 │        - │     11.8 │
└──────┴────────┴──────┴───────┴──────┴───────────┴──────────┴──────────┘
```

### History

```bash
# Show recent runs
coderace history

# Filter by task or agent
coderace history --task fix-auth-bug
coderace history --agent claude

# Limit results
coderace history --limit 10

# Output as JSON or markdown
coderace history --format json
```

Example output:

```
┌────────┬─────────────────────┬──────────────┬────────────────┬────────┬────────────┐
│ Run ID │ Date                │ Task         │ Agents         │ Winner │ Best Score │
├────────┼─────────────────────┼──────────────┼────────────────┼────────┼────────────┤
│      3 │ 2026-02-24 14:32:10 │ fix-auth-bug │ claude, codex  │ claude │       90.0 │
│      2 │ 2026-02-24 14:30:05 │ add-types    │ claude, codex  │ codex  │       80.0 │
│      1 │ 2026-02-24 14:28:00 │ fix-auth-bug │ claude, aider  │ claude │       85.0 │
└────────┴─────────────────────┴──────────────┴────────────────┴────────┴────────────┘
```

### Configuration

- **Database location:** `~/.coderace/results.db` by default. Override with `CODERACE_DB` env var.
- **Skip saving:** `coderace run task.yaml --no-save` to run without persisting results.

## Dashboard & Publishing

Generate a shareable HTML dashboard from your race results:

```bash
# Generate dashboard.html in current directory
coderace dashboard

# Custom output path
coderace dashboard -o report.html

# Filter to a specific task, last 10 races
coderace dashboard --task fix-auth-bug --last 10

# Custom title and open in browser
coderace dashboard --title "My Team Benchmarks" --open

# Publish to here.now (anonymous, 24h expiry)
coderace dashboard --publish

# Publish with API key (persistent URL)
coderace dashboard --publish --here-now-key YOUR_KEY
```

The dashboard is a single self-contained HTML file (no external dependencies) with:
- Aggregate leaderboard table (wins, avg score, avg time, win rate, avg cost)
- Race history with expandable per-agent details
- Per-agent performance cards (total races, wins, best score, avg cost)
- CSS-only cost efficiency bar chart (cost per point)
- Dark mode default with light/dark toggle
- Responsive design (readable on mobile)

### Publishing

The `--publish` flag uploads the dashboard to [here.now](https://here.now) for sharing:
- Without an API key: anonymous publish with 24h expiry
- With `--here-now-key` or `HERENOW_API_KEY` env var: persistent URL

## Supported Agents

| Agent | CLI | Notes |
|-------|-----|-------|
| Claude Code | `claude` | Anthropic's coding agent |
| Codex | `codex` | OpenAI Codex CLI |
| Aider | `aider` | Git-integrated AI coding |
| Gemini CLI | `gemini` | Google's Gemini CLI |
| OpenCode | `opencode` | Open-source terminal agent |

Each agent must be installed and authenticated separately.

## Parallel Mode

Use `--parallel` (or `-p`) to run all agents simultaneously using git worktrees. Each agent gets its own isolated working directory, so they don't interfere with each other.

```bash
coderace run task.yaml --parallel
```

Sequential mode (default) runs agents one at a time on the same repo.

## Race Mode

Use `coderace race` for first-to-pass execution. Unlike `coderace run --parallel`, race mode stops as soon as one agent passes the win condition:

- If verification is configured, winner = first agent that passes verification.
- If verification is not configured, winner = first agent that exits cleanly.
- Remaining agents are stopped after a short graceful shutdown window.

```bash
coderace race task.yaml --agent claude --agent codex
```

Example terminal output:

```text
🏁 coderace race - fix-auth-bug
Running 3 agents in parallel...

Agent   Status                 Time
claude  🔨 coding...           0:00:23
codex   🧪 testing...          0:00:31
aider   🛑 stopped             0:00:18

🏆 Winner: codex - completed in 1:23 (first to pass verification)
Runner-up: claude - finished 0:12 later
```

When to use each mode:
- Use `coderace race` when you want the fastest successful patch and can stop early.
- Use `coderace run --parallel` when you want full scoring across all agents before deciding.

## Why coderace?

**Blog posts compare models. coderace compares agents on your work.**

- Run on your actual codebase, not HumanEval
- Automated scoring: tests, lint, time, lines changed
- Parallel mode with git worktrees (no interference between agents)
- JSON output for CI integration and tracking over time
- Works with any agent that has a CLI

The goal isn't "which model is best." It's "which agent solves my specific problem best."

## CI Integration

Use coderace in GitHub Actions to automatically race agents on PRs and post results as comments.

### Quick setup

1. Copy `examples/ci-race-on-pr.yml` into `.github/workflows/` in your repo.
2. Create a task YAML at `.github/coderace-task.yaml` (see [Task Format](#task-format)).
3. Install the agent CLIs your task requires (see comments in the workflow file).
4. Open or update a PR — results appear as a PR comment automatically.

### Workflow: Race on every PR

```yaml
name: Race Coding Agents

on:
  pull_request:
    branches: [main]

jobs:
  race:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - name: Run coderace
        uses: mikiships/coderace@v0.3
        with:
          task: .github/coderace-task.yaml
          agents: claude,aider
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Workflow: Race only when "race-agents" label is added

Cost-control pattern: only race when a maintainer deliberately triggers it.

```yaml
name: Race Coding Agents (on label)

on:
  pull_request:
    types: [labeled]

jobs:
  race:
    if: github.event.label.name == 'race-agents'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - name: Run coderace
        uses: mikiships/coderace@v0.3
        with:
          task: .github/coderace-task.yaml
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Action inputs

| Input | Description | Default |
|-------|-------------|---------|
| `task` | Path to coderace task YAML | _(required)_ |
| `agents` | Comma-separated agents to race | _(from task file)_ |
| `parallel` | Run agents in parallel (`true`/`false`) | `false` |
| `github-token` | Token for posting PR comments | `${{ github.token }}` |
| `coderace-version` | coderace version to install | `latest` |
| `python-version` | Python version | `3.11` |

### Example PR comment

The action automatically posts (and updates on re-run) a comment like:

> ✅ **coderace** — `fix-auth-bug` | **Winner: `claude`** (85.0 pts) | 3 agent(s) raced
>
> | Rank | Agent | Score | Tests | Lint | Exit | Time (s) | Lines |
> |------|-------|------:|:-----:|:----:|:----:|---------:|------:|
> | 1 | `claude` | 85.0 | ✅ | ✅ | ✅ | 10.5 | 42 |
> | 2 | `codex` | 70.0 | ✅ | ❌ | ✅ | 15.2 | 98 |
> | 3 | `aider` | 55.0 | ❌ | ✅ | ✅ | 8.1 | 31 |

The action uses a hidden HTML marker to find and update existing comments, so re-running doesn't spam the PR.

## See Also

- **[pytest-agentcontract](https://github.com/mikiships/pytest-agentcontract)** -- Deterministic CI tests for LLM agent trajectories. Record once, replay offline, assert contracts. Pairs well with coderace: race agents to find the best one, then lock down its behavior with contract tests.

## Requirements

- Python 3.10+
- Git
- At least one coding agent CLI installed

## License

MIT

## Benchmarking

The `coderace benchmark` command runs all (or selected) built-in tasks against one or more agents and produces a comprehensive comparison report.

```bash
# Race claude vs codex across ALL built-in tasks
coderace benchmark --agents claude,codex

# Select specific tasks
coderace benchmark --agents claude,codex --tasks fibonacci,json-parser

# Filter by difficulty
coderace benchmark --agents claude --difficulty easy,medium

# Dry-run: see what would run without executing
coderace benchmark --agents claude,codex --dry-run

# Statistical mode: run repeated trials per pair
coderace benchmark --agents claude,codex --tasks fibonacci,json-parser --trials 5

# Save report to file
coderace benchmark --agents claude,codex --output report.md
coderace benchmark --agents claude,codex --output report.html

# Export standardized JSON (shareable benchmark artifact)
coderace benchmark --agents claude,codex --trials 5 --export benchmark.json
```

### Example Terminal Output

```
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Task                 ┃ claude         ┃ codex          ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ fibonacci            │ 100.0 (3s)     │ 95.0 (5s)      │
│ json-parser          │ 85.0 (12s)     │ 100.0 (9s)     │
│ csv-analyzer         │ 70.0 (18s)     │ 65.0 (22s)     │
│ markdown-to-html     │ 90.0 (8s)      │ 85.0 (11s)     │
│ binary-search-tree   │ 80.0 (25s)     │ 75.0 (30s)     │
│ http-server          │ 55.0 (45s)     │ 60.0 (40s)     │
├──────────────────────┼────────────────┼────────────────┤
│ TOTAL                │ 480.0          │ 480.0          │
│ Win Rate             │ 50%            │ 50%            │
│ Avg Time             │ 18.5s          │ 19.5s          │
│ Total Cost           │ $0.12          │ $0.09          │
└──────────────────────┴────────────────┴────────────────┘
```

### Benchmark History

Results are saved to the local store automatically:

```bash
# List past benchmark runs
coderace benchmark history

# View a specific past benchmark
coderace benchmark show bench-20260227-143022
```

### Benchmark CLI Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--agents` | Comma-separated agent names (required) | — |
| `--tasks` | Comma-separated task names | all built-ins |
| `--difficulty` | Filter by difficulty: `easy`, `medium`, `hard` | all |
| `--timeout` | Per-task timeout in seconds | `300` |
| `--parallel N` | Run N agents in parallel | `1` (sequential) |
| `--trials N` | Repeat each `(task, agent)` pair N times | `1` |
| `--dry-run` | List combinations without running | `false` |
| `--format` | Output format: `terminal`, `markdown`, `html` | `terminal` |
| `--output` | Save report to file | — |
| `--export` | Write standardized benchmark JSON file | — |
| `--no-save` | Skip saving results to the store | `false` |

### Statistical Reports (`--trials > 1`)

When `--trials` is greater than 1, benchmark reports switch to statistical mode:

- Task cells show `mean score +/- stddev` (plus mean wall time)
- Report includes `CI (95%)`, `Consistency`, and `Reliability` columns
- Summary includes per-agent mean score, confidence interval, win rate, and reliability
- ELO ratings are rendered at the bottom of terminal/markdown/html reports

### ELO Ratings

Every benchmark run updates persistent ELO ratings across all benchmark history.

```bash
# Show ratings
coderace ratings

# JSON output
coderace ratings --json

# Reset all ratings to 1500
coderace ratings --reset
```

ELO rules:
- Initial rating: `1500`
- K-factor: `32`
- Each task is treated as a round-robin set of pairwise matches
- Winner per pair is based on higher mean trial score (draw when within 1 point)

### Export Format (`--export`)

`coderace benchmark --export benchmark.json` writes a standardized JSON artifact:

```json
{
  "coderace_version": "1.0.0",
  "benchmark_id": "bench-20260228-133000",
  "timestamp": "2026-02-28T13:30:00Z",
  "system": { "os": "...", "python": "...", "cpu": "..." },
  "config": { "trials": 5, "timeout": 300, "tasks": ["..."], "agents": ["..."] },
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
      "consistency_score": 0.96,
      "per_trial": []
    }
  ],
  "elo_ratings": { "claude": 1523, "codex": 1488 },
  "summary": {}
}
```

## Context Evaluation

The `coderace context-eval` command measures whether a context file (CLAUDE.md, AGENTS.md, .cursorrules, etc.) actually improves agent performance. It runs A/B trials — baseline (no context file) vs treatment (with context file) — and produces statistical comparisons.

```bash
# Evaluate whether CLAUDE.md improves claude's performance on a task
coderace context-eval --context-file CLAUDE.md --task fix-auth-bug.yaml --agents claude --trials 5

# Evaluate across all built-in benchmark tasks
coderace context-eval --context-file CLAUDE.md --benchmark --agents claude,codex

# Save results as JSON
coderace context-eval --context-file CLAUDE.md --task task.yaml --agents claude --output results.json

# Use a custom task directory
coderace context-eval --context-file CLAUDE.md --benchmark --task-dir ./my-tasks --agents claude
```

### How It Works

For each agent × task combination:
1. Run N trials **without** the context file (baseline condition)
2. Run N trials **with** the context file placed in the task directory (treatment condition)
3. Compare pass rates, mean scores, and compute statistical significance

### Output

The terminal report shows:
- **Per-agent summary**: baseline vs treatment pass rates and scores, delta with 95% CI, Cohen's d effect size
- **Per-task breakdown**: which tasks improved, which degraded
- **Verdict**: whether the context file significantly improved performance

```
┌────────┬───────────────────┬────────────────────┬────────────────┬─────────────────┬────────┬──────────────────┬─────────────┐
│ Agent  │ Baseline Pass Rate│ Treatment Pass Rate │ Baseline Score │ Treatment Score │ Delta  │ CI (95%)         │ Effect Size │
├────────┼───────────────────┼────────────────────┼────────────────┼─────────────────┼────────┼──────────────────┼─────────────┤
│ claude │              67%  │              100%  │           55.0 │            81.0 │ +26.0  │ [10.5, 41.5]     │        2.10 │
│ codex  │              33%  │               67%  │           45.0 │            70.0 │ +25.0  │ [8.0, 42.0]      │        1.80 │
└────────┴───────────────────┴────────────────────┴────────────────┴─────────────────┴────────┴──────────────────┴─────────────┘

Context file improved performance by +25.5 points (CI: [12.0, 39.0])
```

### Context-Eval CLI Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--context-file` | Path to the context file to evaluate (required) | — |
| `--task` | Path to a single task YAML | — |
| `--benchmark` | Run against built-in benchmark tasks | `false` |
| `--agents` | Comma-separated agent names (required) | — |
| `--trials` | Trials per condition (min: 2) | `3` |
| `--output` | Save JSON results to file | — |
| `--task-dir` | Custom task directory for benchmark mode | — |

### Dashboard Integration

Include context-eval results in the HTML dashboard:

```bash
# Run context-eval and save JSON
coderace context-eval --context-file CLAUDE.md --task task.yaml --agents claude --output eval.json

# Generate dashboard with A/B comparison section
coderace dashboard --context-eval eval.json
```

## Measuring Context Engineering Impact

Context engineering — crafting CLAUDE.md, AGENTS.md, .cursorrules, and similar files — is becoming a core developer skill. But until now, there was no way to empirically measure whether your context files actually help.

**The problem:** You write a CLAUDE.md with coding conventions, architectural guidelines, and project-specific instructions. But does it actually make agents produce better code? Or is it cargo-cult configuration?

**The solution:** `coderace context-eval` gives you data:

1. **Write your context file** (e.g., CLAUDE.md with project conventions)
2. **Run A/B evaluation** against real coding tasks
3. **Get statistical evidence** of improvement (or lack thereof)

```bash
# Iterate on your context file with data
coderace context-eval --context-file CLAUDE.md --benchmark --agents claude --trials 5

# Compare different context files
coderace context-eval --context-file v1-claude.md --task task.yaml --agents claude --output v1.json
coderace context-eval --context-file v2-claude.md --task task.yaml --agents claude --output v2.json
```

**Interpreting results:**
- **Effect size > 0.8**: Large improvement — your context file is helping significantly
- **Effect size 0.2–0.8**: Moderate improvement — some benefit, room to iterate
- **Effect size < 0.2**: Negligible — your context file isn't making a measurable difference
- **CI crosses zero**: Not statistically significant — need more trials or a better context file

## See Also

- **[agentmd](https://github.com/mikiships/agentmd)** — Generate and score context files (CLAUDE.md, AGENTS.md, .cursorrules) for AI coding agents. Pair with coderace: generate context with agentmd, measure agent performance with coderace, iterate with data instead of vibes.
- **[agentlint](https://github.com/mikiships/agentlint)** — Lint AI agent git diffs for risky patterns (scope drift, secret leaks, test regression). Static analysis, no LLM required.

Measure (coderace) → Optimize (agentmd) → Guard (agentlint).
