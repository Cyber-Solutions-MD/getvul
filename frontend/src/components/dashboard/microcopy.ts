// Minimal subset of dashboard microcopy needed by Plan 10-04 (TrendChart).
// This is a stub created by Plan 10-04 because Plan 10-02 (wave-0 dependency)
// has not yet landed on this worktree branch — its outputs will be merged by
// the orchestrator after all wave-1 parallel agents complete. The canonical
// microcopy.ts from Plan 10-02 is a superset of these strings and will
// overwrite this file at merge time (verbatim D-Ax-01 + copy-voice values).
//
// Verbatim strings (D-Ax-01 + D-C-04 + D-C-07):
//   - trend.h2 = '30-day vulnerability trend'
//   - trend.todaySoFar = 'Today (so far)'
//   - trend.range7d / range30d / range90d = '7d' / '30d' / '90d'
'use client';

export const microcopy = {
  trend: {
    h2: '30-day vulnerability trend',
    todaySoFar: 'Today (so far)',
    range7d: '7d',
    range30d: '30d',
    range90d: '90d',
    range7dA11y: '7 days',
    range30dA11y: '30 days',
    range90dA11y: '90 days',
  },
} as const;
