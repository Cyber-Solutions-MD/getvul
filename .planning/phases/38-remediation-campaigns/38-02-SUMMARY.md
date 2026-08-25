---
phase: 38-remediation-campaigns
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, ticketing, dispatch, rbac, audit, campaigns]

# Dependency graph
requires:
  - phase: 38-remediation-campaigns
    provides: "Plan 01's persisted Campaign identity row + get_or_create_campaign/get_campaign_progress/list_campaigns + RBAC/audit/tenant-scoping precedent this plan builds on additively"
provides:
  - "bulk_create_campaign_tickets() -- per-owner re-carve of create_remediation_ticket()'s single-ticket-for-the-whole-group shape into N-tickets-one-per-owner, each owner's members sharing one external_ticket_url"
  - "D-06 adoption: per-vulnerability unresolved-Ticket exclusion (not the group-level created_by_rule check create_remediation_ticket uses) so already-ticketed findings are counted, never duplicated"
  - "D-08 unassigned bucket: an owner-less finding (no asset.mdm_details.humaans_email) still gets ticketed, in the None-owner bucket, never silently dropped"
  - "D-20/Pitfall 1 closure: campaign tickets set created_by_rule to the bare campaign.remediation_id (never a 'campaign:{id}' prefix), so a later per_remediation automation rule's own group-level dedup check sees them and will not double-ticket"
  - "POST /api/v1/campaigns/{campaign_id}/bulk-assign -- require_analyst-gated, tenant-scoped 404, audited on EVERY run (including a no-op rerun that tickets nobody)"
  - "CampaignBulkAssignRequest schema (extra=forbid, provider pattern-validated to ASANA|JIRA|GITHUB)"
  - "_get_campaign_ticketing_client() -- tenant-scoped ConnectorConfig lookup + Fernet-decrypt + build_ticketing_client dispatch, scoped local to campaigns/router.py"
affects: [38-03-lifecycle-mttr, 38-04-remediation-grouped-page, 38-05-campaign-views]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-owner ticket carve-up: group live members by owner_email, one client.create() call per owner bucket, N Ticket rows sharing that owner's returned url -- Ticket.vulnerability_id stays singular (Pitfall 4), never an array/join-table"
    - "D-06 adoption uses a per-vulnerability existence check (Ticket.vulnerability_id.in_(...), resolved_at IS NULL) -- deliberately NOT create_remediation_ticket()'s coarser group-level created_by_rule==remediation_id check, which is the exact asymmetry Pitfall 1 warns about"
    - "A tenant-scoped ticketing-client resolver duplicated locally in campaigns/router.py (not imported cross-router from ticketing/router.py::_get_ticketing_client) -- kept in-scope since this plan's file list didn't include ticketing/router.py, and campaign bulk-assign's project_key is always caller-supplied (no connector-config fallback needed, unlike the ticketing router's version)"

key-files:
  created: []
  modified:
    - backend/app/campaigns/service.py
    - backend/app/campaigns/schemas.py
    - backend/app/campaigns/router.py
    - backend/tests/test_campaigns.py

key-decisions:
  - "D-06 adoption check is per-vulnerability (Ticket.vulnerability_id IN (...) AND resolved_at IS NULL), never create_remediation_ticket()'s group-level created_by_rule==remediation_id check -- this is the plan's own explicit instruction (interfaces block step 2) and is what makes campaign bulk-assign safely idempotent across reruns with mixed old/new members"
  - "created_by_rule is set to the BARE campaign.remediation_id, never a 'campaign:{id}'-prefixed string -- closes 38-RESEARCH.md Pitfall 1 (a later per_remediation automation rule's own dedup check does an exact string match against the bare remediation_id and would otherwise double-ticket campaign members)"
  - "_get_campaign_ticketing_client is a small, locally-scoped duplicate of ticketing/router.py::_get_ticketing_client's ConnectorConfig-lookup/decrypt/build_ticketing_client shape, not a cross-router import or a refactor extracting shared code -- kept within this plan's declared file scope (campaigns/service.py, schemas.py, router.py, tests/test_campaigns.py only); ticketing/router.py was not touched"
  - "CampaignBulkAssignRequest.provider uses the same Field(..., pattern='^(ASANA|JIRA|GITHUB)$') convention as ticketing/schemas.py's TicketCreateRequest.provider, not a bare `str`, for input-validation parity with the existing ticketing surface"
  - "CAMP-02 and CAMP-04 left [ ] unmarked in REQUIREMENTS.md -- both are shared with sibling plans that haven't produced a SUMMARY.md yet (CAMP-02 also declared by 38-05; CAMP-04 also declared by 38-01/38-03, and 38-01 itself left CAMP-04 unmarked for the identical reason). Confirmed by inspecting every phase-38 plan's frontmatter `requirements:` field directly (the SDK's requirements ready-ids verb is not installed in this environment)."

patterns-established:
  - "Bulk per-owner ticket-carve-up service functions accept an already-resolved TicketingClient (never build one themselves) and a `campaign` model instance (not just its id/remediation_id string) -- callers own client resolution + campaign lookup, service owns only the ticketing business logic"

requirements-completed: []  # CAMP-02 blocked by 38-05 (no SUMMARY.md yet); CAMP-04 blocked by 38-01/38-03 (neither marks it complete either) -- see key-decisions

coverage:
  - id: D1
    description: "3 findings across 2 distinct owners -> exactly 2 external_ticket_urls; each owner's findings share only their own owner's url (D-04)"
    requirement: "CAMP-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_bulk_assign_one_ticket_per_owner"
        status: pass
    human_judgment: false
  - id: D2
    description: "Owner assignment is read from asset.mdm_details['humaans_email'] using the SAME derivation as ticketing/service.py:614, byte-identical, never a new resolver (D-05)"
    requirement: "CAMP-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_owner_derivation_matches_ticketing_service"
        status: pass
    human_judgment: false
  - id: D3
    description: "An owner-less finding (no humaans_email) still gets ticketed in the None/unassigned bucket, assignee NULL -- never silently dropped (D-08)"
    requirement: "CAMP-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_bulk_assign_unassigned_bucket"
        status: pass
    human_judgment: false
  - id: D4
    description: "bulk-assign writes exactly one campaign.bulk_assign audit row on EVERY run, including a second no-op rerun that tickets nobody (D-10)"
    requirement: "CAMP-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_bulk_assign_endpoint_audited_every_run"
        status: pass
    human_judgment: false
  - id: D5
    description: "Campaign-created Ticket rows set created_by_rule == campaign.remediation_id (bare string, no 'campaign:' prefix) -- D-20/Pitfall 1 rule-engine double-ticket gap closed"
    requirement: "CAMP-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_bulk_assign_one_ticket_per_owner"
        status: pass
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_bulk_assign_unassigned_bucket"
        status: pass
    human_judgment: false
  - id: D6
    description: "bulk-assign requires require_analyst -- a viewer gets 403"
    requirement: "CAMP-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_bulk_assign_viewer_forbidden"
        status: pass
    human_judgment: false
  - id: D7
    description: "Re-running bulk-assign adopts findings already linked to an unresolved Ticket (no duplicate); tickets only the newcomers (D-06/D-10)"
    requirement: "CAMP-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_bulk_assign_adopts_existing_ticket"
        status: pass
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_bulk_assign_idempotent_rerun"
        status: pass
    human_judgment: false
  - id: D8
    description: "An unknown/cross-tenant campaign_id 404s on bulk-assign (T-38-01 tenant-scoped lookup, IDOR defense)"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_bulk_assign_unknown_campaign_404"
        status: pass
    human_judgment: false

# Metrics
duration: ~35min
completed: 2026-08-18
status: complete
---

# Phase 38 Plan 02: Per-Owner Bulk Ticketing Summary

**Re-carved `create_remediation_ticket()`'s single-ticket-for-the-whole-group shape into `bulk_create_campaign_tickets()` — one ticket PER OWNER via `POST /api/v1/campaigns/{id}/bulk-assign`, reusing owner routing verbatim, adopting already-ticketed findings, bucketing owner-less findings as unassigned, and closing the rule-engine double-ticket gap by sharing the bare `remediation_id` as `created_by_rule`.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-08-18 (session start)
- **Completed:** 2026-08-18T10:44:32+03:00
- **Tasks:** 2 (both `type="auto" tdd="true"`, both complete)
- **Files modified:** 4 (0 created, 4 modified)

## Accomplishments
- `bulk_create_campaign_tickets()` proven to carve N campaign findings into exactly one ticket per distinct owner — 3 findings across 2 owners produces exactly 2 `external_ticket_url`s, each covering only that owner's members, with `Ticket.vulnerability_id` staying singular (N rows share one URL, never an array/join-table, Pitfall 4)
- Owner derivation proven byte-identical to `ticketing/service.py:614`'s `(mdm or {}).get("humaans_email")` for the same asset fixture — no new resolver introduced (D-05)
- Owner-less findings proven to land in a real ticket (assignee `NULL`, default project) rather than being dropped (D-08)
- D-06 adoption proven idempotent across two live scenarios: a finding pre-linked to an unresolved `Ticket` from a *different* rule is adopted with zero new ticket; a rerun after a newcomer arrives tickets only the newcomer while the original member's `Ticket` row count stays at exactly 1
- D-10 proven live at the HTTP layer: a `campaign.bulk_assign` audit row lands on the first (ticketing) run AND on a second no-op rerun that tickets nobody — never gated on `created_tickets > 0`
- D-20/Pitfall 1 proven: every campaign-created `Ticket.created_by_rule` equals the bare `campaign.remediation_id`, matching `create_remediation_ticket()`'s own dedup-check convention exactly, so a later `per_remediation` automation rule on the same `remediation_id` will see these rows and skip re-ticketing
- RBAC + tenant-isolation proven: viewer 403 on bulk-assign; unknown/cross-tenant `campaign_id` 404s via the existing `_get_campaign_or_404` tenant-scoped WHERE clause
- `POST /api/v1/campaigns/{campaign_id}/bulk-assign` registered and live — confirmed via `app.openapi()`'s generated schema alongside Plan 01's two routes

## Task Commits

Each task was committed atomically:

1. **Task 1: bulk_create_campaign_tickets service (per-owner carve-up, adopt, D-08 bucket)** — `1e86355` (feat)
2. **Task 2: bulk-assign schema + router endpoint (require_analyst + audit every run)** — `6eaea9e` (feat)

**Plan metadata:** _pending this commit_ (docs: complete plan)

_Note: both `tdd="true"` tasks were committed as single combined test+implementation commits per task (tests were written and passing against the implementation before each commit), not separate `test(...)`→`feat(...)` sub-commits — mirrors the same deviation Plan 01 documented for the identical reason (tests and implementation were developed together against a live re-carve target, not in a strict RED-before-GREEN sequence with intermediate failing-test commits)._

## Files Created/Modified
- `backend/app/campaigns/service.py` — adds `bulk_create_campaign_tickets()` (per-owner carve-up: live-member select, D-06 per-vulnerability adopt-exclude, owner grouping, per-owner `client.create()` + N-Ticket-rows-share-one-url linkage, `recompute_ticket_sla` reuse) and `_build_owner_ticket_description()` helper; imports `SEVERITY_SLA_DAYS`/`_extract_ref`/`_provider_create_kwargs`/`recompute_ticket_sla` from `ticketing/service.py` verbatim
- `backend/app/campaigns/schemas.py` — adds `CampaignBulkAssignRequest` (`extra="forbid"`, `provider` pattern-validated, `project_key` required, `due_days` optional bounded 1-365)
- `backend/app/campaigns/router.py` — adds `POST /{campaign_id}/bulk-assign` (require_analyst, tenant-scoped 404, audit-every-run, commit) and `_get_campaign_ticketing_client()` (tenant-scoped `ConnectorConfig` lookup + Fernet-decrypt + `build_ticketing_client` dispatch)
- `backend/tests/test_campaigns.py` — 8 new tests: 5 service-level (`test_bulk_assign_one_ticket_per_owner`, `test_bulk_assign_unassigned_bucket`, `test_bulk_assign_adopts_existing_ticket`, `test_bulk_assign_idempotent_rerun`, `test_owner_derivation_matches_ticketing_service`) + 3 router-level (`test_bulk_assign_endpoint_audited_every_run`, `test_bulk_assign_viewer_forbidden`, `test_bulk_assign_unknown_campaign_404`), plus local `FakeTicketingClient`/`_seed_connector`/`_seed_asset` test helpers (16/16 file total, up from Plan 01's 8)

## Decisions Made
- D-06 adoption uses a per-vulnerability existence check (`Ticket.vulnerability_id.in_(...) AND resolved_at IS NULL`), never `create_remediation_ticket()`'s coarser group-level `created_by_rule == remediation_id` check — this was the plan's own explicit instruction and is what makes campaign bulk-assign correctly idempotent when only *some* members have prior tickets from unrelated sources
- `created_by_rule` is the bare `campaign.remediation_id`, never a `"campaign:{id}"`-prefixed string — closes 38-RESEARCH.md Pitfall 1 so a later `per_remediation`-mode automation rule's own dedup check sees campaign-created tickets and does not double-ticket
- `_get_campaign_ticketing_client` duplicates (rather than cross-router-imports) `ticketing/router.py::_get_ticketing_client`'s tenant-scoped lookup/decrypt/dispatch shape, kept local to `campaigns/router.py` since this plan's declared file scope excludes `ticketing/router.py` and campaign bulk-assign's `project_key` is always caller-supplied (no connector-config-fallback branch needed, unlike the ticketing router's more general version)
- `CampaignBulkAssignRequest.provider` uses `Field(..., pattern="^(ASANA|JIRA|GITHUB)$")`, matching `ticketing/schemas.py`'s `TicketCreateRequest.provider` convention exactly, rather than a bare `str`
- CAMP-02/CAMP-04 left `[ ]` unmarked in REQUIREMENTS.md — CAMP-02 is also declared by 38-05 (no SUMMARY.md yet); CAMP-04 is also declared by 38-01/38-03 (38-01 itself left it unmarked for the same reason). Verified directly against every phase-38 `PLAN.md`'s `requirements:` frontmatter field, since the SDK's `requirements ready-ids` verb is not installed in this environment (only `requirements mark-complete` is available via the `gsd-tools.cjs` fallback)

## Deviations from Plan

None — plan executed exactly as written. `bulk_create_campaign_tickets()`'s shape, the D-06/D-08/D-20 handling, and the router's audit-every-run wiring all match the plan's `<interfaces>` block and `38-RESEARCH.md` Pattern 4 / Code Example 4 verbatim, with the one pre-declared naming convention already established by Plan 01 (`tenant_id`/`user_id` as separate scalar params rather than a whole `user` object).

## Issues Encountered
- Postgres/Redis for local test execution were not running at session start — the project's `getvul-postgres-1`/`getvul-redis-1` Docker containers (from a prior session) existed but were stopped; started via `docker start getvul-postgres-1 getvul-redis-1` (already at migration head `049_add_campaigns`, no fresh migration run needed). Not a plan defect — an environment-setup step outside the plan's scope.
- The GSD SDK's `requirements ready-ids` verb is not installed in this environment (`node .../sdk/dist/cli.js query requirements.ready-ids` falls back to `gsd-tools.cjs`, which only exposes `requirements mark-complete`). Worked around by reading every phase-38 `PLAN.md`'s `requirements:` frontmatter field directly to confirm CAMP-02/CAMP-04's shared-plan blocking status — same conclusion the missing verb would have produced. Logged here for visibility; not fixed (SDK installation is out of this plan's scope).
- A pre-existing, unrelated `mypy-baseline.txt` drift (`app/ticketing/daily_sync.py`'s 6 untyped-function/call violations + a `jose`-stub `note` line in `app/auth/dependencies.py`) surfaces as "new" on every `mypy-baseline filter --allow-unsynced` run regardless of whether any campaigns code exists — reconfirmed via `git stash` (reverting to a Plan-1-only tree state) + rerun, which reproduced the byte-identical 9-fixed/9-new delta. This is the exact same flake Plan 01 logged and the project memory `getvul-backend-test-harness-rot` describes; not fixed (out of scope — unrelated files).

## User Setup Required
None — no external service configuration required. No new environment variables, no new dependencies (zero new packages; reuses `app.ticketing.dispatch`/`app.ticketing.service` verbatim).

## Next Phase Readiness
- `bulk_create_campaign_tickets()` and `POST /{id}/bulk-assign` are ready for Plan 04 (remediation-grouped entry page) and Plan 05 (campaign list/detail views) to wire a "Bulk-assign" action against, with no backend changes required for a first-pass UI — the response shape (`created_tickets`, `tickets_linked`, `adopted`, `owners`, `failed_owners`) is stable and can drive a partial-failure banner (`failed_owners`) directly.
- Plan 03 (CAMP-03, full progress/MTTR + lifecycle close/reactivate) is unaffected by this plan — no shared files, no shared service functions. Plan 03's `close_campaign` endpoint can be added to `campaigns/router.py` alongside `bulk_assign_campaign` with zero conflict.
- No blockers. One thing for Plan 05's UI author to note: `failed_owners` is a `list[str | None]` (the `None` entry represents the unassigned bucket failing, not a missing owner name) — the UI should render it as "Unassigned" rather than blank/null in any partial-failure list.

---
*Phase: 38-remediation-campaigns*
*Completed: 2026-08-18*

## Self-Check: PASSED

**Files verified to exist:**
- FOUND: backend/app/campaigns/service.py
- FOUND: backend/app/campaigns/schemas.py
- FOUND: backend/app/campaigns/router.py
- FOUND: backend/tests/test_campaigns.py

**Commits verified to exist (`git log --oneline --all`):**
- FOUND: 1e86355 (Task 1)
- FOUND: 6eaea9e (Task 2)

**Test suite re-verified green:** `ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test-secret pytest backend/tests/test_campaigns.py -v` — 16/16 passed.

**Route registration re-verified:** `app.openapi()` schema contains `POST /api/v1/campaigns/{campaign_id}/bulk-assign` alongside Plan 01's two routes.

**mypy-baseline re-verified:** `mypy app/ | mypy-baseline filter --allow-unsynced` shows zero campaigns-attributable new violations (confirmed via `grep -i campaign` on the filtered output); the 9-new/9-fixed drift present is byte-identical to a `git stash`-reverted clean-HEAD run (pre-existing, unrelated to this plan).
