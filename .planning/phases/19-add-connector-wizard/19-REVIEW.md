---
phase: 19-add-connector-wizard
reviewed: 2026-07-20T11:58:12Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - frontend/src/components/connectors/wizard/use-wizard-state.ts
  - frontend/src/components/connectors/wizard/add-connector-wizard.tsx
  - frontend/src/components/connectors/wizard/wizard-stepper.tsx
  - frontend/src/components/connectors/wizard/credentials-step.tsx
  - frontend/src/components/connectors/wizard/test-step.tsx
  - frontend/src/components/connectors/wizard/confirm-step.tsx
  - frontend/src/components/connectors/microcopy.ts
  - frontend/src/components/connectors/connector-form.tsx
  - frontend/src/components/ui/responsive-dialog.tsx
  - frontend/src/app/(authed)/dashboard/connectors/page.tsx
  - frontend/src/components/connectors/wizard/use-wizard-state.test.ts
  - frontend/src/components/connectors/wizard/add-connector-wizard.test.tsx
  - frontend/src/components/connectors/wizard/add-connector-wizard.a11y.test.tsx
  - frontend/src/components/connectors/wizard/credentials-step.test.tsx
  - frontend/src/components/connectors/wizard/confirm-step.test.tsx
  - frontend/src/components/ui/responsive-dialog.test.tsx
  - frontend/src/app/(authed)/dashboard/connectors/page.test.tsx
  - frontend/e2e/connector-wizard-a11y.spec.ts
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-07-20T11:58:12Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Reviewed the four-step add-connector wizard: the `useWizardState` gating state machine,
the three in-dialog step components, the stepper, the `ConfirmStep` submit path, the
`ResponsiveDialog` backdrop opt-out, the page integration, and the edit-mode color
reconcile in `connector-form.tsx`.

The core logic is sound. I traced every gating branch that the brief flagged:

- **Test gate + D-08 re-test invalidation** — correct. `SET_TEST_RESULT` clears
  `credentialsChangedSinceTest`; `UPDATE_FIELD` re-arms it on the first keystroke only
  when `testResult !== null`; `isTestStale`/`testPassed`/`canAdvanceFrom('test')` all
  key off both flags consistently. The Pitfall-4 "bounce" scenario (pass → confirm →
  back → back → edit → re-test → advance twice) resolves to `isTestStale === false`, as
  Test E asserts.
- **`ADVANCE` re-guards** `canAdvanceFrom` inside the reducer, so `aria-disabled` on the
  Next button is backed by a real enforcement path (T-19-01) — not display-only.
- **ConfirmStep POST /connectors** — body shape (`connector_type` uppercased,
  `credentials ?? {}`, `sync_interval_minutes`) matches `CreateConnectorBody`; credential
  VALUES are passed to `mutate` but never rendered in the review DOM (T-19-02 holds).
- **connector-form.tsx success color** — the edit/test result block now uses
  `--color-success` green tokens for both border/bg/text; no lavender remains.

No blockers. Findings below are three accessibility/robustness warnings and three
quality/info items.

## Warnings

### WR-01: Wizard dialog has no desktop focus trap; Esc breaks once focus escapes

**File:** `frontend/src/components/ui/responsive-dialog.tsx:91-113`, `frontend/src/app/(authed)/dashboard/connectors/page.tsx:363-413`
**Issue:** `ResponsiveDialog`'s desktop branch renders `role="dialog" aria-modal="true"`
but implements **no Tab focus trap**. Its own file comment concedes this: *"The caller
(ConfirmModal) retains its own Esc + trapTabKey effects so the desktop focus-trap
contract is not regressed."* `ConfirmModal.tsx` does exactly that (`trapTabKey` +
document-level `keydown` at lines 57-72). But the connectors page opens the add/edit
dialog by rendering `ResponsiveDialog` **directly** (page.tsx:363), *not* through
`ConfirmModal` — so the wizard dialog inherits no trap. On desktop, Tab walks focus out
of the wizard onto the page behind the overlay. Worse, the only Esc handler is
`onKeyDown` on the backdrop `role="presentation"` div (responsive-dialog.tsx:101); it
fires only via bubbling from a focused descendant, so once focus leaves the dialog, Esc
stops closing it too. This violates modal focus-management expectations (WCAG 2.4.3 /
2.1.2) and materially regressed in impact this phase because the wizard packs many
focusable controls (fields, eye toggles, sync chips, Test, Back/Next) into that
untrapped container. The axe e2e sweep (`connector-wizard-a11y.spec.ts`) will not catch
this — axe does not test focus containment.
**Fix:** Either route the wizard/form dialog through a trapping wrapper, or add a Tab
trap to `ResponsiveDialog`'s desktop branch so it no longer depends on the caller:
```tsx
// responsive-dialog.tsx desktop branch
const panelRef = useRef<HTMLDivElement>(null);
useEffect(() => {
  if (!open || isMobile) return;
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Tab' && panelRef.current) trapTabKey(e, getFocusable(panelRef.current));
  };
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}, [open, isMobile]);
// ...attach ref={panelRef} to the role="dialog" div, and move the Esc handler
// to a document-level listener so it survives focus leaving the overlay.
```

### WR-02: Credentials step gives screen-reader users no "why" for the disabled Next button

**File:** `frontend/src/components/connectors/wizard/credentials-step.tsx:88-102`, `frontend/src/components/connectors/wizard/add-connector-wizard.tsx:82-89,175-176`
**Issue:** Two gaps compound on step 2. (1) The credential `<input>`s carry no
`required`/`aria-required` (nor does `connector-form.tsx`), so assistive tech gets no
signal the fields are mandatory. (2) The Next button is `aria-disabled` with
`aria-describedby={hintId}`, but `hintText` is computed only for non-credentials steps
(the `if (w.state.step !== 'credentials')` guard at add-connector-wizard.tsx:83) — so on
the credentials step the described-by target resolves to an **empty** paragraph. A blind
user tabbing to a dimmed "Next" on step 2 hears no reason the gate is closed, while the
test step (WR: correctly) announces `testGateHint`. UX-D-02-02 "announce-why" is only
half-wired.
**Fix:** Mark the inputs required and provide a credentials-gate hint:
```tsx
// credentials-step.tsx <input ...>
aria-required="true"
```
```tsx
// add-connector-wizard.tsx — extend the hint logic
if (w.state.step === 'credentials' && !w.canAdvance) {
  hintText = 'Fill every field to continue.'; // add to WIZARD_COPY
}
```

### WR-03: Credentials gate is vacuously true when `fields` is empty

**File:** `frontend/src/components/connectors/wizard/use-wizard-state.ts:54-64,115-118`
**Issue:** `canAdvanceFrom` on the credentials step returns
`fields.every((f) => ...trim() !== '')`, and `[].every()` is `true`. If the wizard mounts
before `useConnectorTypes()` resolves, `AddConnectorWizard` derives `fields = fieldsProp
?? typeInfo?.fields ?? []` (add-connector-wizard.tsx:58) → `[]` → Next is enabled with
zero inputs rendered, letting the user advance (and, after a passing test with empty
credentials `{}`, submit). In the shipped page flow this is not reachable (the add
buttons only render from already-loaded `typesQuery.data`, and `fieldsProp` is always
supplied), but the component is documented as usable standalone and the RED scaffolds
exercise the derive-fields path, so this is a live latent gate hole.
**Fix:** Require at least one field before the credentials gate can open:
```ts
case 'credentials':
  return fields.length > 0 && fields.every((f) => (state.values[f] ?? '').trim() !== '');
```

## Info

### IN-01: `handleSave` declared `async` with no `await`

**File:** `frontend/src/components/connectors/connector-form.tsx:138-174`
**Issue:** `async function handleSave()` contains no `await`; both branches call
`mutate(...)` fire-and-forget with callbacks. The `async` keyword is misleading (implies
the click handler settles a promise it doesn't).
**Fix:** Drop `async` from the declaration.

### IN-02: Failed create surfaces the error twice (toast + inline block)

**File:** `frontend/src/components/connectors/wizard/confirm-step.tsx:51-64`, `frontend/src/lib/queries/use-connectors-admin.ts:145-147`
**Issue:** On a failed `POST /connectors`, `useCreateConnector`'s own `onError` fires a
toast *and* `ConfirmStep`'s `onError` sets `formError`, rendering an inline red alert —
the same message appears in two places. `connector-form.tsx` shares this pattern, so it
is consistent, but it is redundant UX.
**Fix:** Pick one surface — either suppress the hook toast for this call site or drop the
inline `formError` block (the inline block is generally preferable for a form-scoped
failure).

### IN-03: Duplicated field helpers and SYNC_INTERVALS across form and wizard

**File:** `frontend/src/components/connectors/wizard/credentials-step.tsx:21-34`, `frontend/src/components/connectors/connector-form.tsx:38-53`
**Issue:** `isSecretField`, `fieldLabel`, and the `SYNC_INTERVALS` constant are copied
verbatim between `connector-form.tsx` and `credentials-step.tsx` (the comments
acknowledge the lift). Two copies of the secret-detection heuristic will drift.
**Fix:** Extract to a shared module (e.g. `connectors/field-utils.ts`) and import from
both; `SYNC_INTERVALS` is already exported from `use-wizard-state.ts` and can be reused.

---

_Reviewed: 2026-07-20T11:58:12Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
