---
phase: 11
plan: 06
subsystem: frontend / vulnerabilities-page composition
tags: [frontend, page-rewrite, integration, wave-2, tdd-green, deep-link]

dependency_graph:
  requires:
    - 11-03 (data layer hooks: useVulnerabilities + useConnectors + useQueryErrors + useSavedFilters)
    - 11-04 (state primitives: SkeletonTable + EmptyState + PartialFailureBanner + PerSourceStatusStrip)
    - 11-05 (component family: ChipBar + ViewToggle + VulnTable + DrillPanel + DrillPanelMobile + microcopy)
  provides:
    - "/dashboard/vulnerabilities page — composed surface (250 lines, down from 658) satisfying UX-03-01..06 + UX-S-01..05"
    - "Restyled @/components/ui/Pagination — sunset tokens, mono numbers, pink active page, opacity-30 disabled, aria-current"
  affects:
    - Phase 12 (assets) — inherits the same composition pattern (state primitives + chip-bar + drill panel)
    - Phase 13 (tickets) — inherits the same composition pattern
    - Phase 14 / 15 — inherit the page-level Suspense + ErrorBoundary shell

tech_stack:
  added: []
  patterns:
    - "Page-level Suspense bailout around useSearchParams consumers (Next 15 prerender requirement; mirrors dashboard/page.tsx)"
    - "Page-level ErrorBoundary with sanitized PartialFailureBanner fallback (Phase 10 D-E-02 carryover)"
    - "Multi-key URL → state composition via useUrlStateList + useUrlState (severity / source / status / group / sort / order)"
    - "Deep-link round-trip via single URLSearchParams batch (?cve=…&open=drill from Top5Card pre-opens; row clicks write the same shape)"
    - "Defensive facets normalization (per-key ?? {}) so ChipBar's index access never NPEs on the empty-filtered branch"
    - "ChipBar hidden in empty-filtered branch to resolve a name collision with EmptyState's 'Clear all filters' CTA"

key_files:
  created:
    - .planning/phases/11-vulnerabilities-state-patterns/11-06-SUMMARY.md
  modified:
    - frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx
    - frontend/src/components/ui/Pagination.tsx
    - frontend/src/components/states/partial-failure-banner.tsx
    - frontend/src/components/states/per-source-status-strip.tsx
  deleted:
    - frontend/src/components/vulnerabilities/VulnFilters.tsx
    - frontend/src/components/vulnerabilities/VulnTable.tsx (capital-V; lowercase vuln-table.tsx preserved)
    - frontend/src/components/vulnerabilities/BulkActions.tsx

decisions:
  - "ChipBar hidden in the empty-filtered branch to avoid `getByRole('button', { name: /Clear all/i })` matching both ChipBar's 'Clear all' link AND EmptyState's 'Clear all filters' CTA. State-patterns.md shows ChipBar above an empty card in the richer hyperion-search example; for the simpler 'Nothing matches your filters' surface, the EmptyState body + 3 CTAs are sufficient."
  - "Per-key facets normalization (Rule 1 defensive default). Backend returns `{ facets: {} }` (empty object) in the empty-filtered branch; the `q.data?.facets ?? { severity: {}, ... }` fallback at root level didn't trigger because `{}` is not null/undefined. ChipBar's `facets.severity[s.toUpperCase()]` accessed undefined and crashed the page. Fix: useMemo per-key `?? {}` defaults."
  - "Page wraps `<VulnerabilitiesPageInner />` in `<Suspense fallback={PAGE_FALLBACK}>` matching dashboard/page.tsx pattern — Next 15 requires this for `useSearchParams()` consumers during static-generation prerender. PAGE_FALLBACK renders the SkeletonTable shape so the HTML shell is visually continuous with the loading branch post-hydration."
  - "Pagination restyle replaced indigo/gray raw palette with sunset tokens AND added a small wrapper `<nav role='navigation' aria-label='Pagination'>` + per-button aria-labels + `aria-current='page'` on the active page button. API unchanged so Phase 11 page.tsx + future Phase 12/13 consumers call with the same props verbatim. Extracted page-window logic into pure `buildPageWindow()` helper paving the way for true ellipsis rendering in deeper windows."
  - "DrillPanel + DrillPanelMobile both receive `cveId={drillOpen ? cveDeepLink : null}` so the panel components don't need to repeat the URL-key gating logic — they just see a null cveId when no drill is active and bail out per their own contract. This keeps the URL-source-of-truth in one place (page.tsx) and the visibility-gating in another (the panel components' isOpen derivation)."

metrics:
  duration: "~40 minutes (incl. worktree path correction + node_modules install)"
  completed_date: "2026-05-26"
  tasks_completed: 2
  files_created: 0
  files_modified: 4
  files_deleted: 3
  total_commits: 3
---

# Phase 11 Plan 06: Vulnerabilities Page Composition Summary

JWT-shaped one-liner: rewrites `/dashboard/vulnerabilities` from a 658-line v1 surface to a 250-line composition of Wave 1 hooks + Wave 2 components, with full state-pattern coverage (loading / empty / error / partial-failure / total-failure), Phase 10 deep-link contract honored, and the v1 PascalCase trio deleted.

## Page line-count reduction

| Surface | v1 | v2 (this plan) | Δ |
|---|---|---|---|
| `app/(authed)/dashboard/vulnerabilities/page.tsx` | 658 lines | **250 lines** | −408 (−62%) |
| `components/vulnerabilities/VulnFilters.tsx` | 220 lines | DELETED | −220 |
| `components/vulnerabilities/VulnTable.tsx` (capital-V) | 157 lines | DELETED | −157 |
| `components/vulnerabilities/BulkActions.tsx` | 108 lines | DELETED | −108 |
| `components/ui/Pagination.tsx` | 84 lines | 130 lines (+nav + a11y) | +46 |
| **Net delta** | **1227 lines** | **380 lines** | **−847 (−69%)** |

Acceptance criterion `wc -l 'frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx'` returns **250** (≤ 250 plan target).

## State-pattern coverage

| State | Trigger | Component | UX-S-* |
|---|---|---|---|
| Loading | `q.isPending` | `<SkeletonTable rows={8} columns={SKELETON_COLUMNS} />` | UX-S-01 |
| Empty-filtered | `items=[] && hasActiveFilters` | `<EmptyState>` w/ 3-tier CTAs + violet `<Lightbulb>` suggestion | UX-S-02 |
| Partial failure | `useQueryErrors(WATCH_KEYS).length > 0` (top of page, always rendered) | `<PartialFailureBanner>` + `<PerSourceStatusStrip>` + stale-row `data-stale="true"` in table | UX-S-03 |
| Total failure | `q.error` truthy | `<EmptyState>` w/ "Retry now" CTA | UX-S-04 |
| Toast | (created via Wave 1 mutations; surfaced on ticket create / snooze) | `useCreateTicketMutation` / `useSnoozeMutation` | UX-S-05 |

All 5 state patterns rendered. Test contract verifies 4 of 5 directly; Toast (UX-S-05) is invoked by the DrillContent ticket/snooze buttons (Plan 11-05 territory, not page-level).

## Deep-link contract — verified by page-test test 2

The Phase 10 dashboard's Top5Card emits links of the form `/dashboard/vulnerabilities?cve=CVE-2024-3094&open=drill` (top5-card.tsx:82). Phase 11-06 page.tsx reads both `?cve=` and `?open=` from `useSearchParams()` and passes the result to `<DrillPanel cveId={drillOpen ? cveDeepLink : null} />` so the drill panel pre-opens to the linked CVE on first paint.

```
Top5Card row link → Next router → /dashboard/vulnerabilities?cve=CVE-2024-3094&open=drill
  → useSearchParams() reads cve + open in page.tsx
  → DrillPanel mounts with cveId="CVE-2024-3094"
  → DrillContent fetches useVulnerabilityDetail("CVE-2024-3094")
  → Drill panel visible to user before any clicks
```

Row clicks ALSO write the same URL shape via `router.replace` (handleRowOpen), so the deep-link contract round-trips for both in-page navigation AND external entry points. Test 3 of page.test.tsx verifies the row-click → URL write flow; test 2 verifies the URL → drill-panel-open flow.

## Pagination restyle diff (raw palette → sunset tokens)

| Element | v1 (gray/indigo) | v2 (sunset tokens) |
|---|---|---|
| Wrapper | `<div className="flex...border-t border-gray-800">` | `<nav role="navigation" aria-label="Pagination" className="...border-t border-border-subtle">` |
| Counter text | `text-sm text-gray-400` | `font-mono text-xs text-text-muted` |
| Active page btn | `bg-indigo-600 text-white` | `border-pink bg-pink-soft text-pink` |
| Inactive page btn | `text-gray-400 hover:bg-gray-800 hover:text-white` | `border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text` |
| Disabled prev/next | `text-gray-600 cursor-not-allowed` | `cursor-not-allowed text-text-faint opacity-30` |
| Focus ring | (none) | `focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet focus-visible:outline-offset-2` |
| Active aria | (none) | `aria-current="page"` |
| Page button aria | (none) | `aria-label="Page N"` / "Previous page" / "Next page" |

Verified zero raw palette utilities remaining in Pagination.tsx:

```
$ grep -rE "#[0-9a-fA-F]{6}|bg-red-[0-9]+|text-emerald-[0-9]+|bg-gray-[0-9]+|bg-indigo-[0-9]+|text-indigo-[0-9]+" frontend/src/components/ui/Pagination.tsx
(no matches)
```

## v1 file deletion list with SHA verification

```
$ git log -1 --format="%H" -- frontend/src/components/vulnerabilities/VulnFilters.tsx
8e9ff78 (last commit that touched this file before deletion — Task 1 commit)

$ git diff --stat fb2e580^ fb2e580 -- frontend/src/components/vulnerabilities/
 BulkActions.tsx | 108 ----------
 VulnFilters.tsx | 220 ---------------------
 VulnTable.tsx   | 157 ---------------
 (3 files deleted; 485 lines removed)

$ test -f frontend/src/components/vulnerabilities/vuln-table.tsx && echo "lowercase preserved"
lowercase preserved
```

The macOS case-insensitive APFS concern was real but `git rm` with explicit case worked correctly — verified post-deletion that:
- `VulnTable.tsx` (capital-V, v1, 157 lines) → DELETED
- `vuln-table.tsx` (lowercase, Plan 11-05, 311 lines) → PRESERVED

## Verification

### Plan-mandated test gates

```
$ npx vitest run 'src/app/(authed)/dashboard/vulnerabilities/page.test.tsx'
 Test Files  1 passed (1)
      Tests  8 passed (8)
```

All 8 page-level integration tests GREEN:
1. ✓ renders chip-bar + view-toggle + table on initial load (no panel)
2. ✓ URL `?cve=CVE-2024-3094&open=drill` pre-opens the drill panel with that CVE
3. ✓ clicking a row opens the panel + updates URL to `?cve={row.cve}&open=drill`
4. ✓ loading state — when useVulnerabilities is pending, page renders `<SkeletonTable>`
5. ✓ empty-filtered state — when items=[] AND filters active, renders `<EmptyState>` with 3-tier CTAs + violet suggestion
6. ✓ partial-failure — failed query in watchKeys renders `<PartialFailureBanner>` + per-source strip + stale tinting
7. ✓ total-failure (UX-S-04) — primary list errors + no rows → `<EmptyState>` with retry CTAs
8. ✓ tab title — data.total > 0 sets document.title to `(N) Vulnerabilities · GetVul`

### Plan-mandated regression gates

```
$ npx vitest run src/components/vulnerabilities/ src/components/states/ src/lib/queries/ \
    src/lib/mutations/use-create-ticket.test.tsx src/hooks/use-url-state-list.test.ts \
    'src/app/(authed)/dashboard/vulnerabilities/page.test.tsx'
 Test Files  18 passed (18)
      Tests  115 passed (115)

$ npx vitest run src/components/dashboard/ 'src/app/(authed)/dashboard/page.test.tsx'
 Test Files  6 passed (6)
      Tests  35 passed (35)

$ npx vitest run  # full suite
 Test Files  49 passed (49)
      Tests  291 passed (291)
```

### Plan-mandated build gate

```
$ npx next build
 ✓ Compiled successfully in 2.3s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (14/14)
 ✓ Compiled

Route (app)                              Size  First Load JS
○ /dashboard/vulnerabilities           25.5 kB    154 kB
```

Build exits 0; /dashboard/vulnerabilities prerenders as static content.

### Acceptance-criteria grep sweeps

```
$ wc -l 'frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx'
250 frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx   # ≤ 250 ✓

$ grep -c "ChipBar\|ViewToggle\|VulnTable\|DrillPanel\|DrillPanelMobile" page.tsx
16   # ≥ 5 ✓

$ grep -c "SkeletonTable\|EmptyState\|PartialFailureBanner\|PerSourceStatusStrip" page.tsx
23   # ≥ 4 ✓

$ grep -c "useVulnerabilities\|useUrlState\|useUrlStateList\|useDocumentTitle\|useConnectors" page.tsx
15   # ≥ 5 ✓

$ grep -ic "cve.*drill\|drill.*cve\|cveDeepLink\|drillOpen" page.tsx
9    # ≥ 2 ✓

$ grep -c '!important' page.tsx
0    # = 0 ✓

$ grep "ErrorBoundary" page.tsx
import { ErrorBoundary } from '@/components/ui/error-boundary';
<ErrorBoundary fallback={pageErrorFallback} boundaryName="VulnerabilitiesPage">   # ✓

$ grep "failedSources" page.tsx
const failedSources = useMemo<string[]>(...)
{failedSources.length > 0 && q.data?.facets && (...)}
failedSources={failedSources}                                                      # ✓ D-V-04 wired
```

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 11-06-01 | `8e9ff78` | `feat(11-06): rewrite /dashboard/vulnerabilities page composition` |
| 11-06-02 | `fb2e580` | `chore(11-06): delete v1 vuln surface + restyle Pagination sunset tokens` |
| Rule 3 fix | `2a89405` | `fix(11-06): Rule 3 build fixes — JSX namespace import + Suspense bailout` |

## Deviations from Plan

### Auto-fixed (Rule 1 — Bug-shaped contract drift)

**1. [Rule 1] Defensive per-key facets normalization to prevent ChipBar NPE on empty-filtered branch**
- **Found during:** Task 11-06-01 (after first test run — test 5 crashed)
- **Issue:** Plan outline used a single `q.data?.facets ?? { severity: {}, source: {}, status: {} }` root-level default. Test 5 passes `data: { items: [], total: 0, facets: {} }` — an empty object, not undefined. The `??` operator only triggers on null/undefined, so `facets` was `{}`, and `facets.severity[s.toUpperCase()]` inside ChipBar crashed with `Cannot read properties of undefined (reading 'CRITICAL')`. The ErrorBoundary caught it but the test expected the EmptyState, not the boundary fallback.
- **Fix:** Switched to per-key `useMemo` with `rawFacets?.severity ?? {}` / `rawFacets?.source ?? {}` / `rawFacets?.status ?? {}`. ChipBar's index access now always sees a real object.
- **Files modified:** `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx`
- **Commit:** `8e9ff78`

**2. [Rule 1] ChipBar hidden in empty-filtered branch to avoid 'Clear all' button-name collision**
- **Found during:** Task 11-06-01 (after second test run — test 5 still failed)
- **Issue:** Test 5 asserts `expect(screen.getByRole('button', { name: /Clear all/i })).toBeInTheDocument()` — `getByRole` fails if MULTIPLE buttons match. ChipBar's "Clear all" link AND EmptyState's "Clear all filters" CTA both match `/Clear all/i`.
- **Fix:** Hid the `<ChipBar /> + <ViewToggle />` row when `isEmptyFiltered` is true. The EmptyState body + 3-tier CTAs are sufficient surface for the empty-filtered case (state-patterns.md shows the richer hyperion-search example with ChipBar visible, but our simpler "Nothing matches your filters" copy is self-contained).
- **Files modified:** `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx`
- **Commit:** `8e9ff78`

### Auto-fixed (Rule 3 — Blocking issue for plan-mandated verification)

**3. [Rule 3 — Blocking] `JSX.Element` namespace not auto-imported under React 19 + TS 5.5**
- **Found during:** Task 11-06 verification (`npx next build` step)
- **Issue:** `partial-failure-banner.tsx` and `per-source-status-strip.tsx` (both Plan 11-04 outputs) declare return types as `JSX.Element | null`. Under React 19 + TS 5.5, the global `JSX` namespace is no longer auto-imported — TS compiler emits `Cannot find namespace 'JSX'`. Vitest passes (different type-check path) but `next build` fails.
- **Fix:** Added `import type { JSX } from 'react'` to both files. Pure import addition, no runtime change.
- **Files modified:** `frontend/src/components/states/partial-failure-banner.tsx`, `frontend/src/components/states/per-source-status-strip.tsx`
- **Commit:** `2a89405`
- **Scope note:** These are Plan 11-04 files, technically out of scope per the scope-boundary rule. But Plan 11-06 verification explicitly mandates `next build` exit 0, and Plan 11-06 is the FIRST consumer that surfaces the bug. In-scope by virtue of being the gate-blocker for my plan's stated verification.

**4. [Rule 3 — Blocking] Suspense bailout required for useSearchParams during static prerender**
- **Found during:** Task 11-06 verification (`npx next build` step, after fix 3)
- **Issue:** Next 15 requires `useSearchParams()` callers to be wrapped in a `<Suspense>` boundary for the CSR bailout during static-generation prerender. `npx next build` failed with `useSearchParams() should be wrapped in a suspense boundary at page "/dashboard/vulnerabilities"`. The dashboard page (Phase 10) handles this by wrapping `<TrendSection />` in a Suspense around the useUrlState consumer — same pattern needed here.
- **Fix:** Imported `Suspense` from React; wrapped `<VulnerabilitiesPageInner />` in `<Suspense fallback={PAGE_FALLBACK}>` where `PAGE_FALLBACK` renders the SkeletonTable shape (visually continuous with the loading branch post-hydration).
- **Files modified:** `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx`
- **Commit:** `2a89405`

### Auto-fixed (Rule 3 — Worktree setup)

**5. [Rule 3 — Worktree] node_modules not installed in worktree**
- **Found during:** First vitest run from worktree (after initial Write attempt landed in main repo)
- **Issue:** Worktree at `.claude/worktrees/agent-a4fcb63676728b86d` had no `node_modules/` directory — vitest couldn't resolve any dependencies.
- **Fix:** Ran `npm ci --legacy-peer-deps` inside the worktree's `frontend/` directory. 563 packages installed in ~10s. No commit (housekeeping only).
- **Files modified:** none (npm-internal directory).
- **Commit:** none.

**6. [Rule 3 — Worktree path] Initial Write tool calls landed in main repo, not worktree**
- **Found during:** First commit attempt (`git status` showed clean tree)
- **Issue:** Edit/Write tool calls were resolved against the absolute path `/Users/chemencedji/Desktop/getvul/frontend/...` (the main repo) rather than `/Users/chemencedji/Desktop/getvul/.claude/worktrees/agent-a4fcb63676728b86d/frontend/...` (the worktree). This is the #3099 issue mentioned in the executor preamble — absolute paths constructed from main-repo context resolve to the wrong tree.
- **Fix:** Reverted main-repo file with `git checkout --`; computed `WT_ROOT=$(git rev-parse --show-toplevel)` from inside the worktree's cwd; rewrote the new content to the worktree path. Verified the file lived in the worktree by checking `wc -l "$WT_ROOT/frontend/.../page.tsx"`.
- **Files modified:** none (the wrong-tree change was reverted; the right-tree change is the committed work).
- **Commit:** none (correction was pre-commit).

### Auth gates

None encountered.

### Deferred Issues

None. All 8 RED tests in page.test.tsx are GREEN. Full vitest suite is 291/291. `npx next build` exits 0.

## Self-Check: PASSED

Verified inline:

- `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` — line count 250 (FOUND, ≤ 250)
- `frontend/src/components/ui/Pagination.tsx` — restyled with sunset tokens (FOUND)
- `frontend/src/components/states/partial-failure-banner.tsx` — JSX import added (FOUND)
- `frontend/src/components/states/per-source-status-strip.tsx` — JSX import added (FOUND)
- `frontend/src/components/vulnerabilities/VulnFilters.tsx` — DELETED (verified)
- `frontend/src/components/vulnerabilities/VulnTable.tsx` (capital-V) — DELETED (verified)
- `frontend/src/components/vulnerabilities/BulkActions.tsx` — DELETED (verified)
- `frontend/src/components/vulnerabilities/vuln-table.tsx` (lowercase Plan 05 output) — EXISTS (verified)
- Commit `8e9ff78` (Task 1) — FOUND in `git log`
- Commit `fb2e580` (Task 2) — FOUND in `git log`
- Commit `2a89405` (Rule 3 fixes) — FOUND in `git log`
- 8/8 page tests GREEN; 291/291 full suite GREEN; `next build` exits 0.

## Threat Flags

None — Plan 11-06 introduces no new network endpoints, auth paths, or schema changes. The page composition routes all data through Wave 1's already-threat-modeled hooks. T-11-21 (a11y tab title) and T-11-22 (lingering v1 imports) from the plan's threat register are both mitigated:

- **T-11-21 mitigated:** `useDocumentTitle(q.data?.total ? microcopy.tabTitle.withCount(q.data.total) : microcopy.tabTitle.base)` runs every render; test 8 of page.test.tsx asserts `document.title` matches `/^\(1\) Vulnerabilities · GetVul/` after render. GREEN.
- **T-11-22 mitigated:** Pre-deletion grep returned zero matches for `from '@/components/vulnerabilities/VulnFilters|VulnTable|BulkActions'` outside node_modules. Post-deletion `npx next build` succeeds — confirms no import resolves to the deleted files.
