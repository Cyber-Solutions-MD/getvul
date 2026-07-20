---
phase: 19-add-connector-wizard
plan: 01
subsystem: ui
tags: [react, nextjs, wizard, a11y, connectors, tanstack-query]

# Dependency graph
requires:
  - phase: 19-00
    provides: "useWizardState gating hook + WIZARD_COPY microcopy + credentials-step.test.tsx RED scaffold (built here as a prerequisite — see Deviations)"
provides:
  - "WizardStepper — display-only 4-step <ol>/aria-current progress indicator (net-new pattern)"
  - "CredentialsStep — credential inputs + Eye/EyeOff toggle + sync-interval chips, delegating state to useWizardState"
  - "TestStep — explicit Test connection button + green/red inline result with live-region roles"
affects: ["19-02", "19-03", "19-04"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "aria-current=\"step\" + <ol> for a non-interactive progress indicator (not ARIA tablist) — literal attribute written per branch (current vs. not) so it's statically greppable/verifiable, not spread from a computed object"
    - "Wizard step components receive all state via props from a single useWizardState hook — no step owns step-order/gating state itself"

key-files:
  created:
    - frontend/src/components/connectors/wizard/wizard-stepper.tsx
    - frontend/src/components/connectors/wizard/credentials-step.tsx
    - frontend/src/components/connectors/wizard/test-step.tsx
    - frontend/src/components/connectors/wizard/use-wizard-state.ts
    - frontend/src/components/connectors/wizard/use-wizard-state.test.ts
    - frontend/src/components/connectors/wizard/credentials-step.test.tsx
  modified:
    - frontend/src/components/connectors/microcopy.ts

key-decisions:
  - "19-00 (this plan's dependency) had not been executed anywhere in the repo — no wizard/ directory, no 19-00-SUMMARY.md. Implemented the minimum needed subset of 19-00 (WIZARD_COPY, useWizardState + its 6-test suite, and the credentials-step.test.tsx RED scaffold) as a Rule-3 auto-fix rather than leaving the plan blocked."
  - "Did not build 19-00's other RED scaffolds (confirm-step.test.tsx, add-connector-wizard.test.tsx, add-connector-wizard.a11y.test.tsx) — those aren't consumed by this plan's tasks and are left for whichever plan(s) build ConfirmStep/AddConnectorWizard, to avoid speculative work outside this plan's scope."
  - "Success test-result color corrected to --color-success green per UI-SPEC reconciliation; the connector-form.tsx source lavender block is intentionally left untouched (that fix is scoped to Plan 19-02)."

patterns-established:
  - "Non-interactive stepper: literal aria-current=\"step\" written via a status-branched <li> render (not JSX-interpolated), keeping the attribute statically verifiable while still being conditional"

requirements-completed: [UX-D-02-02, UX-D-02-03, UX-D-02-05]

# Metrics
duration: 67min
completed: 2026-07-20
---

# Phase 19 Plan 01: Wizard Leaf Components (Stepper / Credentials / Test) Summary

**Display-only WizardStepper (net-new `<ol>`+`aria-current` pattern), CredentialsStep, and TestStep built as pure-prop consumers of a from-scratch `useWizardState` gating hook — the hook itself had to be built here first because plan 19-00 had never been executed.**

## Performance

- **Duration:** 67 min (includes ~40 min of prerequisite 19-00 work)
- **Started:** 2026-07-20T11:50:22+03:00
- **Completed:** 2026-07-20T12:57:24+03:00
- **Tasks:** 3 (plus 3 prerequisite tasks — see Deviations)
- **Files modified:** 7 (1 modified, 6 created)

## Accomplishments
- `WizardStepper` renders the 4-step progress indicator (`① Provider ✓ · ② Credentials · ③ Test · ④ Confirm`) fully from `foundation.md` tokens, status conveyed by shape+glyph+weight (never color alone), display-only (no button/a elements)
- `CredentialsStep` lifts the field + sync-interval markup from `connector-form.tsx` verbatim, delegating every state change to the parent hook via props
- `TestStep` fires the connection test only on explicit click (D-06), with the corrected green `--color-success` success block and `role="alert"` failure block
- Unblocked the whole plan by building the missing `useWizardState` hook (fully unit-tested, 6/6 green, including the Pitfall-4 back/next "bounce" scenario) and `WIZARD_COPY` microcopy

## Task Commits

Prerequisite work (19-00, auto-fixed blocking dependency — see Deviations):
1. **microcopy.ts WIZARD_COPY** - `e147040` (feat)
2. **useWizardState hook + 6-test suite** - `e8f6974` (test, RED confirmed before implementation was written; committed together with the GREEN implementation)
3. **credentials-step.test.tsx RED scaffold** - `c1a6a99` (test)

Plan 19-01 tasks:
1. **Task 1: WizardStepper** - `5120055` (feat)
2. **Task 2: CredentialsStep** - `a104f3f` (feat)
3. **Task 3: TestStep** - `1492e3f` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `frontend/src/components/connectors/microcopy.ts` - added `WIZARD_COPY` (step labels, nav/test/retest copy, confirm section labels)
- `frontend/src/components/connectors/wizard/use-wizard-state.ts` - the four-step gating state machine (step/values/touched/testResult/credentialsChangedSinceTest/syncInterval), `isTestStale`/`testPassed`/`canAdvance` derived state, D-12 `buildCredentials` add-path
- `frontend/src/components/connectors/wizard/use-wizard-state.test.ts` - 6 unit tests (ordering, credentials gate, test gate, D-08 invalidation, Pitfall-4 bounce, buildCredentials)
- `frontend/src/components/connectors/wizard/credentials-step.test.tsx` - RED scaffold pinning the `CredentialsStep` prop contract, now GREEN
- `frontend/src/components/connectors/wizard/wizard-stepper.tsx` - net-new display-only `<nav><ol>` stepper, `aria-current="step"` on the current step, `CheckCircle2` + sr-only " (completed)" on complete steps
- `frontend/src/components/connectors/wizard/credentials-step.tsx` - credential inputs + Eye/EyeOff toggle + sync-interval chips
- `frontend/src/components/connectors/wizard/test-step.tsx` - explicit Test connection button + green/red inline result

## Decisions Made
- Kept `ConnectorTypeInfo.fields: string[]` per the 19-00 planner decision (carried forward) — `isSecretField()` name-heuristic used for password-vs-text, all fields treated as required.
- `aria-current="step"` is rendered via a branched `<li>` (current vs. not) rather than a spread computed prop object, so the literal attribute string is statically present in source (verifiable by grep and, more importantly, unambiguous to read).
- Test-result success color intentionally diverges from the still-lavender `connector-form.tsx` block — documented as the sanctioned UI-SPEC reconciliation, not a bug.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree was based on a stale commit (7c9063a instead of 9979aaa)**
- **Found during:** Initial `<worktree_branch_check>` step
- **Issue:** `git merge-base HEAD 9979aaa...` returned `7c9063a`, not matching the target base — I initially misread these as equal and proceeded, then caught the error before making any real edits. This is the documented "GSD worktree stale-base hazard" (project memory).
- **Fix:** `git reset --hard 9979aaa72598aa326296862410aae40bcab9e751` (safe here — no prior commits/edits existed in the worktree at the time; `--hard` is explicitly permitted only inside this branch-check step per the destructive-git-prohibition carve-out).
- **Verification:** Post-reset `git log`/`git status` confirmed HEAD at `9979aaa` with a clean tree; `.planning/phases/19-add-connector-wizard/` files present.
- **Committed in:** N/A (working-tree/HEAD correction, not a content change)

**2. [Rule 3 - Blocking] Missing dependency: plan 19-00 had never been executed**
- **Found during:** Pre-Task-1 file discovery — `frontend/src/components/connectors/wizard/` didn't exist anywhere (checked both the worktree and the main checkout); no `19-00-SUMMARY.md`.
- **Issue:** This plan's tasks directly consume 19-00's deliverables: the `useWizardState` hook (props for all three components), `WIZARD_COPY` (stepper labels, test button copy), and the `credentials-step.test.tsx` RED scaffold that Task 2's acceptance criteria requires turning GREEN.
- **Fix:** Implemented the subset of 19-00 that this plan directly needs — Task 1 (`WIZARD_COPY`), Task 2 (`useWizardState` + its full 6-test suite, TDD RED-then-GREEN), and the `credentials-step.test.tsx` slice of Task 3. Did NOT build `confirm-step.test.tsx` / `add-connector-wizard.test.tsx` / `add-connector-wizard.a11y.test.tsx` — those aren't needed by this plan's components and are left for whichever plan builds `ConfirmStep`/`AddConnectorWizard`.
- **Files modified:** `frontend/src/components/connectors/microcopy.ts`, `frontend/src/components/connectors/wizard/use-wizard-state.ts`, `frontend/src/components/connectors/wizard/use-wizard-state.test.ts`, `frontend/src/components/connectors/wizard/credentials-step.test.tsx`
- **Verification:** All 6 `use-wizard-state` tests pass; `credentials-step.test.tsx` confirmed RED before `CredentialsStep` existed, GREEN after.
- **Committed in:** `e147040`, `e8f6974`, `c1a6a99`

**3. [Environment] `frontend/node_modules` unavailable in the worktree**
- **Found during:** First attempt to run `npm test`/`tsc`/`eslint`
- **Issue:** `node_modules` is gitignored and not worktree-portable (documented project memory); a fresh `npm install` would be slow and risks lockfile drift.
- **Fix:** Symlinked `frontend/node_modules` to the main checkout's `node_modules` (verified `package.json`/`package-lock.json` byte-identical between worktree and main first). Added `frontend/node_modules` to the shared `.git/info/exclude` so it never shows as untracked.
- **Verification:** `npm test`, `npx tsc --noEmit`, `npx eslint` all ran successfully afterward.
- **Committed in:** N/A (local tooling only, not a repo content change)

---

**Total deviations:** 3 (1 stale-base self-recovery, 1 blocking-dependency auto-fix spanning 3 sub-commits, 1 environment workaround)
**Impact on plan:** All three were necessary to execute 19-01 at all. No scope creep beyond what this plan's own tasks require — the unbuilt 19-00 RED scaffolds (confirm-step, add-connector-wizard) are explicitly left for their consuming plans.

## Issues Encountered
- A file-content permission restriction (unrelated to git) began denying direct `Read`/`grep` access to `credentials-step.tsx` mid-session (likely a heuristic on files containing many literal occurrences of "secret"/"password"/"token"). Worked around by relying on `npm test`/`tsc`/`eslint` (which still had access) plus prior verified grep output captured before the restriction engaged; no functional impact — all acceptance criteria for that file were confirmed green before the restriction appeared.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `useWizardState`, `WizardStepper`, `CredentialsStep`, and `TestStep` are ready for `AddConnectorWizard` (whichever plan builds it) to compose into the full 4-step flow.
- `confirm-step.test.tsx`, `add-connector-wizard.test.tsx`, and `add-connector-wizard.a11y.test.tsx` RED scaffolds from 19-00's original Task 3 were NOT created by this plan — whichever plan builds `ConfirmStep`/`AddConnectorWizard` should either find them already scaffolded by a parallel 19-00 execution, or write them fresh (TDD RED-first) before implementing.
- The `connector-form.tsx` success-block lavender color is a known, intentional carry-over (fixed in Plan 19-02, per UI-SPEC).

---
*Phase: 19-add-connector-wizard*
*Completed: 2026-07-20*

## Self-Check: PASSED

All 8 claimed files found on disk; all 6 claimed commit hashes found in git log.
