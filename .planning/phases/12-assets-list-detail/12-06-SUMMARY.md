---
phase: 12-assets-list-detail
plan: 06
subsystem: frontend/assets-list-page
tags: [ux-04-01, ux-04-05, chip-bar, state-patterns, assets-table]
requires:
  - 12-03  # RiskRing.getRiskBand + Avatar + osFamily helper
  - 12-04  # generic ChipBar primitive
  - 12-05  # useAssets hook + assets query-key namespace
provides:
  - AssetsChipBar  # 4-axis chip-bar wrapping the generic ChipBar
  - AssetsTable    # 6-column list table with keyboard nav + stale tinting
  - microcopy.assets  # co-located strings for the /assets surface
affects:
  - frontend/src/app/(authed)/dashboard/assets/page.tsx  # v1 386-line rewrite → 184 lines composed
tech-stack:
  added: []
  patterns:
    - "ChipBar axes={ChipAxis[]} composition (Plan 12-04 primitive consumed by domain wrapper)"
    - "Hardcoded allowList per axis → useUrlStateList read+write clamp (T-12-05 / WR-04)"
    - "useMemo on filters object for stable TanStack cache key (useUrlStateList returns fresh array refs each render)"
    - "Hybrid PartialFailureBanner props-mode (page error + ErrorBoundary fallback)"
    - "EmptyState compound subcomponent pattern (Title/Body)"
key-files:
  created:
    - frontend/src/components/assets/microcopy.ts
    - frontend/src/components/assets/assets-chip-bar.tsx
    - frontend/src/components/assets/assets-chip-bar.test.tsx
    - frontend/src/components/assets/assets-table.tsx
    - frontend/src/components/assets/assets-table.test.tsx
    - frontend/src/app/(authed)/dashboard/assets/page.test.tsx
  modified:
    - frontend/src/app/(authed)/dashboard/assets/page.tsx  # full rewrite
decisions:
  - "AssetsChipBar axes locked: category (5-value enum) · risk_band (4-band enum) · source (derivedFromCounts per D-F-03) · os_family (4-value enum). Phase 13 reuse: any new surface that needs the same axes should consume <AssetsChipBar /> directly rather than re-deriving the lists."
  - "Page passes facets={{ source: undefined, category: undefined }} as a placeholder until backend list_assets emits facet counts. The source axis is wired and will light up automatically when facets arrive; no code change required."
  - "Source axis label/chips don't render until facet counts arrive (derivedFromCounts contract). Page test asserts only static axes (category/risk_band/os_family) by data-axis selector; this is documented in the test and is the expected D-F-03 behavior."
metrics:
  duration: "~7m"
  completed: "2026-05-30"
  tasks: 3
  files: 7
---

# Phase 12 Plan 06: Rewrite /assets List Page Summary

One-liner — Rewrote the 386-line v1 `/assets` page into a 184-line composition of `AssetsChipBar` (4 axes) + Phase 11 state primitives + new `AssetsTable` (6 columns) + `useAssets` (Plan 12-05), with co-located tests covering 18 cases across the three new components.

## What Shipped

### `frontend/src/components/assets/microcopy.ts`
Co-located strings for the /assets surface (page H1, eyebrow, chip labels, empty-state copy, column headers). Mirrors `frontend/src/components/vulnerabilities/microcopy.ts` from Phase 11.

### `frontend/src/components/assets/assets-chip-bar.tsx`
Domain wrapper around the generic `<ChipBar axes={...} />` primitive from Plan 12-04. Locks 4 axes:

| Axis        | URL key      | Allow-list                                                                  | Render mode          |
| ----------- | ------------ | --------------------------------------------------------------------------- | -------------------- |
| Category    | `category`   | `WORKSTATION` · `SERVER` · `NETWORK` · `MOBILE` · `OTHER`                   | static chips         |
| Risk band   | `risk_band`  | `critical` · `high` · `medium` · `low`                                      | static chips         |
| Source      | `source`     | `QUALYS` · `TENABLE` · `RAPID7` · `CROWDSTRIKE` · `AWS_INSPECTOR` · `WIZ` · `MOCK` | `derivedFromCounts` |
| OS family   | `os_family`  | `linux` · `windows` · `macos` · `other`                                     | static chips         |

T-12-05 mitigation: every axis carries the `allowList` reference straight through to `useUrlStateList`, which clamps reflected URL values on both read and write.

### `frontend/src/components/assets/assets-table.tsx`
6-column semantic `<table>` (no grid role per Pitfall 5):

1. Hostname (mono, `font-mono`)
2. OS (`os_name` text)
3. Owner (Avatar 24px + name; renders `Unassigned` when `assigned_user === null`)
4. Risk Score (mono `tabular-nums`, band-tinted via `getRiskBand` from RiskRing primitive)
5. Tags (flex-wrap chip list)
6. Sources (flex-wrap mono chip list)

Keyboard nav: `tr[tabIndex={0}]` with ArrowDown/ArrowUp/Home/End/Enter/Space → `onRowOpen`. Sticky `<thead>`. D-V-04 stale-row tinting: when any of the row's `seen_by_sources` intersects `failedSources`, the row gets `data-stale="true"` and `bg-amber-soft`.

### `frontend/src/app/(authed)/dashboard/assets/page.tsx` (rewritten)
Compose-only page (`AssetsPageInner` wrapped by `ErrorBoundary` + `Suspense`):

- Reads filters from URL via `useUrlStateList` (4 chip axes) + `useUrlState` (`order`).
- `useMemo` on the `filters` object to keep the TanStack cache key stable (useUrlStateList returns a fresh array reference each render — without memoization the page would refetch on every render).
- Calls `useAssets({ filters, page, sort: 'risk_score', order })`.
- Branches: `isPending` → `SkeletonTable` (6-col shape matches AssetsTable); `q.data.items.length === 0` → `EmptyState` (Title + Body, no CTAs since saved filters / connector wiring is deferred per D-L-04); otherwise renders `AssetsTable` + `Pagination` when `pages > 1`.
- Errors: `q.error` → `PartialFailureBanner` (props mode) with `onRetry={() => q.refetch()}`. `ErrorBoundary` fallback synthesizes `code: 'crash'` so no raw stack reaches the DOM.
- Row click: `router.push('/assets/${id}')` — list does not host DrillPanel; that's the detail page's responsibility (CONTEXT D-D-03).

## How v1 → v2 Diffs

The v1 page (deleted from the rewrite):
- Called `api()` directly inside `useEffect` (no TanStack — Phase 10 milestone-wide contract violation).
- Hardcoded `bg-red-500`, `text-orange-400`, `bg-emerald-500/10`, etc. (freehand palette).
- No skeleton, no proper empty state ("No assets found matching your filters" inside a `<tr><td colSpan=12>` block), no partial-failure UI.
- Page-local stats grid with custom hex tint per category (`bg-blue-500/20 text-blue-400`).
- Bulk ignore + classify-devices buttons that no longer match the v2 detail flow (reassign owner moves to the detail page per CONTEXT D-A-01).

The v2 page:
- All data via `useAssets` (TanStack v5).
- Zero raw hex / zero `*-500` palette — only design-token classes.
- All three state primitives (SkeletonTable / EmptyState / PartialFailureBanner) wired.
- Surface trimmed: stats grid / bulk ignore / classify-devices are deferred to phase 12-07 (detail page) and follow-up flows; list is now purely list-of-assets.

## Verification

- ✅ `pnpm vitest run src/components/assets src/app/\(authed\)/dashboard/assets/page` — 18/18 tests pass (6 chip-bar + 8 table + 4 page).
- ✅ `pnpm vitest run` (full frontend suite) — 365/365 tests pass across 62 files. No regressions.
- ✅ `pnpm tsc --noEmit` — clean.
- ✅ State-variant audit: `ls src/components/states/*.tsx | grep -v test | wc -l` returns 4 — UX-04-05 grep gate passes (no new state variants added).
- ✅ Freehand hex scan on new files — empty.
- ⏭️ `pnpm lint` — `next lint` is deprecated and tries to interactively configure ESLint; skipped per scope boundary (pre-existing repo infra gap, unrelated to this plan).

## Deviations from Plan

### [Rule 1 - Bug] Adjusted page test to use `data-axis` selectors for chip-bar axes

- **Found during:** Task 3
- **Issue:** The plan's page test asserted `getByText('Source')` and `getByText('OS')`. (a) The Source axis is `derivedFromCounts: true` (per CONTEXT D-F-03 / Plan §"Axes 3") and the page deliberately passes `facets.source = undefined` until the backend emits facets — so the Source label intentionally does not render at page load. (b) 'OS' is also the table column header, so `getByText('OS')` matched multiple elements after the chip-bar rendered with an OS axis label.
- **Fix:** The page test asserts the static-rendered axes (category, risk_band, os_family) via the `data-axis-label`/`data-axis` selectors injected by the ChipGroup component (instead of fragile text matching). Documented in a test comment that Source axis lights up automatically once backend facets land.
- **Files modified:** `frontend/src/app/(authed)/dashboard/assets/page.test.tsx`
- **Commit:** `a088f1d` (Task 3)

### [Rule 1 - Bug] Adjusted Task 1 test to provide facets for `data-axis="source"` assertion

- **Found during:** Task 1
- **Issue:** The plan's chip-bar test `it('exposes data-axis selector per group', ...)` rendered `<AssetsChipBar />` without facets, then asserted `[data-axis="source"]` exists. Since the source axis is `derivedFromCounts: true`, `ChipGroup` returns null when there are no counts — the `data-axis` wrapper never renders.
- **Fix:** Test passes `facets={{ source: { QUALYS: 1 } }}` so the source axis renders. Documented in a test comment.
- **Files modified:** `frontend/src/components/assets/assets-chip-bar.test.tsx`
- **Commit:** `a1414ff` (Task 1)

### [Rule 2 - Missing critical functionality] Wrapped page in `ErrorBoundary` + `Suspense`

- **Found during:** Task 3
- **Issue:** The plan included `Suspense + ErrorBoundary` only briefly inside the page action — but the plan body's `pageErrorFallback` factory pattern + the `boundaryName="AssetsPage"` audit tag follow the Phase 11 vulnerabilities page convention. Without `boundaryName`, downstream Sentry/Rollbar wiring can't filter boundary failures by surface.
- **Fix:** Added `boundaryName="AssetsPage"` to the ErrorBoundary, plus a module-scoped `PAGE_FALLBACK` constant (mirrors the Phase 11 pattern at vulnerabilities/page.tsx:235) so the Suspense fallback shape matches the post-hydration SkeletonTable shape exactly.
- **Files modified:** `frontend/src/app/(authed)/dashboard/assets/page.tsx`
- **Commit:** `a088f1d` (Task 3)

## Threat Surface

All three `<threat_model>` mitigations from the plan are implemented:

- **T-12-05** (URL → chip render reflected-XSS): AssetsChipBar passes each axis's hardcoded `allowList` straight through to the generic ChipBar primitive; `useUrlStateList` clamps on read + write.
- **T-12-07** (cell XSS via hostname / owner / tags / sources): All AssetsTable cells render values as React text children. Avatar primitive carries its own XSS guard (T-12-04 from Plan 12-03 — text-only initial, never innerHTML).
- **T-12-16** (cross-tenant via URL): Frontend hooks pass through; backend `list_assets` already enforces tenant boundary. No client-side gate required.

No new threat flags introduced.

## Known Stubs / Deferred Wiring

- **Source axis facet counts:** Page passes `facets.source = undefined` to AssetsChipBar. The Source axis label/chips will render automatically once the backend `list_assets` endpoint emits per-source counts (deferred — out of scope for this plan; tracked via CONTEXT D-F-03 inheritance from Phase 11). This is documented in a comment at `page.tsx:120` and is the expected state per Plan 12-06's §"backend doesn't emit facets yet" note.
- **Saved filters pill:** Not wired (per CONTEXT D-L-04 — same Phase 11 deferred decision; backend `/assets/saved-filters` doesn't exist yet).
- **Bulk ignore / classify-devices buttons:** Removed from v2 surface (v1 had them); the v2 redesign moves ownership reassignment to the detail page per CONTEXT D-A-01. If a v1-equivalent "Ignore" workflow is needed, it returns as a future surface.

## Commits

| Task | Hash      | Subject                                                                  |
| ---- | --------- | ------------------------------------------------------------------------ |
| 1    | a1414ff   | feat(12-06): AssetsChipBar — 4-axis wrapper around generic ChipBar      |
| 2    | fb242af   | feat(12-06): AssetsTable — 6-column table with keyboard nav + tinting   |
| 3    | a088f1d   | feat(12-06): rewrite /assets page using Phase 11 state primitives       |

## Self-Check: PASSED

- All 7 plan output files exist on disk (microcopy.ts, assets-chip-bar.tsx + test, assets-table.tsx + test, page.tsx rewritten, page.test.tsx).
- All 3 task commits present in git log (a1414ff, fb242af, a088f1d).
- 18 new tests pass; 365 total frontend tests pass; tsc clean.
- UX-04-05 grep gate: 4 state-variant .tsx files (no new variants added).
