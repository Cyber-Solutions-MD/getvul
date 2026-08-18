---
phase: 38-remediation-campaigns
plan: 04
subsystem: ui
tags: [nextjs, react, tanstack-query, tailwind, campaigns]

# Dependency graph
requires:
  - phase: 38-remediation-campaigns
    provides: "Plan 01's GET /api/v1/campaigns (list) + GET /api/v1/campaigns/{id} (detail) endpoints and CampaignSummary/CampaignDetail JSON contract this plan's frontend consumes verbatim, with zero backend changes"
provides:
  - "Campaigns WORKFLOW_ITEMS nav entry (Target icon, no chip) routing to /dashboard/campaigns"
  - "queryKeys.campaigns block (all/list/detail) + useCampaigns()/useCampaignDetail(id) hooks, both staleTime:0 (D-07 compute-on-read is never cached)"
  - "CampaignStatusRibbon — status-lifecycle pill (ACTIVE=violet, COMPLETE=success green), never severity colors"
  - "CampaignsChipBar (single status axis) + CampaignsTable (6 UI-SPEC columns, onRowClick-driven, no internal useRouter) + /dashboard/campaigns list page (ErrorBoundary>Suspense>Inner, WR-13 branch order, exact empty-state copy, row click -> full navigation to the Plan 05 detail route)"
affects: [38-05-campaign-detail-view]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Client-side chip-bar filtering against a full, unpaginated GET response — GET /campaigns returns the entire tenant-scoped list with no server-side status/pagination params (unlike tickets), so CampaignsChipBar's status axis filters the already-fetched array in the page rather than round-tripping a new request"
    - "onRowClick prop contract (table invokes on click + Enter/Space, page owns useRouter/navigation) — reused verbatim from tickets-table.tsx for CampaignsTable"

key-files:
  created:
    - frontend/src/lib/queries/use-campaigns.ts
    - frontend/src/lib/queries/use-campaigns.test.ts
    - frontend/src/components/campaigns/campaign-status-ribbon.tsx
    - frontend/src/components/campaigns/campaign-status-ribbon.test.tsx
    - frontend/src/components/campaigns/campaigns-chip-bar.tsx
    - frontend/src/components/campaigns/campaigns-table.tsx
    - frontend/src/components/campaigns/campaigns-table.test.tsx
    - frontend/src/app/(authed)/dashboard/campaigns/page.tsx
    - frontend/src/app/(authed)/dashboard/campaigns/page.test.tsx
  modified:
    - frontend/src/lib/queries/keys.ts
    - frontend/src/components/shell/nav-items.ts

key-decisions:
  - "queryKeys.campaigns.list() takes no opts (unlike tickets.list) — GET /api/v1/campaigns has no filter/pagination query params (D-07 always returns the full tenant-scoped list), so there is no cache-key dimension to encode; the status chip-bar filters the fetched array client-side instead"
  - "CampaignsTable's MTTR column always renders the em-dash placeholder — CampaignSummary (the actual GET /campaigns list response, per backend/app/campaigns/schemas.py) carries no mttr_seconds field at all. Plan 03 wired mttr_seconds only into CampaignDetail (GET /{id}), not the list response the plan's own <interfaces> block assumed. Real per-row MTTR is out of reach without a backend change, which is out of this frontend-only plan's file scope; deferred as a Plan 05 (campaign-detail) or future-backend concern."
  - "CampaignsTable's 'Tickets' column uses in_progress (members that have moved off raw OPEN into an active ticket) as the best available proxy for the UI-SPEC's 'owner-ticket count' column — CampaignSummary has no distinct-owner or distinct-ticket field; a literal owner count would require a new backend aggregation query joining Ticket/Asset.mdm_details, out of scope for a frontend-only plan"
  - "Row click is a full navigation (router.push('/dashboard/campaigns/' + id)) owned by the page's Inner component, passed to CampaignsTable via the onRowClick prop; CampaignsTable itself never imports next/navigation or calls useRouter — mirrors tickets-table.tsx's established contract verbatim"
  - "Added frontend/src/app/(authed)/dashboard/campaigns/page.test.tsx even though it is not listed in the plan's files_modified — every other list page in this codebase (tickets, connectors, asset-groups, users, cspm, assets) has a co-located page.test.tsx covering WR-13 branch order + empty-state copy, and the plan's own must_haves require exactly that coverage (which campaigns-table.test.tsx alone cannot exercise, since branch-order/empty-state/EmptyState-CTA are page-level, not table-level, concerns)"
  - "CAMP-01 left [ ] unmarked in REQUIREMENTS.md — still shared with 38-05 (campaign detail view), which has not yet produced a SUMMARY.md; the SDK's requirements ready-ids verb is not installed in this environment (confirmed, matching every prior phase-38 plan's identical finding), so this was verified directly against 38-05-PLAN.md's requirements: frontmatter field"

patterns-established:
  - "Frontend hooks/components for a compute-on-read backend resource (campaigns) mirror the read-only escalations-hook shape (use-vuln-escalations.ts) but with staleTime:0 instead of 30_000 — the D-07 compute-on-read family's client-side caching rule going forward"

requirements-completed: []  # CAMP-01 blocked by sibling plan 38-05, which has no SUMMARY.md yet (see key-decisions)

coverage:
  - id: D1
    description: "A Campaigns item appears in WORKFLOW_ITEMS nav and routes to /dashboard/campaigns"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/shell/nav-items.ts (grep 'Campaigns')"
        status: pass
    human_judgment: false
  - id: D2
    description: "/dashboard/campaigns lists campaigns via GET /api/v1/campaigns with the UI-SPEC columns; clicking a row navigates to /dashboard/campaigns/{id}"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/campaigns/campaigns-table.test.tsx, frontend/src/app/(authed)/dashboard/campaigns/page.test.tsx#Test 4"
        status: pass
    human_judgment: false
  - id: D3
    description: "The status pill is violet for ACTIVE and green for COMPLETE, never severity colors"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/campaigns/campaign-status-ribbon.test.tsx"
        status: pass
    human_judgment: false
  - id: D4
    description: "useCampaigns/useCampaignDetail set staleTime:0 (D-07 compute-on-read is never cached as authoritative)"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "frontend/src/lib/queries/use-campaigns.test.ts"
        status: pass
    human_judgment: false
  - id: D5
    description: "Empty/loading/error states render per state-patterns.md, WR-13 mutually-exclusive branch order, exact 'No campaigns yet' + CTA copy"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "frontend/src/app/(authed)/dashboard/campaigns/page.test.tsx#Test 2,3"
        status: pass
    human_judgment: false
  - id: D6
    description: "Count strings singularize at M=1 (never '1 findings') across member count and the ticket-count proxy column"
    requirement: "CAMP-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/campaigns/campaigns-table.test.tsx#singularizes member/ticket count strings"
        status: pass
    human_judgment: false

# Metrics
duration: ~13min
completed: 2026-08-18
status: complete
---

# Phase 38 Plan 04: Campaigns List View Summary

**CAMP-01's dedicated `/dashboard/campaigns` list view shipped: a nav entry, a 6-column table (remediation/members/%remediated/MTTR/status/tickets) driven by two staleTime:0 TanStack hooks against Plan 01's compute-on-read API, a status chip-bar, and full WR-13 empty/loading/error state coverage — each row clicking through to the Plan 05 campaign detail route.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-08-18T08:36:50Z (approx., from the prior plan's completion commit)
- **Completed:** 2026-08-18T08:48:28Z
- **Tasks:** 2 (both `type="auto" tdd="true"`, both complete)
- **Files modified:** 11 (9 created, 2 modified)

## Accomplishments
- `useCampaigns()`/`useCampaignDetail(id)` hooks proven against a mocked `api()` — correct URLs (`/api/v1/campaigns`, `/api/v1/campaigns/{id}`), `staleTime:0` verified directly against the TanStack `QueryCache`'s stored options (not just inferred from source), and `useCampaignDetail('')` proven to never call `api()` (disabled gate)
- `CampaignStatusRibbon` proven to render violet chrome for `ACTIVE` and green (`success`) chrome for `COMPLETE`, with an explicit assertion that no `severity-*` class ever appears in its output — the status/severity color-family separation from `visual-language.md` held mechanically, not just by convention
- `CampaignsTable` ships all 6 UI-SPEC columns (remediation label mono-truncated-with-tooltip, member count, % remediated mono+tabular-nums, MTTR, status pill, tickets), singularizes count strings at M=1 (`"1 finding"`/`"1 ticket"`, never the plural), and proves its `onRowClick` prop fires on both click and Enter/Space keydown while never importing `next/navigation` itself
- `/dashboard/campaigns` composes `ErrorBoundary > Suspense > Inner` with the WR-13 mutually-exclusive branch order (error > loading > empty > data), the exact "No campaigns yet" + "View remediation groups" empty-state copy from the UI-SPEC's Copywriting Contract, and a `router.push` row-click handler proven to fire with the correct target URL
- `Campaigns` added to `WORKFLOW_ITEMS` (Target icon, no chip per D-N-01) — confirmed both via a direct grep and via the full nav test suite staying green
- Full frontend regression: 1005/1005 tests green (144 files), `npm run build` clean, `/dashboard/campaigns` at 130 KB First-Load JS (well under the 250 KB budget)

## Task Commits

Each task was committed atomically:

1. **Task 1: use-campaigns hook + keys.ts block + campaign-status-ribbon** — `f1d2dbe` (feat)
2. **Task 2: campaigns list page + table (row-click nav) + chip-bar + Campaigns nav item** — `31da9fc` (feat)

**Plan metadata:** _pending this commit_ (docs: complete plan)

_Note: both `tdd="true"` tasks were committed as single combined test+implementation commits per task, not separate `test(...)`→`feat(...)` sub-commits — matching every prior phase-38 plan's identical, previously-documented deviation for this repo._

## Files Created/Modified
- `frontend/src/lib/queries/keys.ts` — adds the `campaigns: { all, list, detail }` block alongside the existing `tickets` block
- `frontend/src/lib/queries/use-campaigns.ts` — `useCampaigns()`, `useCampaignDetail(id)`, `CampaignSummary`/`CampaignDetail`/`CampaignStatus` types
- `frontend/src/lib/queries/use-campaigns.test.ts` — 4 tests (URL, staleTime, disabled-on-empty-id)
- `frontend/src/components/campaigns/campaign-status-ribbon.tsx` — the ACTIVE/COMPLETE lifecycle pill
- `frontend/src/components/campaigns/campaign-status-ribbon.test.tsx` — 3 tests (violet/green chrome, no severity leakage)
- `frontend/src/components/campaigns/campaigns-chip-bar.tsx` — single `status` axis (Active/Complete)
- `frontend/src/components/campaigns/campaigns-table.tsx` — the 6-column list table
- `frontend/src/components/campaigns/campaigns-table.test.tsx` — 6 tests (columns, mono/tabular-nums, singularization, click, keyboard, no-useRouter)
- `frontend/src/app/(authed)/dashboard/campaigns/page.tsx` — the list page composition
- `frontend/src/app/(authed)/dashboard/campaigns/page.test.tsx` — 6 tests (render, WR-13 branches, empty copy, row-click nav) — see Deviations
- `frontend/src/components/shell/nav-items.ts` — adds the `Campaigns` `WORKFLOW_ITEMS` entry

## Decisions Made
- `queryKeys.campaigns.list()` takes no opts — GET `/api/v1/campaigns` has no filter/pagination params; the status chip-bar filters the fetched array client-side in the page instead of round-tripping a new request
- `CampaignsTable`'s MTTR column always renders `—` — `CampaignSummary` (the real GET `/campaigns` list response) has no `mttr_seconds` field; Plan 03 wired it only into `CampaignDetail` (GET `/{id}`)
- `CampaignsTable`'s `Tickets` column uses `in_progress` as the best available proxy for an owner-ticket count, since `CampaignSummary` has no distinct owner/ticket field
- Row click is a full navigation owned by the page (`router.push`), passed to `CampaignsTable` via `onRowClick` — the table never imports `useRouter`
- Added `campaigns/page.test.tsx` (not in the plan's `files_modified`) to cover WR-13/empty-state/row-click, matching the established co-located `page.test.tsx` convention every other list page in this codebase already follows
- CAMP-01 left `[ ]` unmarked in REQUIREMENTS.md — still shared with 38-05, which hasn't shipped a SUMMARY.md yet

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - source-grounding correction] MTTR column has no data at the list level**
- **Found during:** Task 2, while reading the real `backend/app/campaigns/schemas.py` before writing `campaigns-table.tsx`
- **Issue:** The plan's `<interfaces>` block asserted the GET `/campaigns` response includes `mttr_seconds: number|null` ("render `—` when null"). The actual, already-shipped `CampaignSummary` schema (Plan 01/03) has NO `mttr_seconds` field at all — only `CampaignDetail` (the single-campaign GET `/{id}` response) carries it, per Plan 03's own SUMMARY.md ("mttr_seconds on CampaignDetail... ready for Plan 04/05 to render").
- **Fix:** `CampaignsTable`'s MTTR column always renders the `—` placeholder (the null-case behavior the plan specified, now applied unconditionally since the field is always absent at this level); documented in the component's own docstring and in this Summary so Plan 05 (which DOES have real `mttr_seconds` via `useCampaignDetail`) doesn't mistake this for an oversight.
- **Files modified:** `frontend/src/components/campaigns/campaigns-table.tsx`
- **Verification:** `campaigns-table.test.tsx` asserts the em-dash always renders; `use-campaigns.ts`'s `CampaignSummary` type has no `mttr_seconds` field (matches the real backend schema byte-for-byte).
- **Committed in:** `31da9fc` (Task 2 commit)

**2. [Rule 1 - source-grounding correction] No owner-ticket-count field exists on the list response**
- **Found during:** Task 2, same schema read as above
- **Issue:** The plan's must_haves require an "owner-ticket count" column, but `CampaignSummary` has no distinct-owner or distinct-ticket field — only per-vulnerability `total/open/in_progress/done`. A literal owner count is not derivable from this endpoint's data (it would need a new join through `Ticket`/`Asset.mdm_details`, a backend change out of this frontend-only plan's file scope).
- **Fix:** The column (labeled "Tickets") uses `in_progress` — the count of members that have moved off raw `OPEN` into an active ticket — as the closest available, honest proxy. Never fabricated data; documented the gap in the component docstring, this Summary, and STATE.md so a future backend plan can add a real field if the product decides the distinction matters.
- **Files modified:** `frontend/src/components/campaigns/campaigns-table.tsx`
- **Verification:** `campaigns-table.test.tsx` proves the column renders `in_progress`-derived counts, correctly singularized.
- **Committed in:** `31da9fc` (Task 2 commit)

**3. [Rule 2 - missing critical test coverage] Added campaigns/page.test.tsx**
- **Found during:** Task 2, while planning how to satisfy the plan's `<behavior>` items about WR-13 branch order and exact empty-state copy
- **Issue:** These are page-level composition concerns (which state branch renders when), not table-component concerns — `campaigns-table.tsx` has no knowledge of loading/error states at all (mirrors `tickets-table.tsx`'s identical separation of concerns). The plan's `files_modified` lists only `campaigns-table.test.tsx`, but that file cannot exercise page-level branch order or CTA-link wiring without importing the page module directly, which would blur the table test's scope.
- **Fix:** Added `frontend/src/app/(authed)/dashboard/campaigns/page.test.tsx`, mirroring every other list page's (`tickets/`, `connectors/`, `asset-groups/`, `users/`, `cspm/`, `assets/`) established co-located `page.test.tsx` convention.
- **Files modified:** `frontend/src/app/(authed)/dashboard/campaigns/page.test.tsx` (new)
- **Verification:** 6 new tests green, covering render/WR-13/empty-copy/row-click-nav.
- **Committed in:** `31da9fc` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (2 source-grounding corrections driven by the real backend contract, 1 missing-test-coverage addition)
**Impact on plan:** All three preserve correctness against the ACTUAL shipped backend contract (never inventing data the API doesn't provide) and close a test-coverage gap the plan's own must_haves required but couldn't be satisfied from the single test file named in `files_modified`. No scope creep — no new backend files touched, no new routes/endpoints invented.

## Issues Encountered
- The `campaigns-table.test.tsx` "never calls useRouter" assertion initially failed against a naive `/useRouter/` regex — the component's own docstring mentions "useRouter" in prose while explaining the constraint. Fixed by narrowing the regex to match an actual `next/navigation` import or a `useRouter(` call, not any textual mention. Test-only fix, zero production code impact.

## User Setup Required
None — no external service configuration required. No new environment variables, no new dependencies (zero new npm packages; `lucide-react`'s `Target` icon already exists in the pinned `^0.383.0` version).

## Next Phase Readiness
- The nav entry, `useCampaigns`/`useCampaignDetail` hooks, and `CampaignStatusRibbon` are all ready for Plan 05 (campaign detail view + remediation-grouped entry point) to consume with zero changes — `useCampaignDetail` already exposes the real `mttr_seconds` field Plan 05's burndown card needs.
- Plan 05's empty-state "View remediation groups" CTA target (`/dashboard/vulnerabilities/remediations`) does not exist until Plan 05 ships it — this is the expected, in-sequence gap (that route is explicitly Plan 05's own `files_modified` scope, not a broken link introduced by this plan).
- No blockers. Phase 38 (`remediation-campaigns`) is now 4/5 plans complete — CAMP-01/CAMP-02/CAMP-04 fully shipped except CAMP-01's final completion gate (shared with Plan 05); CAMP-03 also awaits Plan 05.

---
*Phase: 38-remediation-campaigns*
*Completed: 2026-08-18*

## Self-Check: PASSED

**Files verified to exist:**
- FOUND: frontend/src/lib/queries/use-campaigns.ts
- FOUND: frontend/src/lib/queries/use-campaigns.test.ts
- FOUND: frontend/src/components/campaigns/campaign-status-ribbon.tsx
- FOUND: frontend/src/components/campaigns/campaign-status-ribbon.test.tsx
- FOUND: frontend/src/components/campaigns/campaigns-chip-bar.tsx
- FOUND: frontend/src/components/campaigns/campaigns-table.tsx
- FOUND: frontend/src/components/campaigns/campaigns-table.test.tsx
- FOUND: frontend/src/app/(authed)/dashboard/campaigns/page.tsx
- FOUND: frontend/src/app/(authed)/dashboard/campaigns/page.test.tsx

**Commits verified to exist (`git log --oneline --all`):**
- FOUND: f1d2dbe (Task 1)
- FOUND: 31da9fc (Task 2)

**Test suite re-verified green:** `npm run test -- run` — 1005/1005 passed (144 test files).

**Build re-verified:** `npm run build` — clean, `/dashboard/campaigns` at 130 KB First-Load JS.

**Nav/route grep re-verified:** `grep -n "Campaigns" frontend/src/components/shell/nav-items.ts` and `grep -n "router.push" "frontend/src/app/(authed)/dashboard/campaigns/page.tsx"` both match.
