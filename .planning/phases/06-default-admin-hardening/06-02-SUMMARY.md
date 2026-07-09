---
phase: 06-default-admin-hardening
plan: 02
subsystem: auth
tags: [fastapi, jwt, auth, admin-hardening, enforcement, audit, security]

# Dependency graph
requires:
  - phase: 06-default-admin-hardening (plan 00)
    provides: backend/tests/test_admin_hardening.py (12 contractual test cases)
  - phase: 06-default-admin-hardening (plan 01)
    provides: users.must_change_password column + User ORM attribute + seed flag
provides:
  - must_change_password claim threaded through create_access_token / TokenPayload / decode_token
  - CurrentUser.must_change_password field
  - issue_tokens + refresh_access_token feed the current DB must_change_password flag
  - get_current_user forced-rotation gate (403 password_change_required) + MUST_CHANGE_PASSWORD_ALLOWLIST
  - /auth/change-password rotation completion (clear flag, auth.first_login_rotation audit, fresh tokens, Admin123! reject)
affects: [06-default-admin-hardening plan 03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Security claim on the JWT is the sole hot-path enforcement input (no DB read on every request); refresh + rotation re-read the DB flag to bound the stale-token window to the access-token TTL"
    - "Enforcement gate lives inside the single shared get_current_user dependency so every protected route (and require_role, which wraps it) inherits it — dev-token path gated too"
    - "Exact frozenset membership on request.url.path (no prefix/suffix/case) for the allowlist"
    - "AUDIT-01 fail-closed order in a mutation: set state -> audit() -> commit()"

key-files:
  created: []
  modified:
    - backend/app/auth/jwt.py
    - backend/app/auth/schemas.py
    - backend/app/auth/service.py
    - backend/app/auth/dependencies.py
    - backend/app/auth/router.py

key-decisions:
  - "get_current_user's request/credentials/db params take defaults so the fixed-contract unit test test_current_user_claim can call the dependency directly without FastAPI wiring; FastAPI still injects Request positionally at runtime. The gate is a documented no-op when request is None (only reachable via a direct in-process call, never in production where every route crosses the ASGI stack)."
  - "Rotation returns a full fresh TokenResponse via issue_tokens (self-contained token re-issue) so the frontend needs no extra round-trip after clearing the flag."
  - "Admin123! is hard-rejected as the NEW password only when the flag was set (belt-and-suspenders against default-cred reuse, since the default tenant has history_count=0)."

patterns-established:
  - "Forced-rotation enforcement is a single choke-point in the shared auth dependency, not scattered per-route"

requirements-completed: [PROD-06-02, PROD-06-04]

# Metrics
duration: ~27min
completed: 2026-07-09
---

# Phase 6 Plan 02: Enforcement Pipeline + Rotation Completion Summary

**Threaded the must_change_password claim through the JWT round-trip and CurrentUser, added a 403 password_change_required gate with a 4-path allowlist inside get_current_user, and completed forced rotation in /auth/change-password (clear DB flag, auth.first_login_rotation audit, fresh flag-free tokens, Admin123! reject) — all 12 backend admin-hardening tests green with no auth regression.**

## Performance

- **Duration:** ~27 min
- **Started:** 2026-07-09T07:20:57Z
- **Completed:** 2026-07-09T07:47:55Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- **Task 1 (JWT claim round-trip):** `create_access_token` gains a `must_change_password: bool = False` kwarg (added to the payload); `TokenPayload` carries the attribute; `decode_token` restores it from the claim. `CurrentUser` gains the field. `issue_tokens` and `refresh_access_token` both feed the CURRENT DB `user.must_change_password` so a refresh after rotation yields a flag-free token (T-06-token-replay partial mitigation).
- **Task 2 (enforcement gate):** `get_current_user` injects `Request`; both the JWT and dev-token construction sites populate `CurrentUser.must_change_password`. A module-level `MUST_CHANGE_PASSWORD_ALLOWLIST` frozenset holds exactly the four D-07 paths (`/auth/change-password`, `/auth/me`, `/auth/logout`, `/auth/refresh`). A flagged user on any non-allowlist path is rejected with `HTTP 403` and body `{"reason": "password_change_required"}`, via exact `request.url.path` membership. The gate runs on both paths so dev-token cannot bypass it.
- **Task 3 (rotation completion):** `/auth/change-password` captures the flag before rotating; when the flag was set it clears the DB flag, emits an `auth.first_login_rotation` audit row BEFORE commit (AUDIT-01), commits, then returns fresh flag-free tokens via `issue_tokens`. Rejects the literal `Admin123!` as the new password. Non-flagged callers keep the original behavior.
- **All 12 admin-hardening tests GREEN** (2 from Wave 1 + 10 from this plan) plus **9 test_auth.py regression tests GREEN** = 21 passed.

## Task Commits

Each task was committed atomically (parallel executor, --no-verify):

1. **Task 1: JWT claim round-trip + CurrentUser + issue_tokens/refresh** — `d64a8e2` (feat)
2. **Task 2: Enforcement gate in get_current_user (Request + allowlist + 403)** — `00cfa7b` (feat)
3. **Task 3: Rotation completion in /auth/change-password** — `3451e57` (feat)

## Files Modified
- `backend/app/auth/jwt.py` — `must_change_password` kwarg + payload key on `create_access_token`; `TokenPayload` attribute; `decode_token` extraction.
- `backend/app/auth/schemas.py` — `CurrentUser.must_change_password: bool = False`.
- `backend/app/auth/service.py` — `issue_tokens` and `refresh_access_token` pass `must_change_password=user.must_change_password` to `create_access_token`.
- `backend/app/auth/dependencies.py` — `Request` injection, `MUST_CHANGE_PASSWORD_ALLOWLIST`, `_enforce_password_change_gate`, both `CurrentUser` sites carry the claim.
- `backend/app/auth/router.py` — `change_password_endpoint` rotation completion (flag clear, audit, fresh tokens, Admin123! reject).

## Decisions Made
- **get_current_user parameter defaults:** `request`, `credentials`, and `db` were given defaults so the fixed-contract unit test `test_current_user_claim` (which calls `get_current_user(credentials=creds, db=db_session)` directly, with no `request`) does not raise a missing-argument `TypeError`. FastAPI still injects `Request` positionally at runtime, so production DI is unchanged. `_enforce_password_change_gate` treats `request is None` as a no-op (the path cannot be resolved outside the ASGI stack; only a direct in-process call can produce `None`, never a real request). This preserves the test contract while keeping the gate live for every real route.
- **Self-contained token re-issue on rotation** so the frontend replaces its stale flagged tokens without a second call.
- **Admin123! reject scoped to `flag_was_set`** — only the forced-rotation path is at risk from default-cred reuse.

## Deviations from Plan

None — plan executed as written. The only judgment call (parameter defaults on `get_current_user` to satisfy the direct-call unit test) is a Claude's-Discretion implementation detail within Task 2's stated intent ("inject Request FIRST … no Depends wrapper"), not a behavioral deviation. FastAPI's positional `Request` injection still applies.

### Note on test_refresh_reads_current_flag task attribution
The plan lists `test_refresh_reads_current_flag` under Task 1's verify block, but the test is a full rotation-then-refresh round-trip: it stays RED after Task 1 alone because clearing the DB flag is Task 3's responsibility. After Task 1 the service-layer wiring (refresh reads the current DB flag) was correct and `test_jwt_claim_round_trip` was green; `test_refresh_reads_current_flag` went green only after Task 3 landed the rotation flag-clear. No code change was needed to close it beyond the planned Task 3 work — it is an inherently cross-task assertion. Documented here rather than treated as a deviation.

## Threat Model Coverage
- **T-06-allowlist-bypass** (mitigate): exact `request.url.path` frozenset membership, minimal 4-path allowlist. Proven by `test_enforcement_blocks` (403) + `test_enforcement_allowlist_me` / `_change`.
- **T-06-enforcement-completeness** (mitigate): gate inside the single shared `get_current_user`; dev-token path gated too.
- **T-06-audit-fail-open** (mitigate): strict `set flag False -> audit() -> db.commit()` order. Proven by `test_rotation_audit_event`.
- **T-06-default-cred-reuse** (mitigate): literal `Admin123!` rejected as the new password when flagged.
- **T-06-token-replay** (accept + partial mitigate): bounded to access-token TTL; `refresh_access_token` re-reads the DB flag and rotation returns fresh flag-free tokens. Proven by `test_refresh_reads_current_flag` + `test_rotation_fresh_tokens`.

## Issues Encountered
- **Worktree base was behind the merged Wave 1 code.** The worktree HEAD was `4d8b197` (the pre-phase merge commit), an ancestor of the required base `99c84a7` — so the Wave 1 artifacts (migration 029, ORM column, seed, `test_admin_hardening.py`) were absent. The branch-check's `ACTUAL_BASE == 99c84a7` condition did not hold (`ACTUAL_BASE` resolved to `4d8b197`). Confirmed `4d8b197` is an ancestor of `99c84a7` and that `main` sits at `99c84a7` carrying the Wave 1 column, then `git reset --hard 99c84a7` onto the correct base (per-agent branch preserved). Verified `backend/app/tenants/models.py` has `must_change_password` and `test_admin_hardening.py` exists before starting.
- **Env setup** (MEMORY.md `getvul-backend-pytest-env`): no `.venv` in the worktree; used the main checkout's `backend/.venv` with `PYTHONPATH` pointed at the worktree backend. Generated an ephemeral Fernet `ENCRYPTION_KEY` + a `JWT_SECRET_KEY` for the run. Postgres + Redis containers already healthy.

## Known Stubs
None. All wired to real behavior; no placeholder data introduced.

## Next Phase Readiness
- Wave 3 (plan 06-03, frontend) can rely on: a flagged login returning an access token with `must_change_password=true`; a 403 `{"reason": "password_change_required"}` on any non-allowlisted call; `/auth/me` exposing the flag; and `/auth/change-password` returning a fresh flag-free `TokenResponse` on rotation.
- **Orchestrator note:** tests were run against the local dev DB (already at migration head 029 from Wave 1). No new migration in this plan. No STATE.md/ROADMAP.md writes performed (orchestrator owns those post-wave).

## Self-Check: PASSED
</content>
