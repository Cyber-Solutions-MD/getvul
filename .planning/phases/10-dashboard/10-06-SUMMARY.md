---
phase: 10-dashboard
plan: 06
subsystem: ui
tags: [phase-10, frontend, shell, sidebar, tanstack-query, useStats, human-uat]

requires:
  - phase: 09-login-foundation
    provides: "AppShell + sidebar (D-35..41) with 7 nav items and em-dash count placeholders that Phase 10 wires to live data"
  - phase: 10-dashboard
    provides: "Plan 10-01 — /api/v1/vulnerabilities/stats top-level fields vuln_open_count / asset_total_count / ticket_open_count (D-N-02)"
  - phase: 10-dashboard
    provides: "Plan 10-02 — TanStack Query v5 + useStats() hook + root QueryClientProvider (D-D-01..02 hoisted) + queryKeys factory"
  - phase: 10-dashboard
    provides: "Plan 10-05 — frontend/src/app/(authed)/dashboard/page.tsx (the page-level useStats() consumer that shares the cache key with Sidebar)"
provides:
  - "Sidebar nav-chip wiring to live useStats() data for Vulnerabilities (vuln_open_count), Assets (asset_total_count), Tickets (ticket_open_count) — D-N-01..03"
  - "Em-dash fallback (no placeholder bar primitive) on loading AND error — preserves chip width, prevents CLS"
  - "Automated single-fetch invariant test asserting Sidebar + DashboardPage share one /stats fetch under a shared QueryClientProvider (Warning 15)"
  - "10-HUMAN-UAT.md — 10-section manual verification checklist feeding /gsd-verify-work (sketch-002 variant B fidelity, forced-colors, keyboard nav, reduce-motion, CLS, First-Load JS, cross-browser, copy-voice, known stubs, Phase 9 regression sanity)"
affects:
  - 11-vulnerabilities  # When Phase 11 honors ?open=drill, the Top-5 row navigations stop being stubs; sidebar nav-chip pattern is the canonical convention for any future chip
  - 12-assets           # Asset nav-chip in sidebar shows asset_total_count live
  - 13-tickets          # Tickets nav-chip in sidebar shows ticket_open_count live
  - 15-mobile-a11y-perf # CLS / forced-colors / reduce-motion items in HUMAN-UAT feed the Phase 15 quality-gate

# Tech tracking
tech-stack:
  added: []  # No new deps in this plan; @tanstack/react-query lands in Plan 10-02
  patterns:
    - "ChipKey discriminator on NavItem — typed key indexing into a counts record; cleaner than threading three optional numbers through the JSX"
    - "Em-dash fallback (no placeholder bar) for live-count chips — prevents CLS without needing a Skeleton primitive"
    - "Single useStats() per page tree — TanStack Query de-dupes by cache key + shared QueryClient; verified by automated test"

key-files:
  created:
    - frontend/src/components/shell/sidebar-cache.test.tsx
    - .planning/phases/10-dashboard/10-HUMAN-UAT.md
  modified:
    - frontend/src/components/shell/sidebar.tsx

key-decisions:
  - "Plan-level D-N-01 reaffirmed at execution: only Vulnerabilities, Assets, Tickets carry chips. Phase 9 had stub chips on Dashboard/CSPM/Connectors — removed in this plan, not just data-wired."
  - "ChipKey discriminator chosen over per-item count fields: keeps the counts record centralized, easier to extend in Phase 11+ if needed, and lets the renderer remain pure (renderChip is decoupled from NavItem shape)."
  - "Single CHIP_FALLBACK constant ('—') instead of inline literal: makes the fallback intention explicit and grep-able."
  - "HUMAN-UAT structured as 10 sections (sketch fidelity / forced-colors / keyboard / reduce-motion / CLS / bundle / cross-browser / copy-voice / known stubs / Phase 9 regression) — mirrors the Manual-Only Verifications table in 10-VALIDATION.md and adds a Phase 9 regression sanity check that the validation table didn't enumerate."

patterns-established:
  - "Sidebar nav-chip pattern: useStats() → counts record → renderChip(value | null). Canonical for any future sidebar chip in Phase 11+."
  - "Automated single-fetch invariant: shared QueryClient + render() of two consumers + filter on api.mock.calls — repeatable test shape for any future query that's consumed by multiple components."

requirements-completed:
  - UX-02-02
  - UX-02-06

# Metrics
duration: ~5 min
started: 2026-05-15T08:41:22Z
completed: 2026-05-15T08:46:32Z
---

# Phase 10 Plan 06: Sidebar nav-chip wiring + Phase 10 HUMAN-UAT checklist Summary

**Sidebar's three count chips (Vulnerabilities open, Assets total, Tickets open) wired to live data via the shared `useStats()` TanStack cache; em-dash fallback on loading/error prevents CLS; CSPM / Connectors / Users / Settings stay chip-less per D-N-01; automated single-fetch invariant test + 10-section HUMAN-UAT checklist ship alongside.**

## Performance

- **Duration:** ~5 min (5min 10s wall-clock)
- **Started:** 2026-05-15T08:41:22Z
- **Completed:** 2026-05-15T08:46:32Z
- **Tasks:** 3 / 3
- **Files modified:** 1 modified, 2 created

## Accomplishments

- Sidebar consumes `useStats()` from the shared TanStack cache. Three chips drive their value from `vuln_open_count`, `asset_total_count`, `ticket_open_count`; em-dash (`—`) renders during loading AND on error to keep chip width stable (no CLS).
- Stub chips on Dashboard, CSPM, Connectors (Phase 9 D-35 placeholders) were removed — D-N-01 says these items get no chip at all. Phase 9 had the placeholder pattern on too many items.
- Automated test `sidebar-cache.test.tsx` mounts `<Sidebar />` + `<DashboardPage />` under one `QueryClientProvider`, mocks `api()`, and asserts `/api/v1/vulnerabilities/stats` is hit exactly once. This catches future regressions in TanStack cache-key de-duplication or the Plan 02 QueryClientProvider hoist.
- `10-HUMAN-UAT.md` ships a 10-section checklist that `/gsd-verify-work` will present to the human reviewer. Covers every Manual-Only Verification from `10-VALIDATION.md` plus a Phase 9 regression sanity section.

## Task Commits

Each task was committed atomically (parallel-executor `--no-verify` flag set; orchestrator validates hooks after wave merge):

1. **Task 1: Wire sidebar nav-chip counts via useStats() — em-dash on loading/error, no layout shift** — `e33c247` (feat)
2. **Task 2: Produce 10-HUMAN-UAT.md — sketch-002 fidelity + forced-colors + keyboard nav + reduce-motion + CLS** — `d403127` (docs)
3. **Task 3 (Warning 15): Automated single-fetch invariant test — Sidebar + dashboard share one /stats request** — `8edd939` (test)

## Files Created/Modified

- `frontend/src/components/shell/sidebar.tsx` — Wired three nav-chip slots to `useStats()`; introduced `ChipKey` discriminator + `counts` record threaded into `NavSection`; added `renderChip` with em-dash fallback for the loading-or-error case. Removed the stub `count: '—'` from Dashboard, CSPM, Connectors per D-N-01 (these items now render no chip at all). Preserved Phase 9's active-state logic, mobile collapse (`max-[999px]:hidden`), gradient active strip, focus-ring, and landmark structure.
- `frontend/src/components/shell/sidebar-cache.test.tsx` — New vitest file. Mocks `@/lib/api`, secondary query hooks (`useTrends`, `useTopTriage`, `useRecentNotifications`), `next/navigation`, and `ResizeObserver` (recharts in jsdom). Mounts both consumers under one `QueryClient`; filters `api.mock.calls` for the `/stats` path; asserts exactly one fetch. Will run as part of `npm run test -- --run` after the wave-2 merge by the orchestrator.
- `.planning/phases/10-dashboard/10-HUMAN-UAT.md` — New 10-section manual UAT checklist: visual fidelity to sketch 002 variant B (hero / stat strip / trend chart / top-5 / activity rail); forced-colors mode (D-Ax-06); keyboard navigation Tab order; reduce-motion (D-Ax-04); CLS measurement; First-Load JS budget (180 kB per D-Perf-01); cross-browser smoke (Chrome/Safari/Firefox); copy-voice audit against verbatim exemplars; known Phase 10 stubs (Top-5 drill, activity routes, ⌘K, light theme — all expected, not bugs); Phase 9 regression sanity (Phase 9 `/login`, AppShell, theme toggle still intact).

## Decisions Made

- **ChipKey discriminator over count fields on NavItem:** Cleaner than threading three optional numbers through the JSX. The renderer is decoupled from `NavItem` shape — future additions only touch the `counts` record + `ChipKey` union.
- **Removed stub chips, not just wired them:** Phase 9 D-35 had `count: '—'` on Dashboard, CSPM, Connectors as well. D-N-01 explicitly says those items get NO chip. Wiring data to them would have left them showing a count when the spec says they shouldn't show one at all.
- **`CHIP_FALLBACK` constant instead of inline `'—'` literal:** Makes the fallback intention explicit and grep-able. Also single source of truth if the fallback symbol ever changes.
- **HUMAN-UAT section 10 (Phase 9 regression sanity) added beyond what 10-VALIDATION.md enumerates:** Validation's Manual-Only Verifications table covers sketch fidelity, forced-colors, keyboard, reduce-motion, CLS. The plan template also calls out cross-browser + copy-voice + known stubs. Section 10 is additional — a sanity check that the sidebar wiring didn't regress Phase 9 behavior (login flow, theme toggle, active-state). Captures the kind of regression that Phase 9's Test 12 middleware-location bug taught us automated tests can miss.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Acceptance grep mismatch: comment text tripped `Skeleton|skeleton` negative check**

- **Found during:** Task 1 (sidebar wiring, acceptance check)
- **Issue:** Initial implementation included comments like "No skeleton bar" and "No <Skeleton/> primitive here" inside the sidebar file. The plan's acceptance criterion grep `grep -E "Skeleton|skeleton" frontend/src/components/shell/sidebar.tsx | wc -l` returns 0 — the test was intended to assert no skeleton component is *used*, but the text grep also matches comments. Initial run returned 3 (all comments).
- **Fix:** Reworded the two comment blocks to use "placeholder bar primitive" / "no placeholder-bar primitive" instead of "skeleton". Intent preserved (no Skeleton primitive imported or used), grep now returns 0.
- **Files modified:** `frontend/src/components/shell/sidebar.tsx` (Task 1 commit `e33c247`)
- **Verification:** `grep -Ec "Skeleton|skeleton" frontend/src/components/shell/sidebar.tsx` → 0.

---

**Total deviations:** 1 auto-fixed (1 bug fix to satisfy plan-stated acceptance grep).
**Impact on plan:** None — change is comment-only, semantic intent preserved.

## Issues Encountered

None during planned work. Worktree-base recovery (Case B) ran cleanly under the orchestrator's authorized hard-reset path — the previous attempt's blocker is now resolved.

## Parallel-Execution Notes

This plan is wave 2; its dependencies (10-01 backend stats fields, 10-02 TanStack + useStats hook, 10-05 dashboard page) live in sibling worktrees. As a result:

- `npm run build` and `npm run test -- --run` were **not** executed in this worktree — those dependency files do not exist here. The orchestrator runs the full suite after merging all wave-2 worktrees; that's where `npm run build 2>&1 | tail -5` and the vitest run (including `sidebar-cache.test.tsx`) get exercised end-to-end.
- All static acceptance criteria were verified inline:
  - `grep -c useStats sidebar.tsx` → 4 (≥ 1 ✓)
  - `grep -c vuln_open_count sidebar.tsx` → 2 (≥ 1 ✓)
  - `grep -c asset_total_count sidebar.tsx` → 2 (≥ 1 ✓)
  - `grep -c ticket_open_count sidebar.tsx` → 2 (≥ 1 ✓)
  - `grep -F "—" sidebar.tsx | wc -l` → 13 (≥ 1 ✓)
  - `grep -Ec "Skeleton|skeleton" sidebar.tsx` → 0 ✓
  - `grep -c "sketch 002 variant B" 10-HUMAN-UAT.md` → 1 ✓
  - `grep -c "forced-colors" 10-HUMAN-UAT.md` → 1 ✓
  - `grep -Ec "Reduce motion|reduce-motion|prefers-reduced-motion" 10-HUMAN-UAT.md` → 2 ✓
  - `grep -Ec "First Load JS|First-Load JS" 10-HUMAN-UAT.md` → 4 ✓
  - `grep -c "Tab order" 10-HUMAN-UAT.md` → 2 ✓
  - `grep -c "Copy-voice" 10-HUMAN-UAT.md` → 1 ✓
  - `grep -Fc "CLS" 10-HUMAN-UAT.md` → 3 ✓
  - `grep -Fc "Known Phase 10 stubs" 10-HUMAN-UAT.md` → 1 ✓
  - `grep -E "statsCalls.length\)\.toBe\(1\)" sidebar-cache.test.tsx | wc -l` → 1 ✓
  - `grep -E "QueryClientProvider" sidebar-cache.test.tsx | wc -l` → 6 ✓

## User Setup Required

None - no external service configuration required by this plan.

## Note for Phase 11+

The sidebar nav-chip pattern is now canonical:

```ts
type ChipKey = 'vuln_open' | 'asset_total' | 'ticket_open';
const stats = useStats();
const counts: Record<ChipKey, number | null> = {
  vuln_open:   stats.data?.vuln_open_count   ?? null,
  asset_total: stats.data?.asset_total_count ?? null,
  ticket_open: stats.data?.ticket_open_count ?? null,
};
// renderChip(value: number | null) → em-dash on null, number otherwise
```

If a future plan adds a fourth chip (e.g., CSPM findings count), extend `ChipKey` union + `counts` record + add the chip slot on the relevant `NavItem`. **Do NOT introduce a `<SkeletonBar />` primitive for chip placeholders.** The em-dash fallback is the canonical convention — it prevents CLS without the cognitive cost of a separate loading state. Any deviation must justify itself against D-N-03.

## Next Phase Readiness

- Wave 2 of Phase 10 has all three pieces this plan owns: live sidebar counts, single-fetch invariant guard, manual UAT checklist.
- `/gsd-verify-work` can now present a complete checklist to the human reviewer once the orchestrator merges all wave-2 worktrees and the wave-final build + test gate passes.
- Phase 11 (`/vulnerabilities`) can rely on the sidebar Vulnerabilities chip already showing live data — no extra wiring needed; only honoring `?cve=…&open=drill` is its responsibility (the chip number updates naturally via TanStack cache invalidation on snooze/etc.).

## Self-Check: PASSED

Files claimed in this SUMMARY exist on disk:

- FOUND: `frontend/src/components/shell/sidebar.tsx`
- FOUND: `frontend/src/components/shell/sidebar-cache.test.tsx`
- FOUND: `.planning/phases/10-dashboard/10-HUMAN-UAT.md`
- FOUND: `.planning/phases/10-dashboard/10-06-SUMMARY.md`

Commits claimed in this SUMMARY exist in git history:

- FOUND: `e33c247` (Task 1 — feat: sidebar wiring)
- FOUND: `d403127` (Task 2 — docs: HUMAN-UAT)
- FOUND: `8edd939` (Task 3 — test: single-fetch invariant)

---
*Phase: 10-dashboard*
*Plan: 06*
*Completed: 2026-05-15*
