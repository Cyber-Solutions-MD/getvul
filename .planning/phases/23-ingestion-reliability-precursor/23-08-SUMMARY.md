---
phase: 23-ingestion-reliability-precursor
plan: 08
subsystem: ui
tags: [react-query, ticketing, drill-panel, state-patterns, tanstack-query, next.js]

requires:
  - phase: 23-ingestion-reliability-precursor (Plan 04)
    provides: "GET /api/v1/tickets/providers — tenant-scoped configured+enabled ticketing providers (D-15)"
  - phase: 23-ingestion-reliability-precursor (Plan 03)
    provides: "frontend/src/lib/ticketing/providers.ts TicketProvider type + PROVIDER_LABELS; CreateTicketRequest.provider field"
provides:
  - "useTicketingProviders() React Query hook (queryKey ['ticketing','providers'])"
  - "TicketProviderPicker component with loading/error/empty(deep-link)/populated states, reusing ConnectorMark gradient marks"
  - "Vuln drill-panel create flow now sends the analyst's chosen provider instead of hardcoded 'ASANA'"
  - "ConfirmModal.tsx additive children + confirmDisabled props (backward compatible)"
affects: [23-09, phase-27-ticket-auto-drafting]

tech-stack:
  added: []
  patterns:
    - "Confirm-dialog-scoped data fetching: mounting a React Query hook only when the dialog is open (via ResponsiveDialog's `!open -> return null` guard) avoids firing the query — and needing to mock it — in tests that never open the dialog."
    - "Additive shared-primitive extension: optional props on a widely-reused component (ConfirmModal) keep all existing call sites byte-identical while unlocking one new caller's requirement."

key-files:
  created:
    - frontend/src/lib/queries/use-ticketing-providers.ts
    - frontend/src/components/vulnerabilities/ticket-provider-picker.tsx
    - frontend/src/components/vulnerabilities/ticket-provider-picker.test.tsx
  modified:
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/ui/ConfirmModal.tsx

key-decisions:
  - "Picker mounts inside ConfirmModal's body (gated by confirmOpen), not always-visible in the Actions section — keeps the providers query from firing until the analyst actually opens the create-ticket confirm step, and keeps drill-panel.test.tsx / drill-panel-mobile.test.tsx passing without needing to mock the new hook."
  - "ConfirmModal.tsx extended additively with optional children + confirmDisabled props (not in the plan's files_modified list) rather than hand-rolling a bespoke dialog for this one flow — all 4 other call sites (connectors, settings, workspace-pane, ticket-bulk-bar) pass neither prop and are unaffected."
  - "Confirm action disabled via `confirmDisabled={!ticketProvider}` — covers both the brief loading window before the picker's default-select fires AND the tenant-has-zero-providers case, without threading a second prop."
  - "Mobile nested-confirm path (drill-panel-mobile.tsx renderConfirm) intentionally left unwired — see Known Gaps."

requirements-completed: [REL-04]

duration: 20min
completed: 2026-07-27
---

# Phase 23 Plan 08: Ticket Provider Picker Summary

**Analyst now picks Asana/Jira/GitHub (filtered to the tenant's D-15 configured+enabled providers) when creating a ticket from the desktop vuln drill panel, replacing the hardcoded `provider: 'ASANA'`.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-27T13:05:00Z (approx, after worktree stale-base fix)
- **Completed:** 2026-07-27T13:22:00Z
- **Tasks:** 3/3 completed
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments
- `useTicketingProviders()` hook consuming Plan 04's `GET /api/v1/tickets/providers` endpoint, mirroring the existing `use-connectors-admin.ts` fetch/queryKey conventions.
- `TicketProviderPicker` component with all four mandatory design-system states (loading skeleton, error alert, empty deep-link to `/dashboard/connectors`, populated radiogroup), reusing `ConnectorMark` gradient marks per the visual-language contract — no invented glyphs, no freehand hex.
- Drill-panel create flow wired end-to-end: the mutation now sends the analyst's chosen provider; the Confirm action is disabled until a provider is selected (covers both the loading window and the zero-configured-providers case).

## Task Commits

Each task was committed atomically:

1. **Task 1: useTicketingProviders query hook** - `c68c21b` (feat)
2. **Task 2: TicketProviderPicker component (TDD)** - `9f2f3e6` (test, RED) → `d2e88c0` (feat, GREEN)
3. **Task 3: Wire picker into drill-content.tsx create flow** - `b36bd76` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `frontend/src/lib/queries/use-ticketing-providers.ts` - `useTicketingProviders()` React Query hook, queryKey `['ticketing','providers']`
- `frontend/src/components/vulnerabilities/ticket-provider-picker.tsx` - Provider picker with loading/error/empty/populated states
- `frontend/src/components/vulnerabilities/ticket-provider-picker.test.tsx` - 5 tests covering all four states + server-side filtering
- `frontend/src/components/vulnerabilities/drill-content.tsx` - Wired `ticketProvider` state; mutation sends `ticketProvider ?? 'ASANA'`; Confirm disabled while unset
- `frontend/src/components/ui/ConfirmModal.tsx` - Additive `children` + `confirmDisabled` props (backward compatible)

## Decisions Made
- Rendered the picker inside `ConfirmModal`'s body (not always-visible in the Actions section) so its query only mounts once the analyst opens the create-ticket confirm step — this is both the literal plan instruction ("inside the ConfirmModal body") and what kept the pre-existing `drill-panel.test.tsx` / `drill-panel-mobile.test.tsx` suites green without new mocks.
- Extended `ConfirmModal.tsx` additively (see Deviations) rather than building a bespoke dialog just for this flow.
- Default-selection logic lives inside `TicketProviderPicker` (calls `onChange` once data loads) rather than in `drill-content.tsx`, keeping the parent's state management trivial (`useState<TicketProvider | null>`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extended ConfirmModal.tsx with optional children + confirmDisabled props**
- **Found during:** Task 3
- **Issue:** The plan's literal instruction — "Render `<TicketProviderPicker>` inside the ConfirmModal body (above/near the confirm action)" — could not be satisfied because `ConfirmModal.tsx` (frontend/src/components/ui/ConfirmModal.tsx) only accepted a plain `message: string`, with no slot for arbitrary JSX, and no way to disable its Confirm button. This file was not in the plan's `files_modified` list.
- **Fix:** Added two optional, backward-compatible props: `children?: React.ReactNode` (rendered between the message and the action row) and `confirmDisabled?: boolean` (disables + dims the Confirm button). All 4 pre-existing call sites (`connectors/page.tsx`, `settings/page.tsx`, `workspace-pane.tsx`, `ticket-bulk-bar.tsx`) pass neither prop and render byte-identical to before.
- **Files modified:** frontend/src/components/ui/ConfirmModal.tsx
- **Verification:** Full frontend suite (126 files / 751 tests) green after the change, including all 4 other call sites' existing tests.
- **Committed in:** b36bd76 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to satisfy the plan's explicit "inside the ConfirmModal body" placement without duplicating dialog chrome in a one-off bespoke modal. No scope creep — additive, backward-compatible, zero behavior change for existing callers.

## Known Gaps

- **Mobile nested-confirm path not wired.** `drill-panel-mobile.tsx`'s `renderConfirm` slot (a `Drawer.NestedRoot` bottom-sheet, used only on `<768px` viewports) renders its own confirm UI independent of `ConfirmModal` and was intentionally left unmodified — it is not in this plan's `files_modified` list. On mobile, `ticketProvider` therefore stays `null` and the create mutation always falls through to the `?? 'ASANA'` fallback, identical to pre-plan behavior (not a regression, but not the fix either). A tenant with Jira/GitHub but no Asana connector configured would still get a failed/misdirected create if they use the mobile create flow. Flagging for a follow-up plan — the desktop flow (drill-panel.tsx / DrillPanel) is unaffected and fully wired.

## Issues Encountered
- Worktree started on the documented stale base (`adc0571`, predating all Phase 23 work) — detected via the mandated `merge-base` check and reset to `a74593d` before any work began (clean tree, no salvage needed).
- `frontend/node_modules` was absent in the fresh worktree as warned — resolved with `npm install --legacy-peer-deps`.

## User Setup Required

None - no external service configuration required. The endpoint consumed (`GET /api/v1/tickets/providers`) already exists on the base commit (Plan 04).

## Next Phase Readiness

- REL-04's user-facing story (analyst chooses the provider at create time) is complete for the desktop drill panel — the primary and most-used create path.
- Follow-up candidate: wire the same picker into `drill-panel-mobile.tsx`'s nested-confirm path for full mobile parity (see Known Gaps).
- `useTicketingProviders()` and the `['ticketing','providers']` queryKey are reusable as-is by Phase 27's ticket auto-drafting (noted in the backend endpoint's own docstring).

---
*Phase: 23-ingestion-reliability-precursor*
*Completed: 2026-07-27*

## Self-Check: PASSED

All 6 created/modified files found on disk; all 4 task commit hashes (c68c21b, 9f2f3e6, d2e88c0, b36bd76) found in git log.
