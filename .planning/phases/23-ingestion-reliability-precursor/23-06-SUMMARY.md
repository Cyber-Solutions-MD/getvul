---
phase: 23-ingestion-reliability-precursor
plan: 06
subsystem: api
tags: [alembic, sqlalchemy, fastapi, pydantic, react, typescript, vitest]

# Dependency graph
requires: []
provides:
  - "connector_configs.last_error + consecutive_failure_count columns (migration 030, chained after 029)"
  - "ConnectorConfig model + ConnectorResponse schema expose last_error/consecutive_failure_count"
  - "_to_response wire-boundary normalization: SUCCESS->ok, FAILED->failed, None->None, syncing passthrough"
  - "SyncStatusPill total-lookup fallback — never throws on an unmapped status value"
  - "frontend ConnectorConfig type + ConnectorConfigResponse type carry last_error/consecutive_failure_count"
affects: [23-07-sync-harness-failure-capture, 23-09-connector-card-health-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wire-boundary enum normalization lives in service.py::_to_response (CR-06 precedent), not the frontend"
    - "Frontend status-lookup Records use a `?? STATUS_CONFIG['__never']` total-lookup fallback so an unexpected wire value degrades instead of crashing the destructure"

key-files:
  created:
    - backend/alembic/versions/030_add_connector_health_columns.py
  modified:
    - backend/app/ticketing/models.py
    - backend/app/connectors/schemas.py
    - backend/app/connectors/service.py
    - frontend/src/components/connectors/sync-status-pill.tsx
    - frontend/src/components/connectors/sync-status-pill.test.tsx
    - frontend/src/components/connectors/connector-card.test.tsx
    - frontend/src/components/connectors/connector-form.test.tsx
    - frontend/src/types/connector.ts
    - frontend/src/lib/queries/use-connectors-admin.ts

key-decisions:
  - "_normalize_sync_status kept as a small module-level dict + function in service.py (not a shared enum) — matches the plan's 'tiny local mapping dict or helper' instruction and the existing CR-06 precedent scope"
  - "Regression test for the raw-value crash uses @ts-expect-error + a literal status=\"SUCCESS\" JSX attribute (rather than a double type-cast) so the acceptance-criteria grep pattern matches literally while tsc stays clean"
  - "connector-form.test.tsx MOCK_EXISTING fixed even though not in the plan's files_modified list — Rule 3 blocking-issue fix, tsc failed once ConnectorConfigResponse gained required fields"

requirements-completed: [REL-06]

# Metrics
duration: 12min
completed: 2026-07-27
---

# Phase 23 Plan 06: Connector Health Data-Model Prerequisites Summary

**Migration 030 adds `last_error`/`consecutive_failure_count` to `connector_configs`, and the SyncStatusPill's pre-existing render-crash on real backend status values (`"SUCCESS"`/`"FAILED"`) is fixed at both the wire boundary (backend normalization) and defensively (frontend total lookup).**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-27T13:06:00+03:00 (approx, worktree branch-check + read start)
- **Completed:** 2026-07-27T13:12:07+03:00
- **Tasks:** 3 completed
- **Files modified:** 9 (1 created, 8 modified)

## Accomplishments
- Migration 030 (`down_revision="029_add_must_change_password"`) adds the two health columns; applied `alembic upgrade head` → `downgrade -1` → `upgrade head` cleanly against the live local Postgres, confirming both directions work
- `ConnectorConfig` model, `ConnectorResponse` schema, and `_to_response` all carry `last_error`/`consecutive_failure_count` end-to-end
- Root-caused and fixed the actual bug: `_to_response` now normalizes the DB-raw uppercase `"SUCCESS"`/`"FAILED"` to the frontend's lowercase `'ok'`/`'failed'` contract (with a `'syncing'` passthrough for forward-compat), matching the existing CR-06 provider-lowercasing precedent
- `SyncStatusPill`'s `STATUS_CONFIG[key]` lookup is now total (`?? STATUS_CONFIG['__never']`) so any future un-normalized value degrades gracefully instead of throwing — proven by a TDD RED→GREEN regression test that literally renders `status="SUCCESS"` and asserts no throw
- Frontend `ConnectorConfig` (types/connector.ts) and `ConnectorConfigResponse` (use-connectors-admin.ts) types extended with the two new fields

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 030 + ConnectorConfig columns + response-schema exposure** - `75e9f72` (feat)
2. **Task 2: Normalize status wire values in `_to_response`** - `224c14a` (fix)
3. **Task 3: Fix SyncStatusPill + correct masking tests + extend ConnectorConfig type** - TDD, two commits:
   - RED: `f8081b1` (test) — failing regression test proving the crash
   - GREEN: `700e65e` (feat) — total-lookup fallback + type extensions, test suite green

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `backend/alembic/versions/030_add_connector_health_columns.py` - additive migration, two nullable/defaulted columns on `connector_configs`
- `backend/app/ticketing/models.py` - `ConnectorConfig.last_error` + `.consecutive_failure_count` columns
- `backend/app/connectors/schemas.py` - `ConnectorResponse` gains `last_error: str | None = None`, `consecutive_failure_count: int = 0`
- `backend/app/connectors/service.py` - `_normalize_sync_status()` helper + `_SYNC_STATUS_MAP`; `_to_response` populates the two new fields and normalizes `last_sync_status`
- `frontend/src/components/connectors/sync-status-pill.tsx` - total `STATUS_CONFIG` lookup fallback
- `frontend/src/components/connectors/sync-status-pill.test.tsx` - Test 6 regression case (raw `"SUCCESS"` doesn't throw)
- `frontend/src/components/connectors/connector-card.test.tsx` - `MOCK_CONNECTOR` gains `last_error: null, consecutive_failure_count: 0`
- `frontend/src/components/connectors/connector-form.test.tsx` - `MOCK_EXISTING` gains the same two fields (Rule 3 fix, see below)
- `frontend/src/types/connector.ts` - `ConnectorConfig` interface gains `last_error`/`consecutive_failure_count`
- `frontend/src/lib/queries/use-connectors-admin.ts` - `ConnectorConfigResponse` type gains `last_error`/`consecutive_failure_count`

## Decisions Made
- Kept the status-normalization mapping as a tiny local dict (`_SYNC_STATUS_MAP`) + a `_normalize_sync_status()` function in `service.py`, per the plan's explicit instruction and to match the CR-06 precedent's scope (no new shared enum/module introduced by this plan — D-23's formal enum is later-plan scope)
- The TDD regression test proves the bug with a literal `status="SUCCESS"` JSX attribute guarded by `@ts-expect-error` (rather than a double type-cast) so the plan's acceptance-criteria grep (`status="SUCCESS"`) matches literally while `tsc --noEmit` stays clean
- `ConnectorConfigResponse = ConnectorResponse` is a backward-compat alias, not a second schema — both plan-referenced "response schemas" are the same class; only one edit site was needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `connector-form.test.tsx` MOCK_EXISTING missing new required type fields**
- **Found during:** Task 3 (frontend type extension)
- **Issue:** Adding `last_error`/`consecutive_failure_count` as required fields to `ConnectorConfigResponse` broke `tsc --noEmit` — a mock object in `connector-form.test.tsx` (not listed in this plan's `files_modified`) no longer satisfied the type
- **Fix:** Added `last_error: null, consecutive_failure_count: 0` to `MOCK_EXISTING`
- **Files modified:** frontend/src/components/connectors/connector-form.test.tsx
- **Verification:** `npx tsc --noEmit` clean afterward
- **Committed in:** `700e65e` (part of Task 3 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary consequence of making the two new fields required (matching the backend schema's non-optional exposure); no scope creep — same fields, same semantics as the plan's other test-file edits.

## Issues Encountered
- This worktree had no local `.venv` (backend) or `node_modules` (frontend) — both are documented as non-portable across GSD parallel worktrees. Backend verification ran the main repo's `.venv` binaries with `PYTHONPATH` pointed at this worktree's `backend/` directory (imports resolve to worktree source, dependencies from the shared venv). Frontend verification used a symlink `frontend/node_modules -> ../../../frontend/node_modules` (untracked, not committed) so `npm run test`/`npx tsc` could resolve locally-installed packages. Neither workaround touched committed files.
- Postgres/Redis were already running via the existing `docker compose` stack (`getvul-postgres-1` on :5432), so the migration verification ran against the live local DB rather than a throwaway test DB — `alembic upgrade head` / `downgrade -1` / `upgrade head` all succeeded cleanly with no data loss (additive-only columns).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plans 07 (sync-harness failure capture: populate `last_error`/increment/reset `consecutive_failure_count`) and 09 (connector-card health UI: last-error inline display, next-sync line, failure count) can now build directly on this data model and fixed pill — the health surface's premise (a real sync-status value rendering without crashing) is proven, not assumed
- No production behavior changed for existing connectors beyond the wire-format fix (frontend now receives lowercase status instead of a crashing uppercase one) — this is a bug fix, not a new feature surface
- Two new nullable/defaulted columns exist in the live local DB; the same migration will apply cleanly to any other environment on `alembic upgrade head`

---
*Phase: 23-ingestion-reliability-precursor*
*Completed: 2026-07-27*

## Self-Check: PASSED

All 10 modified/created source files found on disk; all 4 task commits (`75e9f72`, `224c14a`, `f8081b1`, `700e65e`) found in git log.
