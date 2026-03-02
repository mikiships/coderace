#!/usr/bin/env bash
# Context Eval Demo: Measure whether a CLAUDE.md file improves agent performance
#
# This script demonstrates the context-eval workflow:
# 1. Create a sample context file
# 2. Run A/B evaluation against a built-in task
# 3. View results and optionally generate a dashboard
#
# Prerequisites:
#   - pip install coderace
#   - At least one agent CLI installed (claude, codex, aider, etc.)

set -euo pipefail

echo "=== coderace context-eval demo ==="
echo ""

# Step 1: Create a sample context file to evaluate
CONTEXT_FILE="demo-claude.md"
cat > "$CONTEXT_FILE" << 'CONTEXT'
# Project Conventions

## Code Style
- Use type hints for all function signatures
- Keep functions under 30 lines
- Prefer list comprehensions over manual loops
- Use descriptive variable names

## Testing
- Write tests before implementation
- Cover edge cases (empty input, None, negative numbers)
- Use pytest fixtures for shared setup

## Architecture
- Single Responsibility Principle: one function, one job
- Pure functions where possible (no side effects)
- Handle errors explicitly, don't let exceptions propagate silently
CONTEXT

echo "Created context file: $CONTEXT_FILE"
echo ""

# Step 2: Run context-eval against a built-in task
echo "Running context-eval (this will take a few minutes)..."
echo ""
coderace context-eval \
  --context-file "$CONTEXT_FILE" \
  --task "$(python3 -c 'from coderace.builtins import get_builtin_path; print(get_builtin_path("fibonacci"))')" \
  --agents claude \
  --trials 3 \
  --output demo-eval-results.json

echo ""
echo "Results saved to: demo-eval-results.json"

# Step 3: Generate dashboard with context-eval results
echo ""
echo "Generating dashboard..."
coderace dashboard --context-eval demo-eval-results.json --output demo-dashboard.html
echo "Dashboard: demo-dashboard.html"

# Cleanup
rm -f "$CONTEXT_FILE"
echo ""
echo "Done! Open demo-dashboard.html to see the A/B comparison."
