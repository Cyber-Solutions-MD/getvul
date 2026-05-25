// Single source of TanStack cache keys per D-D-03. Domain-first nesting so
// `queryKeys.vulnerabilities.all` invalidates the entire vulnerability subtree
// (snooze / unsnooze relies on this — see use-snooze.ts, use-undo-snooze.ts).
export const queryKeys = {
  vulnerabilities: {
    all: ['vulnerabilities'] as const,
    stats: () => ['vulnerabilities', 'stats'] as const,
    trends: (range: '7d' | '30d' | '90d') =>
      ['vulnerabilities', 'trends', { range }] as const,
    topTriage: (limit = 5) =>
      ['vulnerabilities', 'top-triage', { limit }] as const,
    dashboardTiles: () => ['vulnerabilities', 'dashboard-tiles'] as const,
    // Phase 11 (D-D-03 extension) — the locked contract Phase 12+ inherits.
    list: (opts: {
      filters: object;
      group: string;
      page: number;
      sort: string;
      order: string;
    }) => ['vulnerabilities', 'list', opts] as const,
    detail: (id: string) => ['vulnerabilities', 'detail', id] as const,
  },
  notifications: {
    all: ['notifications'] as const,
    recent: (limit = 5) => ['notifications', 'recent', { limit }] as const,
  },
  // Phase 11.
  connectors: {
    all: ['connectors'] as const,
    list: () => ['connectors', 'list'] as const,
  },
  savedFilters: {
    all: ['saved-filters'] as const,
    list: () => ['saved-filters', 'list'] as const,
  },
} as const;
