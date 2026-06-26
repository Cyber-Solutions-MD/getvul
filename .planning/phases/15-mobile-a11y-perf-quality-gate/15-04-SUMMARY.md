---
phase: 15-mobile-a11y-perf-quality-gate
plan: "04"
subsystem: frontend/a11y
tags: [a11y, jsx-a11y, eslint, keyboard, accessibility, aria, react]
dependency_graph:
  requires:
    - frontend/.eslintrc.json (Plan 01 — jsx-a11y rules elevated to error)
    - frontend/src/components/shell/bottom-nav.tsx (Plan 02 — new nav files also covered by this sweep)
    - frontend/src/components/ui/responsive-dialog.tsx (Plan 03 — dialog file also covered by this sweep)
  provides:
    - Zero jsx-a11y ESLint errors across the entire frontend (UX-07-03 / D-09)
    - Interactive rows keyboard-operable (tickets-table.tsx, reassign-combobox.tsx)
    - Dialog backdrop keyboard-parity (ticket-bulk-bar.tsx, responsive-dialog.tsx)
    - WatcherStack popover Escape key via outer wrapper instead of dialog element
  affects:
    - Phase 15 Plans 05-06 (subsequent quality-gate plans can assume clean lint baseline)
tech-stack:
  added: []
  patterns:
    - "Keyboard wrapper pattern: onKeyDown on parent <div> (no role) instead of role=dialog element — satisfies jsx-a11y/no-noninteractive-element-interactions without changing semantics"
    - "Backdrop split: role='presentation' outer div captures Escape/click-outside; inner role='dialog' owns the modal semantics"
    - "Named inner function in HOF (SectionErrorFallback) satisfies react/display-name without extra import"
    - "displayName assignment on factory-returned components (Wrapper.displayName='Wrapper') resolves react/display-name in test wrappers"

key-files:
  created: []
  modified:
    - frontend/src/components/tickets/watcher-stack.tsx (onKeyDown moved off role=dialog to outer wrapper)
    - frontend/src/components/tickets/tickets-table.tsx (role=button + tabIndex + onKeyDown on clickable li rows)
    - frontend/src/components/assets/reassign-combobox.tsx (onKeyDown Enter/Space on option rows)
    - frontend/src/components/tickets/ticket-bulk-bar.tsx (backdrop split for keyboard parity)
    - frontend/src/components/ui/responsive-dialog.tsx (backdrop split + dialog tabIndex)
    - frontend/src/types/vitest-axe.d.ts (remove invalid @typescript-eslint/no-empty-object-type eslint-disable comments)
    - frontend/src/components/settings/profile-pane.tsx (escape unescaped apostrophe)
    - frontend/src/app/(authed)/dashboard/page.tsx (name inner function in SectionErrorFallback HOF)
    - 14 test wrapper files (Wrapper.displayName on factory-returned components)

key-decisions:
  - "watcher-stack.tsx: moved onKeyDown from role=dialog to outer wrapper div — Escape bubbles up naturally, no semantic change, satisfies jsx-a11y/no-noninteractive-element-interactions cleanly"
  - "backdrop split pattern (role=presentation outer + role=dialog inner) preferred over adding handlers to dialog element — role=presentation removes landmark semantics from the overlay so AT only announces the inner dialog"
  - "responsive-dialog.tsx: replaced stopPropagation on inner div with click-guard on outer (e.target === e.currentTarget) — cleaner, no event swallowing"
  - "react/display-name in test wrappers: Wrapper.displayName assignment chosen over refactoring to module-level named components — preserves factory encapsulation, minimal diff"
  - "no-autofocus warnings in login/page.tsx intentionally left as warnings — autofocus is configured at warn (not error) in .eslintrc.json per Plan 01 design; 3 inputs use autofocus in the step-by-step login flow for good UX reason"
  - "pre-existing react/display-name, react/no-unescaped-entities, and @typescript-eslint rule-not-found errors fixed as Rule 3 blockers — they were preventing npm run lint from exiting 0 (plan success criterion)"

requirements-completed: [UX-07-03]

duration: ~35min
completed: "2026-06-26"
---

# Phase 15 Plan 04: jsx-a11y Zero-Error Sweep Summary

**eslint-plugin-jsx-a11y driven to zero errors: keyboard-operable interactive rows (tickets, combobox), dialog backdrop keyboard parity, and Escape propagation fix in WatcherStack — plus pre-existing react/display-name and unescaped-entity blockers cleared to achieve npm run lint exit 0**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-26T08:10:00Z
- **Completed:** 2026-06-26T08:49:17Z
- **Tasks:** 2
- **Files modified:** 25 (5 component files + 20 test/utility files with pre-existing non-jsx-a11y errors)

## Accomplishments

- `npm run lint` exits 0 with zero jsx-a11y errors across the entire frontend (UX-07-03, D-09)
- Interactive rows are keyboard-operable: tickets-table `<li>` rows have `role="button" tabIndex={0} onKeyDown(Enter/Space)`, combobox option rows have `onKeyDown(Enter/Space)`, dialog backdrops handle Escape
- WatcherStack popover Escape key now propagates from outer wrapper instead of attaching to `role="dialog"` element
- All 113 test files / 676 tests remain green after markup changes
- Cleared 15+ pre-existing blocking lint errors (react/display-name in test wrappers, react/no-unescaped-entities, invalid @typescript-eslint eslint-disable comments)

## Task Commits

Each task was committed atomically:

1. **Task 1: Triage jsx-a11y violations and fix non-table cluster** - `d6d9462` (fix — label-has-associated-control in notifications/workspace/showcase, from prior partial run) + `fd69ff6` (fix — display-name, unescaped entity, vitest-axe.d.ts invalid disable comments)
2. **Task 2: Fix interactive-element cluster and reach zero jsx-a11y errors** - `4da5ff1` (fix — watcher-stack, tickets-table, reassign-combobox, ticket-bulk-bar, responsive-dialog)

## Files Created/Modified

- `frontend/src/components/tickets/watcher-stack.tsx` — onKeyDown moved from `role="dialog"` to outer wrapper div (no role); jsx-a11y compliant
- `frontend/src/components/tickets/tickets-table.tsx` — `<li>` click rows get `role="button" tabIndex={0} onKeyDown(Enter/Space)` for keyboard operability
- `frontend/src/components/assets/reassign-combobox.tsx` — option rows get `onKeyDown(Enter/Space)` for keyboard selection
- `frontend/src/components/tickets/ticket-bulk-bar.tsx` — backdrop split: `role="presentation"` outer div + inner `role="dialog"` with `tabIndex={-1}`
- `frontend/src/components/ui/responsive-dialog.tsx` — backdrop split + click-guard + `onKeyDown(Escape)` on outer; inner dialog gets `tabIndex={-1}`
- `frontend/src/types/vitest-axe.d.ts` — removed 4 invalid `eslint-disable @typescript-eslint/no-empty-object-type` comments (rule not in config)
- `frontend/src/components/settings/profile-pane.tsx` — escaped `'` → `&apos;` in "You'll stay signed in"
- `frontend/src/app/(authed)/dashboard/page.tsx` — named inner function `SectionFallback` in `SectionErrorFallback` HOF
- 14 test wrapper files — `Wrapper.displayName = 'Wrapper'` added to all factory-returned anonymous components

## Decisions Made

- **watcher-stack.tsx keyboard fix:** moved `onKeyDown` off `role="dialog"` onto the outer container div (which has no ARIA role). Escape key bubbles from inside the popup naturally. This avoids putting keyboard handlers on a non-interactive element while preserving the Escape-closes-popover UX contract.
- **Backdrop split pattern:** `role="presentation"` outer div handles click-outside and Escape, inner `role="dialog"` owns modal semantics. This is cleaner than adding handlers to the dialog element itself and avoids assistive technology announcing the overlay as a second landmark.
- **Pre-existing errors treated as Rule 3 blockers:** `react/display-name`, `react/no-unescaped-entities`, and invalid `@typescript-eslint/no-empty-object-type` eslint-disable comments were pre-existing but blocking `npm run lint` exit 0 (the plan's success criterion). Fixed automatically per Rule 3.
- **no-autofocus warnings preserved:** `jsx-a11y/no-autofocus` is configured at `warn` (not `error`) per Plan 01's design. The 3 autofocus usages in `login/page.tsx` serve the step-by-step login UX and are acceptable at warning level.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-existing react/display-name in 14 test wrapper files**
- **Found during:** Task 1 (triage phase)
- **Issue:** 14 test files with `function wrap() { return ({ children }) => <JSX> }` pattern had anonymous returned components triggering `react/display-name`. These prevented `npm run lint` from exiting 0.
- **Fix:** Added `Wrapper.displayName = 'Wrapper'` on the returned component inside each factory function.
- **Files modified:** 14 test/lib files across `src/lib/mutations/`, `src/lib/queries/`, `src/components/` (see full list in Files section)
- **Verification:** `npm run lint` exit 0 — PASSED
- **Committed in:** fd69ff6 (Task 1 commit)

**2. [Rule 3 - Blocking] Invalid eslint-disable comments in vitest-axe.d.ts**
- **Found during:** Task 1 (triage phase)
- **Issue:** 4 `eslint-disable-next-line @typescript-eslint/no-empty-object-type` comments referenced a rule not present in the project's ESLint config. ESLint reported "Definition for rule was not found" errors for each.
- **Fix:** Removed the disable comments entirely. The empty interface augmentations are valid TypeScript module augmentation syntax; no rule needed disabling.
- **Files modified:** `frontend/src/types/vitest-axe.d.ts`
- **Verification:** `npm run lint` exit 0 — PASSED
- **Committed in:** fd69ff6 (Task 1 commit)

**3. [Rule 3 - Blocking] react/no-unescaped-entities in profile-pane.tsx**
- **Found during:** Task 1 (triage phase)
- **Issue:** `"You'll stay signed in"` had an unescaped apostrophe in JSX text.
- **Fix:** Changed to `You&apos;ll stay signed in`.
- **Files modified:** `frontend/src/components/settings/profile-pane.tsx`
- **Committed in:** fd69ff6 (Task 1 commit)

**4. [Rule 3 - Blocking] react/display-name in dashboard/page.tsx**
- **Found during:** Task 1 (triage phase)
- **Issue:** `SectionErrorFallback` HOF returned an anonymous arrow function component.
- **Fix:** Changed to a named inner function declaration (`function SectionFallback(...)`) so React DevTools and ESLint can identify it.
- **Files modified:** `frontend/src/app/(authed)/dashboard/page.tsx`
- **Committed in:** fd69ff6 (Task 1 commit)

---

**Total deviations:** 4 auto-fixed (all Rule 3 — blocking pre-existing lint errors that prevented `npm run lint` exit 0)
**Impact on plan:** All auto-fixes necessary for the plan's success criterion (`npm run lint` exit 0). No scope creep — no eslint-disable suppressions added.

## Threat Flags

T-15-08 (eslint-disable misuse): NO undocumented `eslint-disable jsx-a11y` suppressions added. Zero violations fixed via suppression — all fixed via proper accessible markup.

## Known Stubs

None — all interactive element fixes use real keyboard handlers, not stubs.

## Self-Check: PASSED

Commits exist:
- d6d9462 (fix jsx-a11y/label-has-associated-control — partial prior run): FOUND
- fd69ff6 (fix non-table jsx-a11y and blocking lint errors): FOUND
- 4da5ff1 (fix interactive-element jsx-a11y cluster — reach zero errors): FOUND

Verification:
- `npm run lint` exit 0: CONFIRMED (exits 0, only 5 warnings, zero errors)
- `npm run lint 2>&1 | grep "jsx-a11y" | grep "Error"`: EMPTY (zero error-level jsx-a11y)
- `npx vitest run`: 113 files, 676 tests, all PASSED
- No eslint-disable jsx-a11y suppressions added: CONFIRMED

## Next Phase Readiness

- Phase 15 Plan 05 (axe-core WCAG E2E tests) can rely on a clean ESLint baseline
- Phase 15 Plan 06 (Lighthouse performance budget) unaffected — markup changes are minor
- All interactive rows are keyboard-operable per the established Phase 11 pattern
