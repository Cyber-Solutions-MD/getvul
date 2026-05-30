---
phase: 12-assets-list-detail
plan: 05
subsystem: frontend/data-layer
tags: [tanstack-query, hooks, assets, types]
requires:
  - frontend/src/lib/queries/keys.ts (existing — extended)
  - frontend/src/lib/queries/use-vulnerabilities.ts (existing — extended)
  - frontend/src/lib/api.ts (existing — unchanged)
provides:
  - "queryKeys.assets namespace (list, byId, vulnerabilities, remediations, savedFilters)"
  - "queryKeys.assignableUsers namespace (all, search)"
  - "VulnerabilitiesFilters.asset_id field + buildSearchParams threading"
  - "useAssets(opts) — list hook with buildSearchParams"
  - "useAsset(id) — detail hook with enabled gate"
  - "useAssetVulnerabilities(id) — Phase 11 wrapper, cache-key-disambiguated"
  - "useAssetRemediations(id) — tickets?asset_id"
  - "useAssignableUsers(search) — /users/directory with >=2-char gate"
  - "AssetSummary / AssetDetail / DirectoryUser / RemediationTicket / AssetsResponse / RemediationsResponse / AssignableUsersResponse types"
affects:
  - "Downstream Plan 12-06 (/assets list page) consumes useAssets"
  - "Downstream Plan 12-07 (/assets/[id] detail) consumes useAsset + useAssetVulnerabilities + useAssetRemediations + useAssignableUsers"
tech-stack:
  added: []
  patterns:
    - "TanStack Query v5 hook factory + co-located buildSearchParams (Phase 11 D-D-03)"
    - "api<T>(path, { signal }) function-call style with AbortSignal threading (Phase 10)"
    - "Wrapper hook reuses existing hook with cache-key disambiguation via filter param"
key-files:
  created:
    - frontend/src/lib/queries/use-assets.ts
    - frontend/src/lib/queries/use-assets.test.ts
    - frontend/src/lib/queries/use-asset-detail.ts
    - frontend/src/lib/queries/use-asset-detail.test.ts
    - frontend/src/lib/queries/use-asset-vulnerabilities.ts
    - frontend/src/lib/queries/use-asset-vulnerabilities.test.ts
    - frontend/src/lib/queries/use-asset-remediations.ts
    - frontend/src/lib/queries/use-asset-remediations.test.ts
    - frontend/src/lib/queries/use-assignable-users.ts
    - frontend/src/lib/queries/use-assignable-users.test.ts
  modified:
    - frontend/src/lib/queries/keys.ts
    - frontend/src/lib/queries/use-vulnerabilities.ts
decisions:
  - "useAssetVulnerabilities is a thin wrapper over Phase 11 useVulnerabilities — single source of truth for vuln listing; cache disambiguation falls out of filters.asset_id being part of the query key"
  - "useAssignableUsers gates fetch on search.length >= 2 to skip empty/single-char calls; debouncing the term itself lives in the combobox component (Plan 12-07)"
  - "Plan-prescribed api.get(...) replaced with api<T>(path, { signal }) — matches actual @/lib/api surface (Rule 3 deviation)"
  - "Risk-band -> min_risk uses LOWEST threshold across selected bands so OR semantics work (Critical+Medium -> min_risk=20 returns everything down to medium)"
metrics:
  duration_minutes: ~30
  completed: 2026-05-30
  tasks: 3
  files_created: 10
  files_modified: 2
  commits: 4
  tests_added: 15
  tests_passing: 37
---

# Phase 12 Plan 05: `/assets` Data-Layer Hooks Summary

Stood up the full frontend data layer for the `/assets` list + detail surface: extended `queryKeys` with `assets` and `assignableUsers` namespaces, threaded `asset_id` through Phase 11's `VulnerabilitiesFilters`, and shipped 5 TanStack Query hooks (`useAssets`, `useAsset`, `useAssetVulnerabilities`, `useAssetRemediations`, `useAssignableUsers`) with co-located URL-composition tests per the Phase 11 D-D-03 pattern.

## What was built

### Task 1 (commit `6ad8560`) — queryKey + filter extension

`frontend/src/lib/queries/keys.ts` gained two new namespaces:

- `queryKeys.assets`: `all`, `list({ filters, page, sort, order })`, `byId(id)`, `vulnerabilities(id)`, `remediations(id)`, `savedFilters()` — covers every endpoint the detail page composes.
- `queryKeys.assignableUsers`: `all`, `search(q)` — keyed per search term so different combobox queries don't thrash each other's cache.

`frontend/src/lib/queries/use-vulnerabilities.ts` extended:

- `VulnerabilitiesFilters` gained `asset_id?: string`.
- `buildSearchParams` appends `asset_id=<id>` when set — this is what makes `useAssetVulnerabilities` a no-op wrapper on top of `useVulnerabilities`.

### Task 2 (commits `c51c4d2` RED + `656b650` GREEN) — useAssets + useAsset

**`useAssets(opts)`** — `GET /api/v1/assets` with `buildSearchParams` exported for tests:

| Filter | Wire shape |
|--------|------------|
| `category[]` | `device_category=<CSV>` |
| `risk_band[]` | `min_risk=<lowest threshold>` (critical=80, high=50, medium=20, low=0) |
| `source[]` | `scanner=<CSV>` |
| `os_family[]` | `os_family=<CSV>` (W4 — backend OR-joins per Plan 12-01 Task 2) |
| `search` | `search=<q>` |
| `page` / `sort` / `order` | `page=N` / `sort_by=...` / `sort_dir=...` |

**`useAsset(id)`** — `GET /api/v1/assets/{id}` with `enabled: !!id`. Returns `AssetDetail` (vuln_counts + tags + sla_breach + directory_user + identity/host metadata).

7 buildSearchParams tests cover empty filters, risk-band-to-min-risk-lowest mapping, CSV joining for category/source/os_family, single-value pass-through, and search/sort/order threading. 2 query-key tests cover byId stability + per-id divergence.

### Task 3 (commit `1b24cae`) — wrapper + remediations + directory

**`useAssetVulnerabilities(id)`** — thin wrapper that calls `useVulnerabilities({ filters: { asset_id: id }, group: 'cve', page: 1, sort: '', order: 'desc' })`. The TanStack cache key naturally differentiates from the global `/vulnerabilities` list because `filters.asset_id` is part of the key shape.

**`useAssetRemediations(id)`** — `GET /api/v1/tickets?asset_id={id}&page=1`. Returns `RemediationsResponse` (note `pages`, not `total_pages` — matches backend `ticketing/service.py`). Backend orders by `ticket_created_at desc` (D-D-02).

**`useAssignableUsers(search)`** — `GET /api/v1/users/directory?status=active&search=<q>&page_size=25`. RESEARCH §2 — hits `/users/directory` (canonical User table), NOT `/users` (device-rollup view). Gates fetch on `search.trim().length >= 2` to skip the empty/single-char calls; the search term itself is debounced upstream in the combobox component (Plan 12-07).

6 query-key composition tests cover the cache-disambiguation contracts.

## Locked Types (downstream pages consume verbatim)

```ts
export type AssetSummary = {
  id: string;
  hostname: string | null;
  os_name: string | null;
  device_category: string | null;
  risk_score: number | null;
  seen_by_sources: string[] | Record<string, unknown>;
  assigned_user: string | null;
  tags: string[] | null;
  total_vulns: number;
  critical: number;
  high: number;
  exploitable: number;
  kev: number;
  sla_breach_count: number;
};

export type DirectoryUser = {
  email: string;
  display_name: string | null;
  department: string | null;
  job_title: string | null;
  avatar_url: string | null;
  groups: string[];
  idp_source: string | null;
  is_active: boolean;
  role: string | null;
};

export type AssetDetail = {
  id: string;
  hostname: string | null;
  os_name: string | null;
  os_version: string | null;
  device_category: string | null;
  risk_score: number | null;
  seen_by_sources: string[] | Record<string, unknown>;
  assigned_user: string | null;
  tags: string[] | null;
  sla_breach: number;
  vuln_counts: {
    total: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
    exploitable: number;
    kev: number;
    sla_breach: number;
  };
  directory_user: DirectoryUser | null;
  ip_addresses: string[] | null;
  mac_addresses: string[] | null;
  serial_number: string | null;
  model: string | null;
  managed_by: string | null;
  last_checkin_at: string | null;
  building: string | null;
  department: string | null;
};

export type RemediationTicket = {
  id: string;
  provider: string | null;
  external_ticket_url: string | null;
  external_status: string | null;
  assignee: string | null;
  title: string | null;
  subtitle: string | null;
  max_severity: string | null;
  vuln_count: number;
  critical_count: number;
  high_count: number;
  ticket_created_at: string | null;
  resolved_at: string | null;
};
```

## Verification

| Check | Result |
|-------|--------|
| `pnpm vitest run src/lib/queries` (full subtree) | 37/37 tests pass (11 test files) |
| `pnpm tsc --noEmit` | clean |
| `grep -n "assets:" frontend/src/lib/queries/keys.ts` | matches namespace block |
| `grep -n "asset_id?: string;" frontend/src/lib/queries/use-vulnerabilities.ts` | 1 hit |
| All 5 hook files + 5 test files exist | confirmed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Plan prescribed non-existent `api.get(path)` API**
- **Found during:** Task 2 (also affects Task 3)
- **Issue:** Plan code used `api.get(...)` and `api.post(...)` member-style calls. The actual `@/lib/api` exports a function `api<T>(path, options): Promise<T>` (see Phase 11's `use-vulnerabilities.ts` and `frontend/src/lib/api.ts`). Plan-as-written would fail to compile.
- **Fix:** All 5 new hooks use the function-call form `api<T>(path, { signal })`. Threaded `signal` into every `queryFn` to honor the Phase 10 cancellation pattern (RESEARCH Pattern 5).
- **Files modified:** `use-assets.ts`, `use-asset-detail.ts`, `use-asset-remediations.ts`, `use-assignable-users.ts` (and the test-file imports unchanged because they import from `./use-vulnerabilities`).
- **Commits:** `656b650`, `1b24cae`

**2. [Rule 2 — Critical functionality] Added Phase-10 cancellation + sensible defaults**
- **Found during:** Task 2
- **Issue:** Plan-prescribed `queryFn: async () => api.get(...)` did not thread `signal`, so an unmounting component would not cancel an in-flight asset/ticket fetch. Plan also lacked `staleTime` / `retry` on the new hooks — Phase 11 standard is `staleTime: 30_000, retry: 1`.
- **Fix:** Every new `useQuery` block now uses `queryFn: ({ signal }) => api<T>(..., { signal })` plus `staleTime: 30_000, retry: 1`. Matches Phase 11 `use-vulnerabilities.ts` (and is what Phase 11's tests assume).
- **Files modified:** `use-assets.ts`, `use-asset-detail.ts`, `use-asset-remediations.ts`, `use-assignable-users.ts`
- **Commits:** `656b650`, `1b24cae`

### Authentication Gates

None — `@/lib/api` already wraps the bearer token and auto-refresh path; no new auth surface introduced.

## Threat Model Compliance

- **T-12-06 (cross-tenant asset probe via useAsset):** Backend owns the scope check (`Asset.tenant_id == user.tenant_id` in `get_asset`); frontend `useAsset` intentionally does not add a tenant filter. Comment in `use-asset-detail.ts` does not call this out — the contract lives in the backend handler.
- **T-12-14 (useAssignableUsers tenant leak):** Accepted — `/users/directory` already restricts to the caller's tenant in `backend/app/users/router.py` (~line 267). Hook header comment documents this.
- **T-12-15 (combobox per-keystroke spam):** Mitigated downstream in Plan 12-07's combobox (debounce). Hook gates fetch on `>=2` chars to trim the obvious zero-value tail; debouncing the search term itself is the consumer's responsibility. Hook header comment documents this.

## TDD Gate Compliance

- Task 2: RED commit `c51c4d2` (test-only, fails on missing `./use-assets`) → GREEN commit `656b650` (implementation passes 9/9). ✓
- Task 3: Tests + implementation committed together (`1b24cae`) because the test assertions are over already-existing infrastructure from Task 1 (`queryKeys.assets.remediations`, `queryKeys.assignableUsers.search`, `buildSearchParams.asset_id`). The hook files themselves don't introduce assert-able URL/key composition — they only wire dependencies. A separate RED gate would have produced trivially-passing tests, so the gate was collapsed. Documented here for traceability.

## Known Stubs

None — every hook has a real query function with the correct backend route.

## Self-Check: PASSED

Verification — all files / commits asserted to exist:

```
FOUND: frontend/src/lib/queries/use-assets.ts
FOUND: frontend/src/lib/queries/use-assets.test.ts
FOUND: frontend/src/lib/queries/use-asset-detail.ts
FOUND: frontend/src/lib/queries/use-asset-detail.test.ts
FOUND: frontend/src/lib/queries/use-asset-vulnerabilities.ts
FOUND: frontend/src/lib/queries/use-asset-vulnerabilities.test.ts
FOUND: frontend/src/lib/queries/use-asset-remediations.ts
FOUND: frontend/src/lib/queries/use-asset-remediations.test.ts
FOUND: frontend/src/lib/queries/use-assignable-users.ts
FOUND: frontend/src/lib/queries/use-assignable-users.test.ts
FOUND commit: 6ad8560 (Task 1: queryKeys + asset_id filter)
FOUND commit: c51c4d2 (Task 2 RED)
FOUND commit: 656b650 (Task 2 GREEN)
FOUND commit: 1b24cae (Task 3)
```
