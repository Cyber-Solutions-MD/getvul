---
phase: 06-default-admin-hardening
reviewed: 2026-07-09T00:00:00Z
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
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-07-09
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Forced default-admin password rotation. The backend enforcement gate is the strongest part of this phase: `_enforce_password_change_gate` runs on both the JWT and dev-token paths in `get_current_user`, FastAPI injects `Request` into the dependency even when it is a sub-dependency of `RequireRole`, and the allowlist is an exact-match `frozenset` with no prefix/case tricks. The `request is None` no-op is genuinely unreachable through the ASGI stack (every route resolves through the dependency with a populated `Request`), so the documented trade-off is acceptable — it is only exercised by direct in-process unit calls, which cannot originate from an attacker. The rotation ordering (clear flag -> audit -> commit -> reissue tokens) is correct, and refresh re-reads the live DB flag rather than trusting a stale claim.

The main defect is on the frontend: the post-login SPA navigation bypasses the client-side redirect gate because the login response payload (`UserInfo`) does not carry `must_change_password`, so a flagged admin logging in via password lands on `/dashboard` and hits a wall of backend 403s instead of the rotation page. The security boundary holds (the backend 403 is authoritative), but the intended UX flow is broken and the code comment asserting it works is inaccurate. Several secondary hardening gaps and robustness issues follow.

## Warnings

### WR-01: Flagged user bypasses the client-side rotation gate after password login

**File:** `frontend/src/lib/auth.tsx:155-160`, `frontend/src/app/login/page.tsx:284-287`
**Issue:** `storeTokens` sets `setUser(data.user)` directly from the `/auth/login` response body. That body is a `TokenResponse` whose `user` field is a `UserInfo` (`backend/app/auth/schemas.py:37-46`), which has **no `must_change_password` field**. So after a password login, `user.must_change_password` is `undefined`. The login page then immediately calls `router.replace(dest)` to `/dashboard` (login/page.tsx:284-287). The force-rotation `useEffect` (auth.tsx:120-124) never fires because `user?.must_change_password` is falsy. The flagged admin lands on `/dashboard`, and every `/api/v1/*` call returns the backend 403 `password_change_required` — a broken dashboard rather than the intended rotation prompt. The comment at auth.tsx:116-119 claims "it also fires post-login: the mount fetchMe resolves the flag" — this is false for the SPA login path; only a subsequent hard reload (which re-runs the mount `fetchMe`) recovers the flag and redirects. Security is intact (backend gate is authoritative), but the enforcement UX is dead on the primary path.
**Fix:** Have `storeTokens` hydrate the flag from `/auth/me` (which does return it) before navigating, or add `must_change_password` to the `UserInfo` schema and `issue_tokens` so the login payload carries it:
```python
# backend/app/auth/schemas.py — UserInfo
must_change_password: bool = False
```
```python
# backend/app/auth/service.py — issue_tokens, inside UserInfo(...)
must_change_password=user.must_change_password,
```
Then the existing auth.tsx:120-124 gate fires immediately after `storeTokens`.

### WR-02: `refreshToken` propagates a flagged user to `/dashboard` without gating

**File:** `frontend/src/lib/auth.tsx:136-153`
**Issue:** `refreshToken` calls `fetchMe(newToken)` and `setUser(u)` on success. `fetchMe` does return `must_change_password`, so the flag is set correctly here — but this path runs inside the mount effect and there is no guarantee the force-rotation `useEffect` re-evaluates before other route logic. More importantly, a flagged user whose access token has expired but whose refresh token is valid will be silently re-authenticated; the redirect gate depends on `pathname` being stable at that moment. This is a softer instance of WR-01. Combined with WR-01, the client gate only reliably fires on a cold page load, not on the interactive login/refresh paths.
**Fix:** Centralize the flag check: after any `setUser`, guard navigation on `must_change_password` in one place rather than relying on a `useEffect` that may race with the login page's own `router.replace`.

### WR-03: `setFormError` may receive a non-string `detail` and crash the render

**File:** `frontend/src/app/change-password/page.tsx:88-92`
**Issue:** On a non-ok response, `body?.detail` is passed to `setFormError`, then rendered in `<ErrorAlert>{formError}</ErrorAlert>`. `formError` is typed `string | null`, but FastAPI `HTTPException` details can be objects — e.g. the enforcement gate raises `detail={"reason": "password_change_required"}` (dependencies.py:110-111). Although `/auth/change-password` is allowlisted so the flag gate will not fire here, other 4xx responses on this route (or a future change) that return a structured `detail` would set `formError` to an object, and React will throw "Objects are not valid as a React child." The `?? 'Password change failed'` fallback does not catch a truthy object.
**Fix:** Coerce defensively:
```ts
const detail = body?.detail;
setFormError(typeof detail === 'string' ? detail : 'Password change failed. Try again.');
```

### WR-04: `create_admin` skips seeding if ANY user in ANY tenant has a password hash

**File:** `backend/create_admin.py:13-20`
**Issue:** The guard counts `users WHERE password_hash IS NOT NULL` across the entire table with no tenant scoping. In a multi-tenant deployment where a non-default tenant already has a password user, the default-admin seed is skipped entirely and no `admin@getvul.local` is created — which may be intended, but it also means the seed is not idempotent per-tenant and the operator gets no admin if the DB was populated by any other flow first. Conversely, if the intent is "only skip when the default admin already exists," the check is too broad.
**Fix:** Scope the existence check to the default admin identity, e.g. `SELECT COUNT(*) FROM users WHERE email = 'admin@getvul.local'`, so the seed is idempotent and independent of unrelated password users.

### WR-05: Default-credential reject is a brittle literal string, not a policy

**File:** `backend/app/auth/router.py:216-217`
**Issue:** The forced-rotation reject only blocks the exact literal `"Admin123!"`. The default tenant policy (`DEFAULT_POLICY`, password.py:19-26) has `history_count=0` and no complexity requirements, so a flagged admin can "rotate" to `Admin1234!`, `admin123!`, or ` Admin123! ` (trailing space) and satisfy the gate while keeping a near-default, guessable credential. The comment acknowledges the history-reuse hole but the mitigation is narrower than the threat. This weakens the security objective of the phase (force a genuinely new credential).
**Fix:** Reject reuse of the current password directly (compare `new_password` against the stored hash via `verify_password`) rather than a hardcoded literal, and/or enforce a minimum complexity policy on the default tenant so a trivially-similar password is not accepted:
```python
if flag_was_set and verify_password(new_password, user_row.password_hash):
    raise HTTPException(400, "Choose a password different from your current one")
```

## Info

### IN-01: `_enforce_password_change_gate` no-op on `request is None` is acceptable but undertested for the enforced path

**File:** `backend/app/auth/dependencies.py:98-112`
**Issue:** The no-op when `request is None` is safe in production (verified: FastAPI injects `Request` into the dependency and all sub-dependencies such as `RequireRole`, so real requests always populate it). However, `test_current_user_claim` (test_admin_hardening.py:163-186) exercises the dependency with `request` omitted, silently taking the no-op branch — the test asserts the claim survives but never exercises the gate through the async path in that case. The gate's real behavior is covered by `test_enforcement_*`, so this is informational, not a gap.
**Fix:** None required. Optionally assert in a test that a direct call with a flagged user and an explicit `request` mock raises 403, to lock the no-op boundary.

### IN-02: Endpoint bodies typed as bare `dict` bypass Pydantic validation

**File:** `backend/app/auth/router.py:142-146, 172-176, 194-199, 249-253, 266-269`
**Issue:** `register`, `login_password`, `change_password_endpoint`, `forgot_password`, and `reset_password` all accept `body: dict` and reach into it with `.get(...)`. This defeats FastAPI's request validation, allows arbitrary/oversized payloads through, and produces silent empty-string defaults (e.g. `body.get("new_password", "")`) rather than 422s. `RefreshRequest` shows the correct pattern already exists.
**Fix:** Define request models (e.g. `ChangePasswordRequest`) with typed, validated fields and use them as the parameter type.

### IN-03: Redundant/dead `require_role` helper alongside `RequireRole`

**File:** `backend/app/auth/dependencies.py:117-136`
**Issue:** `dependencies.py` defines a `ROLE_HIERARCHY` and a `require_role` factory, while `rbac.py` defines a separate `ROLE_HIERARCHY` (different values: 4/3/2/1 vs 40/30/20/10) and a `RequireRole` class. Two divergent role-hierarchy sources are a maintenance and correctness hazard; if only one is wired into routes, the other is dead code.
**Fix:** Consolidate on `rbac.py`'s `RequireRole` and remove the duplicate `ROLE_HIERARCHY`/`require_role` from `dependencies.py`.

### IN-04: Unused fetched row in rotation path

**File:** `backend/app/auth/router.py:238-239`
**Issue:** `tenant_row` is fetched and later used by `issue_tokens`, which is fine; but `user_row` is re-fetched via a fresh `select` even though `change_password` already loaded and mutated the same identity-mapped `User` object earlier in the request. The extra query is harmless (same identity map) but redundant.
**Fix:** Optional — `change_password` could return the mutated user object to avoid the re-query, tightening the flag-clear/token-reissue path.

---

_Reviewed: 2026-07-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
