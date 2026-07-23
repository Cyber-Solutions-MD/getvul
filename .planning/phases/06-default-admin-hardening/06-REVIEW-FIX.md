---
phase: 06-default-admin-hardening
fixed_at: 2026-07-23T00:00:00Z
review_path: .planning/phases/06-default-admin-hardening/06-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-07-23
**Source review:** .planning/phases/06-default-admin-hardening/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (Warnings; the review reported 0 Critical, 5 Info)
- Fixed: 2
- Skipped: 0

Both in-scope Warnings concern the *strength* of the phase's forced-rotation
guarantee. Changes are behavior-preserving and minimal; the full
`test_admin_hardening.py` file passes (13 tests, incl. 1 new — see below).

## Fixed Issues

### WR-02: `create_admin` skips seeding if ANY user in ANY tenant has a password hash

**Files modified:** `backend/create_admin.py`
**Commit:** 3f5b937
**Applied fix:** Re-scoped the idempotency guard from a table-wide count
(`WHERE password_hash IS NOT NULL`) to the seed's own identity
(`WHERE email = 'admin@getvul.local'`). The default admin is now seeded
independently of unrelated password users in other tenants (e.g. after a
`register` call), and the seed remains idempotent on re-run. Updated the
skip message to match ("Default admin already exists — skipping."). Verified
by the existing `test_seed_flag` contract test (passes).

### WR-01: Default-credential reject is a brittle literal, not a policy

**Files modified:** `backend/app/auth/router.py`, `backend/tests/test_admin_hardening.py`
**Commit:** 9ab0aa3
**Status:** fixed: requires human verification (security-logic change)
**Applied fix:** Replaced the exact-literal check
(`new_password == "Admin123!"`) in the forced-rotation branch of
`change_password_endpoint` with two complementary, safe guards, applied only
when `flag_was_set`:
1. **Normalized default-credential match** — reject when
   `new_password.strip().casefold()` equals the default credential's casefold.
   This closes the finding's cited bypasses: leading/trailing whitespace
   (`" Admin123!"`, `"Admin123! "`) and case variants (`"admin123!"`,
   `"ADMIN123!"`).
2. **Current-password reuse rejection by hash** — read the caller's current
   `password_hash` and reject if `verify_password(new_password, current_hash)`
   is true. This generalizes the guard beyond a single hardcoded literal (the
   review's primary recommendation) and defends the objective directly:
   a flagged user cannot rotate back to whatever they currently have.

Added `test_rotation_rejects_default_variant`, which asserts all cited
variants (` Admin123!`, `Admin123! `, `admin123!`, `ADMIN123!`, exact
`Admin123!`) are rejected 400 and leave `must_change_password = True`.
Existing rotation tests (which rotate to `NewPassw0rd!x`) remain green, so the
legitimate happy path is preserved.

**Why "requires human verification":** this is a security-boundary condition.
Tier-1 (re-read) and Tier-2 (syntax) verification confirm structure, and the
test file passes, but a human should confirm the rejection semantics match
intent before the phase proceeds.

**Residual flagged for backlog (out of scope here):** near-but-not-equal
variants such as `Admin1234!` (extra char) still pass. Catching those requires
a real password complexity / similarity (edit-distance) / history policy —
`DEFAULT_POLICY` currently sets `history_count=0` and every complexity flag
`False`. That is a larger design change and was deliberately NOT implemented as
part of this minimal, confident hardening. Recommended follow-up: a genuine
complexity+history policy on the LOCAL/default tenant. This is documented in an
inline `RESIDUAL (backlog)` comment at the fix site.

## Test Results

Ran per the backend pytest env note (MEMORY `getvul-backend-pytest-env`):
`ENCRYPTION_KEY` + `JWT_SECRET_KEY` set, single file, in `backend/.venv`:

```
tests/test_admin_hardening.py .............  [100%]
13 passed, 1 warning in 9.79s
```

Postgres was reachable, so no tests were skipped (all 12 original contract
tests + the 1 new WR-01 test executed and passed). The lone warning is a
pre-existing Pydantic-v2 deprecation in `app/connectors/schemas.py`, unrelated
to this change.

---

_Fixed: 2026-07-23_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
