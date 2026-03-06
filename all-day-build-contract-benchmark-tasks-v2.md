# All-Day Build Contract: New Benchmark Tasks (Batch 2)

Status: In Progress
Date: 2026-03-05
Owner: Claude Code execution pass
Scope type: Deliverable-gated (no hour promises)

## 1. Objective

Add 4 new built-in benchmark tasks to coderace that test **real-world coding skills** beyond "build from scratch." Current 16 tasks all ask agents to implement something new. These 4 test debugging, refactoring, concurrency, and API design — skills that matter in production but aren't benchmarked.

This contract is considered complete only when every deliverable and validation gate below is satisfied.

## 2. Non-Negotiable Build Rules

1. No time-based completion claims.
2. Completion is allowed only when all checklist items are checked.
3. Full test suite must pass at the end (`pytest tests/ -x`).
4. New tasks must follow the exact same format as existing built-in tasks (see `src/coderace/tasks/` for examples).
5. CLI outputs must be deterministic and schema-backed where specified.
6. Never modify files outside the project directory.
7. Commit after each completed deliverable (not at the end).
8. If stuck on same issue for 3 attempts, stop and write a blocker report.
9. Do NOT refactor, restyle, or "improve" existing code or tasks.
10. Read existing tasks in `src/coderace/tasks/` before writing new ones. Match the exact YAML format, naming conventions, and verification test style.

## 3. Feature Deliverables

### D1. Task: `bug-hunt` (debugging — fix planted bugs in existing code)

**Concept:** Provide a working-looking module (`buggy_calculator.py`) with 5 planted bugs. The agent must find and fix them without being told exactly what's wrong.

The task description gives the agent:
- A pre-written `buggy_calculator.py` with an advanced calculator (expressions, variables, functions like `sqrt`, `abs`, `min`, `max`)
- A failing test file that demonstrates the bugs exist
- Instructions: "Fix ALL bugs. Do not rewrite from scratch."

Planted bugs (specific, not vague):
1. Division rounds to int instead of float (`//` instead of `/`)
2. Negative number parsing fails (misses unary minus in expressions)
3. Variable assignment overwrites built-in functions
4. `min(a, b)` returns max (arguments reversed)
5. Parenthesized expressions off-by-one in closing paren detection

Hidden verification tests:
- All 5 bugs must be fixed
- Original working functionality must still work
- Code must not be a complete rewrite (verify specific function signatures still exist)
- Edge cases: nested expressions with negatives, chained function calls

Required files:
- `src/coderace/tasks/bug-hunt.yaml`
- The YAML must include `setup_files:` with the buggy source and failing tests

- [ ] Write buggy_calculator.py with exactly 5 planted bugs
- [ ] Write test_buggy_calculator.py that exposes the bugs
- [ ] Write verify_bug_hunt.py with hidden tests for all 5 fixes + non-rewrite check
- [ ] Write bug-hunt.yaml task definition
- [ ] Tests for D1 (task loads, runs dry-run, YAML validates)

### D2. Task: `refactor` (improve existing messy code while keeping tests passing)

**Concept:** Provide a working but messy module (`data_store.py`) — a key-value store with bad naming, duplicated logic, no type hints, mixed concerns, and poor error handling. The agent must refactor it while keeping the existing test suite passing.

The task description gives the agent:
- `data_store.py` — a working but ugly key-value store (~150 lines, deliberately messy)
- `test_data_store.py` — passing tests (these must STILL pass after refactoring)
- Instructions: "Refactor for readability, maintainability, and best practices. All existing tests must pass. Do not change test file."

Quality dimensions to verify:
1. Type hints added (verify with mypy or ast inspection)
2. Functions under 25 lines each
3. No duplicated logic (measure before/after)
4. Consistent naming convention
5. Proper error handling (specific exceptions, not bare except)

Hidden verification tests:
- All original test_data_store.py tests still pass
- AST analysis: type hints present on all public functions
- AST analysis: no function exceeds 25 lines
- New edge cases that the refactored code should handle more gracefully
- Import check: the module still exports the same public API

Required files:
- `src/coderace/tasks/refactor.yaml`

- [ ] Write messy data_store.py (~150 lines, working but ugly)
- [ ] Write test_data_store.py with comprehensive passing tests
- [ ] Write verify_refactor.py with hidden quality checks (AST-based + functional)
- [ ] Write refactor.yaml task definition
- [ ] Tests for D2

### D3. Task: `concurrent-queue` (thread-safe producer/consumer with priority)

**Concept:** Build a thread-safe priority queue with producer/consumer pattern. Tests concurrency understanding — a known weak spot for LLMs.

The task description tells the agent to create `concurrent_queue.py` with:
- `PriorityTaskQueue` class
- `submit(task, priority)` — thread-safe task submission
- `worker(callback)` — starts a worker thread that processes tasks by priority
- `shutdown(wait=True)` — graceful shutdown
- Support for: task cancellation, timeout on get, max queue size with backpressure
- Thread-safe stats: tasks_submitted, tasks_completed, tasks_failed

And `test_concurrent_queue.py` with tests for:
- Basic submit and process
- Priority ordering (higher priority processed first)
- Multiple workers
- Graceful shutdown (pending tasks complete)
- Task cancellation
- Backpressure when queue is full
- Thread safety under concurrent access

Hidden verification tests:
- Stress test: 1000 tasks, 10 workers, verify all complete
- Priority ordering under load (submit mixed priorities, verify processing order)
- Shutdown with pending tasks (verify all complete before shutdown returns)
- Cancellation of in-flight vs queued tasks
- Deadlock detection (timeout-based, the test itself must complete in <10s)

Required files:
- `src/coderace/tasks/concurrent-queue.yaml`

- [ ] Write concurrent-queue.yaml with full spec
- [ ] Write verify_concurrent_queue.py with stress tests and deadlock detection
- [ ] Tests for D3

### D4. Task: `api-client` (HTTP client with retry, rate limiting, circuit breaker)

**Concept:** Build a production-grade HTTP API client with resilience patterns. Tests real-world engineering patterns.

The task description tells the agent to create `api_client.py` with:
- `APIClient(base_url, max_retries=3, rate_limit_per_sec=10)`
- Methods: `get`, `post`, `put`, `delete` — all async-compatible but sync by default
- Retry with exponential backoff (jitter) on 429 and 5xx
- Rate limiting (token bucket)
- Circuit breaker (open after N consecutive failures, half-open after timeout)
- Request/response logging
- Configurable timeout per request

And `test_api_client.py` with tests using unittest.mock to simulate server responses.

Hidden verification tests:
- Retry behavior: mock server returns 503 twice then 200, verify 3 attempts made
- Rate limiting: fire 20 requests, verify spacing respects rate limit
- Circuit breaker: force 5 failures, verify circuit opens, then half-opens after cooldown
- Backoff jitter: verify retry delays aren't deterministic (statistical test)
- Timeout handling: mock slow server, verify timeout raised

Required files:
- `src/coderace/tasks/api-client.yaml`

- [ ] Write api-client.yaml with full spec
- [ ] Write verify_api_client.py with resilience pattern tests
- [ ] Tests for D4

### D5. Integration + Documentation

- [ ] All 4 new tasks appear in `coderace tasks list` output
- [ ] `coderace benchmark --dry-run --tasks bug-hunt,refactor,concurrent-queue,api-client` works
- [ ] Update CHANGELOG.md with new tasks
- [ ] Version bump to 1.4.0 in pyproject.toml
- [ ] README: add "20 built-in tasks" (update from 16) and mention the new task categories
- [ ] All existing tests still pass (`pytest tests/ -x`)

## 4. Test Requirements

- [ ] Unit tests for each new task (YAML loads, validates, dry-run works)
- [ ] Integration test: `coderace benchmark --dry-run --tasks bug-hunt,refactor,concurrent-queue,api-client` completes
- [ ] All existing 574 tests must still pass
- [ ] New tests bring total to 590+

## 5. Reports

- Write progress to `progress-log.md` after each deliverable
- Include: what was built, what tests pass, what's next, any blockers
- Final summary when all deliverables done or stopped

## 6. Stop Conditions

- All deliverables checked and all tests passing -> DONE
- 3 consecutive failed attempts on same issue -> STOP, write blocker report
- Scope creep detected (new requirements discovered) -> STOP, report what's new
- All tests passing but deliverables remain -> continue to next deliverable
