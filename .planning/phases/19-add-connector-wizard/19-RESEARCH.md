# Phase 19: Add-connector wizard - Research

**Researched:** 2026-07-20
**Domain:** Frontend multi-step wizard UI (React 19 / Next.js 15) inside an existing vaul/Radix-pattern responsive dialog, reusing existing FastAPI endpoints
**Confidence:** HIGH

## Summary

This phase replaces the single-step add-connector form with a four-step wizard, but three of the four steps ("Provider" already lives on the page grid) are hosted inside the existing `ResponsiveDialog`. There is no new backend work, no new npm dependency, and — per a fresh production build performed during this research — **no bundle-budget risk**: `/dashboard/connectors` currently measures **153 kB First-Load JS** against the 250 kB gate, a 97 kB margin. The wizard is composed entirely from hooks/components that already exist (`useCreateConnector`, `useUpdateConnector`, `useTestConnector`, `useConnectorTypes`, `ResponsiveDialog`, `focus-trap.ts` helpers), so `next/dynamic({ssr:false})` is very unlikely to be needed — treat it as a fallback only if a build after implementation approaches budget.

The single highest-value finding from reading the actual backend code: the `ConnectorTypeInfo.fields` "type mismatch" flagged in CONTEXT.md and UI-SPEC.md is **not a wire-contract bug**. `GET /connectors/types` (`backend/app/connectors/router.py:51-86`) explicitly flattens the internal `fields: list[dict]` model down to a `fields: string[]` array before returning JSON — the frontend type is already correct for what actually crosses the wire today. The richer per-field metadata (`label`, `type`, `required`) exists in the internal `ConnectorTypeInfo` Pydantic model (`backend/app/connectors/schemas.py`) but is **discarded by the endpoint handler**, never sent to the client. All 38 field definitions across every connector type in `CONNECTOR_TYPES` currently have `required: True` (zero exceptions), so today's "all fields required" client-side assumption happens to be correct — but it is an accidental invariant, not a guaranteed contract, and the planner has three real options (detailed in Pitfall 1 below), not a simple type-widening exercise.

The stepper is genuinely net-new UI (confirmed: zero occurrences of "stepper"/"wizard"/"step" in `interaction-patterns.md`). The UI-SPEC.md already specifies its full visual, copy, color, and a11y contract in detail — this research does not re-litigate that spec, it fills the gaps UI-SPEC intentionally left to the planner (state-machine shape, focus-management mechanics inside an already-open vaul sheet, exact WAI-ARIA semantics, and test strategy).

**Primary recommendation:** Decompose `ConnectorForm` into a `useWizardState` reducer + three step components (Credentials / Test / Confirm) that render inside the existing `ResponsiveDialog`, reusing `buildCredentials()`, `useTestConnector`, `useCreateConnector`, and the `focus-trap.ts` helpers verbatim; keep `ConnectorForm` itself unchanged for the edit path (D-11). Use `<ol>` + `aria-current="step"` for the stepper (not the ARIA tablist pattern — the stepper is intentionally non-interactive per D-04, so tablist's implied keyboard-navigability would be a false affordance). Move focus to each step's `<h3>` on advance using a `tabIndex={-1}` + `.focus()` effect that runs on **both** desktop and mobile — this deliberately differs from the existing `ConfirmModal`/`drill-panel-mobile` precedent (which skips all programmatic focus on mobile) because those components have static content while the wizard's content changes underneath an already-open vaul sheet.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Provider selection | Frontend (existing page/grid) | — | D-01: grid IS step 1, no in-modal picker built |
| Wizard step state (current step, field values/touched, test result, sync interval) | Frontend (client component, dialog-scoped) | — | D-02: resets on close/reopen; no persistence needed, no backend involvement |
| Step navigation gating (D-05) | Frontend | — | Pure client-side derived state (`canAdvance` computed from `buildCredentials()` / `testResult`) |
| Credential input + sentinel passthrough | Frontend | Backend (accepts credentials, never returns them) | `has_credentials` boolean only ever returned by backend (T-14-06); UI never displays real secrets |
| Connection test | Frontend (trigger + render) | Backend (`POST /connectors/test`, live network call to the 3rd-party API) | No new backend; existing `useTestConnector` hook covers it |
| Required scopes/permissions display | Frontend (render) | Backend (`GET /connectors/types` — source of `permissions[]`) | Data already flows to frontend; no new plumbing |
| Connector creation | Frontend (submit) | Backend (`POST /connectors`, persists `ConnectorConfig` row) | No new backend |
| Bundle/a11y quality gate | Frontend (CI checks) | — | `scripts/check-bundle-all.mjs` + Playwright axe fixtures already sweep `/dashboard/connectors` |

## User Constraints (from CONTEXT.md)

<user_constraints>

### Locked Decisions

- **D-01:** The category grid on `/dashboard/connectors` IS the provider-pick step. Clicking a provider (or "Add another" / `?provider=`) opens `ResponsiveDialog` already scoped to that provider. No in-modal provider picker.
- **D-02:** Wizard state (current step, per-field values/touched, test result, sync interval) is dialog-scoped and resets on close/reopen.
- **D-03:** Numbered step indicator shows all 4 steps (`① Provider · ② Credentials · ③ Test · ④ Confirm`), with Provider always rendered complete (✓). Interactive steps in the dialog are 2–4.
- **D-04:** Step indicator is display-only. Navigation is Back/Next only — no click-to-jump.
- **D-05:** Next is gated per step. Cannot leave the test step until the connection test succeeds; `Next` disabled with inline hint until met.
- **D-06:** Test step uses an explicit "Test connection" button (reuses `useTestConnector`) — no auto-fire on step entry.
- **D-07:** On success → inline ✓ result, `Next` unlocks. On failure → inline error, `Next` stays disabled, user fixes via Back or re-tests. Failure keeps user on test step.
- **D-08:** Editing any credential field after a passing test immediately clears the ✓ (first keystroke, not blur). If on/past test step, `Next` disables with hint "Credentials changed — re-test to continue."
- **D-09:** Confirm step is a full review: provider, connection-test ✓, required scopes, sync-interval selector (5/15/30/60 min). Primary "Add connector" CTA submits `POST /connectors`.
- **D-10:** Required scopes sourced from connector type's `permissions[]` (`{scope, access, purpose}`) from `GET /connectors/types` — canonical "required access" source. `/connectors/test` response's optional `scopes?` MAY reflect granted scopes.
- **D-11:** Wizard is add-only. Editing keeps today's single-step `ConnectorForm` (sentinel `••••••` pre-fill, per-field touched tracking, inline test, save). No provider-pick step for edit.
- **D-12:** Add mode starts empty; `buildCredentials()` add-path logic (include only non-empty fields, never send `••••••`) carries over verbatim into the wizard's credentials step.
- **D-13:** Keep Phase-15 dialog behavior: backdrop-click is a no-op; X/Esc close immediately with no confirm prompt. No discard-warning modal.
- **D-14:** `/dashboard/connectors` passes axe WCAG 2.1 AA in both light and dark themes, stays ≤250 KB First-Load JS, and is reduced-motion-safe. Stepper, Back/Next, and inline test/error states must be keyboard-navigable and screen-reader legible.

### Claude's Discretion

- Exact visual design of the step indicator within the sunset system (no existing stepper/wizard pattern — design from `foundation.md` tokens and flag the new pattern). **Resolved by UI-SPEC.md** (approved) — see its "Stepper Visual Spec" section; planner should treat that spec as locked, not re-derive.
- Precise inline copy for the re-test hint, test button, and confirm CTA (follow `copy-voice.md`). **Resolved by UI-SPEC.md** "Copywriting Contract" section.
- Whether the wizard is a new component tree or a refactor of `ConnectorForm` into step sub-components (planner's call; edit mode must keep working either way). **This research recommends**: decompose into step sub-components sharing a `useWizardState` hook; keep `ConnectorForm` as the edit-mode container, do not delete it.
- Mobile (vaul) layout of the stepper + Back/Next within the bottom sheet. **Resolved by UI-SPEC.md** "Responsive (mobile vaul) Contract" section.

### Deferred Ideas (OUT OF SCOPE)

- Wizard-ifying the edit flow (D-11) — edit keeps the single-step form this milestone.
- In-modal provider picker — rejected in favor of reusing the page grid (D-01).
- Discard-warning on dismissal — rejected (D-13) to avoid modal-on-modal.
- Promoting the stepper to a shared design-system primitive — build inline first; extract only if a second wizard appears.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-D-02-01 | Adding a connector runs a four-step wizard: provider pick → credentials → test connection → confirm | See Architecture Patterns (Wave/Component structure); D-01 grid-is-step-1 confirmed against `connectors/page.tsx` `openAddForm`/`?provider=` handling, unchanged |
| UX-D-02-02 | Step navigation is gated — cannot advance past test step until test succeeds | See Common Pitfalls #1 (required-field data gap) and #4 (gating state machine); UI-SPEC "Interaction & Gating Contract" is the copy/visual source of truth |
| UX-D-02-03 | Credentials step reuses sentinel-passthrough (edit preserves untouched secrets; only touched fields sent) | Verified in `connector-form.tsx` `buildCredentials()` (lines 112–136) — carries over verbatim per D-12; edit path (D-11) untouched |
| UX-D-02-04 | Confirm step shows required OAuth scopes/permissions before final submit | Verified `permissions[]` already returned by `GET /connectors/types` (`router.py:76-79`); zero new plumbing needed |
| UX-D-02-05 | Wizard reuses existing endpoints (`POST /connectors/test`, `POST /connectors`) — no new backend | Verified both endpoints exist unchanged in `router.py`; hooks `useTestConnector`/`useCreateConnector` in `use-connectors-admin.ts` need no modification |
| UX-D-02-06 | Wizard works in ResponsiveDialog/vaul mobile pattern; passes axe both themes; connectors route ≤250 KB | Verified current build: 153 kB First-Load JS (97 kB headroom); `ResponsiveDialog` mobile/desktop branches read in full (see Code Examples); axe fixture infra already covers `/dashboard/connectors` via `STATIC_ROUTES` |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vaul | 1.1.2 (installed = npm latest) [VERIFIED: `npm view vaul version` + `node_modules/vaul/package.json`] | Mobile bottom-sheet primitive behind `ResponsiveDialog` | Already the app's sole drawer/sheet library (Phase 15); no upgrade needed |
| @tanstack/react-query | ^5.100.10 [VERIFIED: package.json] | `useCreateConnector`/`useTestConnector`/`useConnectorTypes` data layer | Already the app's sole data-fetching layer; no new hooks needed, only new call sites |
| lucide-react | ^0.383.0 [VERIFIED: package.json] | `CheckCircle2`, `XCircle`, `Loader2`, `X`, (+`ArrowLeft`/`ArrowRight` if desired per UI-SPEC) | Already the app's icon set; install requires `--legacy-peer-deps` per existing project convention (React 19 peer conflict, noted in STATE.md Phase 15/18 history) — not a new install this phase since it's already a dependency |
| React | ^19.0.0 [VERIFIED: package.json] | Wizard state via `useReducer`/`useState` | No new state library needed — 4-step gated flow is well within plain React state |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| vitest-axe | ^0.1.0 [VERIFIED: package.json] | Component-level jsdom axe assertions | Fast per-task a11y check on the wizard component tree, before the full Playwright e2e sweep (see Validation Architecture) |
| @axe-core/playwright | ^4.12.1 [VERIFIED: package.json] | E2E axe sweep (`makeAxeBuilder`/`makeAxeBuilderReportOnly` fixtures) | Route-level gate for `/dashboard/connectors` in both themes (already wired in `e2e/a11y-routes.spec.ts` via `STATIC_ROUTES`) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Plain `useState`/`useReducer` wizard state | A form library (react-hook-form, Formik) | Rejected — the app has zero existing form-library dependency; the existing `ConnectorForm` uses plain state, and CONTEXT explicitly scopes "no new backend"/minimal footprint. Introducing a form library here would be inconsistent with every other GetVul form and adds bundle weight for no benefit at this field count (2–4 fields per connector type). |
| `<ol>` + `aria-current="step"` stepper | ARIA `tablist`/`tab`/`tabpanel` pattern (APG "Tabs" widget) | Tablist implies interactive, arrow-key-navigable tabs — but D-04 makes the stepper explicitly non-interactive/non-focusable (no click-to-jump). Using tablist semantics would create a false affordance (screen readers announce it as operable) that contradicts the locked decision. `<ol>`/`aria-current` is the correct pattern for a *progress indicator*, distinct from a *tab-switcher*. |
| `next/dynamic({ssr:false})` for the wizard | Ship the wizard as regular imports | With 153 kB current / 250 kB budget, and the wizard composed from zero new dependencies, dynamic-import is unnecessary overhead (adds a loading-flash edge case inside an already-open dialog). Reserve as a fallback only if a post-implementation build measurement approaches budget — see Common Pitfalls #3. |

**Installation:** No new packages required — `npm install` is a no-op for this phase (confirm via `npm ci` / lockfile diff during Wave 0 if any drift is suspected).

**Version verification:** vaul 1.1.2 confirmed current via `npm view vaul version` (returns `1.1.2`, matching `node_modules/vaul/package.json`) [VERIFIED: npm registry, 2026-07-20].

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ /dashboard/connectors (page.tsx)                                 │
│                                                                    │
│  Category grid (UNCHANGED — this IS step 1 "Provider", D-01)     │
│    │                                                              │
│    ├─ click provider card ──────┐                                │
│    ├─ click "+ Add another" ────┤                                │
│    └─ ?provider= deep-link ─────┤                                │
│                                  ▼                                │
│                     openAddForm(connectorType)                    │
│                     setFormState({ open: true, mode: 'add', ... })│
│                                  │                                │
│                                  ▼                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ResponsiveDialog (UNCHANGED container, D-13)                 │ │
│  │   mobile <768px → vaul Drawer.Root/Content (bottom sheet)    │ │
│  │   desktop       → centered role="dialog"                    │ │
│  │                                                                │
│  │  ┌──────────────────────────────────────────────────────┐   │ │
│  │  │ AddConnectorWizard (NEW)                               │   │ │
│  │  │   useWizardState() reducer:                            │   │ │
│  │  │     step: 'credentials' | 'test' | 'confirm'            │   │ │
│  │  │     values, touched, testResult, syncInterval           │   │ │
│  │  │                                                          │   │ │
│  │  │   WizardStepper (display-only, <ol>, aria-current)       │   │ │
│  │  │        │                                                 │   │ │
│  │  │        ▼ (only one step's <section> visible at a time)  │   │ │
│  │  │   ┌─────────────┐  ┌──────────┐  ┌───────────────────┐ │   │ │
│  │  │   │ Credentials │─▶│  Test    │─▶│ Confirm            │ │   │ │
│  │  │   │ step        │  │  step    │  │ step                │ │   │ │
│  │  │   │             │  │          │  │                     │ │   │ │
│  │  │   │ inputs +    │  │ "Test    │  │ provider + ✓ +      │ │   │ │
│  │  │   │ buildCreds()│  │ connect' │  │ permissions[] +     │ │   │ │
│  │  │   │ (D-12,      │  │ button   │  │ sync-interval chips │ │   │ │
│  │  │   │ verbatim)   │  │ (D-06)   │  │ + "Add connector"   │ │   │ │
│  │  │   └─────────────┘  └────┬─────┘  └──────────┬──────────┘ │   │ │
│  │  │                          │                    │            │   │ │
│  │  │                          ▼                    ▼            │   │ │
│  │  │              useTestConnector.mutate   useCreateConnector  │   │ │
│  │  │              → POST /connectors/test   .mutate → POST      │   │ │
│  │  │                (existing hook,          /connectors         │   │ │
│  │  │                 unchanged)              (existing hook,      │   │ │
│  │  │                                          unchanged)          │   │ │
│  │  └──────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

Edit flow (UNCHANGED, D-11):
  openEditForm(connector) → same ResponsiveDialog → <ConnectorForm mode="edit" .../>
  (today's single-step form — no wizard, no provider-pick step)
```

### Recommended Project Structure

```
frontend/src/components/connectors/
├── connector-form.tsx           # UNCHANGED — edit-mode container (D-11); add-mode render
│                                 #   replaced at the page.tsx call site (see below)
├── microcopy.ts                 # extend FORM_COPY: nextLabel, backLabel, retestHint,
│                                 #   testGateHint, confirm section labels
├── wizard/                      # NEW directory
│   ├── add-connector-wizard.tsx    # top-level: owns useWizardState, renders stepper + steps
│   ├── use-wizard-state.ts         # NEW: reducer/hook — step, values, touched, testResult,
│   │                                 #   syncInterval, canAdvance derived state, invalidation
│   ├── wizard-stepper.tsx          # NEW: display-only <ol> stepper per UI-SPEC
│   ├── credentials-step.tsx        # NEW: lifts field-rendering JSX from connector-form.tsx
│   ├── test-step.tsx               # NEW: reuses inline result block (color-corrected, see
│   │                                 #   Pitfall 2), explicit test button
│   └── confirm-step.tsx            # NEW: review screen, permissions[] list, sync chips,
│                                     #   final submit CTA
└── connector-form.test.tsx      # UNCHANGED test file for edit mode; NEW test files added
                                  #   under wizard/ mirroring this file's patterns
```

`frontend/src/app/(authed)/dashboard/connectors/page.tsx` changes: the `<ConnectorForm mode={formState.mode} .../>` render inside `ResponsiveDialog` becomes conditional — `mode === 'add'` renders `<AddConnectorWizard .../>`, `mode === 'edit'` renders the existing `<ConnectorForm mode="edit" .../>` unchanged. `openAddForm`/`?provider=` effect logic is untouched (D-01).

### Pattern 1: Dialog-scoped wizard state via reset-on-open reducer

**What:** A single `useWizardState(fields, connectorType)` hook owns `{ step, values, touched, testResult, syncInterval }` and exposes `canAdvance`, `advance()`, `back()`, `updateField()`, `setTestResult()`. Because `ResponsiveDialog` already unmounts its children when `!open` (guard: `if (!open) return null` — see `responsive-dialog.tsx` line 45), mounting `<AddConnectorWizard key={connectorType}>` fresh on every open is sufficient for D-02's "resets on close/reopen" — no explicit reset effect needed, just don't lift state above the dialog boundary.

**When to use:** Any dialog-scoped multi-step flow in this codebase where state must not survive a close/reopen cycle.

**Example:**
```typescript
// Source: pattern observed in responsive-dialog.tsx (existing unmount-on-close guard)
// frontend/src/components/ui/responsive-dialog.tsx line 45:
//   if (!open) return null;
// This guard already destroys children on close — a wizard component mounted
// as a child gets a fresh instance (and fresh internal state) on every re-open,
// satisfying D-02 without extra reset plumbing.
```

### Pattern 2: Non-interactive progress indicator (`<ol>` + `aria-current="step"`)

**What:** The stepper renders as `<nav aria-label="Wizard progress"><ol>...<li></ol></nav>`, with the current step's element carrying `aria-current="step"`. Steps are plain `<li>` (or a `<span>`/`<div>` inside), never `<button>`/`<a>` — this is a WAI-ARIA-recognized pattern (`aria-current` for progress/breadcrumb-like indicators) distinct from the `tablist` widget, which requires roving tabindex and Left/Right arrow-key navigation because tabs are interactive. [CITED: MDN "WAI-ARIA basics", W3C ARIA Authoring Practices Guide — no APG reference implementation exists specifically named "wizard"; `aria-current="step"` is the documented value for exactly this "step in a process" case, distinct from `aria-current="page"`, `"location"`, `"date"`, `"time"`, `"true"`.]

**When to use:** Any progress indicator where steps are NOT independently navigable (matches D-04 exactly).

**Example:**
```tsx
// Illustrative — synthesize from UI-SPEC "Stepper Visual Spec" + this ARIA pattern.
<nav aria-label="Wizard progress">
  <ol className="flex items-center gap-6">
    {STEPS.map((s, i) => (
      <li key={s.key} aria-current={s.key === currentStep ? 'step' : undefined}>
        {s.status === 'complete' ? (
          <>
            <CheckCircle2 aria-hidden />
            <span className="sr-only"> (completed)</span>
          </>
        ) : (
          <span aria-hidden>{i + 1}</span>
        )}
        <span>{s.label}</span>
      </li>
    ))}
  </ol>
</nav>
```

### Pattern 3: Focus-to-heading on step change, including on mobile

**What:** On step advance/back, focus moves to that step's `<h3 tabIndex={-1}>` via a `useEffect` keyed on the current step. Unlike `ConfirmModal`'s `isMobile` guard (which skips ALL programmatic focus on mobile because vaul's own drawer-open focus grab is sufficient for static content), the wizard's step-to-step focus move must run on **both** desktop and mobile, because vaul only manages focus once — at `Drawer.Root` open — not on every internal content swap. UI-SPEC explicitly calls this out ("this runs after vaul has established the sheet's focus scope").

**When to use:** Any future multi-step content that changes *inside* an already-open vaul sheet (this is the first such case in the codebase — flag as a new precedent if it works well).

**Example:**
```tsx
// Source: adapted from ConfirmModal's confirmRef pattern (frontend/src/components/ui/ConfirmModal.tsx
// lines 38-51) — but WITHOUT the `!isMobile` guard, since content changes post-open.
const headingRef = useRef<HTMLHeadingElement>(null);
useEffect(() => {
  headingRef.current?.focus();
}, [currentStep]); // no isMobile guard — see Pattern 3 rationale
// ...
<h3 ref={headingRef} tabIndex={-1} id={stepHeadingId}>{stepLabel}</h3>
```

### Anti-Patterns to Avoid

- **Rendering the stepper as clickable tabs:** Contradicts D-04 (display-only, no click-to-jump) and would require implementing skip logic for the ungated Provider step and re-test invalidation on backward jumps — the exact complexity D-04 was written to avoid.
- **Auto-firing the connection test on step 3 entry:** Contradicts D-06 explicitly (no surprise API calls, no re-fire on Back/Next bounce).
- **Using `disabled` (not `aria-disabled`) on the gated Next button:** Native `disabled` removes the button from the tab order, so screen-reader users can't discover *why* they can't advance — UI-SPEC's "Disabled-Next pattern" section mandates `aria-disabled` + `aria-describedby` + a no-op click guard instead.
- **Treating `permissions[]` absence as an error state:** UI-SPEC already specifies the empty-scopes copy ("No special scopes required.") — this is a valid, expected state for connector types with no special permissions, not a partial-failure.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tab/focus trapping inside the dialog | Custom keydown-based trap for the wizard specifically | `focus-trap.ts` (`getFocusable`, `trapTabKey`) — already used by `ConfirmModal` | Proven, tested helper; desktop-only (mobile defers to vaul) exactly matches the wizard's needs for Tab-order containment within the dialog panel |
| Mobile bottom-sheet mechanics (drag, snap, overlay, Esc) | Custom `position: fixed` sheet | `ResponsiveDialog` (vaul-backed) unchanged | D-13 locks this; vaul already handles gesture drag, Esc, and focus scope on open |
| Credential sentinel-passthrough logic | A new "smart" diffing algorithm for the wizard | `buildCredentials()` add-path verbatim (D-12) | Already correct, already tested (`connector-form.test.tsx` Tests 1–3); re-deriving it risks regressing the T-14-07 sentinel-safety guarantee |
| Axe/bundle CI gating | New Playwright specs / new bundle scripts | `e2e/a11y-routes.spec.ts` (`STATIC_ROUTES` already includes `/dashboard/connectors`) + `scripts/check-bundle-all.mjs` (`npm run perf:budget`) | Both already sweep this exact route in both themes; the wizard just needs to not break its own DOM structure. No new CI plumbing needed. |

**Key insight:** Every piece of infrastructure this wizard needs — data hooks, dialog chrome, focus-trap primitive, sentinel logic, a11y/bundle CI — already exists and is already exercised by other parts of the app. This phase is almost entirely a UI composition and state-machine exercise, not an integration exercise. The risk surface is concentrated in the two genuinely new things: the stepper's ARIA semantics (Pattern 2) and the required-fields data gap (Pitfall 1).

## Common Pitfalls

### Pitfall 1: `GET /connectors/types` does not expose which fields are `required`

**What goes wrong:** D-05 (UX-D-02-02) requires "Next enabled only when all required credential fields are non-empty." But the wire contract from `GET /connectors/types` only returns `fields: string[]` (flattened, see Summary) — there is no `required` flag over the wire, even though the backend's internal `CONNECTOR_TYPES` model has it per-field.

**Why it happens:** `router.py`'s `get_connector_types()` handler (lines 51-86) explicitly does `field_names = [f["name"] if isinstance(f, dict) else f for f in v.fields]` and only ships `field_names`, discarding `label`/`type`/`required` from the internal dict.

**How to avoid — three real options for the planner, in order of recommendation:**
1. **(Recommended) Treat all fields as required, matching today's `buildCredentials()` non-empty-check behavior.** Verified: 100% (38/38) of field definitions across all connector types in `schemas.py` currently have `required: True` — zero exceptions exist today. This makes "all fields non-empty" behaviorally identical to "all required fields non-empty" for every real connector, with no backend change and no risk to the "no new backend" constraint (UX-D-02-05). Document this as an explicit assumption so a future connector type with an optional field doesn't silently break gating (flag a code comment referencing this research).
2. **Enrich `GET /connectors/types`'s response to also include `label`/`type`/`required` per field** (additive JSON keys, not a new endpoint, not a new route). This is defensible as still satisfying "no new backend" in spirit (UX-D-02-05 names `POST /connectors/test` and `POST /connectors` specifically as the two endpoints being reused, not `GET /types`), but it IS a backend code change and should be called out explicitly to the user/planner as a scope question rather than assumed silently.
3. **Do nothing different from today** and use the existing `isSecretField()` name-heuristic (`connector-form.tsx` lines 38-45) for password-vs-text rendering, plus option 1 for required-check. This is the lowest-risk path and is what this research recommends combining with option 1.

**Warning signs:** If a future connector type ships with an optional field (e.g., an optional `region` override), gating logic built on "all fields non-empty" will incorrectly block `Next` until the optional field is filled. Not a Phase-19 blocker (no such field exists today) but worth a one-line comment in the code.

### Pitfall 2: The current test-result "success" color is lavender, not green

**What goes wrong:** `connector-form.tsx` lines 278-280 use `border-severity-low/30 bg-severity-low/10 text-severity-low` (lavender, `#A78BFA`) for the success block, but `visual-language.md`/`state-patterns.md` define success as `--color-success` (green, `#4ADE80` dark / `#15803D` light).

**Why it happens:** Pre-existing design-system drift from before the sunset tokens were fully reconciled (same class of issue as the three dark-theme contrast overrides logged in STATE.md's "v2.0 Closeout Notes").

**How to avoid:** UI-SPEC.md already mandates the fix explicitly ("§Color reconciliation") — the wizard's test-pass block MUST use `--color-success` green; reuse the *structure* (icon + bordered block + `role="status"`/`role="alert"`) from `connector-form.tsx` but correct the color token. UI-SPEC leaves it to the planner whether to also fix the source `ConnectorForm` (edit-mode) block or leave a `DESIGN-SYSTEM GAP` comment there — recommend fixing both for consistency, since it's a one-line class change and leaving one green/one lavender within the same route would itself likely fail an axe non-text-contrast or a visual-consistency review.

**Warning signs:** Grep for `severity-low` in `connector-form.tsx` before closing out the phase — if the edit-mode block still shows lavender, decide explicitly (fix or flag) rather than accidentally leaving both variants live.

### Pitfall 3: Bundle budget is currently healthy — don't reach for `next/dynamic` preemptively

**What goes wrong:** UI-SPEC and CONTEXT both mention `next/dynamic({ssr:false})` (used for the Phase-18 kanban) as a fallback "if bundle pressure appears near the 250 KB gate." A fresh production build performed during this research shows `/dashboard/connectors` at **153 kB** First-Load JS today (against 250 kB budget) — a 97 kB margin. [VERIFIED: `npx next build` run 2026-07-20, `frontend/scripts/check-bundle-all.mjs` and `check-bundle.mjs` are the enforcing scripts, `npm run perf:budget` wraps `check-bundle-all.mjs`.]

**Why it happens:** The wizard adds zero new npm dependencies (stepper is composed from JSX + existing icons; all data access reuses existing hooks) — realistically this should add low single-digit kB of new component code, nowhere near exhausting 97 kB of headroom.

**How to avoid:** Implement normally with static imports first. Only reach for `next/dynamic({ssr:false})` if a real `npm run build` measurement after implementation shows the route approaching (not just touching) 250 kB. Premature dynamic-import adds a loading-flash edge case *inside an already-open dialog*, which is its own new a11y/UX surface (focus lands where? does the dialog show a spinner mid-flow?) that isn't justified by the current numbers.

**Warning signs:** If `npm run perf:budget` fails after implementation, investigate what specifically grew (check `next build`'s per-chunk breakdown) before reaching for dynamic-import — it may be an unrelated regression, not the wizard.

### Pitfall 4: Gating state machine has more edge cases than the four steps suggest

**What goes wrong:** D-05 (gate gate) + D-07 (failure keeps user on test step) + D-08 (re-test invalidation on first keystroke) interact: a user can (a) test successfully, (b) go to confirm, (c) hit Back twice to credentials, (d) edit a field, (e) hit Next twice. Per D-08, editing at step (d) must retroactively invalidate the test result even though the user is now on the credentials step, not the test step — the invalidation is a property of `testResult`, not of "being on the test step." The `Next` disable + hint only needs to render "on or past the test step" (UI-SPEC's own wording), meaning credentials step's `Next` gating is untouched by D-08 (it's still just the D-05 non-empty check) but test/confirm steps must re-check `testResult` validity, not just its existence.

**Why it happens:** The four visible steps hide a state machine with more than four states once test-validity and field-touch tracking are cross-referenced.

**How to avoid:** Model this explicitly as `testResult: { success: boolean; message: string; testedCredentialsHash: string } | null` (or a simpler `testResult` + `credentialsChangedSinceTest: boolean` boolean) rather than relying on "did any change event fire since success" implicitly. Recommend a single derived boolean `isTestStale = testResult !== null && credentialsChangedSinceTest` computed in the wizard reducer, consumed by both the test-step gate and the confirm-step gate (confirm step should also refuse to submit — or at minimum re-show the stale warning — if reached via Back/Next bouncing after invalidation, though D-09/D-10 don't explicitly require blocking submit from confirm on staleness since `Next` gating at step 3 already prevents reaching confirm with stale credentials in the normal flow).

**Warning signs:** A test that types in a credential field, sees `Next` re-disable, retests successfully, goes Back then Next again without further edits — the wizard must NOT re-show the stale-credentials hint in that case (it's not stale anymore). Write this exact scenario as a unit test (see Validation Architecture).

## Code Examples

### Existing `buildCredentials()` add-path — reuse verbatim

```typescript
// Source: frontend/src/components/connectors/connector-form.tsx lines 112-121
function buildCredentials(): Record<string, string> | undefined {
  if (mode === 'add') {
    const creds: Record<string, string> = {};
    for (const f of fields) {
      if (values[f] && values[f].trim() !== '') {
        creds[f] = values[f];
      }
    }
    return Object.keys(creds).length > 0 ? creds : undefined;
  }
  // ... edit-mode branch unchanged, not needed in the wizard
}
```

### Existing hooks — no changes needed

```typescript
// Source: frontend/src/lib/queries/use-connectors-admin.ts
// useTestConnector() — POST /api/v1/connectors/test, retry: 0, no cache invalidation
// useCreateConnector() — POST /api/v1/connectors, invalidates queryKeys.connectors.all on success
// useConnectorTypes() — GET /api/v1/connectors/types, staleTime 5min, returns permissions[]
```

### `ResponsiveDialog` unmount-on-close guard (enables Pattern 1's reset-on-reopen)

```typescript
// Source: frontend/src/components/ui/responsive-dialog.tsx line 45
if (!open) return null;
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Single-step `ConnectorForm` for both add and edit | Add flow becomes a 4-step wizard; edit flow stays single-step | This phase (Phase 19) | Add path gains explicit test-gating and a confirm/review step; edit path unaffected — smallest blast radius per D-11 |

**Deprecated/outdated:** Nothing in this phase deprecates existing infrastructure — `ConnectorForm` remains live for edit mode.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | All 38 field definitions across `CONNECTOR_TYPES` currently have `required: True` with zero exceptions, so "all fields non-empty" is a safe proxy for "all required fields non-empty" (Pitfall 1, option 1) | Common Pitfalls #1 | LOW — verified directly via grep count (`required": True` × 38, `required": False` × 0) against `backend/app/connectors/schemas.py`; this is a code-verified fact, not a training-data guess, but is time-bound (could change if a future connector type adds an optional field) |
| A2 | `aria-current="step"` + `<ol>` (not ARIA `tablist`) is the correct, W3C-documented pattern for a non-interactive multi-step progress indicator | Architecture Patterns #2, Don't Hand-Roll | LOW-MEDIUM — confirmed via WebSearch that `aria-current="step"` is a documented enum value and that APG has no dedicated "wizard" reference pattern (so no canonical implementation to diverge from); this is a defensible synthesis rather than a single authoritative spec citation |
| A3 | Focus must move to each step's heading on **both** mobile and desktop (breaking from the existing `ConfirmModal`/`drill-panel-mobile` mobile-skip precedent) | Architecture Patterns #3 | MEDIUM — this is reasoned from vaul's documented behavior (focus scope established once, at Drawer open) combined with the fact that step content changes post-open; not verified against a live vaul-in-this-app repro during this research session, so the planner should confirm empirically (e.g., a manual mobile-viewport check) that vaul does not silently re-fight this focus move |

**If this table is empty:** N/A — see entries above; none are compliance/retention/security-critical, all are UI-mechanics decisions with bounded blast radius.

## Open Questions

1. **Should `GET /connectors/types` be enriched to carry `required`/`label`/`type` per field, or is the "assume all required" proxy (Pitfall 1, option 1) acceptable for this phase?**
   - What we know: Zero current connector types have an optional field; the wire contract change would be additive/non-breaking.
   - What's unclear: Whether "no new backend" (UX-D-02-05) is meant to also cover incidental enrichment of `GET /types` (not one of the two explicitly named endpoints), or whether it's a hard freeze on all backend files touched by this phase.
   - Recommendation: Default to option 1 (no backend change) unless the planner/user explicitly wants the richer per-field metadata surfaced now (e.g., to also improve today's client-side `isSecretField()` heuristic, which currently pattern-matches field *names* — `secret`, `key`, `password`, `token` — rather than using the backend's authoritative `type: "password"`). Flag this in the plan's assumptions rather than deciding silently.

2. **Should the confirm step re-validate staleness defensively (Pitfall 4), even though the step-3 gate should prevent reaching it with stale credentials in the normal flow?**
   - What we know: D-05/D-07/D-08 together should make it structurally impossible to reach confirm with `isTestStale === true` if gating is implemented correctly at step 3.
   - What's unclear: Whether a defensive re-check at the confirm/submit boundary is worth the extra code path versus trusting the step-3 gate as the single source of truth.
   - Recommendation: Rely on the step-3 gate as the single enforcement point (simpler, one less place to get wrong) but add the exact bounce-scenario unit test from Pitfall 4 to prove the gate actually holds under Back/Next churn.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| vaul | ResponsiveDialog mobile branch | ✓ | 1.1.2 | — |
| @tanstack/react-query | Data hooks | ✓ | ^5.100.10 | — |
| lucide-react | Icons | ✓ | ^0.383.0 | — |
| vitest / vitest-axe | Component + a11y unit tests | ✓ | see package.json | — |
| @axe-core/playwright | E2E a11y sweep | ✓ | ^4.12.1 | — |
| `npx next build` (local) | Bundle-budget measurement | ✓ (ran successfully during research; current `/dashboard/connectors` = 153 kB) | Next.js 15.5.20 | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — everything needed is already installed and verified working in this environment.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest (unit/component) + `vitest-axe` (component a11y) + Playwright (`@axe-core/playwright`, e2e) |
| Config file | `frontend/vitest.config.mts` (unit); `frontend/e2e/playwright.config.ts` (e2e) |
| Quick run command | `npm test -- connector-form src/components/connectors/wizard` (Vitest, targeted) |
| Full suite command | `npm test` (all Vitest) + `npm run test:e2e` (Playwright, requires prod build + server per existing project convention) + `npm run perf:budget` (bundle gate) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-D-02-01 | Wizard renders credentials→test→confirm in order, provider pre-selected | unit | `npm test -- add-connector-wizard` | ❌ Wave 0 |
| UX-D-02-02 | `Next` disabled until test succeeds; stale-after-edit re-disable (Pitfall 4 bounce scenario) | unit | `npm test -- use-wizard-state` | ❌ Wave 0 |
| UX-D-02-03 | `buildCredentials()` add-path still correct when lifted into the wizard's credentials step | unit | `npm test -- credentials-step` | ❌ Wave 0 |
| UX-D-02-04 | Confirm step renders `permissions[]` scope+purpose; empty-scopes copy when `permissions: []` | unit | `npm test -- confirm-step` | ❌ Wave 0 |
| UX-D-02-05 | `useTestConnector`/`useCreateConnector` called with correct bodies, no new hook created | unit | `npm test -- add-connector-wizard` | ❌ Wave 0 (reuses existing hook mocks pattern from `connector-form.test.tsx`) |
| UX-D-02-06a | `/dashboard/connectors` axe-clean in both themes | e2e | `npm run test:e2e -- a11y-routes` (already covers this route; needs prod build) | ✅ existing spec, wizard must not regress it |
| UX-D-02-06b | `/dashboard/connectors` ≤250 KB First-Load JS | build-gate | `npm run build && npm run perf:budget` | ✅ existing script, currently 153 kB |
| UX-D-02-06c | Wizard renders correctly inside vaul mobile sheet | e2e or manual | Extend `e2e/a11y-routes.spec.ts`-style mobile viewport check, or manual per UI-SPEC "Responsive (mobile vaul) Contract" | ❌ Wave 0 if automated; otherwise document as manual checkpoint |
| — | Component-level axe on the wizard tree (fast, jsdom, pre-e2e) | unit | `npm test -- add-connector-wizard.a11y` (pattern: `dashboard.a11y.test.tsx`) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `npm test -- <touched-file-glob>` (Vitest, targeted — matches existing project convention of file-scoped test runs, not whole-`tests/`-dir runs per the backend pytest lesson logged in project memory, mirrored here for frontend Vitest to keep iteration fast)
- **Per wave merge:** `npm test` (full Vitest suite) + `npm run lint` + `npm run build` (also produces the bundle numbers for `perf:budget`)
- **Phase gate:** `npm run test:e2e` (full Playwright suite, prod build + server per the project's documented local e2e setup) + `npm run perf:budget` green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `frontend/src/components/connectors/wizard/use-wizard-state.test.ts` — covers UX-D-02-02 gating + Pitfall 4 bounce scenario
- [ ] `frontend/src/components/connectors/wizard/add-connector-wizard.test.tsx` — covers UX-D-02-01, UX-D-02-05 (hook call assertions, mirroring `connector-form.test.tsx`'s `vi.mock` pattern for `useCreateConnector`/`useTestConnector`)
- [ ] `frontend/src/components/connectors/wizard/credentials-step.test.tsx` — covers UX-D-02-03
- [ ] `frontend/src/components/connectors/wizard/confirm-step.test.tsx` — covers UX-D-02-04 (including empty-`permissions[]` case)
- [ ] `frontend/src/components/connectors/wizard/add-connector-wizard.a11y.test.tsx` — component-level `vitest-axe` sweep, pattern from `dashboard.a11y.test.tsx` (mock `useConnectorTypes`/`useCreateConnector`/`useTestConnector`, render, assert `axe(container)` has no violations)
- [ ] Extend `e2e/a11y-routes.spec.ts` or add a wizard-open state to the existing `/dashboard/connectors` sweep so the axe check exercises the dialog OPEN state, not just the closed grid (current sweep likely only hits the closed-dialog DOM) — confirm during planning whether the existing sweep opens the dialog at all; if not, this is a real coverage gap predating this phase, not introduced by it
- [ ] No new test-framework install needed — Vitest, vitest-axe, Playwright, @axe-core/playwright all already configured

## Security Domain

> `security_enforcement` config key not found in `.planning/config.json` (absent = enabled per instructions) — included per default.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Connector admin routes already require `require_admin` (backend, unchanged this phase) |
| V3 Session Management | No | No session changes in this phase |
| V4 Access Control | No | Admin-gating unchanged (`require_admin` on all connector routes, backend unchanged) |
| V5 Input Validation | Yes (client-side UX only, not security-critical) | Wizard credential inputs are plain controlled `<input>` elements; no new validation library needed — same pattern as existing `ConnectorForm` |
| V6 Cryptography | No new surface | Credentials are transmitted as today (HTTPS, backend-encrypted at rest — unchanged); the wizard introduces no new credential-handling path, it reuses `buildCredentials()` verbatim |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential re-exposure via sentinel leakage | Information Disclosure | Already mitigated by T-14-07 (never send `••••••` literal) — carried over verbatim (D-12); this phase's credentials step starts with empty fields (add mode never shows a sentinel), so the sentinel-leak risk class doesn't even apply to the wizard's own code path — it only matters for the untouched edit path |
| Stale/untested credentials silently submitted | Tampering (of trust, not data) | D-08's re-test invalidation is the mitigation; Pitfall 4 documents the state-machine edge case that must be tested to prove this holds under Back/Next churn |

This phase has no new attack surface beyond what `ConnectorForm` already has (same endpoints, same admin-only gating, same credential-transmission path) — the wizard reorganizes UI flow, not the security boundary.

## Sources

### Primary (HIGH confidence)
- `frontend/src/components/connectors/connector-form.tsx` — full read, `buildCredentials()`, test-result UI, sentinel logic
- `frontend/src/app/(authed)/dashboard/connectors/page.tsx` — full read, grid/deep-link/dialog wiring
- `frontend/src/components/ui/responsive-dialog.tsx` — full read, mobile/desktop branches, unmount guard
- `frontend/src/components/ui/ConfirmModal.tsx` + `frontend/src/components/ui/focus-trap.ts` — full read, existing focus-management precedent
- `frontend/src/lib/queries/use-connectors-admin.ts` — full read, all hooks/types
- `backend/app/connectors/router.py` (lines 1-100, 95-220) — full read, `/types` handler flattening logic, `/test`/`/connectors` POST handlers
- `backend/app/connectors/schemas.py` — full read of `ConnectorTypeInfo`, `ConnectorPermission`, verified `required` field-count via grep
- `frontend/src/components/connectors/microcopy.ts` — full read, `FORM_COPY`
- `frontend/src/components/connectors/connector-form.test.tsx` — full read, existing test patterns to mirror
- `frontend/e2e/a11y-routes.spec.ts`, `frontend/e2e/fixtures/axe.ts`, `frontend/e2e/routes.ts` — full read, existing axe gate covers `/dashboard/connectors`
- `frontend/scripts/check-bundle.mjs`, `frontend/scripts/check-bundle-all.mjs` — full read, bundle-gate mechanics
- `npx next build` run live during this research (2026-07-20) — `/dashboard/connectors` = 153 kB First-Load JS [VERIFIED]
- `npm view vaul version` — `1.1.2` [VERIFIED: npm registry]
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — grepped for "stepper"/"wizard"/"step", zero hits, confirming net-new pattern claim
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — spacing/motion token values
- `.planning/phases/19-add-connector-wizard/19-CONTEXT.md`, `19-UI-SPEC.md` — full read (locked decisions + approved design contract)
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — full read

### Secondary (MEDIUM confidence)
- WebSearch: "WAI-ARIA multi-step wizard form accessibility pattern aria-current focus management step change" — cross-referenced against MDN/W3C APG general guidance; no single canonical "wizard" APG pattern exists, so the `<ol>`+`aria-current="step"` synthesis is a reasoned application of documented primitives, not a copy of one reference implementation
- WebSearch: "vaul drawer React multi-step content height change focus scroll pitfalls" — GitHub issues (emilkowalski/vaul #550, #635, #152, #168, #575, #613) confirm known vaul focus/scroll interaction quirks around keyboard and snap-points, informing the "focus must run on mobile too" recommendation (Assumption A3)

### Tertiary (LOW confidence)
- None — all findings above were either verified directly against this repository or cross-referenced against a second source

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; all versions verified against installed `node_modules` and `npm view`
- Architecture: HIGH — every reused component/hook read in full; new component structure is a straightforward decomposition with one genuinely novel piece (stepper a11y) researched via CITED sources
- Pitfalls: HIGH for #1/#2/#3 (all code-verified against this repo); MEDIUM for #4 (reasoned from the locked decisions' interactions, not yet proven against a running implementation — hence the recommended unit test)

**Research date:** 2026-07-20
**Valid until:** 30 days (stable frontend stack, no fast-moving dependencies; re-verify the 153 kB bundle number if other Phase-19-adjacent work lands first)
