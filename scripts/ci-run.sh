#!/usr/bin/env bash
# ci-run.sh — Run coderace in CI and emit results path as a GitHub Actions output.
#
# Environment variables (set by action.yml):
#   CODERACE_TASK      Path to the task YAML file (required)
#   CODERACE_AGENTS    Comma-separated agents, e.g. "claude,codex" (optional)
#   CODERACE_PARALLEL  "true" to run agents in parallel (optional)
#
# GitHub Actions output:
#   results-json       Path to the JSON results file (may be empty on failure)

set -euo pipefail

echo "::group::coderace run"

if [ -z "${CODERACE_TASK:-}" ]; then
  echo "::error::CODERACE_TASK is required"
  exit 1
fi

if [ ! -f "${CODERACE_TASK}" ]; then
  echo "::error::Task file not found: ${CODERACE_TASK}"
  exit 1
fi

# Build the coderace run command
CMD=(coderace run "${CODERACE_TASK}")

if [ -n "${CODERACE_AGENTS:-}" ]; then
  IFS=',' read -ra AGENT_LIST <<< "${CODERACE_AGENTS}"
  for agent in "${AGENT_LIST[@]}"; do
    agent="$(echo "${agent}" | tr -d '[:space:]')"
    CMD+=(--agent "${agent}")
  done
fi

if [ "${CODERACE_PARALLEL:-false}" = "true" ]; then
  CMD+=(--parallel)
fi

echo "Running: ${CMD[*]}"
EXIT_CODE=0
"${CMD[@]}" || EXIT_CODE=$?

echo "::endgroup::"

# Derive the expected JSON results path.
# Convention: .coderace/<task-name>-results.json next to the task file.
TASK_DIR="$(dirname "${CODERACE_TASK}")"
TASK_NAME="$(basename "${CODERACE_TASK}" .yaml)"
RESULTS_JSON="${TASK_DIR}/.coderace/${TASK_NAME}-results.json"

if [ -f "${RESULTS_JSON}" ]; then
  echo "results-json=${RESULTS_JSON}" >> "${GITHUB_OUTPUT:-/dev/null}"
  echo "::notice::Results saved to ${RESULTS_JSON}"
else
  echo "results-json=" >> "${GITHUB_OUTPUT:-/dev/null}"
  echo "::warning::No results file found at ${RESULTS_JSON}"
fi

exit "${EXIT_CODE}"
