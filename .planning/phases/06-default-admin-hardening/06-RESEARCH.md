# Phase 6: Default Admin Hardening — Research

**Researched:** 2026-07-08
**Domain:** FastAPI auth layer (JWT, dependency injection, Alembic migration) + Next.js 15 App Router frontend page
**Confidence:** HIGH (all integration points verified against live code)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Add `must_change_password` boolean column to `users` (Python default `False`, `server_default="false"`, non-null) via a new Alembic migration.
- **D-02:** `backend/create_admin.py` sets `must_change_password = true` on the seeded OWNER admin row.
- **D-03:** `must_change_password` travels as a JWT access-token claim, populated at login time by `issue_tokens()` from the user's DB flag. Enforcement reads the claim — zero extra DB queries on the hot path.
- **D-04:** Add `must_change_password` to the `CurrentUser` schema, populated from the JWT claim in `get_current_user`. `/auth/me` returns it with no DB read.
- **D-05 (accepted edge case):** DB-side flag change mid-session only takes effect on next login/refresh. Acceptable for first-login rotation. Hybrid JWT+DB option rejected.
- **D-06:** Enforce in the auth dependency layer (in/around `get_current_user`). When the claim is set, raise HTTP 403 with `{"reason": "password_change_required"}` for every path NOT on the allowlist.
- **D-07:** Allowlist while flagged: `/auth/change-password`, `/auth/me`, `/auth/logout`, `/auth/refresh`.
- **D-08:** Reason string is exactly `password_change_required`.
- **D-09:** Reuse existing `/auth/change-password` endpoint + `change_password()` helper. On success when flag was set: (a) clear `users.must_change_password` in DB, (b) emit `auth.first_login_rotation` audit event, (c) re-issue fresh tokens without the flag claim.
- **D-10:** New-password validation reuses existing `change_password()` rules, including `password_history` reuse-prevention.
- **D-11:** Dedicated blocking route `/change-password`, placed OUTSIDE `(authed)` route group, built on sunset design system + Phase 9 primitives.
- **D-12:** After login (or when `useAuth()` sees `must_change_password`), `router.replace('/change-password')`. On success → `/dashboard` honoring sanitized `?next` per Phase 9 D-50.
- **D-13:** Copy follows `copy-voice.md` — direct, no "Please…"/"Welcome!". State plainly why rotation is required. Cover states: submitting (loading), error, success.
- **D-14:** Extend frontend `User` interface + `/auth/me` consumer in `frontend/src/lib/auth.tsx` to carry `must_change_password`, expose via `useAuth()`.
- **D-15:** Enforcement honors `must_change_password` on any user, not just the seeded admin.

### Claude's Discretion

- Alembic migration filename/revision wiring (follow existing `backend/alembic/versions/` conventions).
- Whether to additionally hard-reject the literal default `Admin123!` as the new password vs relying solely on `password_history`.
- Exact token re-issue plumbing (reuse `issue_tokens()`; whether endpoint returns tokens in body or frontend calls `/auth/refresh`).
- Whether the enforcement allowlist is a path constant shared between the dependency and tests.

### Deferred Ideas (OUT OF SCOPE)

- Org-wide password-expiry / periodic forced-rotation policy.
- Admin UI to flag arbitrary users for forced rotation.
- SSO/directory users forced rotation (no `password_hash`; meaningless for them).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-06-01 | New users with the OWNER role created by `create_admin.py` are flagged `must_change_password` on first login | D-01 migration + D-02 seed script change verified against `create_admin.py` and `User` model |
| PROD-06-02 | Auth flow enforces password change before any non-`/auth/change-password` call succeeds when flag is set | D-06 dependency gate verified: `get_current_user` has the right shape; see §Critical Finding 1 |
| PROD-06-03 | Login UI surfaces a forced-rotation banner and routes to change-password | D-11/D-12/D-14 verified: `User` interface + `useAuth()` + `/auth/me` response shape; page doesn't exist yet |
| PROD-06-04 | Audit event recorded on first-login rotation (`auth.first_login_rotation`) | D-09 verified: `audit()` signature confirmed; `audit_logs` table confirmed |
</phase_requirements>

---

## Summary

Phase 6 delivers a forced password-rotation gate for the seeded default admin. The approach is entirely additive: one new Alembic migration, two small backend mutations (JWT payload + dependency gate), one new frontend page, and extensions to three existing files. No existing endpoint contracts change shape; the new behavior is a superset.

The most critical implementation detail is the `get_current_user` dependency's lack of `Request` injection. Verified live: the current signature is `(credentials, db)` — no `Request`. Enforcing path-based allowlist logic from inside `get_current_user` therefore requires either adding `Request` as an explicit FastAPI dependency (FastAPI will inject it via DI without problem — it is a first-class injectable), or extracting the flag check into a separate callable dependency layered on top of `get_current_user`. Both approaches are viable; adding `Request` to `get_current_user` is the lower-ceremony option.

The token pipeline is similarly clear-cut: `create_access_token()` builds its payload dict directly; adding `must_change_password` is a one-line dict key addition. `decode_token()` returns a `TokenPayload` object constructed from the raw dict; adding the new attribute there, and threading it through `CurrentUser`, closes the round-trip.

**Primary recommendation:** implement in three independent layers — (1) migration + model, (2) JWT round-trip + dependency enforcement, (3) frontend page — each testable in isolation before the next begins.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `must_change_password` persistence | Database / Storage | — | Boolean column on `users`; Alembic-managed |
| Flag population at login | API / Backend | — | `issue_tokens()` reads DB row, encodes claim |
| Flag enforcement (403 gate) | API / Backend | — | FastAPI dependency; enforces before any route handler runs |
| Flag surface to frontend | API / Backend | — | `/auth/me` returns `CurrentUser` which includes the claim |
| Flag propagation in UI | Frontend Server (SSR) | Browser / Client | `useAuth()` + `User` interface; redirect gate runs client-side |
| Force-rotation page | Browser / Client | — | Dedicated `/change-password` Next.js page outside `(authed)` group |
| Audit trail | Database / Storage | API / Backend | `audit()` helper writes to `audit_logs` table |

---

## Standard Stack

All libraries are already installed. No new dependencies needed.

### Core (Backend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-jose | installed | JWT encode/decode — `create_access_token`, `decode_token` | Already wired in `app/auth/jwt.py` |
| SQLAlchemy (async) | installed | ORM + `Boolean` column | All models use it |
| Alembic | installed | Database migration | 028 migrations already exist; conventions established |
| FastAPI | installed | Dependency injection for enforcement gate | `get_current_user` is already a FastAPI `Depends` |

### Core (Frontend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-hook-form | installed | Form state for change-password form | Phase 9 D-21 pattern; used in `login/page.tsx` |
| zod | installed | Schema validation | Same as login form |
| @hookform/resolvers | installed | react-hook-form ↔ zod bridge | Same as login form |
| Next.js 15 App Router | installed | `/change-password` page routing | Project standard |

### Supporting
None new — Phase 9 primitives (`Form`, `Input`, `Button`, `ErrorAlert`) are already in `frontend/src/components/`.

---

## Critical Integration-Point Findings

### Finding 1: `get_current_user` does NOT currently receive `Request` [VERIFIED: live code]

**File:** `backend/app/auth/dependencies.py`, lines 22–25

Current signature:
```python
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
```

`Request` is **not injected**. To gate on `request.url.path` from inside this dependency, the planner must add `Request` as a third parameter. FastAPI treats `Request` as a special first-class injectable — adding it does not require a `Depends()` wrapper:

```python
from fastapi import Request

async def get_current_user(
    request: Request,
    credentials: Annotated[...],
    db: Annotated[...],
) -> CurrentUser:
```

This is the single highest-impact integration risk for the enforcement gate (D-06/D-07). If `Request` is not added, the path-allowlist check has no way to read the URL.

### Finding 2: JWT token payload is a plain dict — one-line addition [VERIFIED: live code]

**File:** `backend/app/auth/jwt.py`, lines 35–56

`create_access_token` builds the payload as a literal dict. Adding `must_change_password` is trivially:
```python
payload = {
    "sub": user_id,
    "tenant_id": tenant_id,
    "email": email,
    "role": role,
    "must_change_password": must_change_password,  # ADD
    "type": "access",
    ...
}
```

`decode_token` constructs `TokenPayload` manually from `payload.get(...)` calls. The new field needs a corresponding attribute on `TokenPayload` and a `.get("must_change_password", False)` extraction.

**IMPORTANT: `create_access_token` signature must gain a `must_change_password: bool = False` parameter.** All existing callers pass positional args for `user_id`, `tenant_id`, `email`, `role`. The new kwarg with a default keeps them unbroken.

### Finding 3: `issue_tokens()` in `service.py` does not yet read `must_change_password` [VERIFIED: live code]

**File:** `backend/app/auth/service.py`, lines 65–91

`issue_tokens(user: User, tenant: Tenant) -> TokenResponse` calls `create_access_token(user_id=..., tenant_id=..., email=..., role=...)`. For D-03, this becomes:
```python
access_token = create_access_token(
    user_id=str(user.id),
    tenant_id=str(user.tenant_id),
    email=user.email,
    role=...,
    must_change_password=user.must_change_password,  # ADD
)
```

`user.must_change_password` requires the column to exist — i.e., migration must run before any code path calling `issue_tokens` with a flagged user.

**`refresh_access_token()` also calls `create_access_token` (lines 112–116).** It currently re-reads `role` from DB on every refresh. For D-03/D-05: the refresh path also needs to carry `must_change_password`. Since the refresh handler already does a DB lookup (`select(User).where(User.id == ...)`), it has the current `user` object and can read `user.must_change_password` at refresh time. **This means token replay after rotation IS handled via the refresh path** — if the user refreshes after the flag is cleared, the new access token will NOT carry the flag. The accepted D-05 edge case (mid-session old token stays flagged until expiry) is limited to the 15-minute access-token window.

### Finding 4: `CurrentUser` schema needs `must_change_password` [VERIFIED: live code]

**File:** `backend/app/auth/schemas.py`, lines 10–16

Current schema:
```python
class CurrentUser(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str
```

Add: `must_change_password: bool = False`

`get_current_user` in `dependencies.py` constructs `CurrentUser(id=..., tenant_id=..., email=..., role=...)` from the decoded token payload (line 64). For D-04, add `must_change_password=payload.must_change_password`.

**One known construction site that would produce a flagless `CurrentUser` in the dev-token path** (lines 44–49): the dev-token shortcut builds `CurrentUser` without `must_change_password`. It reads the DB user, so it can include the column value once it exists.

### Finding 5: `/auth/change-password` endpoint currently commits without audit and does not re-issue tokens [VERIFIED: live code]

**File:** `backend/app/auth/router.py`, lines 194–212

Current behavior:
1. Calls `change_password(db, user.id, current_password, new_password)` — returns `{"message": "Password updated"}` on success
2. `await db.commit()` — no audit
3. Returns `result` (the `{"message": ...}` dict)

For D-09, the endpoint needs to:
1. Know whether `user.must_change_password` was set BEFORE calling `change_password()` — read `user.must_change_password` from the current token claim (already on `CurrentUser` after D-04)
2. Call `change_password()` as before
3. On success AND if flag was set: (a) write `users.must_change_password = False` + flush, (b) emit `audit(db, user, "auth.first_login_rotation", "user", str(user.id), {...})`, (c) `await db.commit()`, (d) return fresh tokens via `issue_tokens()`
4. On success AND flag was NOT set: existing path — just `{"message": "Password updated"}`

**Sequence matters:** `db.commit()` must happen AFTER the audit row is added (fail-closed per `AUDIT-01` comment in `audit.py`).

### Finding 6: `change_password()` helper does NOT currently clear the flag [VERIFIED: live code]

**File:** `backend/app/auth/password.py`, lines 183–225

`change_password()` only updates `password_hash` and `password_history`. It does NOT touch `must_change_password`. The flag clearing logic must live in the endpoint handler (D-09), not in the helper — consistent with D-09's design: "on success, clear the DB column."

**Signature:** `async def change_password(db, user_id, current_password, new_password) -> dict`

Returns `{"error": "..."}` on failure, `{"message": "Password updated"}` on success. Endpoint checks `"error" in result` to short-circuit.

### Finding 7: `audit()` signature confirmed [VERIFIED: live code]

**File:** `backend/app/audit.py`, line 129

```python
async def audit(
    db: AsyncSession,
    user: CurrentUser | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
```

For D-09: `await audit(db, user, "auth.first_login_rotation", "user", str(user.id), {"email": user.email})`

Note: the `audit()` function adds a row but does NOT commit — the caller commits. Pattern in `router.py`: `await audit(...); await db.commit()`. This is the required order (fail-closed per AUDIT-01).

### Finding 8: Alembic conventions [VERIFIED: live code]

- **Head revision (current):** `028_add_ticket_watchers`
- **Naming convention:** `NNN_short_description.py` (three-digit zero-padded number)
- **Next migration:** `029_add_must_change_password.py`
- **Fields required:** `revision = "029_add_must_change_password"`, `down_revision = "028_add_ticket_watchers"`, `branch_labels = None`, `depends_on = None`
- **Column-add pattern** (from `011_add_password_auth.py`): `op.add_column("users", sa.Column("must_change_password", sa.Boolean(), server_default="false", nullable=False))`
- No autogenerate workflow; migrations are hand-written.

### Finding 9: `create_admin.py` uses raw SQL — must include the new column [VERIFIED: live code]

**File:** `backend/create_admin.py`, lines 42–44

The INSERT is a hand-written SQL string that lists explicit columns:
```python
"INSERT INTO users (id, tenant_id, email, display_name, role, password_hash, is_active, idp_subject, idp_source) "
"VALUES (gen_random_uuid(), :tid, 'admin@getvul.local', 'Admin', 'OWNER', :pw, true, 'local-admin', 'local')"
```

Because `must_change_password` has a `server_default="false"`, the INSERT will succeed without listing it — the DB will write `false`. For D-02, the INSERT must be updated to explicitly set `must_change_password = true`. Either add the column name + a `:mcp` placeholder, or append a follow-up `UPDATE`.

The simpler fix: add `must_change_password` to the column list and `true` to the values list. This is robust even if the server_default is later changed.

### Finding 10: Frontend `User` interface and `useAuth()` [VERIFIED: live code]

**File:** `frontend/src/lib/auth.tsx`

Current `User` interface (lines 15–23) does NOT include `must_change_password`. For D-14, add:
```typescript
interface User {
  ...
  must_change_password?: boolean;
}
```

`fetchMe()` at line 110 returns the raw `/auth/me` JSON — once the backend returns `must_change_password`, it will automatically land on the `User` object and be exposed via `useAuth().user.must_change_password`.

The `AuthState` interface (lines 38–48) exposes `user: User | null`. Consumers read `user.must_change_password` directly — no change to `AuthState` needed (the field is on `User`).

**The redirect gate** (lines 101–108) currently only guards `isProtectedPath(pathname)` (i.e., `/dashboard/*`). For D-12, a second `useEffect` (or condition in the existing one) must catch `user.must_change_password === true` and `router.replace('/change-password')` from any protected path.

**`storeTokens()`** at line 139 calls `if (data.user) setUser(data.user)`. This path sets the `User` from the login response body. The login response (`TokenResponse`) currently includes `user: UserInfo` — but `UserInfo` in `schemas.py` does NOT include `must_change_password`. However, since D-04 says the frontend reads the flag from `/auth/me` (not from the login response body), `UserInfo` does not need to change — `fetchMe()` is the source of truth for the flag.

**Important: After login (`storeTokens`), the flag will NOT yet be on `user` because `storeTokens` sets user from `data.user` (which is `UserInfo`, no flag). The `useEffect` that calls `fetchMe()` on mount (lines 77–96) will pick it up on next mount. This means the redirect from `/login` → `/change-password` fires after the post-login `fetchMe` resolves, NOT immediately after `storeTokens`.** The planner needs to account for this flow: `login()` call → `storeTokens()` → `LoginForm.onSubmit` calls `router.replace(dest)` → mount of `dest` triggers `AuthProvider.useEffect` → `fetchMe()` reads `must_change_password` → redirect gate fires `router.replace('/change-password')`. This is an existing navigation pattern consistent with how the login-time `user` guard works.

Alternatively: the `login()` callback in `auth.tsx` can be extended to call `fetchMe(newToken)` and set user before returning, so `must_change_password` is available synchronously after login. The planner should choose.

### Finding 11: `useChangePassword` hook already exists [VERIFIED: live code]

**File:** `frontend/src/lib/queries/use-tenant-users.ts`, lines 68–91

There is already a `useChangePassword()` TanStack mutation that calls `POST /auth/change-password`. It is used by `settings/profile-pane.tsx`. The `/change-password` page (D-11) should decide whether to reuse this hook or make a raw `fetch` call directly (for parity with how the login page handles its own API calls without TanStack). Given the page is outside `(authed)` and needs access to the raw response (fresh tokens), a raw `fetch` approach is cleaner — `useChangePassword` is a toast-wrapped mutation that discards the response body.

### Finding 12: No existing `/change-password` page [VERIFIED: live code]

`frontend/src/app/change-password/` does not exist. The page is purely new. The correct path is `frontend/src/app/change-password/page.tsx`. It lives outside `(authed)/` (no `AppShell`, no sidebar) — consistent with `frontend/src/app/login/page.tsx`.

---

## Architecture Patterns

### System Architecture Diagram

```
POST /auth/login
      │
      ▼
login_with_password()  ──reads──▶  users table
      │                            (must_change_password)
      ▼
issue_tokens(user, tenant)
      │
      ├─ create_access_token(... must_change_password=user.must_change_password)
      │         └─ JWT payload: { sub, tenant_id, email, role, must_change_password, type, ... }
      └─ TokenResponse { access_token, refresh_token, user: UserInfo }
                │
                ▼
          Frontend: storeTokens()
                │
                ▼
          fetchMe() → GET /auth/me
                │
                ▼
          get_current_user(request, credentials, db)
                │ decode_token() → TokenPayload.must_change_password
                └─ CurrentUser { id, tenant_id, email, role, must_change_password }
                │
                ├──[must_change_password == False]──▶ normal route handler
                │
                └──[must_change_password == True]──▶
                        │
                        ├── path in ALLOWLIST?
                        │         ├── YES → pass through
                        │         └── NO  → HTTP 403 { "reason": "password_change_required" }
                        │
                        └── useAuth() redirect gate
                                  └── router.replace('/change-password')

POST /auth/change-password
      │  [user.must_change_password from CurrentUser claim]
      ▼
change_password(db, user_id, current_password, new_password)
      │
      ├── [error] → return 400 { error }
      └── [success + flag was set]
              │
              ├── UPDATE users SET must_change_password=False WHERE id=user_id
              ├── audit(db, user, "auth.first_login_rotation", "user", str(user.id), {...})
              ├── await db.commit()
              └── issue_tokens(user, tenant)  → new flag-free TokenResponse
```

### Recommended Project Structure (new/changed files)

```
backend/
├── alembic/versions/
│   └── 029_add_must_change_password.py     # NEW migration
├── create_admin.py                          # MODIFY: add must_change_password=True to INSERT
└── app/auth/
    ├── jwt.py                               # MODIFY: TokenPayload + create_access_token
    ├── schemas.py                           # MODIFY: CurrentUser.must_change_password
    ├── service.py                           # MODIFY: issue_tokens + refresh_access_token
    ├── dependencies.py                      # MODIFY: get_current_user + Request + 403 gate
    └── router.py                            # MODIFY: change_password_endpoint
backend/app/tenants/models.py               # MODIFY: User.must_change_password column

frontend/src/
├── app/change-password/
│   └── page.tsx                             # NEW: force-rotation page
└── lib/auth.tsx                             # MODIFY: User interface + redirect gate
```

### Pattern 1: Alembic Column-Add (hand-written)

```python
# Source: verified from 011_add_password_auth.py and 016_add_password_policy.py
revision = "029_add_must_change_password"
down_revision = "028_add_ticket_watchers"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), server_default="false", nullable=False),
    )

def downgrade() -> None:
    op.drop_column("users", "must_change_password")
```

### Pattern 2: JWT Claim Round-Trip

```python
# create_access_token — add kwarg with default False
# Source: verified from backend/app/auth/jwt.py
def create_access_token(
    user_id: str,
    tenant_id: str,
    email: str,
    role: str,
    must_change_password: bool = False,
) -> str:
    payload = {
        ...existing keys...,
        "must_change_password": must_change_password,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

# TokenPayload — add attribute
class TokenPayload:
    def __init__(self, ..., must_change_password: bool = False):
        ...
        self.must_change_password = must_change_password

# decode_token — extract from payload dict
return TokenPayload(
    ...existing...,
    must_change_password=payload.get("must_change_password", False),
)
```

### Pattern 3: Enforcement Gate in `get_current_user`

```python
# Source: verified from backend/app/auth/dependencies.py + FastAPI docs [CITED: fastapi.tiangolo.com/tutorial/requests]
from fastapi import Request

MUST_CHANGE_PASSWORD_ALLOWLIST = frozenset({
    "/auth/change-password",
    "/auth/me",
    "/auth/logout",
    "/auth/refresh",
})

async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    ...
    current_user = CurrentUser(
        id=uuid.UUID(payload.sub),
        tenant_id=uuid.UUID(payload.tenant_id),
        email=payload.email,
        role=payload.role,
        must_change_password=payload.must_change_password,
    )
    # Enforce flag — check AFTER constructing CurrentUser (claim is the source)
    if current_user.must_change_password:
        path = request.url.path
        if path not in MUST_CHANGE_PASSWORD_ALLOWLIST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": "password_change_required"},
            )
    return current_user
```

**Note on path normalization:** The auth router is mounted at `/api/v1` in `main.py` (verify). The allowlist entries in D-07 are bare paths (`/auth/change-password`), but the actual request path will be `/api/v1/auth/change-password`. The enforcement logic must match correctly — either use `endswith()` or store allowlist as the full mounted path. Planner must verify the router mount prefix.

### Pattern 4: Frontend Redirect Gate Extension

```typescript
// Source: verified from frontend/src/lib/auth.tsx
// Add must_change_password to User interface
interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  role: string;
  tenant_id: string;
  tenant_name: string;
  must_change_password?: boolean;  // ADD
}

// Add second useEffect for force-rotation redirect
useEffect(() => {
  if (!loading && user?.must_change_password && pathname !== '/change-password') {
    router.replace('/change-password');
  }
}, [loading, user, pathname, router]);
```

### Anti-Patterns to Avoid

- **Checking the DB flag in `get_current_user` on every request:** This would add a DB query to the hot path. D-03 locks the JWT-claim approach specifically to avoid this.
- **Returning the `must_change_password` flag from the login response body `UserInfo`:** `UserInfo` schema is used by the callback and login endpoints. If changed, SSO login also sends it. The clean path is: flag is in the JWT, `/auth/me` surfaces it — not in `UserInfo`.
- **Putting the redirect gate in `(authed)/layout.tsx`:** The authed layout has no knowledge of `must_change_password`. The gate must be in `useAuth()` (AuthProvider), consistent with how the `/login` redirect works.
- **Committing before the audit row is added:** Per AUDIT-01 in `audit.py`, the pattern is always `await audit(...); await db.commit()` in that order — never `commit()` then `audit()`.
- **Forgetting `flag_modified()` for JSONB columns:** Not needed for `Boolean` columns, but `password_history` (JSONB) already uses `flag_modified(user, "password_history")` in `change_password()`. Do not add it for the new Boolean column.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password validation rules | Custom validator | `validate_password()` + `check_password_history()` in `password.py` | Already handles policy from tenant config + bcrypt history |
| Open-redirect protection | Custom URL checker | `sanitizeNext()` from `frontend/src/app/login/sanitize-next.ts` | Handles protocol-relative and path tricks; already tested |
| Form state management | Custom useState chain | `react-hook-form` + `zod` + shadcn `Form` compound | Phase 9 established pattern; used on login page |
| JWT encoding/decoding | Custom crypto | `python-jose` via `app/auth/jwt.py` | Already in use; consistent across all token operations |
| Audit logging | Custom audit table write | `audit()` from `app/audit.py` | Handles syslog, CEF, fail-closed semantics (AUDIT-01) |
| Password hashing | Any other method | `bcrypt` via `hash_password()` / `verify_password()` | Already in use; matches stored hashes |

**Key insight:** This phase is almost entirely wiring existing infrastructure — not building new components. The value is in the correctness of the wiring, not the novelty.

---

## Common Pitfalls

### Pitfall 1: Router mount prefix breaks the allowlist path match
**What goes wrong:** The enforcement gate checks `request.url.path` against `/auth/change-password`, but the actual request path is `/api/v1/auth/change-password` — so EVERY path is blocked including the allowlisted ones.
**Why it happens:** The auth router is mounted with a prefix in `main.py`. `request.url.path` returns the full path including the prefix.
**How to avoid:** Use `path.endswith(allowed)` for simple substring match, or store allowlist as the full mounted paths (e.g., `"/api/v1/auth/change-password"`). Verify the prefix in `main.py` before hardcoding.
**Warning signs:** All `/auth/*` calls return 403 with `password_change_required` even on a non-flagged user.

### Pitfall 2: Dev-token path in `get_current_user` doesn't set the new field
**What goes wrong:** The dev-token shortcut (lines 43–50 in `dependencies.py`) constructs `CurrentUser(id=..., email=..., role=...)` — it will silently get `must_change_password=False` after the field is added with a default. This is correct behavior, but if someone tests with dev-token and a flagged admin, enforcement won't fire.
**Why it happens:** Dev shortcut bypasses JWT decode; reads live user from DB but doesn't read `must_change_password` from the DB row.
**How to avoid:** Update the dev-token shortcut to include `must_change_password=user.must_change_password` (requires the column to exist after migration).

### Pitfall 3: Token replay window after flag clearance
**What goes wrong:** User rotates password. Flag is cleared in DB. Backend re-issues fresh flag-free tokens. But the OLD access token is still valid for up to 15 minutes (until expiry). If the user (or a different client) uses the OLD token, they get blocked.
**Why it happens:** D-05 accepted edge case applies in reverse too — clearing the flag mid-session doesn't revoke existing tokens.
**How to avoid:** The `/auth/change-password` endpoint returns new tokens (D-09c). The frontend must replace stored tokens with the fresh ones before navigating to `/dashboard`. Document this as an accepted limitation.
**Warning signs:** User rotates successfully but immediately gets redirected back to `/change-password` — old token still in localStorage.

### Pitfall 4: Missing `must_change_password` on `UserInfo` breaks `storeTokens` flow
**What goes wrong:** After login, `storeTokens(data)` sets `user = data.user` (which is `UserInfo`). `UserInfo` doesn't have `must_change_password`. The AuthProvider's redirect guard checks `user.must_change_password` — it reads `undefined`, which is falsy. User is never redirected to `/change-password`.
**Why it happens:** There are two `User` representations: the backend `UserInfo` (in login response body) and the `CurrentUser` from `/auth/me`. The flag is only on `CurrentUser`.
**How to avoid:** The flag detection in `useAuth()` must come from `/auth/me` (via `fetchMe()`), not from `storeTokens`. The mount-time `fetchMe()` call (lines 78–96) already updates `user` state — the redirect gate useEffect must run AFTER `fetchMe()` sets the user. Ensure the dependency array of the redirect-gate useEffect includes `user` (it already does in the existing pattern).
**Alternative:** Extend `storeTokens` to call `fetchMe()` synchronously and wait for it before returning.

### Pitfall 5: Allowlist in enforcement gate vs. tests — duplication drift
**What goes wrong:** The allowlist constant is defined inline in `dependencies.py`. Tests hardcode the same paths. When the allowlist changes, tests silently test the old paths.
**How to avoid:** Per Claude's Discretion, export the allowlist as a module-level constant from `dependencies.py` (e.g., `MUST_CHANGE_PASSWORD_ALLOWLIST`) and import it in tests. One source of truth.

### Pitfall 6: `change_password()` helper's `current_password` requirement
**What goes wrong:** The `change_password()` helper at lines 203–204 only verifies `current_password` when `user.password_hash and current_password and not verify_password(...)`. For the forced rotation case, the admin MUST provide their current password (`Admin123!`) to authenticate the rotation.
**Why it happens:** The helper's verification logic is: if `user.password_hash` exists and `current_password` was provided and it doesn't match → error. If `current_password` is None, verification is skipped.
**Impact:** This is the intended behavior. The force-rotation page must include a "current password" field so the admin proves they know `Admin123!` before setting a new one. The form schema must require `current_password`.

### Pitfall 7: SQLAlchemy ORM and the `must_change_password` column after migration
**What goes wrong:** `User` model in `models.py` does not yet have `must_change_password`. If code reads `user.must_change_password` before the model column is added, `AttributeError` is raised.
**How to avoid:** The Alembic migration (task 1) and the model change (also task 1) must ship together in the same wave. No code in task 2 (JWT/enforcement) should reference the column until task 1 is complete.

---

## Token Replay and Security Threat Model

| Threat | Vector | Mitigation |
|--------|--------|-----------|
| Old flagged access token used after rotation | Attacker/user has a cached token from before rotation | Accepted D-05 edge case — 15min window; endpoint returns fresh tokens; client must replace |
| Old UN-flagged refresh token used to get a new access token | User rotates but doesn't discard old refresh token | `refresh_access_token()` re-reads DB; if flag was set (e.g., by admin), new access token WILL carry the flag. Conversely, if flag was cleared, new access token will NOT carry it — correct behavior |
| Allowlist bypass via path traversal | `GET /api/v1/auth/change-password/../vulnerabilities` | FastAPI normalizes paths before routing; `request.url.path` returns the normalized path |
| SSO users hit the flag | SSO user with no `password_hash` gets flagged | D-15 scope is generic, but SSO users have `password_hash = None`. The `/auth/change-password` endpoint will error for them. Deferred per CONTEXT.md — keep `must_change_password` as `False` for SSO-created users by convention |
| Force-rotation page accessible without auth | `/change-password` outside `(authed)` group has no server-side auth check | Page must call `/auth/me` on mount to get the flag; if `/auth/me` returns 401 (no token), redirect to `/login`. The page is a UI gate, not a security boundary — the backend `change_password_endpoint` still validates the JWT |

---

## Design System Requirements (Frontend Page)

**Read mandatory skill files before implementing:**
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — CSS variables, never raw hex
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — loading/error/success states mandatory
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — tone rules
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — "Hero split-screen" pattern applies (unauthenticated surface, no sidebar)

**Layout:** `/change-password` is an unauthenticated surface (outside `(authed)`). Per `page-layouts.md`, the "Hero split-screen" pattern applies — but since the purpose is purely operational (not marketing), a simplified single-column centered form (like the form side of `/login`) is more appropriate than a full split-screen with product peek. The planner should decide: full split-screen (consistent visual grammar with `/login`) or slim centered form. The hero-split-screen pattern is the validated approach for this type of page.

**Copy (per `copy-voice.md`):**
- No "Please", no "Welcome", no "!"
- Heading: `Rotate your password` or `Set a new password` — sentence case, imperative
- Subheading: Direct statement of why — e.g., "This account was created with default install credentials. Set a new password before continuing."
- Submit button: `Update password` or `Set new password` — verb phrase
- Loading: `loadingText="Updating…"` on `<Button loading>`
- Field errors: specific (`Current password is incorrect`, `Cannot reuse a recent password`)
- Success: brief, no celebration — redirect immediately or show `Password updated` before navigating

**Phase 9 primitives confirmed present and verified:**

| Primitive | File | Key Props |
|-----------|------|-----------|
| `Form`, `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormMessage` | `components/ui/form.tsx` | shadcn compound; wraps react-hook-form Controller |
| `Input` | `components/ui/input.tsx` | `type="password"` auto-adds eye toggle; `type="text"|"email"|"password"|...` |
| `Button` | `components/ui/button.tsx` | `loading?: boolean`, `loadingText?: string`, `variant: "cta"|"secondary"|"ghost"|"icon"`, `size: "sm"|"md"|"lg"` |
| `ErrorAlert` | `components/auth/error-alert.tsx` | `children: ReactNode` — renders `role="alert"` banner in danger-soft |

**Import paths:**
```typescript
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form';
import { ErrorAlert } from '@/components/auth/error-alert';
```

---

## Code Examples

### Migration (029)
```python
# Source: verified pattern from 011_add_password_auth.py + 028_add_ticket_watchers.py
import sqlalchemy as sa
from alembic import op

revision = "029_add_must_change_password"
down_revision = "028_add_ticket_watchers"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), server_default="false", nullable=False),
    )

def downgrade() -> None:
    op.drop_column("users", "must_change_password")
```

### Model Column Addition
```python
# Source: verified from backend/app/tenants/models.py; follows existing Boolean column pattern
# Add after `password_history` on line ~65
must_change_password: Mapped[bool] = mapped_column(
    Boolean, default=False, server_default="false"
)
```

### Audit Call for Rotation
```python
# Source: verified from backend/app/audit.py + existing audit calls in router.py
await audit(
    db,
    user,
    "auth.first_login_rotation",
    "user",
    str(user.id),
    {"email": user.email},
)
await db.commit()
```

### Zod Schema for Change-Password Form
```typescript
// Source: pattern from frontend/src/lib/validation/auth.ts (existing validation module)
import { z } from 'zod';

export const changePasswordSchema = z.object({
  current_password: z.string().min(1, 'Current password is required'),
  new_password: z.string().min(8, 'Min 8 characters'),
  confirm_password: z.string().min(1, 'Confirm your new password'),
}).refine((d) => d.new_password === d.confirm_password, {
  message: "Passwords don't match",
  path: ['confirm_password'],
});
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest with pytest-asyncio (asyncio_mode=auto) |
| Backend config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Backend quick run | `cd backend && python -m pytest tests/test_auth.py -x` |
| Backend full suite | `cd backend && python -m pytest tests/ -x` (per-file isolation required — see MEMORY.md) |
| Frontend framework | Vitest 2.x with jsdom + @testing-library/react |
| Frontend config file | `frontend/vitest.config.mts` |
| Frontend quick run | `cd frontend && npm run test` |
| Frontend full suite | `cd frontend && npm run test` |

**Backend env vars required:** `ENCRYPTION_KEY` and `JWT_SECRET_KEY` must be set (see MEMORY.md: `getvul-backend-pytest-env`). Run tests per-file, not the whole `tests/` directory, to avoid false failures.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-06-01 | Migration adds column; `create_admin.py` seeds flag=True | integration | `pytest tests/test_admin_hardening.py::test_migration_column -x` | ❌ Wave 0 |
| PROD-06-01 | Seeded admin has `must_change_password=True` in DB | integration | `pytest tests/test_admin_hardening.py::test_seed_flag -x` | ❌ Wave 0 |
| PROD-06-02 | JWT access token carries claim from login | unit | `pytest tests/test_admin_hardening.py::test_jwt_claim_round_trip -x` | ❌ Wave 0 |
| PROD-06-02 | `get_current_user` returns `must_change_password=True` for flagged token | unit | `pytest tests/test_admin_hardening.py::test_current_user_claim -x` | ❌ Wave 0 |
| PROD-06-02 | Flagged user: non-allowlist request → 403 + `password_change_required` | integration | `pytest tests/test_admin_hardening.py::test_enforcement_blocks -x` | ❌ Wave 0 |
| PROD-06-02 | Flagged user: `/auth/me` → 200 (allowlist pass) | integration | `pytest tests/test_admin_hardening.py::test_enforcement_allowlist_me -x` | ❌ Wave 0 |
| PROD-06-02 | Flagged user: `/auth/change-password` → not blocked | integration | `pytest tests/test_admin_hardening.py::test_enforcement_allowlist_change -x` | ❌ Wave 0 |
| PROD-06-02 | Unflagged user: no 403 interference | integration | `pytest tests/test_admin_hardening.py::test_unflagged_user_unblocked -x` | ❌ Wave 0 |
| PROD-06-03 | (Frontend redirect gate) — covered by Vitest unit test | unit | `cd frontend && npm run test -- change-password` | ❌ Wave 0 |
| PROD-06-04 | Successful rotation clears DB flag | integration | `pytest tests/test_admin_hardening.py::test_rotation_clears_flag -x` | ❌ Wave 0 |
| PROD-06-04 | Successful rotation emits `auth.first_login_rotation` audit row | integration | `pytest tests/test_admin_hardening.py::test_rotation_audit_event -x` | ❌ Wave 0 |
| PROD-06-04 | Returned tokens after rotation do NOT carry flag | integration | `pytest tests/test_admin_hardening.py::test_rotation_fresh_tokens -x` | ❌ Wave 0 |
| PROD-06-04 | `/auth/refresh` after rotation carries current DB flag state | integration | `pytest tests/test_admin_hardening.py::test_refresh_reads_current_flag -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** Run the specific test file — `pytest tests/test_admin_hardening.py -x`
- **Per wave merge:** `pytest tests/test_admin_hardening.py tests/test_auth.py -x` (regression: ensure existing JWT tests still pass)
- **Phase gate:** Full backend suite green + `npm run test` frontend green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_admin_hardening.py` — all 13 backend test cases above; needs `db_session`, `tenant_a`, `client_factory` fixtures from `conftest.py` (already present)
- [ ] `frontend/src/app/change-password/change-password.test.tsx` — Vitest unit: redirect gate fires when `must_change_password=true`; form submits correctly; error states render; success redirects

---

## Environment Availability

Step 2.6: No new external dependencies. Phase adds a boolean column and auth middleware — no new CLI tools, databases, runtimes, or external services required. Postgres + Redis already available per prior phase execution.

---

## Open Questions

1. **Router mount prefix for allowlist path matching**
   - What we know: Auth router is registered in `main.py` with a prefix (likely `/api/v1`)
   - What's unclear: The exact prefix determines whether allowlist entries must be `/auth/change-password` or `/api/v1/auth/change-password`
   - Recommendation: Planner must read `backend/app/main.py` line where `router.include_router(auth_router, ...)` is called and record the prefix before writing the allowlist constant.

2. **Token re-issue mechanism: response body or redirect to `/auth/refresh`**
   - What we know: D-09c says "re-issue fresh access+refresh tokens" — Claude's Discretion on mechanism
   - What's unclear: (a) Return new `TokenResponse` from `/auth/change-password` (currently returns `{"message": "Password updated"}`), or (b) frontend calls `/auth/refresh` after success
   - Recommendation: Return a new `TokenResponse` from the endpoint when the flag was set (the endpoint knows the user's tenant from `user.tenant_id` and can do a DB lookup to get the tenant for `issue_tokens`). This makes the flow self-contained and doesn't require the frontend to do two round-trips.

3. **Whether to hard-reject `Admin123!` as the new password**
   - What we know: `password_history` reuse prevention exists but requires `history_count > 0` in tenant policy; default `history_count = 0` means it does NOT reject reuse
   - What's unclear: Default tenant created by `create_admin.py` has no `password_policy` set (null) → `DEFAULT_POLICY` applies → `history_count = 0` → password history check is effectively disabled
   - Recommendation (Claude's Discretion): Belt-and-suspenders literal check in the endpoint: if `user.must_change_password` was set AND `new_password == "Admin123!"`, return 400 with a clear error. This is the safest default and costs one line of code.

4. **`confirm_password` field on the change-password form**
   - What we know: The login page's reset form has only `token` + `newPassword` fields, no confirmation
   - What's unclear: D-13 doesn't specify whether to require confirm-password
   - Recommendation: Include a `confirm_password` field and zod refinement — it is standard UX for a force-rotation flow and prevents typos on a critical one-time operation.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Auth router is mounted with a `/api/v1` prefix in `main.py` | Pitfall 1, Pattern 3 | Allowlist path check always fails or always passes — enforcement broken in one direction |
| A2 | The default tenant created by `create_admin.py` has `password_policy = null` (no history enforcement) | Open Questions #3 | If policy does enforce history, the Admin123! belt-and-suspenders check may be redundant but harmless |

**Planner action for A1:** Read `backend/app/main.py` auth router include call to confirm prefix before writing the allowlist constant.

---

## Sources

### Primary (HIGH confidence)
- `backend/app/auth/jwt.py` — TokenPayload class, create_access_token, create_refresh_token, decode_token — verified line by line
- `backend/app/auth/dependencies.py` — get_current_user, require_role — verified line by line
- `backend/app/auth/schemas.py` — CurrentUser, TokenResponse, UserInfo — verified
- `backend/app/auth/router.py` — all auth endpoints — verified
- `backend/app/auth/service.py` — issue_tokens, refresh_access_token — verified
- `backend/app/auth/password.py` — change_password, validate_password, check_password_history — verified
- `backend/app/tenants/models.py` — User model, existing columns — verified
- `backend/app/audit.py` — audit() signature, AuditLog model — verified
- `backend/create_admin.py` — INSERT SQL, flag-setting requirement — verified
- `backend/alembic/versions/028_add_ticket_watchers.py` — current head revision, conventions — verified
- `backend/alembic/versions/011_add_password_auth.py` — Boolean column-add pattern — verified
- `backend/alembic/versions/016_add_password_policy.py` — JSONB column-add pattern — verified
- `backend/tests/conftest.py` — db_session, tenant_a, client_factory fixtures — verified
- `frontend/src/lib/auth.tsx` — User interface, useAuth, fetchMe, redirect gate — verified
- `frontend/src/app/login/page.tsx` — LoginForm pattern, post-success router.replace — verified
- `frontend/src/app/login/sanitize-next.ts` — sanitizeNext function — verified
- `frontend/src/app/(authed)/layout.tsx` — no auth check, AppShell wrapper — verified
- `frontend/src/components/ui/button.tsx` — ButtonProps, loading prop — verified
- `frontend/src/components/ui/input.tsx` — InputProps, password eye-toggle — verified
- `frontend/src/components/ui/form.tsx` — shadcn Form compound — verified
- `frontend/src/components/auth/error-alert.tsx` — ErrorAlert props — verified
- `frontend/src/lib/queries/use-tenant-users.ts` — useChangePassword hook exists — verified

### Secondary (MEDIUM confidence)
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — tone rules for copy
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — loading/error/success patterns
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — Hero split-screen layout
- `.planning/phases/09-login-foundation/09-CONTEXT.md` — Phase 9 decisions (D-21, D-28, D-50)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; verified in live code
- Architecture: HIGH — all integration points verified line-by-line in live code
- Pitfalls: HIGH — derived from verified code structure, not speculation
- Frontend page design: HIGH — primitives verified; design system references verified

**Research date:** 2026-07-08
**Valid until:** 2026-08-08 (stable codebase; no external fast-moving dependencies)
