---
phase: 23-ingestion-reliability-precursor
plan: 11
subsystem: ui
tags: [react, vulnerability-drill-panel, ticketing, mobile, vaul, vitest]

requires:
  - phase: 23-ingestion-reliability-precursor
    provides: "Plan 04's backend TicketProvider(...) re-coercion (client provider is advisory, not the trust anchor); Plan 08's desktop TicketProviderPicker + confirmDisabled={!ticketProvider} gate"
provides:
  - "Mobile drill-panel ticket creation now honors the analyst-selected/tenant-default provider, closing the D-07-class ASANA-fallback defect on the mobile nested-confirm path"
  - "Extended renderConfirm slot contract (ticketProvider, onProviderChange) reusable by any future renderConfirm consumer"
  - "Regression test proving the mobile confirm fires the selected provider and blocks confirm until one is chosen"
affects: [vulnerabilities, ticketing, mobile-ui]

tech-stack:
  added: []
  patterns:
    - "renderConfirm slot now forwards ticketProvider state so any custom confirm surface (mobile, future embeds) can reuse TicketProviderPicker without duplicating DrillContent's provider state"

key-files:
  created: []
  modified:
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx

key-decisions:
  - "Widened the renderConfirm callback-args type (ticketProvider, onProviderChange) rather than lifting ticketProvider state out of DrillContent — smallest additive change, no API surface removed, desktop ConfirmModal branch untouched"
  - "Mobile Create-ticket button disabled={ticketProvider === null} mirrors the desktop confirmDisabled={!ticketProvider} gate exactly, rather than inventing new mobile-specific validation logic"
  - "Reused <TicketProviderPicker> verbatim (loading/error/empty/populated states already built and tested) instead of a mobile-specific picker"

patterns-established:
  - "Confirm-slot callbacks that need provider selection should always destructure ticketProvider + onProviderChange from renderConfirm rather than duplicating provider state locally"

requirements-completed: [REL-04]

coverage:
  - id: D1
    description: "Mobile nested confirm dialog renders TicketProviderPicker and gates the Create-ticket button on ticketProvider !== null, so a ticket is never silently fired against the ASANA default"
    requirement: "REL-04"
    verification:
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx#Case A — mobile confirm fires the SELECTED provider (JIRA), never a silent ASANA fallback"
        status: pass
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx#Case B — mobile confirm is BLOCKED (disabled), not defaulted to ASANA, while no provider is loaded/selected"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-07-28
status: complete
---

# Phase 23 Plan 11: Mobile Ticket-Create Provider Gap Closure Summary

**Closed CR-01/REL-04 gap: the mobile drill-panel nested confirm now renders `TicketProviderPicker` and blocks its Create-ticket button until a provider is selected, instead of silently firing every mobile ticket as ASANA.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-28T05:49:00Z
- **Completed:** 2026-07-28T05:53:09Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Extended `DrillContent`'s `renderConfirm` slot contract to forward `ticketProvider` and `onProviderChange`, without touching the desktop `ConfirmModal` branch or `fireTicket`
- Wired `<TicketProviderPicker>` into the mobile `Drawer.NestedRoot` confirm dialog and gated its Create-ticket button with `disabled={ticketProvider === null}` (with visible disabled styling), reaching desktop parity
- Added a regression test (`drill-panel-mobile.test.tsx`) with two cases: the selected/default provider (`JIRA`) is honored and never falls through to `ASANA`, and the confirm button stays disabled while no provider is loaded/selected — manually proved the guard is live by temporarily reverting the Task 2 fix, confirming both cases fail against pre-fix code (fires `ASANA`, button enabled) before restoring the fix

## Task Commits

Each task was committed atomically:

1. **Task 1: Thread ticketProvider + onProviderChange through DrillContent's renderConfirm slot** - `109afea` (feat)
2. **Task 2: Render TicketProviderPicker in the mobile nested confirm dialog and gate its confirm button** - `f18da4f` (feat)
3. **Task 3: Regression test — mobile confirm fires the SELECTED provider and is blocked until one is chosen** - `c037e32` (test)

**Plan metadata:** see final docs commit below.

_Note: Task 3 is test-only by design (the fix landed in Tasks 1-2); the plan intentionally sequences fix-then-test for this gap-closure regression, and the regression proof (revert → both cases fail) was verified manually before restoring the fix, confirming the test is a live guard rather than a tautology._

## Files Created/Modified
- `frontend/src/components/vulnerabilities/drill-content.tsx` - `renderConfirm` slot type gains `ticketProvider: TicketProvider | null` and `onProviderChange: (p: TicketProvider) => void`; call site forwards live state
- `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` - nested confirm renders `<TicketProviderPicker>` and disables its Create-ticket button while `ticketProvider === null`
- `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` - `useTicketingProviders` mock added, `use-create-ticket` mock switched to `mutateAsync`, two new regression cases (provider honored / confirm gated)

## Decisions Made
- Widened the `renderConfirm` callback-args type instead of lifting `ticketProvider` state out of `DrillContent` (smallest additive change; desktop branch untouched)
- Mobile Create-ticket button uses `disabled={ticketProvider === null}`, the direct mirror of desktop's `confirmDisabled={!ticketProvider}`
- Reused `<TicketProviderPicker>` verbatim rather than building mobile-specific picker UI

## Deviations from Plan

None - plan executed exactly as written. The existing `use-create-ticket` mock in `drill-panel-mobile.test.tsx` was already flagged by the plan as needing a `mutateAsync` correction (Task 3's `<read_first>` called this out explicitly), so that change was anticipated, not a deviation.

## Issues Encountered
- Before Task 3's mock update, the pre-existing "nested ConfirmModal" test failed with `No QueryClient set` once the mobile confirm started rendering `<TicketProviderPicker>` (which calls `useTicketingProviders` → `useQuery`). Resolved by adding the `useTicketingProviders` mock with a `beforeEach` default (`JIRA` configured) so pre-existing tests that open the nested confirm without asserting on provider selection continue to pass — this was the planned Task 3 work, not an unplanned fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- REL-04 now holds on both desktop and mobile drill-panel ticket-creation paths; CR-01 gap from the 23-VERIFICATION.md / 23-REVIEW.md is closed.
- No further work identified for this gap; phase 23's remaining plans (already summarized) are unaffected by this change.

---
*Phase: 23-ingestion-reliability-precursor*
*Completed: 2026-07-28*

## Self-Check: PASSED

All created/modified files verified present on disk; all three task commit hashes (`109afea`, `f18da4f`, `c037e32`) verified present in `git log --all`.
