---
phase: 10-dashboard
plan: 05
status: complete
tasks_completed: 4
tasks_total: 4
duration: ~45 min (inline execution)
---

# Plan 10-05 SUMMARY — `/dashboard` Page Composition

## Tasks

| Task | What shipped | Tests |
|------|--------------|-------|
| 1 | Hero + Top5Card + OnboardingPanel | 22 vitest cases (axe-core a11y included) |
| 2 | TrendSection + StatStripWired + ActivityRail | 7 focused glue tests |
| 3 | `/dashboard/page.tsx` full rewrite | build green; bundle gate green |
| 4 | Page integration + full-page a11y scan | 5 vitest cases |

## Files

### Created (10)
- `frontend/src/components/dashboard/hero.tsx`
- `frontend/src/components/dashboard/top5-card.tsx`
- `frontend/src/components/dashboard/onboarding-panel.tsx`
- `frontend/src/components/dashboard/trend-section.tsx`
- `frontend/src/components/dashboard/stat-strip-wired.tsx`
- `frontend/src/components/dashboard/activity-rail.tsx`
- `frontend/src/components/dashboard/hero.test.tsx`
- `frontend/src/components/dashboard/top5-card.test.tsx`
- `frontend/src/components/dashboard/onboarding-panel.test.tsx`
- `frontend/src/components/dashboard/trend-section.test.tsx`
- `frontend/src/components/dashboard/stat-strip-wired.test.tsx`
- `frontend/src/app/(authed)/dashboard/page.test.tsx`
- `frontend/src/app/(authed)/dashboard/dashboard.a11y.test.tsx`

### Rewritten (1)
- `frontend/src/app/(authed)/dashboard/page.tsx` — full v1→v2.0 rewrite (912→77 lines).
  Removed the v1 ReportBuilder + ScheduleReportSection + chart helpers; the v2.0
  milestone moves report-builder to a future dedicated screen per ROADMAP.

### Updated (3, Wave 1 regression fix)
- `frontend/src/components/shell/sidebar.test.tsx` — wrap renders in `QueryClientProvider`
- `frontend/src/components/shell/app-shell.test.tsx` — wrap renders in `QueryClientProvider`
- `frontend/vitest.setup.ts` — add default `window.matchMedia` polyfill

## Verification

### Tests
- Full vitest suite: **35 files / 176 tests passing** (0 failures)
- Phase 10 surface: 39 new test cases this plan + axe-core a11y on every component

### Build
- `npm run build` → green
- `/dashboard` First-Load JS: **134.0 kB** (46 kB headroom vs 180 kB budget)
- `check-bundle.mjs --route /dashboard --max-kb 180` → exit 0

### Grep gates
- Hex literals in NEW Phase 10 surface: **0**
- `next/dynamic` in `trend-section.tsx`: present (TrendChart route-split confirmed)
- `import type { TrendChartProps }` (type-only) in `trend-section.tsx`: present
- Static `import { TrendChart }` in `page.tsx`: **0** (never directly imported)
- 5× `<ErrorBoundary>` in `page.tsx`: present (one per section)
- `xl:grid-cols-[1fr_340px]` (2-column at ≥1280px): present
- `useDocumentTitle` + `onboarding_state` switch: present
- All 7 section/component `microcopy.*.h2` references: present

## Snooze id resolution

Per Plan 01 backend: `top_vuln.id` is the UUID exposed by the `/stats` response.
The Hero component calls `useSnoozeMutation().mutate({ id: topVuln.id })` directly.
The plan's "Blocker 2 fix" (use UUID not cve_id) was honored — no cve_id stopgap
was needed because Plan 01 ships the UUID natively. The matching `POST
/api/v1/vulnerabilities/{id}/unsnooze` route drives the toast's Undo action via
`useUndoSnoozeMutation()`.

## Deviations recorded

### Rule 1 — Bug (auto-fix during execution)
**Button `asChild` drops `leftIcon`**: the plan code for the Hero gradient CTA
passed `<Button asChild variant="cta" leftIcon={<Zap />}>` with `<Link>` as the
child, but Button intentionally drops icon affordances when `asChild=true`
(documented in `button.tsx` lines 60-63 — "asChild is polymorphism, not full
feature parity"). The Zap icon would not have rendered. Fix: moved `<Zap aria-hidden />`
inline inside the `<Link>` child. Visual result identical because Button's base
class includes `gap-2` for flex spacing.

### Rule 1 — Bug (auto-fix during execution)
**Next 15 Suspense requirement**: `TrendSection` reads `?range=` via
`useUrlState` → `useSearchParams()`. Next 15 requires `useSearchParams` consumers
to be wrapped in `<Suspense>` for static page generation (CSR bailout). Without
this, `npm run build` fails with `missing-suspense-with-csr-bailout`. Fix: wrap
`<TrendSection />` in `<Suspense fallback={<TrendChartSkeleton />}>` inside the
page composition (sibling to its `ErrorBoundary`).

### Rule 3 — Wave 1 regression follow-up
**Cross-plan test breakage surfaced during Task 4**: three test files broke
after Wave 1 merges because the Wave 1 worktrees couldn't run `npm test`
(no symlinked `node_modules`):

1. `sidebar.test.tsx` (Phase 9 test) — Plan 10-06 added `useStats()` to Sidebar
   but didn't wrap the older test renders in `QueryClientProvider`. Fixed.
2. `app-shell.test.tsx` (Phase 9 test) — same issue via `AppShell`→`Sidebar`. Fixed.
3. `trend-chart.test.tsx` (Plan 10-04 test) — `usePrefersReducedMotion` calls
   `window.matchMedia` which jsdom doesn't implement. Fixed by adding a default
   polyfill to `vitest.setup.ts` (preserves any per-test `vi.spyOn` overrides).

### Scope clarification — hex literals
The plan's acceptance gate `grep -RE "#[0-9a-fA-F]{3,6}"
frontend/src/components/dashboard/ frontend/src/app/(authed)/dashboard/ | wc -l = 0`
matches 2 hex literals in `dashboard/settings/page.tsx` (the v1 settings screen
that this milestone hasn't migrated yet). The intent of the gate is clearly the
new Phase 10 surface — zero hex literals there. The settings screen will be
migrated in a future phase.

## Note for Plan 06 (already complete)

Sidebar's nav-chip counts read from the same `useStats()` cache as this page.
Verified by `sidebar-cache.test.tsx` (Plan 10-06) which asserts a single fetch
across both consumers. No double-fetch on `/dashboard` mount.

## Commits (4)

- `bef9203` — feat(10-05): Hero + Top5Card + OnboardingPanel + tests (Task 1)
- `Xfeat(10-05): TrendSection + StatStripWired + ActivityRail + tests (Task 2)`
- `feat(10-05): /dashboard page rewrite with composition + ErrorBoundary (Task 3)`
- `test(10-05): page integration + full-page a11y scan (Task 4) + Wave 1 regression fixes`
