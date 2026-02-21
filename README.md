# coderace

Race coding agents against each other on real tasks in your repo.

Define a task. Run it against Claude Code, Codex, and Aider. Get a scored comparison table.

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

Results also saved as JSON in `.coderace/<task>-results.json`.

## Supported Agents

| Agent | CLI | Command |
|-------|-----|---------|
| Claude Code | `claude` | `claude --print --output-format json -p "<task>"` |
| Codex | `codex` | `codex --quiet --full-auto -p "<task>"` |
| Aider | `aider` | `aider --message "<task>" --yes --no-auto-commits` |
| Gemini CLI | `gemini` | `gemini --non-interactive -p "<task>"` |

Each agent must be installed and authenticated separately.

## Parallel Mode

Use `--parallel` (or `-p`) to run all agents simultaneously using git worktrees. Each agent gets its own isolated working directory, so they don't interfere with each other.

```bash
coderace run task.yaml --parallel
```

Sequential mode (default) runs agents one at a time on the same repo.

## Requirements

- Python 3.10+
- Git
- At least one coding agent CLI installed

## License

MIT
