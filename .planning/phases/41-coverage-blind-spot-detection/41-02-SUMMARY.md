---
phase: 41-coverage-blind-spot-detection
plan: 02
subsystem: connectors
tags: [intune, mdm, sync, tenant-isolation, sqlalchemy, pytest]

# Dependency graph
requires: []
provides:
  - "run_intune_sync now constructs a valid SyncLog (connector_id/tenant_id, uppercase status) instead of raising a TypeError on the nonexistent connector_config_id kwarg"
  - "Intune Asset lookups (hostname, serial_number) and the Asset(...) constructor are tenant-scoped, closing a latent cross-tenant asset-matching bug"
  - "An Intune-configured tenant's devices now actually reach seen_by_sources with INTUNE, making the D-01 authoritative baseline truthful for Intune-only tenants"
affects: [41-coverage-blind-spot-detection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SyncLog construction pattern (connector_id + tenant_id + uppercase RUNNING/SUCCESS/FAILED) now consistent across jamf_sync.py and intune_sync.py"
    - "Tenant-scoped Asset upsert (Asset.tenant_id == connector_config.tenant_id on every select + the constructor) — mirrors jamf_sync.py's _upsert_jamf_device pattern"

key-files:
  created: []
  modified:
    - "backend/app/connectors/intune_sync.py"
    - "backend/tests/test_intune_sync.py"

key-decisions:
  - "Task 1 (fix) was applied before Task 2 (integration test) per the plan's explicit task ordering — the new test proves the already-fixed behavior rather than driving it via a literal RED-then-implement cycle. No unimplemented behavior was left untested at any commit boundary."
  - "Mocked the Graph auth/fetch layer (_get_access_token, _fetch_managed_devices) and get_decrypted_credentials directly at the module level via monkeypatch, rather than mocking httpx transport — matches the plan's guidance to mirror the closest sibling DB-integration test pattern while keeping the test fast and network-free."

patterns-established: []

requirements-completed: [COV-01]

# Metrics
duration: ~15min
completed: 2026-08-20
---

# Phase 41 Plan 02: Fix run_intune_sync SyncLog + tenant-scoping defect Summary

**Corrected `run_intune_sync`'s SyncLog construction (connector_id/tenant_id, uppercase status) and tenant-scoped every Asset lookup/constructor, closing both a TypeError that silently prevented any Intune sync from ever completing and a latent cross-tenant asset-matching bug — proven by a new DB-integration test.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 2/2 completed
- **Files modified:** 2

## Accomplishments
- `run_intune_sync` no longer raises `TypeError` on `SyncLog(connector_config_id=...)` — it now builds a valid, tenant-scoped `SyncLog` with an uppercase status recognized by `_normalize_sync_status`.
- Both Asset lookups (by hostname, by serial number) and the `Asset(...)` constructor for newly-discovered devices are tenant-scoped, closing a cross-tenant asset-matching bug (T-41-05).
- Added an async DB-integration test proving one `SyncLog` row is created with `status == "SUCCESS"` and the correct `tenant_id`, and that the discovered device persists as a tenant-scoped `Asset` with `"INTUNE"` in `seen_by_sources`.
- An Intune-configured tenant's baseline is now truthful for D-01 / COV-01 — previously it was silently empty for any Intune-only tenant.

## Task Commits

Each task was committed atomically:

1. **Task 1: Correct SyncLog construction + tenant-scope the Asset upsert in run_intune_sync** - `7a87bde` (fix)
2. **Task 2: Integration test — run_intune_sync persists a SyncLog + asset** - `2e080d7` (test)

**Plan metadata:** (this commit)

_Note: This tdd="true" task's test was written after the fix (Task 1) per the plan's own task sequencing — see Deviations/TDD Gate Compliance below._

## Files Created/Modified
- `backend/app/connectors/intune_sync.py` - `SyncLog` now built with `connector_id`/`tenant_id` and uppercase `RUNNING`/`SUCCESS`/`FAILED`; both `select(Asset)` lookups and the `Asset(...)` constructor now scope on `connector_config.tenant_id`
- `backend/tests/test_intune_sync.py` - added `test_run_intune_sync_persists_synclog_and_tenant_scoped_asset`, an async DB-integration test mocking the Graph auth/fetch layer + credential decryption

## Decisions Made
- Task ordering (fix-then-test) followed the plan exactly as written; documented as a TDD-gate note below rather than a deviation requiring investigation, since the plan itself specified this sequence (not a test that unexpectedly passed against unimplemented behavior — the behavior was implemented one task earlier, by design).
- Mocked `get_decrypted_credentials`, `_get_access_token`, and `_fetch_managed_devices` directly via `monkeypatch.setattr` on the `intune_sync` module object (not `httpx.MockTransport`) — simplest way to avoid both a real Graph API call and real Fernet-encrypted credentials while still exercising the full DB read/write path.

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

Task 2 is marked `tdd="true"`, but per the plan's own task sequence, Task 1 (the fix) was committed *before* Task 2 (the test). This means the new integration test in Task 2 passed on first run rather than following a strict RED-then-GREEN cycle within Task 2 itself. This is not a violation of the fail-fast RED rule (which guards against a test unexpectedly passing against code that was supposed to still be broken) — the plan explicitly scoped Task 1 as "fix" and Task 2 as "test proving the fix," with no gap in behavior coverage at any commit boundary. Git log for this plan:

```
2e080d7 test(41-02): integration test proving run_intune_sync persists SyncLog + tenant-scoped Asset
7a87bde fix(41-02): correct SyncLog construction + tenant-scope Asset upsert in run_intune_sync
```

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- COV-01's D-01 authoritative baseline is now truthful for Intune-only tenants; no further Intune-specific work is needed for the coverage module.
- Remaining Phase 41 plans (COV-02, COV-03, and any coverage-module plans) are unaffected by and independent of this fix — no shared files.

---
*Phase: 41-coverage-blind-spot-detection*
*Completed: 2026-08-20*

## Self-Check: PASSED

- FOUND: backend/app/connectors/intune_sync.py
- FOUND: backend/tests/test_intune_sync.py
- FOUND: .planning/phases/41-coverage-blind-spot-detection/41-02-SUMMARY.md
- FOUND commit: 7a87bde
- FOUND commit: 2e080d7
