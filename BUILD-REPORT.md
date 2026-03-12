# coderace v1.9.0 Build Report

**Built:** 2026-03-12  
**Version:** 1.9.0  
**Commit:** 19d65382e908d292b0e42003f98cdf7832fea49a  
**Tests:** 729 passing (700 baseline + 29 new)  
**PyPI:** https://pypi.org/project/coderace/1.9.0/

---

## What was built

**CI Quality Gate** — makes the maintainer rubric enforceable in CI.

METR published research (Mar 2026) showing ~50% of SWE-bench-passing PRs would be rejected by real maintainers. coderace v1.8.0 shipped the rubric as a diagnostic. v1.9.0 makes it a gate.

### D1: `--min-score` on `coderace review --maintainer-mode`
- New `--min-score N` flag (0-100 int)
- Exits 1 when composite rubric score < N
- Prints `✅ Maintainer score 87 ≥ 80 (gate: PASS)` or `❌ Maintainer score 54 < 80 (gate: FAIL)`
- Without `--min-score`: existing behavior unchanged

### D2: `coderace gate` standalone command
- `coderace gate --diff <file|-> --min-score 80`
- Accepts diff via file path or stdin (`--diff -`)
- Exits 0 (pass) or 1 (fail)
- `--json` flag for CI log parsing (score, gate, dimensions)
- Pure static analysis — no LLM, no API keys required

### D3: GitHub Action update
- New `action.yml` input: `maintainer-min-score` (default: empty = no gate, backward compatible)
- New `scripts/ci-gate.sh` CI script handling all diff sources
- Example workflow: `.github/workflows/examples/coderace-quality-gate.yml`

### D4: Tests (29 new)
- `tests/test_ci_gate.py` — 29 tests covering gate pass/fail, threshold edge cases, empty diff, JSON output, error handling, --min-score on review, action.yml structure

### D5: Docs
- README: "CI Quality Gate" section with one-liner examples and GitHub Action snippet
- CHANGELOG: v1.9.0 entry
- Version bumped: 1.8.0 → 1.9.0
