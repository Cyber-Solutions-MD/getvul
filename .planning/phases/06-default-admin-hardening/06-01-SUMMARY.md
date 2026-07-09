---
phase: 06-default-admin-hardening
plan: 01
subsystem: database
tags: [alembic, sqlalchemy, postgres, migration, auth, admin-hardening]

# Dependency graph
requires:
  - phase: 06-default-admin-hardening (plan 00)
    provides: backend/tests/test_admin_hardening.py (12 contractual RED test cases)
provides:
  - users.must_change_password column (boolean, NOT NULL, server_default false)
  - Alembic migration 029 (revision chain 028 -> 029) with real downgrade
  - User ORM mapped column .must_change_password
  - create_admin.py seeds must_change_password=true on the OWNER admin
  - migration applied to the running DB (head 029_add_must_change_password)
affects: [06-default-admin-hardening plan 02, 06-default-admin-hardening plan 03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive boolean flag column: NOT NULL + server_default false so every existing row gets a concrete non-NULL value (no NULL-bypass of a security gate)"
    - "Hand-written alembic revision (no autogenerate) mirroring the 011 column-add pattern"

key-files:
  created:
    - backend/alembic/versions/029_add_must_change_password.py
    - backend/tests/test_admin_hardening.py
  modified:
    - backend/app/tenants/models.py
    - backend/create_admin.py

key-decisions:
  - "Column is NOT NULL + server_default false (T-06-01-02) so no row can bypass the enforcement gate with a NULL/falsy flag"
  - "Seed sets literal true (T-06-01-01) so the shipped admin@getvul.local / Admin123! default cannot be used past first login"
  - "Migration applied to the running DB before Wave 2 (T-06-01-03) to prevent AttributeError/DB-error storms once Wave 2 reads the flag"

patterns-established:
  - "Security flag columns default to the safe value at the DB layer (server_default), not only the ORM layer"

requirements-completed: [PROD-06-01]

# Metrics
duration: ~12min
completed: 2026-07-09
---

# Phase 6 Plan 01: Forced-Rotation Persistence Layer Summary

**Added users.must_change_password (boolean, NOT NULL, server_default false) via Alembic migration 029 + matching ORM column, and seeded it true on the OWNER admin so the default admin credential is forced to rotate on first login.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-09T06:56Z (approx, post environment setup)
- **Completed:** 2026-07-09T07:08:37Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- Migration 029 adds `users.must_change_password` (Boolean, NOT NULL, server_default false) with a real reversible downgrade; revision chain 028 -> 029 verified as head.
- `User` ORM model exposes `.must_change_password` (default False, server_default false) so Wave 2/3 code reads it without AttributeError.
- `create_admin.py` seed sets `must_change_password = true` on the OWNER admin (D-02).
- Migration applied to the running Postgres (head `029_add_must_change_password`); down/up cycle spot-checked clean.
- PROD-06-01 tests `test_migration_column` + `test_seed_flag` are GREEN; `test_auth.py` regression stays green (9 passed).

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 029 + User model column** - `cb2da47` (feat)
2. **Task 2: Seed flag + apply migration + green column/seed tests** - `536bb16` (feat)

## Files Created/Modified
- `backend/alembic/versions/029_add_must_change_password.py` - Additive migration adding `users.must_change_password` (Boolean, NOT NULL, server_default false) with a real `drop_column` downgrade.
- `backend/app/tenants/models.py` - Added `must_change_password: Mapped[bool]` column to the `User` model (default False, server_default false), placed near `password_history`.
- `backend/create_admin.py` - Appended `must_change_password` + literal `true` to the seeded OWNER admin INSERT.
- `backend/tests/test_admin_hardening.py` - Created (Wave-0 dependency, see deviation): 12 contractual node IDs; `test_migration_column` + `test_seed_flag` GREEN, other 10 honest RED stubs for Waves 2-3.

## Decisions Made
- Column enforced NOT NULL + server_default false at the DB layer (not just ORM default) so no existing/future row can present a NULL/falsy flag and slip past the Wave-2 enforcement gate (T-06-01-02).
- Applied the migration to the live DB as part of this plan (rather than deferring) because Wave 2 `depends_on: [01]` and reads the column — an unapplied migration would produce runtime DB errors (T-06-01-03).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created the Wave-0 test file test_admin_hardening.py**
- **Found during:** Task 2 (verification requires `test_migration_column` + `test_seed_flag`)
- **Issue:** Plan 06-00 (Wave 0, the test scaffold) had not been merged onto this executor's base at spawn time. The base was the pre-wave phase commit `74da062`, and the worktree had additionally been branched from a stale HEAD (~370 commits behind the real phase base) — resolved via the branch-check hard reset to `74da062`. The referenced test file existed nowhere in the repo, so Task 2 had no automated verify target.
- **Fix:** Created `backend/tests/test_admin_hardening.py` with the exact 12 contractual node IDs from 06-VALIDATION.md. Implemented the two Wave-1 cases (`test_migration_column`, `test_seed_flag`) GREEN; wrote the other 10 as honest RED stubs (plain `pytest.fail(...)`, no skip/xfail) asserting the real Wave 2/3 behaviour.
- **Files modified:** backend/tests/test_admin_hardening.py
- **Verification:** `pytest tests/test_admin_hardening.py --collect-only` lists exactly 12 node IDs; full run reports 2 passed / 10 failed (RED); no skip/xfail/only markers.
- **Committed in:** `536bb16` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed NOT-NULL idp_subject violation in test_migration_column's raw insert**
- **Found during:** Task 2 (first run of `test_migration_column`)
- **Issue:** The running DB enforces NOT NULL on `users.idp_subject`; the test's raw INSERT omitted it and raised `NotNullViolationError`.
- **Fix:** Added `idp_subject` (+ bind param) to the test's INSERT.
- **Files modified:** backend/tests/test_admin_hardening.py
- **Verification:** `test_migration_column` passes.
- **Committed in:** `536bb16` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug — both confined to the test file)
**Impact on plan:** No change to the plan's production deliverables (migration 029, ORM column, seed). The blocking fix supplies the missing Wave-0 dependency so this plan is genuinely verified; the bug fix is inside that new test file only. No scope creep in production code.

## Issues Encountered
- **Environment down:** Postgres + Redis containers were stopped (only a broken restarting nginx). Started `postgres` + `redis` via `docker compose up -d`; generated a valid Fernet `ENCRYPTION_KEY` and a `JWT_SECRET_KEY` for the local run (MEMORY.md `getvul-backend-pytest-env`). The worktree has no `.venv`; used the main checkout's `backend/.venv` with `PYTHONPATH` pointed at the worktree backend so imports and alembic resolve the worktree copy.
- **Stale-base hazard (MEMORY.md `gsd-worktree-stale-base-hazard`):** the worktree branch was ~370 commits behind the real phase base. The branch-check hard reset to `74da062` recovered a clean base; verified no poisoned revert was committed (only the 4 intended files are in the two task commits).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 2 (plan 06-02) can now read `user.must_change_password` (column exists in DB at head 029 + on the ORM model) and green its 8 enforcement/JWT tests.
- The 10 RED stub cases in `test_admin_hardening.py` are the concrete targets for Waves 2-3.
- **Orchestrator note:** the migration was applied to the *local dev DB* used for this run. Production/CI DBs still need `alembic upgrade head` at deploy time. Wave-0 plan 06-00 was effectively fulfilled here (the test file); if the orchestrator also merges a separate 06-00 output, de-duplicate `backend/tests/test_admin_hardening.py`.

## Self-Check: PASSED

Files verified present: migration 029, test_admin_hardening.py, models.py, create_admin.py, 06-01-SUMMARY.md.
Commits verified present: cb2da47 (Task 1), 536bb16 (Task 2).

---
*Phase: 06-default-admin-hardening*
*Completed: 2026-07-09*
