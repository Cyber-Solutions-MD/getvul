---
phase: 21-page-transition-verification
reviewed: 2026-07-21T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - frontend/e2e/page-transitions.spec.ts
  - frontend/e2e/playwright.config.ts
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-07-21
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the two Phase 21 e2e artifacts: the hardened `page-transitions.spec.ts`
(real router-driven View Transitions assertions + a Firefox dual-branch feature-detect)
and the `playwright.config.ts` change that registers the new `firefox-transitions`
project. No production code changed in this phase.

Overall the hardening is solid and the intent is well-documented: the positive
cross-fade tests carry genuine `>= 1` assertions plus a `toHaveURL` destination check,
the Firefox project scoping gap (`firefox-smoke` only matching `smoke.spec.ts`) is
correctly closed by a dedicated `firefox-transitions` project, and the describe-level
`browserName === 'firefox'` skip is defense-in-depth alongside `testMatch` scoping. The
feature-detecting dual-branch Firefox logic is correct in principle (it detects exactly
what `template.tsx` detects).

However, three tests can pass **vacuously** — they assert an *absence* (0 fades / no
layout shift / no observed animation) without first proving the action they are gating
on actually occurred. In an e2e suite whose whole purpose is to be "the arbiter," a
vacuous green is the most dangerous outcome because it silently retires the very signal
the test exists to protect. Details below.

## Warnings

### WR-01: Firefox reduced-motion native branch can pass with zero executed assertions

**File:** `frontend/e2e/page-transitions.spec.ts:362-397`
**Issue:** In the `supportsNativeVt` branch, when `everSeen` stays `false` (no named VT
animation observed at all — which the file itself documents as the actual behavior of
the installed Firefox), the `if (everSeen) { expect(...) }` block never runs and the
branch executes **no assertion whatsoever**. There is also no `toHaveURL` / nav guard.
So a completely broken navigation on Firefox (link never clicked, page errored, wrong
route, hydration failure) produces the identical "no animation observed" state and the
test passes green. The comment "No named animation observed at all is also a valid
suppressed state" is correct for the *reduced-motion* contract, but the test has no
independent proof that a navigation was even attempted — the suppressed-state pass and
the broken-nav pass are indistinguishable.
**Fix:** Add a positive liveness assertion so the "instant swap" pass is only reachable
after a real navigation:
```ts
await page.locator('nav[aria-label="Primary navigation"]')
  .getByRole('link', { name: /vulnerab/i }).click();

// Prove the navigation actually happened before accepting "no animation" as valid.
await expect(page).toHaveURL(/\/dashboard\/vulnerabilities/);

if (supportsNativeVt) {
  // ... existing poll ...
  if (everSeen) {
    expect(maxDurationMs, '...').toBeLessThanOrEqual(20);
  }
  // now "not seen" is a *suppressed* state, not a *broken-nav* state.
}
```

### WR-02: searchParams-only no-fade test never proves searchParams actually changed

**File:** `frontend/e2e/page-transitions.spec.ts:141-159`
**Issue:** This is the primary UX-D-06-04 no-fade evidence, but it only asserts (a)
`maxNamedVtCount === 0` and (b) `pathnameAfter === pathnameBefore`. Both hold trivially
if the ChipBar click is a **no-op** — e.g. the button resolves but its handler is not
wired, or the click lands but `router.replace` never fires. In that case the test still
goes green while proving nothing about the "searchParams change → no remount → no fade"
guarantee it is meant to establish. The test verifies the chip is *visible* and clicks
it, but never verifies the search string actually mutated.
**Fix:** Assert the searchParams changed (while pathname did not) so the no-fade result
is conditioned on a real searchParams mutation:
```ts
const searchBefore = await page.evaluate(() => location.search);
await criticalChip.click();
await expect(page).toHaveURL(/[?&]severity=critical/); // real router.replace landed
const maxNamedVtCount = await pollMaxNamedVt(page, 800);
expect(maxNamedVtCount, '...').toBe(0);
const searchAfter = await page.evaluate(() => location.search);
expect(searchAfter).not.toBe(searchBefore);
expect(await page.evaluate(() => location.pathname)).toBe(pathnameBefore);
```

### WR-03: `getByRole('button', { name: /critical/i })` is data-dependent and strict-mode fragile

**File:** `frontend/e2e/page-transitions.spec.ts:141`
**Issue:** The selector relies on a substring regex (`/critical/i`) matching exactly one
button in the current seeded data state (the comment documents `count=1`). Playwright
runs in strict mode, so if any other "Critical"-labeled button ever renders in this
session (a second severity control, a summary badge rendered as a button, a modal CTA),
`expect(criticalChip).toBeVisible()` and `.click()` will throw a strict-mode violation,
or click the wrong control. The test's correctness is coupled to a fixture invariant
that lives outside this file, making it a latent flake as seed data or the ChipBar
evolves.
**Fix:** Pin to a stable, unambiguous selector — a `data-testid` on the severity chip,
or scope within the ChipBar's accessible container and use an exact name:
```ts
const criticalChip = page.getByTestId('chipbar-severity-critical');
// or, scoped + exact:
const criticalChip = page.getByRole('group', { name: /severity/i })
  .getByRole('button', { name: 'Critical', exact: true });
```

## Info

### IN-01: `boundingBox()` deep-equality is sub-pixel fragile

**File:** `frontend/e2e/page-transitions.spec.ts:221, 249`
**Issue:** `expect(navAfter).toEqual(navBefore)` deep-compares `{x, y, width, height}`
floats. `boundingBox()` can return sub-pixel values, and a fractional-pixel reflow
during the transition (fonts settling, scrollbar gutter, transform rounding) would fail
the strict deep-equal even though there is no visible chrome shift. This can surface as
an intermittent red on an otherwise-correct app.
**Fix:** Compare with a tolerance instead of exact deep-equality:
```ts
expect(Math.abs(navAfter!.x - navBefore!.x)).toBeLessThanOrEqual(1);
expect(Math.abs(navAfter!.y - navBefore!.y)).toBeLessThanOrEqual(1);
expect(Math.abs(navAfter!.width - navBefore!.width)).toBeLessThanOrEqual(1);
expect(Math.abs(navAfter!.height - navBefore!.height)).toBeLessThanOrEqual(1);
```

### IN-02: Both Firefox `else` (CSS-fallback) branches are unexercised on the installed engine

**File:** `frontend/e2e/page-transitions.spec.ts:342-348, 398-408`
**Issue:** The file documents that the installed Firefox (151.0) supports
`startViewTransition`, so `supportsNativeVt` is always `true` and the fallback branches
(`data-no-vt` / `page-fade-in` keyframe assertions) never run in CI. Keeping them for a
future/older Firefox is a reasonable, well-justified decision — but it is untested test
code: a typo or logic error in the fallback branch (e.g. the `parseFloat` of a
comma-separated `animationDuration`, line 404) would go undetected until an engine that
lacks VT support appears. Worth a note so a future reader knows the branch has never
actually executed green.
**Fix:** No change required; optionally add a targeted unit-style test that forces the
fallback path (e.g. inject `delete document.startViewTransition` via `addInitScript`)
so the fallback assertions are exercised at least once.

### IN-03: Residual sampling-window flake on the `toBe(0)` no-fade assertions

**File:** `frontend/e2e/page-transitions.spec.ts:71-90` (used at 149, 179, 236)
**Issue:** `pollMaxNamedVt` samples `getAnimations()` every 50ms across the window. A
named VT cross-fade that both starts and finishes entirely between two samples would be
missed, turning a real (unwanted) fade into a false `toBe(0)` pass. At the default VT
duration (~250ms) versus a 50ms cadence this is low-probability, but it is a structural
false-negative path for the absence assertions specifically (the positive tests are safe
because they only need to catch the animation once). Combined with WR-02 this is the
weakest link in the no-fade evidence chain.
**Fix:** Lower the sampling interval for the no-fade windows (e.g. 16–25ms) to increase
the chance of catching a stray short animation, or instrument
`document.startViewTransition` via `addInitScript` to count invocations deterministically
rather than sampling running animations.

### IN-04: Poll-body duplication across two helpers and the inline Firefox loop

**File:** `frontend/e2e/page-transitions.spec.ts:44-90, 304-333`
**Issue:** The named-VT `getAnimations().filter(...)` predicate is copy-pasted three
times: `clickAndPollNamedVt`, `pollMaxNamedVt`, and the inline Firefox loop
(308-333). Divergence between copies (one already differs by also tracking `sawFallback`)
risks the three tests silently measuring subtly different things over time.
**Fix:** Extract a single `countNamedVt(page)` evaluate helper (and a `sampleFirefox`
variant) and have all three call sites reuse it, so the pseudoElement predicate lives in
exactly one place.

---

_Reviewed: 2026-07-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
