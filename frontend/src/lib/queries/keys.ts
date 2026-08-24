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
    // Phase 36 (SLA-03, D-07): escalation-fire history list in the drill panel.
    escalations: (id: string) => ['vulnerabilities', id, 'escalations'] as const,
    // Phase 38 (WR-03 fix): member-hosts list on the campaign detail page
    // (GET /vulnerabilities/remediations/{id}/hosts) -- previously an inline
    // key bypassing this registry.
    remediationHosts: (remediationId: string) =>
      ['vulnerabilities', 'remediation-hosts', remediationId] as const,
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
  // Phase 32 (32-05) — /dashboard/asset-groups management surface.
  assetGroups: {
    all: ['asset-groups'] as const,
    list: () => ['asset-groups', 'list'] as const,
    members: (groupId: string) => ['asset-groups', groupId, 'members'] as const,
    exposureContext: (groupId: string) =>
      ['asset-groups', groupId, 'exposure-context'] as const,
  },
  savedFilters: {
    all: ['saved-filters'] as const,
    list: () => ['saved-filters', 'list'] as const,
  },
  // Phase 12 — /assets surface.
  assets: {
    all: ['assets'] as const,
    list: (opts: {
      filters: object;
      page: number;
      sort: string;
      order: string;
    }) => ['assets', 'list', opts] as const,
    byId: (id: string) => ['assets', 'detail', id] as const,
    vulnerabilities: (id: string) => ['assets', id, 'vulnerabilities'] as const,
    remediations: (id: string) => ['assets', id, 'remediations'] as const,
    savedFilters: () => ['assets', 'saved-filters'] as const,
  },
  assignableUsers: {
    all: ['assignable-users'] as const,
    search: (q: string) => ['assignable-users', 'search', q] as const,
  },
  // Phase 13 — /tickets surface. Single source; Plans 07/08/09 import these read-only.
  tickets: {
    all: ['tickets'] as const,
    list: (opts: { filters: object; page: number; view: string }) =>
      ['tickets', 'list', opts] as const,
    byId: (id: string) => ['tickets', 'detail', id] as const,
    comments: (id: string) => ['tickets', id, 'comments'] as const,
    watchers: (id: string) => ['tickets', id, 'watchers'] as const,
    rules: () => ['tickets', 'rules'] as const,
  },
  // Phase 14 — Wave 0 namespace extension (14-00 Task 2).
  // cspm, settings, directoryUsers consumed by Plans 14-01 through 14-05.
  cspm: {
    all: ['cspm'] as const,
    list: (opts: { filters: object; page: number }) =>
      ['cspm', 'list', opts] as const,
    detail: (id: string) => ['cspm', 'detail', id] as const,
    stats: () => ['cspm', 'stats'] as const,
    compliance: () => ['cspm', 'compliance'] as const,
  },
  settings: {
    all: ['settings'] as const,
    tenant: () => ['settings', 'tenant'] as const,
    users: () => ['settings', 'users'] as const,
    auditLog: (opts: {
      action?: string;
      resource_type?: string;
      user_email?: string;
      page: number;
    }) => ['settings', 'audit-log', opts] as const,
    groups: () => ['settings', 'groups'] as const,
  },
  directoryUsers: {
    all: ['directory-users'] as const,
    list: (opts: { filters: object; page: number; sort: string; order: string }) =>
      ['directory-users', 'list', opts] as const,
    stats: () => ['directory-users', 'stats'] as const,
  },
  // Phase 24 (24-05) — AI Explanation cache-check. resourceType/resourceId
  // parameterized (D-15) so host/remediation views share the same key shape.
  // (24-10) status — the require_viewer "is AI configured" boolean signal;
  // tenant-scoped server-side so no tenant/id needs to be part of the key.
  // (28-04) usage — the require_admin usage/cost aggregation pane's single key.
  ai: {
    explain: (resourceType: string, resourceId: string) =>
      ['ai', 'explain', resourceType, resourceId] as const,
    status: () => ['ai', 'status'] as const,
    usage: () => ['ai', 'usage'] as const,
  },
  // Phase 38 (38-04) — /dashboard/campaigns list + detail surface. GET
  // /api/v1/campaigns has no filter/pagination params (D-07 compute-on-read
  // returns the full tenant-scoped list every time; the status chip-bar
  // filters client-side) so `list()` takes no opts, unlike `tickets.list`.
  campaigns: {
    all: ['campaigns'] as const,
    list: () => ['campaigns', 'list'] as const,
    detail: (id: string) => ['campaigns', 'detail', id] as const,
  },
  // Phase 39 (39-06) — /dashboard/exceptions manage-only list surface. GET
  // /api/v1/exceptions has no filter/pagination params (mirrors campaigns'
  // D-07 compute-on-read full-tenant-list precedent) so list() takes no
  // opts; the chip-bar filters + client-side pagination apply over the
  // fetched array. No detail key — the row's inline-expand accordion reads
  // from the already-fetched list array, not a per-row fetch.
  exceptions: {
    all: ['exceptions'] as const,
    list: () => ['exceptions', 'list'] as const,
  },
  // Phase 38 (38-05) — /dashboard/vulnerabilities/remediations entry point
  // (CAMP-01). GET /api/v1/vulnerabilities/remediations/grouped supports
  // page/page_size (plus severity/exploit/kev/search/device_type filters
  // this plan's minimal entry point doesn't surface yet) — list() takes an
  // opts object so pagination stays part of the cache key, mirroring
  // tickets.list's shape rather than campaigns.list's no-opts shape.
  remediationsGrouped: {
    all: ['remediations-grouped'] as const,
    list: (opts: { page: number; pageSize: number }) =>
      ['remediations-grouped', 'list', opts] as const,
  },
  // Phase 41 (41-01, COV-01) — /dashboard/coverage blind-spot-detection
  // tracer slice. GET /api/v1/coverage/blind-spots supports page/page_size
  // (mirrors tickets.list's opts-object shape so pagination stays part of
  // the cache key). `summary()` is added now (no opts) so Plan 02 (COV-02
  // coverage strip, GET /api/v1/coverage/summary) needs no re-touch here.
  coverage: {
    all: ['coverage'] as const,
    summary: () => ['coverage', 'summary'] as const,
    blindSpots: (opts: { page: number }) => ['coverage', 'blind-spots', opts] as const,
  },
  // Phase 42 (42-01, TREND-01..03) — /dashboard/analytics tracer slice. ONE
  // combined read (single compute pass, D-13's live-on-read shape) so
  // overview() takes the full scope+window opts object as its cache key
  // (mirrors tickets.list's opts-object shape, not coverage.summary's
  // no-arg shape). `scope`/`from`/`to` are placeholders this plan's hook
  // always passes as scope:'all'/undefined — Plan 03 wires group scope +
  // custom range through fully without needing to re-touch this key shape.
  analytics: {
    all: ['analytics'] as const,
    overview: (opts: { scope: string; window: string; from?: string; to?: string }) =>
      ['analytics', 'overview', opts] as const,
  },
  // Phase 43 (43-01, RPT-03) — /dashboard/compliance tracer slice. GET
  // /api/v1/compliance/overview has no filter/pagination params (mirrors
  // coverage.summary's no-arg shape) so overview() takes no opts; the
  // framework chip bar filters the fetched array client-side. Top-level
  // key, distinct from the pre-existing CSPM-nested `cspm.compliance()`
  // above — no collision (different top-level property name).
  compliance: {
    all: ['compliance'] as const,
    overview: () => ['compliance', 'overview'] as const,
  },
} as const;
