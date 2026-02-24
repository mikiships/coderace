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
