---
phase: 19-add-connector-wizard
plan: 00
subsystem: ui
tags: [react, vitest, vitest-axe, state-machine, connectors, wizard]

# Dependency graph
requires: []
provides:
  - WIZARD_COPY microcopy contract (frontend/src/components/connectors/microcopy.ts)
  - useWizardState — the four-step gating state machine hook, fully unit-tested
  - 4 RED test scaffolds (credentials-step, confirm-step, add-connector-wizard,
    add-connector-wizard.a11y) as concrete GREEN targets for Waves 1-2
affects: [19-01, 19-02, 19-03, 19-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "useReducer-based dialog-scoped wizard state (step/values/touched/testResult/credentialsChangedSinceTest/syncInterval)"
    - "Derived-state gating: canAdvance computed per-step from raw state, never stored directly"
    - "D-08 tamper-evident re-test invalidation via credentialsChangedSinceTest flag, distinct from testResult===null"

key-files:
  created:
    - frontend/src/components/connectors/wizard/use-wizard-state.ts
    - frontend/src/components/connectors/wizard/use-wizard-state.test.ts
    - frontend/src/components/connectors/wizard/credentials-step.test.tsx
    - frontend/src/components/connectors/wizard/confirm-step.test.tsx
    - frontend/src/components/connectors/wizard/add-connector-wizard.test.tsx
    - frontend/src/components/connectors/wizard/add-connector-wizard.a11y.test.tsx
  modified:
    - frontend/src/components/connectors/microcopy.ts

key-decisions:
  - "Kept ConnectorTypeInfo.fields as string[] (no backend change) per PLANNER DECISION in 19-00-PLAN.md — all fields treated as required, matching today's 100%-required invariant (RESEARCH Pitfall 1)"
  - "isTestStale modeled as a derived boolean (testResult !== null && credentialsChangedSinceTest), not a reducer-persisted field, so it can never drift from the raw state"
  - "Plain useReducer, no form library — matches project convention and RESEARCH's explicit rejection of react-hook-form/formik"

patterns-established:
  - "Pitfall-4 bounce-scenario unit test (Test E): test-pass -> confirm -> back -> back -> edit -> re-test-pass -> advance twice -> isTestStale===false — proves the D-08 gate survives Back/Next churn without false-positive staleness"

requirements-completed: [UX-D-02-01, UX-D-02-02]

# Metrics
duration: 8min
completed: 2026-07-20
---

# Phase 19 Plan 00: Wizard Foundations (Copy + State Machine + RED Scaffolds) Summary

**Implemented and fully unit-tested `useWizardState` — the single-source-of-truth four-step gating state machine (credentials → test → confirm) — plus the wizard's verbatim copy contract and four RED test scaffolds that give Waves 1-2 concrete GREEN targets.**

## Performance

- **Duration:** 8 min (11:50–11:58 UTC+3)
- **Started:** 2026-07-20T08:50:22Z
- **Completed:** 2026-07-20T08:57:47Z
- **Tasks:** 3/3 completed
- **Files modified:** 7 (1 modified, 6 created)

## Accomplishments
- `useWizardState` fully implemented and green across 6 unit tests (A–F), including the Pitfall-4 Back/Next bounce scenario that proves D-08 re-test invalidation survives step churn without false positives
- `WIZARD_COPY` extends `microcopy.ts` with every UI-SPEC copywriting-contract string verbatim (stepper labels, dialog heading builder, gating hints, confirm section labels) — `FORM_COPY` untouched for the edit path
- Four RED test scaffolds created and confirmed failing (module-not-found / TS2307) against not-yet-built `credentials-step`, `confirm-step`, and `add-connector-wizard` components — pinning UX-D-02-03/04/01/05/06 assertions for Waves 1–2

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend microcopy.ts with the wizard copy contract** - `bc3ff99` (feat)
2. **Task 2 (TDD): Implement useWizardState** - `74ffcaa` (test, RED) → `4807997` (feat, GREEN)
3. **Task 3: RED test scaffolds for step + wizard components** - `c099dbb` (test)

_No refactor commit was needed — the GREEN implementation required no cleanup pass._

## TDD Gate Compliance

- RED gate: `74ffcaa test(19-00): add failing test for useWizardState gating machine` — confirmed failing (`Cannot find module './use-wizard-state'`) before implementation existed.
- GREEN gate: `4807997 feat(19-00): implement useWizardState — four-step gating state machine` — all 6 tests (A–F) pass.
- Gate sequence verified via `git log --oneline`: test commit precedes feat commit. Compliant.

## Files Created/Modified
- `frontend/src/components/connectors/microcopy.ts` - Added `WIZARD_COPY` export (stepper labels, dialog heading builder, next/back/cancel/add/test labels, gate hints, confirm section labels, no-scopes copy)
- `frontend/src/components/connectors/wizard/use-wizard-state.ts` - `useWizardState(fields)` hook: `useReducer`-based state (step/values/touched/testResult/credentialsChangedSinceTest/syncInterval), derived `allFieldsFilled`/`isTestStale`/`testPassed`/`canAdvance`, `updateField`/`setTestResult`/`setSyncInterval`/`advance`/`back`/`buildCredentials`
- `frontend/src/components/connectors/wizard/use-wizard-state.test.ts` - 6 unit tests (A–F): step ordering, credentials gate, test gate, D-08 first-keystroke invalidation, Pitfall-4 bounce, D-12 buildCredentials add-path
- `frontend/src/components/connectors/wizard/credentials-step.test.tsx` - RED scaffold for `CredentialsStep` (UX-D-02-03): field-count, secret-field password+Eye-toggle, onFieldChange wiring, values-prop reflection
- `frontend/src/components/connectors/wizard/confirm-step.test.tsx` - RED scaffold for `ConfirmStep` (UX-D-02-04): scope+purpose render, empty-permissions copy, Add-connector → `useCreateConnector().mutate` with uppercased `connector_type` + `sync_interval_minutes`
- `frontend/src/components/connectors/wizard/add-connector-wizard.test.tsx` - RED scaffold for `AddConnectorWizard` (UX-D-02-01, UX-D-02-05): 4-label stepper + credentials-first render, D-06 no-auto-fire test gate, only-3-documented-hooks check
- `frontend/src/components/connectors/wizard/add-connector-wizard.a11y.test.tsx` - RED scaffold, component-level `vitest-axe` sweep mirroring `dashboard.a11y.test.tsx`

## Decisions Made
- Kept `ConnectorTypeInfo.fields: string[]` (no backend change), per the plan's PLANNER DECISION — documented with a code comment in `use-wizard-state.ts` referencing 19-RESEARCH Pitfall 1
- `isTestStale` computed as a derived value (`testResult !== null && credentialsChangedSinceTest`) rather than stored, so it can never desync from the underlying state on any code path
- No form library introduced (plain `useReducer`), consistent with `connector-form.tsx` and the RESEARCH's explicit rejection of react-hook-form/Formik

## Deviations from Plan

None — plan executed exactly as written. The `useWizardState` implementation matches the exported type contract in the plan verbatim (same field names, same function signatures).

## Environment Note (non-blocking, worktree-local)

The worktree's `frontend/node_modules` was absent (not checked out — correctly gitignored). Since the worktree's `package-lock.json` is byte-identical to the main repo's, a symlink (`frontend/node_modules -> /Users/chemencedji/Desktop/getvul/frontend/node_modules`) was created to run tests without a full `npm install`. This symlink is untracked (gitignored) and does not appear in any commit — it is local-only tooling convenience for this worktree session.

## Self-Check: PASSED

- FOUND: frontend/src/components/connectors/microcopy.ts
- FOUND: frontend/src/components/connectors/wizard/use-wizard-state.ts
- FOUND: frontend/src/components/connectors/wizard/use-wizard-state.test.ts
- FOUND: frontend/src/components/connectors/wizard/credentials-step.test.tsx
- FOUND: frontend/src/components/connectors/wizard/confirm-step.test.tsx
- FOUND: frontend/src/components/connectors/wizard/add-connector-wizard.test.tsx
- FOUND: frontend/src/components/connectors/wizard/add-connector-wizard.a11y.test.tsx
- FOUND commit: bc3ff99
- FOUND commit: 74ffcaa
- FOUND commit: 4807997
- FOUND commit: c099dbb
