---
phase: 19-add-connector-wizard
plan: 02
subsystem: ui
tags: [react, tanstack-query, tailwind, connectors, wizard, design-tokens]

# Dependency graph
requires:
  - phase: 19-add-connector-wizard (plan 00, not yet executed at run time)
    provides: "WIZARD_COPY + confirm-step.test.tsx RED scaffold — added inline here as a blocking-dependency fix (see Deviations)"
provides:
  - "ConfirmStep component: review screen (provider, connection ✓, permissions[] scope+purpose, sync interval, gradient Add-connector CTA)"
  - "Edit-mode ConnectorForm test-success block reconciled to the green design-system success token"
affects: [19-01, 19-03, 19-04, add-connector-wizard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wizard confirm-step review pattern: labeled surface-2 rows (Provider/Connection/Required access/Sync interval), single gradient CTA reserved for the primary forward action"
    - "permissions[] scope rendered font-mono + purpose as text-xs caption sub-line, empty-permissions renders explicit valid-state copy (not an error)"

key-files:
  created:
    - frontend/src/components/connectors/wizard/confirm-step.tsx
    - frontend/src/components/connectors/wizard/confirm-step.test.tsx
  modified:
    - frontend/src/components/connectors/microcopy.ts
    - frontend/src/components/connectors/connector-form.tsx

key-decisions:
  - "19-00 (this plan's declared dependency) had not been executed in this worktree at run time; added only the minimal prerequisite slice it owns (WIZARD_COPY export + confirm-step.test.tsx RED scaffold) rather than its full scope (useWizardState, credentials-step, add-connector-wizard, a11y test all remain out of scope for 19-02)"
  - "ConfirmStep is a presentational component (props-driven), does not consume useWizardState directly — no coupling to the not-yet-built wizard state hook"
  - "Edit-mode ConnectorForm success block color fixed to --color-success (green) to match the wizard and design system; failure block and D-11 edit/sentinel path left untouched"

patterns-established:
  - "Confirm/review step pattern for multi-step wizards: bordered surface-2 rows per data category, one gradient CTA, credential values never rendered (only permissions/labels)"

requirements-completed: [UX-D-02-04, UX-D-02-05]

# Metrics
duration: 25min
completed: 2026-07-20
---

# Phase 19 Plan 02: ConfirmStep Review Screen Summary

**ConfirmStep review screen (provider + ✓ connection + permissions[] scope/purpose + sync interval) submitting POST /connectors via useCreateConnector, plus a lavender→green success-color reconciliation in the edit-mode ConnectorForm.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-20T08:31:00Z
- **Completed:** 2026-07-20T08:56:32Z
- **Tasks:** 2 completed (+ 1 inline blocking-dependency fix)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- Built `ConfirmStep`, the wizard's step-4 payoff surface: renders provider name, `✓ Connection verified`, the connector type's `permissions[]` (scope in mono + purpose caption, or the valid "No special scopes required." empty state), and the sync interval, then submits `POST /connectors` via `useCreateConnector().mutate` with the add-path credentials + selected sync interval
- Reconciled the pre-existing color drift in the edit-mode `ConnectorForm` test-success block (lavender `severity-low` → green `--color-success`), so add (wizard) and edit paths now agree on the design-system success token
- Unblocked plan execution by adding the two artifacts 19-02 depends on from 19-00 (which had not executed): `WIZARD_COPY` in `microcopy.ts` and the `confirm-step.test.tsx` RED scaffold — scoped strictly to what 19-02 needs, not the rest of 19-00

## Task Commits

Each task was committed atomically:

1. **Task 1: ConfirmStep — review screen + required scopes + Add connector CTA** - `52b46e8` (feat)
2. **Task 2: Reconcile the edit-mode ConnectorForm test-success color** - `9ea7e20` (fix)

_Note: Task 1's commit also includes the WIZARD_COPY addition and confirm-step RED scaffold — see Deviations below for why these were bundled in._

## Files Created/Modified
- `frontend/src/components/connectors/wizard/confirm-step.tsx` - ConfirmStep component: 4 review rows + gradient Add-connector CTA + submit-error block
- `frontend/src/components/connectors/wizard/confirm-step.test.tsx` - RED→GREEN test scaffold (3 tests: full render, empty-permissions, submit call shape)
- `frontend/src/components/connectors/microcopy.ts` - added `WIZARD_COPY` export (wizard copy strings, verbatim from UI-SPEC)
- `frontend/src/components/connectors/connector-form.tsx` - test-success block color reconciled to `--color-success`

## Decisions Made
- Kept `ConfirmStep` purely props-driven (no `useWizardState` dependency) so it has zero coupling to the not-yet-built wizard state hook from 19-00 — it can be wired into `AddConnectorWizard` later without rework
- Followed the plan's exact markup reuse instructions: gradient CTA markup and submit-error block mirror `connector-form.tsx` lines 292-297/326-340 verbatim (button structure, `Loader2` spinner, disabled/pending state)
- Left `FORM_COPY` untouched per D-11 — `WIZARD_COPY` is additive, not a replacement

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added prerequisite `WIZARD_COPY` export and `confirm-step.test.tsx` RED scaffold (19-00 not yet executed)**
- **Found during:** Task 1 (ConfirmStep implementation)
- **Issue:** Plan 19-02 declares `depends_on: [19-00]`, and its Task 1 `read_first` references `confirm-step.test.tsx` as an existing RED scaffold and `WIZARD_COPY` as an existing interface — neither existed because 19-00 (Wave 0) had not been executed in this worktree. Without them, Task 1 could not proceed at all (no test target, no copy constants to import).
- **Fix:** Added only the minimal slice of 19-00 that 19-02 actually needs: (a) the `WIZARD_COPY` const in `microcopy.ts` with the exact strings from 19-UI-SPEC.md §Copywriting Contract, and (b) `confirm-step.test.tsx` mirroring the 19-00-PLAN.md Task 3 spec (Test 1: full render with scope+purpose, Test 2: empty-permissions valid state, Test 3: `Add connector` click → `useCreateConnector().mutate` with uppercased type). Did NOT build `use-wizard-state.ts`, `credentials-step.test.tsx`, `add-connector-wizard.test.tsx`, or the a11y test — those remain 19-00's scope and are unaffected/unblocked by this change.
- **Files modified:** `frontend/src/components/connectors/microcopy.ts`, `frontend/src/components/connectors/wizard/confirm-step.test.tsx`
- **Verification:** Ran the test file before implementation to confirm RED (`Cannot find module "./confirm-step"`), then GREEN after `confirm-step.tsx` was implemented (3/3 tests passing); `npx tsc --noEmit` clean for both touched files.
- **Committed in:** `52b46e8` (Task 1 commit)

**2. [Rule 1 - Bug] Worktree branch was on a stale base predating Phases 16-18**
- **Found during:** Startup `<worktree_branch_check>` step
- **Issue:** `git merge-base HEAD <expected-base>` returned an ancestor commit (`7c9063a`, pre-Phase-16) instead of the expected base (`9979aaa`), matching the documented GSD worktree stale-base hazard. The instructed `git reset --soft 9979aaa...` staged what would have been a revert of ~90 commits of Phase 16-18 work plus phase-19 planning docs (visible as `M`/`D` entries in `git status` for globals.css, sunset.css, PROJECT.md, ROADMAP.md, and deleted phase-16/17 SUMMARY/PLAN files).
- **Fix:** Did NOT commit the staged reversion. Ran `git reset --hard 9979aaa72598aa326296862410aae40bcab9e751` instead (permitted only in this startup step per the destructive-git-prohibition carve-out) to align the worktree cleanly with the correct base before any task work began.
- **Files modified:** none (working tree reset, no commit)
- **Verification:** Post-reset `git status --short` clean; `git log --oneline -5` showed the expected Phase-19 planning commit history with no stray staged changes.
- **Committed in:** N/A (pre-work correction, not part of any task commit)

---

**Total deviations:** 2 auto-fixed (1 blocking-dependency fix, 1 startup hazard correction)
**Impact on plan:** Both were necessary preconditions for correct execution. The WIZARD_COPY/RED-scaffold addition was scoped tightly to avoid absorbing 19-00's full workload; the stale-base correction prevented silently reverting prior-phase work (the exact hazard logged in project memory).

## Issues Encountered
- `frontend/node_modules` is gitignored and not present in the worktree (documented worktree/frontend incompatibility). Symlinked `frontend/node_modules` → the main checkout's `frontend/node_modules` to run `npm test`/`tsc` locally; this symlink is itself gitignored and was not committed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `ConfirmStep` is ready to be wired into `AddConnectorWizard` (19-01/19-03) once `useWizardState` (19-00) lands — its props contract (`providerName`, `connectorType`, `permissions`, `syncInterval`, `credentials`, `onSuccess`, `headingRef`, `headingId`) is stable and requires no changes to consume wizard state.
- 19-00 still needs to be executed for `use-wizard-state.ts`, `credentials-step.test.tsx`, `add-connector-wizard.test.tsx`, and `add-connector-wizard.a11y.test.tsx` — these were deliberately NOT built here (out of 19-02's scope) and remain blockers for 19-01/19-03/19-04 unless already in progress elsewhere.
- Both add (wizard, via ConfirmStep) and edit (ConnectorForm) paths now render test-success in the same green token — no remaining lavender/green split on the connectors route.

---
*Phase: 19-add-connector-wizard*
*Completed: 2026-07-20*

## Self-Check: PASSED

All created files verified present on disk; both task commits (`52b46e8`, `9ea7e20`) verified present in git log.
