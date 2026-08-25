---
phase: 41-coverage-blind-spot-detection
plan: 04
subsystem: api
tags: [fastapi, sqlalchemy, postgres, notifications, audit, coverage]

# Dependency graph
requires:
  - phase: 41-03
    provides: "backend/app/coverage/{schemas,service,router}.py module extended additively; _get_asset_or_404 already staged in Plan 01/03 for this plan's POST to import directly"
provides:
  - "POST /api/v1/coverage/assets/{asset_id}/route-to-owner (require_analyst) — resolve-then-notify-with-fallback (D-07/D-09), audit-then-commit (D-08), notify-only"
  - "route_to_owner(db, tenant, user, asset) service function returning {hostname, routed_to}"
  - "coverage_unmanaged_asset routing key in DEFAULT_ALERTING_CONFIG['routing'] (D-09 channel push, empty default)"
  - "coverage.route_to_owner audit action (fail-closed via audit())"
affects: [41-05-route-to-owner-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "route_to_owner mirrors alerts.py::_fire_kev_epss_alert's resolve-then-notify-with-fallback template verbatim, adapted to a real CurrentUser actor: the caller (router) audits and commits via the fail-closed audit() helper instead of a raw scheduler-side AuditLog(...) insert."
    - "Local imports inside route_to_owner (get_directory_user, _email_owners_and_admins, dispatch_channel, _send_notification_email, _build_channel_config) re-resolve their origin module's attribute fresh on every call — mirrors _fire_kev_epss_alert / detect_and_escalate's own documented idiom, which is what makes monkeypatch.setattr on the origin module (not a local alias) effective in tests."

key-files:
  created: []
  modified:
    - backend/app/coverage/service.py
    - backend/app/coverage/router.py
    - backend/app/coverage/schemas.py
    - backend/app/notifications/alerting_config.py
    - backend/app/audit.py
    - backend/tests/test_coverage.py

key-decisions:
  - "route_to_owner never calls db.commit() and never constructs AuditLog directly — the router endpoint does `result = await route_to_owner(...); await audit(db, user, \"coverage.route_to_owner\", ...); await db.commit()`, matching the exceptions/campaigns audit-then-commit convention (D-08) rather than the scheduler's raw-insert shape used by _fire_kev_epss_alert (which has no real CurrentUser actor)."
  - "routed_to is either the resolved owner's display_name (falling back to email if display_name is falsy) or the literal string \"your admins\" on the D-09 fallback path — both the response body and the audit row's details carry this same value."
  - "No idempotency/state-transition guard on the endpoint, per the plan's explicit prohibition — it is a repeatable notify action; every invocation writes its own audit row, which is the intended abuse-attribution control (T-41-14, disposition: accept)."

patterns-established:
  - "coverage_unmanaged_asset joins new_kev_epss/digest_owner/digest_team as the fourth DEFAULT_ALERTING_CONFIG['routing'] key — an empty list default, so dispatch is a no-op until a tenant explicitly configures a channel for it (no migration, one-line JSONB default)."

requirements-completed: []  # COV-03 shared with 41-05 (frontend drill panel); not yet closeable until both declaring plans land

# Metrics
duration: 35min
completed: 2026-08-21
status: complete
---

# Phase 41 Plan 04: Route-to-Owner Backend (COV-03)

**POST /api/v1/coverage/assets/{asset_id}/route-to-owner resolves a never-scanned asset's owner via the directory and notifies them to onboard it, falling back to tenant admins + the tenant alert channel when no owner resolves — notify-only, analyst-gated, audit-then-commit, mirroring the shipped `_fire_kev_epss_alert` template.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-08-21T07:35:00Z (approx)
- **Completed:** 2026-08-21T08:10:00Z
- **Tasks:** 1 completed
- **Files modified:** 6

## Accomplishments

- `route_to_owner(db, tenant, user, asset)` in `backend/app/coverage/service.py`: resolves the asset's owner via `get_directory_user`; if resolved with an email, calls `_send_notification_email` directly and sets `routed_to` to the owner's display name (or email); otherwise falls back to `_email_owners_and_admins` (D-09 email leg) with `routed_to = "your admins"`. Always then attempts the D-09 channel leg — `merged_alerting_config(tenant)["routing"]["coverage_unmanaged_asset"]` channels via `dispatch_channel` + `_build_channel_config`, each wrapped in its own try/except so a channel failure never blocks the email or the caller's audit row. Returns `{"hostname", "routed_to"}`; never commits, never constructs `AuditLog` directly.
- `POST /api/v1/coverage/assets/{asset_id}/route-to-owner` in `backend/app/coverage/router.py`, gated on `require_analyst` (imported from `app.auth.rbac`, not `app.auth.dependencies` per Pitfall 4): `_get_asset_or_404` (tenant-scoped, T-41-11 IDOR) → loads the tenant row → `route_to_owner(...)` → `audit(db, user, "coverage.route_to_owner", "asset", str(asset.id), result)` → `await db.commit()` → returns the result.
- `RouteToOwnerResponse` schema (`hostname: str`, `routed_to: str`) added to `backend/app/coverage/schemas.py`.
- `"coverage_unmanaged_asset": []` added to `DEFAULT_ALERTING_CONFIG["routing"]` in `backend/app/notifications/alerting_config.py` — one-line JSONB default, no migration.
- `coverage.route_to_owner` appended to the action-name reference comment in `backend/app/audit.py`.
- 5 new backend tests in `backend/tests/test_coverage.py`: resolved (owner email sent + audit `routed_to` == owner display name), fallback (admin email + channel dispatch attempted + audit `routed_to == "your admins"`), channel-failure-isolated (a `dispatch_channel` exception does not block the admin email or the audit row), RBAC (viewer 403 on POST, viewer 200 on both GETs, analyst 200 on POST), cross-tenant 404. All 16 tests in the file pass (11 pre-existing + 5 new).

## Task Commits

1. **Task 1: route_to_owner service + POST endpoint + D-09 fallback + audit (COV-03)** — `7de92d8` (feat)

**Plan metadata:** _(pending — this commit)_

## Files Created/Modified

- `backend/app/coverage/service.py` — `route_to_owner()` (resolve-then-notify-with-fallback + D-09 channel push)
- `backend/app/coverage/router.py` — `POST /assets/{asset_id}/route-to-owner` endpoint (require_analyst)
- `backend/app/coverage/schemas.py` — `RouteToOwnerResponse`
- `backend/app/notifications/alerting_config.py` — `coverage_unmanaged_asset` routing key
- `backend/app/audit.py` — `coverage.route_to_owner` action-name comment
- `backend/tests/test_coverage.py` — 5 new COV-03 behavior tests + `_analyst_user_for`/`_audit_rows` test helpers (mirroring `test_exceptions.py`)

## Decisions Made

- `route_to_owner`'s five collaborator imports (`get_directory_user`, `_email_owners_and_admins`, `dispatch_channel`, `_send_notification_email`, `_build_channel_config`) are all local imports inside the function body, mirroring `_fire_kev_epss_alert`'s and `detect_and_escalate`'s own documented idiom — each re-resolves the origin module's attribute fresh on every call, which is what makes `monkeypatch.setattr` on the origin module (e.g. `app.notifications.escalation_channels.dispatch_channel`) effective in the new tests, rather than requiring a harder-to-patch local alias.
- `merged_alerting_config` itself is imported at module top level in `service.py` (not locally) since it needs no test-time monkeypatching — only the I/O-performing collaborators need the local-import indirection.
- The "resolved" test seeds `asset.assigned_user` with the `viewer_user` fixture's email (a real, already-persisted `User` row from `conftest.py`'s `_make_user`) rather than creating a bespoke owner fixture — `get_directory_user`'s precedence (`humaans_email` → `assigned_user` → `last_login_user`) only needs a real tenant-scoped `User.email` match, and this fixture already satisfies that with zero new seed helpers.

## Deviations from Plan

None — plan executed exactly as written. The only adjustment was fixing an initial test-authoring mistake (asserting `viewer_user.display_name`, which doesn't exist on the `CurrentUser` schema returned by the fixture) by querying the real `User` row's `display_name` from the DB instead — caught immediately by the first test run, not a deviation from the plan's design.

## Issues Encountered

None. `ruff check`/`ruff format --check` clean on all six touched files; `mypy` reports zero new errors in `app/coverage/{service,router,schemas}.py` (the ~103 errors surfaced when checking those files are all pre-existing, in transitively-imported dependency modules such as `app/ticketing/service.py`, `app/vulnerabilities/trends.py`, `app/auth/dependencies.py` — none in this plan's files).

## User Setup Required

None — no external service configuration required. Tenants that want the D-09 channel push to actually fire must configure a channel name under `alerting_config.routing.coverage_unmanaged_asset` (empty list by default, a future settings-pane concern, not this plan's scope).

## Next Phase Readiness

- `POST /api/v1/coverage/assets/{asset_id}/route-to-owner` and its `RouteToOwnerResponse` contract are ready for Plan 05 (COV-03 frontend, route-to-owner drill panel) to build against.
- COV-03 is shared with 41-05 (mirrors the COV-01/41-01+41-02 split) — left `[ ]` unmarked in REQUIREMENTS.md until 41-05 also lands.
- No blockers.

## Self-Check: PASSED

- `git log --oneline --all | grep 7de92d8` confirmed present.
- `grep -q "coverage_unmanaged_asset" backend/app/notifications/alerting_config.py` and `grep -q "coverage.route_to_owner" backend/app/audit.py` both confirmed.
- `backend/app/coverage/service.py` contains no `AuditLog(` and no `.commit(` calls (only docstring prose referencing them); `backend/app/coverage/router.py` contains `require_analyst`.
- `ENCRYPTION_KEY=... JWT_SECRET_KEY=test-secret pytest tests/test_coverage.py -q` re-run green: 16/16 passed immediately before this summary's commit.

---
*Phase: 41-coverage-blind-spot-detection*
*Completed: 2026-08-21*
