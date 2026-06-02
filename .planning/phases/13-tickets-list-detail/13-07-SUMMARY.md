---
phase: 13-tickets-list-detail
plan: "07"
subsystem: frontend
tags: [tickets, list-page, chip-bar, table, drill-panel, bulk-bar, tdd, optimistic-mutation]
dependency_graph:
  requires:
    - Plan 04 (queryKeys.tickets, ProviderMark, StatusPill, SlaPill, VulnCount, types.ts)
    - Plan 05 (generalized DrillPanel/DrillPanelMobile with idKey/renderContent, TicketDrillContent)
    - Plan 06 (BlockedToggle)
    - Plan 03 (backend: GET /tickets, POST /tickets/{id}/blocked, POST /tickets/bulk-action)
  provides:
    - useTickets list hook + buildSearchParams (URL-shape testable without TanStack)
    - useMarkBlocked optimistic mutation with snapshot rollback + predicate invalidation
    - TicketsChipBar (4 axes: Status/Provider/Severity/SLA with hardcoded allowLists)
    - TicketsTable (8-column table composing Plan 04 primitives + mobile card collapse)
    - TicketBulkBar (Close + Mark blocked/Unblock with modals, D-S-03)
    - /tickets page rewrite (v1 sunset — ErrorBoundary > Suspense > Inner composition)
  affects:
    - Plans 08/09 (share useMarkBlocked; plan 08 wires real BlockedToggle in detail page)
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN per task (3 RED commits, 3 GREEN commits)
    - buildSearchParams co-located + exported for URL-shape tests (Phase 11 D-D-03)
    - Optimistic mutation with onMutate snapshot / onError rollback / onSuccess invalidation (Pattern 4)
    - Predicate-based cross-prefix cache invalidation (assets remediations on blocked toggle)
    - WR-13 mutually exclusive state branches (error → loading → empty → data)
    - WR-10 full err.message to PartialFailureBanner (no slice)
    - D-S-02 asana_not_configured → connector deep-link EmptyState (not generic error banner)
    - XSS allow-lists module-scope (T-13-22) matching chip-bar axes
    - min-[900px]: Tailwind breakpoint for mobile card collapse (D-L-01 Pitfall 3)
key_files:
  created:
    - frontend/src/lib/queries/use-tickets.ts
    - frontend/src/lib/queries/use-tickets.test.ts
    - frontend/src/lib/queries/use-mark-blocked.ts
    - frontend/src/components/tickets/tickets-chip-bar.tsx
    - frontend/src/components/tickets/tickets-table.tsx
    - frontend/src/components/tickets/tickets-table.test.tsx
    - frontend/src/components/tickets/ticket-bulk-bar.tsx
    - frontend/src/app/(authed)/dashboard/tickets/page.test.tsx
  modified:
    - frontend/src/app/(authed)/dashboard/tickets/page.tsx (v1 sunset rewrite — 1239 lines removed, 421 added)
decisions:
  - asana_not_configured error renders connector deep-link EmptyState (D-S-02), NOT PartialFailureBanner — the error is an expected "unconfigured" signal, not a transient failure
  - buildSearchParams allow-list clamping happens in the hook itself (not only in chip-bar) for defense-in-depth (T-13-22)
  - useMarkBlocked patches both byId cache AND list cache in onMutate for immediate table row update
  - Predicate-based invalidation targets ['assets', *, 'remediations'] on blocked toggle success (RESEARCH Pattern 4)
  - TicketsTable renders both desktop table AND mobile card list (not CSS-only hidden); both contain same primitives
  - Page test uses vi.spyOn(module, 'useTickets') pattern (not vi.mock factory) to avoid hoisting issues
  - Board placeholder copy verbatim from plan spec: "Board view coming in a future update — for now, use the List view with the Status chip filter to organize work by status."
metrics:
  duration: "~20 minutes"
  completed: "2026-06-02"
  tasks_completed: 3
  tasks_total: 3
  tests_added: 15
  files_created: 8
  files_modified: 1
---

# Phase 13 Plan 07: /tickets List Page + Queries Summary

**One-liner:** v1 tickets page (1186-line raw-fetch + freehand hex) replaced with TanStack-driven sunset composition: useTickets/useMarkBlocked hooks, 4-axis chip-bar, 8-column table composing Plan 04 primitives, generalized DrillPanel(idKey="ticket"), List/Board toggle, connector deep-link empty state, bulk-bar — 15 tests green.

## What Was Built

### Task 1: useTickets + buildSearchParams + useMarkBlocked

**`use-tickets.ts`** — clones `use-assets.ts` structure. Exports:
- `TicketsFilters` type (status/provider/severity/sla/search)
- `TicketSummary` type (8-column row contract)
- `TicketsResponse` type
- `buildSearchParams(opts)` — co-located and exported per Phase 11 D-D-03 pattern; applies XSS allow-list clamps (T-13-22) before building query string
- `useTickets(opts)` — TanStack query keyed by `queryKeys.tickets.list(...)` (imported read-only from Plan 04)

**`use-mark-blocked.ts`** — optimistic mutation cloning `use-reassign-asset.ts` Pattern 4:
- POST `/api/v1/tickets/{id}/blocked` — sends ONLY `{blocked, blocked_reason}` (T-13-23 mass-assignment guard)
- `onMutate`: cancels byId + all queries, snapshots both, optimistically patches byId detail cache AND list cache items
- `onError`: restores both snapshots, emits error toast
- `onSuccess`: invalidates `tickets.byId(id)` + `tickets.all` + predicate-invalidates `['assets', *, 'remediations']` (RESEARCH Pattern 4)
- `retry: 0`

**9 tests green** (`use-tickets.test.ts`):
- buildSearchParams serializes all filter types correctly
- allow-list clamp drops out-of-list values
- empty arrays produce no URL params

### Task 2: TicketsChipBar + TicketsTable + TicketBulkBar

**`tickets-chip-bar.tsx`** (D-L-04):
- Wraps `<ChipBar>` with 4 axes: Status (multi), Provider (multi), Severity (multi), SLA (single-select)
- Each axis has a hardcoded `allowList` per T-12-05 (XSS clamp at chip-bar + at URL read)
- Provider values: `['jira', 'asana', 'github']`; can be data-driven from facets when provided
- Search: placeholder "Search ID, title, or assignee…" with 250ms debounce (inherited from ChipBar)

**`tickets-table.tsx`** (D-L-01/02):
- 8 columns: Severity (glyph ■▲◆○□) · Provider (`<ProviderMark>`) · ID (mono) · Title (truncate + title attr) · Vulns (`<VulnCount>`) · Assignee (Avatar + name) · Status (`<StatusPill>`) · SLA (`<SlaPill>`)
- Row checkbox selection feeds bulk bar; `onRowClick(ticket)` callback for drill
- Keyboard nav: ArrowDown/Up/Home/End/Enter/Space (mirrors AssetsTable pattern)
- Mobile card collapse at `<900px` via `min-[900px]:` variants (D-L-01 Pitfall 3)
- No inline hex — all colors via Tailwind sunset tokens

**`ticket-bulk-bar.tsx`** (D-S-03):
- Bottom-anchored bar visible when `selectedCount > 0`
- Close: ConfirmModal confirmation
- Mark blocked: inline modal collecting shared `blocked_reason` (max 500 chars)
- Unblock: ConfirmModal confirmation
- Callbacks to page which fires `/tickets/bulk-action`

**2 tests green** (`tickets-table.test.tsx`): 8 headers asserted; ProviderMark/StatusPill/SlaPill/VulnCount all render.

### Task 3: /tickets/page.tsx rewrite

**Structure** — mirrors `assets/page.tsx`:
- `ErrorBoundary > Suspense > TicketsPageInner`
- Module-scope XSS allow-lists (T-13-22), module-scope `SKELETON_COLUMNS`

**State branches** (WR-13 mutually exclusive):
1. `asanaUnconfigured` (error.message contains `asana_not_configured`) → EmptyState with `/dashboard/connectors` deep-link (D-S-02) — treated as expected signal, not transient failure
2. `q.error` (other errors) → PartialFailureBanner with full `err.message` (WR-10)
3. `isLoading` → SkeletonTable
4. `items.length === 0` → generic EmptyState
5. else → TicketsTable + Pagination

**List/Board toggle** (D-L-03):
- Segmented control in page header using `useUrlState('view', ['list','board'], 'list')`
- Board branch renders BOARD_PLACEHOLDER copy (verbatim from plan spec) — no table
- List branch renders full TicketsTable

**Drill panel** (D-D-02):
- Desktop: `<DrillPanel idKey="ticket" id={ticketIdFromUrl} renderContent={...}/>`
- Mobile: `<DrillPanelMobile idKey="ticket" .../>`
- Row click sets `?ticket=<id>&open=drill`
- `TicketDrillContent` receives ticket data from the list row (no extra fetch)
- `BlockedToggle` wired to `useMarkBlocked` in the drill footer

**4 page tests green** (`page.test.tsx`):
- Test 1: 8 column headers + row data
- Test 2: mutually exclusive state branches
- Test 3: List/Board toggle buttons present
- Test 4: connector deep-link EmptyState on asana_not_configured

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test hoisting issue with vi.mock factory**
- **Found during:** Task 3 — `page.test.tsx` RED → GREEN
- **Issue:** `vi.mock` is hoisted to top of file, so `useTicketsMock` variable declared outside the factory was not yet initialized when the factory ran, throwing "Cannot access before initialization"
- **Fix:** Switched from `vi.mock` factory pattern to `vi.spyOn(useTicketsModule, 'useTickets')` pattern inside `beforeEach` — avoids hoisting issue while still controlling mock return values
- **Files modified:** `page.test.tsx`

**2. [Rule 1 - Bug] getByText('Unknown') and getByText('5') had multiple matches**
- **Found during:** Task 2 table tests (both desktop table and mobile card render the same primitives)
- **Fix:** Used `getAllByText(...)` + `expect(length).toBeGreaterThan(0)` in table test and page test for duplicate-rendered text
- **Files modified:** `tickets-table.test.tsx`, `page.test.tsx`

**3. [Rule 2 - Missing] asana_not_configured treated as EmptyState not PartialFailureBanner**
- **Found during:** Task 3 Test 4 — the plan says "if the response/error indicates Asana not configured, render the connector deep-link variant" which implies a special case for this error type
- **Fix:** Added `asanaUnconfigured` predicate check before the generic `q.error` branch; when Asana is not configured, show the connector EmptyState instead of the generic error banner. This is the correct UX: analysts see a clear call-to-action, not a cryptic HTTP error
- **Files modified:** `page.tsx`

## Known Stubs

The drill panel renders `description: null` and `linkedVulns: []` for tickets from the list (these fields aren't in the list API response). This is intentional — full detail is shown on the `/tickets/[id]` detail page (Plan 08). The drill panel shows a useful subset (externalId, title, status, SLA, vuln count) and links to full detail.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| T-13-22 (mitigated) | tickets-chip-bar.tsx + page.tsx | Chip URL params reflected via allowList clamp in both chip-bar axes and buildSearchParams |
| T-13-23 (mitigated) | use-mark-blocked.ts | Only {blocked, blocked_reason} sent to /tickets/{id}/blocked |

No new unplanned network endpoints or auth paths introduced.

## Self-Check

### Files exist:
- frontend/src/lib/queries/use-tickets.ts: FOUND (created)
- frontend/src/lib/queries/use-tickets.test.ts: FOUND (created)
- frontend/src/lib/queries/use-mark-blocked.ts: FOUND (created)
- frontend/src/components/tickets/tickets-chip-bar.tsx: FOUND (created)
- frontend/src/components/tickets/tickets-table.tsx: FOUND (created)
- frontend/src/components/tickets/tickets-table.test.tsx: FOUND (created)
- frontend/src/components/tickets/ticket-bulk-bar.tsx: FOUND (created)
- frontend/src/app/(authed)/dashboard/tickets/page.tsx: FOUND (modified/rewritten)
- frontend/src/app/(authed)/dashboard/tickets/page.test.tsx: FOUND (created)

### Commits:
- 779515c: test(13-07): add failing tests for useTickets buildSearchParams (RED)
- 100c9e4: feat(13-07): implement useTickets + buildSearchParams + useMarkBlocked optimistic mutation
- c107a58: test(13-07): add failing tests for TicketsTable 8-column contract (RED)
- 3da87fe: feat(13-07): implement TicketsChipBar (4 axes) + TicketsTable (8 cols) + TicketBulkBar
- ab4b725: test(13-07): add failing tests for /tickets page rewrite (RED)
- 9fd8667: feat(13-07): rewrite /tickets list page (v1 sunset — full replacement)

## TDD Gate Compliance

All three tasks followed RED → GREEN sequence:
1. `test(13-07)` commit (RED) → `feat(13-07)` commit (GREEN) for each task
2. Gate sequence: ✓ 3 test commits exist before their corresponding feat commits

## Self-Check: PASSED
