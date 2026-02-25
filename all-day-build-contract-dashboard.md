# All-Day Build Contract: Web Dashboard Export

Status: In Progress
Date: 2026-02-25
Owner: Codex/Sonnet execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add a `coderace dashboard` command that generates a self-contained, single-file HTML dashboard from the SQLite results database. The dashboard shows aggregate leaderboard, race history, per-agent performance trends, and cost efficiency. The HTML file works standalone (no external dependencies) and can be published to any static host (here.now, GitHub Pages, Netlify).

This transforms coderace from a CLI-only tool into something with a shareable, visual artifact. When users run `coderace dashboard`, they get a beautiful public-facing page showing their agent benchmarks.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end.
4. New features must ship with docs and report addendum updates in the same pass.
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside the project directory.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report.
9. Do NOT refactor, restyle, or "improve" code outside the deliverables.
10. Read existing tests and docs before writing new code.

## 3. Feature Deliverables

### D1. Dashboard Generator Core (`coderace/dashboard.py`)

Build the HTML dashboard generator that reads from the SQLite store and produces a single self-contained HTML file.

The dashboard must include these sections:
- **Hero/Header:** "coderace Leaderboard" with last-updated timestamp
- **Aggregate Leaderboard Table:** Agent, Wins, Avg Score, Avg Time, Win Rate, Avg Cost, sorted by wins
- **Race History:** List of all runs with date, task, winner, agent count. Clickable to expand individual results.
- **Agent Performance Cards:** Per-agent summary with total races, wins, avg score, best score, avg cost
- **Cost Efficiency Chart:** A simple CSS-only bar chart showing cost-per-point for each agent (no JavaScript charting library needed, use CSS widths)

Technical requirements:
- Single file, self-contained HTML (all CSS inline in `<style>`, all JS inline in `<script>`)
- NO external CDN dependencies (no Tailwind CDN, no Chart.js CDN)
- Responsive design (readable on mobile)
- Dark mode default with a light/dark toggle (CSS variables + 10 lines of JS)
- Clean, modern look (think: Linear, Vercel dashboard aesthetics)

Required files:
- `coderace/dashboard.py`

- [ ] Dashboard generator function that reads from ResultStore
- [ ] Aggregate stats computation (wins, avg score, win rate, avg cost per agent)
- [ ] Race history list generation
- [ ] Agent performance card generation
- [ ] CSS-only bar charts for cost efficiency
- [ ] Responsive CSS with dark/light mode
- [ ] Tests for D1 (at least 8 tests)

### D2. CLI Command (`coderace dashboard`)

Add the `coderace dashboard` subcommand to the CLI.

Usage:
```
coderace dashboard                    # Generate dashboard.html in current dir
coderace dashboard -o report.html     # Custom output path
coderace dashboard --task fizzbuzz    # Filter to specific task
coderace dashboard --last 10          # Only last N races
coderace dashboard --title "My Team"  # Custom title
coderace dashboard --open             # Generate and open in browser
```

Required files:
- `coderace/commands/dashboard.py`
- Update `coderace/cli.py` to register the subcommand

- [ ] Subcommand with all flags above
- [ ] --open flag uses `webbrowser.open()` 
- [ ] Graceful handling when database is empty (generate a "No races yet" page with instructions)
- [ ] Tests for D2 (at least 5 tests)

### D3. Publish Integration (`coderace dashboard --publish`)

Add a `--publish` flag that uploads the generated HTML to here.now (or any similar service).

Usage:
```
coderace dashboard --publish                      # Publish, print URL
coderace dashboard --publish --here-now-key KEY   # With API key for persistent URL
```

Implementation:
- POST to here.now API (3-step: create upload URLs, PUT file, finalize)
- Print the published URL to stdout
- If no API key, anonymous publish (24h expiry)
- If API key provided (via flag or HERENOW_API_KEY env var), persistent publish

Required files:
- `coderace/publish.py` (here.now API client, keep it simple)
- Update `coderace/commands/dashboard.py` for --publish flag

- [ ] here.now API integration (publish flow)
- [ ] Anonymous publish (no key)
- [ ] Authenticated publish (with key)
- [ ] URL printed to stdout on success
- [ ] Tests for D3 (at least 4 tests, mock the HTTP calls)

### D4. Documentation + CHANGELOG

- [ ] README section: "Dashboard & Publishing" with usage examples and a screenshot description
- [ ] CHANGELOG entry for v0.6.0
- [ ] `coderace dashboard --help` shows clear usage

## 4. Test Requirements

- [ ] Unit tests for dashboard HTML generation (structure, sections present, data accuracy)
- [ ] Unit tests for CLI flags (output path, filters, title)
- [ ] Unit tests for publish module (mocked HTTP)
- [ ] Integration test: generate dashboard from a test database with known data, verify HTML contents
- [ ] Edge case: empty database produces valid HTML with "No races yet" message
- [ ] Edge case: single race with single agent produces valid dashboard
- [ ] All existing tests must still pass
- [ ] Target: 20+ new tests (274+ total)

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
