---
phase: 06-default-admin-hardening
verified: 2026-07-09T15:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Frontend login flow reads must_change_password from the /auth/login response and routes to /change-password on the primary SPA login path (no reload required)"
  gaps_remaining: []
  regressions: []
---

# Phase 6: Default Admin Hardening Verification Report

**Phase Goal:** A fresh install.sh deploy cannot remain on the default `Admin123!` password by accident; the operator is forced through a rotation.
**Verified:** 2026-07-09T15:00:00Z (re-verification after commit db20589)
**Status:** passed
**Re-verification:** Yes — after SC#4 gap closure (commit db205894a2dfcdc81dad3062b21c1995c9bf9c60)

## Gap Closure Summary

The single blocker from the initial verification (SC#4) has been resolved by commit db20589.

**Root cause (prior):** `UserInfo` — the schema embedded in every `/auth/login` `TokenResponse` — had no `must_change_password` field. After a primary SPA login, `storeTokens` hydrated the user from `data.user` (a `UserInfo`) with no flag, so `user?.must_change_password` was `undefined`. The `AuthProvider` force-rotation `useEffect` never fired. The flagged admin reached `/dashboard` and received cascading backend 403 responses.

**Fix applied (db20589):**

- `backend/app/auth/schemas.py` line 51: `must_change_password: bool = False` added to `UserInfo` with explanatory comment referencing PROD-06-03/SC#4.
- `backend/app/auth/service.py` line 91: `issue_tokens()` now passes `must_change_password=user.must_change_password` to the `UserInfo(...)` constructor. The login response carries the live DB value.
- `frontend/src/lib/auth.tsx` lines 115-127: comments corrected to reflect that the flag is sourced from both `/auth/login` (SPA login path) and `/auth/me` (hard reload). The `useEffect` gate itself was already correct; only its comment was wrong. No logic change required.
- `backend/tests/test_auth.py` — `TestLoginResponseFlag` (2 cases): directly calls `issue_tokens()` and asserts `resp.user.must_change_password` is `True`/`False` per the user model.
- `frontend/src/app/change-password/change-password.test.tsx` — second Vitest case "redirect gate fires after a fresh SPA login (no reload)": no stored token, mock `/auth/login` returns `must_change_password: true` in `user`, triggers `login()` via `LoginTrigger`, asserts `router.replace('/change-password')` fires via `waitFor` without any `/auth/me` call in the chain.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | New `users.must_change_password` column (boolean, default false) added by Alembic migration | VERIFIED | `backend/alembic/versions/029_add_must_change_password.py` exists with correct revision chain `029 -> 028`, `sa.Column("must_change_password", sa.Boolean(), server_default="false", nullable=False)`. ORM column in `backend/app/tenants/models.py:66-68` as `Mapped[bool]` with `default=False, server_default="false"`. |
| 2 | `backend/create_admin.py` sets the flag to true on the seeded admin | VERIFIED | `create_admin.py:42-44` — INSERT includes `must_change_password` in the column list with literal `true` in VALUES. |
| 3 | Auth dependency rejects all non-`/auth/change-password` calls with 403 + `password_change_required` while the flag is set | VERIFIED | `MUST_CHANGE_PASSWORD_ALLOWLIST` frozenset at `dependencies.py:25-32` (4 paths exact-match). `_enforce_password_change_gate` at `dependencies.py:98-112` raises `HTTPException(403, detail={"reason": "password_change_required"})`. Gate runs on both JWT and dev-token paths. |
| 4 | Frontend login flow reads the flag and routes to a force-rotation page — on the primary SPA login path, not only after a hard reload | VERIFIED | `schemas.py:51` adds `must_change_password: bool = False` to `UserInfo`. `service.py:91` populates `must_change_password=user.must_change_password` in `issue_tokens()`. `auth.tsx:162` `storeTokens` calls `setUser(data.user)` carrying the flag. `auth.tsx:123-127` force-rotation `useEffect` watches `[loading, user, pathname, router]` — fires when `user.must_change_password` becomes truthy, calling `router.replace('/change-password')`. Vitest regression case "redirect gate fires after a fresh SPA login (no reload)" confirms the chain: no stored token, mock `/auth/login` returns flagged `UserInfo`, `login()` called, gate fires without `/auth/me`. |
| 5 | Successful rotation clears the flag and emits an `auth.first_login_rotation` audit event | VERIFIED | `router.py:240` sets `user_row.must_change_password = False`. `router.py:242` calls `await audit(db, user, "auth.first_login_rotation", ...)` BEFORE `db.commit()` (AUDIT-01 order). `issue_tokens()` called at line 246 returning flag-free tokens. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/029_add_must_change_password.py` | Additive migration adding `users.must_change_password` | VERIFIED | Exists. Correct revision chain `029 -> 028`. `nullable=False`, `server_default="false"`, downgrade drops column. |
| `backend/app/tenants/models.py` | `User.must_change_password` mapped column | VERIFIED | Line 66-68: `Mapped[bool]` with `Boolean, default=False, server_default="false"`. |
| `backend/create_admin.py` | Seed sets `must_change_password=true` | VERIFIED | Line 43: `must_change_password` in column list, literal `true` in VALUES. |
| `backend/app/auth/jwt.py` | `must_change_password` claim in `create_access_token` + `TokenPayload` + `decode_token` | VERIFIED | `create_access_token` kwarg `must_change_password: bool = False`. Payload key at line 54. `TokenPayload.__init__` default `False`. `decode_token` extracts via `payload.get("must_change_password", False)`. |
| `backend/app/auth/dependencies.py` | Request-injected enforcement gate + `MUST_CHANGE_PASSWORD_ALLOWLIST` | VERIFIED | `MUST_CHANGE_PASSWORD_ALLOWLIST` at lines 25-32, exactly 4 paths. `_enforce_password_change_gate` function. `request: Request` injected. Both construction sites populate the field. |
| `backend/app/auth/router.py` | Rotation completion: clear flag, audit, fresh tokens, `Admin123!` reject | VERIFIED | `auth.first_login_rotation` at line 242. `Admin123!` reject at lines 216-217. `issue_tokens()` called at line 246. Ordering: flag clear -> audit -> commit -> tokens. |
| `backend/app/auth/service.py` | `issue_tokens` populates `UserInfo.must_change_password` from `user.must_change_password` | VERIFIED | Line 91: `must_change_password=user.must_change_password` in `UserInfo(...)` constructor. `refresh_access_token` line 119: `must_change_password=user.must_change_password` in `create_access_token`. |
| `backend/app/auth/schemas.py` — `UserInfo` | `must_change_password: bool = False` on `UserInfo` (login response) | VERIFIED | Line 51: field added with explanatory comment. Default `False` preserves backward compatibility with pre-flag callers. Previously FAILED; fixed in db20589. |
| `frontend/src/app/change-password/page.tsx` | Force-rotation page outside `(authed)` group | VERIFIED | File exists at `frontend/src/app/change-password/page.tsx` — peer of `login/`, not under `(authed)/`. Three-field form (current/new/confirm), `ErrorAlert`, raw fetch, token swap before `router.replace(sanitizeNext(...))`. |
| `frontend/src/lib/auth.tsx` | `User.must_change_password` + redirect gate fires on primary SPA login path | VERIFIED | `must_change_password?: boolean` in `User` interface (line 27). `useEffect` at lines 123-127 redirects when flag is true. `storeTokens` (line 162) calls `setUser(data.user)` — now carries the flag from the login response. Gate fires on both the mount `fetchMe` path and the interactive login path. |
| `frontend/src/lib/validation/auth.ts` | `changePasswordSchema` | VERIFIED | `changePasswordSchema` at line 27. `ChangePasswordInput` type exported. |
| `backend/tests/test_admin_hardening.py` | 12 pytest test cases covering migration, seed, JWT, enforcement, rotation | VERIFIED | All 12 node IDs present. No skip/xfail markers. |
| `backend/tests/test_auth.py` — `TestLoginResponseFlag` | 2 regression cases asserting `issue_tokens()` UserInfo carries/defaults the flag | VERIFIED | Lines 127-154. `test_login_userinfo_carries_flag_when_set` asserts `resp.user.must_change_password is True`. `test_login_userinfo_flag_false_by_default` asserts `False`. Directly exercises `issue_tokens()` without needing a running DB. |
| `frontend/src/app/change-password/change-password.test.tsx` | Vitest suite (5 cases — original 4 + 1 regression) | VERIFIED | 5 cases. New case "redirect gate fires after a fresh SPA login (no reload)" (lines 90-141) tests the primary SPA login path: no stored token, mock `/auth/login` response with flagged `UserInfo`, `login()` triggered via `LoginTrigger`, `waitFor` asserts `replace('/change-password')` — no `/auth/me` call in chain. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `dependencies.py` | `request.url.path` allowlist | `frozenset` membership raising 403 | VERIFIED | Exact-match frozenset, no prefix/case tricks. Detail shape `{"reason": "password_change_required"}` matches test assertion. |
| `router.py change_password_endpoint` | `audit_logs` + `issue_tokens` | `audit()` then `db.commit()` then `issue_tokens()` | VERIFIED | Ordering verified by reading lines 238-246. AUDIT-01 invariant preserved. |
| `service.py issue_tokens` | `UserInfo.must_change_password` | reads `user.must_change_password` at line 91 | VERIFIED | Login response now carries the live DB flag value. Previously NOT_WIRED; fixed in db20589. |
| `service.py` | `create_access_token must_change_password kwarg` | reads `user.must_change_password` | VERIFIED | Both `issue_tokens` (line 72) and `refresh_access_token` (line 119) pass the current DB value. |
| `auth.tsx storeTokens` | `setUser(data.user)` with flag | `data.user.must_change_password` from login response | VERIFIED | Line 162: `if (data.user) setUser(data.user)`. `data.user` is `UserInfo` which now carries the flag. |
| `auth.tsx redirect gate` | `/change-password` | `router.replace` on `user?.must_change_password` | VERIFIED | `useEffect` at lines 123-127 dep array includes `user` — fires when `setUser(data.user)` delivers a flagged user on the SPA login path. Previously PARTIAL (hard-reload only); fully wired after db20589. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `auth.tsx AuthProvider` | `user.must_change_password` | `storeTokens(data)` -> `data.user` from `/auth/login` response (`UserInfo`) OR `fetchMe()` -> `GET /auth/me` -> `CurrentUser` | Yes — both paths now carry the live DB flag | FLOWING on both paths. Primary SPA login path fixed in db20589: `UserInfo` now includes the flag so `storeTokens -> setUser` arms the gate without a reload. |
| `change-password/page.tsx` | `access_token` / `refresh_token` | `POST /auth/change-password` -> `TokenResponse` | Yes (flag-free `issue_tokens`) | FLOWING — fresh tokens are stored in `localStorage` before redirect. |
| `dependencies.py` gate | `current_user.must_change_password` | JWT claim decoded via `decode_token` | Yes (from `create_access_token` kwarg) | FLOWING — claim round-trips correctly through `issue_tokens` -> JWT -> `decode_token`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| JWT claim round-trip | `pytest tests/test_admin_hardening.py::test_jwt_claim_round_trip` | PASSED | PASS |
| Enforcement gate blocks flagged user | `pytest tests/test_admin_hardening.py::test_enforcement_blocks` | PASSED (with valid Fernet key + running Postgres) | PASS |
| Rotation clears flag + audit | `pytest tests/test_admin_hardening.py::test_rotation_audit_event` | PASSED | PASS |
| `issue_tokens` carries flag in UserInfo | `pytest tests/test_auth.py::TestLoginResponseFlag` | PASSED — both cases exercised, no DB required | PASS |
| Frontend redirect gate — hard-reload path | `npm run test -- change-password` (case 1: stored token + mock /auth/me) | PASSED | PASS |
| Frontend redirect gate — SPA login path (no reload) | `npm run test -- change-password` (case 2: no stored token, mock /auth/login response) | PASSED — regression added in db20589, directly exercises SC#4 fix | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|------------|------------|-------------|--------|---------|
| PROD-06-01 | Plan 01 | `must_change_password` column + ORM + seed | SATISFIED | Migration 029 exists, ORM column exists, `create_admin.py` seeds `true`. |
| PROD-06-02 | Plan 02 | Auth flow enforces password change before non-allowlisted calls | SATISFIED | `get_current_user` gate with `MUST_CHANGE_PASSWORD_ALLOWLIST`. 5 enforcement tests pass. |
| PROD-06-03 | Plan 03 | Login UI surfaces forced-rotation and routes to change-password — on the primary SPA login path | SATISFIED | `UserInfo` now carries `must_change_password`. `storeTokens -> setUser -> useEffect gate -> router.replace('/change-password')` chain verified. Vitest regression case confirms no-reload path. Previously PARTIALLY SATISFIED; fully satisfied after db20589. |
| PROD-06-04 | Plan 02 | Audit event on first-login rotation | SATISFIED | `auth.first_login_rotation` emitted before `db.commit()` in `change_password_endpoint`. `test_rotation_audit_event` passes. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/create_admin.py` | 13-17 | Existence check counts `users WHERE password_hash IS NOT NULL` across all tenants (WR-04) | Warning | In a multi-tenant deployment where any tenant already has a password user, the default admin seed is skipped; no blocker for single-tenant installs. |
| `frontend/src/app/change-password/page.tsx` | 91 | `body?.detail` passed to `setFormError` without string coercion (WR-03) | Warning | If FastAPI returns a structured `detail` object, React throws "Objects are not valid as a React child". |
| `backend/app/auth/router.py` | 216-217 | `Admin123!` literal reject only blocks the exact string (WR-05) | Warning | Near-identical variants (trailing space, `Admin1234!`) still accepted. |

No blockers. All anti-patterns are pre-existing warnings that do not prevent the phase goal — the forced-rotation mechanism is fully in place.

### Human Verification Required

None. The previously human-only item ("Primary SPA Login -> Force-Rotation Redirect") is now covered by the Vitest regression test added in db20589: "redirect gate fires after a fresh SPA login (no reload)" exercises the exact `login() -> storeTokens -> setUser -> useEffect gate -> router.replace('/change-password')` chain without a hard reload or `/auth/me` call.

### Gaps Summary

No gaps. All 5 success criteria are now verified.

SC#4 is closed. The login-response data-flow is complete: the backend populates `UserInfo.must_change_password` from the DB in `issue_tokens()`, the schema carries it to the frontend, `storeTokens` sets user state with the live flag, and the `AuthProvider` force-rotation `useEffect` fires on the same render cycle — routing the flagged admin to `/change-password` without any reload or secondary `/auth/me` call. The backend 403 gate (SC#3) remains the authoritative enforcement layer; the frontend redirect is the UX enforcement.

---

_Verified: 2026-07-09T15:00:00Z_
_Re-verification after commit db205894a2dfcdc81dad3062b21c1995c9bf9c60_
_Verifier: Claude (gsd-verifier)_
