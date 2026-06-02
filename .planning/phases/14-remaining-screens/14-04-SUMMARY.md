---
phase: 14-remaining-screens
plan: 04
subsystem: frontend/users
tags: [users-directory, source-pill, tanstack-query, chip-bar, bulk-bar, segmented-toggle, sunset-tokens, tdd]
dependency_graph:
  requires:
    - "14-00: queryKeys.directoryUsers + queryKeys.settings.groups + ExportButton (sunset-restyled)"
  provides:
    - "frontend/src/lib/queries/use-directory-users.ts: useDirectoryUsers + useDirectoryStats + buildDirectorySearchParams + DirectoryUser type"
    - "frontend/src/lib/queries/use-tenant-groups.ts: useTenantGroups + TenantGroup type"
    - "frontend/src/components/users/source-pill.tsx: SourcePill (idp_source→sunset tokens)"
    - "frontend/src/components/users/directory-table.tsx: DirectoryTable (Avatar + SourcePill + title/dept chip, selection)"
    - "frontend/src/components/users/users-export-bar.tsx: UsersExportBar (export-only bulk bar)"
    - "frontend/src/components/users/microcopy.ts: copy strings for users directory"
    - "frontend/src/app/(authed)/dashboard/users/page.tsx: directory + groups page (segmented toggle)"
  affects:
    - "/dashboard/users route: v1 surface fully replaced (horizontal tabs, raw palette, inline fetch deleted)"
tech_stack:
  added: []
  patterns:
    - "Literal Record<string, string> lookup for SOURCE_CLASSES in SourcePill (injection guard, T-14-13)"
    - "buildDirectorySearchParams co-located helper for URL-shape tests (Phase 11/12 D-D-03 pattern)"
    - "useUrlState for segmented toggle (View), useUrlStateList for multi-value chip axes"
    - "vi.importActual() in page.test.tsx for isolated sub-component testing alongside module-level vi.mock"
key_files:
  created:
    - frontend/src/lib/queries/use-directory-users.ts
    - frontend/src/lib/queries/use-directory-users.test.ts
    - frontend/src/lib/queries/use-tenant-groups.ts
    - frontend/src/components/users/source-pill.tsx
    - frontend/src/components/users/source-pill.test.tsx
    - frontend/src/components/users/directory-table.tsx
    - frontend/src/components/users/directory-table.test.tsx
    - frontend/src/components/users/users-export-bar.tsx
    - frontend/src/components/users/microcopy.ts
    - frontend/src/app/(authed)/dashboard/users/page.test.tsx
  modified:
    - frontend/src/app/(authed)/dashboard/users/page.tsx
decisions:
  - "SourcePill uses literal Record lookup (SOURCE_CLASSES) not string interpolation — injection guard mirrors ConnectorMark T-14-01 pattern"
  - "humaans idp_source maps to text-info (--color-info = #60A5FA) as the cyan analog — no cyan-* Tailwind utility used"
  - "Segmented toggle (Directory/Groups) mirrors vuln ViewToggle shape: rounded-full border, bg-surface-2 active, no border-b-2 tabs"
  - "buildDirectorySearchParams exported separately so URL-shape tests run without TanStack (D-D-03 pattern)"
  - "ChipBar department axis: derivedFromCounts=true with dynamic allowList from stats.departments (names); source axis similarly dynamic from stats.by_source"
  - "vi.importActual() used in page.test.tsx to test real UsersExportBar alongside module-level mock for page integration tests"
  - "RBAC role field present in DirectoryUser type (fetched from API) but never rendered — Pitfall 7 enforced; grep -cE 'u\\.role|user\\.role|\\.role' returns 0"
metrics:
  duration: "~45 minutes"
  completed: "2026-06-02"
  tasks_completed: 2
  files_modified: 11
---

# Phase 14 Plan 04: Users Directory Summary

Full rewrite of `/dashboard/users` against the sunset design system (UX-06-03). Directory with idp_source enrichment-source pill + job-title/department chips (never RBAC role), Directory/Groups segmented toggle (no horizontal tabs), export-only bulk bar via ExportButton, and all three state patterns; 37 tests green.

## What Was Built

### Task 1: Directory/groups hooks + SourcePill + DirectoryTable

**`use-directory-users.ts`** — Two TanStack hooks:
- `useDirectoryUsers(opts)` — GETs `/api/v1/users/directory` with search/status/department/source/sort_by/sort_dir params. staleTime 60s. Uses `queryKeys.directoryUsers.list(opts)`.
- `useDirectoryStats()` — GETs `/api/v1/users/stats`. Uses `queryKeys.directoryUsers.stats()`.
- `buildDirectorySearchParams()` — co-located URL helper exported for wire-contract tests without TanStack (Phase 11 D-D-03 pattern).
- `DirectoryUser` type mirrors the backend response shape (snake_case per D-X-02). The `role` field is typed but deliberately not rendered.

**`use-tenant-groups.ts`** — `useTenantGroups()` hook: GETs `/api/v1/tenant/groups`, uses `queryKeys.settings.groups()`.

**`source-pill.tsx`** — `SourcePill` component:
- Props: `{ source: string; className? }`.
- Literal `SOURCE_CLASSES: Record<string, string>` maps idp_source values to sunset token class strings: `google/azure/humaans → text-info/border-info/40/bg-info/10`, `okta → text-violet/border-violet/40/bg-violet-soft`, `local → text-text-faint/border-border-subtle/bg-surface-2`. Fallback to local tokens for unknown sources.
- `data-source-pill={source}` test hook, `font-mono` per visual-language.md pill spec.
- Zero raw palette utilities (0 matches for gray-N/indigo-N/cyan-N).

**`directory-table.tsx`** — `DirectoryTable` component:
- Props: `{ users: DirectoryUser[]; selectedIds: string[]; onSelect: (id: string) => void; onSelectAll?: () => void }`.
- Columns: checkbox · person (Avatar 28px + display_name + email mono) · Source (SourcePill) · Title/Dept (job_title chip + department chip) · Devices (count, mono) · Risk (score badge with severity tokens).
- Pitfall 7 enforced: `u.role` (RBAC) never appears in JSX. `grep -cE 'u\.role|user\.role|\.role'` = 0.
- Attributes: `data-directory-table`, `data-user-row={id}`.
- Row selection: checkbox with `aria-label="Select {displayName}"` calls `onSelect(id)`.

**`microcopy.ts`** — Copy strings per copy-voice.md: sentence case, no exclamation marks, explains WHY in empty state, verb-phrase export labels.

### Task 2: UsersExportBar + users page rewrite

**`users-export-bar.tsx`** — `UsersExportBar` component:
- Returns `null` when `selectedIds.length === 0`.
- `fixed inset-x-0 bottom-0 z-30 animate-in slide-in-from-bottom-2` bar.
- Shows `{n} person/people selected` count + `ExportButton resource="users" label="Export selected" filters={{ ids: selectedIds }}`.
- No write actions (D-USR-02): export is the only action.
- `data-users-export-bar` test hook.

**`page.tsx`** — Full rewrite of `/dashboard/users`:
- v1 surface deleted: horizontal tabs (`border-b-2 border-indigo-500`), raw palette (`gray-*`, `indigo-*`), inline `useEffect` fetching — all gone. Zero matches for these patterns.
- D-USR-03: Directory/Groups segmented toggle via `useUrlState('view', VIEWS, 'directory')` — `rounded-full border border-border-subtle bg-surface p-0.5` chrome, no `border-b-2`.
- Directory view: `ChipBar` with 3 axes (status/department/source), each with T-14-13 allowLists. `DirectoryTable` with row selection → `UsersExportBar`.
- Groups view: `useTenantGroups` list rendering group name + member_count badge + `ExportButton resource="groups"`.
- D-X-01 state patterns: `SkeletonTable` (isPending), `EmptyState` (empty items), `PartialFailureBanner` (query error) — all present.
- D-X-02: snake_case throughout.
- `Suspense` wrapper preserved (required for `useSearchParams()` in Next.js 15).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] vi.importActual() for export bar test isolation**
- **Found during:** Task 2 test GREEN phase
- **Issue:** `vi.mock` is hoisted to module scope, which replaced the real `UsersExportBar` even when directly imported for isolation tests in the same test file. Standard pattern of importing the real module alongside a module-level mock fails.
- **Fix:** Used `vi.importActual()` inside specific describe blocks to access the real UsersExportBar implementation for Test 1 isolation, while the page-level tests use the mock version. This is a Vitest-idiomatic pattern for this conflict.
- **Files modified:** `page.test.tsx`
- **Commit:** `c5f0b55`

## Known Stubs

None — all components are fully wired:
- `useDirectoryUsers` and `useDirectoryStats` fetch real backend endpoints.
- `useTenantGroups` fetches real `/api/v1/tenant/groups`.
- `SourcePill` maps all documented idp_source values to sunset tokens.
- `DirectoryTable` renders all column data (no placeholder cells).
- `UsersExportBar` passes actual `selectedIds` to `ExportButton`.
- Page renders real data from hooks; no hardcoded mock data in production code.

## Threat Flags

No new threat surface beyond what was documented in the plan's threat model:
- T-14-13 (URL filter injection): mitigated by ChipBar axis allowLists. Every `ChipAxis` carries a hardcoded `allowList`; `useUrlStateList` clamps reflected values on both read and write.
- T-14-14 (directory export): accepted at backend (tenant-scoped); ExportButton auth logic unchanged per RESEARCH anti-pattern.
- T-14-15 (RBAC role in directory): mitigated. `u.role` never rendered in `directory-table.tsx` (grep returns 0).

## Self-Check

### Created files exist:
- FOUND: `frontend/src/lib/queries/use-directory-users.ts`
- FOUND: `frontend/src/lib/queries/use-directory-users.test.ts`
- FOUND: `frontend/src/lib/queries/use-tenant-groups.ts`
- FOUND: `frontend/src/components/users/source-pill.tsx`
- FOUND: `frontend/src/components/users/source-pill.test.tsx`
- FOUND: `frontend/src/components/users/directory-table.tsx`
- FOUND: `frontend/src/components/users/directory-table.test.tsx`
- FOUND: `frontend/src/components/users/users-export-bar.tsx`
- FOUND: `frontend/src/components/users/microcopy.ts`
- FOUND: `frontend/src/app/(authed)/dashboard/users/page.test.tsx`

### Commits exist:
- `11a7245`: feat(14-04): Task 1 — directory/groups hooks + SourcePill + DirectoryTable
- `c5f0b55`: feat(14-04): Task 2 — UsersExportBar + users page rewrite (segmented toggle + chip-bar + states)

## Self-Check: PASSED
