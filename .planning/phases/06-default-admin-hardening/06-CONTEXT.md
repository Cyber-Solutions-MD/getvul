# Phase 6: Default Admin Hardening - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Force the seeded default admin (`admin@getvul.local` / `Admin123!`, created by `create_admin.py`) through a password rotation before it can use the app. Deliver: a `must_change_password` flag on `users`, seeding that sets it, backend enforcement that blocks the app until it's cleared, a `/auth/me` surface for the flag, a frontend force-rotation page, and an audit event on rotation.

**In scope:** the 5 ROADMAP success criteria (migration, seed flag, 403 enforcement, frontend force-rotation, clear-flag-on-success + audit).
**Out of scope (new capabilities → other phases):** org-wide password-expiry policy, scheduled forced rotations, admin UI to flag arbitrary users, SSO/directory users (they have no `password_hash`).
</domain>

<decisions>
## Implementation Decisions

### Data model & seeding
- **D-01:** Add a `must_change_password` boolean column to `users` (Python default `False`, `server_default="false"`, non-null) via a new Alembic migration. (SC#1, PROD-06-01)
- **D-02:** `backend/create_admin.py` sets `must_change_password = true` on the seeded `OWNER` admin row. The mechanism is generic (D-15) — the seed script is just the first setter. (SC#2, PROD-06-01)

### Flag propagation (enforcement source) — JWT claim
- **D-03:** `must_change_password` travels as a **JWT access-token claim**, populated at login time by `issue_tokens()` from the user's DB flag. Enforcement reads the claim — **zero extra DB queries on the hot path**. Rationale: the flag only matters at login, and forced rotation happens immediately, so a token-carried value is authoritative for the session.
- **D-04:** Add `must_change_password` to the `CurrentUser` schema (`backend/app/auth/schemas.py`), populated from the JWT claim in `get_current_user`. `/auth/me` returns it with **no DB read** — this is how the frontend reads the flag. (SC#4)
- **D-05 (accepted edge case):** Because the flag lives in the token, a DB-side flag change mid-session only takes effect on next login/refresh. Acceptable for first-login rotation. The "hybrid: JWT claim + `/me` DB read" option was considered and **rejected** to keep the hot path DB-free.

### Enforcement mechanism — dependency + allowlist
- **D-06:** Enforce in the **auth dependency layer** (in/around `get_current_user`), not middleware. When the claim is set, raise **HTTP 403** with a machine-readable JSON body `{"reason": "password_change_required"}` for every request whose path is NOT on the allowlist. (SC#3, PROD-06-02)
- **D-07:** Allowlist while flagged: **`/auth/change-password`, `/auth/me`, `/auth/logout`, `/auth/refresh`**. Rationale: the frontend must call `/me` to learn the reason, rotate the password, refresh, and sign out — all while otherwise blocked.
- **D-08:** The reason string is **exactly** `password_change_required` (SC#3 wording), returned in the response body so the frontend branches on it deterministically (not by parsing prose).

### Rotation completion (backend)
- **D-09:** Reuse the existing `/auth/change-password` endpoint + `change_password()` helper (`backend/app/auth/password.py`). When the caller's flag was set, on success: (a) clear `users.must_change_password` in the DB, (b) emit an `auth.first_login_rotation` audit event via the `audit(db, cu, action, entity, id, meta)` helper, and (c) re-issue fresh access+refresh tokens **without** the flag claim so the user is immediately unblocked. (SC#5, PROD-06-04)
- **D-10:** New-password validation reuses the existing `change_password()` rules, including `password_history` reuse-prevention. (See Claude's Discretion for the `Admin123!`-specific reject.)

### Frontend force-rotation — dedicated blocking route
- **D-11:** A dedicated blocking route **`/change-password`**, placed OUTSIDE the `(authed)` route group (like `/login`), built on the sunset design system + Phase 9 primitives (`Form` = react-hook-form+zod, `Input` with password eye-toggle, `Button` with `loading`, `ErrorAlert`).
- **D-12:** Detection + redirect: after login (or when `useAuth()` sees `must_change_password` from `/auth/me`), the auth layer `router.replace('/change-password')`. The page is inescapable while flagged — any nav to a protected route 403s (`password_change_required`) and bounces back. On success (fresh flag-free tokens) → redirect to `/dashboard`, honoring a sanitized `?next` per Phase 9 D-50.
- **D-13:** Copy follows `copy-voice.md` — direct, no "Please…"/"Welcome!". State plainly *why* rotation is required (the account still uses default install credentials). Cover states: submitting (loading), error (wrong current password, weak/reused new password → `ErrorAlert` + field messages per Phase 9 D-28), success.
- **D-14:** Extend the frontend `User` interface + `/auth/me` consumer in `frontend/src/lib/auth.tsx` to carry `must_change_password`, and have `useAuth()` expose it for the redirect gate.

### Generality
- **D-15:** Enforcement honors `must_change_password` on **any** user, not just the seeded admin. `create_admin.py` merely happens to set it. Same effort, durable for future reuse (admin-provisioned users, forced resets). Matches PROD-06-01 wording.

### Claude's Discretion
- Alembic migration filename/revision wiring (follow existing `backend/alembic/versions/` conventions).
- Whether to additionally hard-reject the literal default `Admin123!` as the *new* password (belt-and-suspenders) vs relying solely on `password_history`.
- Exact token re-issue plumbing (reuse `issue_tokens()`; whether the endpoint returns tokens in the body or the frontend calls `/auth/refresh`).
- Whether the enforcement allowlist is a path constant shared between the dependency and tests.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase spec & requirements
- `.planning/ROADMAP.md` §"Phase 6: Default Admin Hardening" — the 5 success criteria (the scope anchor)
- `.planning/REQUIREMENTS.md` §"Default Admin Hardening (PROD-06)" — PROD-06-01..04

### Backend integration points
- `backend/create_admin.py` — seed script; sets the flag (D-02)
- `backend/app/auth/dependencies.py` §`get_current_user` (line ~22), `require_role` — where enforcement + claim-read wire in (D-04, D-06)
- `backend/app/auth/router.py` §`/auth/me` (line ~127), §`/auth/change-password` (line ~194), §`/auth/login` — endpoints touched (D-04, D-09)
- `backend/app/auth/password.py` §`change_password` (line ~183) — reused rotation helper + validation (D-09, D-10)
- `backend/app/auth/schemas.py` §`CurrentUser` (line ~10) — add `must_change_password` (D-04)
- `backend/app/tenants/models.py` §`User` (line ~49) — add the column (D-01)
- `backend/app/audit.py` — `audit(db, cu, action, entity, id, meta)` helper for `auth.first_login_rotation` (D-09)
- JWT issue/decode: locate `issue_tokens` + `decode_token`/token payload schema (used by D-03) — in `backend/app/auth/` (jwt/token module)

### Frontend integration points
- `frontend/src/lib/auth.tsx` — `User` interface, `useAuth()`, `me`/`refresh`/`login`, redirect gate (D-12, D-14)
- `frontend/src/app/login/page.tsx` — owns post-success redirect; pattern to mirror (D-12)
- `frontend/src/app/login/sanitize-next.ts` — `?next` open-redirect guard to reuse (D-12)
- `frontend/src/app/(authed)/layout.tsx` — the route group `/change-password` sits OUTSIDE (D-11)
- `.planning/phases/09-login-foundation/09-CONTEXT.md` — primitive + routing decisions (Form/Input/Button/ErrorAlert, `(authed)` group, `/login` redirect ownership, D-28 error styling, D-50 next-param)

### Design system (MANDATORY for the frontend page)
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — tone/microcopy (D-13)
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — loading/empty/error (mandatory)
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — tokens
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — layout patterns
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `change_password()` helper + `/auth/change-password` endpoint already exist — extend, don't rebuild (D-09).
- `password_history` column on `User` already prevents password reuse (D-10).
- Phase 9 primitives (`Form`, `Input` w/ password toggle, `Button` loading, `ErrorAlert`) cover the whole rotation form (D-11).
- `audit()` helper is the established audit pattern (Phase 5) — reuse for `auth.first_login_rotation`.

### Established Patterns
- `CurrentUser` is JWT-derived (no DB on the hot path) — the JWT-claim approach (D-03) preserves that.
- `(authed)` route group + `AppShell`; `/login` (and now `/change-password`) live outside it (D-11).
- `/login` owns its post-success `router.replace` with a sanitized `?next` (Phase 9 D-50) — the rotation page mirrors this (D-12).

### Integration Points
- `get_current_user` (`dependencies.py`) — claim read + 403 enforcement gate (D-04, D-06).
- `/auth/me` (`router.py`) — surfaces the flag from the claim (D-04).
- `create_admin.py` — sets the flag on seed (D-02).
- `auth.tsx` `User` interface + `useAuth()` — frontend flag consumer + redirect gate (D-12, D-14).
</code_context>

<specifics>
## Specific Ideas

No specific external references beyond the decisions above. The 403 reason string `password_change_required` and the audit action `auth.first_login_rotation` are fixed by the ROADMAP success criteria and must match verbatim.
</specifics>

<deferred>
## Deferred Ideas

- Org-wide password-expiry / periodic forced-rotation policy — a new capability, its own phase.
- Admin UI to flag arbitrary users for forced rotation — future; the generic flag (D-15) leaves the door open but no UI is in scope here.
- SSO/directory users have no `password_hash`; forced password rotation is meaningless for them and is out of scope. If forced re-consent/re-auth for SSO is ever wanted, that's a separate phase.

None of these block Phase 6 — discussion stayed within scope; these are noted so they aren't lost.
</deferred>

---

*Phase: 06-default-admin-hardening*
*Context gathered: 2026-07-08*
