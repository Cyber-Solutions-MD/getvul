# Phase 34 — Deferred Items

## Pre-existing test-isolation hazard: `test_risk_exposure_service.py` + `test_scheduler_enrichment_refresh.py` hang when run in the SAME pytest session

**Found during:** 34-01 Task 3, while running the plan's regression gate
(`pytest tests/test_risk_exposure_service.py tests/test_scheduler_ai_batch.py
tests/test_scheduler_enrichment_refresh.py`).

**Confirmed pre-existing, NOT caused by Phase 34 Plan 01's changes:**
reproduced the hang by temporarily reverting `app/connectors/scheduler.py`
to its pre-Plan-01 committed state (`git show HEAD:...`) and re-running the
exact same 2-file combination — the hang reproduced identically with zero
Phase 34 code present. Root cause: `test_risk_exposure_service.py::
test_get_vulnerability_returns_risk_fields` is the only test in that file
using the `client` fixture, which (via `asgi_lifespan.LifespanManager`)
runs the FastAPI app's real `lifespan()` — which calls
`app.connectors.scheduler.start_scheduler()` for real. Because
`asyncio_default_test_loop_scope=session` (pyproject.toml), the resulting
`_scheduler_loop()` background task and its module-level globals
(`_last_enrichment_refresh`, `_enrichment_refresh_lock`) persist for the
REST of the pytest session — polluting `test_scheduler_enrichment_refresh.py`'s
own gate-state assumptions when run afterward in the same process. Symptom:
two `..._24h_gated`-style tests fail (`assert 0 == 1`, the fake never gets
called because the REAL background task already holds
`_enrichment_refresh_lock` or has already advanced the gate), and
`test_dispatch_enrichment_refresh_concurrent_calls_do_not_race` hangs
indefinitely (plausibly waiting on that same lock while the real
`_dispatch_enrichment_refresh()` is stuck in an actual outbound HTTP call
inside `refresh_enrichment_reference_data`, which this sandboxed
environment cannot complete).

**Verified NOT a Phase 34 regression:** every one of the 3 files in the
plan's regression gate passes cleanly in ISOLATION with Plan 01's changes
present:
- `pytest tests/test_risk_exposure_service.py` — 12 passed
- `pytest tests/test_scheduler_ai_batch.py` — 7 passed
- `pytest tests/test_scheduler_enrichment_refresh.py` — 8 passed

The 2-file combination `test_risk_exposure_service.py` +
`test_scheduler_ai_batch.py` also passes together (19 passed) — the hang
is specific to `test_scheduler_enrichment_refresh.py` being in the same
session as any test that exercises the real app lifespan/scheduler.

**Scope boundary:** out of scope for Plan 01 (Rule 1/3 do not apply — this
bug lives entirely in pre-existing fixture/scheduler-state test isolation,
untouched by this plan's files). Logged here per the executor's
scope-boundary protocol rather than fixed inline.

**Suggested future fix (not actioned this plan):** either (a) have the
`client`/`app_factory`/`single_app`/`two_apps` fixtures call
`stop_scheduler()` at teardown and reset the scheduler module's
`_last_*`/lock globals, or (b) have `test_scheduler_enrichment_refresh.py`'s
tests defensively reset `scheduler_module._enrichment_refresh_lock =
asyncio.Lock()` at the start of each test (in addition to the existing
`_last_enrichment_refresh` monkeypatch) so a leaked real lock from another
file's real scheduler never poisons this file's own gate tests.
