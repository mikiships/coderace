#!/usr/bin/env bash
# ci-review.sh — Run coderace review in CI and emit outputs to GITHUB_OUTPUT.
#
# Environment variables (set by action.yml):
#   CODERACE_DIFF_SOURCE    Diff source: "pr", "commit:<sha>", "branch:<base>...<head>", "file:<path>"
#   CODERACE_AGENTS         Comma-separated agents (optional, uses coderace defaults)
#   CODERACE_LANES          Comma-separated lane names (optional)
#   CODERACE_CROSS_REVIEWERS  Number of cross-review agents (optional, default 2)
#   CODERACE_JSON_OUT       Path for JSON output (optional, defaults to /tmp/coderace-review.json)
#   CODERACE_MD_OUT         Path for markdown output (optional)
#   GITHUB_BASE_REF         Set by GitHub Actions for PR context (used for "pr" diff source)
#
# GitHub Actions outputs:
#   review-json             Path to the JSON review file
#   review-md               Path to the markdown review file (if generated)

set -euo pipefail

echo "::group::coderace review"

# ---- Defaults ---------------------------------------------------------------
DIFF_SOURCE="${CODERACE_DIFF_SOURCE:-pr}"
JSON_OUT="${CODERACE_JSON_OUT:-/tmp/coderace-review.json}"
MD_OUT="${CODERACE_MD_OUT:-}"
CROSS_REVIEWERS="${CODERACE_CROSS_REVIEWERS:-2}"

# ---- Resolve diff -----------------------------------------------------------
DIFF_FILE=""
DIFF_FLAGS=()

case "${DIFF_SOURCE}" in
  pr)
    # Auto-extract from PR context using git diff against base branch.
    # Requires: actions/checkout with fetch-depth: 0
    BASE_REF="${GITHUB_BASE_REF:-main}"
    echo "::notice::Using PR diff: git diff origin/${BASE_REF}...HEAD"
    DIFF_TMPFILE="$(mktemp /tmp/coderace-pr-diff.XXXXXX)"
    if ! git diff "origin/${BASE_REF}...HEAD" > "${DIFF_TMPFILE}" 2>&1; then
      echo "::error::git diff failed. Make sure checkout uses fetch-depth: 0"
      cat "${DIFF_TMPFILE}" >&2
      exit 1
    fi
    if [ ! -s "${DIFF_TMPFILE}" ]; then
      echo "::notice::PR diff is empty — no files changed against ${BASE_REF}."
      echo "review-json=" >> "${GITHUB_OUTPUT:-/dev/null}"
      echo "review-md=" >> "${GITHUB_OUTPUT:-/dev/null}"
      echo "::endgroup::"
      exit 0
    fi
    DIFF_FILE="${DIFF_TMPFILE}"
    DIFF_FLAGS+=(--diff "${DIFF_FILE}")
    ;;

  commit:*)
    SHA="${DIFF_SOURCE#commit:}"
    if [ -z "${SHA}" ]; then
      echo "::error::commit diff source requires a SHA: commit:<sha>"
      exit 1
    fi
    echo "::notice::Using commit diff: ${SHA}"
    DIFF_FLAGS+=(--commit "${SHA}")
    ;;

  branch:*)
    RANGE="${DIFF_SOURCE#branch:}"
    if [ -z "${RANGE}" ] || [[ "${RANGE}" != *"..."* ]]; then
      echo "::error::branch diff source requires <base>...<head> syntax: branch:<base>...<head>"
      exit 1
    fi
    echo "::notice::Using branch diff: ${RANGE}"
    DIFF_FLAGS+=(--branch "${RANGE}")
    ;;

  file:*)
    FILE_PATH="${DIFF_SOURCE#file:}"
    if [ -z "${FILE_PATH}" ]; then
      echo "::error::file diff source requires a path: file:<path>"
      exit 1
    fi
    if [ ! -f "${FILE_PATH}" ]; then
      echo "::error::Diff file not found: ${FILE_PATH}"
      exit 1
    fi
    echo "::notice::Using diff from file: ${FILE_PATH}"
    DIFF_FLAGS+=(--diff "${FILE_PATH}")
    ;;

  *)
    echo "::error::Unknown diff source: ${DIFF_SOURCE}. Valid: pr | commit:<sha> | branch:<base>...<head> | file:<path>"
    exit 1
    ;;
esac

# ---- Build coderace review command ------------------------------------------
CMD=(coderace review)
CMD+=("${DIFF_FLAGS[@]}")

if [ -n "${CODERACE_AGENTS:-}" ]; then
  CMD+=(--agents "${CODERACE_AGENTS}")
fi

if [ -n "${CODERACE_LANES:-}" ]; then
  CMD+=(--lanes "${CODERACE_LANES}")
fi

# Cross-review: pass --cross-review flag if cross-reviewers > 0
if [ "${CROSS_REVIEWERS}" -gt 0 ] 2>/dev/null; then
  CMD+=(--cross-review)
fi

# Always capture JSON output
CMD+=(--format json --output "${JSON_OUT}")

echo "Running: ${CMD[*]}"
EXIT_CODE=0
"${CMD[@]}" || EXIT_CODE=$?

echo "::endgroup::"

if [ "${EXIT_CODE}" -ne 0 ]; then
  echo "::error::coderace review exited with code ${EXIT_CODE}"
  exit "${EXIT_CODE}"
fi

# ---- Emit outputs -----------------------------------------------------------
if [ -f "${JSON_OUT}" ]; then
  echo "review-json=${JSON_OUT}" >> "${GITHUB_OUTPUT:-/dev/null}"
  echo "::notice::Review JSON saved to ${JSON_OUT}"
else
  echo "review-json=" >> "${GITHUB_OUTPUT:-/dev/null}"
  echo "::warning::No review JSON found at ${JSON_OUT}"
fi

# Optional: also generate markdown output
if [ -n "${MD_OUT}" ]; then
  MD_CMD=(coderace review)
  MD_CMD+=("${DIFF_FLAGS[@]}")
  if [ -n "${CODERACE_AGENTS:-}" ]; then
    MD_CMD+=(--agents "${CODERACE_AGENTS}")
  fi
  if [ -n "${CODERACE_LANES:-}" ]; then
    MD_CMD+=(--lanes "${CODERACE_LANES}")
  fi
  if [ "${CROSS_REVIEWERS}" -gt 0 ] 2>/dev/null; then
    MD_CMD+=(--cross-review)
  fi
  MD_CMD+=(--format markdown --output "${MD_OUT}")
  "${MD_CMD[@]}" || true
  if [ -f "${MD_OUT}" ]; then
    echo "review-md=${MD_OUT}" >> "${GITHUB_OUTPUT:-/dev/null}"
  fi
else
  echo "review-md=" >> "${GITHUB_OUTPUT:-/dev/null}"
fi

exit 0
