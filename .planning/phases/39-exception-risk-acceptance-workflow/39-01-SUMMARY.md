---
phase: 39-exception-risk-acceptance-workflow
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, alembic, postgres, exceptions, risk-acceptance, compute-on-read, audit]

# Dependency graph
requires:
  - phase: 38-remediation-campaigns
    provides: the new-governed-table + compute-on-read + audit + RBAC module shape (Campaign model/schema/router/service) this plan's ExceptionRecord/exceptions module directly clones
  - phase: 32-asset-exposure-context
    provides: AssetGroupMember live-membership join table, reused (read-only) by active_exception_subquery's ASSET_GROUP branch
provides:
  - "ExceptionRecord model + exceptions table (migration 050_add_exceptions), no partial-unique index (D-12 overlap allowed)"
  - "active_exception_subquery(tenant_id, now): the shared compute-on-read exclusion seam (FINDING/ASSET/ASSET_GROUP branches, CVE-pinned, D-10/D-12)"
  - "POST/GET /api/v1/exceptions + POST /{id}/revoke — FINDING scope end-to-end; ASSET/ASSET_GROUP 400 cleanly (Plan 02)"
  - "Pattern 4 lazy-on-read exception.expire audit sweep, idempotent via resurfaced_audited_at"
  - "vulnerabilities/service.py::_apply_filters wired to the exclusion join — the FIRST of ~20 consumers (RESEARCH Consumer Sweep) to learn it"
affects: [39-02-scope-resolution, 39-03-sla-subtraction, 39-04-consumer-sweep, 39-05-consumer-sweep, 39-06-dashboards-frontend, 39-07-frontend, 39-08-closing-plan]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Compute-on-read exclusion via a correlated EXISTS subquery, shared across every consumer (mirrors Phase 36 SLA / Phase 38 campaign progress discipline)"
    - "Lazy-on-read system-attributed audit sweep guarded by a nullable stamp column (Pattern 4, mirrors campaigns' apply_lifecycle_transition)"
    - "Server-side scope resolution — never trust client-supplied cve_id/asset_id independently of the resolved target row (Pitfall 9)"

key-files:
  created:
    - backend/app/exceptions/__init__.py
    - backend/app/exceptions/models.py
    - backend/app/exceptions/schemas.py
    - backend/app/exceptions/service.py
    - backend/app/exceptions/router.py
    - backend/alembic/versions/050_add_exceptions.py
    - backend/tests/test_exceptions.py
  modified:
    - backend/app/main.py
    - backend/app/audit.py
    - backend/app/vulnerabilities/service.py

key-decisions:
  - "D-03's OPEN/IN_PROGRESS grant precondition applied to FINDING scope only (not ASSET/ASSET_GROUP, which are forward-looking per D-11) — implemented per RESEARCH Pattern 2 even though Task 2's action bullets didn't restate it verbatim"
  - "ExceptionResponse omits a pre-formatted 'target' display label — exposes raw scope_type/cve_id/vulnerability_id/asset_id/asset_group_id instead, since ASSET/ASSET_GROUP resolution doesn't exist until Plan 02 and a partial target formatter would be untested dead branches in a tracer plan"
  - "approver_user_id is validated to be a same-tenant User at grant time (400 otherwise) plus a tenant-scoped defense-in-depth filter on the display-name read lookup — added as a Rule 2 fix after self-review found the bare FK alone permits a cross-tenant approver, which would leak that user's display_name/email via GET /exceptions"
  - "EXC-01..04 requirement checkboxes deliberately left unmarked in REQUIREMENTS.md — every one is also claimed by 2-4 of this phase's other 7 plans (39-08 is the last to touch all four); mirrors the Phase 38 CAMP-01 precedent of only the declaring/last plan marking a requirement complete"
  - "Task 2's literal <verify> command (app.routes introspection) doesn't work under the installed FastAPI 0.141.1 — routes are wrapped in lazy _IncludedRouter objects with no resolved .path until first request/OpenAPI build; verified via app.openapi()'s resolved paths + a live smoke request instead (500-not-404, matching the pre-existing campaigns router's identical behavior)"

patterns-established:
  - "Exception scope resolution is server-authoritative: FINDING scope derives cve_id/asset_id from the resolved Vulnerability row, never from client-supplied fields"
  - "Every new 'active work' query filter gets ~active_exception_subquery(tenant_id, now) added immediately after its tenant_id clause — the single line every future consumer-sweep plan repeats"

requirements-completed: []  # EXC-01..04 span all 8 plans in this phase; not yet fully satisfied (FINDING scope only, 1 of ~20 consumers wired) — see key-decisions

# Metrics
duration: 29min
completed: 2026-08-19
---

# Phase 39 Plan 01: Exception & Risk-Acceptance Tracer Slice Summary

**New `exceptions` table + a shared `active_exception_subquery` compute-on-read exclusion seam, grant/list/revoke endpoints (FINDING scope), a Pattern 4 lazy-on-read expiry-audit sweep, and the vuln list wired as the first excluded consumer — proven end-to-end by an 8-test tracer suite.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-08-19T06:29:56Z
- **Completed:** 2026-08-19T06:58:39Z
- **Tasks:** 3/3 (plus one Rule-2 deviation fix)
- **Files modified:** 11 (8 created, 3 modified)

## Accomplishments

- `ExceptionRecord` model + `exceptions` table (migration `050_add_exceptions`, 7 indexes incl. a pure-NULL-check partial index) — the exclusion source of truth, additive to the legacy `SUPPRESSED`/`FALSE_POSITIVE` status signal (D-01/D-02)
- `active_exception_subquery(tenant_id, now)` — one correlated `EXISTS` covering FINDING/ASSET/ASSET_GROUP scope matching, CVE-pinned (D-10), OR-semantics across overlapping exceptions (D-12)
- `POST /api/v1/exceptions` (grant), `GET /api/v1/exceptions` (list), `POST /api/v1/exceptions/{id}/revoke` — `require_analyst` on writes / `require_viewer` on list, tenant-scoped 404s, audit-then-commit exactly mirroring `ignore_cve`
- Pattern 4 lazy-on-read `exception.expire` audit sweep — fires exactly once per naturally-lapsed exception, guarded by `resurfaced_audited_at IS NULL`, closing EXC-03's otherwise-silent lifecycle gap
- `vulnerabilities/service.py::_apply_filters` now excludes actively-excepted findings — the first of ~20 consumers identified in RESEARCH's Consumer Sweep to learn the shared seam
- 8-test tracer suite (`backend/tests/test_exceptions.py`) proving grant → excluded → auto-resurface (+ lazy-audit) → revoke → audited end-to-end, plus the strict `now == expires_at` boundary and cross-tenant IDOR defenses

## Task Commits

Each task was committed atomically:

1. **Task 1: exceptions table — model, Pydantic schemas, Alembic migration** - `ba69747` (feat)
2. **Task 2: shared active_exception_subquery seam + grant/list/revoke endpoints + lazy expiry-audit + wire the vuln list** - `7643d56` (feat)
3. **Task 3: end-to-end tracer test — grant → excluded → auto-resurface + lazy-audit + revoke → audited** - `ab2c2b4` (test)

**Deviation fix (Rule 2, found during Task 3 self-review):** `914ef25` (fix)

**Plan metadata:** _pending — this commit follows_

## Files Created/Modified

- `backend/app/exceptions/__init__.py` - empty package marker (mirrors `campaigns/__init__.py`)
- `backend/app/exceptions/models.py` - `ExceptionRecord` SQLAlchemy model (class named `ExceptionRecord`, not `Exception` — Pitfall 10)
- `backend/app/exceptions/schemas.py` - `ExceptionCreate` (extra="forbid", Literal type/scope_type) + `ExceptionResponse` (persisted columns + `approver_display_name`)
- `backend/app/exceptions/service.py` - `active_exception_subquery`, `validate_expiry` (D-14, 365-day cap), `sweep_expired_audits` (Pattern 4), `grant_exception`/`list_exceptions`/`revoke_exception`
- `backend/app/exceptions/router.py` - `POST /`, `GET /`, `POST /{id}/revoke`; `_get_exception_or_404`; batched `_to_responses` (tenant-scoped approver display-name lookup)
- `backend/alembic/versions/050_add_exceptions.py` - migration, `down_revision = "049_add_campaigns"`, 7 indexes
- `backend/tests/test_exceptions.py` - 8 tests (the plan's 7 + 1 self-review addendum)
- `backend/app/main.py` - mounts `exceptions_router` at `/api/v1/exceptions`
- `backend/app/audit.py` - Actions comment extended with `exception.grant`/`exception.revoke`/`exception.expire`
- `backend/app/vulnerabilities/service.py` - `_apply_filters` excludes actively-excepted findings
- `.planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md` - logs pre-existing, unrelated mypy-baseline drift (out of scope, verified via git-stash)

## Decisions Made

- D-03's grant precondition (reject FINDING-scope grants on non-OPEN/IN_PROGRESS findings) implemented per RESEARCH Pattern 2/Pitfall 8, even though Task 2's action bullets didn't restate it verbatim — the task's own `<read_first>` cites "D-03 precondition text" explicitly.
- `ExceptionResponse` skips a pre-formatted `target` display string; exposes raw scope fields instead. Building `target` formatting now (ahead of Plan 02's ASSET/ASSET_GROUP resolution) would be untested dead branches in a tracer plan whose stated goal is minimum blast radius.
- `approver_user_id` is validated to be a same-tenant `User` at grant time (see Deviations below).
- EXC-01..04 checkboxes in REQUIREMENTS.md left unmarked — every requirement ID is claimed by 2-4 of this phase's 8 plans (39-08 is the last to touch all four); marking them now would overclaim. Mirrors Phase 38's CAMP-01 precedent.
- Task 2's literal `<verify>` command (`app.routes` introspection) doesn't resolve `.path` under the installed FastAPI 0.141.1 (routes are wrapped in lazy `_IncludedRouter` objects). Verified the identical intent via `app.openapi()`'s resolved paths (`/api/v1/exceptions`, `/api/v1/exceptions/{exception_id}/revoke`) plus a live smoke request returning 500-not-404 (matching the pre-existing `campaigns` router's identical unauthenticated-request behavior) — confirmed this is a pre-existing environment characteristic, not a regression, by reproducing the same `app.routes` opacity against the already-shipped `campaigns` router.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `active_exception_subquery` missing a return-type annotation (mypy)**
- **Found during:** Task 2 verification (`mypy app/ | mypy-baseline filter`)
- **Issue:** The function had no return-type annotation, tripping `no-untyped-def` — the one genuinely new mypy violation attributable to this plan (confirmed via `git stash` against the pre-existing tree, which independently showed the same 9 unrelated violations with zero of this plan's code present).
- **Fix:** Added `-> Exists` (from `sqlalchemy`).
- **Files modified:** `backend/app/exceptions/service.py`
- **Verification:** `mypy app/ | mypy-baseline filter` "new" count returned to the pre-existing-drift baseline (9), i.e. net-zero-new from this plan.
- **Committed in:** `7643d56` (Task 2 commit)

**2. [Rule 2 - Missing Critical] Cross-tenant approver_user_id was not rejected (IDOR/information-disclosure gap)**
- **Found during:** Post-Task-3 self-review (threat surface scan)
- **Issue:** `grant_exception` only relied on the `approver_user_id` FK, which checks *existence* in the global `users` table, not tenant membership. An analyst could name another tenant's (guessable) user as approver. `GET /api/v1/exceptions`'s batched `approver_display_name` lookup then had no tenant filter either, so that foreign user's `display_name`/`email` would resolve and be returned to this tenant's viewers.
- **Fix:** `grant_exception` now validates `approver_user_id` resolves to a `User` row in the granting tenant (400 otherwise); `_to_responses`'s batched lookup is additionally tenant-scoped as defense-in-depth.
- **Files modified:** `backend/app/exceptions/service.py`, `backend/app/exceptions/router.py`, `backend/tests/test_exceptions.py` (added `test_grant_rejects_cross_tenant_approver`)
- **Verification:** New test passes (proves both the 400 on a foreign approver and that a same-tenant approver still succeeds); full 8/8 suite green; no regressions across vulnerabilities/campaigns/asset-groups suites (39 passed).
- **Committed in:** `914ef25`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing-critical/security)
**Impact on plan:** Both fixes are correctness/security-necessary. No scope creep — neither touches ASSET/ASSET_GROUP resolution, SLA subtraction, or any consumer beyond the one this plan wires.

## Issues Encountered

- Pre-existing, unrelated `mypy-baseline` drift (9 violations in `backend/app/ticketing/daily_sync.py` + a `note:` line-count mismatch) surfaced when running the CI-equivalent `mypy app/ | mypy-baseline filter`. Verified via `git stash` (re-running the identical command against the tree with zero of this plan's changes present reproduces the exact same 9 violations) that this predates and is unrelated to this plan. Logged to `deferred-items.md`, not fixed (out of scope — `daily_sync.py` is untouched by 39-01).
- FastAPI 0.141.1 (newer than the `PROJECT.md`-documented "≥0.115" floor) wraps `app.include_router(...)` results in a lazy `_IncludedRouter` object that doesn't expose a resolved `.path` on `app.routes` until the app actually serves a request or builds its OpenAPI schema. This made Task 2's literal `<verify>` assertion fail even though the router was correctly mounted — resolved by using `app.openapi()`'s resolved `paths` dict (the authoritative flattened route list) plus a live smoke request as equivalent verification, after confirming the pre-existing `campaigns` router exhibits the identical `app.routes` opacity.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The `active_exception_subquery` seam, `ExceptionRecord` model, and audit/RBAC scaffolding are in place for Plan 02 to add ASSET/ASSET_GROUP scope resolution (the `else: raise HTTPException(400, ...)` branch in `grant_exception` is the exact landing spot).
- Plans 03-06 can now sweep the remaining ~19 consumers (SLA tier service, risk score, remediation grouped view, campaign denominator, rule engine, escalation, etc.) by adding the same one-line `~active_exception_subquery(...)` filter — Pattern 1 from RESEARCH.md is proven correct against a real consumer.
- No blockers. `alembic upgrade head` / `downgrade -1` / `upgrade head` round-trips clean; full `test_exceptions.py` suite (8/8) plus a 111-test regression sweep across vulnerabilities/campaigns/asset-groups/SLA/dashboard suites all green.

## Self-Check: PASSED

- `backend/app/exceptions/__init__.py` — FOUND
- `backend/app/exceptions/models.py` — FOUND
- `backend/app/exceptions/schemas.py` — FOUND
- `backend/app/exceptions/service.py` — FOUND
- `backend/app/exceptions/router.py` — FOUND
- `backend/alembic/versions/050_add_exceptions.py` — FOUND
- `backend/tests/test_exceptions.py` — FOUND
- `.planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md` — FOUND
- Commit `ba69747` — FOUND in git log
- Commit `7643d56` — FOUND in git log
- Commit `ab2c2b4` — FOUND in git log
- Commit `914ef25` — FOUND in git log

---
*Phase: 39-exception-risk-acceptance-workflow*
*Completed: 2026-08-19*
