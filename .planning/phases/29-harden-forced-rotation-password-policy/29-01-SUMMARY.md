---
phase: 29-harden-forced-rotation-password-policy
plan: 01
subsystem: auth
tags: [password-policy, bcrypt, difflib, fastapi, forced-rotation, sqlalchemy]

# Dependency graph
requires:
  - phase: 06-default-admin-hardening
    provides: must_change_password DB column, JWT claim, CurrentUser claim, 403 enforcement gate + allowlist, forced-rotation endpoint with WR-01 default-credential/current-hash guards (all preserved verbatim by this plan)
provides:
  - FORCED_ROTATION_POLICY constant (min_length=12, all 4 char classes, history_count=5) enforced only on the flagged (must_change_password) rotation path
  - merge_policy_floor() — strictest-wins merge of a tenant's password_policy with a floor, so a tenant can be stricter but never weaker
  - password_similarity_ratio() / is_too_similar() — DoS-bounded (128-char truncation) difflib-based similarity guard, Django UserAttributeSimilarityValidator-style (0.7 threshold)
  - change_password(policy_override=) — optional strong-floor override param, additive and backward-compatible
  - Forced-rotation branch of POST /auth/change-password now rejects: weak complexity, superseded (non-current) password-history reuse, near-default-variant similarity, and current-password similarity — closing the WR-01 "Admin1234!" residual
affects: [30-, future-auth-hardening, security-review]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Policy-floor merge pattern (merge_policy_floor): additive strong-floor overrides that compose with tenant config without a schema/API change"
    - "Similarity guard via difflib.SequenceMatcher with pre-truncation (normalize THEN truncate) to bound O(n*m) cost against attacker-controlled input length"
    - "Core-style SQLAlchemy UPDATE for test-helper DB mutation, avoiding ORM identity-map staleness across sessions in multi-step integration tests"

key-files:
  created: []
  modified:
    - backend/app/auth/password.py
    - backend/app/auth/router.py
    - backend/tests/test_admin_hardening.py

key-decisions:
  - "FORCED_ROTATION_POLICY is applied via change_password(policy_override=...) only on the flagged (must_change_password) path; the normal change-password path and tenant-configured policies are untouched."
  - "The WR-01 current-hash guard is kept strictly before the change_password() call and before the new similarity guard, so a rotation back to the LIVE current password is still caught there — not by check_password_history — preserving the mechanism-isolation the Phase 06 tests rely on."
  - "password_similarity_ratio truncates to 128 chars AFTER casefold+strip normalization (not before), so the DoS cap and the normalization compose correctly and are independently testable."
  - "_reflag() test helper was switched from an ORM select+mutate+commit to a Core-style UPDATE after discovering an identity-map staleness bug (see Deviations) — this is a test-only change with no production impact."

requirements-completed: [WR-02]

# Metrics
duration: 55min
completed: 2026-08-04
---

# Phase 29 Plan 01: Harden Forced-Rotation Password Policy Summary

**Closed the WR-01 `Admin1234!` near-variant residual with a real complexity/history/similarity policy (FORCED_ROTATION_POLICY, min-length-12 + all 4 char classes + history_count=5, plus a difflib-based 0.7-threshold similarity guard) enforced only on the forced first-login rotation path.**

## Performance

- **Duration:** ~55 min
- **Completed:** 2026-08-04T08:22:25Z
- **Tasks:** 3/3 completed
- **Files modified:** 3 (`backend/app/auth/password.py`, `backend/app/auth/router.py`, `backend/tests/test_admin_hardening.py`)

## Accomplishments
- Added `FORCED_ROTATION_POLICY`, `merge_policy_floor()`, `password_similarity_ratio()`, and `is_too_similar()` to `password.py`, plus an additive `policy_override` param on `change_password()`.
- Wired a similarity guard (default-credential branch + submitted-current-password branch, each with a distinct 400 message) and the strong policy floor into the flagged branch of `POST /auth/change-password`, while preserving every existing WR-01 guard verbatim.
- Proved all 5 ROADMAP/threat-model success criteria with dedicated tests, including a 3-rotation cycle that isolates `check_password_history` from the WR-01 current-password guard (the superseded-reuse test), and a positive control proving the new guards are not over-broad.
- Full `test_admin_hardening.py` suite (19 tests: 14 pre-existing Phase 06 + 5 new Phase 29) is green; `ruff check`/`ruff format --check` clean on all touched files.

## Task Commits

Each task was committed atomically (strict RED → GREEN):

1. **Task 1: RED — extend test_admin_hardening.py with the forced-rotation policy contract** - `660b7cf` (test)
2. **Task 2: GREEN — add policy floor + similarity primitives to password.py** - `532db13` (feat)
3. **Task 3: GREEN — wire the strong policy + similarity guard into the forced-rotation branch** - `87d1568` (feat)

_No plan-metadata commit yet — this SUMMARY + STATE/ROADMAP updates will follow in the final docs commit._

## Files Created/Modified
- `backend/app/auth/password.py` - `FORCED_ROTATION_POLICY` constant; `merge_policy_floor()`, `password_similarity_ratio()`, `is_too_similar()` pure functions; `change_password(policy_override=)` param
- `backend/app/auth/router.py` - Flagged branch of `POST /auth/change-password`: similarity guard (two message branches) + `policy_override=FORCED_ROTATION_POLICY` on the flagged path only; WR-01 guards preserved verbatim
- `backend/tests/test_admin_hardening.py` - `_seed_password_user(password=...)` param, `_reflag()` helper, 5 new Phase 29 tests + 1 pure-function unit test (`test_password_similarity_helpers`)

## Decisions Made
- Similarity threshold fixed at 0.7 (Django `UserAttributeSimilarityValidator` default), applied to both the default-install-credential and submitted-current-password forbidden entries, with distinct 400 messages so each branch is independently provable.
- `password_similarity_ratio` normalizes (casefold + strip) before truncating to 128 chars, keeping normalization and the DoS cap composable and each independently testable (per the plan's checker-verified ratio table).
- Kept `change_password()`'s existing bare `dict` return-type annotation untouched (pre-existing, already baselined) but typed the new `policy_override` param and `merge_policy_floor`'s signature as `dict[str, Any]` to avoid introducing new mypy `type-arg` violations in the file being touched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a semgrep-flagged hardcoded-password-default-argument finding on the extended test seed helper**
- **Found during:** Task 1 (extending `_seed_password_user`)
- **Issue:** Adding `password: str = "Admin123!"` as a defaulted kwarg (as directed by the plan) tripped the repo's pre-commit semgrep gate (`python.lang.security.audit.hardcoded-password-default-argument`), which blocked the commit.
- **Fix:** Added an inline `# nosemgrep: <full-rule-id>` suppression on the function's `def` line (matching the existing precedent at `backend/tests/test_auth.py:82`) — the value is a well-known test fixture credential already used throughout this file, not a real secret.
- **Files modified:** `backend/tests/test_admin_hardening.py`
- **Committed in:** `660b7cf` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed `_reflag()` test helper's identity-map staleness causing a false test failure**
- **Found during:** Task 3 GREEN verification (running the full Phase 29 test suite)
- **Issue:** `_reflag()` (added in Task 1) used `select(User).where(...).scalar_one()` then mutated `.must_change_password = True` and committed. Because SQLAlchemy's async-session identity map returns the *same* cached Python object across repeated entity selects in one test session — and that cached object still held its initially-seeded `True` value even after a *different* session (the app's own request-scoped DB session, used during rotations 1 and 2) had committed it to `False` — the assignment `user.must_change_password = True` was a same-value no-op from the ORM's dirty-tracking perspective, so `_reflag()`'s commit silently wrote nothing. This surfaced as `test_rotation_rejects_superseded_password_history`'s final "flag stays True" assertion reading a stale `False`.
- **Fix:** Rewrote `_reflag()` to use a Core-style `update(User).where(User.id == user_id).values(must_change_password=True)` statement, which always issues a real UPDATE regardless of identity-map state.
- **Files modified:** `backend/tests/test_admin_hardening.py`
- **Verification:** `test_rotation_rejects_superseded_password_history` and the full 19-test suite pass.
- **Committed in:** `87d1568` (Task 3 commit)

**3. [Rule 3 - Blocking, documented not fixed] Logged a pre-existing mypy-baseline "note" flake as out of scope**
- **Found during:** Task 2 and Task 3 GREEN verification
- **Issue:** `mypy app/ | mypy-baseline filter --allow-unsynced` intermittently reports 2-6 "new" errors that are always `note:` hints ("Hint: pip install types-python-jose") attaching to whichever `jose`-importing file (`app/auth/jwt.py`, `app/auth/service.py`, `app/auth/dependencies.py`, or `app/connectors/google_workspace.py`) mypy happens to check first in a given run; `mypy-baseline.txt` only baselines this note trio once. Verified via `git stash` (reverting `password.py`/`router.py` entirely) + `rm -rf .mypy_cache` that this reproduces identically on unmodified committed code — it is not caused by this plan's changes.
- **Fix:** Not fixed (out of scope per the executor's SCOPE BOUNDARY rule — pre-existing, unrelated to this task's files). Diffed the full `mypy app/ | grep <file>` error list before vs. after each of Task 2's and Task 3's edits: byte-identical multiset of errors for both `password.py` and `router.py` (only line numbers shifted, from insertions). Confirmed zero new mypy errors introduced by this plan.
- **Files modified:** none (documented only)
- **Logged in:** `.planning/phases/29-harden-forced-rotation-password-policy/deferred-items.md`

---

**Total deviations:** 3 (2 auto-fixed bugs, 1 documented-and-deferred pre-existing flake)
**Impact on plan:** The semgrep suppression and the `_reflag()` fix were both necessary to land the plan's own test design correctly; neither touches production code. The deferred mypy-baseline flake is pre-existing tooling noise, confirmed unrelated to this plan's files via direct before/after diff — no scope creep.

## Issues Encountered
None beyond the two auto-fixed items above (both test-file-only, no production-code impact).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- WR-02 fully closed: the forced-rotation path enforces complexity (min-12 + all 4 classes), active password-history reuse-prevention (history_count=5), and a similarity/edit-distance guard closing the `Admin1234!` near-variant gap — all proven by dedicated, mechanism-isolated tests, with zero regression to the Phase 06 WR-01 suite.
- `merge_policy_floor()` is a general-purpose primitive; a future phase could reuse it to apply other path-specific policy floors (e.g., a stricter floor for OWNER-role rotations) without further schema changes.
- No blockers for subsequent phases.

---
*Phase: 29-harden-forced-rotation-password-policy*
*Completed: 2026-08-04*

## Self-Check: PASSED

- FOUND: backend/app/auth/password.py
- FOUND: backend/app/auth/router.py
- FOUND: backend/tests/test_admin_hardening.py
- FOUND: .planning/phases/29-harden-forced-rotation-password-policy/deferred-items.md
- FOUND: .planning/phases/29-harden-forced-rotation-password-policy/29-01-SUMMARY.md
- FOUND commit: 660b7cf
- FOUND commit: 532db13
- FOUND commit: 87d1568
