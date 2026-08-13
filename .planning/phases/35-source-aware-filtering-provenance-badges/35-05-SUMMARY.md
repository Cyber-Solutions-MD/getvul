---
phase: 35-source-aware-filtering-provenance-badges
plan: 05
subsystem: ui
tags: [react, nextjs, tailwind, url-state, chip-bar, provenance]

# Dependency graph
requires:
  - phase: 35-source-aware-filtering-provenance-badges
    plan: 02
    provides: "SourceBadgeGroup (frontend/src/components/vulnerabilities/source-badge-group.tsx) + the chip-bar OR/AND source_mode toggle pattern (sibling row beneath <ChipBar>, copy-voice-compliant 'Any selected'/'All selected' labels)"
  - phase: 35-source-aware-filtering-provenance-badges
    plan: 03
    provides: "Assets backend: SCANNER_SOURCES/ENRICHMENT_SOURCES partition, ?scanner=/?enrichment_source=/?source_mode= query params, sources/sources_count on every asset row"
  - phase: 35-source-aware-filtering-provenance-badges
    plan: 04
    provides: "CSPM ?source_mode= true multi-tool corroboration + sources/sources_count on MisconfigSummary; Tickets real OR-default ?source= filter + transitive union sources/sources_count on TicketSummary"
provides:
  - "SourceBadgeGroup rendered on Assets rows, CSPM finding cards, and Ticket rows — the SAME shared component (Plan 02) consuming each surface's own sources/sources_count API fields; a single-source entity never reads as 'confirmed' on any of the 4 entities Phase 35 touches"
  - "Assets chip-bar: the stale single source axis is now TWO axes (scanner + enrichment_source), with an OR/AND ?source_mode toggle on the scanner axis only"
  - "CSPM: OR/AND ?source_mode toggle wired end-to-end (page -> use-cspm-findings -> backend Plan 04 contract)"
  - "Tickets: a REAL server-filtering ?source= chip axis (OR-default, no AND toggle) distinct from the display-only SourceBadgeGroup on rows"
affects: [v4.0-close, 36-if-any-followup]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SourceBadgeGroup reuse verbatim across 4 surfaces (Vulnerabilities/Assets/CSPM/Tickets) with zero changes to the component itself — only what each surface feeds it (sources[]/count) differs"
    - "OR/AND source_mode toggle as a sibling row beneath the generic <ChipBar>, reading the same selected-source list the axis itself uses so it self-disables below 2 selections — replicated identically on Assets (scanner axis) and CSPM (source axis); Tickets deliberately omits it (SRC-04 scope)"

key-files:
  created:
    - frontend/src/components/tickets/tickets-chip-bar.test.tsx
  modified:
    - frontend/src/components/assets/assets-chip-bar.tsx
    - frontend/src/components/assets/assets-chip-bar.test.tsx
    - frontend/src/components/assets/assets-table.tsx
    - frontend/src/components/assets/assets-table.test.tsx
    - frontend/src/components/assets/microcopy.ts
    - frontend/src/lib/queries/use-assets.ts
    - frontend/src/lib/queries/use-assets.test.ts
    - frontend/src/app/(authed)/dashboard/assets/page.tsx
    - frontend/src/app/(authed)/dashboard/cspm/page.tsx
    - frontend/src/app/(authed)/dashboard/cspm/page.test.tsx
    - frontend/src/components/cspm/finding-card.tsx
    - frontend/src/components/cspm/finding-card.test.tsx
    - frontend/src/components/cspm/microcopy.ts
    - frontend/src/lib/queries/use-cspm-findings.ts
    - frontend/src/lib/queries/use-cspm-findings.test.ts
    - frontend/src/components/tickets/tickets-chip-bar.tsx
    - frontend/src/components/tickets/tickets-table.tsx
    - frontend/src/components/tickets/tickets-table.test.tsx
    - frontend/src/lib/queries/use-tickets.ts
    - frontend/src/lib/queries/use-tickets.test.ts
    - frontend/src/app/(authed)/dashboard/tickets/page.tsx

key-decisions:
  - "The ticket chip-bar's source axis is a REAL server filter (confirmed): TicketsFilters.source flows through buildSearchParams as REPEATED ?source= params (matching the backend's `source: list[str] | None = Query(None)` shape, NOT the comma-joined single-param shape the other 3 ticket axes use in this same function) and reaches Plan 04's real backend OR-default filter. This is explicitly distinct from the SourceBadgeGroup shown on each ticket row, which is a DISPLAY of transitive union provenance and has no filtering effect."
  - "SourceBadgeGroup placement per surface: Assets — desktop `<td data-col=sources>` + mobile Row-3 cluster (replacing the old plain mono-chip rendering). CSPM — inline in FindingCard's content column, between resource_id and the framework tags. Tickets — inside the existing Provider `<td>`/mobile-card-header cluster, alongside (not replacing) ProviderMark, since the two marks represent genuinely different provenance concepts (ticket's own issue-tracker provider vs. the linked vuln's scanner provenance)."
  - "Deviation (Rule 3, blocking, all 3 tasks): the plan's files_modified list only names the chip-bar/table/card presentation files, but wiring a NEW chip-bar axis or toggle to actually reach the backend requires touching the surface's query-hook file (use-assets.ts / use-cspm-findings.ts / use-tickets.ts) and its page.tsx (Assets, Tickets — CSPM's page.tsx was already in-scope). Without these, the new UI controls would write URL params that are silently never read into the TanStack query, i.e. a cosmetically-complete but functionally inert filter — directly contradicting the plan's own success criteria ('SRC-02/03/04: real per-entity OR/AND scanner-source filtering'). Applied Rule 3 (auto-fix blocking issue) rather than shipping dead UI controls; documented per-task below."
  - "Confirmed all 4 entities now share the identical non-overclaiming behavior: a single-scanner Asset/CSPM-finding/Ticket renders exactly like a single-scanner Vulnerability (Plan 02) — one neutral provider mark, zero 'confirmed'/checkmark chrome — verified directly by dedicated tests on each of the 3 new surfaces (not just inherited by inspection)."
  - "Stale-source-literal gate (`TENABLE`/`AWS_INSPECTOR`/`MOCK`) is satisfied for all PRODUCTION source files under `components/{assets,vulnerabilities}/`; the only remaining occurrences are in *.test.tsx negative-test fixtures that assert those values are excluded (identical precedent to Plan 02's own chip-bar.test.tsx and vuln-table.test.tsx, both already on main) — a literal directory-wide grep including test files would flag these, but they are intentional proof-of-exclusion fixtures, not stale production data."

patterns-established:
  - "Query-hook + page.tsx co-requirement for any new chip-bar axis: a ChipAxis/toggle wired only in the presentation component is inert without a matching filter field in the surface's `use-X.ts` (Filters type + buildSearchParams) AND the page reading the URL state into that filter — noted here for any future phase adding a new filterable axis to Assets/CSPM/Tickets/Vulnerabilities."

requirements-completed: [SRC-01, SRC-02, SRC-03, SRC-04]

coverage:
  - id: D1
    description: "Assets chip-bar splits the single stale source axis into a `scanner` axis (?scanner=, OR/AND ?source_mode toggle) and an independent `enrichment_source` facet (?enrichment_source=, plain OR, no toggle) — the stale TENABLE/AWS_INSPECTOR/MOCK values are gone from the scanner allow-list"
    requirement: "SRC-03"
    verification:
      - kind: unit
        ref: "frontend/src/components/assets/assets-chip-bar.test.tsx (5-axes label test, scanner/enrichment facet-derivation tests, stale-value exclusion test, OR/AND toggle disabled/enabled/copy tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "SourceBadgeGroup renders on Assets rows (desktop + mobile), consuming row.sources/row.sources_count; single vs multi-scanner never reads as 'confirmed'"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/assets/assets-table.test.tsx#'renders SourceBadgeGroup: multi-source corroborated for row1, single neutral for row2'"
        status: pass
    human_judgment: false
  - id: D3
    description: "CSPM page exposes an OR/AND ?source_mode toggle on the source axis, disabled below 2 selected sources, copy-voice-compliant (no AND/OR jargon), reaching Plan 04's real backend corroboration filter"
    requirement: "SRC-04"
    verification:
      - kind: unit
        ref: "frontend/src/app/(authed)/dashboard/cspm/page.test.tsx#'renders the source_mode toggle, disabled by default...'"
        status: pass
    human_judgment: false
  - id: D4
    description: "CSPM finding cards render SourceBadgeGroup (group sources over (rule_id,resource_id)), falling back to [finding.source] for pre-Plan-04 response shapes"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/cspm/finding-card.test.tsx#'renders SourceBadgeGroup: single neutral...'/'...multi-source corroborated...'/'...falls back to [finding.source]...'"
        status: pass
    human_judgment: false
  - id: D5
    description: "Tickets chip-bar exposes a REAL server-filtering source axis (?source=, OR-default, 6 real VulnSource values), with NO AND toggle (SRC-04 scoped to Vulnerabilities/Assets/CSPM)"
    requirement: "SRC-02"
    verification:
      - kind: unit
        ref: "frontend/src/components/tickets/tickets-chip-bar.test.tsx (5-axes label test, static-fallback + facet-derived chip tests, data-axis test, no-AND-toggle test)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Ticket rows render SourceBadgeGroup (transitive union provenance) alongside — and visually distinct from — the existing ticket-provider mark; empty-source state renders the neutral em-dash, never a crash"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/tickets/tickets-table.test.tsx#'renders SourceBadgeGroup (transitive union provenance) distinct from ProviderMark'/'renders the neutral empty-source state...'"
        status: pass
    human_judgment: false
  - id: D7
    description: "The new filter axes are wired end-to-end, not just presentational: use-assets.ts/use-cspm-findings.ts/use-tickets.ts + their pages thread the new params into the actual TanStack query"
    verification:
      - kind: unit
        ref: "frontend/src/lib/queries/use-assets.test.ts (scanner/enrichment_source/source_mode param tests), frontend/src/lib/queries/use-cspm-findings.test.ts#'buildCspmParams' source_mode test, frontend/src/lib/queries/use-tickets.test.ts (repeated-source-param + allow-list-clamp tests)"
        status: pass
    human_judgment: false
  - id: D8
    description: "Manual visual verification that all 4 surfaces (Vulnerabilities + the 3 this plan touches) render single vs multi source consistently on a live page, never 'confirmed'; OR/AND toggles disable below 2; empty/loading/error states intact"
    verification: []
    human_judgment: true
    rationale: "Deferred to phase UAT per the plan's own <verification> block — this execution session ran component/unit-level tests + tsc/eslint only, no live-browser check."

duration: 32min
completed: 2026-08-12
status: complete
---

# Phase 35 Plan 05: Frontend Expansion — Assets/CSPM/Tickets Summary

**Replicated Plan 02's proven SourceBadgeGroup + OR/AND chip-bar toggle pattern verbatim across Assets (scanner/enrichment axis split), CSPM (true multi-tool corroboration toggle), and Tickets (a real server-filtering source axis, OR-only) — closing v4.0's SRC-01..04 across all four triage entities.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-08-12T14:47:00Z (approx, context load)
- **Completed:** 2026-08-12T15:19:00Z
- **Tasks:** 3
- **Files modified:** 21 (1 new test file, 20 modified)

## Accomplishments

- **Assets:** split `assets-chip-bar.tsx`'s single stale `source` axis (still carrying the fake `TENABLE`/`AWS_INSPECTOR`/`MOCK` values) into a `scanner` axis (real 6-value set, `?scanner=`, OR/AND `?source_mode` toggle) and an independent `enrichment_source` facet (`JAMF`/`HUMAANS`/`INTUNE`, plain OR, no toggle) — mirroring the backend partition Plan 03 shipped. Wired `SourceBadgeGroup` into `assets-table.tsx`'s desktop and mobile row clusters.
- **CSPM:** added the OR/AND `?source_mode` toggle to `cspm/page.tsx` (identical shape/copy to Plan 02's vuln chip-bar toggle — disabled below 2 selected sources), and wired `SourceBadgeGroup` into `finding-card.tsx` (group sources over the finding's `(rule_id, resource_id)` corroboration group).
- **Tickets:** added a REAL server-filtering `source` chip axis to `tickets-chip-bar.tsx` (`?source=`, OR-default, reaching Plan 04's real backend filter — confirmed by tracing `buildSearchParams`'s repeated-param shape through to the router's `list[str] Query` binding) and wired `SourceBadgeGroup` into `tickets-table.tsx`'s rows, placed alongside (not replacing) the existing ticket `ProviderMark` since they represent different provenance concepts.
- **Necessary plumbing beyond the plan's stated files (Rule 3):** all three new/extended chip-bar controls would have been inert without threading their filter values through each surface's query hook (`use-assets.ts`, `use-cspm-findings.ts`, `use-tickets.ts`) and page (`assets/page.tsx`, `tickets/page.tsx` — `cspm/page.tsx` was already in-scope). Did this for all three surfaces so the UI controls are real, not cosmetic.
- Full frontend regression suite green: `npx vitest run` — 139 test files, 961 tests passed (175 in the 4 touched surfaces' own directories). `npx tsc --noEmit` clean. `npx eslint src/` — 0 errors (6 pre-existing unrelated warnings, untouched by this plan).

## Task Commits

Each task was committed atomically:

1. **Task 1: Assets — split scanner/enrichment chip axes + source_mode toggle + SourceBadgeGroup on rows** - `a175cf4` (feat)
2. **Task 2: CSPM — scanner-source chip axis + OR/AND source_mode toggle + SourceBadgeGroup on finding cards** - `6a689fd` (feat)
3. **Task 3: Tickets — scanner-source provenance chip axis + SourceBadgeGroup on ticket rows** - `ebbf094` (feat)

**Plan metadata:** _committed alongside this SUMMARY._

## Files Created/Modified

- `frontend/src/components/assets/assets-chip-bar.tsx` - scanner/enrichment_source axis split + OR/AND `source_mode` toggle (mirrors Plan 02 verbatim)
- `frontend/src/components/assets/assets-chip-bar.test.tsx` - 5-axes labels, scanner/enrichment facet-derivation, stale-value exclusion, toggle disabled/enabled/copy tests
- `frontend/src/components/assets/assets-table.tsx` - `SourceBadgeGroup` wired into desktop `<td>` + mobile Row-3 cluster
- `frontend/src/components/assets/assets-table.test.tsx` - `sources`/`sources_count` fixtures + multi/single SourceBadgeGroup assertion
- `frontend/src/components/assets/microcopy.ts` - `chips.scanner`/`enrichment_source` labels + `sourceMode*` copy (mirrors vuln microcopy)
- `frontend/src/lib/queries/use-assets.ts` - `AssetsFilters.scanner`/`enrichment_source`/`source_mode`, `AssetSummary.sources`/`sources_count`, `buildSearchParams` wiring
- `frontend/src/lib/queries/use-assets.test.ts` - scanner/enrichment_source/source_mode param serialization tests
- `frontend/src/app/(authed)/dashboard/assets/page.tsx` - reads `?scanner=`/`?enrichment_source=`/`?source_mode=` and threads into `useAssets` filters
- `frontend/src/app/(authed)/dashboard/cspm/page.tsx` - OR/AND `source_mode` toggle UI + filter wiring
- `frontend/src/app/(authed)/dashboard/cspm/page.test.tsx` - toggle disabled-by-default + no-jargon test
- `frontend/src/components/cspm/finding-card.tsx` - `SourceBadgeGroup` wired in, with pre-Plan-04 fallback
- `frontend/src/components/cspm/finding-card.test.tsx` - single/multi/fallback SourceBadgeGroup tests
- `frontend/src/components/cspm/microcopy.ts` - `chips.sourceMode*` copy (mirrors vuln microcopy)
- `frontend/src/lib/queries/use-cspm-findings.ts` - `CspmFilters.source_mode`, `MisconfigSummary.sources`/`sources_count`, `buildCspmParams` wiring
- `frontend/src/lib/queries/use-cspm-findings.test.ts` - `buildCspmParams` source_mode test
- `frontend/src/components/tickets/tickets-chip-bar.tsx` - new real `source` filter axis (6 real values, `?source=`, no AND toggle)
- `frontend/src/components/tickets/tickets-chip-bar.test.tsx` - NEW file: 5-axes labels, static-fallback + facet-derived chips, data-axis, no-toggle tests
- `frontend/src/components/tickets/tickets-table.tsx` - `SourceBadgeGroup` wired into desktop + mobile rows, alongside `ProviderMark`
- `frontend/src/components/tickets/tickets-table.test.tsx` - `sources`/`sources_count` fixture + multi-source/empty-state SourceBadgeGroup tests
- `frontend/src/lib/queries/use-tickets.ts` - `TicketsFilters.source`, `TicketSummary.sources`/`sources_count`, `buildSearchParams` (repeated-param shape)
- `frontend/src/lib/queries/use-tickets.test.ts` - repeated-source-param + allow-list-clamp tests
- `frontend/src/app/(authed)/dashboard/tickets/page.tsx` - reads `?source=` and threads into `useTickets` filters

## Decisions Made

See `key-decisions` in frontmatter for the full list. The two most consequential:

1. **Query-hook + page.tsx wiring was necessary, not optional scope creep.** The plan's `files_modified` list named only the chip-bar/table/card presentation files, but a chip-bar axis or toggle that writes a URL param nobody reads into the TanStack query is a UI control with no observable effect — directly contradicting the plan's own stated purpose ("real per-entity OR/AND scanner-source filtering"). Applied Rule 3 (auto-fix blocking issue) to all three tasks rather than ship a cosmetically-complete but functionally inert feature.
2. **Confirmed the Tickets `?source=` param must be sent as REPEATED query params**, not the comma-joined shape the other 3 ticket chip-bar axes use in the same `buildSearchParams` function — traced directly to the backend router's `source: list[str] | None = Query(None)` binding (35-04-SUMMARY.md, confirmed by reading `ticketing/router.py` directly), which would silently receive a single un-split string if comma-joined.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Assets: threaded scanner/enrichment_source/source_mode through use-assets.ts + assets/page.tsx**
- **Found during:** Task 1 — after splitting `assets-chip-bar.tsx`'s axes, tracing the data flow showed `assets/page.tsx` still read a single stale `?source=` URL param (via its own module-scope allow-list, independent of the chip-bar's) and passed it to `AssetsFilters.source`, which `buildSearchParams` comma-joined into `?scanner=` — meaning the chip-bar's new `?scanner=`/`?enrichment_source=`/`?source_mode=` URL writes would never reach the actual asset list query.
- **Issue:** The new chip-bar axes and toggle would render and update the URL, but the fetched data would never reflect the selection — an inert filter.
- **Fix:** Renamed `AssetsFilters.source` to `scanner`, added `enrichment_source`/`source_mode` fields + `buildSearchParams` branches (`use-assets.ts`); updated `assets/page.tsx`'s own allow-lists and URL-state reads to match the chip-bar's axis keys, and threaded all three into the `useAssets` filter object.
- **Files modified:** `frontend/src/lib/queries/use-assets.ts`, `frontend/src/lib/queries/use-assets.test.ts`, `frontend/src/app/(authed)/dashboard/assets/page.tsx`
- **Verification:** `npx vitest run src/components/assets/ src/lib/queries/use-assets.test.ts "src/app/(authed)/dashboard/assets/"` — 98/98 pass. `npx tsc --noEmit` clean.
- **Committed in:** `a175cf4` (Task 1 commit)

**2. [Rule 3 - Blocking] CSPM: threaded source_mode through use-cspm-findings.ts**
- **Found during:** Task 2 — `CspmFilters` had no `source_mode` field and `buildCspmParams` never emitted the param, so the new page-level toggle would flip local state with no effect on the actual query.
- **Issue:** Same inert-filter risk as Assets.
- **Fix:** Added `CspmFilters.source_mode` + a `buildCspmParams` branch (omits the param when `'or'`, the default, to keep the common case's URL/query clean); added `MisconfigSummary.sources`/`sources_count` for the FindingCard wiring.
- **Files modified:** `frontend/src/lib/queries/use-cspm-findings.ts`, `frontend/src/lib/queries/use-cspm-findings.test.ts`
- **Verification:** `npx vitest run src/components/cspm/ "src/app/(authed)/dashboard/cspm/" src/lib/queries/use-cspm-findings.test.ts` — 26/26 pass.
- **Committed in:** `6a689fd` (Task 2 commit)

**3. [Rule 3 - Blocking] Tickets: threaded source through use-tickets.ts + tickets/page.tsx**
- **Found during:** Task 3 — same inert-filter pattern; additionally discovered the backend expects `source` as REPEATED params (`list[str] Query`), not the comma-joined shape the other 3 ticket filters use in the same function.
- **Issue:** Without this, the new tickets chip-bar source axis would write `?source=` to the URL with no effect on fetched data; naively copying the comma-join convention from `status`/`provider`/`severity`/`sla` would also have silently mismatched the backend's expected shape.
- **Fix:** Added `TicketsFilters.source` + a `buildSearchParams` branch using `sp.append('source', v)` per value (clamped against the allow-list first); added `TicketSummary.sources`/`sources_count`; updated `tickets/page.tsx`'s URL-state reads and filter object.
- **Files modified:** `frontend/src/lib/queries/use-tickets.ts`, `frontend/src/lib/queries/use-tickets.test.ts`, `frontend/src/app/(authed)/dashboard/tickets/page.tsx`
- **Verification:** `npx vitest run src/components/tickets/ "src/app/(authed)/dashboard/tickets/" src/lib/queries/use-tickets.test.ts` — 117/117 pass.
- **Committed in:** `ebbf094` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 3 — blocking-issue fixes required for the plan's own stated filtering behavior to function; no architectural changes, no new files beyond the plan's own intent, no scope creep beyond "make the wired UI control actually filter").
**Impact on plan:** Necessary corollary of wiring real (not cosmetic) filter axes per the plan's own success criteria. No change to any interface described in the plan's `<interfaces>` block; only additive fields/params in adjacent query-hook and page files.

## Issues Encountered

None beyond the three deviations documented above.

## User Setup Required

None — no external service configuration required. No backend changes (all consumed from Plans 01/03/04, already shipped on main).

## Next Phase Readiness

- All 4 triage entities (Vulnerabilities, Assets, CSPM, Tickets) now share the identical SourceBadgeGroup non-overclaiming provenance display and the SRC-02/03/04 OR/AND filter contract (Tickets: OR-only by design, per Plan 04's scope decision).
- This is the final plan of Phase 35 and of v4.0 — no blockers for phase/milestone closure.
- Deferred to phase UAT (not this session): live-browser visual verification that single vs multi source never reads as "confirmed" on a running server, and that empty/loading/error states render correctly end-to-end (component/unit tests cover the underlying logic; no browser was spun up this session).
- Design-token gap: none newly discovered — all 6 scanner gradient tokens (`--gradient-provider-{crowdstrike,nessus,defender,wiz,qualys,rapid7}`) already existed from Phase 14's `ConnectorMark` work (confirmed by Plan 02) and are reused verbatim by every surface `SourceBadgeGroup` now renders on.

---
*Phase: 35-source-aware-filtering-provenance-badges*
*Completed: 2026-08-12*

## Self-Check: PASSED

All 12 created/modified files verified present on disk (plus this SUMMARY.md); all 3 task commits (`a175cf4`, `6a689fd`, `ebbf094`) verified present in `git log --oneline --all`.
