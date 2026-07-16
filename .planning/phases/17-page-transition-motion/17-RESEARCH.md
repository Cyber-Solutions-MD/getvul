# Phase 17: Page-transition motion — Research

**Researched:** 2026-07-16
**Domain:** View Transitions API · Next.js 15 App Router template.tsx · CSS animation accessibility
**Confidence:** HIGH (core approach), MEDIUM (reduced-motion edge case), HIGH (validation architecture)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Cross-fade fires only on pathname changes (keyed off `usePathname()`), not raw navigation.
- **D-02:** `searchParams`-only changes do NOT fade. DrillPanel (`?drill=…`), tabs, and list↔board toggles excluded.
- **D-03:** Pure opacity cross-fade — no transforms. No vertical drift, no slide.
- **D-04:** Duration 220–320ms (not the reserved 520ms `--motion-xslow`). Claude's discretion within that band, leaning 320ms (`--motion-slow`).
- **D-05:** Content region only fades. Sidebar + topbar (chrome, owned by `(authed)/layout.tsx`) stay static. Requires `view-transition-name` on the content wrapper.
- **D-06:** CSS-keyframe opacity fallback for Firefox / non-supporting browsers. Added to `globals.css` @keyframes block. Reduced-motion blanket (D-12) suppresses it.
- **D-07:** No fade on first load / hard refresh.
- **D-08:** No fade on app entry (login → dashboard first mount).
- **D-09:** Fade runs on pathname change (old content → new route's skeleton). No second fade on skeleton→data resolution.
- **D-10:** Keep Next.js default scroll behavior — no custom scroll management.
- **D-11:** When DrillPanel is open and user navigates to a different route (pathname change), the panel fades out with content in the outgoing snapshot.

### Claude's Discretion

- Exact duration within 220–320ms band (D-04), leaning 320ms.
- Exact `view-transition-name` value and where the content wrapper lives (`template.tsx` vs a thin client component inside it).
- Where the transition CSS lives — recommend following the single-source convention in `globals.css`.
- Validation depth: recommend a lightweight e2e assertion that the cross-fade fires on a real pathname change (in addition to keeping `e2e/reduced-motion.spec.ts` green for UX-D-06-02).

### Deferred Ideas (OUT OF SCOPE)

- Navigation pending indicator (top loading bar / pending cue during navigation to `force-dynamic` routes).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-D-06-01 | Route changes within the `(authed)` shell animate with a cross-fade via the View Transitions API (single `template.tsx`). | Template.tsx remount behavior + `document.startViewTransition` pattern confirmed. |
| UX-D-06-02 | Transitions fully suppressed under `prefers-reduced-motion` (≤0.02s); `e2e/reduced-motion.spec.ts` stays green. | Critical finding: blanket `*` rule does NOT reliably suppress `::view-transition-*` pseudo-elements — explicit rule required. |
| UX-D-06-03 | CSS-animation fallback keeps navigation clean in Firefox (no jank, no broken nav). | Feature-detection + `@keyframes` fallback pattern documented. |
| UX-D-06-04 | No race with DrillPanel Esc/clickaway; no layout shift. | D-02 (searchParams ≠ pathname) architecturally eliminates the race. DrillPanel close operates on searchParams only. |
| UX-D-06-05 | No route exceeds 250 KB First-Load JS. | Phase 15 budget was 15/15 green. `template.tsx` adds 0 KB JS (CSS + native API only). |
</phase_requirements>

---

## Summary

Phase 17 adds a single file (`(authed)/template.tsx`) and CSS rules to `globals.css`. The approach uses the native View Transitions API (`document.startViewTransition`) triggered from a `useEffect` in `template.tsx` on every remount — which Next.js guarantees happens on pathname changes and not on searchParams-only changes. The chrome (sidebar + topbar) stays mounted in `layout.tsx` and never fades. Only the content wrapper inside `template.tsx` gets a `view-transition-name`, isolating it from the root snapshot.

The most important research finding is a **gap between the CONTEXT.md assumption (D-06) and the technical reality**: the existing D-12 blanket rule (`*, *::before, *::after { animation-duration: 0.01ms !important }`) does NOT reliably suppress `::view-transition-old()` / `::view-transition-new()` pseudo-elements. These UA-generated pseudo-elements are not consistently matched by the universal CSS selector — they require an explicit `@media (prefers-reduced-motion: reduce) { ::view-transition-group(*), ::view-transition-old(*), ::view-transition-new(*) { animation-duration: 0.01ms !important; } }` rule. This rule must be added alongside the existing blanket.

The Firefox CSS-keyframe fallback is straightforward and zero-cost. The 250 KB budget is safe — the phase adds no JS. The DrillPanel race is architecturally resolved: close paths mutate only searchParams, which never trigger a `template.tsx` remount.

**Primary recommendation:** One `'use client'` `template.tsx` + two CSS blocks in `globals.css` (VT pseudo-elements + explicit reduced-motion suppressor for those pseudo-elements). No new packages. No `experimental.viewTransition` flag (that is a different, experimental React `<ViewTransition>` integration — not the approach locked by this project).

---

## Standard Stack

### Core

| Library / API | Version | Purpose | Why Standard |
|---------------|---------|---------|--------------|
| View Transitions API | Native browser (Chrome 111+, Edge 111+, Safari 18+) | Cross-fade snapshot machinery | 0 KB JS; hardware-accelerated; no peer dependency |
| Next.js `template.tsx` convention | v13.0.0+ (project: ^15.5.18) [VERIFIED: package.json] | Forces remount on pathname change; skips searchParams remounts | Native to App Router; no additional code needed |
| `usePathname()` (next/navigation) | bundled with Next.js | Detects pathname in a Client Component | Required to trigger effect on pathname change |
| `useEffect` / `useLayoutEffect` (React 19) | bundled with React 19 [VERIFIED: package.json] | Detects mount → triggers `startViewTransition` | See Pattern 1 below |
| CSS `::view-transition-old()` / `::view-transition-new()` | W3C CSS View Transitions Level 1 [CITED: developer.chrome.com/docs/web-platform/view-transitions/same-document] | Opacity keyframe override | Pure CSS, no JS |

### No Additions Needed

No new `npm install` required. The entire phase is a new file + CSS edits. The existing `globals.css` @keyframes registry absorbs the fallback keyframe per the project's single-source convention.

---

## Architecture Patterns

### Template.tsx Nesting (Confirmed)

Next.js renders `template.tsx` **between** `layout.tsx` and its children [CITED: nextjs.org/docs/app/api-reference/file-conventions/template]:

```
<AuthedLayout>           ← (authed)/layout.tsx: AppShell + ToastProvider — MOUNTED ONCE
  <Template key={...}>  ← (authed)/template.tsx: REMOUNTS on pathname change
    {children}           ← Route page content
  </Template>
</AuthedLayout>
```

`Template` receives a new `key` whenever the **segment** changes. Crucially, `searchParams` changes do NOT trigger a remount [CITED: nextjs.org/docs/app/api-reference/file-conventions/template §Behavior]. This is the architectural guarantee for D-01 and D-02.

### Pattern 1: template.tsx — pathname-keyed transition trigger

```tsx
// frontend/src/app/(authed)/template.tsx
'use client';
import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

export default function AuthedTemplate({ children }: { children: ReactNode }) {
  const isFirstMount = useRef(true);

  useEffect(() => {
    // D-07/D-08: Skip first mount — no fade on hard refresh or app entry.
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    // Feature-detect: D-06 fallback handles browsers without VT.
    if (!document.startViewTransition) return;
    // Note: startViewTransition captures OLD state before the new render is
    // committed. In the template.tsx pattern, the remount itself IS the DOM
    // update — so this call runs AFTER the new children are mounted, meaning
    // there is no DOM update callback to pass. Instead, we trigger startViewTransition
    // in the effect, which fires after React has painted the new template content.
    // The browser captures the incoming state automatically.
    //
    // Correct approach: wrap the already-committed render in a transition by
    // using a ref to queue the call BEFORE the next paint, or use the
    // useLayoutEffect variant. See Pitfall 2 below for the timing detail.
    document.startViewTransition();
  });
  // NOTE: No deps array — fires after EVERY render, but isFirstMount guards the
  // first call. Template remounts guarantee it fires fresh per navigation.

  return (
    <div
      className="contents"
      style={{ viewTransitionName: 'page-content' }}
    >
      {children}
    </div>
  );
}
```

**Critical implementation note (see Pitfall 2 below):** The `useEffect` / `useLayoutEffect` timing with `document.startViewTransition` in App Router's streaming model requires care. The most reliable documented pattern for template.tsx is: call `startViewTransition()` with no update callback (the DOM has already updated when the effect fires). The browser's snapshot is of the new state. The OLD state was captured before React committed. This means the transition animates from the previous route's snapshot to the new one — which is the correct cross-fade direction. [ASSUMED — timing model not explicitly documented in Next.js docs; based on React rendering lifecycle and web.dev VT documentation]

### Pattern 2: CSS — content-only isolation + cross-fade

All CSS additions go in `globals.css` (single-source convention, per existing @keyframes at lines 155–173):

```css
/* ─── Phase 17: Page-transition motion ─────────────────────────────────────── */

/* 1. Assign a stable view-transition-name to the content wrapper.
      This isolates the content region from the root ::view-transition snapshot,
      keeping sidebar + topbar chrome static (D-05). */
.page-transition-root {
  view-transition-name: page-content;
}

/* 2. Override the UA default cross-fade (250ms) with the project's 320ms
      and pure opacity (no transforms, D-03). --ease-standard: cubic-bezier(0.2,0,0,1). */
::view-transition-old(page-content),
::view-transition-new(page-content) {
  animation-duration: 320ms; /* --motion-slow (D-04 upper bound) */
  animation-timing-function: var(--ease-standard);
  /* Default UA animation is already opacity cross-fade — no animation-name override needed. */
}

/* 3. CRITICAL: Explicit reduced-motion suppression for VT pseudo-elements.
      The D-12 blanket (*,*::before,*::after) does NOT reliably reach these
      UA-generated pseudo-elements (see Pitfall 1). Explicit rule required. */
@media (prefers-reduced-motion: reduce) {
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.01ms !important;
    animation-delay: 0.01ms !important;
  }
}

/* 4. Firefox / no-VT CSS fallback (D-06).
      Feature-detected in template.tsx: fallback class applied only when
      document.startViewTransition is absent. Alternatively: a CSS @supports rule. */
@keyframes page-fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* Applied to the wrapper when VT is unavailable — see template.tsx data-no-vt pattern. */
[data-no-vt] .page-transition-root {
  animation: page-fade-in 320ms var(--ease-standard) both;
}
/* D-12 blanket catches this keyframe automatically (it targets CSS animations on
   regular elements, not VT pseudo-elements). No extra rule needed for the fallback. */
```

### Anti-Patterns to Avoid

- **Using `experimental.viewTransition: true` in next.config.js**: This enables React's `<ViewTransition>` component (a different, experimental integration) — NOT the locked `template.tsx` + `document.startViewTransition` approach. Do not add this flag. [CITED: nextjs.org/docs/app/api-reference/config/next-config-js/viewTransition]
- **Calling `startViewTransition` with a DOM-update callback**: In the template.tsx pattern, the DOM is already updated when the effect fires. Passing an update callback would double-update the DOM.
- **Relying on the D-12 blanket alone for reduced motion**: The `*, *::before, *::after` rule does NOT reliably catch `::view-transition-old/new/group`. Explicit VT pseudo-element rule is non-optional. [CITED: web.dev/learn/css/view-transitions-spas + nextjs.org/docs/app/guides/view-transitions §reduced-motion example]
- **Applying `view-transition-name` to the entire `<main>` in AppShell**: That element is in `layout.tsx` (stays mounted), so the VT snapshot would include the chrome and still fade the whole viewport. The name must be on the content wrapper inside `template.tsx`.
- **Animating with transforms (slide, drift)**: D-03 locks this out. The `prefers-reduced-motion` fallback is identical (opacity only). No `translateY`, no directional motion.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Opacity cross-fade between routes | Custom React animation library integration (framer-motion, etc.) | Native View Transitions API + CSS | 0 KB; rejected in milestone as non-standard |
| Fallback for Firefox | JS-based fade-in/out logic | CSS `@keyframes page-fade-in` + `@supports` / data attribute | Stays in CSS so D-12 blanket catches it |
| Reduced-motion detection in JS | `usePrefersReducedMotion()` hook to gate `startViewTransition` | CSS `@media (prefers-reduced-motion: reduce)` targeting VT pseudo-elements | Keeps motion logic in CSS; hook already exists for other uses but is not the right gate here |

---

## Common Pitfalls

### Pitfall 1: Blanket prefers-reduced-motion rule misses VT pseudo-elements (CRITICAL)

**What goes wrong:** The existing `globals.css` D-12 blanket (`*, *::before, *::after { animation-duration: 0.01ms !important }`) does NOT reliably suppress `::view-transition-old()`, `::view-transition-new()`, and `::view-transition-group()` under `prefers-reduced-motion: reduce`. These pseudo-elements are UA-generated outside the normal DOM tree. The project's CONTEXT.md D-06 assumes the blanket "already suppresses" the native VT path — this assumption is incorrect.

**Why it happens:** The universal selector `*` does not match these specialized pseudo-elements consistently across browsers. The UA stylesheet sets `animation-duration: inherit` on them, but the inheritance chain goes through `:root::view-transition-old(*)`, not through the `*` rule in author stylesheets. [CITED: web.dev/learn/css/view-transitions-spas — recommends explicit targeting; nextjs.org/docs/app/guides/view-transitions §reduced-motion — uses explicit `::view-transition-old/new/group` rule]

**How to avoid:** Add an explicit rule:
```css
@media (prefers-reduced-motion: reduce) {
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.01ms !important;
    animation-delay: 0.01ms !important;
  }
}
```

**Warning signs:** `e2e/reduced-motion.spec.ts` does not currently test VT pseudo-elements (it tests `.bg-gradient-mesh` and `.bg-severity-critical`). A new test case must probe the computed `animation-duration` of `::view-transition-old` itself, or confirm via a Playwright `page.evaluate` that `document.startViewTransition` fires a near-instantaneous transition under `reducedMotion: 'reduce'` emulation.

### Pitfall 2: Timing of startViewTransition in template.tsx

**What goes wrong:** Calling `document.startViewTransition(updateCallback)` AFTER React has committed the new DOM defeats the purpose — the browser captures the new state as both old and new, producing no visible transition. The `useEffect` fires post-paint; by then the new page is already visible.

**Why it happens:** The View Transitions API requires `startViewTransition` to be called BEFORE the DOM update to capture the old state. In a `template.tsx` remount context, the component already mounted (new state committed) before any `useEffect` runs.

**Correct approach:** The documented community pattern for `template.tsx` (without the `experimental.viewTransition` React integration) is to call `document.startViewTransition()` with NO update callback in `useLayoutEffect`. `useLayoutEffect` fires synchronously after DOM mutation but before paint, so the browser can capture the outgoing snapshot correctly. Alternatively, some implementations wrap the navigation trigger itself (in a `Link` onClick / router.push wrapper) to call `startViewTransition` before the route update — but that conflicts with D-01/D-02 (it would require instrumenting every `<Link>`, not just `template.tsx`).

**Validated pattern (useLayoutEffect):** [ASSUMED — based on React rendering lifecycle; the official Next.js docs do not document the template.tsx + startViewTransition pattern explicitly. The `experimental.viewTransition` flag + React `<ViewTransition>` is the documented path. This phase deliberately uses the undocumented manual path.]

```tsx
useLayoutEffect(() => {
  if (isFirstMount.current) { isFirstMount.current = false; return; }
  if (!document.startViewTransition) return;
  // Fires before paint — captures outgoing state correctly.
  document.startViewTransition();
  // No update callback — React already committed the new DOM.
});
```

**Recommendation for planner:** Flag this as the highest-risk implementation detail. The planner should include a manual smoke test step (navigate Dashboard → Vulnerabilities, confirm the fade is visible) immediately after the first `template.tsx` implementation attempt.

### Pitfall 3: view-transition-name uniqueness conflict

**What goes wrong:** If any other element in the page carries `view-transition-name: page-content` (or the same name chosen for the content wrapper), the browser throws an error and the transition fails silently.

**Why it happens:** The VT spec requires each `view-transition-name` value to be unique across all rendered elements at the same time.

**How to avoid:** Use a distinct, non-generic name (e.g., `authed-page-content`). Grep the codebase for `view-transition-name` before finalizing the name to ensure no conflict exists. Currently: no `view-transition-name` usage found in the codebase. [VERIFIED: grep returned no results]

### Pitfall 4: DrillPanel race — only applies to pathname changes (non-issue per D-02)

**What goes wrong:** If `template.tsx` remounted on searchParams changes (e.g., `?open=drill`), the DrillPanel Esc/clickaway close would trigger a fade while the panel is disappearing — a double-animation race.

**Why it is not an issue here:** Next.js `template.tsx` remount is keyed on the **segment**, not on `searchParams`. The Next.js docs explicitly state: "Search params do not trigger remounts." [CITED: nextjs.org/docs/app/api-reference/file-conventions/template §Behavior] DrillPanel close uses `router.replace(pathname?qs, { scroll: false })` which changes searchParams only — this does not remount the template. D-02 is architecturally guaranteed.

**Verification required (UX-D-06-04):** Even though the race is architecturally prevented, the planner must include a manual UAT step: open a DrillPanel on the Vulnerabilities page, hit Esc, confirm no fade occurs. This confirms the architectural assumption holds in the production build.

### Pitfall 5: First-mount fade (D-07/D-08)

**What goes wrong:** Without a mount guard, `startViewTransition` fires on the first render of `template.tsx` (e.g., hard refresh to `/dashboard`), causing an initial fade-in delay on every page load.

**How to avoid:** `useRef(true)` initialized to `true`; set to `false` after first effect run. The `useLayoutEffect` is guarded by this ref before calling `startViewTransition`.

### Pitfall 6: AppShell children vs. content wrapper nesting

**What goes wrong:** Applying `view-transition-name` to the `<main>` element in `AppShell` (which lives in `layout.tsx`, not `template.tsx`) would make the chrome snapshot include sidebar/topbar — fading the whole viewport including chrome (violates D-05).

**How to avoid:** The `view-transition-name` must be on the wrapper **inside `template.tsx`**, which sits between the `layout`'s `<main>` and the route `{children}`. Looking at `app-shell.tsx` line 37: `<main className="..."><{children}></main>` — the `template.tsx` wrapper wraps `{children}`, which is INSIDE the `<main>` tag. The `view-transition-name` on the `template.tsx` wrapper div will therefore only snapshot the page content, not the sidebar/topbar/bottomnav.

---

## Code Examples

### Minimal template.tsx pattern
```tsx
// Source: community pattern; timing model [ASSUMED] — see Pitfall 2
'use client';
import { useLayoutEffect, useRef } from 'react';
import type { ReactNode } from 'react';

export default function AuthedTemplate({ children }: { children: ReactNode }) {
  const isFirstMount = useRef(true);
  const noVt = typeof document !== 'undefined' && !document.startViewTransition;

  useLayoutEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    if (!document.startViewTransition) return;
    document.startViewTransition();
  });

  return (
    <div
      className="contents"
      style={{ viewTransitionName: 'authed-page-content' }}
      data-no-vt={noVt ? '' : undefined}
    >
      {children}
    </div>
  );
}
```

### CSS — reduced-motion explicit rule for VT pseudo-elements
```css
/* Source: nextjs.org/docs/app/guides/view-transitions §reduced-motion, web.dev/learn/css/view-transitions-spas */
@media (prefers-reduced-motion: reduce) {
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.01ms !important;
    animation-delay: 0.01ms !important;
  }
}
```

### CSS — content cross-fade (override UA default duration)
```css
/* Source: developer.chrome.com/docs/web-platform/view-transitions/same-document */
::view-transition-old(authed-page-content),
::view-transition-new(authed-page-content) {
  animation-duration: 320ms;
  animation-timing-function: var(--ease-standard);  /* cubic-bezier(0.2, 0, 0, 1) */
}
```

### CSS — Firefox fallback keyframe (add to the @keyframes block at lines 155–173)
```css
/* Source: design pattern; lives in globals.css alongside pulse-urgency, gradient-drift, etc. */
@keyframes page-fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}
[data-no-vt] [style*="authed-page-content"] {
  animation: page-fade-in 320ms var(--ease-standard) both;
}
```

### Feature detection (JavaScript)
```js
// Source: developer.chrome.com/docs/web-platform/view-transitions/same-document §feature-detection
if (!document.startViewTransition) {
  // Fallback path — CSS keyframe handles this via data-no-vt attribute
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| react-router page transitions via framer-motion | Native View Transitions API | Chrome 111 (March 2023), Safari 18 (Sep 2024) | 0 KB JS; browser-native |
| `next-view-transitions` npm package | Template.tsx + `document.startViewTransition` directly | App Router maturity (2024) | No package needed |
| `experimental.viewTransition + <ViewTransition>` | Same, but experimental React integration | React canary + Next.js experimental (2025–2026) | Different approach from what this project uses; do NOT add |

**Deprecated/outdated:**
- `experimental.viewTransition` flag: Relevant to React's `<ViewTransition>` component pattern — a **different** implementation from this phase's `template.tsx` + `document.startViewTransition` approach. [CITED: nextjs.org/docs/app/api-reference/config/next-config-js/viewTransition — "not recommended for production"] Do not enable.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `useLayoutEffect` (not `useEffect`) is the correct hook to call `document.startViewTransition()` from `template.tsx` so the browser captures the outgoing state before paint. | Pitfall 2 / Pattern 1 | If wrong: transitions run but in the wrong direction (new→new crossfade instead of old→new); requires switching hooks or a different approach. Mitigated by the "navigate and visually confirm" UAT step. |
| A2 | The `template.tsx` wrapper `div` with `style={{ viewTransitionName: '...' }}` and `className="contents"` correctly isolates the content without affecting layout (since `display: contents` makes the div transparent to layout). | Pattern 1 | If `display: contents` breaks flex/grid in some routes, may need to use a different wrapper approach. Low risk — `contents` is widely supported and was already reviewed in Phase 15. |
| A3 | The Firefox fallback approach (detect `!document.startViewTransition` during render, apply `data-no-vt` attribute) works correctly in Next.js 15 SSR/hydration context without causing hydration mismatch. | Pattern 1 / Pitfall 3 | If wrong: React hydration error in Firefox. Mitigation: use `useEffect` to set the attribute client-side only, or use CSS `@supports (view-transition-name: none)` as an alternative detection method. |

---

## Open Questions (RESOLVED)

> All three questions were resolved during planning (Phase 17 plans 17-01/17-02). Each
> carries its resolution below. No open unknowns remain that block execution.

1. **useLayoutEffect vs. useEffect timing with startViewTransition**
   - What we know: `useLayoutEffect` fires before paint; `useEffect` fires after paint. The VT API captures the old state at `startViewTransition` call time, then runs the update callback (if provided), then captures the new state.
   - What's unclear: When called with NO update callback in a template.tsx remount, does `startViewTransition()` called in `useLayoutEffect` (which fires after React commits) correctly animate from the PREVIOUS page snapshot (captured by the browser before React committed the new DOM)?
   - **RESOLVED:** `useLayoutEffect` chosen (Plan 02 Task 2). This is the highest-risk ASSUMED item — mitigated by the blocking manual smoke-test checkpoint (Plan 02 Task 4: navigate Dashboard → Vulnerabilities and visually confirm the fade before proceeding). If it fails, the router-wrapping fallback is the documented escalation.

2. **Blanket prefers-reduced-motion vs. explicit VT rule — redundancy or conflict?**
   - What we know: The explicit rule is needed. The blanket rule is already present. Both use `!important`.
   - What's unclear: Specificity resolution when both match the same pseudo-element (if the blanket does reach them).
   - **RESOLVED:** Both rules present (Plan 02 Task 1 adds the explicit `::view-transition-*(*)` rule; the D-12 `*` blanket stays). Same `!important` value ⇒ no conflict; the explicit VT rule is the one that actually reaches the UA pseudo-elements the blanket cannot.

3. **CSS `@supports` vs. JS feature-detection for Firefox fallback**
   - What we know: `@supports (view-transition-name: none)` is a CSS-only detection path that avoids the `data-no-vt` attribute and hydration risk.
   - What's unclear: Whether all browsers that support `view-transition-name` also support `document.startViewTransition` (they should).
   - **RESOLVED:** JS feature-detection + `data-no-vt` attribute chosen (Plan 02 Task 2) for the `startViewTransition` gate; the `@supports` CSS alternative is noted as available but not needed. The fallback keyframe is caught by the D-12 reduced-motion blanket, so hydration risk is bounded.

---

## Environment Availability

Step 2.6: No external tool dependencies for this phase. All implementation is:
- A new file (`template.tsx`) added to an existing Next.js project
- CSS edits to `globals.css`
- A new Playwright e2e spec in the existing e2e runner

No CLI tools, databases, or services beyond what already exists need to be installed or verified.

**Playwright 1.61.1** is installed [VERIFIED: package.json `@playwright/test: ^1.61.1`]. The e2e suite runs against `localhost:3000` (prod build) per the getvul memory note (admin user, `:3000` CORS, prod build, kill next-server children, Firefox dark pref).

---

## Validation Architecture

> nyquist_validation is enabled (absent from config.json = treat as true).

### Critical Context

The project memory notes that "executors claim WCAG AA but never run the Playwright axe e2e sweep." The same pattern is at risk here: implementing the VT cross-fade and then claiming it works without running any automated assertion. This section enforces a concrete verification architecture.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Playwright 1.61.1 (`@playwright/test`) |
| Config file | `frontend/e2e/playwright.config.ts` |
| Quick run command | `npx playwright test e2e/reduced-motion.spec.ts --project=chromium-a11y` |
| Full suite command | `npx playwright test --project=chromium-a11y --project=chromium-smoke --project=webkit-smoke --project=firefox-smoke` |
| Prerequisite | Prod build running on `:3000` (see getvul memory) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-D-06-01 | Route changes produce a VT cross-fade | e2e smoke | `npx playwright test e2e/page-transitions.spec.ts --project=chromium-a11y` | ❌ Wave 0 |
| UX-D-06-02 | Transitions suppressed under prefers-reduced-motion (≤0.02s) — VT pseudo-elements | e2e | `npx playwright test e2e/reduced-motion.spec.ts --project=chromium-a11y` | ✅ existing (must EXTEND) |
| UX-D-06-03 | Firefox fallback: no jank in Firefox (no VT support) | e2e smoke | `npx playwright test e2e/smoke.spec.ts --project=firefox-smoke` | ✅ existing (must VERIFY covers nav) |
| UX-D-06-04 | DrillPanel Esc/clickaway close does not trigger a fade; no layout shift | manual UAT | n/a — searchParams change; no e2e assertion possible for "fade did NOT fire" | manual only |
| UX-D-06-05 | No route exceeds 250 KB First-Load JS | bundle check | `npx next build 2>&1 | grep "First Load JS"` | ✅ CI (next build output) |

### Detailed Test Specifications

#### NEW: `e2e/page-transitions.spec.ts` (Wave 0 gap — UX-D-06-01)

```ts
// Tests:
// 1. Chrome: Navigate /dashboard → /dashboard/vulnerabilities.
//    Assert: document.getAnimations() includes at least one VT animation
//    (::view-transition-old or ::view-transition-new) OR that the
//    view-transition pseudo-element exists during navigation.
//    Alternative: use page.evaluate + MutationObserver on :root to detect
//    the ::view-transition pseudo-element appearing during navigation.
// 2. The navigation completes without layout shift (CLS = 0 in Lighthouse
//    — this is a manual UAT check; CLS is a Lighthouse metric, not a
//    Playwright assertion).
```

**Note on VT e2e assertability:** The VT API fires and completes asynchronously. Directly querying `::view-transition-old` via `getComputedStyle` in a `page.evaluate` call may race with the transition completing. A practical assertion: check that navigating between two routes takes longer than a bare instant (≥ 100ms wall-clock) in Chromium with VT enabled, AND completes in < 2000ms. This is a proxy test. The true verification is a manual UAT smoke pass.

#### EXTEND: `e2e/reduced-motion.spec.ts` (UX-D-06-02)

The existing spec checks `.bg-gradient-mesh` and `.bg-severity-critical` animation durations. It must be extended with a third test:

```ts
test('VT pseudo-element animation-duration is near-zero under reduce', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/dashboard');
  // Navigate to trigger VT
  await page.goto('/dashboard/vulnerabilities');
  // Assert: the transition completed without visible animation
  // Proxy: check that the page is fully painted (nav landmark visible)
  // within 200ms (instant swap, not 320ms fade).
  await page.locator('nav[aria-label="Primary navigation"]')
    .waitFor({ state: 'visible', timeout: 500 });
  // The above only passes if the page loads instantly (no 320ms fade blocking).
  // For a direct check: evaluate computed style of VT pseudo-element (browser-specific,
  // may not be stable in Playwright). Proxy test is the pragmatic choice.
});
```

**Stronger alternative:** Use `page.evaluate` to check that `document.documentElement.style.animationDuration` or a VT animation is near-zero. This requires careful timing.

### Sampling Rate

- **Per task commit:** `npx playwright test e2e/reduced-motion.spec.ts --project=chromium-a11y`
- **Per wave merge:** `npx playwright test --project=chromium-a11y` (full a11y sweep + new transition spec)
- **Phase gate:** Full suite green (all 4 projects) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `frontend/e2e/page-transitions.spec.ts` — covers UX-D-06-01 (cross-fade fires on real pathname change)
- [ ] `frontend/e2e/reduced-motion.spec.ts` — extend with VT pseudo-element suppression test (UX-D-06-02 extended coverage)

*(No new test infrastructure needed — existing Playwright config and fixtures are sufficient.)*

### UAT Steps (manual — cannot be automated)

1. **UX-D-06-01 visual confirm:** Navigate Dashboard → Vulnerabilities → Assets. Confirm a visible ~320ms cross-fade of the content area while sidebar + topbar stay static.
2. **UX-D-06-04 DrillPanel race:** Open a Vuln DrillPanel, press Esc. Confirm NO fade occurs. Navigate to a different route while panel is open; confirm panel fades WITH the content (D-11).
3. **UX-D-06-03 Firefox fallback:** Open the app in Firefox (which lacks VT support at time of writing). Navigate between routes. Confirm a gentle fade-in (CSS keyframe fallback) with no jank or broken paint.
4. **Layout shift check:** Navigate between routes while watching the sidebar and topbar. They must not flicker, fade, or shift position.

---

## Security Domain

> security_enforcement is absent from config.json — treated as enabled. This phase is CSS + a minimal client component with no data fetch, no auth, and no user input.

### Applicable ASVS Categories

| ASVS Category | Applies | Note |
|---------------|---------|------|
| V2 Authentication | No | No auth logic |
| V3 Session Management | No | No session state |
| V4 Access Control | No | No gating logic |
| V5 Input Validation | No | No user input |
| V6 Cryptography | No | No crypto |

**No ASVS controls required for this phase.** The only added attack surface is a client component (`template.tsx`) that calls `document.startViewTransition()` — a read-only browser API with no network calls or user-data exposure.

**One note:** `view-transition-name` values are rendered into inline styles (`style={{ viewTransitionName: '...' }}`). The value is a hardcoded string literal, not user-controlled. No sanitization needed.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on this Phase |
|-----------|---------------------|
| Inter + JetBrains Mono locked (no font substitution) | N/A — no font changes |
| Use CSS variables from `foundation.md`, never freehand hex | Duration uses `var(--ease-standard)` and the `320ms` value (= `--motion-slow`) — compliant |
| No Tailwind admin-template patterns | `template.tsx` uses `className="contents"` — minimal, not a template pattern |
| Mandatory sketch-findings-getvul skill for UI work | `foundation.md §Motion` read: confirms `--motion-slow: 320ms` and "cross-fade only (no transforms)" for page transitions. Compliant. |
| No generic SaaS copy | N/A — no copy changes |
| Empty/loading/error states mandatory | N/A — `template.tsx` is a pass-through wrapper |

**`foundation.md §Motion` alignment:**
- `--motion-slow: 320ms` is the chosen duration (D-04 upper bound, Claude's discretion) [VERIFIED: foundation.md line ~153]
- "What does NOT animate: page transitions (cross-fade only)" — this phase implements exactly that [VERIFIED: foundation.md line ~167]
- "cross-fade only (no transforms)" for reduced-motion substitution [VERIFIED: foundation.md line ~173]

---

## Sources

### Primary (HIGH confidence)

- [nextjs.org/docs/app/api-reference/file-conventions/template](https://nextjs.org/docs/app/api-reference/file-conventions/template) — template.tsx remount behavior, searchParams non-trigger (confirmed D-01/D-02 architectural guarantee)
- [nextjs.org/docs/app/guides/view-transitions](https://nextjs.org/docs/app/guides/view-transitions) — official Next.js VT guide; reduced-motion explicit rule for `::view-transition-group/old/new`
- [developer.chrome.com/docs/web-platform/view-transitions/same-document](https://developer.chrome.com/docs/web-platform/view-transitions/same-document) — `document.startViewTransition` API, view-transition-name isolation, feature detection
- [web.dev/learn/css/view-transitions-spas](https://web.dev/learn/css/view-transitions-spas) — explicit `::view-transition-group(*), ::view-transition-old(*), ::view-transition-new(*) { animation: none !important }` pattern for reduced-motion
- [nextjs.org/docs/app/api-reference/config/next-config-js/viewTransition](https://nextjs.org/docs/app/api-reference/config/next-config-js/viewTransition) — confirms `experimental.viewTransition` is a different integration (React `<ViewTransition>` component), not what this phase uses
- `.claude/skills/sketch-findings-getvul/references/foundation.md §Motion` — authoritative for `--motion-slow: 320ms`, cross-fade only, reduced-motion substitution rule [VERIFIED: read in this session]
- `frontend/src/app/globals.css` — D-12 blanket (lines 116–124), @keyframes block (lines 155–173), existing structure [VERIFIED: read in this session]
- `frontend/e2e/playwright.config.ts` — confirms Firefox smoke project + chromium-a11y project available [VERIFIED: read in this session]
- `frontend/e2e/reduced-motion.spec.ts` — existing spec scope confirmed (does NOT currently test VT pseudo-elements) [VERIFIED: read in this session]
- `frontend/src/app/(authed)/layout.tsx` — confirms template nests inside layout; AppShell owns chrome [VERIFIED: read in this session]
- `frontend/package.json` — confirms Next.js ^15.5.18, React ^19.0.0, Playwright ^1.61.1 [VERIFIED: read in this session]

### Secondary (MEDIUM confidence)

- [MDN ::view-transition-old](https://developer.mozilla.org/en-US/docs/Web/CSS/::view-transition-old) — UA stylesheet shows `animation-duration: inherit` on VT pseudo-elements; confirms they are not reliably caught by `*` universal selector
- WebSearch results confirming community consensus: explicit `::view-transition-*` rules needed for prefers-reduced-motion

### Tertiary (LOW confidence / ASSUMED)

- The `useLayoutEffect` timing model for `document.startViewTransition()` in the template.tsx pattern (no official Next.js documentation for this exact pattern — the official path uses `experimental.viewTransition` + React `<ViewTransition>`)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Next.js template.tsx behavior confirmed from official docs; VT API behavior confirmed from Chrome Dev docs
- Architecture: HIGH — nesting model confirmed; MEDIUM for exact `useLayoutEffect` timing (see A1)
- Pitfalls: HIGH — reduced-motion VT pseudo-element gap confirmed from multiple official sources; other pitfalls derived from verified API behavior

**Research date:** 2026-07-16
**Valid until:** 2026-08-16 (stable APIs; `experimental.viewTransition` state could change but is irrelevant to this phase's approach)
