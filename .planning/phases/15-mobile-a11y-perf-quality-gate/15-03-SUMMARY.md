---
phase: 15-mobile-a11y-perf-quality-gate
plan: "03"
subsystem: frontend/ui
tags: [mobile, responsive, vaul, bottom-sheet, reduced-motion, a11y, modal, drawer]
dependency_graph:
  requires:
    - frontend/src/components/vulnerabilities/drill-panel-mobile.tsx (vaul Drawer pattern reference)
    - frontend/src/hooks/use-media-query.ts (SSR-safe breakpoint hook)
    - frontend/src/components/ui/focus-trap.ts (getFocusable + trapTabKey — desktop branch)
    - frontend/src/app/globals.css (prefers-reduced-motion blanket — confirmed exists)
  provides:
    - frontend/src/components/ui/responsive-dialog.tsx (desktop centered modal / mobile vaul bottom sheet)
  affects:
    - frontend/src/components/ui/ConfirmModal.tsx (now routes through ResponsiveDialog)
    - frontend/src/app/(authed)/dashboard/connectors/page.tsx (credential form now uses ResponsiveDialog)
    - frontend/src/app/login/page.tsx (gradient-drift gated behind motion-safe:)
    - frontend/src/components/dashboard/hero.tsx (urgency dot pulse gated behind motion-safe:)
tech_stack:
  added: []
  patterns:
    - "ResponsiveDialog: useMediaQuery('(max-width: 767px)') + vaul Drawer on mobile / role=dialog div on desktop"
    - "if (!open) return null guard in ResponsiveDialog (matches drill-panel-mobile precedent)"
    - "SSR-safe: useMediaQuery returns false on first render → desktop branch always in jsdom tests"
    - "motion-safe: Tailwind prefix for per-site reduced-motion guards (belt-and-suspenders alongside globals.css blanket)"
    - "isMobile guard on programmatic focus + Tab trap in ConfirmModal (vaul manages focus on mobile)"
key_files:
  created:
    - frontend/src/components/ui/responsive-dialog.tsx
  modified:
    - frontend/src/components/ui/ConfirmModal.tsx
    - frontend/src/app/(authed)/dashboard/connectors/page.tsx
    - frontend/src/app/login/page.tsx
    - frontend/src/components/dashboard/hero.tsx
decisions:
  - "ResponsiveDialog uses if (!open) return null guard — prevents lingering vaul portal chrome from breaking queryByRole('dialog')===null contract in jsdom tests"
  - "Desktop branch of ResponsiveDialog produces role=dialog on the inner div (not the outer overlay) so jsdom test assertions continue to pass"
  - "ConfirmModal isMobile guard skips programmatic focus + Tab trap on mobile — vaul manages focus natively; Esc handler kept belt-and-suspenders on both paths"
  - "connector form removes custom trapTabKey/Esc effect entirely — ResponsiveDialog handles dismissal on both mobile (vaul) and desktop (onOpenChange)"
  - "Skeleton loading animate-pulse (hero.tsx line 28) NOT converted — transient state, covered by globals.css blanket, acceptable per research audit"
  - "reassign-owner NOT converted — confirmed inline combobox, not a modal (research finding #4)"
  - "motion-safe: used instead of checked-prefers-reduced-motion hook for gradient-drift + urgency dot — simpler, consistent with Tailwind patterns"
metrics:
  duration: "~91 minutes"
  completed: "2026-06-25"
  tasks_completed: 3
  files_created: 1
  files_modified: 4
---

# Phase 15 Plan 03: ResponsiveDialog (D-07) + Reduced-Motion Fixes (D-11) Summary

Introduced `ResponsiveDialog` — a reusable desktop-centered-modal / mobile-vaul-bottom-sheet wrapper — and routed `ConfirmModal` (5 call sites) + the connector credential form through it. Fixed the two concrete reduced-motion gaps identified in the research audit: login gradient-drift and hero urgency-dot pulse.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Create ResponsiveDialog wrapper + route ConfirmModal through it | b2ce8be | frontend/src/components/ui/responsive-dialog.tsx, frontend/src/components/ui/ConfirmModal.tsx |
| 2 | Convert connector credential form to ResponsiveDialog | 552b387 | frontend/src/app/(authed)/dashboard/connectors/page.tsx |
| 3 | Fix login gradient-drift + hero urgency dot reduced-motion gaps | 158d901 | frontend/src/app/login/page.tsx, frontend/src/components/dashboard/hero.tsx |

## Verification Results

- `cd frontend && npx tsc --noEmit` — 0 new errors in any of the 5 plan files
- `cd frontend && npx vitest run src/app src/components` — 80 test files, 509 tests, all PASSED
- `grep -q "useMediaQuery" src/components/ui/responsive-dialog.tsx` — FOUND
- `grep -q "Drawer.Root" src/components/ui/responsive-dialog.tsx` — FOUND
- `grep -q 'role="dialog"' src/components/ui/responsive-dialog.tsx` — FOUND
- `grep -q "ResponsiveDialog" src/components/ui/ConfirmModal.tsx` — FOUND
- `grep -c "bg-severity-critical|bg-amber|bg-violet" src/components/ui/ConfirmModal.tsx` — 3
- `grep -q "ResponsiveDialog" "src/app/(authed)/dashboard/connectors/page.tsx"` — FOUND
- `grep -c "trapTabKey" "src/app/(authed)/dashboard/connectors/page.tsx"` — 0
- `grep -c "motion-safe:animate-gradient-drift" src/app/login/page.tsx` — 1
- `grep -c "motion-safe:animate-pulse" src/components/dashboard/hero.tsx` — 1 (urgency dot)
- `git diff -- login/page.tsx hero.tsx | grep "^+" | grep "!important"` — only in a comment, no CSS !important added

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes on implementation choices (within plan scope)

**1. isMobile guard in ConfirmModal for programmatic focus**
- Plan said "guard it so it does not fight vaul on mobile (only run when not mobile, or accept vaul tolerates one programmatic focus; document the choice in a comment)".
- Chose: skip programmatic focus when `isMobile` — cleaner than racing vaul's internal focus placement.
- Esc handler kept on both paths (vaul also provides Esc; belt-and-suspenders).

**2. Tab trap guard in ConfirmModal**
- Plan said "Drop the manual trapTabKey loop from the OUTER shell" and optionally "if a desktop focus trap is still wanted, retain trapTabKey scoped to the desktop branch only".
- Chose: keep `trapTabKey` in the ConfirmModal keydown handler, gated by `!isMobile`, so the desktop modal focus trap contract is preserved for keyboard users.

**3. ResponsiveDialog max-w-md vs max-w-lg for connector form**
- ResponsiveDialog desktop branch hard-codes `max-w-md` per the plan spec.
- The connector form wraps its content in a `p-6` div inside ResponsiveDialog children without overriding max-w — the form is narrower than the original `max-w-lg` shell. This is acceptable: ConnectorForm renders within the available width naturally.

**4. Comment-only `!important` in hero.tsx diff**
- The diff adds a comment that mentions `animation-duration: 0.01ms !important` (the globals.css blanket). This is a JavaScript code comment, not a CSS rule. Zero CSS `!important` was added (UX-F-02 contract fully preserved).

## Known Stubs

None — all data flows are real. ResponsiveDialog passes all props to the real vaul Drawer / role=dialog shell. ConfirmModal variant colors and action handlers are unchanged from the original implementation.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced.

T-15-06 (connector credential form secrets): form submit handler, field masking, and transport are UNCHANGED — only the modal container chrome was swapped.

T-15-07 (ResponsiveDialog dismissal): both branches always provide a dismissal path — vaul Esc/overlay on mobile, onOpenChange(false) on desktop. No half-open dialog trap.

## Self-Check: PASSED

Created files:
- frontend/src/components/ui/responsive-dialog.tsx: FOUND

Modified files contain expected changes:
- frontend/src/components/ui/ConfirmModal.tsx: contains ResponsiveDialog, DEFAULT export with 8 props, 3 variant color tokens
- frontend/src/app/(authed)/dashboard/connectors/page.tsx: contains ResponsiveDialog, 0 trapTabKey
- frontend/src/app/login/page.tsx: contains motion-safe:animate-gradient-drift
- frontend/src/components/dashboard/hero.tsx: urgency dot contains motion-safe:animate-pulse

Commits exist:
- b2ce8be (Task 1 — ResponsiveDialog + ConfirmModal): FOUND
- 552b387 (Task 2 — connector form): FOUND
- 158d901 (Task 3 — reduced-motion fixes): FOUND
