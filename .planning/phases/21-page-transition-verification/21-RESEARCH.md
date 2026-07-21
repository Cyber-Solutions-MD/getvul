# Phase 21: Page-transition verification - Research

**Researched:** 2026-07-21
**Domain:** Playwright e2e test-hardening (Next.js 15 App Router View Transitions) + GSD verification-artifact authoring
**Confidence:** HIGH (all core findings grounded in direct codebase reads; e2e idiom cross-verified with current web guidance)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Drive **real Next.js router navigation**, not the synthetic `history.pushState` +
  `PopStateEvent` proxy. The new test must exercise the actual App Router segment-diffing path
  so the assertion is trustworthy.
- **D-02:** Cover **BOTH cases** with real navigation:
  - **No-fade case (D-02 from Phase 17):** a `searchParams`-only change (e.g. `?drill=…` /
    `?tab=…` via a real `router.replace`) must produce **0** `authed-page-content` view-transition
    animations — the template is keyed on the segment, so searchParams never remount it.
  - **Fade case (D-11 from Phase 17):** a **pathname change while a DrillPanel is open** must
    fade the content region (drill included) — the panel goes out with the outgoing snapshot,
    no special close choreography, no layout shift.
- **D-03:** Prefer driving the real `router.replace`/`router.push` over depending on seeded
  interactive data (clicking a live vuln row). Rationale: Phase 17 fell back to the proxy
  precisely because interactive controls weren't trivially reachable in a stateless e2e
  session — a real `router` drive gets genuine segment behavior without a fixture dependency.
  (If the planner finds a reachable real control cheaply, driving the actual UI click is an
  acceptable upgrade — the point is "real routing, not PopStateEvent.")
- **D-04:** Add an **automated e2e assertion** (Firefox project) that the **CSS-keyframe
  fallback** cross-fade runs on `(authed)/template.tsx` mount for a real pathname change —
  Firefox lacks the View Transitions API, so it exercises the D-06 fallback path. Planner to
  confirm the existing `e2e/playwright.config.ts` Firefox project supports the assertion, and
  that the D-12 reduced-motion blanket still suppresses it.
- **D-05:** Add a **dedicated close-path test**: open a DrillPanel, trigger an Esc/clickaway
  close (which mutates searchParams), and assert **no** `authed-page-content` fade fires AND
  **no layout shift** — directly exercising the UX-D-06-04 race guard.
- **D-06:** The user will **perform the perceptual sign-off during execution, guided**. The
  executor (or orchestrator) stands up the app (or the user runs it), presents a concise
  perceptual checklist, and the user signs off item-by-item; results are recorded in
  `17-HUMAN-UAT.md`. **This is a `human-action` checkpoint** — plan for a real interactive
  pause, not an auto-approved gate.
- **D-07:** The UAT checklist items to record: (a) cross-fade *feel* — snappy 220–320ms
  pure-opacity, no drift; (b) chrome *stillness* — sidebar/topbar do not move or fade during a
  route change; (c) DrillPanel-during-transition — an open drill fades out cleanly with the
  content on a pathname change, no stuck/ghost panel; (d) Firefox fallback *feel* — the
  cross-fade looks equivalent under the CSS-keyframe path.
- **D-08:** On successful sign-off, mark `17-HUMAN-UAT.md` status closed/resolved AND clear the
  `human-UAT checkpoint OUTSTANDING` line in STATE.md (SC#2 requires both).
- **D-09:** Produce a goal-backward `17-VERIFICATION.md` confirming UX-D-06-01..05 against the
  shipped code + the newly-hardened tests. Standard `gsd-verifier` artifact, back-dated in
  intent to Phase 17's goal but authored now.

### Claude's Discretion

- Exact structure/wording of the new e2e assertions and how the real `router.replace` is
  invoked from Playwright (e.g. `page.evaluate` against the Next router vs. a reachable in-app
  control).
- Whether the Firefox fallback assertion lives in `page-transitions.spec.ts` or a sibling spec.
- Layout-shift measurement technique for D-05 (CLS observer vs. bounding-box before/after).

### Deferred Ideas (OUT OF SCOPE)

- **Navigation pending indicator** (top loading bar during navigation to `force-dynamic`
  routes) — carried over from Phase 17's deferred list; a new capability, not part of UX-D-06
  verification. Note for a future backlog item if analysts report the fade alone is
  insufficient feedback.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-D-06-01 | Route changes within the `(authed)` shell animate with a cross-fade via the View Transitions API (single `template.tsx`). | §Code Examples "Existing TEST A" + §Architecture Patterns Pattern 1 confirm the mechanism is sound; §Validation Architecture maps this to the existing `page-transitions.spec.ts` real-pathname test (already real — clicks the nav Link) plus the new goal-backward `17-VERIFICATION.md`. |
| UX-D-06-03 | A CSS-animation fallback keeps navigation clean in browsers without View Transitions support (no jank/broken nav in Firefox). | §Common Pitfalls Pitfall 3 + §Code Examples "Firefox fallback assertion" — concretely how to detect `page-fade-in` on Firefox and why the current `firefox-smoke` project's `testMatch` won't pick it up without a config change. |
| UX-D-06-04 | Transitions do not race with DrillPanel Esc/clickaway close and cause no layout shift. | §Architecture Patterns Pattern 2 (URL-driven DrillPanel deep-link, no fixture dependency) + §Code Examples "Real DrillPanel + real pathname nav" and "Close-race + layout-shift test" — the concrete idiom that satisfies D-01/D-02/D-03/D-05 without touching Next's internal router object. |
</phase_requirements>
</user_constraints>

## Project Constraints (from CLAUDE.md)

- Frontend stack: Next.js 15 App Router + React 19 + TypeScript 5.5 + Tailwind 3.4 — confirmed
  installed version is **Next.js 15.5.20**, **@playwright/test 1.61.1** `[VERIFIED: npm ls]`.
- Sketch-findings skill (`foundation.md` §Motion, `app-shell.md`) is authoritative for
  perceptual "feel" — durations (120/220/320/520ms), easing curves, and the persistent-chrome
  contract are locked; the new tests and the UAT checklist must reference these, not invent new
  language.
- Don't ship a screen without empty/loading/error states — N/A here (no new screens; this
  phase adds tests + docs only).
- No hex colors / font substitution rules — N/A (no visual changes).

## Summary

Phase 21 is **not a build phase** — it is a verification-rigor phase closing three concrete
gaps against already-shipped, e2e-green Phase 17 code. All three success criteria are
achievable with **no production code changes**: (1) a Playwright spec hardening pass that
replaces a synthetic `PopStateEvent` proxy with genuine Next.js App Router navigation, (2) a
guided human-sign-off session persisted to `17-HUMAN-UAT.md`, and (3) a goal-backward
`17-VERIFICATION.md` written against the hardened tests + shipped code.

The most important finding from grounding this in the real codebase: **the DrillPanel's open
state is driven entirely by URL search params** (`?cve=<id>&open=drill`), read directly by
`drill-panel.tsx` (`isOpen = params.get('open') === 'drill' && effectiveId !== null`) with no
server round-trip gating the panel *shell* from mounting. This means the planner does **not**
need a seeded/interactive vuln row to open a DrillPanel in e2e — `page.goto('/dashboard/vulnerabilities?cve=<any-id>&open=drill')`
mounts the real `<aside role="dialog" data-drill-panel>` deterministically, with zero fixture
dependency. Combined with the sidebar's real `<Link>` navigation (already used in the existing
spec) and the vulnerabilities page's always-rendered severity `ChipBar` (a real control that
calls `router.replace` with a searchParams-only mutation, confirmed via its own unit test:
"chip click is synchronous — calls router.replace immediately with axis key flipped"), **every
required navigation in this phase can be driven by clicking a real, always-present UI element**
— no `page.evaluate` reaching into Next's internal router instance is needed, sidestepping the
documented instability of that pattern entirely.

The other material finding: the current `firefox-smoke` Playwright project's `testMatch` is
hardcoded to `/smoke\.spec\.ts/` — a new Firefox-targeted assertion (D-04) will silently never
run unless the planner either broadens that regex or adds a new project. This must be an
explicit task, not an assumption.

**Primary recommendation:** Reuse the existing `document.getAnimations()` polling harness
verbatim; swap only the *trigger* — replace the `history.pushState`/`PopStateEvent` block with
(a) a URL deep-link `page.goto` to open the DrillPanel, (b) a real sidebar `<Link>` click for
the pathname-change/fade case, (c) a real `ChipBar` severity-chip click for the
searchParams-only/no-fade case, and (d) the DrillPanel's own Escape-key handler for the
dedicated close-race + layout-shift test. Add a new Firefox-scoped test (new project or
broadened `testMatch`) asserting the `page-fade-in` keyframe via `getAnimations()` filtered by
`animationName`, confirmed suppressed under `prefers-reduced-motion` by the existing D-12
blanket (no new CSS needed — the blanket already catches ordinary keyframe animations on real
elements, unlike the VT pseudo-elements which needed an explicit second rule).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @playwright/test | 1.61.1 `[VERIFIED: npm ls, frontend/package.json]` | e2e test runner | Already the project's only e2e framework; no new dependency needed for this phase |
| Next.js | 15.5.20 `[VERIFIED: npm ls]` | App Router, real navigation under test | Locked stack; App Router segment-diffing is exactly what's under verification |

### Supporting

None — this phase adds no new libraries. It is entirely additive test code + Markdown docs
against the existing stack.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Real UI clicks (Link, ChipBar chip, Escape key) | `page.evaluate()` reaching into Next's internal router instance (e.g. attempting to call an internal `appRouterContext` method) | Internal router internals are not a public, stable API surface across Next.js versions — `[ASSUMED]` this is unreliable/unsupported; real UI interaction is both more "real" (per D-01's own rationale) and avoids version coupling. No installation or version check needed since the real-click path is used. |
| Bounding-box before/after comparison for layout shift | `PerformanceObserver({type: 'layout-shift'})` (Web CLS API) | The Layout Instability API is a Chromium-only feature `[ASSUMED — not verified against a definitive current caniuse snapshot this session, but consistent with longstanding platform support gaps]`; since this phase's close-race test only needs to run once (chromium-a11y project, matching all other specs in this suite), either works — bounding-box is simpler, requires no feature-detection branch, and directly answers "did the sidebar/topbar move" which is the literal UX-D-06-04 ask. Recommended: bounding-box. |

**Installation:** None required — no new packages.

## Architecture Patterns

### Recommended Test File Structure

No new files required by the locked decisions, but the plan should explicitly choose between:

```
frontend/e2e/
├── page-transitions.spec.ts     # harden existing 2 tests + add close-race test (Chromium)
└── page-transitions.spec.ts     # OR add a 3rd describe block for the Firefox fallback,
                                  # scoped via test.skip(browserName !== 'firefox', ...)
                                  # — avoids a new file + new playwright.config.ts project entirely
```

**Recommendation:** Keep everything in `page-transitions.spec.ts`. Rather than adding a new
Playwright *project* (which requires editing `playwright.config.ts`'s `firefox-smoke` project
testMatch or adding a `firefox-a11y` project — more moving parts, more CI surface), use
Playwright's built-in per-test `test.skip(({ browserName }) => browserName !== 'firefox', ...)`
gate **inside the existing `chromium-a11y`-style default project** — but this only works if the
test *runs under a project that launches Firefox*. Since `chromium-a11y` is Chromium-only, the
Firefox fallback test **must** run under a project that launches the Firefox engine. Two viable
options, in order of minimal-diff:

1. **Broaden `firefox-smoke`'s `testMatch`** from `/smoke\.spec\.ts/` to an array/regex that
   also matches `page-transitions.spec.ts`, then gate the two existing pathname/searchParams
   tests with `test.skip(({ browserName }) => browserName === 'firefox', 'VT-only assertion')`
   so they don't spuriously run (and fail) under Firefox, and gate the new Firefox-fallback test
   with the inverse skip so it only runs there.
2. **Add a new project** (`firefox-a11y`) mirroring `firefox-smoke`'s Firefox launch options but
   pointed at `page-transitions.spec.ts` only.

Option 1 is lower-diff (`[ASSUMED]` — Claude's Discretion per CONTEXT.md, planner should pick
based on how much `playwright.config.ts` churn is acceptable). Either way: **this is a required
planning task, not an assumption** — without touching `playwright.config.ts`, the new Firefox
assertion will not execute in the existing `firefox-smoke` project run.

### Pattern 1: Reusable `document.getAnimations()` polling harness (existing, verbatim-reusable)

**What:** Both existing tests in `page-transitions.spec.ts` already implement a bounded poll
(50ms interval, ~800–1500ms deadline) over `document.getAnimations()`, filtering
`(a.effect as CSSEffect)?.pseudoElement` for the substring `'authed-page-content'`. This is the
WR-03-tightened named-group check — it is the correct mechanism and needs no change.

**When to use:** Any assertion about whether a *named* VT pseudo-element animation fired (or
didn't) during a bounded window after a trigger.

**Example (existing code, unmodified — from `frontend/e2e/page-transitions.spec.ts:44-67`):**
```typescript
// Source: frontend/e2e/page-transitions.spec.ts (existing, Phase 17)
const clickAndPoll = async (): Promise<number> => {
  await vulnLink.click();
  const pollMs = 1500;
  const intervalMs = 50;
  const deadline = Date.now() + pollMs;
  while (Date.now() < deadline) {
    const namedVtCount = await page.evaluate(() =>
      document.getAnimations().filter(
        (a) =>
          typeof (a.effect as CSSEffect | null)?.pseudoElement === 'string' &&
          ((a.effect as CSSEffect).pseudoElement as string).includes('authed-page-content'),
      ).length,
    );
    if (namedVtCount >= 1) return namedVtCount;
    await page.waitForTimeout(intervalMs);
  }
  return 0;
};
```

**Only the trigger changes** for the new/hardened tests below — the poll body is unchanged.

### Pattern 2: URL deep-link opens the DrillPanel with zero fixture dependency

**What:** `drill-panel.tsx`'s `isOpen` gate is `params.get('open') === 'drill' && effectiveId !== null`
— it does not validate that `effectiveId` corresponds to real seeded data before mounting the
`<aside role="dialog" data-drill-panel>` shell. `DrillContent` (the child, not the shell) does
the actual data fetch and may render a loading/error state for a non-existent CVE id, but the
panel wrapper itself — the thing whose presence-in-the-content-region is what UX-D-06-04 cares
about — mounts unconditionally.

**When to use:** Any test needing "a DrillPanel is open" as a precondition, without depending on
seeded vulnerability rows.

**Example:**
```typescript
// Source: frontend/src/components/vulnerabilities/drill-panel.tsx:45,90-99 (read directly)
// isOpen = params?.get('open') === 'drill' && effectiveId !== null;
// → deep-link opens the panel shell regardless of whether the id resolves to real data.

await page.goto('/dashboard/vulnerabilities?cve=CVE-2024-0001&open=drill');
await page.locator('[data-drill-panel]').waitFor({ state: 'visible', timeout: 10_000 });
// Panel is now open. This is the FIRST paint (D-07 first-mount guard suppresses the VT fade
// here — expected, not a bug) — do not assert VT animations on this initial goto.
```

**Caveat:** because this is a hard navigation (`page.goto`), the first-mount VT-suppression
guard in `template.tsx` (`isFirstMount`) applies — no fade is expected on this load. The VT
assertion must happen on the *subsequent* client-side navigation (the nav-Link click), not on
this initial goto. This matches Phase 17's own D-07/D-08 contract, so the test doesn't need a
special case — it is simply the correct point to *start* polling, not before.

### Pattern 3: Real searchParams-only mutation via the always-rendered severity `ChipBar`

**What:** `/dashboard/vulnerabilities` always renders a `<ChipBar facets={facets}>` with a
severity axis (confirmed via `ChipBar.test.tsx`: "chip click is synchronous — calls
router.replace immediately with axis key flipped"). Clicking a severity chip button
(`getByRole('button', { name: /critical/i })`) triggers a real `router.replace` that only
touches `?severity=...` — pathname unchanged. This requires **no seeded rows** (the chip buttons
render unconditionally from static `allowList` descriptors, independent of whether any row
matches).

**When to use:** D-02's no-fade case — proving a real, router-driven searchParams change does
not remount `template.tsx` / never produces an `authed-page-content` VT animation.

**Example:**
```typescript
// Source: frontend/src/components/ui/ChipBar.tsx + ChipBar.test.tsx (read directly)
await page.goto('/dashboard/vulnerabilities');
await page.locator('nav[aria-label="Primary navigation"]').waitFor({ state: 'visible' });
const pathnameBefore = await page.evaluate(() => location.pathname);

const criticalChip = page.getByRole('button', { name: /critical/i });
await criticalChip.click(); // real router.replace(..., 'severity=critical'...), searchParams only

// Poll (Pattern 1 harness) — expect 0 named authed-page-content animations.
// Then assert pathname unchanged:
const pathnameAfter = await page.evaluate(() => location.pathname);
expect(pathnameAfter).toBe(pathnameBefore);
```

**Fallback if the chip isn't reliably present at test time** (e.g. `facets` empty in a
zero-data environment causes the empty-filtered EmptyState branch to hide ChipBar per the
codebase comment "ChipBar hidden in empty-filtered branch"): fall back to the DrillPanel
Esc-close (Pattern 4) as the searchParams-only trigger instead — it requires only the deep-link
goto, no data at all.

### Pattern 4: DrillPanel Escape-close as the dedicated close-race + layout-shift trigger (D-05)

**What:** `drill-panel.tsx` attaches a real `keydown` listener when `isOpen`; `Escape` calls
`close()`, which does `router.replace(pathname?withoutCveAndOpen, { scroll: false })` — a real,
production `router.replace` call, searchParams-only, triggered by a real keyboard event. No
`page.evaluate` router access needed at all.

**When to use:** D-05's dedicated close-race test — open a DrillPanel (Pattern 2), press
Escape, assert (a) 0 named VT animations fire, and (b) no layout shift in the persistent chrome.

**Example:**
```typescript
// Source: frontend/src/components/vulnerabilities/drill-panel.tsx:59-68 (read directly)
await page.goto('/dashboard/vulnerabilities?cve=CVE-2024-0001&open=drill');
await page.locator('[data-drill-panel]').waitFor({ state: 'visible' });

// Capture chrome bounding boxes BEFORE close.
const navBefore = await page.locator('nav[aria-label="Primary navigation"]').boundingBox();

await page.keyboard.press('Escape'); // real close() → router.replace, searchParams only

// Poll (Pattern 1 harness) for 0 named VT animations over the close window.

// Capture chrome bounding boxes AFTER close — must be pixel-identical (D-05 chrome stillness).
const navAfter = await page.locator('nav[aria-label="Primary navigation"]').boundingBox();
expect(navAfter).toEqual(navBefore);

// Panel itself should be gone (no stuck/ghost panel).
await expect(page.locator('[data-drill-panel]')).toHaveCount(0);
```

### Pattern 5: Real pathname change while DrillPanel is open (D-02 fade case / D-11)

**What:** Combines Pattern 2 (deep-link open) with a real sidebar `<Link>` click (already used
in the existing "cross-fade fires" test) to produce a genuine pathname change while the panel is
mounted. Because `DrillPanel` is rendered as a sibling inside the page component's own return
(itself inside `template.tsx`'s `{children}` → inside the `authed-page-content` wrapper div),
it is part of the same VT-captured content snapshot — no special-case wiring needed, and the
existing "at least 1 named VT animation" assertion already proves this if it passes with the
panel open.

**Example:**
```typescript
await page.goto('/dashboard/vulnerabilities?cve=CVE-2024-0001&open=drill');
await page.locator('[data-drill-panel]').waitFor({ state: 'visible' });

const dashboardLink = page.locator('nav[aria-label="Primary navigation"]')
  .getByRole('link', { name: /dashboard/i });

// Reuse Pattern 1's clickAndPoll harness — trigger = dashboardLink.click() instead of vulnLink.click()
const namedVtCount = await clickAndPollWith(dashboardLink);
expect(namedVtCount).toBeGreaterThanOrEqual(1);

// No stuck/ghost panel after navigating away.
await expect(page.locator('[data-drill-panel]')).toHaveCount(0);
// No layout shift on the destination chrome either (optional extra assertion, reuse Pattern 4's boundingBox compare).
```

### Anti-Patterns to Avoid

- **`page.evaluate()` against Next's internal router instance** (e.g. trying to reach an
  `appRouterContext`/`__NEXT_DATA__`-adjacent object to call `.replace()` directly): not a
  documented, stable public API; brittle across Next.js versions. Every trigger needed by this
  phase has a real-UI equivalent (Patterns 2–5) — use those instead.
- **Re-synthesizing `history.pushState` + `PopStateEvent`**: this is exactly the IN-01 gap being
  closed. Do not keep it as the primary assertion; it may remain, if the planner chooses, as an
  explicitly-labeled legacy/regression check, but the *primary* no-fade assertion must be a real
  router-driven trigger (Pattern 3 or 4).
- **Assuming `firefox-smoke`'s existing `testMatch` will pick up a new spec automatically**: it
  will not (`testMatch: /smoke\.spec\.ts/` is a single literal-file regex). This must be an
  explicit task.
- **Silent pass on absent data** (the IN-02 pattern already flagged in `17-REVIEW.md` for
  `reduced-motion.spec.ts`): if a fallback path (e.g. ChipBar absent) is taken, use
  `test.skip(true, '[reason]')` — visible in the report — never a bare early `return`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting whether a named VT pseudo-element animation fired | A custom MutationObserver watching for `::view-transition-*` DOM nodes (view-transition pseudo-elements aren't real DOM nodes and can't be observed this way) | `document.getAnimations()` + `effect.pseudoElement` filtering (Pattern 1, already built) | This is the only mechanism the Web Animations API exposes for VT pseudo-elements; the existing harness already gets it right — don't reinvent |
| CVE seed-data fixtures to open a DrillPanel | A new Playwright fixture / backend seed script for a real vulnerability row | The URL deep-link contract (`?cve=<id>&open=drill`, Pattern 2) | The panel shell's `isOpen` gate doesn't require real data; building seed infrastructure for this phase would be pure overhead against a verification-only phase with "no production-code change expected" |
| Layout-shift detection | Hand-rolled MutationObserver diffing every element's `getBoundingClientRect()` on every frame | Either the native `PerformanceObserver({type:'layout-shift'})` CLS API (Chromium-only) or simple before/after `boundingBox()` diff (cross-engine, simplest) — Pattern 4 recommends the latter | Simpler, deterministic, and directly answers "did the chrome move," which is the literal UX-D-06-04 ask; avoids Chromium-only API coupling |

**Key insight:** Every "hard" part of this phase already has a load-bearing, already-shipped
mechanism in the codebase (URL-driven panel state, real `<Link>` nav, real `ChipBar` chip
clicks, real Escape-key close). The research effort here is entirely about *finding* those
existing hooks, not building new test infrastructure.

## Common Pitfalls

### Pitfall 1: First-mount VT suppression can be mistaken for a bug during the deep-link `page.goto`

**What goes wrong:** If a test polls for VT animations immediately after `page.goto('...?cve=...&open=drill')`, it will correctly see 0 — and a hasty test author might read that as "deep-link doesn't work" rather than "this is the documented D-07/D-08 first-mount guard."
**Why it happens:** `template.tsx`'s module-level `isFirstMount` flag suppresses the fade on the very first client render (hard nav / hard refresh), by design.
**How to avoid:** Only start polling for VT animations *after* the subsequent client-side navigation (the nav-Link click or chip click), never on the initial `page.goto`.
**Warning signs:** A "cross-fade never fires" failure that only reproduces on the very first navigation after `page.goto`, never on a second navigation in the same test.

### Pitfall 2: `firefox-smoke`'s `testMatch` silently excludes the new Firefox assertion

**What goes wrong:** Planner adds a Firefox-gated `test.skip` block inside `page-transitions.spec.ts` assuming it will "just run" under the Firefox project, but `firefox-smoke`'s `testMatch: /smoke\.spec\.ts/` means Playwright never even collects `page-transitions.spec.ts` under that project — the new test silently never executes (a false-green outcome, exactly the anti-pattern this whole phase exists to eliminate).
**Why it happens:** Each Playwright project independently filters which spec files it runs via `testMatch`; adding a `test.skip` guard inside a file doesn't matter if the project's `testMatch` never selects that file in the first place.
**How to avoid:** Explicitly verify (as a Wave 0 / first task) that `npx playwright test page-transitions.spec.ts --project=firefox-smoke` (or a new project name) actually lists the new test in its output — not just that the command exits 0. A 0-test run (`0 passed`) is not the same as "the assertion held."
**Warning signs:** Full-suite command reports "0 tests found" or an unexpectedly low test count for the Firefox project after adding the new assertion.

### Pitfall 3: The VT-fires assertion and the CSS-fallback assertion are mutually exclusive per browser engine, not per test

**What goes wrong:** Reusing the exact same "expect ≥1 named `authed-page-content` VT animation" assertion under the Firefox project will always fail, because Firefox has no `document.startViewTransition` — there is no VT pseudo-element to detect at all. The correct Firefox-side assertion is a **different** filter: `document.getAnimations().filter(a => a.animationName === 'page-fade-in' or similar)`, or a computed-style check that the `.authed-page-content[data-no-vt]` element carries the `page-fade-in` animation-name.
**Why it happens:** It's tempting to think "same feature, same assertion, just a different browser" — but the two code paths (native VT vs. CSS-keyframe fallback in `globals.css:207-216`) are architecturally distinct and must be asserted distinctly.
**How to avoid:** Write the Firefox assertion against the `[data-no-vt]` attribute + `page-fade-in` animation name (confirmed present in `globals.css`), not against `pseudoElement`.
**Warning signs:** A "Firefox fallback" test that reuses the `pseudoElement.includes('authed-page-content')` filter verbatim — this will always return 0 on Firefox regardless of whether the fallback actually ran, producing a false negative (or, if inverted incorrectly, a false positive).

### Pitfall 4: Layout-shift assertion timing — the panel unmount is synchronous with the DOM but the VT/close animation may still be in flight

**What goes wrong:** Asserting `boundingBox()` equality on the sidebar/topbar immediately after `page.keyboard.press('Escape')` without waiting for the (searchParams-only, so *should be instant*) React re-render to commit could produce a flaky false pass/fail if the assertion races the render.
**Why it happens:** `router.replace` → React re-render is asynchronous relative to the synchronous `keyboard.press` call.
**How to avoid:** Wait for `[data-drill-panel]` to reach `toHaveCount(0)` (panel gone) before capturing the "after" bounding box — this guarantees the re-render has committed.
**Warning signs:** Intermittent test failures where the "after" bounding box occasionally differs by a few pixels, inconsistent across runs.

## Code Examples

See §Architecture Patterns 1–5 above — all five are the load-bearing code examples for this
phase, each sourced directly from the existing codebase (`frontend/e2e/page-transitions.spec.ts`,
`frontend/src/components/vulnerabilities/drill-panel.tsx`, `frontend/src/components/ui/ChipBar.tsx`
+ its test file, and `frontend/src/app/globals.css`).

### Firefox fallback keyframe detection (new)

```typescript
// Source: frontend/src/app/globals.css:207-216 (read directly) — the fallback contract:
//   [data-no-vt].authed-page-content { animation: page-fade-in 320ms var(--ease-standard) both; }
// template.tsx sets data-no-vt on the wrapper only when `!('startViewTransition' in document)`
// AND pastFirstMount is true (src/app/(authed)/template.tsx:69-72).

test('CSS-keyframe fallback fires on Firefox pathname change (UX-D-06-03)', async ({ page, browserName }) => {
  test.skip(browserName !== 'firefox', 'Fallback path only exercised on engines without VT API');

  await page.goto('/dashboard');
  await page.locator('nav[aria-label="Primary navigation"]').waitFor({ state: 'visible' });

  const vulnLink = page.locator('nav[aria-label="Primary navigation"]').getByRole('link', { name: /vulnerab/i });
  await vulnLink.click();

  // Poll for the fallback keyframe by animationName rather than pseudoElement (Pitfall 3).
  const pollMs = 1000; const intervalMs = 50; const deadline = Date.now() + pollMs;
  let sawFallback = false;
  while (Date.now() < deadline) {
    sawFallback = await page.evaluate(() =>
      document.getAnimations().some((a) => {
        const effect = a.effect as KeyframeEffect | null;
        return effect?.target instanceof Element
          && effect.target.classList.contains('authed-page-content')
          && effect.target.hasAttribute('data-no-vt');
      }),
    );
    if (sawFallback) break;
    await page.waitForTimeout(intervalMs);
  }
  expect(sawFallback, 'Expected [data-no-vt] fallback fade to run on Firefox').toBe(true);
});
```

**Confidence on this specific snippet:** MEDIUM — the *mechanism* (`data-no-vt` attribute +
`page-fade-in` keyframe) is `[VERIFIED: direct code read]`, but the exact `getAnimations()`
filtering idiom for keyframe (non-pseudo-element) animations via `effect.target` is
`[ASSUMED]` based on standard Web Animations API shape; the planner/executor should confirm
`effect.target` resolves as expected in Firefox specifically during Wave 0 (Firefox's WAAPI
`effect` typing can differ slightly from Chromium's in edge cases).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `history.pushState` + `PopStateEvent` proxy for searchParams-only nav (IN-01) | Real `router.replace` via a real UI control (ChipBar chip or Escape key) | This phase (21) | Assertion now exercises Next's actual segment-diffing decision, not a hand-rolled approximation of it |
| No `17-VERIFICATION.md` | Goal-backward verification authored against hardened tests | This phase (21) | Closes milestone-audit Blocker #2 |
| `human-UAT checkpoint OUTSTANDING` (unpersisted) | Persisted `17-HUMAN-UAT.md` + STATE.md flag cleared | This phase (21) | Converts an informal note into an auditable artifact, per the project's own recurring anti-pattern guard |

**Deprecated/outdated:** The `PopStateEvent` proxy pattern in `page-transitions.spec.ts:94-108`
is superseded but not necessarily deleted — the planner may retain it as an explicitly-labeled
secondary/regression check if desired, but it must not remain the primary evidence for D-02.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `page.evaluate()` access to Next's internal App Router instance is unstable/unofficial across versions | Alternatives Considered | Low — moot either way, since the recommended real-UI-click approach is used instead; only affects whether we should explicitly warn against the alternative |
| A2 | The Layout Instability API (`PerformanceObserver({type:'layout-shift'})`) has cross-engine support gaps (historically Chromium-only) | Alternatives Considered | Low — recommendation is bounding-box comparison regardless, so this doesn't change the plan; only matters if a future phase wants full-page CLS numbers |
| A3 | `effect.target` reliably identifies the animated element for non-pseudo-element (regular keyframe) animations returned by `document.getAnimations()` in Firefox specifically | Code Examples — Firefox fallback snippet | Medium — if this doesn't resolve as expected, the Firefox fallback test could false-fail; Wave 0 should smoke-test this specific `getAnimations()` shape against a live Firefox instance before relying on it in the assertion |
| A4 | Option 1 (broaden `firefox-smoke`'s `testMatch`) vs. Option 2 (new project) — no strong evidence either way beyond general Playwright config practice | Architecture Patterns — recommended structure | Low — both are valid; either choice satisfies D-04 as long as the planner explicitly verifies (Pitfall 2) that the new test is actually collected and run |

**If this table is empty:** N/A — see above; all four assumptions are low-to-medium risk and
none block planning (each has a documented sidestep or verification step).

## Open Questions

1. **Does the vulnerabilities page's `ChipBar` reliably render in the e2e session's data state
   (Pattern 3), or should the plan default straight to the DrillPanel Escape-close (Pattern 4)
   as the primary no-fade trigger?**
   - What we know: `ChipBar` is hidden in the "empty-filtered" branch per an inline codebase
     comment; the normal/seeded-data branch renders it unconditionally from static
     `allowList` descriptors.
   - What's unclear: whether the e2e auth/seed fixture used by this suite (`e2e/fixtures/auth.ts`)
     produces enough vulnerability data for the normal branch to render (not checked this
     session — the auth fixture only sets up login state, not data fixtures).
   - Recommendation: Wave 0 should probe this live (`page.goto('/dashboard/vulnerabilities')`,
     check whether the severity chip is present) before committing to Pattern 3 as primary;
     Pattern 4 (Escape-close) has zero data dependency and can serve as the primary no-fade
     trigger with Pattern 3 as a secondary/upgrade if data is present.

2. **Should the retroactive `17-VERIFICATION.md` re-run the FULL Phase 17 quality gate (bundle
   budget, reduced-motion, cross-browser smoke) or scope strictly to UX-D-06-01..05 using the
   now-hardened `page-transitions.spec.ts` + `reduced-motion.spec.ts`?**
   - What we know: `17-VALIDATION.md`'s Per-Task Verification Map already lists the specific
     commands per requirement (bundle via `next build | grep "First Load JS"`, reduced-motion
     via the existing spec).
   - What's unclear: whether the goal-backward verifier should re-execute all of these live now,
     or treat the original Phase 17 execution's green run as sufficient prior evidence for the
     unchanged requirements (UX-D-06-02, UX-D-06-05) and focus fresh evidence-gathering only on
     -01/-03/-04 (the ones this phase actually touches).
   - Recommendation: Re-run all of them live as part of `17-VERIFICATION.md` authorship — the
     whole point of this phase is "evidence that would survive an audit," and a stale "trust the
     old green run" claim is exactly the anti-pattern being fixed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Playwright runner | ✓ | v26.5.0 `[VERIFIED: node -v]` | — |
| @playwright/test | e2e specs | ✓ | 1.61.1 `[VERIFIED: npm ls]` | — |
| Next.js dev/prod server on :3000 | live e2e run (per project memory `getvul-local-e2e-perf-gate`) | Not probed this session (requires a running server) | — | Follow the documented recipe: prod build + :3000 + admin login + kill next-server children |
| Firefox engine (Playwright-managed browser binary) | D-04 assertion | Not probed this session (`npx playwright install` state unknown) | — | If missing, `npx playwright install firefox` — standard, no alternative fallback needed |

**Missing dependencies with no fallback:** None identified — all dependencies are either
already verified present or have a standard, low-risk install step.

**Missing dependencies with fallback:** Firefox browser binary (if not yet installed locally) —
`npx playwright install firefox`.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Playwright 1.61.1 (`@playwright/test`) `[VERIFIED: npm ls]` |
| Config file | `frontend/e2e/playwright.config.ts` |
| Quick run command | `npx playwright test e2e/page-transitions.spec.ts --project=chromium-a11y` |
| Full suite command | `npx playwright test --project=chromium-a11y --project=chromium-smoke --project=webkit-smoke --project=firefox-smoke` (plus whichever Firefox project/testMatch change D-04 introduces) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-D-06-01 | Real pathname change fires named `authed-page-content` VT animation | e2e | `npx playwright test e2e/page-transitions.spec.ts -g "pathname change" --project=chromium-a11y` | ✅ (existing, to be confirmed still green — no change needed to the trigger, it already clicks a real Link) |
| UX-D-06-04 (no-fade case) | Real searchParams-only change (ChipBar or Escape-close) fires 0 named VT animations | e2e | `npx playwright test e2e/page-transitions.spec.ts -g "searchParams" --project=chromium-a11y` | ❌ Wave 0 — hardening task: replace `PopStateEvent` trigger per Pattern 3/4 |
| UX-D-06-04 (fade case / D-11) | Pathname change with DrillPanel open fades panel+content, no ghost panel | e2e | `npx playwright test e2e/page-transitions.spec.ts -g "DrillPanel" --project=chromium-a11y` | ❌ Wave 0 — new test, Pattern 5 |
| UX-D-06-04 (close-race + layout shift) | Esc-close DrillPanel: 0 VT animations + 0px chrome bounding-box delta | e2e | `npx playwright test e2e/page-transitions.spec.ts -g "close-race" --project=chromium-a11y` | ❌ Wave 0 — new test, Pattern 4 |
| UX-D-06-03 | Firefox CSS-fallback keyframe fires on real pathname change; suppressed under reduced-motion | e2e | `npx playwright test e2e/page-transitions.spec.ts --project=firefox-smoke` (pending testMatch fix, Pitfall 2) | ❌ Wave 0 — new test + config change |
| UX-D-06-01..05 (goal-backward) | Formal verification artifact confirming all of the above + bundle budget + reduced-motion | doc artifact | Manual authoring by `gsd-verifier` pattern, re-running each command above and pasting live output | ❌ — `17-VERIFICATION.md` does not yet exist (this phase's SC#3) |
| Perceptual "feel" (D-07 checklist a–d) | Human-observed cross-fade snappiness, chrome stillness, DrillPanel behavior, Firefox feel | manual (human-action checkpoint) | N/A — guided live session, `autonomous: false` | ❌ — `17-HUMAN-UAT.md` does not yet exist (this phase's SC#2) |

### Sampling Rate

- **Per task commit:** `npx playwright test e2e/page-transitions.spec.ts --project=chromium-a11y`
- **Per wave merge:** `npx playwright test --project=chromium-a11y --project=firefox-smoke` (or
  the new Firefox project name, once decided) + `npx playwright test e2e/reduced-motion.spec.ts --project=chromium-a11y` (must stay green per CONTEXT.md)
- **Phase gate:** Full suite green (all 4+ projects) before authoring `17-VERIFICATION.md`, and
  before the guided human-UAT session (D-06) — no point running a perceptual check against code
  whose automated assertions are still red.

### Wave 0 Gaps

- [ ] Confirm live whether `ChipBar`'s severity chip renders in the e2e session's actual data
  state (Open Question 1) — determines whether Pattern 3 or Pattern 4 is the primary no-fade
  trigger.
- [ ] Decide + implement the Firefox `testMatch`/project change (Architecture Patterns
  recommended structure) — without this, D-04's new test silently never runs (Pitfall 2).
- [ ] Smoke-test the `document.getAnimations()` shape for the `page-fade-in` keyframe under
  Firefox specifically (Assumption A3) before finalizing the fallback assertion's exact filter
  expression.

*(No pre-existing test-framework install gap — Playwright + all 4 projects already exist and
are green per `17-VALIDATION.md`'s Wave 0 section, which stated "No new test infrastructure
needed" for the original Phase 17 build; this phase only needs new spec content + one config
touch.)*

## Security Domain

This phase adds no new attack surface, no new auth/session/crypto code, and no new input
handling — it is exclusively Playwright test code + Markdown documentation against
already-shipped, already-reviewed production code. Per CONTEXT.md's `code_context` §Integration
Points: "No production-code change expected... If a test surfaces a real VT×DrillPanel race or
layout shift, that becomes an in-scope fix (the test, not the file list, is the arbiter)."

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Uses existing `e2e/.auth/state.json` storageState — no new auth code |
| V5 Input Validation | No | The `?cve=<any-id>` deep-link is read-only test-driving of an existing, already-shipped URL contract; no new parsing/validation logic is added |

**Note:** if a genuine VT×DrillPanel race is *discovered* by the new tests (an in-scope
possibility per CONTEXT.md), any resulting production-code fix would need its own security
re-assessment at that time — out of scope for this research pass, which assumes the
architectural-soundness claim in the milestone audit holds.

## Sources

### Primary (HIGH confidence — direct codebase reads this session)

- `frontend/src/app/(authed)/template.tsx` — transition driver, first-mount guard, `data-no-vt` gate
- `frontend/src/app/globals.css` lines 178-217 — VT rules, reduced-motion suppression, fallback keyframe
- `frontend/e2e/page-transitions.spec.ts` — existing polling harness + IN-01 proxy (to replace)
- `frontend/e2e/reduced-motion.spec.ts` — existing UX-D-06-02 coverage, must stay green
- `frontend/e2e/playwright.config.ts` — project definitions, `firefox-smoke` testMatch gap
- `frontend/src/components/vulnerabilities/drill-panel.tsx` — URL-driven open/close gate, Esc/clickaway handlers
- `frontend/src/components/ui/ChipBar.tsx` + `ChipBar.test.tsx` — real searchParams-only control
- `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` — DrillPanel mount point, deep-link contract comment
- `.planning/phases/17-page-transition-motion/17-CONTEXT.md`, `17-REVIEW.md` (IN-01), `17-VALIDATION.md` — prior decisions + gap definitions
- `.planning/v2.2-MILESTONE-AUDIT.md` — Blocker #2 definition this phase closes
- `.planning/STATE.md` line 29 — the exact "human-UAT checkpoint OUTSTANDING" line to clear
- `$HOME/.claude/get-shit-done/templates/UAT.md` + existing `16-HUMAN-UAT.md` — confirmed file-naming
  convention is `{phase}-HUMAN-UAT.md` (not the generic `UAT.md` template name) with frontmatter
  `status/phase/source/started/updated` + Current Test / Tests / Summary / Gaps sections
- `$HOME/.claude/get-shit-done/templates/verification-report.md` — confirmed `{phase}-VERIFICATION.md`
  structure: frontmatter (`phase/verified/status/score`), Goal Achievement (Observable Truths
  table), Requirements Coverage, Anti-Patterns Found, Human Verification Required, Gaps Summary
- `npm ls @playwright/test`, `node -v` — verified installed versions

### Secondary (MEDIUM confidence — WebSearch, cross-referenced with codebase patterns)

- WebSearch "Playwright measure Cumulative Layout Shift PerformanceObserver layout-shift" —
  confirms the `PerformanceObserver({type:'layout-shift', buffered:true})` idiom as the current
  community-standard approach; used here only to inform the Alternatives Considered comparison,
  not the recommended path
- WebSearch "Playwright test Next.js App Router client-side navigation click Link real router" —
  confirms "click real UI + assert URL" as the standard/recommended idiom over reaching into
  router internals, consistent with this research's Pattern 3/4/5 recommendation

### Tertiary (LOW confidence — flagged for validation)

- A3 (Firefox `getAnimations()`/`effect.target` shape) — not verified live this session; flagged
  in Assumptions Log and Wave 0 Gaps for a smoke-test before finalizing the assertion

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, versions verified via `npm ls`
- Architecture patterns: HIGH — every pattern grounded in direct reads of the actual shipped
  code (drill-panel.tsx, ChipBar.tsx, template.tsx, globals.css), not inferred
- Pitfalls: HIGH for Pitfalls 1/2/4 (directly derivable from code read), MEDIUM for Pitfall 3
  (the exact `getAnimations()` filter shape for keyframe vs. pseudo-element animations is
  standard WAAPI knowledge, not independently verified against a live Firefox run this session)

**Research date:** 2026-07-21
**Valid until:** 30 days (stable stack, no fast-moving dependencies; re-verify if Next.js or
Playwright are upgraded before this phase executes)
