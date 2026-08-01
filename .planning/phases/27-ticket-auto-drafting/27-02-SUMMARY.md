---
phase: 27-ticket-auto-drafting
plan: 02
subsystem: ui
tags: [react, tanstack-query, vitest, ai-composition, TDD, AID-01]

# Dependency graph
requires:
  - phase: 27-01
    provides: "TicketCreateRequest.title backend contract + CreateTicketRequest.title? frontend mutation type this plan's fireTicket() threads into"
provides:
  - "frontend/src/lib/tickets/compose-ticket-draft.ts — composeTicketTitle (deterministic '[{sev}] {cve} on {hosts}', zero AI call) + composeTicketDescription (labeled multi-section plain-text body: Description -> Remediation -> Asset context -> Prioritization, each AI section present only on a grounded cache hit, Asset context always present)"
  - "drill-content.tsx desktop wiring: title/setTitle state, a resourceId-keyed composedForId ref guard + compose-on-open effect (RESEARCH Pattern 4), a Title Input in the ConfirmModal, renderConfirm args extended with title/onTitleChange, title threaded into fireTicket()'s mutateAsync body"
  - "The shared compose-on-open effect lives inside DrillContent itself (not desktop-only) -- drill-panel-mobile.tsx already inherits the auto-composed title/description via its renderConfirm args, ahead of Plan 03's own mobile Title Input UI"
affects: [27-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared pure-function composer module (frontend/src/lib/tickets/compose-ticket-draft.ts) callable identically from desktop (this plan) and mobile (Plan 03) -- closes the 'Phase 25 divergence lesson' at its source instead of hand-duplicating conditional section logic across two files (RESEARCH Pattern 1)"
    - "Composed-once guard as a useRef<string|null> keyed to resourceId (v.id ?? idOrCve), not a blank-string check -- resolves three distinct edge cases with one mechanism: same-vuln re-open preserves edits, cross-vuln switch recomposes, and the pre-existing 'Copy into ticket description' button never starves the guard (RESEARCH Pattern 4)"
    - "Hooks moved before the pending/error early-return guards: v/cveLabel/hostsLine/sevLabel now computed unconditionally (via `(q.data ?? {}) as unknown as FlexibleDetail`) so the new useExplainCache reads + compose-on-open effect satisfy Rules of Hooks while the detail query is still pending"

key-files:
  created:
    - frontend/src/lib/tickets/compose-ticket-draft.ts
    - frontend/src/lib/tickets/compose-ticket-draft.test.ts
  modified:
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/vulnerabilities/drill-panel.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx

key-decisions:
  - "Caption placement resolved in favor of 'AI-drafted -- review before creating.' rendering ABOVE the Title Input (matching the Copywriting Contract's explicit '(sits once above the Title field)' annotation and the Spacing Scale row's literal gap order 'TicketProviderPicker -> caption -> Title field -> ...'), over 27-UI-SPEC.md section 2's 'Reading order: provider picker -> Title -> caption' bullet, which appears to be an internal drafting inconsistency in a still-'pending'/unapproved UI-SPEC doc (2 of 3 mentions agree; the reading-order bullet is the outlier)"
  - "getByLabelText('Description')/('Title') was rejected as the test query -- it matches BOTH the actual form control and the pre-existing section heading (`<section aria-labelledby=\"drill-desc-h\">`), which testing-library's label-text query also resolves via aria-labelledby even though it isn't a form control. Switched to getByRole('textbox', {name}), which correctly scopes to only the input/textarea"
  - "drill-panel-mobile.test.tsx's 2 tests exercising the shared DrillContent compose-on-open effect (Rule 1 auto-fix, out of this plan's declared <files> scope) were updated to reflect the new auto-composed reality, WITHOUT touching drill-panel-mobile.tsx's own JSX/copy -- that file's Title Input + updated caption/placeholder remain Plan 03's explicit scope ('mobile Title Input mirror')"

patterns-established: []

requirements-completed: []  # AID-01 is backend-contract (Plan 01) + desktop-composer (this plan) delivered. Plan 03 (mobile Title Input mirror + "Draft with AI" gap-fill row + exported AnalyzingIndicator) completes the end-to-end feature. Mark AID-01 complete only after Plan 03 ships, per this phase's tracking_tool_caution.

# Metrics
duration: 12min
completed: 2026-08-01
---

# Phase 27 Plan 02: Ticket Draft Composer + Desktop Title Wiring Summary

**A shared, unit-tested `compose-ticket-draft.ts` (deterministic title + labeled multi-section description) wired into `drill-content.tsx`'s desktop ConfirmModal via a `resourceId`-keyed composed-once guard — proven to survive same-vuln re-opens, recompose on vuln switches, and never auto-submit.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-01T15:13:00Z (approx, first file read)
- **Completed:** 2026-08-01T15:25:35Z
- **Tasks:** 2 completed
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `compose-ticket-draft.ts` ships two pure, zero-React/zero-network functions: `composeTicketTitle` (mirrors the backend's own `service.py:202` fallback convention exactly, so an unedited draft matches the server auto-build) and `composeTicketDescription` (a 1-to-4-section labeled plain-text body — Description/Remediation only on a grounded cache hit, Asset context always present with zero AI dependency, Prioritization only when already cached). 16 permutation tests cover every cache-state combination the UI-SPEC's "partial" row enumerates.
- `drill-content.tsx`'s desktop ConfirmModal gained a fully editable Title `Input` (`ticket-title-input`), auto-composed the first time the dialog opens for a given vuln — true even with zero AI key configured, since the title is purely deterministic string interpolation.
- The `composedForId` `useRef<string | null>` guard (compared against `v.id ?? idOrCve`, gated on `confirmOpen`) resolves three discovered edge cases with one mechanism: an analyst's Title/Description edits survive a same-vuln Cancel-then-reopen; a row-switch to a *different* vuln while the panel stays mounted recomposes instead of leaking vuln A's draft onto vuln B (Pitfall 3, proven by a dedicated regression test); and the pre-existing "Copy into ticket description" button no longer prevents the first genuine dialog open from composing the full body (Pitfall 2).
- `fireTicket()` threads `title: title || undefined` into `createTicket.mutateAsync` alongside `description`; `confirmDisabled` remains exactly `!ticketProvider` — no new disable condition, no new effect, no `<form>` — SC3 (never auto-submit) is proven by a negative assertion, not just documented.
- Because the compose-on-open effect lives inside the *shared* `DrillContent` component (not desktop-only JSX), mobile's confirm dialog already auto-composes `title`/`description` too, ahead of Plan 03's own mobile Title Input UI — confirmed by 2 pre-existing mobile tests that needed updating (see Deviations).

## Task Commits

Each task followed the RED -> GREEN TDD cycle, committed atomically:

1. **Task 1: compose-ticket-draft.ts pure module + exhaustive cache-state tests**
   - `5a76c6c` (test — RED, module doesn't exist yet, import fails to resolve)
   - `f6c4bd7` (feat — GREEN, 16/16 tests pass, `tsc` clean, `business_risk` grep == 0)
2. **Task 2: desktop Title field + resourceId-keyed compose-on-open guard + mutation threading**
   - `a792236` (test — RED, 9 new/updated AID-01 assertions fail against the pre-existing `drill-content.tsx`)
   - `5431c49` (feat — GREEN, 21/21 `drill-panel` tests + 874/874 full frontend suite pass, `tsc`/`eslint` clean)

**Plan metadata:** (this commit, docs: complete plan)

_Note: both tasks were declared `tdd="true"`; each ran its own RED-then-GREEN pair rather than the split-task pattern Plan 01 used._

## Files Created/Modified

- `frontend/src/lib/tickets/compose-ticket-draft.ts` — `composeTicketTitle`/`composeTicketDescription` pure functions; `CacheSection` type (`{grounded, summary} | null`).
- `frontend/src/lib/tickets/compose-ticket-draft.test.ts` — 16 permutation tests (all-null, single/double/all-four sections, grounded:false omission, cisaKev/exploitAvailable toggles, affectedProduct null fallback, business_risk never referenced).
- `frontend/src/components/vulnerabilities/drill-content.tsx` — `title`/`setTitle` state, `composedForId` ref, `v`/`cveLabel`/`hostsLine`/`sevLabel` hoisted before the pending/error early returns, 3 `useExplainCache` reads, the compose-on-open effect, `renderConfirm` args extended, `fireTicket()` title threading, desktop ConfirmModal's new caption + Title `Input` block + updated Description label/placeholder.
- `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — 4 pre-existing description tests updated for the new locked label/placeholder/always-composed body; the Pitfall-2 "Copy into ticket description" test now asserts the full body composes unconditionally on first open; 5 new AID-01 tests (deterministic compose, mutation threading, same-vuln edit-survives-reopen, cross-vuln recompose, never-auto-submit negative assertion).
- `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — 2 tests updated (Rule 1 auto-fix) to reflect the shared `DrillContent` compose-on-open effect now populating `title`/`description` on mobile too.

## Decisions Made

- **Caption-above-Title placement:** 27-UI-SPEC.md contains an internal inconsistency — the Copywriting Contract row ("sits once above the Title field") and the Spacing Scale row (`TicketProviderPicker -> caption -> Title field -> ...`) both place the caption *before* the Title Input, while section 2's prose "Reading order" bullet lists Title before caption. Resolved in favor of the two more explicit, position-specific statements (caption first) since the UI-SPEC's own Checker Sign-Off is still unchecked/"pending" — flagged here rather than silently picking one.
- **`getByRole('textbox', {name})` over `getByLabelText`:** discovered mid-implementation that `getByLabelText('Description')` matches both the Textarea AND the pre-existing `<section aria-labelledby="drill-desc-h">` heading (testing-library resolves aria-labelledby associations broadly, not just on form controls). Standardized on `getByRole('textbox', {name})` for both Title and Description lookups across the updated test file.
- **Shared compose-on-open effect intentionally lives in `DrillContent`, not duplicated per-branch:** confirmed by RESEARCH.md's own Pattern 4 note ("mirrored inside drill-panel-mobile.tsx's renderConfirm closure over the same DrillContent instance — no separate state needed there"). This is why mobile's tests needed updating even though this plan's own `<files>` scope never lists `drill-panel-mobile.tsx`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated 2 `drill-panel-mobile.test.tsx` tests broken by the shared `DrillContent` compose-on-open effect**

- **Found during:** Task 2 (full-suite verification after the desktop implementation went GREEN)
- **Issue:** `drill-panel-mobile.tsx` renders `DrillContent` directly (never a separate instance), so the new `title`/`description` compose-on-open effect populates both fields there too — even though `drill-panel-mobile.tsx`'s own JSX (Title Input UI, updated caption/placeholder) is explicitly Plan 03's scope ("mobile Title Input mirror"). Two pre-existing tests asserted stale premises: "renders the description Textarea ... starting empty" and "leaving the mobile textarea blank threads description: undefined."
- **Fix:** Updated both tests' assertions to match the new reality (auto-composed on open; an explicit clear-then-confirm proves the `undefined`-not-empty-string contract still holds) — without touching `drill-panel-mobile.tsx`'s own production JSX/copy, which stays exactly as Phase 25 left it, pending Plan 03.
- **Files modified:** `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx`
- **Verification:** Full frontend suite 874/874 green (was 872/874 before this fix); `tsc --noEmit` and `eslint` clean.
- **Committed in:** `5431c49` (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug/regression — test assertions broken by an intentionally-shared component effect, not a mobile UI change)
**Impact on plan:** No scope creep — `drill-panel-mobile.tsx`'s own JSX/copy (Title Input, updated caption/placeholder) remains untouched, preserved for Plan 03 exactly as planned. Only the 2 test *assertions* whose premises this plan's shared-state change made false were updated.

## Issues Encountered

None beyond the deviation above — both TDD cycles (compose module, desktop wiring) went RED then GREEN on the first implementation pass with no debugging iterations required.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The shared `compose-ticket-draft.ts` module and the `resourceId`-keyed composed-once guard pattern are proven end-to-end on desktop and are directly reusable by Plan 03's mobile wiring (`drill-panel-mobile.tsx renderConfirm` already receives `title`/`onTitleChange` via the same `DrillContent` args — Plan 03 only needs to add the mobile Title `Input` JSX + the "Draft with AI" gap-fill row, not any new state/effect logic).
- `AnalyzingIndicator` in `ai-explanation-section.tsx` is still private (unexported) — Plan 03 must add the one-line `export` before the gap-fill row can reuse it (RESEARCH Pitfall 4, untouched by this plan).
- **AID-01 remains NOT complete** — Plan 03 (mobile mirror + gap-fill row) completes the end-to-end feature. Per this phase's tracking guidance, do not flip the phase checkbox or mark AID-01 satisfied until Plan 03 ships.
- No blockers.

## TDD Gate Compliance

Both tasks are marked `tdd="true"` and each ran its own genuine RED-then-GREEN pair (unlike Plan 01's split-task structure):
- Task 1: `test` commit (`5a76c6c`, RED — import fails, module doesn't exist) -> `feat` commit (`f6c4bd7`, GREEN — 16/16 pass).
- Task 2: `test` commit (`a792236`, RED — 9 failures, all new/updated AID-01 assertions) -> `feat` commit (`5431c49`, GREEN — 21/21 `drill-panel` + 874/874 full suite pass).
No REFACTOR commit was needed for either task — both GREEN commits were correct on first implementation pass.

## Self-Check: PASSED

- `frontend/src/lib/tickets/compose-ticket-draft.ts` — FOUND, exports `composeTicketTitle`/`composeTicketDescription`/`CacheSection`.
- `frontend/src/lib/tickets/compose-ticket-draft.test.ts` — FOUND, 16 tests, all passing.
- `frontend/src/components/vulnerabilities/drill-content.tsx` — FOUND, contains `composedForId`, `ticket-title-input`, `title: title || undefined` (count 1).
- `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — FOUND, 21 tests, all passing (12 pre-existing + 9 new/updated).
- `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — FOUND, 2 tests updated, full mobile suite passing.
- Commits `5a76c6c`, `f6c4bd7`, `a792236`, `5431c49` — all FOUND in `git log --oneline`.

---
*Phase: 27-ticket-auto-drafting*
*Completed: 2026-08-01*
