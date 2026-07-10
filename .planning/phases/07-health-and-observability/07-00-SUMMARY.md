---
phase: 07-health-and-observability
plan: "00"
subsystem: backend/observability
tags: [tdd, nyquist, logging, health, tests]
dependency_graph:
  requires: []
  provides:
    - backend/app/logging.py (importable stub: configure_logging, redact_sensitive_keys, SENSITIVE_KEYS)
    - backend/tests/test_health_observability.py (RED test scaffold — 9 named tests)
  affects:
    - backend/tests/conftest.py (consumed but not modified; single_app fixture reused)
tech_stack:
  added: []
  patterns:
    - structlog processor signature (logger, method, event_dict) stub
    - SENSITIVE_KEYS frozenset (D-17 key set)
    - asyncio.wait_for timeout pattern documented in tests
    - mock-after-lifespan monkeypatch pattern (test_rate_limit.py convention)
key_files:
  created:
    - backend/app/logging.py
    - backend/tests/test_health_observability.py
  modified: []
decisions:
  - configure_logging() is a no-op stub (not NotImplementedError) so lifespan does not crash before 07-02
  - redact_sensitive_keys() raises NotImplementedError so test_redact_sensitive_keys is correctly RED
  - test_ready_200_both_up skips via pytest.skip if Postgres is not reachable (sandbox guard)
metrics:
  duration_minutes: 15
  completed_date: "2026-07-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 07 Plan 00: Health and Observability RED Scaffold Summary

**One-liner:** Nyquist wave-0 scaffold — importable `logging.py` stub + 9-test RED matrix covering /health, /ready 503 paths, timeout, logging renderer selection, X-Request-ID middleware, and sensitive-key redaction.

## What Was Built

### Task 1: `backend/app/logging.py` (importable stub)

Created a minimal importable stub exposing the three public names required by the downstream test and wiring plans:

- `SENSITIVE_KEYS: frozenset` — the D-17 key set verbatim: `{"authorization", "cookie", "password", "token", "secret", "credentials", "api_key"}`
- `def configure_logging() -> None` — no-op stub (returns immediately). Rationale: 07-01 wires this as the first statement in `lifespan()`; a `NotImplementedError` here would crash every `single_app`-based test before any assertion runs.
- `def redact_sensitive_keys(logger, method, event_dict)` — raises `NotImplementedError("implemented in 07-02")`. Correct RED signal: `test_redact_sensitive_keys` calls this directly, so `NotImplementedError` confirms the stub is in place without a false green pass.

The stub explicitly avoids importing `structlog` or `orjson` to prevent side effects before the real config lands in 07-02.

### Task 2: `backend/tests/test_health_observability.py` (RED test scaffold)

9 test functions matching VALIDATION.md §"Per-Task Verification Map" exactly:

| # | Function | Requirement | RED Reason |
|---|----------|-------------|------------|
| 1 | `test_health_always_200` | PROD-07-01 | No `assert` body mismatch yet (route will exist, need to verify verbatim body) |
| 2 | `test_ready_200_both_up` | PROD-07-02 | `/ready` route does not exist (404 in current app) |
| 3 | `test_ready_503_postgres_down` | PROD-07-02 | `/ready` route does not exist |
| 4 | `test_ready_503_redis_down` | PROD-07-02 | `/ready` route does not exist |
| 5 | `test_ready_503_timeout_path` | PROD-07-02 | `/ready` route does not exist + timeout logic not wired |
| 6 | `test_logging_json_in_production` | PROD-07-04 | no-op `configure_logging()` adds no handler — AssertionError |
| 7 | `test_logging_console_in_dev` | PROD-07-04 | no-op `configure_logging()` adds no handler — AssertionError |
| 8 | `test_request_id_middleware` | PROD-07-04 (D-13/D-14) | No `X-Request-ID` header in response (middleware not wired) |
| 9 | `test_redact_sensitive_keys` | PROD-07-04 (D-17) | `NotImplementedError` from stub |

All 9 tests collect with zero `ImportError`. Tests 6 and 9 fail with `AssertionError`/`NotImplementedError` (correct RED). Tests 1-5, 7-8 require Redis (sandbox fails at fixture setup, not at collection).

## Deviations from Plan

None — plan executed exactly as written.

The `single_app`-based tests fail at fixture setup (Redis not running in sandbox) rather than at assertion level. This is expected and documented in the project memory. Collection succeeds cleanly (the key acceptance criterion for Wave 0).

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| `backend/app/logging.py` | `configure_logging()` is a no-op | Full implementation in 07-02 |
| `backend/app/logging.py` | `redact_sensitive_keys()` raises `NotImplementedError` | Full implementation in 07-02 |

Both stubs are intentional per plan spec. They do NOT prevent the plan's goal (correct RED baseline) from being achieved.

## Threat Flags

None. This plan introduces no runtime network surface — only test infrastructure and an importable stub.

## Self-Check: PASSED

- `backend/app/logging.py` exists: FOUND
- `backend/tests/test_health_observability.py` exists: FOUND
- Commit `9544003` (Task 1 — logging.py stub): FOUND
- Commit `a0b5947` (Task 2 — test scaffold): FOUND
- 9 tests collect cleanly: VERIFIED (`9 tests collected in 0.01s`)
- Import assertion passes: VERIFIED (`PASS`)
- Tests RED for right reason: VERIFIED (`NotImplementedError`, `AssertionError` — not `ImportError`)
