---
phase: 11
plan: 07
status: complete
completed: 2026-05-26
commits:
  - "5d780b8 refactor(11-07): retrofit top5-card to SkeletonTable + PartialFailureBanner"
  - "7afce0f refactor(11-07): retrofit trend-section error → PartialFailureBanner"
  - "7f1dce1 refactor(11-07): retrofit activity-rail error → PartialFailureBanner"
  - "e4bab23 refactor(11-07): retrofit stat-strip-wired error → PartialFailureBanner"
  - "44a2f4e refactor(11-07): retrofit onboarding-panel to EmptyState compound primitive"
key-files:
  modified:
    - frontend/src/components/dashboard/top5-card.tsx
    - frontend/src/components/dashboard/trend-section.tsx
    - frontend/src/components/dashboard/activity-rail.tsx
    - frontend/src/components/dashboard/stat-strip-wired.tsx
    - frontend/src/components/dashboard/onboarding-panel.tsx
requirements: [UX-S-01, UX-S-02, UX-S-03]
---

## What was built

Retrofitted the 5 Phase 10 dashboard child components flagged in
11-RESEARCH.md §Phase 10 Retrofit Audit to consume Phase 11's canonical
state primitives. Per CONTEXT.md §D-S-06, this happened IN Phase 11
(not deferred) so the dashboard's inline-minimal UI is uniformly
replaced by Phase 11's canonical primitives.

### Component retrofits

1. **top5-card.tsx** — inline `animate-pulse` skeleton → `<SkeletonTable
   columns=[…] rows=5>` (4-column shape matching the real Top-5 row);
   inline error `<p>` → `<PartialFailureBanner source="Top 5">`.
2. **trend-section.tsx** — inline error `<p>` → `<PartialFailureBanner
   source="Trend">`. Loading kept as `<TrendChartSkeleton>` per D-C-03
   chart-bundle split (the chart skeleton has chart-aware shape that
   SkeletonTable can't match).
3. **activity-rail.tsx** — inline error `<p>` → `<PartialFailureBanner
   source="Activity">`. Loading kept inline (non-table shape; rail-style
   skeleton not in primitive vocabulary).
4. **stat-strip-wired.tsx** — inline error `<p>` → `<PartialFailureBanner
   source="Stats">`. Loading kept inline (4-tile grid; not table-shaped).
5. **onboarding-panel.tsx** — both `'no_scanners'` and `'no_data_yet'`
   variants now use the `<EmptyState>` compound primitive (`<EmptyState.Title>`,
   `<EmptyState.Body>`, `<EmptyState.Actions>`).

## Verification

```
$ npx vitest run src/components/dashboard/
 Test Files  5 passed (5)
      Tests  31 passed (31)
```

No Phase 10 dashboard test regression. All 5 retrofitted components keep
their existing test contracts.

## Deviations

**Resumed from stalled worktree:** Plan 11-07 originally dispatched to
worktree agent `a878d1c92acef58e5`. The agent committed top5-card +
trend-section (commits 5d780b8 + 7afce0f) and had activity-rail
uncommitted in working tree when the stream watchdog stalled. The
orchestrator extracted the uncommitted activity-rail diff via stash,
applied it inline on main, and finished the remaining 2 retrofits
(stat-strip-wired, onboarding-panel) inline. No behavioral drift from
the planned approach — each retrofit still landed as its own atomic
commit per the D-S-06 commitment.

## Key links honored

- 5 dashboard components → `@/components/states` canonical primitives
  via `from '@/components/states'` imports — all 5 files now import
  from the canonical barrel (SkeletonTable + PartialFailureBanner +
  EmptyState).
