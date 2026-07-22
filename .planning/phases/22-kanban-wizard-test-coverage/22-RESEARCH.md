# Phase 22: Kanban + Wizard Test-Coverage Hardening - Research

**Researched:** 2026-07-22
**Domain:** Playwright e2e test authoring (keyboard-driven drag-and-drop assertions, ARIA live-region assertions, multi-step dialog axe sweeps, network mocking) — NOT production feature work.
**Confidence:** HIGH (all claims verified by reading the actual installed library source, the actual current component source, and the actual current test infra on disk — no speculative library-capability claims)

## Summary

This phase closes two test-coverage warnings left open from Phases 18 and 19. Both gaps are about **automatable, deterministic behavior that was never exercised**, not about behavior whose correctness is genuinely unknowable without a human. Reading the actual `@dnd-kit/core` v6.3.1 source (installed in `frontend/node_modules`) proves that dnd-kit's `KeyboardSensor` really does call `event.preventDefault()` synchronously on every `start`/`end`/`cancel` keyboard activation (`Space`, `Enter`, `Escape`, `Tab` per `defaultKeyboardCodes`) — this is exactly the mechanism `kanban-card.tsx`'s CR-01 guard (`if (e.defaultPrevented) return;`) depends on, and it is a real, trusted-event-driven DOM behavior that Playwright's `page.keyboard.press()` can exercise and assert without a human or a screen reader. Likewise, `@dnd-kit/accessibility`'s `LiveRegion` renders a real `role="status" aria-live="assertive" id="DndLiveRegion-…"` DOM node containing the exact announcement string as literal text content — this is queryable and assertable in Playwright with zero AT (assistive technology) involvement, which resolves the WR-02 "screen reader" framing into a plain DOM-text assertion.

For the wizard, the Test and Confirm steps were never axe-swept because the existing spec (`connector-wizard-a11y.spec.ts`) only opens the dialog and stops at the Credentials step. Driving further requires (a) filling credentials and clicking Next (client-side gate only — no backend call), then (b) the Test step's real `POST /api/v1/connectors/test` endpoint, which the backend implements as **live outbound HTTP calls to the real provider APIs** (CrowdStrike OAuth, Nessus, Defender, etc.) — there is no sandbox/mock provider type, so a real network round-trip cannot deterministically produce a "success" state in CI/local without real credentials. The standard, deterministic, zero-side-effect approach — already precedented in this exact codebase (`tickets-kanban.spec.ts:117` mocks a mutation endpoint with `page.route()` to force a 500 for its rollback test) — is to intercept `**/api/v1/connectors/test` and `**/api/v1/connectors` with `page.route()` to drive both the success and error DOM states without touching the real backend or creating real connector rows.

**Primary recommendation:** Extend `tickets-kanban.spec.ts` with two new Playwright tests using real `page.keyboard.press('Enter')` sequences and a `#DndLiveRegion`-prefixed locator assertion (no human/VoiceOver step required — supersedes the `human_needed` framing in `18-VERIFICATION.md`/`18-HUMAN-UAT.md`); extend `connector-wizard-a11y.spec.ts` with two new `describe` blocks that drive the wizard to Test (mocked loader/success/error via `page.route`) and Confirm (real permissions from `GET /connectors/types`, mocked submit-error) and axe-sweep each state in both themes, mirroring the existing spec's dark/light pattern. Zero production code changes are anticipated.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-D-01-02 (coverage) | A ticket can be moved between columns by pointer drag, persisting via mutation w/ optimistic update + rollback — **already satisfied**; this phase adds automated coverage for CR-01 (Enter-key drag must not also open DrillPanel) and WR-02 (gated no-op drop must announce correct SR wording) | See "CR-01: Enter-key drag determinism" and "WR-02: Live-region wording" below — both are provably automatable via real `page.keyboard.press()` + a DOM-text assertion on dnd-kit's real `LiveRegion` node |
| UX-D-02-06 (coverage) | Wizard works in ResponsiveDialog/vaul; axe passes both themes; connectors route ≤250 KB — **already satisfied for the Credentials step only**; this phase extends the axe sweep to the Test step (loader/success/error) and Confirm step (permission list, sync display, submit-error) | See "Driving the wizard to Test/Confirm" and "Don't Hand-Roll: connector test mocking" below |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Playwright e2e must be invoked with `--config=e2e/playwright.config.ts` (no root `playwright.config.ts` exists; confirmed in `21-01-SUMMARY.md`'s "Issues Encountered" — this bit a prior phase).
- Frontend stack: Next.js 15 App Router + React 19 + TS 5.5 + Tailwind 3.4 — unaffected here since this phase is test-only.
- No screen may ship without empty/loading/error states — already satisfied by the existing Test/Confirm step implementations (loader spinner, success/error blocks, submit-error alert); this phase only adds test coverage for states that already exist in code.
- Don't substitute fonts / hand-pick hex colors — N/A, no new UI is authored in this phase.
- Sketch-findings skill (`sketch-findings-getvul/SKILL.md`) explicitly states its scope **excludes** "Tests, a11y audits, performance budgets — those are production concerns, not design concerns" — confirms this phase does not need to consult `state-patterns.md`/`interaction-patterns.md` for new decisions; the states being tested were already designed and shipped in Phases 18–19.

## Standard Stack

No new dependencies. This phase only extends two existing spec files using already-installed tooling.

### Core (already installed, verified via `npm ls`)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@playwright/test` | 1.61.1 [VERIFIED: npm ls] | e2e runner, real trusted-event keyboard/mouse driver | Already the project's sole e2e framework |
| `@axe-core/playwright` | 4.12.1 [VERIFIED: npm ls] | Automated WCAG 2.1 AA sweep | Already used by every other a11y spec in this repo |
| `@dnd-kit/core` | 6.3.1 [VERIFIED: npm ls + read `node_modules/@dnd-kit/core/dist/core.cjs.development.js`] | Kanban drag/keyboard sensor, `LiveRegion` announcements | Locked decision (v2.2 ROADMAP); already shipped in Phase 18 |
| `@dnd-kit/accessibility` | bundled transitive dep of `@dnd-kit/core` [VERIFIED: read `node_modules/@dnd-kit/accessibility/dist/accessibility.cjs.development.js`] | Renders the `role="status"` live region dnd-kit uses for announcements | Not directly imported by app code but is the actual DOM contract the WR-02 test must assert against |

**No installation needed** — nothing to add to `package.json`.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Real Playwright keyboard events for CR-01 | A Vitest/RTL `fireEvent.keyDown` unit test | RTL's synthetic events are dispatched directly on the target only; while jsdom's own event bubbling would likely still propagate `defaultPrevented` correctly, this is exactly the class of behavior 18-REVIEW-FIX.md flagged as "no test in this repo asserts" and explicitly recommended extending the **e2e** spec for — a real browser removes all doubt about cross-listener event-timing correctness this fix depends on. Recommend e2e only. |
| `page.route()` mocking of connector test/create endpoints | Real outbound calls to CrowdStrike/Nessus/Defender with garbage credentials | Real calls require real network egress (may be blocked/flaky in CI/sandboxes), produce a "connection error" message rather than a controlled "auth failed" message, and — for the Confirm step submit — would create a **real** `ConnectorConfig` row in the tenant's Postgres (no backend re-validation of the test result before create; see Pitfall below) with no built-in cleanup. `page.route()` mocking is deterministic, network-independent, and side-effect-free — the codebase's own precedent (`tickets-kanban.spec.ts:117`). |
| Querying dnd-kit's live region via `getByRole('status')` | A dedicated id-prefix locator (`[id^="DndLiveRegion"]`) | `role="status"` is not unique on this page — `kanban-column.tsx`'s empty-state (`EmptyState`) also renders `role="status"`. Use the id-prefix locator to avoid ambiguity; do not rely on `getByRole('status')` alone. |

## Architecture Patterns

### Pattern 1: Real-event keyboard drag assertion (CR-01)

**What:** Assert dnd-kit's `KeyboardSensor` actually consumes `Enter` (calls `preventDefault()`) on both drag-start and drag-end, so `kanban-card.tsx`'s guard suppresses `onOpen` (DrillPanel) on both presses.

**Why this is provably deterministic, not a "maybe":**
```js
// Source: frontend/node_modules/@dnd-kit/core/dist/core.cjs.development.js (installed v6.3.1)
// lines ~1092-1106
KeyboardCode["Space"] = "Space";
KeyboardCode["Enter"] = "Enter";
const defaultKeyboardCodes = {
  start: [KeyboardCode.Space, KeyboardCode.Enter],
  cancel: [KeyboardCode.Esc],
  end: [KeyboardCode.Space, KeyboardCode.Enter, KeyboardCode.Tab]
};
// lines ~1320, 1328, 1337, 1369 — each of the start/end/cancel key handlers:
event.preventDefault();
```
`Enter` is in BOTH `start` and `end` — and every one of those branches calls `event.preventDefault()` on the real, trusted `KeyboardEvent` synchronously, before `kanban-card.tsx`'s own `handleKeyDown` checks `e.defaultPrevented`. Playwright's `page.keyboard.press('Enter')` dispatches a real, trusted browser `KeyboardEvent` through the actual DOM event pipeline (not a synthetic RTL `fireEvent`), which is exactly the mechanism this fix depends on.

**Example (extend `frontend/e2e/tickets-kanban.spec.ts`):**
```typescript
// New test, sibling to the existing 'keyboard drag' test (which uses Space).
test('keyboard drag with Enter does not open the DrillPanel', async ({ page }) => {
  await page.goto('/dashboard/tickets?view=board');
  await waitForNav(page, 1280);
  await page.waitForLoadState('networkidle');

  const cards = page.locator('[data-ticket-id]');
  if ((await cards.count()) === 0) {
    test.skip(true, 'no seeded tickets — cannot assert board keyboard drag');
    return;
  }
  const firstCard = cards.first();
  const ticketId = await firstCard.getAttribute('data-ticket-id');
  await firstCard.focus();

  // Sanity: Enter on a NON-dragging, focused card DOES open the drill (separate assertion,
  // can be a second test) — confirms the guard is branch-specific, not "Enter never opens drill".

  // Pick up with Enter (dnd-kit consumes it -> preventDefault -> onOpen suppressed).
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toHaveCount(0); // DrillPanel not opened mid-drag

  for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowRight'); // -> Blocked column
  await page.keyboard.press('Enter'); // drop -> reason prompt opens, NOT DrillPanel

  await expect(page.getByRole('dialog')).toHaveCount(0); // still no DrillPanel after drop
  const saveButton = page.getByRole('button', { name: /save/i });
  await saveButton.waitFor({ state: 'visible', timeout: 5_000 });
  await saveButton.click();

  await expect(
    page.locator('[data-column="blocked"]').locator(`[data-ticket-id="${ticketId}"]`),
  ).toBeVisible({ timeout: 5_000 });
});
```
Note `KanbanReasonPrompt` uses `role="group"` (post-WR-05 fix, not `role="dialog"`), so `getByRole('dialog')` unambiguously targets only the DrillPanel (`drill-panel.tsx:95`, `role="dialog" aria-modal="false"`) — no collision.

### Pattern 2: DOM-text assertion on dnd-kit's real live region (WR-02)

**What:** Assert the exact announcement string dnd-kit's `LiveRegion` renders on a gated no-op drop, without any screen reader.

**Why this works — the live region is real, visible-to-Playwright DOM, not an internal callback:**
```js
// Source: frontend/node_modules/@dnd-kit/accessibility/dist/accessibility.cjs.development.js (installed)
function LiveRegion({ id, announcement, ariaLiveType = 'assertive' }) {
  return React.createElement('div', {
    id,
    style: { position: 'fixed', top: 0, left: 0, width: 1, height: 1, margin: -1,
             border: 0, padding: 0, overflow: 'hidden', clip: 'rect(0 0 0 0)',
             clipPath: 'inset(100%)', whiteSpace: 'nowrap' },
    role: 'status',
    'aria-live': ariaLiveType,
    'aria-atomic': true,
  }, announcement);
}
```
`useUniqueId("DndLiveRegion")` (core.cjs.development.js:104) generates the `id` — `[id^="DndLiveRegion"]` is a stable, unique locator (does NOT collide with `EmptyState`'s `role="status"` nodes, which have no such id prefix).

**Example (extend `frontend/e2e/tickets-kanban.spec.ts`):**
```typescript
test('gated no-op drop announces "returned to its column", not a false success', async ({ page }) => {
  await page.goto('/dashboard/tickets?view=board');
  await waitForNav(page, 1280);
  await page.waitForLoadState('networkidle');

  const openColumn = page.locator('[data-column="open"]');
  const openCard = openColumn.locator('[data-ticket-id]').first();
  if ((await openCard.count()) === 0) {
    test.skip(true, 'no Open tickets seeded — cannot assert read-only -> read-only gated drop');
    return;
  }
  await openCard.focus();
  const liveRegion = page.locator('[id^="DndLiveRegion"]');

  await page.keyboard.press('Space'); // pick up
  await page.keyboard.press('ArrowRight'); // -> In progress (still read-only lane)
  await page.keyboard.press('Space'); // drop -> gated no-op, snaps back

  await expect(liveRegion).toContainText(/returned to its column/i);
  await expect(liveRegion).not.toContainText(/^Moved ticket/i);
});
```
A committed-move sibling test (Open → Blocked) already exists implicitly via the current `keyboard drag` test; optionally assert `liveRegion` text there too (`/Moved ticket .* to the Blocked column/i`) to prove both branches of the WR-02 fix, not just the gated one.

### Pattern 3: Driving the wizard to Test/Confirm for axe sweeps (UX-D-02-06)

**What:** Extend `connector-wizard-a11y.spec.ts` past the Credentials step it currently stops at.

**Real backend behavior that shapes the test design (verified by reading `backend/app/connectors/`):**
- `POST /api/v1/connectors/test` (`backend/app/connectors/router.py:131-136` → `app/connectors/tester.py`) makes **real outbound `httpx` calls** to the provider's live API (CrowdStrike OAuth token endpoint, Nessus `/server/status`, Microsoft Defender OAuth, etc.) — [VERIFIED: read `tester.py`]. There is no local/mock connector type. A "success" state cannot be produced deterministically without real credentials.
- `POST /api/v1/connectors` (`backend/app/connectors/service.py:58-77`, `create_connector`) does **not** re-validate that a test passed — it stores whatever `credentials` dict it's given [VERIFIED: read `service.py`]. This is a real latent gap (not this phase's concern to fix) but means a real create-with-garbage-credentials call would silently succeed and leave a row in the DB — reason enough to mock rather than hit the real endpoint even for the "happy path" Confirm-step render.
- `GET /api/v1/connectors/types` (`router.py:52`, backed by the static `CONNECTOR_TYPES` dict in `schemas.py`) is safe to hit for real — it returns real `fields`/`permissions` metadata with no side effects. The Confirm step's "Required access" permission list should be axe-swept against this **real** data (no mocking needed there).

**Recommended interception pattern** (mirrors `tickets-kanban.spec.ts:117`'s existing `page.route()` precedent):
```typescript
// Loader state: delay the mocked response so the spinner + "Testing…" label render
// long enough for axe to sweep it.
await page.route('**/api/v1/connectors/test', async (route) => {
  await new Promise((r) => setTimeout(r, 300));
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, message: 'Successfully authenticated' }),
  });
});
// Fill required fields (per connector type's `fields[]`), click Test, assert testMutation.isPending
// UI is visible immediately after click (before the 300ms delay resolves) -> axe sweep -> await result.

// Error state: same route, body: { success: false, message: 'Authentication failed: HTTP 401' }.

// Confirm-step submit-error: mock POST /api/v1/connectors -> 500, assert role="alert" formError block.
```
Advancing past Credentials requires filling every field returned by the selected connector type (per `use-wizard-state.ts`'s `canAdvanceFrom('credentials')`: `fields.length > 0 && fields.every(f => values[f].trim() !== '')`) — the existing spec's provider-agnostic `[data-add-connector]` selector strategy should be kept, but the new test needs to read each field's `name`/`label`/`type` from the rendered form (credentials-step renders one `<input>` per field) rather than hardcoding a specific connector type's field names, since "a fresh test tenant may have any subset of connector types already configured" (per the existing spec's own comment).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Simulating a screen-reader announcement | A custom ARIA live-region polling utility, or skipping to a human-only VoiceOver/NVDA step | A Playwright locator on dnd-kit's real `[id^="DndLiveRegion"]` node + `toContainText()` | The announcement is already a literal DOM text node — no synthesis needed; this is the same DOM the AT would read from |
| Detecting whether dnd-kit consumed a keypress | A custom keyboard-event harness / manual QA checklist | Real `page.keyboard.press()` + `e.defaultPrevented` is already implemented in `kanban-card.tsx`; test it via the DOM outcome (`getByRole('dialog')` count) not the internal event object | `defaultPrevented` is not independently observable from Playwright — assert the downstream DOM effect (drill panel absent) instead, which is what actually matters |
| Faking a passing connector test | A test-only "MOCK" connector type added to the backend `CONNECTOR_TYPES` dict | `page.route()` interception of `POST /api/v1/connectors/test` | Adding a backend-only test fixture connector type is production-code scope creep for a test-coverage phase; `page.route()` achieves the same determinism with zero backend changes |

**Key insight:** Every "needs a human" flag left over from Phases 18/19 was flagged because no *existing* automated test happened to exercise the code path — not because the behavior is inherently unobservable. In both cases the actual DOM/event surface (`role="dialog"` presence, `role="status"` live-region text) is fully inspectable by Playwright. Treat the `human_needed` framing in `18-VERIFICATION.md` as superseded once these tests are authored and passing live.

## Common Pitfalls

### Pitfall 1: Confusing "requires human/AT verification" with "requires a live screen reader"
**What goes wrong:** Concluding CR-01/WR-02 can only be closed by a manual VoiceOver/NVDA pass (as `18-HUMAN-UAT.md` currently frames them), and therefore treating this phase as impossible to fully automate.
**Why it happens:** The original code review (`18-REVIEW.md`) and verification (`18-VERIFICATION.md`) were written before anyone inspected dnd-kit's actual source for whether the announcement text and the `preventDefault()` call are DOM-observable — they reasoned from "the unit suite can't assert screen-reader text" (true) to "only a human can" (not true — Playwright can, via the DOM).
**How to avoid:** Write the two new Playwright tests above; if they pass live, close `18-HUMAN-UAT.md` items 1 and 2 as automated rather than leaving them pending indefinitely.
**Warning signs:** If a plan for this phase still proposes a `*-HUMAN-UAT.md` entry for CR-01/WR-02 instead of an e2e test, that's a signal the plan didn't verify the dnd-kit source claims above.

### Pitfall 2: Driving the wizard's Test step against the real backend
**What goes wrong:** A naive test fills real-looking-but-fake credentials and clicks "Test connection" expecting a controllable result — but the request goes out over the real network to `api.crowdstrike.com`/etc., which either times out (slow test, possible CI egress block) or returns a real HTTP error whose exact message text differs from what the frontend's own copy implies, making the "success" DOM state unreachable at all in this environment.
**Why it happens:** The endpoint's name (`/connectors/test`) suggests a test/sandbox surface, but reading `tester.py` shows it's a thin wrapper directly around provider SDK-equivalent httpx calls — there is no "TEST" connector type.
**How to avoid:** Always mock `**/api/v1/connectors/test` (and `**/api/v1/connectors` for the Confirm-step submit-error case) via `page.route()`. Only the Confirm step's permission-list/sync-interval sections should read real data (`GET /connectors/types`).
**Warning signs:** A test that takes >5s per assertion (real network round-trip) or is flaky specifically in CI but not locally.

### Pitfall 3: `getByRole('status')` ambiguity
**What goes wrong:** Asserting on `page.getByRole('status')` for the dnd-kit announcement resolves multiple elements (dnd-kit's live region AND `kanban-column.tsx`'s `EmptyState`, which also uses `role="status"`) — `.first()` or a strict-mode violation error results.
**Why it happens:** Both are legitimately `role="status"` per ARIA spec; they're for different purposes.
**How to avoid:** Use `page.locator('[id^="DndLiveRegion"]')` instead — unique to dnd-kit's own live region.

### Pitfall 4: Claiming an axe/e2e pass without a live prod-build run (recurring anti-pattern, project memory `getvul-axe-sweep-not-run-during-exec`)
**What goes wrong:** A plan/summary states "axe sweep passes" or "e2e green" based on authoring the test correctly, without actually running `npm run build && npm run start` and executing Playwright against the live server.
**Why it happens:** Running the full local e2e gate takes real setup time (prod build + server + admin login) and is easy to skip when the code "looks right."
**How to avoid:** Follow the exact recipe validated live in `21-01-SUMMARY.md` (below, Validation Architecture section) — every new test in this phase MUST be run against a real `npm run build` + `npm run start` before being reported as passing, with pasted, unedited terminal output (not paraphrased).
**Warning signs:** A SUMMARY.md that describes what a test "should" assert without a pasted terminal transcript showing the actual pass/fail count.

## Code Examples

### Existing precedent for `page.route()` mocking (already in this codebase)
```typescript
// Source: frontend/e2e/tickets-kanban.spec.ts:117-119 (existing, unmodified)
await page.route('**/api/v1/tickets/*/blocked', (route) =>
  route.fulfill({ status: 500, body: '{}' }),
);
```

### Existing precedent for both-theme axe sweep (already in this codebase)
```typescript
// Source: frontend/e2e/connector-wizard-a11y.spec.ts:59-68 (existing, unmodified)
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { window.localStorage.setItem('getvul_theme', 'light'); } catch {}
  });
});
// ...then a defensive re-assert/force of data-theme="light" after goto (Pitfall 2 in 19-RESEARCH.md).
```
Reuse this exact `beforeEach` pattern for the new Test-step/Confirm-step describe blocks — do not invent a new theme-forcing mechanism.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| CR-01/WR-02 routed to `*-HUMAN-UAT.md` as pending-human items | Both are closeable via real Playwright keyboard/DOM assertions (this research) | This phase (2026-07-22) | `18-HUMAN-UAT.md`'s two pending items can be marked resolved-by-automation once the new tests pass live, rather than remaining permanently pending |
| `connector-wizard-a11y.spec.ts` axe-sweeps only the Credentials step | Extend to Test (loader/success/error) + Confirm (permissions/sync/submit-error) | This phase | Closes the last of the three wizard steps rendered inside the dialog; Provider-pick step is outside the dialog (page grid) and already covered by the base `a11y-routes.spec.ts` sweep of `/dashboard/connectors` |

**Deprecated/outdated:** None — no library versions or APIs are changing in this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Playwright's `page.keyboard.press('Enter')` dispatches a trusted, native `KeyboardEvent` indistinguishable (for `preventDefault()` propagation purposes) from a real user keypress, such that dnd-kit's real document-level sensor listener and React's synthetic delegated listener both observe the same `defaultPrevented` state | Pattern 1 (CR-01) | If Playwright's CDP-driven key dispatch behaves differently from a real OS-level keypress in some edge case, the new test could pass in CI while a genuinely different code path exists for real hardware keyboards. Low risk — this is Playwright's core design guarantee and is exactly the class of test `18-REVIEW-FIX.md` itself recommended ("extending `tickets-kanban.spec.ts` to press Enter"), but it has not been run live yet in this research session. |
| A2 | The wizard's Test step can render its `isPending` (loader) state long enough for axe to sweep it, given a `page.route()` handler with an artificial delay (e.g. 300ms) before `route.fulfill()` | Pattern 3 | If the delay is too short relative to axe's analysis time, the loader assertion could flake. Mitigate by asserting `testMutation.isPending` DOM markers (disabled button + `Loader2` icon) are visible before calling `analyze()`, not just relying on timing. |

**If empty:** N/A — see table above; two low-risk assumptions logged for planner awareness, neither blocks planning.

## Open Questions (RESOLVED)

_All open questions from the phase's own framing were resolved during this research session:_

1. **Can Playwright's keyboard driver deterministically assert CR-01 (status changed AND no DrillPanel opened)?**
   - What we know: Yes — resolved above via reading the installed `@dnd-kit/core` source. `Enter` is a `start` AND `end` keyboard code; every branch calls `event.preventDefault()` on the real event.
   - What's unclear: Nothing blocking; only the low-risk Assumption A1 above.
   - Recommendation: Author the test per Pattern 1; do not add a new `*-HUMAN-UAT.md` entry for this item.

2. **How does the existing spec authenticate, and can the wizard's Test/Confirm steps be driven without a mock backend?**
   - What we know: Auth is via the `setup` Playwright project (`e2e/auth/setup.ts`), which logs in as `admin@getvul.local` against a real running backend and persists `storageState`. The Test/Confirm steps CAN be driven with a real backend up to the point of the outbound-network-dependent test/create calls, which must be intercepted via `page.route()` per Pattern 3.
   - What's unclear: Nothing blocking.
   - Recommendation: Keep the real backend running (per the local e2e recipe below) for `GET /connectors/types` and page auth; mock only `POST /connectors/test` and `POST /connectors`.

3. **Is there a risk of DB pollution from real `POST /connectors` calls during these new tests?**
   - What we know: `create_connector` does not re-validate credentials server-side, so a real call with a mocked-passing client-side gate would create a real row.
   - What's unclear: Whether any OTHER phase-22-adjacent test might accidentally hit the real endpoint.
   - Recommendation: Mock `POST /connectors` for all new Confirm-step tests (submit-error path only needs the mock to return 500; no successful real create is needed to axe-sweep the pre-submit Confirm DOM).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Compose (postgres/redis/backend/frontend) | Local e2e gate (real login, real `GET /connectors/types`) | Not probed this session (assume per project memory `getvul-local-e2e-perf-gate`, used successfully in Phases 15/18/19/20/21) | — | — |
| `npx playwright test --config=e2e/playwright.config.ts` | All new tests | ✓ (installed, `@playwright/test@1.61.1`) | 1.61.1 | — |
| `@axe-core/playwright` | Axe sweeps | ✓ (installed) | 4.12.1 | — |
| Real outbound network to provider APIs (CrowdStrike, Nessus, etc.) | NOT required — deliberately avoided via `page.route()` mocking | N/A | — | `page.route()` interception (chosen approach, not a fallback) |

**Missing dependencies with no fallback:** None identified — this phase needs nothing beyond what Phases 15/18/19/20/21 already required and used successfully.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Playwright `@playwright/test` 1.61.1 [VERIFIED: npm ls] |
| Config file | `frontend/e2e/playwright.config.ts` (no root config — MUST pass `--config=e2e/playwright.config.ts` explicitly, per `21-01-SUMMARY.md`'s documented gotcha) |
| Quick run command (CR-01/WR-02 only) | `cd frontend && npx playwright test e2e/tickets-kanban.spec.ts --config=e2e/playwright.config.ts --project=chromium-a11y` |
| Quick run command (wizard axe only) | `cd frontend && npx playwright test e2e/connector-wizard-a11y.spec.ts --config=e2e/playwright.config.ts --project=chromium-a11y` |
| Full suite command | `cd frontend && npm run test:e2e -- --project=chromium-a11y` (plus `--project=firefox-transitions`/`firefox-smoke` for the unrelated existing Firefox-scoped specs — not required for this phase's new tests, which are Chromium-scoped like the rest of `a11y-routes`/`tickets-kanban`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-D-01-02 (CR-01 coverage) | Enter-key drag changes status without opening DrillPanel (both pickup and drop presses) | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "Enter" --config=e2e/playwright.config.ts --project=chromium-a11y` | ❌ Wave 0 — new test to author |
| UX-D-01-02 (WR-02 coverage) | Gated no-op drop (read-only→read-only) announces "returned to its column"; committed drop announces "Moved ticket … to the … column" | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "announce" --config=e2e/playwright.config.ts --project=chromium-a11y` | ❌ Wave 0 — new test to author |
| UX-D-02-06 (Test-step axe) | Test step's loader / success / error states each have zero critical/serious axe violations, both themes | e2e | `npx playwright test e2e/connector-wizard-a11y.spec.ts -g "Test step" --config=e2e/playwright.config.ts --project=chromium-a11y` | ❌ Wave 0 — new test to author |
| UX-D-02-06 (Confirm-step axe) | Confirm step's permission list / sync display / submit-error each have zero critical/serious axe violations, both themes | e2e | `npx playwright test e2e/connector-wizard-a11y.spec.ts -g "Confirm step" --config=e2e/playwright.config.ts --project=chromium-a11y` | ❌ Wave 0 — new test to author |
| (regression guard) | No production-code regression; both routes stay ≤250 KB | perf | `npm run perf:budget` | ✅ existing script; baseline already established (`/dashboard/tickets` 167.0 kB, `/dashboard/connectors` 156.0 kB per `18-VERIFICATION.md`/`19-VERIFICATION.md`) |

### Sampling Rate
- **Per task commit:** the specific new test's `-g "<title>"`-filtered run against a locally running dev/prod server.
- **Per wave merge:** full `tickets-kanban.spec.ts` + `connector-wizard-a11y.spec.ts` files (not just the new tests — guard against regressing the pre-existing passing tests in the same files).
- **Phase gate:** `npm run build && npm run start` (prod build, port 3000) then the full commands above, PLUS `npm run perf:budget`, following the exact recipe validated live in `21-01-SUMMARY.md` and documented in project memory `getvul-local-e2e-perf-gate`. Every claim of "passes" in this phase's SUMMARY/VERIFICATION MUST be backed by pasted, unedited terminal output — per the recurring anti-pattern flagged in project memory `getvul-axe-sweep-not-run-during-exec`.

### Wave 0 Gaps
- [ ] `frontend/e2e/tickets-kanban.spec.ts` — add "keyboard drag with Enter does not open the DrillPanel" test (CR-01)
- [ ] `frontend/e2e/tickets-kanban.spec.ts` — add "gated no-op drop announces returned-to-column wording" test (WR-02), and optionally strengthen the existing "keyboard drag" test with a live-region assertion for the committed-move wording
- [ ] `frontend/e2e/connector-wizard-a11y.spec.ts` — add a "Test step" describe block (loader/success/error × dark/light) that fills credentials, clicks Next, mocks `POST /connectors/test`, and axe-sweeps each of the 3 states
- [ ] `frontend/e2e/connector-wizard-a11y.spec.ts` — add a "Confirm step" describe block (permission list/sync display × dark/light, submit-error via mocked `POST /connectors` 500) and axe-sweeps each state
- No new framework/config install needed — `playwright.config.ts`'s `chromium-a11y` project already collects all spec files with no `testMatch` restriction, so no new project entry is required.

## Security Domain

This is a test-authoring-only phase; no new production endpoints, auth surfaces, or input-handling code are introduced. ASVS review is minimal by design.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No change — tests reuse the existing `auth/setup.ts` storageState flow |
| V4 Access Control | No | No change |
| V5 Input Validation | N/A | No new input paths; the wizard's existing field validation (`use-wizard-state.ts`) is untouched |
| V6 Cryptography | No | No change — `POST /connectors` credential encryption (`encrypt_value`) is untouched and, per this phase's mocking strategy, never actually invoked with test data |

### Known Threat Patterns for {stack}
Not applicable — no new attack surface. One pre-existing, out-of-scope observation surfaced incidentally during this research: `create_connector` (`backend/app/connectors/service.py:58-77`) does not require a passing `/connectors/test` result before persisting credentials, meaning a caller who bypasses the frontend wizard entirely (e.g. a direct API call) can store arbitrary unvalidated credentials. This is a pre-existing backend behavior, not introduced or worsened by this phase, and is explicitly out of scope (this phase mocks around it rather than fixing it) — flagged here only for awareness, not as a phase-22 action item.

## Sources

### Primary (HIGH confidence)
- `frontend/node_modules/@dnd-kit/core/dist/core.cjs.development.js` (installed v6.3.1) — `KeyboardCode`/`defaultKeyboardCodes`/`preventDefault()` call sites, read directly
- `frontend/node_modules/@dnd-kit/accessibility/dist/accessibility.cjs.development.js` (installed) — `LiveRegion` component source, read directly
- `backend/app/connectors/tester.py`, `backend/app/connectors/service.py`, `backend/app/connectors/router.py`, `backend/app/connectors/schemas.py` — read directly to confirm the real-network-call behavior and the create-without-re-validation gap
- `frontend/src/components/tickets/kanban-card.tsx`, `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx`, `frontend/src/components/tickets/kanban-reason-prompt.tsx` — current CR-01/WR-02/WR-05 fixed source, read directly
- `frontend/src/components/connectors/wizard/{add-connector-wizard,test-step,confirm-step,use-wizard-state,wizard-stepper}.tsx`, `frontend/src/components/connectors/microcopy.ts` — current wizard implementation, read directly
- `frontend/e2e/{tickets-kanban,connector-wizard-a11y,routes,playwright.config,auth/setup,fixtures/axe}.ts/.tsx` — current e2e infra, read directly
- `.planning/phases/18-tickets-kanban-board/{18-REVIEW,18-REVIEW-FIX,18-VERIFICATION,18-HUMAN-UAT}.md` — origin and exact wording of CR-01/WR-02
- `.planning/phases/19-add-connector-wizard/19-REVIEW.md` — wizard review findings (WR-01..03, none of which are this phase's scope but confirm no blockers)
- `.planning/phases/21-page-transition-verification/21-01-SUMMARY.md` — the validated local e2e recipe (`npm run build` → `npm run start` :3000 → `--config=e2e/playwright.config.ts --project=…`) and the "paste real output, not paraphrase" discipline this phase must follow
- `npm ls @dnd-kit/core @axe-core/playwright @playwright/test vitest` (run live in this session) — exact installed versions

### Secondary (MEDIUM confidence)
- None used — all claims for this phase were verifiable directly against installed source/config, no WebSearch was needed.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; versions confirmed via `npm ls` against the actual installed `node_modules`
- Architecture (CR-01/WR-02 automatability): HIGH — verified by reading the actual installed `@dnd-kit` source, not training-data assumptions about dnd-kit's API
- Architecture (wizard driving strategy): HIGH — verified by reading the actual backend connector service/tester/router/schemas source
- Pitfalls: HIGH — each pitfall is grounded in a specific, cited line of either the installed library source or the actual backend/frontend source

**Research date:** 2026-07-22
**Valid until:** 30 days (stable internal codebase; no external API drift risk since no new third-party dependencies are introduced) — re-verify library source claims if `@dnd-kit/core` is upgraded before this phase executes.
