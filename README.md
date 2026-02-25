# coderace

Stop reading blog comparisons. Race coding agents against each other on real tasks in *your* repo with *your* code.

Every week there's a new "Claude Code vs Codex vs Cursor" post. They test on toy problems with cherry-picked examples. coderace gives you automated, reproducible, scored comparisons on the tasks you actually care about.

Define a task. Run it against Claude Code, Codex, Aider, Gemini CLI, and OpenCode. Get a scored comparison table.

## Install

```bash
pip install coderace
```

## Quick Start

```bash
# Create a task template
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

## Task Format

```yaml
name: fix-auth-bug
description: |
  The login endpoint returns 500 when email contains a plus sign.
  Fix the email validation in auth/validators.py.
repo: .
test_command: pytest tests/test_auth.py -x
lint_command: ruff check .
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
