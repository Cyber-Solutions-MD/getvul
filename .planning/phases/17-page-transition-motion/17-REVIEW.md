---
phase: 17-page-transition-motion
reviewed: 2026-07-16T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - frontend/e2e/page-transitions.spec.ts
  - frontend/e2e/reduced-motion.spec.ts
  - frontend/src/app/(authed)/template.tsx
  - frontend/src/app/globals.css
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-07-16T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 17 wires page-transition motion via the View Transitions API: an `(authed)/template.tsx`
that calls `document.startViewTransition()` on pathname change, a `globals.css` block that names
the content wrapper, overrides the cross-fade duration, suppresses VT pseudo-elements under
`prefers-reduced-motion`, and provides a Firefox/no-VT keyframe fallback. Two Playwright specs act
as the quality gate.

The reduced-motion suppression, the module-level first-mount guard, the SSR/feature-detect guards,
and the searchParams-vs-pathname architecture are all sound and correctly reasoned in the inline
comments. Token references (`--motion-slow`, `--ease-standard`) resolve against `sunset.css`, and
the e2e viewport (1280px) keeps the `Primary navigation` landmark visible (sidebar hides at ≤999px).

However, two design choices in `template.tsx` + `globals.css` interact in ways that likely make the
*named* cross-fade a visual no-op rather than the intended old→new page fade. These are correctness
concerns worth confirming against a real browser run before treating the e2e green as proof of the
UX. Neither is a security or crash risk, so both are Warnings, not Critical. The e2e specs are
structurally solid but assert only "a VT animation fired," which the no-op path would still satisfy —
so the gate can pass while the visible effect is wrong.

## Warnings

### WR-01: `view-transition-name` is set on a `display: contents` element — no box to snapshot

**File:** `frontend/src/app/(authed)/template.tsx:59`, `frontend/src/app/globals.css:179-181`
**Issue:** The wrapper is `className="authed-page-content contents"`. The `contents` utility applies
`display: contents`, which means the element generates **no principal box** — its children are
promoted into the parent box for layout. Per the CSS View Transitions spec, `view-transition-name`
takes effect on an element that generates a box (it snapshots that element's rendered
representation). An element with `display: contents` has no box, so the browser has nothing to
capture for the `authed-page-content` named transition. In practice the named
`::view-transition-old(authed-page-content)` / `-new(...)` group is not produced, and the transition
falls back to the default `root` snapshot — which is exactly the sidebar+topbar-included fade that
D-05 says to avoid.

The comment on line 21-22 asserts `contents` is chosen so "no route shifts (A2)," and the comment on
line 19-20 asserts the class "receives view-transition-name ... isolating the content snapshot from
the root" — these two goals are in direct tension on the same element. You cannot both opt the
element out of the box tree (`display: contents`) and ask the browser to snapshot that element's box.

**Fix:** Give the wrapper a real box that fills its slot without shifting layout, e.g. drop `contents`
and use a block that does not perturb the flex/grid parent:
```tsx
// template.tsx — give the VT-named element an actual box
<div className="authed-page-content" {...(noVt ? { 'data-no-vt': '' } : {})}>
  {children}
</div>
```
```css
/* globals.css — ensure the box fills the content slot without introducing a shift */
.authed-page-content {
  view-transition-name: authed-page-content;
  display: flow-root; /* or block; must NOT be `contents` */
  min-height: 0;
}
```
Then verify in a real Chromium run that `::view-transition-group(authed-page-content)` appears in
`document.getAnimations()` (the current spec does not distinguish the named group from the `root`
group — see WR-03).

### WR-02: `startViewTransition()` called with no callback after the DOM already shows the new page — captures identical old/new snapshots

**File:** `frontend/src/app/(authed)/template.tsx:48`
**Issue:** `startViewTransition()` is invoked from `useLayoutEffect`, which runs **after** React has
committed the remounted subtree — i.e. the new route's DOM is already on screen. The comment on line
46-47 acknowledges this ("React has already committed the new DOM on remount. No update callback").
But the View Transitions algorithm is: capture the **old** snapshot → run the callback to mutate the
DOM → capture the **new** snapshot → animate old→new. With no callback and the DOM already displaying
the destination page, the "old" and "new" snapshots are captured from the *same* post-navigation
frame. The cross-fade then animates between two identical images — a 320ms no-op, not a fade from the
previous page. The outgoing (dashboard) content is never captured as the "old" state because it was
already replaced before the effect ran.

To capture the outgoing page as "old," the transition must start **before** React commits the new
DOM, with the DOM mutation happening inside the callback. In the App Router `template.tsx` remount
model this is awkward because the framework controls the commit; the common patterns are to
intercept navigation (patch `router` / use `next-view-transitions`) or to start the transition in a
navigation event rather than a post-commit layout effect.

**Fix:** Confirm the intended visual (does the UX want an old→new cross-fade, or just a fade-in of the
new page?). If the design is a fade-*in* of the arriving page only, the `startViewTransition()` call
is the wrong tool — the `[data-no-vt]` `page-fade-in` keyframe (globals.css:206-212) already
expresses that and could be used for all browsers. If the design genuinely wants an outgoing→incoming
cross-fade, the transition must be initiated on the client-side navigation *before* the new segment
commits, e.g. via the `next-view-transitions` package or by wrapping `router.push` so the DOM swap
occurs inside the `startViewTransition` callback. As written, the effect fires a transition whose old
and new frames are the same, which the e2e (WR-03) cannot tell apart from a correct one.

### WR-03: e2e specs assert "a VT animation fired," not "the named content cross-fade fired" — green gate does not prove the intended effect

**File:** `frontend/e2e/page-transitions.spec.ts:49-62`, `frontend/e2e/reduced-motion.spec.ts:136-150`
**Issue:** Both specs filter `document.getAnimations()` for any pseudo-element whose name
`.includes('view-transition')`. This matches the default `::view-transition-old(root)` /
`-new(root)` animations that the browser generates for *any* `startViewTransition()` call — even when
the named `authed-page-content` group never forms (WR-01) and even when old==new (WR-02). So the
positive test (`toBeGreaterThanOrEqual(1)`) passes on the fallback/root path, and the reduced-motion
suppression test passes because the suppressor uses the `(*)` universal selector that also covers
`root`. The gate therefore cannot detect the two Warnings above; it verifies "some view transition
occurred," which is a weaker claim than the phase's D-03/D-05 contract ("only page content fades, on
a real pathname change").

**Fix:** Tighten the positive assertion to require the *named* group, so the gate fails if the name
never binds (WR-01):
```ts
const namedVtCount = await page.evaluate(() =>
  document.getAnimations().filter((a) => {
    const pe = (a.effect as CSSEffect | null)?.pseudoElement;
    return typeof pe === 'string' && pe.includes('authed-page-content');
  }).length,
);
expect(namedVtCount).toBeGreaterThanOrEqual(1);
```
Consider also asserting that the `root` group did NOT animate (chrome stays static, D-05), which is
the actual UX guarantee. Detecting the WR-02 old==new no-op from Playwright is harder, but a visual
snapshot diff mid-transition (or asserting the outgoing page's marker is still painted during the
fade) would close that gap.

## Info

### IN-01: `PopStateEvent` proxy for a searchParams change may not exercise the real App Router remount path

**File:** `frontend/e2e/page-transitions.spec.ts:94-99`
**Issue:** The "searchParams-only" negative test synthesizes the change with
`history.pushState(...)` + `dispatchEvent(new PopStateEvent('popstate'))` rather than driving Next's
`router.replace`/`useSearchParams`. The comment (lines 90-93) acknowledges this is a "proxy." A raw
`pushState` does not necessarily run the Next.js client router's segment-diffing that decides whether
`template.tsx` remounts, so a passing test here weakly supports the D-02 guarantee. It cannot produce
a false failure (no VT is expected either way), so severity is Info, but the assertion proves less
than the comment implies.
**Fix:** Where an interactive `?tab=` / `?view=` control is reachable in the authed session, prefer
clicking it so the real router path is exercised; keep the `pushState` proxy only as a documented
fallback.

### IN-02: Reduced-motion hero test silently passes when the urgency dot is absent

**File:** `frontend/e2e/reduced-motion.spec.ts:80-85`
**Issue:** When `.bg-severity-critical.rounded-full` is not in the DOM (quiet-win mode,
`criticalOpen === 0`), the test `console.warn`s and `return`s — a silent pass that asserts nothing.
Because the fixture's critical-open count is data-dependent, this test can pass in CI without ever
evaluating the reduced-motion behavior it exists to guard. Not a bug in the code under review, but a
gate that can no-op.
**Fix:** Seed the test with a fixture guaranteeing `criticalOpen > 0`, or use
`test.skip(durationSeconds === null, '...')` so the skipped state is visible in the report rather than
reported as a pass.

### IN-03: Firefox fallback fires on every pathname remount, including cases the VT guard would skip

**File:** `frontend/src/app/globals.css:210-212`, `frontend/src/app/(authed)/template.tsx:55-59`
**Issue:** On no-VT browsers, `data-no-vt` is set whenever `startViewTransition` is unavailable, and
the CSS keyframe `page-fade-in` runs on *every* mount of `.authed-page-content` — including the very
first paint / hard refresh. The JS first-mount guard (`isFirstMount`, lines 31-43) suppresses the VT
path on first load, but the CSS fallback has no equivalent first-mount guard, so no-VT browsers get a
fade-in on initial app entry that D-07/D-08 say to avoid for the VT path. Minor and browser-specific
(Firefox), hence Info.
**Fix:** If D-07/D-08 should apply uniformly, gate the fallback keyframe behind a class the template
adds only after first mount (e.g. add `data-no-vt` only when `!isFirstMount`), or accept the
first-paint fade-in for no-VT browsers and document the intentional divergence.

---

_Reviewed: 2026-07-16T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
