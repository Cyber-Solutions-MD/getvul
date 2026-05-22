# Deferred Items — Phase 11

Items discovered during execution but outside the scope of the current plan's
changes. To be addressed by a future phase or bug-fix plan.

## Pre-existing test-infra: rate-limiter Redis unreachable from inside `getvul-backend-1` container

**Discovered during:** Plan 11-01, Task 11-01-01 (running `pytest
tests/test_vuln_sort.py`).

**Symptom:** When multiple tests that use `client` or `client_factory` run in
the same pytest session, the second test onward fails at setup with
`asyncpg.connection.Connection._cancel` "Event loop is closed" and the
underlying app-startup log emits:

```
redis_unavailable error="...Connect call failed ('127.0.0.1', 6379)..." subsystem=rate_limiter
```

**Root cause:** `tests/conftest.py` hard-codes `REDIS_TEST_URL =
"redis://localhost:6379/1"`. Inside the backend container Redis is reachable
only at `redis:6379` (compose service hostname). The rate-limiter middleware
running in the app instance tries to connect to localhost and fails, which
in turn leaks a coroutine that pollutes the next test's connection pool.

**Pre-existing evidence:** `tests/test_triage_sort.py::test_triage_sort_rejects_invalid_value`
also FAILs/ERRORs in the same way on Phase 10 commit history (verified by
running it standalone before any Phase 11 file existed).

**Workaround used in this plan:** Tests verified individually (`pytest
path/to/test.py::test_name`) where each test passes. Per-file pytest runs
exit non-zero (correctly RED for facets / group_host; incorrectly ERROR on
tickets_create rows 4-5 due to pollution only).

**Fix recommendation:** Update `tests/conftest.py:36` to compute the Redis
URL from an env var with a sensible localhost default for host-run tests, or
configure the test runner to route through the container's `redis:` hostname
when running `docker exec`. Suggested:

```python
REDIS_TEST_URL = os.environ.get("REDIS_TEST_URL", "redis://localhost:6379/1")
```

Tracked as a Phase-11 deferred item — not blocking Wave 0 RED tests because
the per-test pass status confirms the assertions themselves are correct.
