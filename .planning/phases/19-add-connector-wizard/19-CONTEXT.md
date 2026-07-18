# Phase 19: Add-connector wizard - Context

**Gathered:** 2026-07-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the single-step `ConnectorForm` **add** flow with a guided four-step wizard —
**provider pick → credentials → test → confirm** — reusing the existing connector
endpoints (`POST /connectors/test`, `POST /connectors`) with **no new backend**. The wizard
lives in the existing `ResponsiveDialog` (vaul bottom-sheet on mobile, centered dialog on
desktop) and must pass axe in both themes and keep `/dashboard/connectors` ≤250 KB First-Load JS.

In scope: UX-D-02-01..06. Out of scope: editing an existing connector (stays on today's
single-step form), any backend/endpoint change, and the deferred milestone items (Safari glyph
check, print stylesheet).
</domain>

<decisions>
## Implementation Decisions

### Wizard structure (Step 1 model)
- **D-01:** The existing **category grid on the connectors page IS the provider-pick step.**
  Clicking a provider (or a `+ provider` / "Add another" card, or arriving via `?provider=`)
  opens the `ResponsiveDialog` already scoped to that provider. The dialog itself hosts the
  remaining three interactive steps: **credentials → test → confirm**. No in-modal provider
  picker is built. This preserves the `?provider=` deep-link and the existing grid affordances
  with the least churn while honoring the four-step flow (pick happens outside the modal).
- **D-02:** Wizard state (current step, per-field values/touched, test result, sync interval)
  is dialog-scoped and resets on close/reopen.

### Stepper + gating
- **D-03:** A **numbered step indicator shows all four steps** — `① Provider · ② Credentials ·
  ③ Test · ④ Confirm` — with **Provider (step 1) rendered as already-complete (✓)** since the
  grid picked it. The interactive steps in the dialog are 2–4.
- **D-04:** The step indicator is **display-only** (progress affordance). Navigation is via
  **Back / Next buttons only** — completed steps are NOT click-to-jump. This keeps the test
  gate unskippable and avoids backward-jump state-invalidation edge cases.
- **D-05:** **Next is gated per step.** The user cannot leave the **test** step until the
  connection test has succeeded. `Next` is disabled with an inline hint until the gate is met.

### Test step
- **D-06:** The test step uses an **explicit "Test connection" button** (reuses
  `useTestConnector`) — it does **not** auto-fire on step entry (no surprise API calls, no
  awkward re-fire on Back/Next bounce).
- **D-07:** On **success** → inline ✓ result (reuse the existing green result UI); `Next`
  unlocks. On **failure** → inline error (reuse the existing red result UI); `Next` stays
  disabled; the user fixes credentials (Back) or re-tests. Failure keeps the user on the test step.

### Re-test invalidation
- **D-08:** Editing **any credential field after a passing test immediately clears the ✓** (on
  the **first keystroke**, not on blur). If the user is on or past the test step, `Next` disables
  with an inline hint: **"Credentials changed — re-test to continue."** Guarantees the confirm/
  submit always reflects credentials that were actually tested.

### Confirm step
- **D-09:** The confirm step is a **full review screen**: provider name, the connection-test ✓
  result, the **required permissions/scopes**, and the **sync-interval selector (5 / 15 / 30 /
  60 min)**. The primary **"Add connector"** CTA submits `POST /connectors`.
- **D-10:** Required scopes/permissions are sourced from the connector type's **`permissions[]`**
  (`{scope, access, purpose}`) already returned by `GET /connectors/types` — display scope +
  purpose. (Satisfies UX-D-02-04.) The `/connectors/test` response also carries an optional
  `scopes?` list that MAY be used to reflect the *granted* scopes if present; the type
  `permissions[]` is the canonical "required access" source.

### Edit-mode scope
- **D-11:** The wizard is **add-only.** Editing an existing connector **keeps today's single-step
  `ConnectorForm`** (sentinel `••••••` pre-fill, per-field touched tracking, inline test, save).
  UX-D-02 is scoped to *adding*; edit has no provider-pick step. Smallest blast radius — the
  proven sentinel-passthrough edit path (D-CONN-04 / T-14-07) is left untouched.

### Sentinel passthrough (carried forward, add-path)
- **D-12:** Add mode starts with empty credential fields, so the sentinel is not shown; but the
  existing `buildCredentials()` **add-path** logic (include only non-empty fields; never send the
  `••••••` literal) carries over verbatim into the wizard's credentials step. Edit-mode sentinel
  behavior is unchanged (see D-11).

### Dismissal
- **D-13:** Keep the Phase-15 dialog behavior exactly: **backdrop-click is a no-op** (no silent
  discard); **X button and Esc close immediately with no confirm prompt.** In-progress credentials
  are lost on explicit close — acceptable since nothing was submitted. No discard-warning modal
  (the app uses no modal-on-modal pattern, and it complicates the vaul mobile sheet).

### Quality gate (non-negotiable, from v2.2 roadmap)
- **D-14:** `/dashboard/connectors` passes **axe WCAG 2.1 AA in both light and dark themes**,
  stays **≤250 KB First-Load JS**, and is **reduced-motion-safe**. The wizard stepper, Back/Next,
  and inline test/error states must be keyboard-navigable and screen-reader legible.

### Claude's Discretion
- Exact visual design of the step indicator within the sunset system (the design system has **no
  existing stepper/wizard pattern** — see code_context; design it from `foundation.md` tokens and
  flag the new pattern).
- Precise inline copy for the re-test hint, test button, and confirm CTA (follow `copy-voice.md`).
- Whether the wizard is a new component tree or a refactor of `ConnectorForm` into step
  sub-components (planner's call; edit mode must keep working either way).
- Mobile (vaul) layout of the stepper + Back/Next within the bottom sheet.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/milestones/v2.2-ROADMAP.md` — Phase 19 goal + 4 success criteria (§"Phase 19")
- `.planning/milestones/v2.2-REQUIREMENTS.md` — UX-D-02-01..06 (the six requirement units) + out-of-scope

### Prior connector decisions (must stay consistent)
- `.planning/phases/14-remaining-screens/14-CONTEXT.md` — origin of D-CONN-* connector decisions:
  category grouping (D-CONN-03), `?provider=` deep-link (D-CONN-07), sentinel-passthrough
  (D-CONN-04). The Phase-14 code review's Critical was a brittle secret sentinel — do not regress.

### Backend contract (fixed — no changes this phase)
- `backend/app/connectors/router.py` — `GET /types` (returns `permissions[] {scope, access,
  purpose}` at lines ~76–78), `POST /test`, `POST /connectors`. Source of required-scopes data.
- `backend/app/connectors/schemas.py` — `ConnectorTypeInfo` (`fields[]` are **objects** with
  `{name, label, type, required}`; per-type `permissions[]`). Note the frontend type mismatch below.

### Existing frontend to reuse / refactor
- `frontend/src/app/(authed)/dashboard/connectors/page.tsx` — the grid = step 1 (D-01); hosts the
  `ResponsiveDialog`; owns `?provider=` deep-link, `openAddForm`/`openEditForm`, form state.
- `frontend/src/components/connectors/connector-form.tsx` — current single-step form; `buildCredentials()`
  add-path (D-12) and the whole edit path (D-11) must survive. Wizard likely decomposes this.
- `frontend/src/components/ui/responsive-dialog.tsx` — vaul mobile / desktop dialog contract (D-13).
- `frontend/src/lib/queries/use-connectors-admin.ts` — `useCreateConnector`, `useTestConnector`,
  `useConnectorTypes`; types `ConnectorTypeInfo`, `ConnectorTypePermission`, `TestConnectorResult
  {success, message, scopes?}`. ⚠ `ConnectorTypeInfo.fields` is typed `string[]` but the backend
  returns field **objects** — the wizard likely needs the richer shape (label/type/required);
  reconcile the type (planner detail).
- `frontend/src/components/connectors/microcopy.ts` — `FORM_COPY` (test/save/cancel/sentinel labels),
  category labels/empty copy. Extend here for wizard copy.

### Design system (sunset)
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — tokens/typography/motion (build
  the new stepper from these; **no freehand hex**).
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — **no existing
  stepper/wizard pattern** (confirmed); follow the spirit + flag the gap.
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — loading/empty/error patterns
  (mandatory); the test step's pending/success/error reuse these.
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — severity/status/CTA visual
  language (test ✓ = success/low-severity green, ✗ = critical red — matches current form).
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — microcopy voice for the re-test
  hint, buttons, confirm summary.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`ResponsiveDialog`** (`ui/responsive-dialog.tsx`) — the wizard container; vaul sheet on mobile,
  centered dialog on desktop, Esc/backdrop handled via `onOpenChange`. Reuse as-is (D-13).
- **`useTestConnector` / `useCreateConnector` / `useConnectorTypes`** (`use-connectors-admin.ts`) —
  all endpoints the wizard needs already exist as hooks. No new backend, no new hooks required.
- **`ConnectorForm.buildCredentials()` add-path** — the exact "include only non-empty, never send
  sentinel" logic to carry into the credentials step (D-12).
- **Existing inline test-result UI** (green/red bordered blocks in `connector-form.tsx` lines
  ~274–290) — reuse verbatim for the test step (D-07).
- **Connector-type `permissions[]`** — already flows to the frontend via `GET /types`; the confirm
  step (D-09/D-10) renders it. No new data plumbing.
- **Category grid + `?provider=` deep-link** (`connectors/page.tsx`) — unchanged; it is step 1 (D-01).

### Established Patterns
- **Sentinel-passthrough** (D-CONN-04 / T-14-07) — sacred; add mode doesn't display it, edit mode
  keeps it. Never send `••••••` to the backend.
- **snake_case wire contract, no transform layer** (D-X-02) — keep it.
- **State patterns mandatory** — pending/empty/error must be handled (test step especially).
- **`next/dynamic({ssr:false})` for heavy client-only UI** (used for the Phase-18 kanban to keep it
  out of First-Load JS) — consider for the wizard if bundle pressure appears near the 250 KB gate.

### Integration Points
- `connectors/page.tsx` `formState` + `ResponsiveDialog` block is where the wizard replaces the
  current `<ConnectorForm mode="add" …>` render. Edit still renders the old form.
- `microcopy.ts` `FORM_COPY` — extend for wizard copy.
- `use-connectors-admin.ts` `ConnectorTypeInfo.fields` type — reconcile `string[]` → field objects.

### Gaps to flag
- **No stepper/wizard pattern exists in the design system** — the step indicator is net-new UI;
  design it from `foundation.md` tokens and note it in the design-system skill if it becomes a
  reusable primitive.

</code_context>

<specifics>
## Specific Ideas

- The four-step framing (`① Provider ✓ · ② Credentials · ③ Test · ④ Confirm`) is the mental model
  even though only steps 2–4 are inside the dialog — the stepper shows all four for continuity.
- The confirm step is deliberately a "here's what you're granting" review: provider + test ✓ +
  required scopes/purpose + sync interval, all on one screen before the single Add CTA.
- Test-gating must be tamper-evident: editing a tested credential visibly revokes the ✓ on the
  first keystroke so a user can never submit untested credentials.

</specifics>

<deferred>
## Deferred Ideas

- **Wizard-ifying the edit flow** — considered and explicitly deferred (D-11). Edit keeps the
  single-step form this milestone; revisit only if a future requirement asks for it.
- **In-modal provider picker** — the alternative Step-1 model (all four steps inside the dialog)
  was rejected in favor of reusing the page grid (D-01). Not lost, just not this phase.
- **Discard-warning on dismissal** — rejected (D-13) to avoid a modal-on-modal pattern; revisit
  only if users report accidental credential loss.
- **Promoting the stepper to a shared design-system primitive** — build it here first; if a second
  wizard appears later, extract it.

</deferred>

---

*Phase: 19-add-connector-wizard*
*Context gathered: 2026-07-18*
