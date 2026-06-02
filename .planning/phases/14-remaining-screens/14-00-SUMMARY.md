---
phase: 14-remaining-screens
plan: 00
subsystem: frontend/connectors
tags: [tokens, primitives, connector-mark, sync-status-pill, query-keys, sunset-restyle]
dependency_graph:
  requires: []
  provides:
    - "frontend/src/app/globals.css: 12 new --gradient-provider-* tokens"
    - "frontend/src/components/connectors/types.ts: ConnectorProvider union type"
    - "frontend/src/components/connectors/connector-mark.tsx: ConnectorMark component"
    - "frontend/src/components/connectors/sync-status-pill.tsx: SyncStatusPill component"
    - "frontend/src/components/ui/ConfirmModal.tsx: sunset-tokenized modal"
    - "frontend/src/components/ui/ExportButton.tsx: sunset-tokenized export button"
    - "frontend/src/lib/queries/keys.ts: cspm/settings/directoryUsers query-key namespaces"
  affects:
    - "Phase 14 Plans 01-05: all consume ConnectorMark, SyncStatusPill, queryKeys.cspm/settings/directoryUsers"
    - "All screens using ConfirmModal or ExportButton: now render in sunset tokens"
tech_stack:
  added: []
  patterns:
    - "Literal Record<ConnectorProvider, string> lookup for CSS var injection guard (T-14-01)"
    - "4-state pill with D-P-04 token triad (border/bg/text per status)"
    - "motion-safe:animate-pulse on leading dot for syncing state"
key_files:
  created:
    - frontend/src/components/connectors/types.ts
    - frontend/src/components/connectors/connector-mark.tsx
    - frontend/src/components/connectors/connector-mark.test.tsx
    - frontend/src/components/connectors/sync-status-pill.tsx
    - frontend/src/components/connectors/sync-status-pill.test.tsx
  modified:
    - frontend/src/app/globals.css
    - frontend/src/components/ui/ConfirmModal.tsx
    - frontend/src/components/ui/ExportButton.tsx
    - frontend/src/lib/queries/keys.ts
    - frontend/src/lib/queries/keys.test.ts
decisions:
  - "ConnectorMark uses literal Record lookup (not string interpolation) per T-14-01/T-13-14"
  - "keys.ts extended with full Phase 11-13 namespace baseline + 3 new Phase 14 namespaces (cspm/settings/directoryUsers)"
  - "ConfirmModal variant info → bg-violet (not bg-info) since --color-blue does not exist in sunset.css"
  - "SyncStatusPill maps backend 'syncing' (not 'running') directly in status prop type"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-02"
  tasks_completed: 3
  files_modified: 10
---

# Phase 14 Plan 00: Connector-Domain Foundation Summary

Wave 0 foundation plan delivering shared tokens, primitives, and cache-key namespaces that all four Phase 14 screen plans consume.

## One-liner

12 provider gradient CSS tokens + 14-provider ConnectorMark (literal-lookup injection guard) + 4-state SyncStatusPill (sunset D-P-04 tokens) + ConfirmModal/ExportButton sunset restyle + queryKeys extended with cspm/settings/directoryUsers namespaces; 33 tests green.

## What Was Built

### Task 1: Provider Gradient Tokens + ConnectorMark

12 new `--gradient-provider-*` CSS custom properties added to the `:root` block in `globals.css` (directly after the Phase 13 jira/asana/github tokens). All at 135deg to match Phase 13 convention.

`ConnectorProvider` union type created in `components/connectors/types.ts` covering all 14 providers (6 vulnerability scanners + 3 identity providers + 3 enrichment/MDM + 3 ticketing).

`ConnectorMark` component created at `components/connectors/connector-mark.tsx` mirroring the Phase 13 `ProviderMark` pattern exactly:
- `PROVIDER_GRADIENTS: Record<ConnectorProvider, string>` — literal entries, never template literals
- `PROVIDER_GLYPH: Record<ConnectorProvider, string>` — uppercase letter per provider
- Same span classes: `inline-grid size-3.5 shrink-0 place-items-center rounded-[3px] text-[8px] font-bold leading-none text-white`
- Unknown provider types fall through to `undefined` background (T-14-01 injection guard)

### Task 2: SyncStatusPill + queryKeys Extension

`SyncStatusPill` component at `components/connectors/sync-status-pill.tsx`:
- Props: `{ status: 'ok' | 'failed' | 'syncing' | null; className?: string }`
- Reuses Phase 13 D-P-04 border/bg/text token triad (no raw palette)
- 4 states: ok→"Synced"/severity-low, failed→"Failed"/severity-critical, syncing→"Syncing"/amber+pulse, null→"Never synced"/text-faint
- `data-sync-status` attribute for test hooks

`queryKeys` extended with full Phase 11-13 baseline (connectors, savedFilters, assets, assignableUsers, tickets namespaces) plus 3 new Phase 14 namespaces:
- `cspm`: all/list/detail/stats/compliance
- `settings`: all/tenant/users/auditLog/groups
- `directoryUsers`: all/list/stats

### Task 3: Sunset Restyle (ConfirmModal + ExportButton)

**ConfirmModal**: All raw palette utilities replaced with sunset tokens:
- Backdrop: `bg-black/60` → `bg-surface/80`
- Modal panel: `bg-gray-900 border-gray-800` → `bg-surface-2 border-border-subtle`
- Text: `text-white`/`text-gray-400` → `text-text`/`text-text-muted`
- Cancel button: `border-gray-700 text-gray-400 hover:bg-gray-800` → sunset equivalents
- Confirm variants: danger `bg-red-600` → `bg-severity-critical`; warning `bg-yellow-600` → `bg-amber`; info `bg-indigo-600` → `bg-violet`
- Props unchanged: `open/title/message/confirmLabel/cancelLabel/variant/onConfirm/onCancel`
- Focus management (useEffect + useRef on confirmRef) unchanged

**ExportButton**: Restyle only (auth/download logic unchanged per RESEARCH anti-pattern):
- `border-gray-700` → `border-border-subtle`
- `text-gray-300` → `text-text-muted`
- `hover:bg-gray-800` → `hover:bg-surface-2`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test path traversal incorrect for globals.css read**
- **Found during:** Task 1 GREEN phase
- **Issue:** Test used `resolve(__dirname, '../../../app/globals.css')` but `__dirname` in vitest resolved to `src/` not `src/components/connectors/`, so the path resolved to `frontend/app/globals.css` (missing `src/`). 3 levels up from `connectors/` exits `src/`, not just `components/`.
- **Fix:** Changed to `resolve(__dirname, '../../app/globals.css')` (2 levels up from `connectors/` → `components/` → `src/`, then `app/globals.css`)
- **Files modified:** `connector-mark.test.tsx`
- **Commit:** `44a5927`

**2. [Rule 2 - Missing critical functionality] keys.ts needed Phase 11-13 baseline**
- **Found during:** Task 2 GREEN phase
- **Issue:** The worktree's `keys.ts` was at Phase 10 state (only `vulnerabilities` and `notifications`). The test referenced `queryKeys.tickets` and `queryKeys.assets` from Phase 12/13. The plan said "append after tickets" implying Phase 12/13 baseline exists.
- **Fix:** Extended `keys.ts` to include full Phase 11-13 namespaces (connectors, savedFilters, assets, assignableUsers, tickets) as required foundation, then added the Phase 14 namespaces.
- **Files modified:** `keys.ts`
- **Commit:** `efea597`

### Worktree State Note

This plan ran in a git worktree reset to commit `5559844` (planning docs branch). The soft reset left the working tree at an older Phase 10 state. Several Phase 12/13 source files (assets/, tickets/, states/) were restored from HEAD using `git checkout HEAD --` to enable the test suite to run. The TSC compiler reports 44 pre-existing errors from Phase 12/13 files that import Phase 12/13 hooks (use-assets, Avatar, ChipBar, etc.) not present in this branch's history — these are NOT caused by Plan 14-00 changes and all new connector files are TSC-clean.

## Known Stubs

None — all four deliverables are fully wired: tokens are in globals.css, ConnectorMark reads them via literal lookup, SyncStatusPill uses sunset tokens, queryKeys namespaces are exported for downstream consumption.

## Threat Flags

No new threat surface beyond T-14-01 (CSS var injection via connector_type) which is mitigated by the literal Record lookup in ConnectorMark. Verified: `grep 'var(--gradient-provider-${' connector-mark.tsx` returns 0 matches in actual code (comment-only reference to document the anti-pattern).

## Self-Check

### Created files exist:
- FOUND: `.planning/phases/14-remaining-screens/14-00-SUMMARY.md`
- FOUND: `frontend/src/components/connectors/types.ts`
- FOUND: `frontend/src/components/connectors/connector-mark.tsx`
- FOUND: `frontend/src/components/connectors/connector-mark.test.tsx`
- FOUND: `frontend/src/components/connectors/sync-status-pill.tsx`
- FOUND: `frontend/src/components/connectors/sync-status-pill.test.tsx`

### Commits exist:
- `131d196`: test(14-00): add failing tests for ConnectorMark (RED)
- `44a5927`: feat(14-00): Task 1 — 12 provider gradient tokens + 14-provider ConnectorMark
- `6c4e657`: test(14-00): add failing tests for SyncStatusPill + queryKeys namespaces (RED)
- `efea597`: feat(14-00): Task 2 — SyncStatusPill (4-state) + queryKeys namespace extension
- `5334c00`: feat(14-00): Task 3 — sunset-restyle ConfirmModal + ExportButton

## Self-Check: PASSED
