# coderace v1.8.0 — Build Report
Date: 2026-03-12
Version: 1.8.0
PyPI: https://pypi.org/project/coderace/1.8.0/

## Deliverables
- [x] D1: Maintainer rubric evaluator (`coderace/maintainer_rubric.py`) — 5 dimension scorers + `MaintainerRubric` dataclass + `score_rubric()` composite. Pure static analysis, no LLM.
- [x] D2: CLI integration — `coderace review --maintainer-mode` and `coderace benchmark --maintainer-mode` flags added
- [x] D3: Rich display (`coderace/display.py` — `MaintainerRubricDisplay`) + markdown/JSON report helpers in `review_report.py`
- [x] D4: 31 new tests in `tests/test_maintainer_rubric.py` (5 scorers × 3 cases + composite + display + CLI + JSON)
- [x] D5: README "Maintainer Rubric" section, CHANGELOG v1.8.0 entry, pyproject.toml bumped to 1.8.0, PyPI published, GitHub tagged v1.8.0

## Tests
700 passed (669 baseline + 31 new)

## Notes
- All 5 dimension scorers are pure static analysis working on unified diff text
- `score_rubric()` accepts optional `allowed_paths` (for scope_discipline) and custom `weights`
- `MaintainerRubricDisplay` uses Rich table with Green/Yellow/Red coloring (≥80/50-79/<50)
- JSON output: `render_review_json_with_rubric()` adds `maintainer_rubric` key to existing JSON shape
- `coderace benchmark --maintainer-mode` renders an infrastructure table; full diff-based scoring for benchmark tasks requires per-task diff exposure (not yet in benchmark engine)
- PyPI publish used `UV_PUBLISH_TOKEN` env var with token from `~/.pypirc`
