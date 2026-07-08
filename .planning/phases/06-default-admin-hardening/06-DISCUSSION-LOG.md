# Phase 6: Default Admin Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-08
**Phase:** 06-default-admin-hardening
**Areas discussed:** Flag source, Enforcement mechanism, Rotation UX, Generality

---

## Flag source (how `must_change_password` reaches request-time enforcement)

| Option | Description | Selected |
|--------|-------------|----------|
| JWT claim | Flag set as a JWT claim at login; enforcement reads the token, zero extra DB queries; rotation re-issues flag-free tokens. | ✓ |
| DB lookup per request | New dependency queries `users.must_change_password` on every request — always fresh, adds a DB round-trip to the hot path. | |
| Hybrid: claim + /me DB read | Flag in JWT for enforcement, but `/auth/me` does a DB read for frontend truth. | |

**User's choice:** JWT claim
**Notes:** Grounded in the finding that `CurrentUser` is JWT-derived today with no DB read on the hot path. `/auth/me` will surface the flag straight from the claim (satisfies SC#4 without a DB read). Accepted edge case: DB-side flag changes only take effect on next login/refresh — fine for first-login rotation.

---

## Enforcement mechanism (wiring + allowlist while flagged)

| Option | Description | Selected |
|--------|-------------|----------|
| Dependency + allowlist | Gate in/around `get_current_user`; 403 `password_change_required` unless path allowlisted (`/auth/change-password`, `/auth/me`, `/auth/logout`, `/auth/refresh`). | ✓ |
| Global middleware | ASGI/HTTP middleware checks the flag before routing; must re-decode JWT + duplicate the allowlist outside the dependency graph. | |
| Minimal allowlist | Only `/auth/change-password` reachable; frontend can't call `/me` to learn the reason. | |

**User's choice:** Dependency + allowlist
**Notes:** Allowlist deliberately includes `/auth/me` (frontend reads the reason + flag), `/auth/logout`, and `/auth/refresh` so the blocked user can still detect state, rotate, refresh, and sign out.

---

## Rotation UX (frontend force-rotation form)

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated /change-password route | Blocking full page outside `(authed)`, sunset design system + Phase 9 primitives; auth layer `router.replace`s here; inescapable until success. | ✓ |
| Blocking modal over app shell | Non-dismissable modal over the shell; but the app is JWT-blocked so the shell shows empty/errored data. | |
| Reuse /login split-screen | Render the rotation form inside the existing `/login` layout as a variant. | |

**User's choice:** Dedicated /change-password route
**Notes:** Consistent with Phase 9 routing (`/login` lives outside `(authed)` and owns its redirect). On success → `/dashboard` honoring sanitized `?next` (Phase 9 D-50). Copy per `copy-voice.md`.

---

## Generality (scope of the plumbing)

| Option | Description | Selected |
|--------|-------------|----------|
| Generic flag-driven | Enforcement honors `must_change_password` on ANY user; `create_admin.py` just sets it. Durable for future reuse. | ✓ |
| Scoped to seeded admin only | Special-case the seeded local admin; flag is dead weight otherwise. | |

**User's choice:** Generic flag-driven
**Notes:** Matches PROD-06-01 wording; same implementation effort, more durable.

## Claude's Discretion

- Alembic migration filename/revision wiring.
- Whether to additionally hard-reject the literal `Admin123!` as the new password vs relying on `password_history`.
- Token re-issue plumbing details (reuse `issue_tokens`; body vs `/auth/refresh`).
- Whether the allowlist is a shared path constant between dependency and tests.

## Deferred Ideas

- Org-wide password-expiry / scheduled forced-rotation policy — own phase.
- Admin UI to flag arbitrary users for rotation — future.
- SSO/directory users (no `password_hash`) — out of scope.
