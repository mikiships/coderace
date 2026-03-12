#!/usr/bin/env bash
# ci-gate.sh — Run coderace gate in CI for the maintainer quality gate.
#
# Environment variables (set by action.yml):
#   CODERACE_DIFF_SOURCE    Diff source: "pr", "commit:<sha>", "branch:<base>...<head>", "file:<path>"
#   CODERACE_MIN_SCORE      Minimum composite rubric score (0-100)
#   GITHUB_BASE_REF         Set by GitHub Actions for PR context (used for "pr" diff source)
#
# Output file:
#   /tmp/coderace-gate-result.json   JSON gate result (score, pass/fail, dimensions)

set -euo pipefail

echo "::group::coderace maintainer quality gate"

# ---- Defaults ---------------------------------------------------------------
DIFF_SOURCE="${CODERACE_DIFF_SOURCE:-pr}"
MIN_SCORE="${CODERACE_MIN_SCORE:-80}"
GATE_JSON="/tmp/coderace-gate-result.json"

# ---- Resolve diff -----------------------------------------------------------
DIFF_FILE=""

case "${DIFF_SOURCE}" in
  pr)
    BASE_REF="${GITHUB_BASE_REF:-main}"
    echo "::notice::Using PR diff: git diff origin/${BASE_REF}...HEAD"
    DIFF_TMPFILE="$(mktemp /tmp/coderace-gate-diff.XXXXXX)"
    if ! git diff "origin/${BASE_REF}...HEAD" > "${DIFF_TMPFILE}" 2>&1; then
      echo "::error::git diff failed. Make sure checkout uses fetch-depth: 0"
      cat "${DIFF_TMPFILE}" >&2
      exit 1
    fi
    if [ ! -s "${DIFF_TMPFILE}" ]; then
      echo "::notice::PR diff is empty — gate automatically passes."
      echo '{"gate":"PASS","score":100,"min_score":'"${MIN_SCORE}"',"passed":true,"dimensions":{}}' > "${GATE_JSON}"
      echo "::endgroup::"
      exit 0
    fi
    DIFF_FILE="${DIFF_TMPFILE}"
    ;;

  commit:*)
    SHA="${DIFF_SOURCE#commit:}"
    DIFF_TMPFILE="$(mktemp /tmp/coderace-gate-diff.XXXXXX)"
    git diff "${SHA}~1" "${SHA}" > "${DIFF_TMPFILE}"
    DIFF_FILE="${DIFF_TMPFILE}"
    ;;

  branch:*)
    RANGE="${DIFF_SOURCE#branch:}"
    DIFF_TMPFILE="$(mktemp /tmp/coderace-gate-diff.XXXXXX)"
    git diff "${RANGE}" > "${DIFF_TMPFILE}"
    DIFF_FILE="${DIFF_TMPFILE}"
    ;;

  file:*)
    DIFF_FILE="${DIFF_SOURCE#file:}"
    if [ ! -f "${DIFF_FILE}" ]; then
      echo "::error::Diff file not found: ${DIFF_FILE}"
      exit 1
    fi
    ;;

  *)
    echo "::error::Unknown diff source: ${DIFF_SOURCE}"
    exit 1
    ;;
esac

# ---- Run gate ---------------------------------------------------------------
echo "Running: coderace gate --diff ${DIFF_FILE} --min-score ${MIN_SCORE} --json"

EXIT_CODE=0
coderace gate --diff "${DIFF_FILE}" --min-score "${MIN_SCORE}" --json > "${GATE_JSON}" || EXIT_CODE=$?

echo "::endgroup::"

# Print human-readable result to CI log
cat "${GATE_JSON}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
icon = '✅' if d['passed'] else '❌'
print(f\"{icon} Maintainer score {d['score']} — gate: {d['gate']}\")
"

if [ "${EXIT_CODE}" -eq 1 ]; then
  echo "::error::Maintainer quality gate FAILED. Score below ${MIN_SCORE}."
  exit 1
fi

exit 0
