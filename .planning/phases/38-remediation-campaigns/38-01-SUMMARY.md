---
phase: 38-remediation-campaigns
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, alembic, postgres, rbac, audit, campaigns]

# Dependency graph
requires:
  - phase: 36-remediation-sla-engine-escalation
    provides: mark_vulnerability_remediated() + RemediationEvent (D-09) -- the single REMEDIATED-transition helper this plan's progress query counts against
  - phase: 37-two-way-ticket-sync-remediation-verification
    provides: "REMEDIATED means rescan-verified (D-03); reopen-on-recurrence semantics (D-04) that the campaign progress query will automatically reflect once Plan 03 adds lifecycle handling"
provides:
  - "campaigns table (migration 049) with the D-11 partial unique index uq_campaign_active_remediation (tenant_id, remediation_id) WHERE closed_at IS NULL"
  - "Campaign SQLAlchemy model (identity + lifecycle only, no progress/label snapshot per D-07)"
  - "get_or_create_campaign() -- race-safe D-11 get-or-create (begin_nested + IntegrityError re-select)"
  - "get_campaign_progress() -- compute-on-read total/open/in_progress/done/pct_remediated with the corrected OPEN/IN_PROGRESS/REMEDIATED filter (D-18, Pitfall 2 fix) and the Pitfall-5 zero-guard"
  - "list_campaigns() -- deterministic created_at DESC/id ordering"
  - "POST /api/v1/campaigns, GET /api/v1/campaigns, GET /api/v1/campaigns/{id} -- RBAC (require_analyst writes / require_viewer reads) + tenant-scoped 404 + audit-once-on-create"
affects: [38-02-bulk-ticketing, 38-03-lifecycle-mttr, 38-04-remediation-grouped-page, 38-05-campaign-views]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Race-safe get-or-create against a Postgres partial unique index: SELECT-first fast path, INSERT inside db.begin_nested(), catch IntegrityError, re-SELECT (mirrors sla_tier_service.py:406-428)"
    - "Compute-on-read aggregation with zero persisted snapshot columns (mirrors get_mttr_by_tier's shape, scoped by remediation_id instead of tier)"
    - "Partial unique index via sqlalchemy.Index(unique=True, postgresql_where=text(...)) -- never UniqueConstraint (Postgres has no partial UNIQUE CONSTRAINT syntax)"
    - "Tenant-scoped 404 via a WHERE-clause filter inside a dedicated _get_campaign_or_404 helper, never a post-fetch check (IDOR defense)"

key-files:
  created:
    - backend/alembic/versions/049_add_campaigns.py
    - backend/app/campaigns/__init__.py
    - backend/app/campaigns/models.py
    - backend/app/campaigns/schemas.py
    - backend/app/campaigns/service.py
    - backend/app/campaigns/router.py
    - backend/tests/test_campaigns.py
  modified:
    - backend/app/main.py

key-decisions:
  - "D-11 confirmed via Task 1 checkpoint: partial unique index (not a full unique constraint) on (tenant_id, remediation_id) WHERE closed_at IS NULL -- coordinator-approved, no changes requested"
  - "DBSession imports from app.dependencies, not app.db.session (38-RESEARCH.md Code Example 4 cited the wrong module -- verified against every real router in the codebase)"
  - "Service functions take tenant_id/user_id as separate uuid.UUID params, not a whole user object (matches create_remediation_ticket/create_host_ticket/create_tickets' established signature convention, not RESEARCH.md's pseudocode)"
  - "MTTR (get_campaign_mttr) deliberately NOT implemented in this plan -- CAMP-03 (full progress/MTTR + lifecycle) is Plan 03's scope; this tracer only ships the minimal compute-on-read progress the interfaces block specifies"
  - "The D-13/D-19 lazy-on-read auto-complete PERSISTENCE + audit mechanism (Pattern 6) is NOT implemented here -- only a transient, non-persisted display-status derivation (ACTIVE/COMPLETE) in the response layer, per the plan's own interfaces block; Plan 03 owns the real auto-complete/reactivate audit writes"
  - "CAMP-01 and CAMP-04 requirements are NOT marked complete in REQUIREMENTS.md -- both are shared across sibling plans (CAMP-01 also declared by 38-04/38-05; CAMP-04 also declared by 38-02/38-03) with no SUMMARY.md yet; confirmed via `requirements ready-ids`, which returned both as blocked"

patterns-established:
  - "app/campaigns/ mirrors app/cspm/'s exact 5-file shape (__init__/models/schemas/service/router) -- the codebase's established convention for a new small top-level domain that reads from one existing domain (vulnerabilities) and will write to another (ticketing) roughly equally"

requirements-completed: []  # CAMP-01/CAMP-04 blocked by sibling plans without SUMMARY.md yet (see key-decisions) -- NOT a completion of either requirement, only a contribution

coverage:
  - id: D1
    description: "POST /api/v1/campaigns with a remediation_id persists exactly one campaigns row and GET /api/v1/campaigns reads it back (list ordering is deterministic: created_at DESC, id tiebreak)"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_create_campaign_new"
        status: pass
    human_judgment: false
  - id: D2
    description: "campaign.create audit row is written exactly once, only when a genuinely new campaign is created -- never on a D-11 reopen of an existing active campaign"
    requirement: "CAMP-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_create_campaign_new"
        status: pass
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_create_campaign_reopens_existing"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-11 get-or-create: launching a campaign on a remediation_id with an existing active campaign returns it (already_existed=true), no duplicate row, no second audit row"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_create_campaign_reopens_existing"
        status: pass
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_campaign_unique_active_index"
        status: pass
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_new_campaign_after_close"
        status: pass
    human_judgment: false
  - id: D4
    description: "RBAC: viewer gets 403 on POST /api/v1/campaigns; viewer CAN GET (list + detail); analyst can POST"
    requirement: "CAMP-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_campaign_rbac"
        status: pass
    human_judgment: false
  - id: D5
    description: "Tenant scoping: a campaign from tenant A is invisible to tenant B (404 on detail, absent from list) -- IDOR defense via a WHERE-clause tenant filter, not a post-fetch check"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_campaign_cross_tenant_isolation"
        status: pass
    human_judgment: false
  - id: D6
    description: "Compute-on-read progress counts a REMEDIATED member in done (Pitfall 2 regression guard against naively reusing _base_open_vulns()) and excludes SUPPRESSED/FALSE_POSITIVE from the denominator (D-18)"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_progress_counts_include_remediated"
        status: pass
    human_judgment: false
  - id: D7
    description: "A zero-member remediation_id renders pct_remediated=0 with HTTP 200 (never a 500 from ZeroDivisionError) and never misreports status as COMPLETE for a 0/0 denominator"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_progress_zero_member_no_crash"
        status: pass
    human_judgment: false

# Metrics
duration: 27min
completed: 2026-08-17
status: complete
---

# Phase 38 Plan 01: Remediation Campaigns Tracer Slice Summary

**Campaign persistence vertical proven end-to-end: a new `campaigns` table with a race-safe D-11 partial-unique-index get-or-create, compute-on-read progress (correcting the `_base_open_vulns()` REMEDIATED-exclusion pitfall), audit-once-on-create, and RBAC+tenant-scoped read/write endpoints.**

## Performance

- **Duration:** ~27 min (includes the Task 1 checkpoint pause awaiting coordinator approval)
- **Started:** 2026-08-17T14:11:21Z
- **Completed:** 2026-08-17T14:38:21Z
- **Tasks:** 3 (1 checkpoint:decision + 2 auto, all complete)
- **Files modified:** 8 (7 created, 1 modified)

## Accomplishments
- `campaigns` table (migration 049) with a Postgres partial unique index (`uq_campaign_active_remediation`) enforcing exactly one ACTIVE campaign per (tenant, remediation_id) — verified directly against the live Postgres catalog (`\d+ campaigns` shows `UNIQUE, btree (tenant_id, remediation_id) WHERE closed_at IS NULL`) and via a real `IntegrityError` raised on a duplicate active insert
- Race-safe `get_or_create_campaign()` — a D-11 relaunch on an active remediation_id opens the existing campaign (`already_existed=true`) with zero duplicate rows and zero duplicate audit rows
- `get_campaign_progress()` with the corrected `OPEN`/`IN_PROGRESS`/`REMEDIATED` filter — proven to count a REMEDIATED member in `done` (the exact regression 38-RESEARCH.md's Pitfall 2 warned naive `_base_open_vulns()` reuse would silently break), while excluding `SUPPRESSED`/`FALSE_POSITIVE` from the denominator (D-18)
- Zero-member zero-guard proven live: `pct_remediated=0`, HTTP 200, `status="ACTIVE"` (never a false "COMPLETE" from a 0/0 comparison)
- Full RBAC + tenant-isolation proof: viewer 403 on writes / 200 on reads; a tenant-B analyst gets 404 (not a fetch-then-403) on a tenant-A campaign, and it's absent from tenant B's list
- `POST/GET /api/v1/campaigns` + `GET /api/v1/campaigns/{id}` registered and live — confirmed via `app.openapi()`'s generated schema, not just import-success

## Task Commits

Each task was committed atomically:

1. **Task 1: Confirm the D-11 one-way partial-unique-index schema before migrating** — `checkpoint:decision`, no commit (coordinator approved "partial-unique-index" exactly as proposed, no changes requested)
2. **Task 2: campaigns table migration + Campaign model + module skeleton** - `6008f7e` (feat)
3. **Task 3: get-or-create service + schemas + router (POST/GET/GET-detail) with audit + RBAC** - `3b4367a` (feat)

**Plan metadata:** _pending this commit_ (docs: complete plan)

_Note: Tasks 2 and 3 each carry `tdd="true"` but were committed as single combined test+implementation commits per task, not separate `test(...)`→`feat(...)` sub-commits — see "Deviations from Plan" below._

## Files Created/Modified
- `backend/alembic/versions/049_add_campaigns.py` - campaigns table + ix_campaigns_tenant_id/remediation_id + the D-11 partial unique index, chained off `048_add_clean_scan_streak`
- `backend/app/campaigns/__init__.py` - empty package marker
- `backend/app/campaigns/models.py` - `Campaign` SQLAlchemy model (identity + lifecycle only, D-07)
- `backend/app/campaigns/schemas.py` - `CampaignCreateRequest` (extra=forbid), `CampaignCreateResponse`, `CampaignSummary`, `CampaignDetail`
- `backend/app/campaigns/service.py` - `get_or_create_campaign`, `get_campaign_progress`, `list_campaigns`
- `backend/app/campaigns/router.py` - `POST/GET /api/v1/campaigns`, `GET /api/v1/campaigns/{id}`, `_derive_status`, `_get_campaign_or_404`
- `backend/app/main.py` - registers `campaigns_router` at `/api/v1/campaigns` alongside `tickets_router`
- `backend/tests/test_campaigns.py` - 8 tests: 2 DB-constraint (Task 2) + 6 endpoint/RBAC/tenant-isolation (Task 3)

## Decisions Made
- D-11 confirmed at the Task 1 checkpoint: partial unique index (recommended option), coordinator-approved verbatim, no changes
- `DBSession` imports from `app.dependencies` (not `app.db.session`, which 38-RESEARCH.md's Code Example 4 incorrectly cited) — verified against `vulnerabilities/router.py` and `cspm/router.py`'s actual imports before writing any router code
- Service functions accept `tenant_id: uuid.UUID, user_id: uuid.UUID` as separate params rather than a whole `user` object, matching `create_remediation_ticket`/`create_host_ticket`/`create_tickets`'s established signature convention in this codebase (RESEARCH.md's Code Example 3 pseudocode passed a whole `user` object — not followed)
- MTTR (`get_campaign_mttr`) and the D-13/D-19 lazy-on-read auto-complete persistence+audit mechanism (Pattern 6) are intentionally NOT built in this plan — both are explicitly Plan 03's scope (CAMP-03 "full progress/MTTR + lifecycle") per the plan's own objective and interfaces block; this plan ships only the minimal compute-on-read progress and a transient (non-persisted) display-status derivation
- CAMP-01/CAMP-04 left `[ ]` unmarked in REQUIREMENTS.md — both are declared by sibling plans in this same phase that haven't produced a SUMMARY.md yet (`38-04`/`38-05` for CAMP-01; `38-02`/`38-03` for CAMP-04); `requirements ready-ids` confirmed both as `blocked`, not `ready`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - source-grounding correction] `DBSession` import path**
- **Found during:** Pre-Task-3 reading (before writing any router code, during the Task 1 checkpoint response)
- **Issue:** 38-RESEARCH.md's Code Example 4 cites `from app.db.session import DBSession` — `app/db/session.py` does not export a `DBSession` symbol at all; the real type alias (`Annotated[AsyncSession, Depends(get_db)]`) lives in `app/dependencies.py:12`, confirmed by direct inspection of `vulnerabilities/router.py` and `cspm/router.py`'s actual imports.
- **Fix:** `backend/app/campaigns/router.py` imports `from app.dependencies import DBSession`.
- **Files modified:** `backend/app/campaigns/router.py`
- **Verification:** App boots (`create_app()` succeeds), all 8 tests pass, `app.openapi()` exposes all 3 campaign routes.
- **Committed in:** `3b4367a` (Task 3 commit)

**2. [Rule 1 - source-grounding correction] Service function signature convention**
- **Found during:** Task 3, before writing `service.py`
- **Issue:** 38-RESEARCH.md's Code Example 3 pseudocode passes a whole `user` object into `get_or_create_campaign(db, tenant_id, remediation_id, user)`. Every real precedent in this codebase (`create_tickets`, `create_host_ticket`, `create_remediation_ticket` in `ticketing/service.py`) takes `tenant_id: uuid.UUID, user_id: uuid.UUID` as separate scalar params.
- **Fix:** `get_or_create_campaign(db, tenant_id, remediation_id, user_id)` — matches the established convention; the router passes `user.tenant_id`/`user.id` explicitly.
- **Files modified:** `backend/app/campaigns/service.py`, `backend/app/campaigns/router.py`
- **Verification:** All 8 tests pass; mypy clean for these signatures.
- **Committed in:** `3b4367a` (Task 3 commit)

**3. [Rule 3 - blocking issue] mypy-baseline gate: 5 new type errors in new files**
- **Found during:** Task 3, pre-commit verification (`mypy app/ | mypy-baseline filter --allow-unsynced`)
- **Issue:** `get_campaign_progress`'s return type (`-> dict`) and `_derive_status`'s `progress` param (`dict`) were missing generic type args; the three router endpoint functions (`create_campaign`, `campaigns_list`, `campaign_detail`) lacked return-type annotations. All 5 surfaced as genuinely NEW violations against the checked-in baseline (not present in a Task-2-only comparison).
- **Fix:** Annotated `dict[str, int]` for both the service return type and the router helper's param; added `-> CampaignCreateResponse`, `-> list[CampaignSummary]`, `-> CampaignDetail` to the three endpoints.
- **Files modified:** `backend/app/campaigns/service.py`, `backend/app/campaigns/router.py`
- **Verification:** Re-ran `mypy app/ | mypy-baseline filter --allow-unsynced` — zero campaigns-attributable errors remain (confirmed via `grep -i campaigns` on the output).
- **Committed in:** `3b4367a` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (2 source-grounding corrections, 1 blocking mypy-gate fix)
**Impact on plan:** All three were necessary for correctness (accurate imports/signatures) or to pass an existing CI-equivalent gate (mypy-baseline). No scope creep — no behavior changed beyond what the plan specified.

## Issues Encountered
- A pre-existing, unrelated `mypy-baseline.txt` drift (`app/ticketing/daily_sync.py` + a `jose`-stub `note` in `app/auth/dependencies.py`) surfaces as "new" violations on every run regardless of whether any campaigns code exists at all — confirmed via `git stash` (reverting to a Task-2-only tree state) + `rm -rf .mypy_cache` + re-run, which reproduced the identical delta. Logged to `.planning/phases/38-remediation-campaigns/deferred-items.md`; not fixed (out of scope — unrelated files, pre-existing per project memory `getvul-backend-test-harness-rot`).
- My own first smoke-test attempt to introspect `app.routes` directly for `.path` substrings reported zero campaign routes and briefly looked like a registration bug. Root cause: this FastAPI/Starlette version wraps `include_router`-included sub-routers in an internal `_IncludedRouter` proxy that has no `.path` attribute at the top level (only routes registered directly via `@app.get(...)` etc. show up that way). `app.openapi()` (which correctly walks the full route tree) confirmed all 3 campaign routes are live; this was a diagnostic-methodology mistake on my part, not a real defect — no code change was needed.

## User Setup Required
None — no external service configuration required. No new environment variables, no new dependencies (confirmed zero new packages needed, per 38-RESEARCH.md's Standard Stack analysis).

## Next Phase Readiness
- The persisted campaign identity + read contract (`Campaign` model, `GET /api/v1/campaigns`, `GET /api/v1/campaigns/{id}` response shape) is ready for Plan 02 (per-owner bulk ticketing) and Plan 03 (full progress/MTTR + lifecycle close/reactivate) to build on additively — neither needs to touch the migration, model, or the two existing service functions, only add new ones alongside them.
- Plans 04/05 (frontend: remediation-grouped entry page + campaign list/detail views) can consume the exact `CampaignSummary`/`CampaignDetail` JSON contract shipped here (`id`, `remediation_id`, `status`, `total`, `open`, `in_progress`, `done`, `pct_remediated`) with no backend changes required for a first-pass UI.
- No blockers. One thing for Plan 03's author to note: the `status` field this plan ships is a **transient, request-time-only** derivation (never persisted, never audited) — Plan 03 must decide whether to keep deriving it the same way inside a richer detail response, or introduce the real Pattern-6 lazy-on-read persistence+audit mechanism (D-13/D-19) alongside it. Both are compatible with this plan's contract; neither is precluded.

---
*Phase: 38-remediation-campaigns*
*Completed: 2026-08-17*

## Self-Check: PASSED

**Files verified to exist:**
- FOUND: backend/alembic/versions/049_add_campaigns.py
- FOUND: backend/app/campaigns/__init__.py
- FOUND: backend/app/campaigns/models.py
- FOUND: backend/app/campaigns/schemas.py
- FOUND: backend/app/campaigns/service.py
- FOUND: backend/app/campaigns/router.py
- FOUND: backend/app/main.py
- FOUND: backend/tests/test_campaigns.py
- FOUND: .planning/phases/38-remediation-campaigns/deferred-items.md

**Commits verified to exist (`git log --oneline --all`):**
- FOUND: 6008f7e (Task 2)
- FOUND: 3b4367a (Task 3)

**Test suite re-verified green:** `ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test-secret pytest backend/tests/test_campaigns.py -v` — 8/8 passed.

**Live DB constraint re-verified:** `\d+ campaigns` confirms `uq_campaign_active_remediation` as `UNIQUE, btree (tenant_id, remediation_id) WHERE closed_at IS NULL`.

**Route registration re-verified:** `app.openapi()` schema contains `GET/POST /api/v1/campaigns` and `GET /api/v1/campaigns/{campaign_id}`.
