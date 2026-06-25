---
phase: 15-mobile-a11y-perf-quality-gate
plan: "02"
subsystem: frontend/shell
tags: [mobile-nav, responsive, bottom-nav, vaul, drawer, focus-trap, a11y, tailwind]
dependency_graph:
  requires:
    - frontend/src/components/shell/sidebar.tsx (nav source refactored from here)
    - frontend/src/components/vulnerabilities/drill-panel-mobile.tsx (vaul Drawer pattern)
    - frontend/src/components/ui/focus-trap.ts (getFocusable + trapTabKey)
  provides:
    - frontend/src/components/shell/nav-items.ts (single source-of-truth nav arrays)
    - frontend/src/components/shell/bottom-nav.tsx (phone <768px 4-slot fixed nav)
    - frontend/src/components/shell/nav-more-sheet.tsx (vaul sheet for 6 secondary destinations)
    - frontend/src/components/shell/nav-drawer.tsx (tablet 768–999px slide-in drawer)
  affects:
    - frontend/src/components/shell/sidebar.tsx (refactored to consume nav-items.ts)
    - frontend/src/components/shell/topbar.tsx (hamburger button added)
    - frontend/src/components/shell/app-shell.tsx (drawer/bottom-nav wired in)
    - All Phase 15 plans requiring mobile nav (15-04 viewport sweep will verify these tiers)
tech_stack:
  added:
    - "vaul Drawer.Root/Portal/Overlay/Content pattern (already a dep) — nav-more-sheet.tsx"
  patterns:
    - "Three-tier responsive nav: <768px bottom-nav / 768–999px hamburger drawer / >=1000px sidebar"
    - "nav-items.ts single source-of-truth: TRIAGE_ITEMS / WORKFLOW_ITEMS / UNLABELED_ITEMS / ALL_ITEMS / BOTTOM_NAV_PRIMARY / MORE_ITEMS"
    - "vaul guard pattern: if (!open) return null (matches drill-panel-mobile, no lingering portal chrome)"
    - "motion-safe:transition-transform on drawer slide (reduced-motion: reduce users get instant toggle)"
    - "Focus trap via getFocusable + trapTabKey + Esc handler (mirrors ConfirmModal pattern)"
    - "env(safe-area-inset-bottom) phone padding in both bottom-nav and main content area"
    - "gradient-strip active indicator: top-edge in bottom-nav (bg-gradient-sunset-vertical), left-edge in drawer/more-sheet (matching sidebar)"
key_files:
  created:
    - frontend/src/components/shell/nav-items.ts
    - frontend/src/components/shell/bottom-nav.tsx
    - frontend/src/components/shell/nav-more-sheet.tsx
    - frontend/src/components/shell/nav-drawer.tsx
  modified:
    - frontend/src/components/shell/sidebar.tsx
    - frontend/src/components/shell/topbar.tsx
    - frontend/src/components/shell/app-shell.tsx
decisions:
  - "nav-items.ts is a .ts (not .tsx) file — no JSX; exports types + arrays + isActive function as module-private-free contract"
  - "MORE_ITEMS computed via Set subtraction from ALL_ITEMS — if BOTTOM_NAV_PRIMARY changes, MORE_ITEMS updates automatically without manual sync"
  - "NavDrawer kept mounted (not null-guarded) with translate-x-full/-translate-x-0 for motion-safe slide; aria-hidden + pointer-events-none prevent interaction when closed"
  - "Topbar hamburger conditionally rendered only when onMenuClick prop provided — existing Topbar callers/tests unaffected"
  - "topbar.tsx promoted to 'use client' (was implicit server component) to accept onMenuClick callback prop"
  - "Bottom-nav gradient-strip on TOP edge (not left edge like sidebar) — strip at the top of bottom-nav aligns with the direction of the nav bar"
  - "NavMoreSheet uses if (!open) return null guard matching drill-panel-mobile precedent — avoids lingering dialog role in DOM when closed"
  - "AppShell pb-[calc(64px+env(safe-area-inset-bottom))] min-[768px]:pb-6 — 64px approx bottom-nav bar height; min-[768px] reverts at tablet+ where bottom-nav is hidden"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-25"
  tasks_completed: 3
  files_created: 4
  files_modified: 3
---

# Phase 15 Plan 02: Three-Tier Responsive Navigation Summary

Built the complete mobile navigation layer: phone <768px 4-slot bottom-nav with safe-area padding and vaul "More" sheet; tablet 768–999px hamburger-triggered slide-in drawer with focus trap; and a single `nav-items.ts` source-of-truth that all three mobile tiers (plus the unmodified sidebar) consume.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Extract nav source-of-truth to nav-items.ts, refactor sidebar | 7af2cc5 | frontend/src/components/shell/nav-items.ts, frontend/src/components/shell/sidebar.tsx |
| 2 | Build bottom-nav.tsx + nav-more-sheet.tsx (phone tier) | 7a789cd | frontend/src/components/shell/bottom-nav.tsx, frontend/src/components/shell/nav-more-sheet.tsx |
| 3 | Build nav-drawer.tsx + wire AppShell/Topbar | 567a873 | frontend/src/components/shell/nav-drawer.tsx, frontend/src/components/shell/topbar.tsx, frontend/src/components/shell/app-shell.tsx |

## Verification Results

- `cd frontend && npx tsc --noEmit` — 0 new errors in any shell file (6 pre-existing errors in e2e/playwright.config.ts and tickets test files are out of scope)
- `cd frontend && npx vitest run src/components/shell` — 3 test files, 12 tests, all PASSED
- `grep -q "env(safe-area-inset-bottom)" bottom-nav.tsx` — FOUND (UX-07-02)
- `grep -q "min-[768px]:hidden" bottom-nav.tsx` — FOUND (phone-only gating)
- `grep -q "Drawer.Root" nav-more-sheet.tsx` — FOUND
- `grep -q "aria-label=\"Mobile navigation\"" bottom-nav.tsx` — FOUND
- `grep -q "aria-label=\"Navigation menu\"" nav-drawer.tsx` — FOUND
- `grep -q "trapTabKey" nav-drawer.tsx` — FOUND (focus trap)
- `grep -E "motion-safe:transition" nav-drawer.tsx` — FOUND
- `grep -q "calc(64px+env(safe-area-inset-bottom))" app-shell.tsx` — FOUND

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes on implementation choices (within plan scope)

**1. topbar.tsx promoted to 'use client'**
- The plan required adding `onClick` to the hamburger; the existing Topbar had no `'use client'` directive.
- Added `'use client'` and the `onMenuClick?: () => void` + `hamburgerRef?` props. Existing tests pass because the hamburger only renders when `onMenuClick` is provided (the test renders `<AppShell>` without it directly mounted to Topbar).

**2. NavDrawer kept mounted (not null-guarded)**
- The plan offered the choice of "render only when open OR keep mounted with translate". Chose keep-mounted with `aria-hidden + pointer-events-none` when closed for a smooth motion-safe:transition. The `NavMoreSheet` uses the null-guard pattern (per drill-panel-mobile precedent) since vaul manages its own portal lifecycle.

**3. hamburgerRef threaded through AppShell → Topbar → NavDrawer**
- Added an optional `hamburgerRef` prop to both Topbar and NavDrawer per T-15-05 focus-trap mitigation (trap cannot lock out the user — Esc always closes, focus restores to hamburger).

## Known Stubs

None — all nav destinations link to real routes. Active state computed from `usePathname`. Stats chips (vuln_open/asset_total/ticket_open) are NOT shown in bottom-nav or drawer (only sidebar renders chips per D-N-01 — chips belong to the persistent 220px sidebar context only).

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All navigation hrefs are static internal route literals (T-15-04: accept). Focus trap reuses vetted getFocusable/trapTabKey with Esc + backdrop always callable (T-15-05: mitigated).

## Self-Check: PASSED

Created files exist:
- frontend/src/components/shell/nav-items.ts: FOUND
- frontend/src/components/shell/bottom-nav.tsx: FOUND
- frontend/src/components/shell/nav-more-sheet.tsx: FOUND
- frontend/src/components/shell/nav-drawer.tsx: FOUND

Modified files contain expected changes:
- frontend/src/components/shell/sidebar.tsx: contains `from './nav-items'`, no inline TRIAGE_ITEMS
- frontend/src/components/shell/topbar.tsx: contains hamburger + min-[768px]:max-[999px]
- frontend/src/components/shell/app-shell.tsx: contains BottomNav, NavDrawer, useState, calc(64px+env(...))

Commits exist:
- 7af2cc5 (Task 1 — nav-items.ts + sidebar refactor): FOUND
- 7a789cd (Task 2 — bottom-nav + nav-more-sheet): FOUND
- 567a873 (Task 3 — nav-drawer + AppShell/Topbar wiring): FOUND
