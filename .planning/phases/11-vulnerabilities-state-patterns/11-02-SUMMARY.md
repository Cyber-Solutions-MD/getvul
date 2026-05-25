---
phase: 11
plan: 02
subsystem: frontend-test-infrastructure
tags: [frontend, testing, tdd, wave-0, scaffolding]
requires: []
provides:
  - "14 RED test files (Wave 0 inventory)"
  - "vaul@1.1.2 pinned (exact, no caret) for D-P-03 mobile bottom-sheet"
  - "animate-shimmer Tailwind alias for D-S-01 SkeletonTable"
affects:
  - frontend/package.json
  - frontend/package-lock.json
  - frontend/tailwind.config.ts
  - frontend/src/hooks/use-url-state-list.test.ts
  - frontend/src/lib/queries/use-query-errors.test.tsx
  - frontend/src/lib/queries/use-vulnerabilities.test.tsx
  - frontend/src/lib/mutations/use-create-ticket.test.tsx
  - frontend/src/components/states/skeleton-table.test.tsx
  - frontend/src/components/states/empty-state.test.tsx
  - frontend/src/components/states/partial-failure-banner.test.tsx
  - frontend/src/components/states/per-source-status-strip.test.tsx
  - frontend/src/components/vulnerabilities/chip-bar.test.tsx
  - frontend/src/components/vulnerabilities/vuln-table.test.tsx
  - frontend/src/components/vulnerabilities/drill-panel.test.tsx
  - frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx
  - frontend/src/components/vulnerabilities/view-toggle.test.tsx
  - frontend/src/app/(authed)/dashboard/vulnerabilities/page.test.tsx
tech-stack:
  added:
    - "vaul@1.1.2 (exact pin via --save-exact + --legacy-peer-deps for React 19 + lucide-react peer)"
  patterns:
    - "TanStack QueryClient wrapper per-test (canonical from use-stats.test.tsx)"
    - "next/navigation mock with getAll for multi-value URL chips"
    - "vitest-axe toHaveNoViolations() on every state primitive"
    - "vi.mock for hooks that ship in Wave 1 (use-connectors, use-saved-filters, use-vulnerabilities, use-vulnerability-detail, use-query-errors)"
key-files:
  created:
    - frontend/src/hooks/use-url-state-list.test.ts
    - frontend/src/lib/queries/use-query-errors.test.tsx
    - frontend/src/lib/queries/use-vulnerabilities.test.tsx
    - frontend/src/lib/mutations/use-create-ticket.test.tsx
    - frontend/src/components/states/skeleton-table.test.tsx
    - frontend/src/components/states/empty-state.test.tsx
    - frontend/src/components/states/partial-failure-banner.test.tsx
    - frontend/src/components/states/per-source-status-strip.test.tsx
    - frontend/src/components/vulnerabilities/chip-bar.test.tsx
    - frontend/src/components/vulnerabilities/vuln-table.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx
    - frontend/src/components/vulnerabilities/view-toggle.test.tsx
    - frontend/src/app/(authed)/dashboard/vulnerabilities/page.test.tsx
  modified:
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/tailwind.config.ts
decisions:
  - "Used --legacy-peer-deps for vaul install because vaul@1.1.2 declares react@^18 peer while project pins react@19; mirrors existing lucide-react resolution path (already on ^18 peer in lockfile). Threat T-11-09 mitigation (exact pin, no caret) still enforced."
  - "Tailwind shimmer alias added rather than renaming existing animation — preserves Phase 10's animate-skeleton-shimmer consumers while letting RESEARCH §Code Examples land verbatim."
  - "Page-level test mocks 6 Wave 1 hooks via vi.mock — Wave 2 implementation has a clean dependency-injection target."
  - "Stale-row contract surface chosen: data-stale='true' attribute + amber-soft className conditional. Wave 2 implementation reads failedSources prop and applies."
metrics:
  duration: "~13 min"
  completed: "2026-05-22"
  tasks_completed: 4
  files_created: 14
  files_modified: 3
  red_tests_total: 109
---

# Phase 11 Plan 02: Wave 0 Test Scaffolding — Summary

Lay the 14-test-file RED scaffolding and infrastructure (vaul pinned, Tailwind shimmer aliased) that all of Wave 1 + Wave 2 will turn GREEN. Every downstream implementation task in 11-VALIDATION.md now has a concrete `<automated>` test command that already exists, satisfying the Nyquist sampling contract: the test describes the locked CONTEXT.md behavior as an executable spec before the implementation lands.

## What shipped

**Infrastructure (Task 11-02-01 — commit `5eef277`):**

- `vaul@1.1.2` installed with `--save-exact` (no caret) — mitigates T-11-09 supply-chain risk (vaul is unmaintained, pin prevents surprise upgrades). Installed via `--legacy-peer-deps` because vaul 1.1.2 declares react@^18 peer while the project ships React 19 (mirrors existing lucide-react resolution path).
- `animate-shimmer` Tailwind alias added — `frontend/tailwind.config.ts:94` now contains `'shimmer': 'skeleton-shimmer 1.6s linear infinite'`. Preserves Phase 10's existing `animate-skeleton-shimmer` consumers while letting Phase 11 components use `motion-safe:animate-shimmer` verbatim from RESEARCH §Code Examples.
- `vitest-axe/matchers` already wired in `vitest.setup.ts` — verified, no change.

**14 RED test files (Tasks 11-02-02..04 — commits `e06a06e`, `9cc4364`, `053e7e4`):**

### Wave 1 hook + query + mutation tests (Task 11-02-02 — commit `e06a06e`)

| File | Tests | Behavior signatures (Wave 1 GREEN target) |
|------|-------|-------------------------------------------|
| `frontend/src/hooks/use-url-state-list.test.ts` | 7 | D-F-05 multi-value URL chips + WR-04-style XSS clamp. `[value, setValue, toggle]` shape; XSS payloads filtered via allow-list; `setValue([])` removes key; toggle is idempotent in-out. |
| `frontend/src/lib/queries/use-query-errors.test.tsx` | 6 | D-S-03 QueryCache subscription bridge. Partial-key matching; success↔error transitions trigger re-render; SSR-safe (getServerSnapshot path); stable array reference across re-renders. |
| `frontend/src/lib/queries/use-vulnerabilities.test.tsx` | 5 | D-D-03 query-key shape `['vulnerabilities', 'list', { filters, group, page, sort, order }]`; `buildSearchParams` exported for testability; `?group=host` flows through; `?facets=severity,source,status` always appended; 401 surface via api.ts BL-06 safe-method refresh path. |
| `frontend/src/lib/mutations/use-create-ticket.test.tsx` | 5 | D-P-04 + BL-06 + T-11-06/07. `POST /api/v1/tickets` happy path; on 401 throws verbatim `Session expired during mutation. Please retry.` (no silent retry); 403 surface; on success invalidates `queryKeys.notifications.all`; signal pass-through. |

### Wave 1 state-primitive tests (Task 11-02-03 — commit `9cc4364`)

| File | Tests | Behavior signatures (Wave 1 GREEN target) |
|------|-------|-------------------------------------------|
| `frontend/src/components/states/skeleton-table.test.tsx` | 7 + axe | D-S-01 column-aware. `rows` (default 8) + `columns: SkeletonColumn[]`; `kind='pill'` → rounded-full; `motion-safe:animate-shimmer` className; `aria-busy="true"` + `aria-label` includes "Loading". |
| `frontend/src/components/states/empty-state.test.tsx` | 9 + axe | D-S-02 compound. Root `role="status"` + `aria-live="polite"`; `.Title` is h2/h3; `.Body` in `<p>`; `.Actions` flex layout; `.Suggestion` violet-soft + text-violet; optional slots; copy-voice guard (no `Welcome`/`Please`). |
| `frontend/src/components/states/partial-failure-banner.test.tsx` | 8 + axe | D-S-03 hybrid. Props mode: `role="alert"` + mono HTTP code + mono request ID + onRetry callback; default mode subscribes via `watchKeys` + QueryClient; amber-not-red guard; `data-failed-sources` attribute for D-V-04. |
| `frontend/src/components/states/per-source-status-strip.test.tsx` | 7 + axe | D-V-02 + D-S-07. One chip per connector; mono font + facets count; ok→success-soft, failed→danger-soft, syncing→pink-soft, null→surface-2; root `role="status"` + `aria-live="polite"`; null on pending/error. |

### Wave 2 vuln-page component tests (Task 11-02-04 — commit `053e7e4`)

| File | Tests | Behavior signatures (Wave 2 GREEN target) |
|------|-------|-------------------------------------------|
| `frontend/src/components/vulnerabilities/chip-bar.test.tsx` | 7 | UX-03-01 + D-F-01/02/03/05. Searchbox + severity/source chips + 250ms search debounce + synchronous chip-click + Clear-all wipes both + saved-filter pill conditional. |
| `frontend/src/components/vulnerabilities/vuln-table.test.tsx` | 13 | UX-03-02 + UX-07-03 + D-V-04. 7 column headers + severity glyph+pill + mono CVE + KEV badge + right-aligned mono SLA + ArrowDown/Up/Home/End/Enter/Space + click + `data-stale="true"` + sticky thead + 3-click sort cycle. |
| `frontend/src/components/vulnerabilities/drill-panel.test.tsx` | 10 | UX-03-03 + D-P-01/02/05/06. 7-section content order + × close + Esc close + clickaway close + row-swap (no close) + initial focus on close button + Tab cycling + Snooze/Create-ticket actions + 420px width + URL-encoded state. |
| `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` | 6 | UX-03-06 + D-P-03 vaul. <900px renders Drawer + ≥900px renders nothing + URL-driven open/close + Esc closes + nested ConfirmModal via Drawer.NestedRoot + shared DrillContent smoke. |
| `frontend/src/components/vulnerabilities/view-toggle.test.tsx` | 5 | UX-03-05 + D-V-01. 2-segment pill + active matches `?group` + click fires URL setter + other params survive + keyboard activates. |
| `frontend/src/app/(authed)/dashboard/vulnerabilities/page.test.tsx` | 8 | UX-03 page-level. Chip-bar + view-toggle + table on initial load + `?cve&open=drill` pre-opens + row click updates URL + isPending → SkeletonTable + empty-filtered → EmptyState with 3-tier CTAs + partial-failure (banner + per-source strip + stale tint) + total-failure → retry shell + `(N) Vulnerabilities · GetVul` document.title. |

### Wave 1 / Wave 2 GREEN consumption

Each test file imports the file Wave 1 or Wave 2 ships. The current import failure is the RED signal. When Wave 1 (Plan 11-03 hooks + Plan 11-04 primitives) and Wave 2 (Plan 11-05 components + Plan 11-06 page rewrite) ship their implementations, the import resolves and the assertions become the locked contract. No implementation may merge if it fails to satisfy these contracts.

Wave 1 GREEN targets (Plans 11-03 + 11-04):

```
src/hooks/use-url-state-list.ts          → satisfies use-url-state-list.test.ts (7 tests)
src/lib/queries/use-query-errors.ts      → satisfies use-query-errors.test.tsx (6 tests)
src/lib/queries/use-vulnerabilities.ts   → satisfies use-vulnerabilities.test.tsx (5 tests)
src/lib/mutations/use-create-ticket.ts   → satisfies use-create-ticket.test.tsx (5 tests)
src/components/states/skeleton-table.tsx → satisfies skeleton-table.test.tsx (7 + axe)
src/components/states/empty-state.tsx    → satisfies empty-state.test.tsx (9 + axe)
src/components/states/partial-failure-banner.tsx → satisfies partial-failure-banner.test.tsx (8 + axe)
src/components/states/per-source-status-strip.tsx → satisfies per-source-status-strip.test.tsx (7 + axe)
```

Wave 2 GREEN targets (Plans 11-05 + 11-06):

```
src/components/vulnerabilities/chip-bar.tsx        → satisfies chip-bar.test.tsx (7 tests)
src/components/vulnerabilities/vuln-table.tsx      → satisfies vuln-table.test.tsx (13 tests)
src/components/vulnerabilities/drill-panel.tsx     → satisfies drill-panel.test.tsx (10 tests)
src/components/vulnerabilities/drill-panel-mobile.tsx → satisfies drill-panel-mobile.test.tsx (6 tests)
src/components/vulnerabilities/view-toggle.tsx     → satisfies view-toggle.test.tsx (5 tests)
src/app/(authed)/dashboard/vulnerabilities/page.tsx (rewrite) → satisfies page.test.tsx (8 tests)
```

## Verification

```
$ grep -l '"vaul": "1.1.2"' frontend/package.json
frontend/package.json

$ find frontend/src -name "*.test.tsx" -o -name "*.test.ts" | matching the Wave 0 inventory
14 NEW test files

$ npx vitest run
Test Files  14 failed | 35 passed (49)
     Tests  187 passed (187)

# 14 failed = the 14 Wave 0 RED test files (Failed to resolve import — implementations don't exist yet)
# 35 passed = existing Phase 9 + 10 test files — NO regression
# 187 passed = individual tests in the 35 GREEN files — NO regression to prior phases
```

axe assertions: 4 (one per state primitive — `skeleton-table`, `empty-state`, `partial-failure-banner`, `per-source-status-strip`).

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 11-02-01 | `5eef277` | `chore(11-02): pin vaul@1.1.2 + alias animate-shimmer in tailwind config` |
| 11-02-02 | `e06a06e` | `test(11-02): RED frontend hook + query + mutation tests for Phase 11` |
| 11-02-03 | `9cc4364` | `test(11-02): RED state-primitive tests with axe coverage` |
| 11-02-04 | `053e7e4` | `test(11-02): RED component + page-level tests for /vulnerabilities` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] vaul@1.1.2 peer-dependency conflict with React 19**

- **Found during:** Task 11-02-01
- **Issue:** `npm install vaul@1.1.2 --save-exact` failed with `ERESOLVE` — vaul 1.1.2 declares `peerDependencies.react: ^16.5.1 || ^17.0.0 || ^18.0.0`, and the project ships React 19. Same conflict shape exists for the project's `lucide-react@0.383.0` (declares react@^18 peer), which is already in the lockfile.
- **Fix:** Used `npm install vaul@1.1.2 --save-exact --legacy-peer-deps`. This mirrors how the project's lockfile originally resolved lucide-react against React 19. T-11-09 mitigation (exact pin, no caret) is still enforced — vaul lands as `"vaul": "1.1.2"` in `package.json`.
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`
- **Commit:** `5eef277`

**No other deviations.** Plan executed exactly as written for tasks 02-04.

### Auth gates

None encountered.

## Decisions Made

1. **`--legacy-peer-deps` for vaul install** — matches existing project pattern (lucide-react resolution); preserves exact-pin contract from T-11-09.
2. **`shimmer` Tailwind alias rather than rename** — keeps Phase 10's `animate-skeleton-shimmer` consumers working untouched while letting RESEARCH §Code Examples land verbatim.
3. **Page-level test mocks 6 Wave 1 hooks** — gives Wave 2 implementation a clean dependency-injection target; mocks land in `vi.mock` calls that succeed even when the target module doesn't exist (which is exactly why these are RED).
4. **Stale-row contract surface** — `data-stale="true"` attribute + amber-soft className. Wave 2 implementation reads `failedSources` prop on `<VulnTable>` and applies. Banner exposes `data-failed-sources` attribute for D-V-04 propagation.
5. **404 not 401 handling for page-level error tests** — the page test's "total-failure" case asserts a Retry CTA; the exact copy is implementation-discretion per state-patterns.md.

## Self-Check: PASSED

- `vaul@1.1.2` exact pin in `frontend/package.json`: FOUND
- `'shimmer':` alias in `frontend/tailwind.config.ts`: FOUND
- `frontend/node_modules/vaul/package.json` (version 1.1.2): FOUND
- 14 RED test files: ALL FOUND (verified via `find`)
- Commit `5eef277` (Task 1 vaul + tailwind): FOUND
- Commit `e06a06e` (Task 2 hooks/queries/mutations): FOUND
- Commit `9cc4364` (Task 3 state primitives): FOUND
- Commit `053e7e4` (Task 4 vuln-page components + page): FOUND
- `npx vitest run` returned `14 failed | 35 passed` (49 files, 187 tests) — RED state confirmed, no regression to existing tests.

## Threat Flags

None — Wave 0 introduces no new network endpoints, auth paths, or schema changes. The only new surface is a third-party npm dependency (vaul 1.1.2) already in the plan's `<threat_model>` as T-11-09 with the `mitigate` disposition (exact pin enforced).
