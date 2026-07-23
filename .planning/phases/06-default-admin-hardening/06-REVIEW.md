---
phase: 06-default-admin-hardening
reviewed: 2026-07-23T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - backend/alembic/versions/029_add_must_change_password.py
  - backend/app/auth/dependencies.py
  - backend/app/auth/jwt.py
  - backend/app/auth/router.py
  - backend/app/auth/schemas.py
  - backend/app/auth/service.py
  - backend/app/tenants/models.py
  - backend/create_admin.py
  - backend/tests/test_admin_hardening.py
  - frontend/src/app/change-password/change-password.test.tsx
  - frontend/src/app/change-password/page.tsx
  - frontend/src/lib/auth.tsx
  - frontend/src/lib/validation/auth.ts
  - frontend/vitest.setup.ts
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-07-23 (re-review of a shipped phase; supersedes the 2026-07-09 report)
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Re-review of the v1.0 default-admin hardening phase against the CURRENT code. The two prior Warnings that mattered most — the broken client-side rotation UX (WR-01) and its refresh-path variant (WR-02) — have been **fixed** since 2026-07-09 and are no longer reported. The remaining findings are genuine but lower-stakes: they persist verbatim in the current tree and are re-confirmed below.

The security boundary remains strong. `_enforce_password_change_gate` (dependencies.py:102-116) runs on both the JWT and dev-token paths in `get_current_user`, the allowlist is an exact-match `frozenset` (dependencies.py:25-32), the JWT claim round-trips through `create_access_token`/`decode_token`, the DB column is `NOT NULL server_default false` (migration 029), and `refresh_access_token` re-reads the live DB flag rather than trusting a stale claim (service.py:96-125). The forced-rotation write order in the router (clear flag → audit → commit → reissue tokens) is correct and fail-closed on the audit row.

**Resolved since the prior review (verified against current code):**
- **WR-01 (client rotation gate bypass) — FIXED.** `UserInfo` now carries `must_change_password` (schemas.py:37-51) and `issue_tokens` populates it (service.py:83-92), so the `/auth/login` payload includes the flag. `storeTokens` → `setUser(data.user)` (auth.tsx:166-171) now arms the force-rotation `useEffect` (auth.tsx:131-135) immediately after a SPA login; the flagged admin is bounced to `/change-password` even though the login page also calls `router.replace(dest)` (login/page.tsx:284-287). The gate's inline comment is now accurate.
- **WR-02 (refresh propagates flagged user) — FIXED by the same change.** `refreshToken` → `fetchMe` → `setUser` (auth.tsx:147-164) also feeds the same gate, and `refresh_access_token` re-issues the claim from the current DB flag.

The two retained Warnings both concern the *strength* of the forced-rotation guarantee (weak-default reuse, seed idempotency), which is the security objective of this phase.

## Warnings

### WR-01: Default-credential reject is a brittle literal, not a policy (retained — verified against current code)

**File:** `backend/app/auth/router.py:216-217` (policy: `backend/app/auth/password.py:19-26`)
**Issue:** The forced-rotation guard still blocks only the exact literal `"Admin123!"`:
```python
if flag_was_set and new_password == "Admin123!":
    raise HTTPException(400, "Choose a password other than the default install credential")
```
`DEFAULT_POLICY` has `history_count=0` and every complexity requirement `False`, so a flagged admin can satisfy the gate with a trivially-near-default credential — `Admin1234!`, `admin123!`, or `" Admin123!"` (leading/trailing space; `new_password` is never stripped) — all of which clear the min-length-8 check and rotate the flag to False. `change_password` also does not reject reusing the *current* password when `history_count == 0`. This weakens the phase's core objective (force a genuinely new credential).
**Fix:** Reject reuse of the current password by hash rather than matching a literal, and/or enforce minimal complexity on the default tenant:
```python
if flag_was_set and verify_password(new_password, user_row.password_hash):
    raise HTTPException(400, "Choose a password different from your current one")
```

### WR-02: `create_admin` skips seeding if ANY user in ANY tenant has a password hash (retained — verified against current code)

**File:** `backend/create_admin.py:13-18`
**Issue:** Unchanged since the prior review. The idempotency guard counts password users table-wide with no identity/tenant scoping:
```python
result = await db.execute(text("SELECT COUNT(*) FROM users WHERE password_hash IS NOT NULL"))
count = result.scalar()
if count > 0:
    print("    App users already exist — skipping.")
    return
```
In any deployment where a non-default tenant already has a password user (e.g. a `register` call ran first), the default-admin seed is skipped and no `admin@getvul.local` is created. The seed is not idempotent on its own identity — it is coupled to unrelated password users.
**Fix:** Scope the existence check to the seed identity so it is idempotent and independent of other users:
```python
result = await db.execute(text("SELECT COUNT(*) FROM users WHERE email = 'admin@getvul.local'"))
```

## Info

### IN-01: `change-password` error handler may pass a non-string `detail` to a React child (was WR-03; downgraded — not currently reachable)

**File:** `frontend/src/app/change-password/page.tsx:89-93`
**Issue:** `setFormError(body?.detail ?? 'Password change failed. Try again.')` forwards `body.detail` unchanged into `<ErrorAlert>{formError}</ErrorAlert>`. `formError` is typed `string | null`, but FastAPI can return a structured `detail` (the gate uses `detail={"reason": "password_change_required"}`). **Currently not reachable:** `/auth/change-password` is on the allowlist so the gate never fires here, and every other raise on this route returns a string detail — so no object reaches `setFormError` today. It remains a latent defensive-coding gap: any future 4xx on this route that returns an object detail would throw "Objects are not valid as a React child." Downgraded from Warning to Info because it cannot fire against the current backend.
**Fix:** Coerce defensively: `const d = body?.detail; setFormError(typeof d === 'string' ? d : 'Password change failed. Try again.');`

### IN-02: `_enforce_password_change_gate` no-op on `request is None` is undertested for the enforced path (retained)

**File:** `backend/app/auth/dependencies.py:102-116`; test at `backend/tests/test_admin_hardening.py:156-177`
**Issue:** The `if request is None: return` no-op is safe in production (FastAPI always injects `Request` through the ASGI stack, including via `RequireRole`/`require_role` sub-dependencies). But `test_current_user_claim` still calls `get_current_user(credentials=creds, db=db_session)` with `request` omitted, silently taking the no-op branch — it asserts the claim survives but never exercises the gate in that call. The gate's real behavior is covered by the `test_enforcement_*` cases via a real ASGI client, so this is informational.
**Fix:** None required. Optionally add a direct-call test that passes a mock `Request` with a non-allowlist path and a flagged user, asserting the 403 — to lock the no-op boundary.

### IN-03: Two divergent role hierarchies coexist; `require_role` is live, not dead (retained — reclassified)

**File:** `backend/app/auth/dependencies.py:121-140` vs `backend/app/auth/rbac.py:14-53`
**Issue:** `dependencies.py` defines `ROLE_HIERARCHY = {"owner": 4, "admin": 3, "analyst": 2, "viewer": 1}` plus a `require_role` factory; `rbac.py` defines a separate `ROLE_HIERARCHY` keyed on `UserRole.*.value` with different magnitudes (40/30/20/10) plus the `RequireRole` class. Contrary to the prior review's "dead code" framing, `require_role` **is wired in** — `app/assets/router.py:538,551` gate admin-only asset endpoints on `Depends(require_role("admin"))`. The lowercasing (`user.role.lower()`) makes it behave correctly today, but two independent, divergent role-hierarchy sources for the same RBAC concept is a real maintenance/correctness hazard: a future role tweak applied to one map silently diverges from the other.
**Fix:** Consolidate on `rbac.py`'s `RequireRole`, migrate the two `assets/router.py` call sites, and delete the duplicate `ROLE_HIERARCHY`/`require_role` from `dependencies.py`.

### IN-04: Endpoint bodies typed as bare `dict` bypass Pydantic validation (retained)

**File:** `backend/app/auth/router.py:141-156, 171-191, 194-224, 249-263, 266-286`
**Issue:** `register`, `login_password`, `change_password_endpoint`, `forgot_password`, and `reset_password` all accept `body: dict` and reach in via `.get(...)`, defeating FastAPI request validation and producing silent empty-string defaults (`body.get("new_password", "")`) instead of 422s. `RefreshRequest` (used by `/auth/refresh`) demonstrates the correct typed pattern already exists in this file.
**Fix:** Define request models (e.g. `ChangePasswordRequest`, `LoginRequest`) with typed, validated fields.

### IN-05: Redundant re-fetch of the mutated user in the rotation path (retained)

**File:** `backend/app/auth/router.py:238`
**Issue:** In the flagged-rotation branch, `user_row` is re-`select`ed even though `change_password` already loaded and mutated the same identity-mapped `User` (setting `password_hash`/`password_history`) earlier in the request. The re-query is harmless (SQLAlchemy identity map returns the same object) but redundant.
**Fix:** Optional — have `change_password` return the mutated `User` so the rotation branch reuses it instead of re-querying.

---

_Reviewed: 2026-07-23 (re-review; prior report dated 2026-07-09 superseded)_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
