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

## Requirements

- Python 3.10+
- Git
- At least one coding agent CLI installed

## License

MIT
