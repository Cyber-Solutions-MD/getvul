---
phase: 06-default-admin-hardening
plan: 00
subsystem: testing
tags: [pytest, vitest, jwt, fastapi, react, testing-library, red-scaffold, nyquist]

# Dependency graph
requires:
  - phase: 06-default-admin-hardening (planning)
    provides: 06-VALIDATION.md node-ID contract + 06-RESEARCH.md enforcement shape
provides:
  - backend/tests/test_admin_hardening.py — 12 RED pytest cases (the automated target for Waves 1-2)
  - frontend/src/app/change-password/change-password.test.tsx — 4 RED Vitest cases (the automated target for Wave 3)
affects: [06-01 (schema+seed), 06-02 (JWT claim + enforcement gate + rotation), 06-03 (frontend gate + page)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RED-first Wave 0: assert the post-implementation call shape so failures are TypeError/AttributeError/AssertionError, not skips"
    - "Enforcement (403 gate) tested with a real JWT + bearer AsyncClient (no get_current_user override) so the dependency actually runs"
    - "next/navigation + global.fetch mocked; redirect gate asserted via router.replace('/change-password')"

key-files:
  created:
    - backend/tests/test_admin_hardening.py
    - frontend/src/app/change-password/change-password.test.tsx
  modified: []

key-decisions:
  - "Enforcement body shape asserted as resp.json()['detail']['reason'] == 'password_change_required' (matches RESEARCH dependencies.py:457 HTTPException detail dict)"
  - "Non-allowlist route under test is GET /api/v1/vulnerabilities (viewer-gated, not on the change-password allowlist)"
  - "Dropped the swallowed MUST_CHANGE_PASSWORD_ALLOWLIST import — a try/except ImportError provides no RED value and would trip lint; per-test must_change_password symbols are the real RED triggers"

patterns-established:
  - "Wave 0 scaffold produces genuinely-failing tests (no xfail/skip/only) so downstream waves have a real green target"

requirements-completed: []  # This plan builds the RED target; PROD-06-01..04 are marked complete by Waves 1-3, not here.

# Metrics
duration: ~30min
completed: 2026-07-09
---

# Phase 6 Plan 00: Admin-Hardening Test Scaffold Summary

**12 RED pytest cases for the force-password-change flow (schema, JWT claim, 403 enforcement + allowlist, rotation/audit/fresh-token, refresh) plus 4 RED Vitest cases for the /change-password redirect gate and rotation form — the automated contract Waves 1-3 turn green.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-07-09 (worktree agent)
- **Completed:** 2026-07-09
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- `backend/tests/test_admin_hardening.py` — exactly the 12 node IDs fixed by 06-VALIDATION.md, all collecting and all RED (0 passed).
- `frontend/src/app/change-password/change-password.test.tsx` — 4 Vitest cases (redirect gate, form render, wrong-password error, success redirect), suite reports failure (RED) via the missing `./page` import + absent gate branch.
- Enforcement tests wired against a real JWT + bearer `AsyncClient` (no `get_current_user` override) so the future 403 gate is genuinely exercised, not bypassed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend test scaffold — test_admin_hardening.py (12 RED cases)** — `1518731` (test)
2. **Task 2: Frontend test scaffold — change-password.test.tsx (RED)** — `ffefb5d` (test)

## Files Created/Modified
- `backend/tests/test_admin_hardening.py` — 12 async pytest cases covering PROD-06-01..04: migration column, seed flag, JWT claim round-trip, CurrentUser claim, 403 enforcement, three allowlist/unblocked cases, rotation clears flag, rotation audit event, rotation fresh tokens, refresh reads current flag.
- `frontend/src/app/change-password/change-password.test.tsx` — 4 Vitest cases mocking `next/navigation` + `global.fetch`, asserting `router.replace('/change-password')` for a flagged user and `router.replace('/dashboard')` on successful rotation.

## Verification Results
- Backend collect-only lists exactly the 12 required node IDs verbatim.
- `grep -c "^async def test_\|^def test_"` → 12; `grep -c "xfail\|@pytest.mark.skip"` → 0.
- Running the file (Postgres reachable): **12 failed, 0 passed** — RED reasons are the intended `AttributeError` (missing `User.must_change_password`), `assert False is True` (seed omits flag), and `TypeError` (missing `must_change_password` kwarg). The "Event loop is closed" teardown noise is the known conftest `_reset_engine_pool` workaround, not a test outcome.
- Frontend `vitest run change-password` → 1 failed file, **0 passing**, exit 1; `grep -c "\.skip\|\.only\|it.todo"` → 0.

## Decisions Made
- Asserted the 403 enforcement body as `resp.json()['detail']['reason']` to match the `HTTPException(403, detail={"reason": "password_change_required"})` shape confirmed in 06-RESEARCH.md.
- Chose `GET /api/v1/vulnerabilities` as the non-allowlist protected route (viewer-gated, off the allowlist).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed the swallowed allowlist import block**
- **Found during:** Task 1 (backend scaffold)
- **Issue:** The plan's suggested `try/except ImportError` around `MUST_CHANGE_PASSWORD_ALLOWLIST` swallows the error, so it provides no RED value, leaves an unused binding, and would trip ruff (F401/unused). The unused `import pytest` was similarly dead.
- **Fix:** Removed both the swallowed allowlist import and the unused `pytest` import. The per-test `must_change_password` kwargs/attributes/column remain the genuine RED triggers, so RED semantics are preserved.
- **Files modified:** backend/tests/test_admin_hardening.py
- **Verification:** File collects 12 cases and all 12 fail RED; no unused-import lint surface.
- **Committed in:** `1518731` (Task 1 commit)

**2. [Rule 3 - Blocking] Docstring/comment wording to keep grep-based acceptance clean**
- **Found during:** Both tasks
- **Issue:** Literal tokens `xfail` / `skip` (backend docstring) and `.skip / .only / .todo` (frontend comment) tripped the acceptance greps (`grep -c` returned 1 instead of 0) even though no real markers were present.
- **Fix:** Reworded the docstring/comment to describe the no-marker intent without the literal tokens.
- **Files modified:** backend/tests/test_admin_hardening.py, frontend/src/app/change-password/change-password.test.tsx
- **Verification:** Both marker greps now return 0.
- **Committed in:** `1518731`, `ffefb5d`

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking, cleanliness/lint).
**Impact on plan:** No scope creep. RED semantics and the fixed node-ID contract are fully preserved; only dead code and grep-tripping prose were removed.

## Issues Encountered
- The worktree has no local `node_modules`/`.venv`. Ran the backend suite with the shared checkout's `.venv/bin/python` (absolute path) and Vitest via a temporary symlink to the shared `frontend/node_modules`, which was removed before committing so nothing extra was staged.

## Threat Flags
None — test scaffolding only; no runtime code or trust-boundary surface introduced (matches the plan's empty threat register beyond T-06-00-01, which is satisfied by copying node IDs + body shapes verbatim and proving RED).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 1 (06-01) can now implement the `must_change_password` column + seed flag against `test_migration_column` and `test_seed_flag`.
- Wave 2 (06-02) has the JWT-claim, CurrentUser, enforcement/allowlist, and rotation cases as its green target; note the enforcement gate must set `detail={"reason": "password_change_required"}` and export the allowlist constant.
- Wave 3 (06-03) must create `frontend/src/app/change-password/page.tsx` (default export) and add the `must_change_password` redirect branch to `lib/auth.tsx`'s route guard to turn the Vitest suite green.

## Self-Check: PASSED

- FOUND: backend/tests/test_admin_hardening.py
- FOUND: frontend/src/app/change-password/change-password.test.tsx
- FOUND: .planning/phases/06-default-admin-hardening/06-00-SUMMARY.md
- FOUND commit: 1518731 (Task 1)
- FOUND commit: ffefb5d (Task 2)

---
*Phase: 06-default-admin-hardening*
*Completed: 2026-07-09*
