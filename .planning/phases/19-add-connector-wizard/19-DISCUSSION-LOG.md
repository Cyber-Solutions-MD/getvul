# Phase 19: Add-connector wizard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-18
**Phase:** 19-add-connector-wizard
**Areas discussed:** Step-1 model, Stepper UX, Edit-mode scope, Confirm step, Test step, Dismissal, Stepper nav, Re-test invalidation

---

## Step-1 model (where "provider pick" lives)

| Option | Description | Selected |
|--------|-------------|----------|
| Grid is step 1, dialog opens at credentials | Existing category grid = provider pick; dialog hosts credentials→test→confirm | ✓ |
| All 4 steps inside the dialog | In-modal provider picker as step 1, duplicating the page grid | |

**User's choice:** Grid is step 1, dialog opens at credentials.
**Notes:** Least churn; preserves `?provider=` deep-link and "+ add another" cards; honors the four-step flow with pick outside the modal. → D-01.

---

## Stepper UX (progress + gating + back-nav)

| Option | Description | Selected |
|--------|-------------|----------|
| Numbered stepper + Back/Next, re-test on edit | Numbered indicator; Next gated; editing creds after a pass forces re-test | ✓ |
| Numbered stepper, edits keep the pass | Same, but edits don't force re-test | |
| Dots only, minimal chrome | Minimal dot progress, no labels | |

**User's choice:** Numbered stepper + Back/Next, re-test on edit.
**Notes:** Confirm/submit always reflects tested credentials. → D-03/D-04/D-05/D-08.

---

## Edit-mode scope

| Option | Description | Selected |
|--------|-------------|----------|
| Wizard is add-only; edit keeps single-step form | Edit stays on today's ConnectorForm | ✓ |
| Both add and edit use the wizard | Edit reuses wizard, skipping provider-pick | |

**User's choice:** Wizard is add-only; edit keeps single-step form.
**Notes:** UX-D-02 is scoped to adding; edit has no provider step; proven sentinel-passthrough path untouched. → D-11.

---

## Confirm step (content + sync-interval placement)

| Option | Description | Selected |
|--------|-------------|----------|
| Full summary + scopes; sync interval on confirm | Provider + test ✓ + required scopes/purpose + sync interval selector | ✓ |
| Scopes + provider only; sync interval on credentials step | Leaner confirm; sync interval moved earlier | |

**User's choice:** Full summary + scopes; sync interval on confirm.
**Notes:** One reviewable "here's what you're granting" screen; scopes from type `permissions[]`. → D-09/D-10.

---

## Test step (fire mode + failure handling)

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit button, retry inline on fail | "Test connection" button; inline ✓/✗; Next gated; retry on failure | ✓ |
| Auto-fire on entering the test step | Test runs automatically on step entry | |

**User's choice:** Explicit button, retry inline on fail.
**Notes:** No surprise API calls; reuses existing inline result UI; failure keeps user on test step. → D-06/D-07.

---

## Dismissal (closing mid-wizard with creds entered)

| Option | Description | Selected |
|--------|-------------|----------|
| Backdrop no-op; X/Esc close immediately, no warn | Keep Phase-15 dialog behavior exactly | ✓ |
| Warn if credentials entered | Discard-confirm modal on close when creds touched | |

**User's choice:** Backdrop no-op; X/Esc close immediately, no warn.
**Notes:** Matches every other dialog; avoids modal-on-modal + vaul complications; nothing submitted so loss is acceptable. → D-13.

---

## Stepper nav (which steps show + click-jump)

| Option | Description | Selected |
|--------|-------------|----------|
| Show all 4; Back/Next only (no click-jump) | 4-step display, provider ✓; indicator is display-only | ✓ |
| Show all 4; completed steps clickable to jump back | Backward jumps allowed | |
| Show only the 3 in-dialog steps | Drop the provider step from the indicator | |

**User's choice:** Show all 4; Back/Next only (no click-jump).
**Notes:** Keeps the test gate unskippable; avoids backward-jump invalidation edge cases; retains the four-step framing. → D-03/D-04.

---

## Re-test invalidation (how the forced re-test is signaled)

| Option | Description | Selected |
|--------|-------------|----------|
| Clear ✓ on first keystroke; Next hint | ✓ clears immediately on edit; inline "Credentials changed — re-test" hint | ✓ |
| Invalidate on leaving the field (onBlur) | ✓ clears on blur | |

**User's choice:** Clear ✓ on first keystroke; Next hint.
**Notes:** Immediate, tamper-evident feedback; user can never submit untested credentials. → D-08.

---

## Claude's Discretion

- Visual design of the stepper within the sunset system (no existing wizard pattern — design from foundation.md).
- Inline copy for re-test hint, test button, confirm CTA (per copy-voice.md).
- New component tree vs refactor of ConnectorForm into step sub-components (planner's call).
- Mobile (vaul) stepper + Back/Next layout.

## Deferred Ideas

- Wizard-ifying the edit flow (D-11 defers).
- In-modal provider picker (rejected Step-1 alternative).
- Discard-warning on dismissal (rejected).
- Promoting the stepper to a shared design-system primitive (build here first).
