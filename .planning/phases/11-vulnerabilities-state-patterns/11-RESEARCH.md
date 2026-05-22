# Phase 11: `/vulnerabilities` + State Patterns — Research

**Researched:** 2026-05-22
**Domain:** Next.js 15 + React 19 frontend (chip-bar list page with side-panel drill, multi-value URL state, cross-phase state-pattern primitives) + FastAPI/SQLAlchemy backend extensions (facets, by-host grouping, expanded sort, POST /tickets).
**Confidence:** HIGH on stack + integration patterns (Phase 10 already cemented TanStack v5, sunset tokens, `useUrlState` clamp, ErrorBoundary, copy-voice contract); MEDIUM on `vaul` (library unmaintained — last release 2024-12-14, but explicitly supports React 19 via peerDeps and Phase 9/15 already committed to it); MEDIUM on `useQueryErrors` design (no first-party TanStack v5 hook — must compose from `QueryCache.subscribe` + `findAll`).

## Summary

Phase 11 is **not a greenfield design phase**. CONTEXT.md locks 33 implementation decisions (D-S-01..07, D-F-01..05, D-P-01..06, D-T-01..04, D-V-01..04) covering every architectural choice — primitive APIs, URL contract shapes, action confirmation semantics, faceting strategy, by-host grouping at the backend, retrofit list. The research job is to verify each locked decision integrates cleanly with the existing stack (Phase 9 sunset tokens, Phase 10 TanStack Query setup + `useUrlState` + Card/ErrorBoundary/Toast primitives, FastAPI SQLAlchemy 2.0 async patterns) and surface the concrete code patterns the planner can paste into PLAN.md tasks.

**Three things drive the most planning risk** and got the deepest investigation: (1) `vaul` integration for the mobile bottom-sheet drill panel — verified `Drawer.NestedRoot` is the official stacked-modal pattern, library is unmaintained but explicitly supports React 19 (peerDeps `^19.0.0`); (2) `useQueryErrors` — TanStack v5 has no first-party hook for "watch errors across a key set", so the implementation must subscribe to `QueryCache` and re-render via `useSyncExternalStore`, with the queryCache events as the snapshot source; (3) faceting math in SQLAlchemy — facets must be computed under "all OTHER filters applied", which requires N+1 separate count queries unless we use FILTER-clause aggregations in one round trip. The plan must specify the FILTER-clause approach to avoid 6 round trips per page load.

**Primary recommendation:** Wave 0 = backend endpoint extensions (POST /tickets exists, just needs FE typing); Wave 1 = state-pattern primitives + `useQueryErrors` + `useUrlStateList` in isolation (these are the contract Phases 12-14 inherit, so they ship first and get exercised by the page rewrite); Wave 2 = chip-bar + table + drill panel composed against Wave 1 primitives; Wave 3 = Phase 10 retrofit (6 inline-minimal sites swapped for canonical primitives) + UAT.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Multi-value URL filter state (`?severity=critical&severity=high`) | Browser/Client (`useUrlStateList`) | Frontend Server (Next.js router.replace) | URL is the source of truth per Phase 10 D-D-04; React reads via `useSearchParams().getAll(key)`; XSS clamp happens client-side before render |
| Facet counts contextual to filters | API/Backend (FILTER-clause aggregation) | — | One SQL round-trip with `count(*) FILTER (WHERE severity='CRITICAL')` per facet; client-side faceting would require pulling unpaginated rows |
| By-host grouping (`?group=host`) | API/Backend (GROUP BY hostname + severity counts) | — | Server-side per D-V-01; client cannot paginate a 10k→500-row group |
| Drill-panel state (`?cve=...&open=drill`) | Browser/Client (URL-encoded) | — | Reload-restorable per D-P-02; closes Phase 10's Top5Card link contract |
| Mobile bottom-sheet (<900px) | Browser/Client (`vaul` Drawer.Root portal) | — | Media-query-driven branch; same drill-panel content, different container |
| Per-source health composition | Browser/Client (compose `/connectors` + facet endpoint via `useQueries.combine`) | API/Backend (no new endpoint) | D-V-02 explicitly composes — no new backend surface |
| Stale-row tinting | Browser/Client (consume `useQueryErrors` → row.source match) | — | D-V-04 derives staleness client-side; zero schema change |
| Action confirmation (Create ticket) | Browser/Client (`ConfirmModal` portal) | API/Backend (`POST /api/v1/tickets`) | Modal is presentational; mutation hook handles 401-restriction per Phase 10 BL-06 |
| Keyboard table nav | Browser/Client (`<tr tabindex="0">` + keydown handler) | — | WAI-ARIA simple-table pattern, not `role="grid"` — see Pitfall 5 |
| Failed-query error events | Browser/Client (`QueryCache.subscribe` + `useSyncExternalStore`) | — | TanStack v5 has no first-party hook; build the bridge |

## Standard Stack

### Core (already in deps — no install needed except `vaul`)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `next` | 15.5.13 [VERIFIED: package.json] | App Router, `useSearchParams`, route segments | Project standard since Phase 9 |
| `react` | 19.0.0 [VERIFIED: package.json] | UI runtime; `useSyncExternalStore` for `useQueryErrors`; native ErrorBoundary primitive | Project standard |
| `@tanstack/react-query` | 5.100.10 [VERIFIED: package.json] (latest is 5.100.11 — within minor diff, no action needed) | List + facet queries, mutation, cache invalidation, `useQueries.combine` for status strip | Phase 10 D-D-01 locked |
| `vaul` | 1.1.2 [VERIFIED: npm registry, published 2024-12-14, peerDeps `react: ^16.8 \|\| ^17.0 \|\| ^18.0 \|\| ^19.0.0 \|\| ^19.0.0-rc`] | Mobile bottom-sheet for drill panel <900px; `Drawer.NestedRoot` for ConfirmModal-inside-drawer stacking | Industry standard React drawer; explicitly React-19 compatible; **library is unmaintained** (see Pitfall 8) — Phase 15 already committed to it (UX-07-02), so we accept the risk and pin the version |
| `recharts` | 2.12.0 [VERIFIED: package.json] | (Not used directly in Phase 11; mentioned only for skeleton placeholder shape parity) | Phase 10 D-C-01 — no Phase 11 chart additions |
| `tailwindcss` | 3.4.0 [VERIFIED: package.json] | Utility CSS with sunset CSS-variable tokens | Phase 9 D-04 |
| `class-variance-authority` | 0.7.1 [VERIFIED: package.json] | Primitive variant API (CVA pattern Phase 9 D-19) | Project standard |
| `clsx` + `tailwind-merge` | 2.1.1 / 2.6.1 [VERIFIED: package.json] | `cn()` utility | Project standard |
| `lucide-react` | 0.383.0 [VERIFIED: package.json] | Icons (close ×, alert, refresh, lightbulb, etc.) | Project standard |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `vitest` | 4.1.6 [VERIFIED: package.json] | Test runner | All `.test.tsx` files |
| `vitest-axe` | 0.1.0 [VERIFIED: package.json + npm registry; latest publish 2025-01-22] | Custom Vitest matcher for axe-core a11y assertions (`toHaveNoViolations`) | Per-primitive axe test in every state-primitive test file (D-S-07) |
| `@testing-library/react` | 16.3.2 [VERIFIED: package.json] | Component render + queries | All test files |
| `@testing-library/user-event` | 14.6.1 [VERIFIED: package.json] | Realistic keyboard events for D-T-02 nav test | Keyboard nav test |
| `jsdom` | 25.0.1 [VERIFIED: package.json] | DOM env (NOT happy-dom — vitest-axe has known bug with happy-dom's `Node.prototype.isConnected`) [CITED: vitest-axe README] | Test env |

### Alternatives Considered (DO NOT propose these to the planner — CONTEXT.md is locked)

| Instead of | Could Use | Why Locked Choice Stands |
|------------|-----------|--------------------------|
| `vaul` for mobile bottom-sheet | Radix Dialog with media-query-driven content | UX-07-02 + Phase 15 already commit to `vaul`; rip-and-replace later cost > unmaintained-library risk now |
| Server-faceting in same endpoint | `useQueries` with separate `/vulnerabilities/facets` endpoint | D-F-02 locks single combined response — fewer round trips, atomic with the list |
| `@tanstack/react-table` for table | Hand-rolled `<table>` | Not needed for 7 columns + pagination (no virtualization per D-T-03); TanStack Table adds 12kB for features we don't use |
| `role="grid"` keyboard pattern | Simple `<tr tabindex="0">` + keydown | WAI-ARIA APG warns grid is for "tabular information is editable or interactive" with multiple focusable elements per cell [CITED: w3.org/WAI/ARIA/apg/patterns/grid/]. Our rows have one focusable element (the row itself) — simple table is correct |

**Installation:**

```bash
cd frontend && npm install vaul@1.1.2
```

**Version verification commands** (planner runs before locking versions in PLAN tasks):

```bash
npm view vaul version time.modified peerDependencies
npm view @tanstack/react-query version
npm view vitest-axe version peerDependencies
```

Recorded results:
- `vaul@1.1.2`, published 2024-12-14, React 19 in peerDeps [VERIFIED: npm registry]
- `@tanstack/react-query@5.100.11`, our pin is `^5.100.10` so npm install resolves to current [VERIFIED: npm registry]
- `vitest-axe@0.1.0`, last modified 2025-01-22 [VERIFIED: npm registry]

## Architecture Patterns

### System Architecture Diagram

```
┌────────────────────────────────────── /vulnerabilities (page.tsx) ──────────────────────────────────────┐
│                                                                                                          │
│  URL ──► useSearchParams() ──► useUrlState (single)   ──► search, group, cve, open                       │
│                            └─► useUrlStateList (multi) ──► severity[], source[], status[], kev?, exploit?│
│                                                                                                          │
│  ┌─────────────────────────────────────── data layer ─────────────────────────────────────────────┐    │
│  │  useVulnerabilities({filters, group, page, sort}) ──► GET /api/v1/vulnerabilities?... + facets │    │
│  │    └─► returns { items, total, page_size, facets: { severity:{}, source:{}, status:{} } }     │    │
│  │  useVulnerabilityDetail(id)                       ──► GET /api/v1/vulnerabilities/{id}          │    │
│  │  useSavedFilters()  (read-only)                   ──► GET /api/v1/vulnerabilities/saved-filters │    │
│  │  useConnectors()                                  ──► GET /api/v1/connectors                    │    │
│  │  useCreateTicketMutation()                        ──► POST /api/v1/tickets                      │    │
│  │  useSnoozeMutation() / useUndoSnoozeMutation()    ──► (Phase 10 — reused verbatim)             │    │
│  │  useQueryErrors([...keys])                         ──► QueryCache.subscribe + findAll bridge    │    │
│  └────────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                          │                                                              │
│                                          ▼                                                              │
│  ┌─────────────────── presentation tree ───────────────────────┐                                       │
│  │ <PartialFailureBanner />  (consumes useQueryErrors default) │                                       │
│  │ <PerSourceStatusStrip />  (consumes useConnectors + facets) │                                       │
│  │ <ChipBar>                                                    │                                       │
│  │   <SearchInput debounced=250ms />                            │                                       │
│  │   <SeverityChip /> × 4 (with facet counts)                   │                                       │
│  │   <SourceChip /> × N (from facets, not hardcoded — D-F-03)   │                                       │
│  │   <SavedFilterPill />  (read-only — D-F-04)                  │                                       │
│  │   <ClearAllButton />                                         │                                       │
│  │ <ViewToggle group="cve|host" />                              │                                       │
│  │ <work-area grid="1fr {panelOpen ? 420px : 0}">               │                                       │
│  │   <table>                                                    │                                       │
│  │     <thead sticky />                                         │                                       │
│  │     <tbody>                                                  │                                       │
│  │       <tr tabindex=0 keydown=Enter|Space|↑↓|Home|End|Esc     │                                       │
│  │           data-stale={row.source in failedSources} />        │                                       │
│  │     </tbody>                                                 │                                       │
│  │   </table>                                                   │                                       │
│  │   <Pagination />                                             │                                       │
│  │   {viewportWidth < 900px ?                                   │                                       │
│  │     <vaul.Drawer.Root direction=bottom> <DrillContent />     │                                       │
│  │   : <aside.DrillPanel> <DrillContent />                      │                                       │
│  │   }                                                          │                                       │
│  │ </work-area>                                                 │                                       │
│  │ <ConfirmModal>  (ticket-create, opens via vaul.NestedRoot    │                                       │
│  │                  when on mobile — D-P-04)                    │                                       │
│  │ <Toast>  (Phase 9, undo-snooze + ticket-created)             │                                       │
│  └──────────────────────────────────────────────────────────────┘                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘

        Loading state ──► <SkeletonTable rows=8 columns=[{kind:'pill',w:80},{kind:'mono',w:130},...] />
        Empty state   ──► <EmptyState> .Title .Body .Actions .Suggestion </EmptyState>
        Error state   ──► <PartialFailureBanner /> (top) + <PerSourceStatusStrip /> + stale-row tinting + footer caveat
```

### Recommended Project Structure

```
frontend/src/
├── components/
│   ├── states/                       # NEW — D-S-04: dedicated grouping
│   │   ├── skeleton-table.tsx        # D-S-01 column-aware
│   │   ├── skeleton-table.test.tsx
│   │   ├── empty-state.tsx           # D-S-02 compound component
│   │   ├── empty-state.test.tsx
│   │   ├── partial-failure-banner.tsx  # D-S-03 hybrid hook+props
│   │   ├── partial-failure-banner.test.tsx
│   │   ├── per-source-status-strip.tsx # D-V-02 + D-S-07 aria-live="polite"
│   │   ├── per-source-status-strip.test.tsx
│   │   └── index.ts                   # public barrel: @/components/states
│   ├── vulnerabilities/               # REWRITTEN — v1 surface deleted
│   │   ├── chip-bar.tsx
│   │   ├── chip-bar.test.tsx
│   │   ├── vuln-table.tsx
│   │   ├── vuln-table.test.tsx        # includes keyboard-nav test (D-T-02 / UX-07-03)
│   │   ├── drill-panel.tsx
│   │   ├── drill-panel.test.tsx
│   │   ├── drill-panel-mobile.tsx     # vaul bottom-sheet wrapper
│   │   ├── view-toggle.tsx
│   │   └── microcopy.ts               # mirrors Phase 10's microcopy.ts pattern
│   ├── ui/                            # Existing — no new primitives here
│   └── dashboard/                     # Existing — D-S-06 retrofit sites
│       ├── top5-card.tsx               # ⟵ retrofit inline skeleton + inline error
│       ├── trend-section.tsx           # ⟵ retrofit
│       ├── activity-rail.tsx           # ⟵ retrofit
│       ├── stat-strip-wired.tsx        # ⟵ retrofit
│       └── onboarding-panel.tsx        # ⟵ retrofit if applicable
├── hooks/
│   ├── use-url-state.ts               # Existing (Phase 10 + WR-04 clamp) — reused for single-value
│   └── use-url-state-list.ts          # NEW — multi-value variant
├── lib/
│   ├── queries/
│   │   ├── keys.ts                    # EXTEND with vulnerabilities.list, .detail, .facets, connectors, savedFilters
│   │   ├── use-vulnerabilities.ts     # NEW (combined list+facets per D-F-02)
│   │   ├── use-vulnerability-detail.ts # NEW
│   │   ├── use-saved-filters.ts       # NEW (read-only)
│   │   ├── use-connectors.ts          # NEW
│   │   └── use-query-errors.ts        # NEW — QueryCache subscribe bridge for D-S-03
│   └── mutations/
│       ├── use-create-ticket.ts       # NEW
│       ├── use-snooze.ts              # Existing (Phase 10) — drill panel reuses
│       └── use-undo-snooze.ts         # Existing
└── app/(authed)/dashboard/
    └── vulnerabilities/
        ├── page.tsx                   # FULL REWRITE — 658 v1 lines → ~150 composition lines
        └── page.test.tsx              # NEW — page-level integration test

backend/app/
├── vulnerabilities/
│   ├── router.py                      # EXTEND list_vulns with ?facets=, ?group=host, expanded ?sort=
│   ├── schemas.py                     # ADD FacetsResponse, VulnerabilityByHost
│   └── service.py                     # ADD facet computation + by-host grouping
└── ticketing/router.py                # EXISTS — POST /api/v1/tickets already wired
```

### Component Responsibilities

| Component | Responsibility | Reads | Writes |
|-----------|----------------|-------|--------|
| `<ChipBar>` | Filter UI; debounce search 250ms (D-F-01); chip click is immediate | `useVulnerabilities().data.facets` for counts | `useUrlStateList('severity')` etc. |
| `<VulnTable>` | 7-column table; sticky header; row keyboard nav (D-T-02); stale-row tinting | `useVulnerabilities().data.items`, `failedSources` from context | `?cve=...&open=drill` via `router.replace` |
| `<DrillPanel>` (desktop) | 420px right-side aside; focus management (D-P-06); 7 sections (D-P-05) | `useVulnerabilityDetail(cve)` | `?cve=&open=` (close button) |
| `<DrillPanelMobile>` (vaul) | Bottom-sheet with same content below 900px; `Drawer.NestedRoot` wraps ConfirmModal | Same as desktop | Same as desktop |
| `<ViewToggle>` | By-CVE ↔ By-Host segmented control | `?group` | `useUrlState('group', ['cve','host'], 'cve')` |
| `<SkeletonTable>` | Column-aware shimmer rows | `columns` prop, `rows` prop | None |
| `<EmptyState>` | Compound slot pattern | Children (Title/Body/Actions/Suggestion) | None |
| `<PartialFailureBanner>` | Top-of-page amber alert; hybrid mode | Default: `useQueryErrors([keys])`. Override: `errors` prop | `onRetry` callback |
| `<PerSourceStatusStrip>` | Per-connector pills row; `aria-live="polite"` | `useConnectors()` + `useVulnerabilities().data.facets.source` | None |
| `useQueryErrors([keys])` | Subscribe to QueryCache, surface failed queries by key | `QueryCache.subscribe + findAll` | None (read-only) |
| `useCreateTicketMutation()` | POST `/api/v1/tickets`; surface 401 cleanly per Phase 10 BL-06 | — | Cache invalidation on success + Toast |

### Pattern 1: Multi-value URL state (D-F-05)

**What:** A hook for chip filters that toggle a value in/out of a URL param represented as a list, with the same XSS-clamp discipline as `useUrlState` (Phase 10 WR-04).

**When to use:** Any filter that produces `?key=a&key=b` (severity chips, source chips, status chips).

**Example (recommended API — locked by D-F-05):**

```typescript
// Source: composed from Next.js 15 useSearchParams.getAll() pattern
// + Phase 10 useUrlState.ts (already in repo)
'use client';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useMemo } from 'react';

export function useUrlStateList<T extends string>(
  key: string,
  allowed: readonly T[],
  defaultValue: readonly T[] = []
): [readonly T[], (next: readonly T[]) => void, (item: T) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // getAll() reads multi-value; Next 15 ReadonlyURLSearchParams supports it.
  const raw = useMemo(() => params?.getAll(key) ?? [], [params, key]);

  // XSS clamp (mirrors WR-04 from useUrlState): keep only allow-listed values.
  const value: readonly T[] = useMemo(
    () => raw.filter((v): v is T => (allowed as readonly string[]).includes(v)),
    [raw, allowed]
  );

  const setValue = useCallback(
    (next: readonly T[]) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      sp.delete(key);
      // Filter through the allow-list on write too (defense in depth).
      next
        .filter((v) => (allowed as readonly string[]).includes(v))
        .forEach((v) => sp.append(key, v));
      const qs = sp.toString();
      const target = qs ? `${pathname}?${qs}` : (pathname ?? '/');
      router.replace(target, { scroll: false });
    },
    [router, pathname, params, key, allowed]
  );

  // Convenience: toggle one item in/out.
  const toggle = useCallback(
    (item: T) =>
      setValue(
        value.includes(item) ? value.filter((v) => v !== item) : [...value, item]
      ),
    [value, setValue]
  );

  return [value.length ? value : defaultValue, setValue, toggle];
}
```

**Test surface (must include):**
- `getAll` returns allow-listed values when URL has multiple `?severity=...&severity=...`
- Garbage value in URL is dropped (XSS clamp)
- `toggle('critical')` adds when absent, removes when present
- Empty array → URL has no key at all (clean URL)
- Coexists with `useUrlState('search', ...)` on same page (different keys = no interference)

### Pattern 2: Combined list + facets in one query (D-F-02)

**What:** Single `useQuery` reads `{ items, total, facets }` from one endpoint round-trip. Avoids two-query coordination (chip counts and table data update together).

**When to use:** Any list endpoint that ships facets in the same response shape.

**Example:**

```typescript
// Source: composed from TanStack v5 useQuery + Phase 10 use-stats.ts pattern
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type VulnerabilitiesFilters = {
  severity?: readonly string[];
  source?: readonly string[];
  status?: readonly string[];
  search?: string;
  kev_only?: boolean;
  exploit_only?: boolean;
};

export type FacetsResponse = {
  severity: Record<string, number>;
  source: Record<string, number>;
  status: Record<string, number>;
};

export type VulnerabilitiesResponse = {
  items: VulnerabilitySummary[] | VulnerabilityByHost[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  facets: FacetsResponse;
};

function buildSearchParams(opts: {
  filters: VulnerabilitiesFilters;
  group: 'cve' | 'host';
  page: number;
  sort: string;
}): URLSearchParams {
  const sp = new URLSearchParams();
  opts.filters.severity?.forEach((s) => sp.append('severity', s));
  opts.filters.source?.forEach((s) => sp.append('source', s));
  opts.filters.status?.forEach((s) => sp.append('status', s));
  if (opts.filters.search) sp.set('search', opts.filters.search);
  if (opts.filters.kev_only) sp.set('cisa_kev', 'true');
  if (opts.filters.exploit_only) sp.set('exploit_available', 'true');
  sp.set('facets', 'severity,source,status');
  if (opts.group === 'host') sp.set('group', 'host');
  sp.set('page', String(opts.page));
  if (opts.sort) sp.set('sort', opts.sort);
  return sp;
}

export function useVulnerabilities(opts: {
  filters: VulnerabilitiesFilters;
  group: 'cve' | 'host';
  page: number;
  sort: string;
}) {
  return useQuery({
    queryKey: queryKeys.vulnerabilities.list(opts),
    queryFn: ({ signal }) =>
      api<VulnerabilitiesResponse>(
        `/api/v1/vulnerabilities?${buildSearchParams(opts).toString()}`,
        { signal }
      ),
    staleTime: 30_000, // facets must reflect filter state without thrashing
    retry: 1,          // D-D-07 — list is most-visible
  });
}
```

**Query key extension (`lib/queries/keys.ts`):**

```typescript
vulnerabilities: {
  all: ['vulnerabilities'] as const,
  // ...existing entries...
  list: (opts: { filters: object; group: string; page: number; sort: string }) =>
    ['vulnerabilities', 'list', opts] as const,
  detail: (id: string) => ['vulnerabilities', 'detail', id] as const,
},
connectors: {
  all: ['connectors'] as const,
  list: () => ['connectors', 'list'] as const,
},
savedFilters: {
  all: ['saved-filters'] as const,
  list: () => ['saved-filters', 'list'] as const,
},
```

### Pattern 3: `useQueryErrors` via QueryCache subscription (D-S-03)

**What:** Reads error state across a set of query keys, re-rendering when any of them transitions to/from error. TanStack v5 has no first-party hook for this — compose using `useSyncExternalStore` + `QueryCache.subscribe + findAll`.

**When to use:** `<PartialFailureBanner />` default mode; anywhere a banner aggregates failures across multiple in-flight queries.

**Example:**

```typescript
// Source: synthesized from TanStack v5 QueryCache API + React 19 useSyncExternalStore.
// VERIFIED via Context7: QueryCache.subscribe + findAll patterns documented at
// tanstack.com/query/latest/docs/reference/QueryCache.
'use client';
import { useSyncExternalStore, useMemo } from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';

export type QueryError = {
  queryKey: QueryKey;
  error: Error;
  code: number | string;
  requestId: string;
};

function extractCode(err: Error): number | string {
  // Phase 10 microcopy.ts pattern: error objects carry .code via api.ts.
  return (err as { code?: number | string }).code ?? 'unknown';
}
function extractRequestId(err: Error): string {
  return (err as { requestId?: string }).requestId ?? 'unknown';
}

/**
 * Watch a set of query keys for error state. Re-renders when any matching
 * query's status flips.
 *
 * @param keys — array of partial query keys (e.g. `[['vulnerabilities'], ['connectors']]`).
 *               Uses `queryCache.findAll({ queryKey })` partial-match semantics.
 */
export function useQueryErrors(keys: readonly QueryKey[]): QueryError[] {
  const qc = useQueryClient();
  const cache = qc.getQueryCache();

  // Subscribe → snapshot. The snapshot is the list of errored queries that
  // partially match any key in `keys`. React re-renders only when the snapshot
  // reference changes (we memoize below).
  const subscribe = useMemo(
    () => (cb: () => void) => cache.subscribe(cb),
    [cache]
  );

  const getSnapshot = useMemo(
    () => () => {
      const errors: QueryError[] = [];
      for (const key of keys) {
        for (const q of cache.findAll({ queryKey: key })) {
          if (q.state.status === 'error' && q.state.error) {
            errors.push({
              queryKey: q.queryKey,
              error: q.state.error as Error,
              code: extractCode(q.state.error as Error),
              requestId: extractRequestId(q.state.error as Error),
            });
          }
        }
      }
      return errors;
    },
    [cache, keys]
  );

  // useSyncExternalStore needs a referentially-stable snapshot for "no change"
  // to skip render. We hash the error list and only return a new array when
  // the hash changes.
  return useSyncExternalStoreWithSelector(subscribe, getSnapshot);
}

// Helper: minimal stabilization since useSyncExternalStore re-renders on any
// snapshot reference change. We compare by serialized fingerprint.
function useSyncExternalStoreWithSelector(
  subscribe: (cb: () => void) => () => void,
  getSnapshot: () => QueryError[]
): QueryError[] {
  let cached: { fingerprint: string; value: QueryError[] } | null = null;
  return useSyncExternalStore(
    subscribe,
    () => {
      const next = getSnapshot();
      const fp = next.map((e) => `${JSON.stringify(e.queryKey)}|${e.code}|${e.requestId}`).join(',');
      if (cached && cached.fingerprint === fp) return cached.value;
      cached = { fingerprint: fp, value: next };
      return next;
    },
    // SSR fallback: no errors during server render.
    () => []
  );
}
```

**Test surface (must include):**
- Returns `[]` when no queries are erroring
- Returns errors for queries matching the provided keys (partial-match semantics)
- Re-renders the consuming component when a query transitions success → error
- Re-renders when a query transitions error → success (banner disappears)
- SSR returns `[]` (server snapshot)

### Pattern 4: Compound component primitive (D-S-02 EmptyState)

**What:** Slot subcomponents attached via `Object.assign`, mirroring Phase 10's `Card` / `Card.Header` / `Card.Body` / `Card.Footer` pattern.

**When to use:** `EmptyState` per D-S-02. Same pattern reused if future primitives need composition.

**Example (mirrors `frontend/src/components/ui/card.tsx` verbatim style):**

```typescript
// Source: extending the Phase 10 Card pattern (card.tsx lines 22-69)
'use client';
import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

const EmptyStateRoot = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="status"            // D-S-07: explicit role
      aria-live="polite"
      className={cn(
        'mx-auto max-w-xl rounded-lg border border-border-subtle bg-surface p-10 text-center',
        className
      )}
      {...props}
    />
  )
);
EmptyStateRoot.displayName = 'EmptyState';

const EmptyStateTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h2 ref={ref} className={cn('text-xl font-semibold text-text', className)} {...props} />
  )
);
EmptyStateTitle.displayName = 'EmptyState.Title';

const EmptyStateBody = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('mt-3 text-text-muted', className)} {...props} />
  )
);
EmptyStateBody.displayName = 'EmptyState.Body';

const EmptyStateActions = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('mt-6 flex flex-wrap justify-center gap-3', className)} {...props} />
  )
);
EmptyStateActions.displayName = 'EmptyState.Actions';

const EmptyStateSuggestion = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'mt-6 inline-flex items-start gap-2 rounded-md bg-violet-soft p-3 text-left text-sm text-violet',
        className
      )}
      {...props}
    />
  )
);
EmptyStateSuggestion.displayName = 'EmptyState.Suggestion';

export const EmptyState = Object.assign(EmptyStateRoot, {
  Title: EmptyStateTitle,
  Body: EmptyStateBody,
  Actions: EmptyStateActions,
  Suggestion: EmptyStateSuggestion,
});
```

### Pattern 5: vaul mobile bottom-sheet + nested confirmation modal (D-P-03 + D-P-04)

**What:** Below 900px, the drill panel is a `vaul` bottom-sheet. Inside it, the "Create ticket" confirmation modal opens via `Drawer.NestedRoot` to get proper stacked focus management.

**When to use:** Only the mobile branch. Desktop ≥900px uses the existing `<aside>` drill panel without vaul.

**Example (controlled `Drawer.Root` so we drive open via URL state):**

```typescript
// Source: VERIFIED via Context7 /emilkowalski/vaul docs (NestedRoot + controlled).
'use client';
import { Drawer } from 'vaul';
import { useUrlState } from '@/hooks/use-url-state';

type Props = { children: React.ReactNode; cveId: string | null };

export function DrillPanelMobile({ children, cveId }: Props) {
  const [open, setOpen] = useUrlState('open', ['drill'] as const, '' as const);

  return (
    <Drawer.Root
      open={open === 'drill' && cveId !== null}
      onOpenChange={(o) => setOpen(o ? 'drill' : ('' as 'drill' | ''))}
      direction="bottom"
      // dismissible: true (default) — Esc + swipe-down + click-overlay all close
    >
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-[9000] bg-overlay" />
        <Drawer.Content className="fixed inset-x-0 bottom-0 z-[9001] h-[92dvh] rounded-t-lg border-t border-border-subtle bg-surface">
          <Drawer.Title className="sr-only">Vulnerability detail: {cveId}</Drawer.Title>
          {children}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}

// Nested confirmation pattern for "Create ticket" from inside the drawer:
function CreateTicketConfirm({ cveId }: { cveId: string }) {
  return (
    <Drawer.NestedRoot>
      <Drawer.Trigger asChild>
        <button className="btn-cta">Create ticket</button>
      </Drawer.Trigger>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-[9100] bg-overlay" />
        <Drawer.Content className="fixed inset-x-0 bottom-0 z-[9101] rounded-t-lg bg-surface-2 p-6">
          <Drawer.Title>Create ticket for {cveId}?</Drawer.Title>
          <Drawer.Description className="mt-2 text-text-muted">
            This opens a Jira ticket. Irreversible from our side.
          </Drawer.Description>
          {/* Action row with Confirm + Cancel */}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.NestedRoot>
  );
}
```

**Why `NestedRoot` and not the existing `ConfirmModal`:** vaul handles z-index, focus trap, scroll lock for both layers. Mixing `ConfirmModal` (fixed-position div with portal) with vaul on mobile causes z-fight + focus-trap drift. On desktop where vaul isn't mounted, the existing `ConfirmModal` is fine.

**Desktop branch (no vaul):**

```typescript
// Desktop ≥900px: render a plain <aside> with custom Esc handler + focus trap.
// Existing ConfirmModal works because nothing else is fighting for focus.
export function DrillPanelDesktop({ cveId }: { cveId: string }) {
  // <aside class="drill-panel"> with focus-trap, Esc-handler, close-on-row-swap (D-P-01)
  // Focus on open → close button (D-P-06)
  // Esc / × / click-outside-panel / row-swap → close + return focus to originating row
}
```

**Viewport branching:** Use a `useMediaQuery('(max-width: 899px)')` hook (Phase 9 already has the primitive structure — re-implement here if not exported, ~10 lines). Render `<DrillPanelMobile>` or `<DrillPanelDesktop>` based on the boolean. Shared `<DrillContent>` component renders the actual sections (D-P-05).

### Pattern 6: Keyboard-navigable table without `role="grid"` (D-T-02)

**What:** Simple `<tr tabindex="0">` rows with a keydown handler implementing Enter/Space/↑/↓/Home/End/Esc — the WAI-ARIA APG "do not use grid pattern unless cells contain multiple focusable elements" guidance [CITED: w3.org/WAI/ARIA/apg/patterns/grid/].

**Example:**

```typescript
'use client';
import { useRef, useCallback, type KeyboardEvent } from 'react';

export function VulnTable({ rows, onRowOpen }: { rows: VulnerabilitySummary[]; onRowOpen: (id: string) => void }) {
  const tbodyRef = useRef<HTMLTableSectionElement>(null);

  const onRowKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTableRowElement>, id: string) => {
      const tbody = tbodyRef.current;
      if (!tbody) return;
      const rows = Array.from(tbody.querySelectorAll<HTMLTableRowElement>('tr[tabindex="0"]'));
      const idx = rows.indexOf(e.currentTarget);

      switch (e.key) {
        case 'Enter':
        case ' ':
          e.preventDefault();
          onRowOpen(id);
          return;
        case 'ArrowDown':
          e.preventDefault();
          rows[Math.min(idx + 1, rows.length - 1)]?.focus();
          return;
        case 'ArrowUp':
          e.preventDefault();
          rows[Math.max(idx - 1, 0)]?.focus();
          return;
        case 'Home':
          e.preventDefault();
          rows[0]?.focus();
          return;
        case 'End':
          e.preventDefault();
          rows[rows.length - 1]?.focus();
          return;
        // Esc handled at the panel level (closes panel + returns focus to originating row, D-P-06)
      }
    },
    [onRowOpen]
  );

  return (
    <table className="w-full">
      <thead className="sticky top-0 z-10 bg-surface">
        <tr>{/* column headers */}</tr>
      </thead>
      <tbody ref={tbodyRef}>
        {rows.map((row) => (
          <tr
            key={row.id}
            tabIndex={0}
            onClick={() => onRowOpen(row.cve_id ?? row.id)}
            onKeyDown={(e) => onRowKeyDown(e, row.cve_id ?? row.id)}
            // D-V-04: stale-row tinting via data-attribute
            data-stale={undefined /* set by table consumer from failedSources */}
            className="cursor-pointer hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet data-[stale=true]:bg-amber-soft/40"
          >
            {/* 7 column cells */}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

### Pattern 7: Per-source status strip composition (D-V-02)

**What:** Compose `/api/v1/connectors` (list of enabled connectors + last sync) with the facet endpoint's source counts. Use `useQueries.combine` so both are observed in one snapshot. `aria-live="polite"` for screen-reader updates without focus stealing (D-S-07).

**Example:**

```typescript
'use client';
import { useQueries } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queries/keys';
import { api } from '@/lib/api';

type ConnectorRow = {
  id: string;
  type: string;          // 'QUALYS' | 'TENABLE' | 'AWS_INSPECTOR' | ...
  last_sync_at: string | null;
  last_sync_status: 'ok' | 'syncing' | 'failed' | null;
  last_sync_record_count: number | null;
};

export function PerSourceStatusStrip({ facets }: { facets: Record<string, number> }) {
  const [connectorsQ] = useQueries({
    queries: [
      {
        queryKey: queryKeys.connectors.list(),
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          api<ConnectorRow[]>('/api/v1/connectors', { signal }),
        staleTime: 60_000,
      },
    ],
  });

  if (connectorsQ.isPending) return null; // ChipBar/PartialFailureBanner cover loading
  if (connectorsQ.error || !connectorsQ.data) return null;

  return (
    <div role="status" aria-live="polite" className="flex flex-wrap gap-2">
      {connectorsQ.data.map((conn) => {
        const count = facets[conn.type] ?? 0;
        const stateClass =
          conn.last_sync_status === 'ok'
            ? 'bg-success-soft text-success'
            : conn.last_sync_status === 'failed'
              ? 'bg-danger-soft text-danger'
              : conn.last_sync_status === 'syncing'
                ? 'bg-pink-soft text-pink'
                : 'bg-surface-2 text-text-muted';
        return (
          <div key={conn.id} className={`rounded-md px-3 py-1 text-xs ${stateClass}`}>
            <span className="font-mono">{conn.type}</span> · {count}
          </div>
        );
      })}
    </div>
  );
}
```

### Anti-Patterns to Avoid

- **Using `role="grid"` on the table.** Our rows have one focusable element (the row itself). Grid is for "tabular information is editable or interactive [with] data elements [as] links to more information" — overkill, and screen readers announce grid coordinates that confuse users [CITED: w3.org/WAI/ARIA/apg/patterns/grid/].
- **Two separate queries for list + facets.** D-F-02 locks single response. Two queries means facets thrash 250ms before/after the list and chip counts don't stay in sync with the table.
- **Computing facets client-side from `items`.** Items are paginated; facets must reflect ALL matching rows. Client-side would require pulling unpaginated data.
- **Hex literals or raw Tailwind palette utilities (`bg-red-500`, `text-emerald-400`).** Phase 9 D-04 + Phase 10 code-review lesson: only sunset tokens (`bg-danger-soft`, `text-severity-critical`, etc.).
- **`!important` anywhere.** CLAUDE.md non-negotiable.
- **Inline skeleton in every component.** D-D-11 (Phase 10) explicitly defers to Phase 11's canonical `SkeletonTable` — and D-S-06 schedules the retrofit here.
- **Optimistic updates on `useCreateTicketMutation`.** Side effect on external Jira/Asana — irreversible from our side. Confirm modal + post-success toast (D-P-04).
- **`ConfirmModal` inside a `vaul.Drawer` on mobile.** Z-fight + focus drift. Use `Drawer.NestedRoot` per D-P-04.
- **Fetching saved-filter list eagerly on every page load.** D-F-04 is read-only — fetch once, cache. Apply on chip click.
- **Pulsing/spinning skeleton without `prefers-reduced-motion` gate.** Skeleton wraps shimmer in `motion-safe:` Tailwind variant; reduced motion shows static surface-2 blocks.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Mobile bottom-sheet | Custom drawer with portal + drag handlers | `vaul@1.1.2` | Drag gestures, focus trap, scroll lock, snap points, swipe-to-close — vaul handles all of them. Pinned at 1.1.2 (unmaintained — see Pitfall 8) |
| Stacked modals (confirm-inside-drawer) | Manual z-index + focus dance | `Drawer.NestedRoot` | vaul's nested pattern auto-handles overlay z-index, background scaling, focus return [VERIFIED: Context7 /emilkowalski/vaul] |
| URL-synced filter state | `useEffect + window.history.replaceState` | `useUrlState` + new `useUrlStateList` | Phase 10 already proved the pattern works with XSS clamp (WR-04) |
| Cache invalidation across mutations | Manual setState in 4 places | TanStack Query `invalidateQueries({ queryKey: ['vulnerabilities'] })` | Phase 10 D-D-13 — invalidates entire subtree |
| Debounce search input | `setTimeout` + `clearTimeout` in component | A small `useDebouncedValue<T>(value, ms)` hook | 8-line hook, easy to test in isolation; component stays clean |
| Per-row keyboard navigation | Add hotkey library | Native keydown handler (Pattern 6) | We need 6 specific keys; library is over-engineering for ~30 lines |
| Skeleton shimmer animation | Custom `@keyframes` | CSS `background-position` shift gated by `motion-safe:` | Tailwind `animate-shimmer` config — accessibility built in [CITED: developer.mozilla.org/.../prefers-reduced-motion] |
| Compound primitive APIs | Context-provider gymnastics | `Object.assign(Root, { Title, Body, Actions, Suggestion })` | Phase 10 Card already uses it; type-safe, zero runtime cost [CITED: tkdodo.eu/blog/building-type-safe-compound-components] |
| Reading TanStack errors across multiple queries | Polling `queryClient.getQueryState` from useEffect | `useSyncExternalStore` + `QueryCache.subscribe` (Pattern 3) | Reactive, SSR-safe, follows React 19 idiom |
| Facet SQL math (client-side post-fetch) | Loop items, increment counters | Backend `count(*) FILTER (WHERE severity='CRITICAL')` | One query, accurate across full result set, paginated rows don't lie |

**Key insight:** Phase 11 is mostly about composing existing primitives (Phase 9 sunset tokens; Phase 10 Card / ErrorBoundary / Toast / TanStack hooks / `useUrlState`) plus four new state primitives. Resist any pull toward bespoke implementations — the cross-phase contract requires that Phases 12/13/14 reuse Phase 11 primitives verbatim.

## Common Pitfalls

### Pitfall 1: Facet counts that contradict the visible table
**What goes wrong:** Backend returns facets with `Severity.CRITICAL=12` but the visible table doesn't have 12 critical rows.
**Why it happens:** Faceting is computed under "all OTHER filters except the one we're showing", not "all current filters". When severity=CRITICAL is already applied, the critical chip should still show the count *as if severity weren't applied* — so the user can see "I'd add 12 rows if I removed this filter" without de-toggling.
**How to avoid:** Backend computes each facet group's count by re-running the query with that group's filter removed. The SQL pattern using FILTER clauses keeps it one round-trip:

```sql
SELECT
  count(*) FILTER (WHERE severity='CRITICAL') AS sev_critical,
  count(*) FILTER (WHERE severity='HIGH')     AS sev_high,
  ...
FROM vulnerabilities
WHERE tenant_id = :tid
  -- ALL filters EXCEPT severity applied here
  AND (source = ANY(:sources) OR :sources IS NULL)
  AND (status = ANY(:statuses) OR :statuses IS NULL);
```

Each facet group needs its own subquery in this style. Pattern carries to source/status the same way.
**Warning signs:** User toggles a chip and the count it just displayed doesn't match the new row count.

### Pitfall 2: Drill-panel URL race with router.replace
**What goes wrong:** Click row → URL updates → drill panel opens but with stale CVE because the URL→state propagation is asynchronous.
**Why it happens:** `router.replace` is async. The DrillPanel reads `?cve=` via `useSearchParams`; in Next 15 this is a Suspense-bailable hook and updates synchronously, but state derived from it via `useMemo`/`useState` may lag one render.
**How to avoid:** Read the CVE param directly from `useSearchParams()` in the DrillPanel and skip useMemo. Let the panel render `null` when the param is missing or doesn't match a known CVE (D-P-13 implicit). Don't pre-resolve in `page.tsx` and pass down.
**Warning signs:** Clicking row #2 right after row #1 shows row #1's content briefly. Reload restores correct CVE.

### Pitfall 3: vaul unmount on viewport resize
**What goes wrong:** User opens drawer on mobile, rotates to landscape (≥900px), the page swaps `<DrillPanelMobile>` for `<DrillPanelDesktop>`, the URL still says `open=drill` — but the desktop panel doesn't know vaul opened it.
**Why it happens:** Both branches read `?cve=&open=` so both will render. Desktop will show side-panel; mobile drawer unmounts gracefully. **Risk:** if the controlled state isn't truly URL-driven, the desktop panel might not open.
**How to avoid:** Mount one branch at a time via media query, but both read from the SAME URL state. The URL is the single source of truth. Vaul's `open` prop reads URL → branch switch is transparent.
**Warning signs:** Test by resizing browser with drawer open — content should stay visible, container changes shape.

### Pitfall 4: useQueryErrors snapshot identity churn
**What goes wrong:** `useQueryErrors` returns a new array on every QueryCache event, causing `<PartialFailureBanner>` to re-render constantly even when no actual error transition happened.
**Why it happens:** `QueryCache.subscribe` fires for *every* state event (loading, success, error, refetch, ...), not just transitions [CITED: github.com/TanStack/query/discussions/846 — "invalidating a query caused the callback to trigger six times"]. Naive `getSnapshot` returns `[]` six times in a row, each a new array reference.
**How to avoid:** Stabilize snapshot identity by fingerprinting the result (see Pattern 3 implementation). React's `useSyncExternalStore` then bails out when fingerprint matches.
**Warning signs:** Profiler shows `<PartialFailureBanner>` re-rendering on every key press in search input (because chips refetch).

### Pitfall 5: Using `role="grid"` defeats native table semantics
**What goes wrong:** Screen readers announce "grid, 50 rows by 7 columns" + cell coordinates on every cell focus, which is overwhelming for users who just want to scan a vuln list.
**Why it happens:** Misreading the WAI-ARIA APG — "grid for interactive tables" is the *complex case* (editable cells, multi-focus per cell), not the *interactive rows* case.
**How to avoid:** Plain `<table>` + `<tr tabindex="0">` + keydown handler. The screen reader announces "row" and reads cells in DOM order — what users expect [CITED: w3.org/WAI/ARIA/apg/patterns/grid/].
**Warning signs:** Axe-core may pass either approach; user testing with NVDA/JAWS would surface the verbosity.

### Pitfall 6: Saved-filter pill applying stale filter shape
**What goes wrong:** Saved filter was created in v1 with a filter shape `{ exploit_available: true }` but Phase 11 uses `?exploit_only=true`. Pill click applies bad shape.
**Why it happens:** v1 frontend used different param names; backend saved-filter table stores frontend's filter blob verbatim.
**How to avoid:** Planner reads `backend/app/vulnerabilities/saved_filters.py` to understand the stored shape; adds a translation layer or only consumes the "first" saved filter as a feature-flag-style trigger that maps to canonical Phase 11 filter shape. D-F-04 keeps it minimal — read first saved filter, apply its `filters` object via translation.
**Warning signs:** Pill click sets URL params that don't match the chip allow-list (gets clamped to empty).

### Pitfall 7: vaul's stacked-drawer Esc key only closes the top layer
**What goes wrong:** User opens drill drawer, opens nested confirm — Esc closes confirm but not the drill (correct), then second Esc closes drill (correct). But on some browser implementations the Esc bubbles and closes both.
**Why it happens:** Browser dispatches keydown to topmost element; vaul stops propagation in `NestedRoot` but only after its own handler runs.
**How to avoid:** Test the Esc cascade explicitly. vaul handles it correctly per Context7 docs, but the test must verify behavior. If broken, override Esc with explicit handlers per drawer level.
**Warning signs:** "I lost my drill panel state when I cancelled the modal."

### Pitfall 8: vaul is unmaintained — version pin required
**What goes wrong:** Future React/Next.js update breaks vaul; we have no upstream fix path. README says "This repo is unmaintained" [CITED: github.com/emilkowalski/vaul, 2024-12-14 final release].
**Why it happens:** Author paused maintenance after 1.1.2.
**How to avoid:** (a) Pin EXACTLY to `1.1.2` (no caret) in package.json to prevent surprise. (b) Note in PLAN that if vaul breaks under a future React 20 or Next 16, the fallback is `vaul-base` (community fork, built on Base UI) or rolling our own minimal drawer. (c) Restrict vaul to the mobile branch only — desktop drill stays plain `<aside>`, so vaul breakage degrades to "desktop works, mobile doesn't" rather than total UI loss.
**Warning signs:** Dependabot PR opens vaul to a new minor version — block it; verify changelog before accepting.

### Pitfall 9: Skeleton column kinds don't survive forced-colors mode
**What goes wrong:** In Windows High Contrast / forced-colors mode, the shimmer gradients disappear (system colors override), leaving invisible skeletons.
**Why it happens:** `@media (forced-colors: active)` strips all CSS backgrounds and replaces with system colors.
**How to avoid:** Skeletons must use `border` (system colors honor borders) in addition to background. In forced-colors mode, render as bordered placeholder rectangles — still visually "loading-shape" without depending on gradient. Phase 10 D-Ax-06 already handles globals.css.
**Warning signs:** Toggle Edge "Force colors" emulator — skeletons must remain perceivable.

### Pitfall 10: 250ms debounced search races with chip clicks
**What goes wrong:** User types in search, immediately clicks a chip before 250ms elapses. Two URL updates collide; one wins.
**Why it happens:** D-F-01 makes chip clicks synchronous and search debounced. Last-write-wins on URL state without coordination.
**How to avoid:** Search debouncer flushes its pending update on any chip click (the chip-click handler reads current search input value and writes both at once). Or: debouncer uses `useTransition` so updates queue rather than race.
**Warning signs:** "I typed 'log4j' then clicked Critical and my search vanished."

## Code Examples

### Sunset-tokenized SkeletonTable (D-S-01)

```typescript
// Source: state-patterns.md + sketch 004 + Phase 9 sunset tokens.
'use client';
import { cn } from '@/lib/utils';

export type SkeletonColumnKind = 'pill' | 'mono' | 'text' | 'badge';
export type SkeletonColumn = { kind: SkeletonColumnKind; width: number };

type Props = { rows?: number; columns: SkeletonColumn[]; className?: string };

const KIND_BG: Record<SkeletonColumnKind, string> = {
  // Sunset-tinted pill shimmer (state-patterns.md `.skel-pill`)
  pill: 'rounded-full bg-gradient-to-r from-pink-soft via-violet-soft to-pink-soft border border-border-subtle',
  // Neutral mono-block shimmer
  mono: 'rounded bg-gradient-to-r from-surface-2 via-border to-surface-2',
  text: 'rounded bg-gradient-to-r from-surface-2 via-border to-surface-2',
  badge: 'rounded bg-gradient-to-r from-surface-2 via-border to-surface-2',
};

export function SkeletonTable({ rows = 8, columns, className }: Props) {
  return (
    <table className={cn('w-full', className)} aria-busy="true" aria-label="Loading vulnerabilities">
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r} className="border-b border-border-subtle">
            {columns.map((col, c) => (
              <td key={c} className="px-3 py-3">
                <span
                  className={cn(
                    'inline-block h-4 bg-[length:200%_100%] motion-safe:animate-shimmer',
                    KIND_BG[col.kind]
                  )}
                  style={{ width: col.width }}
                />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**Required Tailwind config addition (`tailwind.config.ts`):**

```typescript
keyframes: {
  shimmer: { from: { backgroundPosition: '200% 0' }, to: { backgroundPosition: '-200% 0' } },
},
animation: { shimmer: 'shimmer 1.6s linear infinite' },
```

`motion-safe:` variant ensures `prefers-reduced-motion: reduce` strips the animation [CITED: developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion]. The static gradient remains, communicating "loading shape" without motion.

### vitest-axe test pattern (D-S-07)

```typescript
// frontend/src/components/states/empty-state.test.tsx
// Source: vitest-axe README + Phase 10 card.test.tsx pattern.
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { EmptyState } from './empty-state';

describe('EmptyState (D-S-02 + D-S-07)', () => {
  it('has no axe violations in the canonical filtered-zero variant', async () => {
    const { container } = render(
      <EmptyState>
        <EmptyState.Title>Nothing matches all 5 filters</EmptyState.Title>
        <EmptyState.Body>That's a tight net — relax one or two and try again.</EmptyState.Body>
        <EmptyState.Actions>
          <button type="button">Clear all filters</button>
          <button type="button">Include Medium severity</button>
        </EmptyState.Actions>
        <EmptyState.Suggestion>
          Try broadening severity or removing the date range.
        </EmptyState.Suggestion>
      </EmptyState>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('exposes role="status" + aria-live for screen readers (D-S-07)', () => {
    const { getByRole } = render(<EmptyState><EmptyState.Title>x</EmptyState.Title></EmptyState>);
    const node = getByRole('status');
    expect(node).toHaveAttribute('aria-live', 'polite');
  });
});
```

**Required setup file (`vitest-setup.ts`):**

```typescript
import * as matchers from 'vitest-axe/matchers';
import { expect } from 'vitest';
import '@testing-library/jest-dom/vitest';
expect.extend(matchers);
```

**Required `vitest.config.ts` change:**

```typescript
export default defineConfig({
  test: {
    environment: 'jsdom',           // NOT happy-dom — vitest-axe is incompatible
    setupFiles: ['./vitest-setup.ts'],
  },
});
```

[CITED: vitest-axe README — happy-dom incompatibility with axe via `Node.prototype.isConnected`]

### Keyboard-nav test for the vuln table (UX-07-03 partial)

```typescript
// frontend/src/components/vulnerabilities/vuln-table.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VulnTable } from './vuln-table';

const fixture = [
  { id: '1', cve_id: 'CVE-2024-0001', severity: 'CRITICAL', /* ... */ },
  { id: '2', cve_id: 'CVE-2024-0002', severity: 'HIGH', /* ... */ },
  { id: '3', cve_id: 'CVE-2024-0003', severity: 'MEDIUM', /* ... */ },
];

describe('VulnTable keyboard navigation (D-T-02 / UX-07-03)', () => {
  it('ArrowDown moves focus to next row', async () => {
    const user = userEvent.setup();
    render(<VulnTable rows={fixture} onRowOpen={() => {}} />);
    const rows = screen.getAllByRole('row').filter((r) => r.getAttribute('tabindex') === '0');
    rows[0].focus();
    await user.keyboard('{ArrowDown}');
    expect(rows[1]).toHaveFocus();
  });

  it('Home/End jump to first/last row', async () => {
    const user = userEvent.setup();
    render(<VulnTable rows={fixture} onRowOpen={() => {}} />);
    const rows = screen.getAllByRole('row').filter((r) => r.getAttribute('tabindex') === '0');
    rows[1].focus();
    await user.keyboard('{End}');
    expect(rows[rows.length - 1]).toHaveFocus();
    await user.keyboard('{Home}');
    expect(rows[0]).toHaveFocus();
  });

  it('Enter/Space fires onRowOpen with the row id', async () => {
    const onRowOpen = vi.fn();
    const user = userEvent.setup();
    render(<VulnTable rows={fixture} onRowOpen={onRowOpen} />);
    const row = screen.getAllByRole('row').find((r) => r.getAttribute('tabindex') === '0')!;
    row.focus();
    await user.keyboard('{Enter}');
    expect(onRowOpen).toHaveBeenCalledWith('CVE-2024-0001');
  });
});
```

### Backend FILTER-clause faceting (D-F-02)

```python
# backend/app/vulnerabilities/service.py — extension of list_vulnerabilities
from sqlalchemy import select, func, case

async def get_facets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filters: VulnerabilityFilter,
) -> dict:
    """Per-group facets contextual to OTHER applied filters.

    For severity facets: re-apply all filters EXCEPT severity, then GROUP BY severity.
    Same shape for source and status. One query per facet group => 3 round trips,
    not N. (Could be unified with WITH ... but separate is clearer to read.)
    """
    # Severity facet — apply all OTHER filters
    f_no_sev = filters.model_copy(update={"severity": None})
    sev_q = (
        _apply_filters(
            select(Vulnerability.severity, func.count(Vulnerability.id)),
            tenant_id,
            f_no_sev,
        )
        .group_by(Vulnerability.severity)
    )
    sev_rows = (await db.execute(sev_q)).all()

    f_no_src = filters.model_copy(update={"source": None})
    src_q = (
        _apply_filters(
            select(Vulnerability.source, func.count(Vulnerability.id)),
            tenant_id,
            f_no_src,
        )
        .group_by(Vulnerability.source)
    )
    src_rows = (await db.execute(src_q)).all()

    f_no_status = filters.model_copy(update={"status": None})
    status_q = (
        _apply_filters(
            select(Vulnerability.status, func.count(Vulnerability.id)),
            tenant_id,
            f_no_status,
        )
        .group_by(Vulnerability.status)
    )
    status_rows = (await db.execute(status_q)).all()

    return {
        "severity": {s: c for s, c in sev_rows},
        "source": {s: c for s, c in src_rows},
        "status": {s: c for s, c in status_rows},
    }
```

**Why 3 separate queries are acceptable:** Each is a single `count(*) GROUP BY <col>` over an indexed column with tenant_id filter. Postgres plans these as index scans completing in <50ms each for typical tenants. A unified CTE could combine them but adds query complexity for negligible savings.

**Note for planner:** `?facets=severity,source,status` query param. If facets not requested, skip the work (don't return the `facets` key in the response).

### Backend by-host grouping (D-V-01)

```python
# backend/app/vulnerabilities/service.py — new function
async def list_vulnerabilities_by_host(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filters: VulnerabilityFilter,
    pagination: PaginationParams,
) -> PaginatedResponse[VulnerabilityByHost]:
    """Group vulns by host with denormalized severity counts.

    Pagination is on HOST rows, not vuln rows (10k vulns on 500 hosts = 500 paginatable rows).
    """
    base = (
        _apply_filters(select(Vulnerability), tenant_id, filters)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
    )
    grouped = (
        select(
            Asset.hostname.label("host"),
            Asset.id.label("asset_id"),
            func.count(Vulnerability.id).label("vuln_count"),
            func.count(case((Vulnerability.severity == "CRITICAL", 1))).label("critical_count"),
            func.count(case((Vulnerability.severity == "HIGH", 1))).label("high_count"),
            func.count(case((Vulnerability.severity == "MEDIUM", 1))).label("medium_count"),
            func.count(case((Vulnerability.severity == "LOW", 1))).label("low_count"),
            func.max(Vulnerability.cvss_v3_score).label("top_cvss"),
        )
        .select_from(base.subquery())  # filter subquery, then group
        .group_by(Asset.hostname, Asset.id)
        .order_by(func.count(case((Vulnerability.severity == "CRITICAL", 1))).desc())
    )
    # Count distinct hosts for pagination total
    count_q = select(func.count()).select_from(grouped.subquery())
    total = (await db.execute(count_q)).scalar_one()
    page_rows = (
        await db.execute(grouped.offset((pagination.page - 1) * pagination.page_size).limit(pagination.page_size))
    ).all()
    return PaginatedResponse(items=[...], total=total, ...)
```

## Runtime State Inventory

**Trigger evaluation:** Phase 11 is a rewrite of one page surface + addition of new primitives + retrofit of 6 existing components. No rename, no migration, no string substitution. Runtime State Inventory is **NOT** a refactor risk for Phase 11 — section omitted per its trigger rule. The retrofit work (D-S-06) is a code-edit replacement of inline UI with primitive imports; no stored data, OS-registered state, or external-service config moves.

## Phase 10 Retrofit Audit (D-S-06)

CONTEXT.md commits to retrofitting 6 sites. Reading the actual files:

| File | Current Inline Pattern | Canonical Replacement | Notes |
|------|------------------------|------------------------|-------|
| `frontend/src/components/dashboard/top5-card.tsx` lines 39-48 | Inline `<div aria-busy="true" className="h-64 animate-pulse rounded-md bg-surface-2" />` for loading | `<SkeletonTable rows={5} columns={[{kind:'mono',width:40},{kind:'mono',width:130},{kind:'mono',width:40},{kind:'pill',width:60}]} />` | 4 cells: glyph + CVE/host + cvss + sla pill |
| `frontend/src/components/dashboard/top5-card.tsx` lines 50-63 | Inline `<p role="alert">{microcopy.error.inline(...)}</p>` for error | Wrap in `<PartialFailureBanner errors={[error]} requestId={reqId} onRetry={() => q.refetch()} />` — props mode | Section is the "main failure source" — props override per D-S-03 |
| `frontend/src/components/dashboard/trend-section.tsx` lines 25-32 | `<TrendChartSkeleton />` for loading | Keep — chart-specific skeleton stays per D-C-03 (chart bundle is route-split) | Not all inline skeletons retrofit; chart-shape isn't a SkeletonTable |
| `frontend/src/components/dashboard/trend-section.tsx` lines 34-47 | Inline error block | `<PartialFailureBanner errors={[error]} ... />` | Same as top5-card |
| `frontend/src/components/dashboard/activity-rail.tsx` lines 23-29 | 5 inline `<div className="h-10 rounded-md bg-surface-2 animate-pulse" />` | A new variant or new primitive — Activity feed isn't a table. Recommendation: keep activity-rail's inline pattern OR add `<SkeletonList rows={5} />` to the state primitives. **D-S-Discretion: planner extends column-kind set if needed.** Suggest adding `<SkeletonRows count={5} variant="single-line" />` as a small primitive. | Lightweight |
| `frontend/src/components/dashboard/activity-rail.tsx` lines 32-39 | Inline error `<p role="alert">` | `<PartialFailureBanner errors={[error]} ... />` | Same |
| `frontend/src/components/dashboard/stat-strip-wired.tsx` lines 17-30 | 4 inline tile skeletons | A new variant on SkeletonTable won't fit (tiles, not table). Keep inline OR extend primitive with `<StatStripSkeleton tiles={4} />`. **Planner discretion.** | Not a table |
| `frontend/src/components/dashboard/stat-strip-wired.tsx` lines 32-46 | Inline error | `<PartialFailureBanner errors={[error]} ... />` | Same |
| `frontend/src/components/dashboard/onboarding-panel.tsx` lines 36-52 | Empty-state-style panel, hand-rolled | `<EmptyState>` with .Title/.Body/.Actions slots | Onboarding states ARE empty states by another name — retrofit to canonical primitive |

**Retrofit decision boundary:** D-S-06 retrofit applies cleanly to **error states** (every error site swaps to `<PartialFailureBanner>` props-mode) and to **OnboardingPanel** (swaps to `<EmptyState>`). For **loading states**, only `top5-card.tsx` cleanly retrofits to `<SkeletonTable>` (its loading is row-shaped). Chart skeleton, activity-rail skeleton, and stat-strip skeleton stay inline OR get tiny one-off skeleton primitives — planner picks per Claude's Discretion. **Recommendation:** retrofit only what's table-shaped; document the discretion call in CONTEXT.md follow-up if needed.

**Critical:** Phase 10 `microcopy.error.inline(section, code, reqId)` returns a string. The `<PartialFailureBanner>` props mode must accept either an `error` object (preferred) or a `message` string (back-compat). Plan must define both.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.6 + @testing-library/react 16.3.2 + vitest-axe 0.1.0 |
| Config file | `frontend/vitest.config.ts` (existing — needs `environment: 'jsdom'` confirmed + `setupFiles: ['./vitest-setup.ts']` if not already wired) |
| Quick run command | `cd frontend && npx vitest run --reporter=dot path/to/file.test.tsx` |
| Full suite command | `cd frontend && npm test` |
| Backend test | `cd backend && pytest tests/test_vulnerabilities.py -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| UX-03-01 | Chip-bar renders search + severity chips + source chips + saved pill + clear-all | integration | `npx vitest run vulnerabilities/page.test.tsx` | Wave 0 (page.test.tsx new) |
| UX-03-02 | Table renders 7 columns with severity glyph + KEV badge + SLA pill | unit | `npx vitest run vulnerabilities/vuln-table.test.tsx` | Wave 0 |
| UX-03-03 | Click row opens 420px right-side panel | integration | `npx vitest run vulnerabilities/page.test.tsx` (panel-open assertion) | Wave 0 |
| UX-03-04 | URL syncs filter state immediately on chip; 250ms on search; reload restores | unit | `npx vitest run hooks/use-url-state-list.test.ts` | Wave 0 |
| UX-03-05 | View toggle switches By-CVE ↔ By-Host without losing filters | unit | `npx vitest run vulnerabilities/view-toggle.test.tsx` | Wave 0 |
| UX-03-06 | <900px → bottom-sheet drawer (vaul); table → card view | integration | `npx vitest run vulnerabilities/drill-panel-mobile.test.tsx` (matchMedia mock) | Wave 0 |
| UX-S-01 | SkeletonTable renders column-aware loading state | unit + axe | `npx vitest run components/states/skeleton-table.test.tsx` | Wave 0 |
| UX-S-02 | EmptyState compound API + lightbulb suggestion + 3-tier CTAs | unit + axe | `npx vitest run components/states/empty-state.test.tsx` | Wave 0 |
| UX-S-03 | PartialFailureBanner default + props mode; stale-row tinting | unit + axe + integration | `npx vitest run components/states/partial-failure-banner.test.tsx vulnerabilities/page.test.tsx` | Wave 0 |
| UX-S-04 | Total-failure renders EmptyState with retry CTAs (uses S-02 shell) | integration | covered by page.test.tsx full-error case | Wave 0 |
| UX-S-05 | Toast on ticket-created + filter-saved + connector-retried events (already shipped in Phase 9) | unit | existing `npx vitest run ui/toast.test.tsx` | Exists |
| UX-07-03 (partial) | Keyboard nav on table rows: Enter/Space/↑↓/Home/End/Esc | unit | `npx vitest run vulnerabilities/vuln-table.test.tsx` (keyboard suite) | Wave 0 |
| Backend `?facets=` | Per-group counts contextual to other filters | pytest | `pytest backend/tests/test_vuln_facets.py -x` | Wave 0 |
| Backend `?group=host` | One row per host with severity counts | pytest | `pytest backend/tests/test_vuln_group_host.py -x` | Wave 0 |
| Backend expanded `?sort=` | Sort by severity, cve_id, cvss_v3_score, sla_due_at asc/desc | pytest | `pytest backend/tests/test_vuln_sort.py -x` | Wave 0 |
| Backend `POST /tickets` | Returns 201 + ticket payload; 401 surfaces cleanly | pytest | `pytest backend/tests/test_tickets_create.py -x` | Exists — verify only |

### Sampling Rate
- **Per task commit:** `npx vitest run --reporter=dot path/to/touched-file.test.tsx`
- **Per wave merge:** `npm test` (frontend) + `pytest backend/tests/test_vulnerabilities*.py` (backend)
- **Phase gate:** Full suite green + axe-core in 5 primitive tests + page-level integration test green

### Wave 0 Gaps (test files to create)

- [ ] `frontend/src/components/states/skeleton-table.test.tsx` — covers UX-S-01 + axe
- [ ] `frontend/src/components/states/empty-state.test.tsx` — covers UX-S-02 + axe + compound API
- [ ] `frontend/src/components/states/partial-failure-banner.test.tsx` — covers UX-S-03 + axe + hybrid mode
- [ ] `frontend/src/components/states/per-source-status-strip.test.tsx` — covers D-V-02 + axe + aria-live
- [ ] `frontend/src/hooks/use-url-state-list.test.ts` — covers D-F-05 + XSS clamp
- [ ] `frontend/src/lib/queries/use-query-errors.test.tsx` — covers D-S-03 + QueryCache subscription
- [ ] `frontend/src/components/vulnerabilities/chip-bar.test.tsx` — covers UX-03-01 + debounce
- [ ] `frontend/src/components/vulnerabilities/vuln-table.test.tsx` — covers UX-03-02 + UX-07-03 keyboard + stale-row
- [ ] `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — covers UX-03-03 + D-P-01/02/05/06 focus
- [ ] `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — covers UX-03-06 + vaul
- [ ] `frontend/src/components/vulnerabilities/view-toggle.test.tsx` — covers UX-03-05
- [ ] `frontend/src/app/(authed)/dashboard/vulnerabilities/page.test.tsx` — page-level integration
- [ ] `frontend/src/lib/queries/use-vulnerabilities.test.tsx` — query hook contract
- [ ] `frontend/src/lib/mutations/use-create-ticket.test.tsx` — 401 surface check (Phase 10 BL-06 carryover)
- [ ] `backend/tests/test_vuln_facets.py` — covers facet endpoint contextual math
- [ ] `backend/tests/test_vuln_group_host.py` — covers by-host grouping
- [ ] `backend/tests/test_vuln_sort.py` — covers expanded sort fields
- [ ] (Verify exists) `backend/tests/test_tickets_create.py` — POST /tickets happy path + 401

**Framework install:** None — Vitest + vitest-axe + RTL already in `frontend/package.json`. Setup file (`vitest-setup.ts`) check first: if it doesn't yet exist or doesn't import vitest-axe matchers, Wave 0 adds it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build/test | ✓ (presumed; project runs on Node) | (project-defined) | — |
| npm | Frontend install | ✓ | — | — |
| Python 3 + pytest | Backend test | ✓ (Phase 10 already used) | (project-defined) | — |
| Postgres | Backend tests | ✓ (presumed — Phase 10 backend tests passed) | — | — |
| vaul package | Mobile drawer | ✗ (not yet installed) | needs `vaul@1.1.2` | None — Phase 11 requires it |

**Missing dependencies with no fallback:**
- `vaul@1.1.2` — must `npm install` in Wave 0

**Missing dependencies with fallback:** None.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (carried) | Phase 9 cookies/JWT path unchanged; Phase 10 BL-06 401 retry restriction inherited |
| V3 Session Management | yes (carried) | TanStack Query cache clears on logout (Phase 10 D-D-09); same here |
| V4 Access Control | yes | `require_viewer` / `require_analyst` on backend endpoints — POST /tickets uses `require_analyst` (existing in `ticketing/router.py`) |
| V5 Input Validation | yes | Pydantic on backend (`VulnerabilityFilter` already validates `search` max_length=200 per WR-05). Frontend: `useUrlState`/`useUrlStateList` XSS clamp before render (WR-04 → multi-value carryover). |
| V6 Cryptography | no | No crypto introduced in this phase |
| V12 Files & Resources | no | No file uploads in this surface |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reflected XSS via `?severity=<script>` | Tampering | `useUrlStateList` clamps to allow-list before render (WR-04 carryover from Phase 10 useUrlState) |
| URL parameter pollution (10× repeated values) | DoS | Backend `VulnerabilityFilter` should validate `severity: list[str] | None` length cap (recommend max=10 to match enum cardinality); frontend allow-list naturally caps |
| Unbounded search input | DoS | Backend `search` Field `max_length=200` (already in `schemas.py` line 87-89, per WR-05) |
| 401 retry replays mutation | AUDIT-01 | Phase 10 BL-06 `api.ts` already restricts retry to safe methods; `useCreateTicketMutation` MUST not silently retry on 401 — surfaces "Session expired during mutation. Please retry." (existing behavior) |
| CSRF on POST /tickets | Tampering | Bearer token in Authorization header (not cookies) — CSRF moot per Phase 9 auth design |
| IDOR on CVE drill | Information disclosure | Backend filters by `tenant_id` on every query (existing pattern in `_apply_filters`) — Phase 11 inherits |
| Saved-filter blob injection (deserialization) | Tampering | Saved filter `filters` JSON is consumed via the same `VulnerabilityFilter` Pydantic validation when applied to a query — no eval, no raw SQL |

### Security Checks Phase 11 Must Verify

- [ ] `useUrlStateList` XSS clamp test mirrors Phase 10's WR-04 test (garbage value clamped, allow-list enforced on both read AND write)
- [ ] Backend `?facets=` validates the comma-separated field against an allow-list (`severity`, `source`, `status`); unknown facet returns 400, not 500
- [ ] Backend `?group=host` enforces `?group in ('cve','host')`; unknown value 422 via Pydantic Literal
- [ ] Backend `?sort=` extended Literal enum covers the 4 new sort fields (`severity`, `cve_id`, `cvss_v3_score`, `sla_due_at`); unknown → 422
- [ ] `useCreateTicketMutation` does NOT call `tryRefreshToken` (Phase 10 BL-06 — already protected in `api.ts`); test verifies the 401 throw path
- [ ] Saved-filter JSON when applied passes through Pydantic — no `eval()`, no `**filter_dict` straight into SQLAlchemy

## Sources

### Primary (HIGH confidence)
- Context7 `/emilkowalski/vaul` — nested drawer + controlled state + props reference (25 snippets, benchmark 96.33)
- Context7 `/tanstack/query` — useQueries combine + QueryCache subscribe + findAll
- `https://tanstack.com/query/latest/docs/reference/QueryCache` — subscribe + findAll API [VERIFIED via WebFetch]
- `https://tanstack.com/query/latest/docs/framework/react/reference/useQueries` — combine option [VERIFIED via WebFetch]
- `https://nextjs.org/docs/app/api-reference/functions/use-search-params` — getAll() on ReadonlyURLSearchParams
- `https://www.w3.org/WAI/ARIA/apg/patterns/grid/` — when to use grid vs simple table [VERIFIED via WebFetch]
- `https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/` — focus return on close [VERIFIED via WebFetch]
- `https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion` — motion gate
- `npm view vaul` — version 1.1.2, React 19 in peerDeps [VERIFIED via npm registry, 2024-12-14]
- `npm view vitest-axe` — version 0.1.0, last modified 2025-01-22 [VERIFIED via npm registry]
- Local files: `.planning/phases/11-vulnerabilities-state-patterns/11-CONTEXT.md` (33 locked decisions); `.planning/phases/10-dashboard/10-CONTEXT.md` (load-bearing prior context); `.claude/skills/sketch-findings-getvul/references/{state-patterns,interaction-patterns,page-layouts,visual-language,copy-voice}.md`; `frontend/src/components/ui/card.tsx`, `error-boundary.tsx`, `Pagination.tsx`, `ConfirmModal.tsx`; `frontend/src/hooks/use-url-state.ts` + `.test.ts`; `frontend/src/lib/api.ts`; `frontend/src/lib/queries/keys.ts`, `use-stats.ts`; `frontend/src/components/dashboard/*.tsx`; `backend/app/vulnerabilities/router.py`, `service.py`, `schemas.py`; `backend/app/ticketing/router.py`, `schemas.py`; `backend/app/connectors/router.py`, `schemas.py`

### Secondary (MEDIUM confidence)
- `https://github.com/emilkowalski/vaul` README — "this repo is unmaintained" notice [VERIFIED via WebFetch]
- `https://www.npmjs.com/package/vitest-axe` — setup pattern + happy-dom incompatibility [VERIFIED via WebSearch]
- `https://tkdodo.eu/blog/the-query-options-api` — TanStack v5 queryOptions co-location pattern
- `https://medium.com/@subashnatrayan28/sliding-into-smooth-ui-my-journey-with-vaul` — vaul nested + focus management notes (community)

### Tertiary (LOW confidence — flagged for validation)
- WebSearch results on TanStack QueryCache subscribe frequency (`fires for every cache event, not just transitions`) — corroborated by community discussion #846 but not v5 docs directly; consequence: useQueryErrors must fingerprint snapshot (handled in Pattern 3).

## Project Constraints (from CLAUDE.md)

These constraints have the same authority as locked decisions:

- **Sketch-findings skill auto-loads on UI work.** Phase 11 implementations consume `.claude/skills/sketch-findings-getvul/references/*.md` verbatim — palette, severity glyphs, SLA tiers, status colors, drill-panel structure, copy voice.
- **No font substitution.** Inter + JetBrains Mono are locked (Phase 9 D-09 already wires).
- **No hex literals.** All colors via sunset CSS variables consumed through Tailwind tokens (`bg-surface`, `bg-danger-soft`, `text-severity-critical`, etc.).
- **No `!important` anywhere.** `grep -c '!important' frontend/src/app/globals.css` must remain 0.
- **No screen without empty/loading/error states.** Phase 11 produces the canonical primitives that enforce this contract going forward.
- **No Tailwind admin-template patterns.** Don't mimic shadcn examples that lean "admin dashboard SaaS" energy — see sketch-findings copy-voice.md.
- **Terse copy.** No "Please", "Welcome", "Click here", exclamation marks. Phase 11 microcopy.ts file is the single source of strings.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The vaul library will continue to install and import cleanly under React 19 + Next 15 for the lifetime of v2.0; "unmaintained" notice doesn't mean broken | Standard Stack / Pitfall 8 | Mobile drawer breaks → Phase 15's UX-07-02 commitment fails → either we fork vaul or rip it out |
| A2 | The QueryCache subscribe + findAll pattern is the correct way to build `useQueryErrors` in TanStack v5 (no first-party hook exists for this) | Pattern 3 | If TanStack v5 ships a `useQueryError` primitive, our hand-rolled hook becomes redundant. Risk: low — verified via Context7 v5 docs |
| A3 | Backend `POST /api/v1/tickets` returns a shape consumable by the frontend without modification — only need typing, no endpoint change | Code Examples / Backend FILTER-clause | If response shape doesn't match `TicketCreateRequest`/`TicketResponse` schemas in `backend/app/ticketing/schemas.py`, frontend mutation needs adapter layer |
| A4 | `motion-safe:` Tailwind variant is wired in the project's Tailwind config | Pattern + SkeletonTable code | If not wired, shimmer animation runs even under prefers-reduced-motion — accessibility regression |
| A5 | The Phase 10 `Pagination.tsx` v1-styled chrome can be carried forward into Phase 11 without restyling | D-T-03 Pagination | Visual incongruity between sunset-styled table and v1-styled pagination — Phase 11 may need to restyle (Claude's discretion already gives planner this option) |
| A6 | Saved-filter API at `/api/v1/vulnerabilities/saved-filters` returns a stable shape from v1 that we can map to canonical Phase 11 filter params | D-F-04 | Pill click applies broken filter; user sees empty results. Mitigation: planner reads `backend/app/vulnerabilities/saved_filters.py` shape before mapping |
| A7 | The 6 retrofit sites are correctly identified — no other v1 components have inline-minimal patterns that should also retrofit | D-S-06 retrofit table | Inconsistent UI across dashboard; need follow-up retrofit later |
| A8 | The "Activity rail" loading state is acceptable to leave inline (or get a tiny SkeletonRows primitive) rather than force-fit `<SkeletonTable>` to non-table content | Retrofit audit | Visual inconsistency; planner has Claude's-Discretion authority here |

**If A1 (vaul unmaintained → broken) materializes:** fallback is `vaul-base` (community fork on Base UI) or hand-rolled Radix Dialog with bottom-sheet styling. Both are recoverable; both cost a half-day.

## Open Questions

1. **Should `<DrillPanelMobile>` and `<DrillPanelDesktop>` mount conditionally or both render with one display-none?**
   - What we know: media query branch lets vaul mount only on mobile.
   - What's unclear: prevents desktop bundle from including vaul.
   - Recommendation: conditional mount via `useMediaQuery('(max-width: 899px)')`. Combined with vaul being SSR-incompatible-by-default this avoids hydration mismatch.

2. **Does the existing Pagination component need sunset restyling in Phase 11?**
   - What we know: CONTEXT.md gives planner Claude's Discretion.
   - What's unclear: the v1 styling uses `text-gray-400`, `bg-indigo-600` — raw palette utilities, which the Phase 10 review treated as debt.
   - Recommendation: restyle to sunset tokens in Phase 11 (small, low-risk; one file). Carry an `<X-PAGINATION>` TODO with the active-page pink + pink-soft styling from `interaction-patterns.md` Pagination section.

3. **Should `useCreateTicketMutation` invalidate cache or refetch the drill panel after success?**
   - What we know: drill-panel content unchanged after ticket creation (the ticket is on Jira, not in our vuln data).
   - What's unclear: do we surface the new ticket somewhere in the drill panel (e.g., activity log)?
   - Recommendation: invalidate `['notifications']` (audit emits `ticket.create` per `ticketing/router.py` line 173) and the activity feed will refresh. No drill-panel invalidation needed.

4. **What's the canonical `aria-live` politeness for the per-source status strip during streaming updates?**
   - What we know: D-S-07 specifies `aria-live="polite"`.
   - What's unclear: in practice updates poll every 30s (TanStack staleTime) — does this cause screen-reader fatigue?
   - Recommendation: `polite` is correct. Updates happen on TanStack refetch, not on every tick — frequency is naturally bounded.

5. **Should keyboard `Esc` on a focused row close any open drill panel, or only when focus is inside the panel?**
   - What we know: D-P-01 lists Esc as one of four close mechanisms.
   - What's unclear: scope — does Esc on a row in the body close the panel even if the panel is unfocused?
   - Recommendation: yes. Esc anywhere on the page closes the drill (matches modal semantics). Page-level keydown listener on the document.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Persistent left filter drawer | Chip-bar above table | sketch findings 2026-05 | Restores horizontal real estate; matches Linear/Vercel pattern |
| Full-page navigation on row click | Side-panel drill-down | sketch findings 2026-05 | Context preserved; matches Wiz / Notion table-detail UX |
| `useEffect + fetch + setState` data layer | TanStack Query v5 | Phase 10 (D-D-01) | Cache, refetch, retry, error semantics standardized; ~13kB cost |
| Custom URL-sync hooks per page | Generic `useUrlState` + `useUrlStateList` | Phase 10 (D-D-04) → Phase 11 (D-F-05) | Single XSS-clamp surface; testable in isolation |
| Storybook for component docs | `/dev/primitives` route | Phase 9 (D-31) | One less dep; matches "lean tooling" project posture |
| Drag-based mobile drawers from scratch | `vaul` (until unmaintained breaks us) | sketch findings (UX-07-02) | Focus mgmt + drag gestures + snap points come for free; risk: unmaintained |
| Backend faceting via separate endpoint | Facets in same response as list | D-F-02 (Phase 11) | One fewer round trip; chip counts stay synced with rows |
| `role="grid"` for interactive tables | `<tr tabindex="0">` + keydown for rows-as-link patterns | WAI-ARIA APG clarification | Less verbose for AT users; matches semantic intent |
| `jest-axe` for a11y tests | `vitest-axe` (Vitest-native matcher) | Vitest migration | Same API shape (`toHaveNoViolations`); no test-runner clash |

**Deprecated/outdated in this codebase:**
- v1 `VulnFilters.tsx` / `VulnTable.tsx` / `BulkActions.tsx` — deleted in Phase 11
- v1 inline `useEffect + fetch` pattern in `dashboard/vulnerabilities/page.tsx` (658 lines) — replaced by TanStack hooks
- v1-style hex-literal colors anywhere in the new files — banned

---

**Research date:** 2026-05-22
**Valid until:** 2026-06-22 (30 days — stable stack, but vaul's unmaintained status warrants a re-check at the start of Phase 12 to confirm no React 19 / Next 15 regression has emerged in the interim)

**Confidence breakdown:**
- Standard stack: HIGH — every version verified against npm registry; Phase 9/10 already prove the integration patterns
- Architecture: HIGH — CONTEXT.md locks 33 decisions; research validates each integrates cleanly
- Pitfalls: MEDIUM-HIGH — vaul unmaintained risk + QueryCache event-frequency are concrete gotchas with mitigations; the other pitfalls are well-understood Phase 10 carryovers
- vaul integration: MEDIUM — Context7 docs are clear, but the library's "unmaintained" status is a forward risk. The plan must include a fallback note.
- Backend faceting math: HIGH — SQL FILTER pattern is well-established; the SQLAlchemy implementation is mechanical.
