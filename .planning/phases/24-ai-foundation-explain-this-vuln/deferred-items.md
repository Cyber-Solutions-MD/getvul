# Phase 24 — Deferred Items (out-of-scope discoveries, not fixed)

Items discovered during plan execution that are DIRECTLY caused by neither
the current plan's changes nor any prior Phase 24 plan's changes — logged
per the executor's scope-boundary rule, not fixed.

---

## 24-04: Full-suite-only flake in `test_connector_health.py` (pre-existing, unrelated)

**Found during:** Plan 24-04, post-Task-2 full-suite regression sweep
(`pytest tests/ -q`, 427 tests collected).

**Symptom:** `tests/test_connector_health.py::test_scheduler_path_error_message_and_log_are_sanitized`
fails only when the FULL `tests/` directory is collected together
(`1 failed, 426 passed`) — asserting `len(complete_events) == 1` where
`complete_events` is empty (`0 == 1`). The test asserts on a captured
structlog event list (`background_sync_complete`) that appears to get
lost/reordered under full-suite log-capture contention.

**Confirmed unrelated to Plan 24-04:** running the file in isolation
(`pytest tests/test_connector_health.py -q`) passes cleanly, 9/9. Plan
24-04 never touches `app/connectors/scheduler.py`, `app/connectors/health.py`,
or any sync-logging code path — the file/behavior under test is completely
outside this plan's `files_modified` list.

**Likely root cause (not investigated further — out of scope):** this
project's `pytest.ini_options` shares ONE session-scoped asyncio event loop
across the whole test session (`asyncio_default_fixture_loop_scope =
"session"`, documented in `pyproject.toml` as a workaround for a different
pre-existing pool-disposal issue, WR-14). A shared event loop across ~427
tests is a plausible vector for structlog capture-fixture cross-test
interference — the same general CLASS of "full-suite-only flake" already
documented in project memory for the frontend Playwright suite
(`getvul-e2e-fullsuite-flake-classes`), just on the backend pytest side.

**Action:** Not fixed (out of scope per SCOPE BOUNDARY — pre-existing,
unrelated file). Flag for a future backend test-harness hardening pass if
this resurfaces; matches the already-tracked `getvul-backend-test-harness-rot`
class of issue.
