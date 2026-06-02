---
phase: 14-remaining-screens
plan: "01"
subsystem: frontend/settings
tags: [settings, rbac, dirty-state, sidebar, tdd]
dependency_graph:
  requires: []
  provides:
    - SettingsSidebarShell (RBAC-gated sidebar shell for settings categories)
    - SaveBar (sticky dirty-state save bar)
    - useDirtyState (dirty-tracking hook)
    - microcopy.ts (settings copy strings + CATEGORY_LABELS + UNSAVED_GUARD)
  affects:
    - frontend/src/app/(authed)/dashboard/settings/page.tsx (consumes SettingsSidebarShell in 14-05)
    - Any settings category pane (consumes SaveBar + useDirtyState in 14-05)
tech_stack:
  added: []
  patterns:
    - TDD (RED/GREEN) — test written first, then minimal implementation
    - Gradient-strip active indicator (mirrors app-shell.md nav-item.active pattern)
    - JSON.stringify dirty comparison with baselineJson state for re-render triggering
key_files:
  created:
    - frontend/src/components/settings/settings-sidebar-shell.tsx
    - frontend/src/components/settings/settings-sidebar-shell.test.tsx
    - frontend/src/components/settings/save-bar.tsx
    - frontend/src/components/settings/save-bar.test.tsx
    - frontend/src/components/settings/use-dirty-state.ts
    - frontend/src/components/settings/microcopy.ts
  modified: []
decisions:
  - "JSON.stringify baseline stored in React state (not just useRef) so that reset() with no args triggers a re-render and isDirty correctly reads false"
  - "SAVE_BAR copy strings live in microcopy.ts and imported by save-bar.tsx; grep on save-bar.tsx matches via comment references"
  - "gradient-brand CSS variable with fallback chain to gradient-sunset and hardcoded gradient for test environments with no CSS"
metrics:
  duration: "~6 minutes"
  completed_date: "2026-06-02"
  tasks_completed: 2
  files_created: 6
  tests_added: 15
---

# Phase 14 Plan 01: Settings Shell + Dirty-State Foundation Summary

Wave 0 settings shell: RBAC-gated `SettingsSidebarShell` (220px sidebar, gradient-strip active indicator, no tab patterns) + `SaveBar` (sticky bottom, slide-in, dirty-driven) + `useDirtyState` hook (JSON.stringify baseline comparison) + settings `microcopy.ts`.

## What Was Built

**Task 1 — SettingsSidebarShell + microcopy** (`e331ba2`)

`SettingsSidebarShell` is the layout primitive consumed verbatim by the settings screen plan (14-05). It implements D-SET-01 (sidebar of categories) and D-SET-05 (RBAC gating).

Key decisions:
- Left 220px `<nav>` with `border-r border-border-subtle`; right `flex-1 overflow-y-auto` pane wrapping `{children}`
- `visibleCategories` filters `ALL_CATEGORIES` using `ADMIN_ONLY` set — `profile` + `api-tokens` always visible; `workspace`, `saml`, `notifications`, `audit` require `isAdmin = role === 'OWNER' || role === 'ADMIN'`
- Active indicator: absolutely-positioned `<span>` with `style={{ background: 'var(--gradient-brand, ...)' }}` at `left-0 top-1 bottom-1 w-0.5 rounded-full` — mirrors `app-shell.md` `nav-item.active::before` pattern
- Zero `border-b-2`, `border-b border-indigo`, `role="tab"` — Pitfall 1 grep gate passes
- T-14-04 security comment in source: UX layer only, backend 403 is authoritative

`microcopy.ts` exports `CATEGORY_LABELS: Record<Category, string>` (sentence case per copy-voice.md), `UNSAVED_GUARD` (names the action; no "Are you sure?"), and `SAVE_BAR` copy strings.

**Task 2 — SaveBar + useDirtyState** (`10dd654`)

`SaveBar` is the sticky per-category save bar (D-SET-04). Mirrors `TicketBulkBar` bottom-anchor pattern from Phase 13.

Key decisions:
- Returns `null` when `!isDirty` (invisible by default)
- `fixed inset-x-0 bottom-0 z-30 border-t border-border-subtle bg-surface-2/95 backdrop-blur px-6 py-3 animate-in slide-in-from-bottom-2`
- `data-save-bar` attribute on container for selector hooks
- "Save changes" gradient CTA (`from-pink to-violet`) + "Discard" ghost button + "Saving…" disabled state
- Zero raw palette utilities (no gray-N, indigo-N)

`useDirtyState<T>` hook:
- `isDirty` computed via `JSON.stringify(values) !== baselineJson`
- `setField(key, val)` — updates one field
- `reset(next?)` — promotes current values to baseline (re-render triggered by `setBaselineJson` state); or sets both baseline+values to `next` after successful PATCH

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] useDirtyState reset() no-args did not trigger re-render**
- **Found during:** Task 2 GREEN phase (test failed: `isDirty` still `true` after `reset()`)
- **Issue:** Initial implementation stored baseline only in a `useRef`. After `reset()` with no args, `baseline.current` was updated but no React state change occurred, so the next render still saw `isDirty=true` (computed from the stale render's `values` vs the silently-updated ref).
- **Fix:** Added `baselineJson` as React state alongside the ref. `isDirty` compares `JSON.stringify(values) !== baselineJson`. `reset()` calls `setBaselineJson(...)` to trigger re-render. `reset(next)` calls `setBaselineJson` + `setValues`. `reset()` with no args uses a functional `setValues` updater to atomically capture latest state then update the baseline JSON.
- **Files modified:** `frontend/src/components/settings/use-dirty-state.ts`
- **Commit:** `10dd654`

## Known Stubs

None — this plan creates pure UI primitives (no data fetching, no wired state). The `SettingsSidebarShell` renders `{children}` as a slot; the actual pane content is wired in 14-05. The `SaveBar` renders save/discard UI with callback props; the PATCH mutation is the caller's responsibility.

## Threat Flags

No new threat surface introduced. These are client-side UI primitives only:
- No new network endpoints
- No new auth paths
- T-14-04 (RBAC gating) and T-14-05 (dirty state) are within the plan's threat model and both dispositioned

## TDD Gate Compliance

Both tasks followed RED/GREEN:
- Task 1: `test(14-01)` commit `a883400` (RED) → `feat(14-01)` commit `e331ba2` (GREEN)
- Task 2: `test(14-01)` commit `5122f51` (RED) → `feat(14-01)` commit `10dd654` (GREEN)

## Self-Check: PASSED

Files created:
- `frontend/src/components/settings/settings-sidebar-shell.tsx` — FOUND
- `frontend/src/components/settings/settings-sidebar-shell.test.tsx` — FOUND
- `frontend/src/components/settings/save-bar.tsx` — FOUND
- `frontend/src/components/settings/save-bar.test.tsx` — FOUND
- `frontend/src/components/settings/use-dirty-state.ts` — FOUND
- `frontend/src/components/settings/microcopy.ts` — FOUND

Commits:
- `a883400` — RED tests for SettingsSidebarShell — FOUND
- `e331ba2` — GREEN implementation for SettingsSidebarShell — FOUND
- `5122f51` — RED tests for SaveBar+useDirtyState — FOUND
- `10dd654` — GREEN implementation for SaveBar+useDirtyState — FOUND

Tests: 15/15 passing across 2 test files.
