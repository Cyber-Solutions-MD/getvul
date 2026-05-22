---
phase: 11-vulnerabilities-state-patterns
plan: 03
subsystem: ui
tags: [frontend, hooks, tanstack-query, useSyncExternalStore, url-state, mutations, xss-clamp]

requires:
  - phase: 11-01
    provides: Backend list+facets response shape (?facets=severity,source,status) + by-host grouping
  - phase: 11-02
    provides: RED test scaffolds + vaul pin + Tailwind shimmer alias (NOTE — Plan 02 did not run in this worktree; the 4 RED test files this plan turns GREEN were authored inline, then turned GREEN as separate commits)

provides:
  - useUrlStateList<T> multi-value URL state hook with allow-list XSS clamp on READ + WRITE (D-F-05 + WR-04 carryover)
  - Extended queryKeys tree — vulnerabilities.list / .detail, connectors, savedFilters (D-D-03 domain-first)
  - useConnectors() — TanStack hook for PerSourceStatusStrip (D-V-02)
  - useSavedFilters() — read-only TanStack hook for the violet ★ Today's triage pill (D-F-04)
  - useQueryErrors([keys]) — QueryCache subscription bridge driving PartialFailureBanner default mode (D-S-03)
  - useVulnerabilities({filters,group,page,sort,order}) — combined list + facets in one round-trip (D-F-02)
  - buildSearchParams(opts) — exported helper so consumers + tests can compose URL params verbatim
  - useVulnerabilityDetail(idOrCve) — drill-panel query, disabled when input is null/empty
  - useCreateTicketMutation() — POST /api/v1/tickets with 401 surface + notifications cache invalidation (D-P-04 + BL-06)

affects:
  - phase: 11-04
    needs: State primitives (SkeletonTable / EmptyState / PartialFailureBanner / PerSourceStatusStrip) — PartialFailureBanner consumes useQueryErrors; PerSourceStatusStrip consumes useConnectors + facets
  - phase: 11-05
    needs: chip-bar consumes useUrlStateList + useSavedFilters + facets; vuln-table consumes useVulnerabilities.items; drill-panel consumes useVulnerabilityDetail + useCreateTicketMutation
  - phase: 12
    needs: query-key contract (vulnerabilities.list shape) — Phase 12 mirrors for assets.list / assets.detail
  - phase: 13
    needs: query-key contract — Phase 13 mirrors for tickets.list / tickets.detail

tech-stack:
  added:
    - useSyncExternalStore + QueryCache.subscribe bridge (no new package — composed from existing React + TanStack v5)
  patterns:
    - "Allow-list clamp on multi-value URL state — read AND write (defense in depth) — D-F-05"
    - "Fingerprint-cached useSyncExternalStore snapshot — return same array reference when watched-error set is unchanged (Pitfall 4)"
    - "Single round-trip list + facets via ?facets=severity,source,status — chip counts atomic with table data (D-F-02)"
    - "Mutation hooks surface api.ts BL-06 401 errors verbatim — no silent retry on non-safe methods"
    - "Notifications cache invalidation on ticket creation — activity feed picks up ticket.create audit event"

key-files:
  created:
    - frontend/src/hooks/use-url-state-list.ts
    - frontend/src/hooks/use-url-state-list.test.ts
    - frontend/src/lib/queries/use-connectors.ts
    - frontend/src/lib/queries/use-saved-filters.ts
    - frontend/src/lib/queries/use-query-errors.ts
    - frontend/src/lib/queries/use-query-errors.test.tsx
    - frontend/src/lib/queries/use-vulnerabilities.ts
    - frontend/src/lib/queries/use-vulnerabilities.test.tsx
    - frontend/src/lib/queries/use-vulnerability-detail.ts
    - frontend/src/lib/mutations/use-create-ticket.ts
    - frontend/src/lib/mutations/use-create-ticket.test.tsx
  modified:
    - frontend/src/lib/queries/keys.ts

key-decisions:
  - "useUrlStateList clamps allow-list on READ (XSS defense) AND WRITE (defense in depth) — caller cannot bypass UI to inject non-allow-listed values"
  - "useQueryErrors caches snapshot by JSON-stringified fingerprint so identical error sets return same array reference — prevents render churn from cache events that don't change the watched set"
  - "?facets=severity,source,status is ALWAYS appended in buildSearchParams — chip counts and table data update atomically (D-F-02)"
  - "useCreateTicketMutation retry:0 + propagates 'Session expired during mutation. Please retry.' verbatim — POST is not idempotent and the audit-trail user attribution matters more than convenience (Phase 10 BL-06 carryover)"
  - "useVulnerabilityDetail uses enabled: idOrCve !== null guard — prevents the detail request from firing before the drill panel opens"

patterns-established:
  - "useSyncExternalStore + QueryCache.subscribe — canonical bridge for any future 'watch X across a key set' hook (Phase 12 may extend for asset enrichment failures)"
  - "buildSearchParams export pattern — co-locate URL composition with the query hook so tests can assert URL shape without reaching into the network layer"
  - "Mutation hook + onSuccess invalidation against queryKeys.{domain}.all — matches Phase 10 use-snooze.ts shape; Phase 13 ticket mutations should follow"

requirements-completed:
  - UX-03-01
  - UX-03-03
  - UX-03-04
  - UX-03-05
  - UX-S-03

duration: 8 min
completed: 2026-05-22
---

# Phase 11 Plan 03: Hooks + Queries + Mutations Data Layer Summary

**TanStack data layer for /vulnerabilities — single-round-trip list+facets query, multi-value URL state with XSS clamp, QueryCache error bridge, and ticket-create mutation that surfaces 401s verbatim per BL-06.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-22T09:32:26Z
- **Completed:** 2026-05-22T09:40:42Z
- **Tasks:** 3
- **Files created:** 11 (4 RED test files + 7 implementation files)
- **Files modified:** 1 (queryKeys barrel)

## Accomplishments

- **8 new TypeScript modules** under `frontend/src/hooks/` + `frontend/src/lib/queries/` + `frontend/src/lib/mutations/` covering the entire data layer that Wave 2 components consume.
- **23/23 tests GREEN** across 4 test files; **0 regressions** in the 6 Phase 10 hook/mutation tests (use-stats, use-trends, use-snooze).
- **Query-key contract locked** for Phase 12+ — `queryKeys.vulnerabilities.list({filters,group,page,sort,order})` is the shape `/assets` and `/tickets` mirror.
- **XSS-clamp pattern extended** from Phase 10's single-value `useUrlState` to multi-value `useUrlStateList` with identical discipline (read clamp + write clamp).

## Task Commits

Each task followed RED → GREEN TDD discipline with separate commits per phase:

1. **Task 11-03-01: useUrlStateList + extended queryKeys + connectors/savedFilters**
   - `559aeab` — `test(11-03): RED test for useUrlStateList (D-F-05 + XSS clamp)`
   - `544d12e` — `feat(11-03): useUrlStateList + extended query keys + connectors/savedFilters queries`

2. **Task 11-03-02: useQueryErrors + useVulnerabilities + useVulnerabilityDetail**
   - `1178b00` — `test(11-03): RED tests for useQueryErrors + useVulnerabilities`
   - `292e4d9` — `feat(11-03): useQueryErrors + useVulnerabilities + useVulnerabilityDetail GREEN`

3. **Task 11-03-03: useCreateTicketMutation**
   - `493c331` — `test(11-03): RED test for useCreateTicketMutation (D-P-04 + BL-06 401 surface)`
   - `bd2eef8` — `feat(11-03): useCreateTicketMutation with 401 surface + notifications invalidation`

## Files Created/Modified

### Created — hooks

- `frontend/src/hooks/use-url-state-list.ts` — multi-value URL hook. Returns `[value, setValue, toggle]`. Allow-list clamp runs on both `params.getAll(key)` (READ) and the write path (WRITE) so reflected `<script>...</script>` in a shareable URL never reaches the chip-bar render tree.
- `frontend/src/hooks/use-url-state-list.test.ts` — 7 tests covering allow-list clamp, toggle idempotency, clean-URL on empty, coexistence with single-value `useUrlState`.

### Created — queries

- `frontend/src/lib/queries/use-connectors.ts` — `useConnectors()` GET `/api/v1/connectors`. `staleTime: 60_000`, `retry: 1`. Exports `ConnectorRow` type.
- `frontend/src/lib/queries/use-saved-filters.ts` — `useSavedFilters()` GET `/api/v1/vulnerabilities/saved-filters?filter_type=vulnerability`. `staleTime: 300_000` (5 min — saved filters change rarely). Read-only per D-F-04. Exports `SavedFilter` type.
- `frontend/src/lib/queries/use-query-errors.ts` — `useQueryErrors([keys])` via `useSyncExternalStore + cache.subscribe + cache.findAll`. Fingerprint-cached snapshot returns same array reference when the watched-error set is unchanged. SSR fallback returns `[]`. Exports `QueryError` type.
- `frontend/src/lib/queries/use-query-errors.test.tsx` — 6 tests covering empty-set, partial-match errors, success→error rerender, error→success rerender, SSR, fingerprint stability.
- `frontend/src/lib/queries/use-vulnerabilities.ts` — `useVulnerabilities(opts)` + exported `buildSearchParams(opts)`. `?facets=severity,source,status` always appended. `staleTime: 30_000`, `retry: 1`, `refetchOnWindowFocus: true`. Exports `VulnerabilitiesFilters`, `FacetsResponse`, `VulnerabilitySummary`, `VulnerabilityByHost`, `VulnerabilitiesResponse`.
- `frontend/src/lib/queries/use-vulnerabilities.test.tsx` — 5 tests covering queryKey shape, params composition, host-group flow, always-on facets, 401 surfacing.
- `frontend/src/lib/queries/use-vulnerability-detail.ts` — `useVulnerabilityDetail(idOrCve)` GET `/api/v1/vulnerabilities/{id}`. `enabled` gated on non-null/non-empty input.

### Created — mutations

- `frontend/src/lib/mutations/use-create-ticket.ts` — `useCreateTicketMutation()` POST `/api/v1/tickets`. `retry: 0` (defense in depth). `onSuccess` invalidates `queryKeys.notifications.all`. Exports `CreateTicketRequest` (`provider: 'ASANA' | 'JIRA' | 'GITHUB'`) + `CreateTicketResponse`.
- `frontend/src/lib/mutations/use-create-ticket.test.tsx` — 5 tests covering happy path, 401 verbatim surface, 403 detail surface, notifications invalidation, provider Literal.

### Modified

- `frontend/src/lib/queries/keys.ts` — added `vulnerabilities.list({filters,group,page,sort,order})`, `vulnerabilities.detail(id)`, `connectors.{all,list}`, `savedFilters.{all,list}`. Phase 10 entries unchanged.

## Decisions Made

- **useUrlStateList allow-list filter runs on both READ and WRITE.** READ defends against XSS in shareable URLs. WRITE defends against any caller that bypasses the chip-bar UI and calls `setValue(['evil'])` directly (e.g., a future programmatic filter helper). Belt-and-braces because the cost is one `.filter()` call and the security upside is permanent.
- **Fingerprint-cached snapshot in useQueryErrors uses `JSON.stringify(queryKey) + code + requestId`.** A pure reference-equal `errors.length` check would miss the case where two errored queries with different keys appear/disappear together. Fingerprinting on the union of identity-bearing fields is the minimum sufficient stabilization (RESEARCH §Pitfall 4).
- **buildSearchParams exported, not inlined.** Page-level tests (Plan 11-05) need to assert that URL composition stays stable across refactors. Exporting the helper makes the URL contract a testable surface rather than an implementation detail buried in the queryFn closure.
- **useCreateTicketMutation `retry: 0` is explicit rather than relying on TanStack defaults.** Documents intent; future TanStack default changes won't silently break the audit-trail contract. The 401 throw at api.ts (BL-06) already throws before the mutation's retry policy applies, so `retry: 0` is defense in depth.
- **useVulnerabilityDetail uses `enabled: idOrCve !== null && idOrCve !== ''`** instead of throwing on null input. Allows the drill panel to mount unconditionally and toggle the query on/off via URL state without ConditionalHookCalls.

## Deviations from Plan

### Significant Deviation: Plan 02 Wave 0 did not run in this worktree

**Issue:** Plan 11-03's frontmatter declares `wave: 1, depends_on: [11-01, 11-02]`. The prompt instructs me to "turn the 6 RED hook/query/mutation tests from Plan 02 GREEN". However, this worktree was spun up from commit `9e368a9` (planning complete) — Plan 02 itself never ran in any visible history, and the 4 RED test files it was supposed to scaffold (`use-url-state-list.test.ts`, `use-query-errors.test.tsx`, `use-vulnerabilities.test.tsx`, `use-create-ticket.test.tsx`) did not exist on disk.

**Decision (Rule 3 — Blocking):** Author the RED tests inline against Plan 02's specification (Plan 02 Task 02 `<behavior>` block) and then turn them GREEN. The alternative was to halt — but Plan 02's spec is fully captured in its `<behavior>` blocks, so the test surface is unambiguous. Authoring inline preserves the TDD gate sequence (separate `test(...)` and `feat(...)` commits per task) without losing the contract.

**Tracking:**
- 4 RED test files committed under `test(11-03): …` messages: `559aeab`, `1178b00`, `493c331`. (The `1178b00` commit bundles 2 test files in one commit because they belong to the same task per Plan 11-03's task structure.)
- 7 GREEN implementation files committed under `feat(11-03): …`: `544d12e`, `292e4d9`, `bd2eef8`.
- TDD gate sequence is preserved per task (RED commit precedes GREEN commit chronologically).

**Out-of-scope Plan 02 work NOT done here** (no impact on this plan's success criteria):
- `vaul@1.1.2` install — irrelevant to the 6 RED tests this plan targets (mobile drill-panel work lives in Plan 11-05).
- `animate-shimmer` Tailwind alias — irrelevant (SkeletonTable lives in Plan 11-04).
- The 10 RED tests Plan 02 was also supposed to scaffold for state primitives + vuln-page components — those are Plan 11-04 and Plan 11-05 inputs and must be addressed by those plans' executors. Documented in `deferred-items.md` if needed.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] node_modules symlinked into worktree**
- **Found during:** Task 11-03-01 (running RED vitest)
- **Issue:** `npx vitest run` failed with "Cannot find package 'vitest'" because the worktree has no `node_modules` (Claude Code worktrees don't replicate node_modules from the main checkout).
- **Fix:** `ln -s /Users/chemencedji/Desktop/getvul/frontend/node_modules frontend/node_modules`. The symlink lives in the worktree only and was never staged (matches the gitignore rule for symlink-as-file).
- **Files modified:** none staged (symlink remains untracked).
- **Verification:** `npx vitest run` resolves dependencies cleanly afterwards.
- **Committed in:** N/A — infrastructure-only.

**2. [Rule 1 - Test flakiness] waitFor timeout for 401 surface test**
- **Found during:** Task 11-03-02 (Test 5 in use-vulnerabilities.test.tsx)
- **Issue:** The test asserted `result.current.isError === true` within the default 1000ms waitFor timeout, but `useVulnerabilities` has `retry: 1` with TanStack's default exponential backoff (~1000ms between attempts) — the error state settles after the timeout expires.
- **Fix:** Pass `{ timeout: 5000 }` to `waitFor` so the assertion succeeds after the retry completes. Documented inline with the rationale.
- **Files modified:** `frontend/src/lib/queries/use-vulnerabilities.test.tsx` (the test only).
- **Verification:** Test 5 passes; full suite 11/11 GREEN.
- **Committed in:** `292e4d9` (bundled with the GREEN feat commit since the test fix and implementation are one logical unit).

---

**Total deviations:** 1 significant (Plan 02 not run in worktree — author RED tests inline) + 2 auto-fixed.
**Impact on plan:** All 6 Plan 02 RED tests targeted by this plan are now GREEN. The success criteria stated by the plan ("Data layer for Phase 11 is complete: URL state (single + multi-value), TanStack queries (list + detail + facets + connectors + saved-filters), QueryCache error bridge, and ticket-create mutation are all GREEN") is fully met. No scope creep — every file shipped is in the plan's `<files_modified>` frontmatter.

## Issues Encountered

- TanStack v5 ESM exports do not support `vi.spyOn` for retry-config assertions. Workaround: inspect the live Query observer options on `qc.getQueryCache().findAll()[0]?.options` (mirrors Plan 10 `use-stats.test.tsx`). Used in the 401 propagation test instead.

## URL Contract for useUrlStateList

```
?severity=critical&severity=high&source=QUALYS&status=open
   └─ getAll('severity') → ['critical', 'high']
   └─ allow-list clamp → only critical/high/medium/low survive
   └─ toggle('critical') → URL becomes ?severity=high&source=QUALYS&status=open
   └─ setValue([]) → severity key removed entirely (clean URL)
   └─ router.replace(target, { scroll: false }) → no scroll jump on filter change
```

## Snapshot Fingerprint Algorithm (useQueryErrors)

```
fingerprint = errors
  .map(e => `${JSON.stringify(e.queryKey)}|${e.code}|${e.requestId}`)
  .join(',')
```

If the new fingerprint equals the cached one → return the cached array reference (no re-render).
If different → cache the new (fingerprint, value) tuple and return the new array.

This stabilizes against QueryCache events that don't change the watched-error set (e.g., refetching an already-errored query produces a new `state.error` Error instance but same `code`/`requestId`, so the fingerprint holds).

## Canonical Filter → URL → Query-Key Flow

```
Chip click          → toggle('critical')
                   ↓
useUrlStateList    → router.replace('/dashboard/vulnerabilities?severity=critical', { scroll: false })
                   ↓
useSearchParams    → re-renders consumers
                   ↓
useVulnerabilities → queryKey = ['vulnerabilities', 'list', {filters:{severity:['critical']}, group:'cve', page:1, sort:'', order:'asc'}]
                   ↓
buildSearchParams  → ?severity=critical&facets=severity,source,status&page=1
                   ↓
api(/api/v1/vulnerabilities?...) → backend returns { items, total, facets }
                   ↓
TanStack cache    → notifies subscribers; chip counts (from facets) and table data update atomically
```

## Next Plan Readiness

- **Plan 11-04 (state primitives):** `useQueryErrors` is ready for `PartialFailureBanner` default-mode consumption. `useConnectors` is ready for `PerSourceStatusStrip`. Both hook contracts (return shapes, types) are now exported.
- **Plan 11-05 (vuln-page components):** `useVulnerabilities` + `buildSearchParams` ready for `ChipBar` (search debounce wraps `buildSearchParams.set('search', ...)`), `VulnTable` (consumes `data.items`), `DrillPanel` (consumes `useVulnerabilityDetail`). `useCreateTicketMutation` ready for the drill-panel "Create ticket" CTA.
- **Plan 11-02 (Wave 0 scaffolding) still needs to run** for the 10 RED tests for state primitives + vuln-page components + the `vaul@1.1.2` install + the Tailwind `animate-shimmer` alias. The orchestrator should sequence Plan 11-02 before Plan 11-04 and Plan 11-05 dispatch.

## Self-Check: PASSED

Files claimed in this SUMMARY exist on disk:
- `frontend/src/hooks/use-url-state-list.ts` — FOUND
- `frontend/src/hooks/use-url-state-list.test.ts` — FOUND
- `frontend/src/lib/queries/use-connectors.ts` — FOUND
- `frontend/src/lib/queries/use-saved-filters.ts` — FOUND
- `frontend/src/lib/queries/use-query-errors.ts` — FOUND
- `frontend/src/lib/queries/use-query-errors.test.tsx` — FOUND
- `frontend/src/lib/queries/use-vulnerabilities.ts` — FOUND
- `frontend/src/lib/queries/use-vulnerabilities.test.tsx` — FOUND
- `frontend/src/lib/queries/use-vulnerability-detail.ts` — FOUND
- `frontend/src/lib/mutations/use-create-ticket.ts` — FOUND
- `frontend/src/lib/mutations/use-create-ticket.test.tsx` — FOUND

Commits claimed in this SUMMARY exist in git log:
- `559aeab` — FOUND
- `544d12e` — FOUND
- `1178b00` — FOUND
- `292e4d9` — FOUND
- `493c331` — FOUND
- `bd2eef8` — FOUND

## TDD Gate Compliance

Each task has a `test(...)` RED commit followed by a `feat(...)` GREEN commit:

| Task | RED commit | GREEN commit |
|------|------------|--------------|
| 11-03-01 | `559aeab` test(11-03): RED test for useUrlStateList | `544d12e` feat(11-03): useUrlStateList + extended query keys |
| 11-03-02 | `1178b00` test(11-03): RED tests for useQueryErrors + useVulnerabilities | `292e4d9` feat(11-03): useQueryErrors + useVulnerabilities + useVulnerabilityDetail GREEN |
| 11-03-03 | `493c331` test(11-03): RED test for useCreateTicketMutation | `bd2eef8` feat(11-03): useCreateTicketMutation with 401 surface |

TDD gate sequence verified. No REFACTOR commits — the GREEN implementations were minimal and clear; no follow-up clean-up was needed.

---
*Phase: 11-vulnerabilities-state-patterns*
*Completed: 2026-05-22*
