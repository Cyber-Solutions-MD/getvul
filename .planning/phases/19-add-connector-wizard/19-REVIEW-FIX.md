---
phase: 19-add-connector-wizard
fixed_at: 2026-07-20T15:11:00Z
review_path: .planning/phases/19-add-connector-wizard/19-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 19: Code Review Fix Report

**Fixed at:** 2026-07-20T15:11:00Z
**Source review:** .planning/phases/19-add-connector-wizard/19-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03; the 3 Info items were out of scope)
- Fixed: 3
- Skipped: 0

## Verification evidence

All fixes were applied in an isolated git worktree, verified per-fix, and the
full suite was run after the ConfirmModal / ResponsiveDialog change.

- `npx tsc --noEmit` → **exit 0** (project-wide clean, run after WR-02 and again after WR-01)
- `npx vitest run src/components/connectors/ src/components/ui/responsive-dialog.test.tsx src/app/(authed)/dashboard/connectors/` → **11 files, 45 tests passed**
- `npx vitest run` (full suite, because ConfirmModal + responsive-dialog were touched) → **124 files, 723 tests passed**
  - Baseline was 722/722; the +1 is the new `Test B2 (WR-03)` case. No regressions.
  - Note: the `HTMLCanvasElement.prototype.getContext` line emitted by axe-core under jsdom is a benign log, not a test failure — all suites report passed.

## Fixed Issues

### WR-03: Credentials gate is vacuously true when `fields` is empty

**Files modified:** `frontend/src/components/connectors/wizard/use-wizard-state.ts`, `frontend/src/components/connectors/wizard/use-wizard-state.test.ts`
**Commit:** 0cbe631
**Applied fix:** Changed the `credentials` case in `canAdvanceFrom` from
`fields.every(...)` to `fields.length > 0 && fields.every(...)`, closing the
`[].every() === true` hole where a wizard mounted before `useConnectorTypes()`
resolves (`fields === []`) would enable Next with zero inputs and let the user
advance / submit empty credentials. Added `Test B2` asserting `canAdvance` is
`false` when `useWizardState([])` is rendered with no fields.

### WR-02: Credentials step gives screen-reader users no "why" for the disabled Next button

**Files modified:** `frontend/src/components/connectors/microcopy.ts`, `frontend/src/components/connectors/wizard/add-connector-wizard.tsx`, `frontend/src/components/connectors/wizard/credentials-step.tsx`
**Commit:** cb9025a
**Applied fix:** (1) Added `aria-required="true"` to the credential `<input>`s in
`credentials-step.tsx` so assistive tech announces the fields are mandatory.
(2) Added `WIZARD_COPY.credentialsGateHint = 'Fill every field to continue.'`.
(3) Restructured the hint logic in `add-connector-wizard.tsx` so the
credentials step now populates `hintText` (`credentialsGateHint`) when the gate
is closed — previously the `if (step !== 'credentials')` guard left the
`aria-describedby` target an empty paragraph on step 2. Test-step / re-test
hint priority (`retestHint` > `testGateHint`) is preserved for the other steps.
The `credentials-step.test.tsx` assertions did not pin input attributes, so no
test change was needed; all connector tests stay green.

### WR-01: Wizard dialog has no desktop focus trap; Esc breaks once focus escapes

**Files modified:** `frontend/src/components/ui/responsive-dialog.tsx`, `frontend/src/components/ui/ConfirmModal.tsx`
**Commit:** 4473b9d
**Applied fix:** Chose option (a) from the fix guidance — made `ResponsiveDialog`
self-sufficient rather than depending on the caller. Added a `panelRef` on the
desktop `role="dialog"` panel and a document-level `keydown` effect (guarded to
desktop + `open`) that (i) closes on `Escape` via `onOpenChange(false)` so Esc
survives focus leaving the overlay, and (ii) runs `trapTabKey(getFocusable(panelRef))`
on `Tab` to contain focus. Removed the old backdrop-only `onKeyDown` Esc. To
avoid a double Esc (calling `onCancel` twice) and a double Tab trap on the same
modal, removed `ConfirmModal`'s now-redundant Esc + `trapTabKey` effect and its
unused `panelRef` / `focus-trap` imports; `ConfirmModal` keeps only its
confirm-button initial-focus effect. All 5 `ConfirmModal` call sites use the
unchanged public API. Verified the full 723-test suite (including
`responsive-dialog.test.tsx`, the settings-page ConfirmModal test, and
drill-panel-mobile) stays green.

**Human verification recommended:** the fix is proven at the unit level (Esc via
bubbling to the document listener, tsc, full suite), but jsdom cannot exercise
real browser Tab-focus containment, and the axe e2e sweep does not test focus
containment (per the review). A manual desktop keyboard pass through the
connectors add/edit dialog (Tab wrapping at first/last control; Esc after focus
has moved) is advised before final sign-off.

---

_Fixed: 2026-07-20T15:11:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
