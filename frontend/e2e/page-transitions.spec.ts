// UX-D-06-01 — Page-transition motion quality gate.
//
// Asserts that a View Transitions cross-fade fires on a real pathname change
// (Dashboard → Vulnerabilities) and does NOT fire on a searchParams-only change.
//
// WR-03 fix: assertions now target the NAMED 'authed-page-content' group specifically
// (e.g. ::view-transition-group(authed-page-content), -old(authed-page-content),
// -new(authed-page-content)) rather than any pseudo-element containing 'view-transition'.
// The generic string match was passing on the default ::view-transition-old(root)
// animation (which fires even when the named group never forms, covering WR-01/WR-02).
// The tightened assertion acts as the WR-02 arbiter: if it passes, a real named-group
// transition fired; if it fails, WR-02 is confirmed and must be escalated.
//
// Runs on the default `chromium-a11y` project — no new project registration needed.
// storageState is set at the project level in playwright.config.ts.
//
// D-01/D-02 architectural guarantee (from CONTEXT.md + RESEARCH.md):
//   - Pathname changes → template.tsx remounts → startViewTransition fires → named VT group animates.
//   - searchParams-only changes → template.tsx does NOT remount → no VT fires.

import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

test.describe('Page-transition motion', () => {
  test('cross-fade fires on a real pathname change (dashboard → vulnerabilities)', async ({ page }) => {
    // Navigate to the starting route and wait for auth + hydration.
    await page.goto('/dashboard');
    await page.locator('nav[aria-label="Primary navigation"]').waitFor({ state: 'visible', timeout: 10_000 });

    // Click the Vulnerabilities nav link to trigger a client-side pathname change.
    // This is the correct approach per D-07 ("no fade on first paint") — page.goto
    // is a hard navigation; clicking an in-app Link is a client-side route change
    // that will trigger template.tsx remount and startViewTransition.
    const vulnLink = page
      .locator('nav[aria-label="Primary navigation"]')
      .getByRole('link', { name: /vulnerab/i });

    // Poll for the NAMED 'authed-page-content' VT group animation immediately after clicking.
    // WR-03: filter specifically on pseudoElement containing 'authed-page-content' rather
    // than the generic 'view-transition' substring. This ensures we observe the isolated
    // content cross-fade (D-05) and not the fallback root animation.
    // The VT animation is short (~320ms) so we poll over a bounded window.
    const clickAndPoll = async (): Promise<number> => {
      // Click without awaiting page navigation (so polling starts in parallel).
      await vulnLink.click();

      // Poll up to ~1500ms at 50ms intervals for a named VT animation.
      const pollMs = 1500;
      const intervalMs = 50;
      const deadline = Date.now() + pollMs;

      while (Date.now() < deadline) {
        const namedVtCount = await page.evaluate(() =>
          document
            .getAnimations()
            .filter(
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

    const namedVtCount = await clickAndPoll();

    // Assert: at least one NAMED authed-page-content VT pseudo-element animation was
    // captured during the navigation window. This is the WR-02 arbiter:
    //   - PASS: confirms a real named-group transition fired (WR-01 + WR-02 resolved).
    //   - FAIL: named group never formed → WR-02 confirmed (escalate, do NOT weaken test).
    expect(
      namedVtCount,
      'Expected at least one authed-page-content named VT pseudo-element animation to fire during pathname change. ' +
      'FAIL = WR-02 confirmed: startViewTransition() called after DOM commit captures old==new. Escalate.',
    ).toBeGreaterThanOrEqual(1);

    // After navigation settles, confirm we reached the destination route.
    await expect(page).toHaveURL(/\/dashboard\/vulnerabilities/);
  });

  test('searchParams-only change does NOT trigger a page fade (D-02)', async ({ page }) => {
    // Navigate to the vulnerabilities route and wait for auth + hydration.
    await page.goto('/dashboard/vulnerabilities');
    await page.locator('nav[aria-label="Primary navigation"]').waitFor({ state: 'visible', timeout: 10_000 });

    // Capture the current pathname before the searchParams mutation.
    const pathnameBefore = await page.evaluate(() => location.pathname);

    // Trigger a searchParams-only change without altering the pathname.
    // This mirrors the DrillPanel / tab / view-toggle behaviour described in D-02:
    //   DrillPanel uses router.replace(pathname?drill=..., { scroll: false })
    //   tab switches use ?tab=...
    //   list/board toggle uses ?view=...
    // The history.pushState approach is an acceptable proxy for
    // "searchParams changed, pathname did not" when an interactive control
    // is not trivially reachable in a stateless test session.
    // IN-01: this proxy does not exercise the real App Router segment-diffing path;
    // kept as documented fallback — a real router.replace drive would be stronger.
    await page.evaluate(() => {
      const u = new URL(location.href);
      u.searchParams.set('tab', 'details');
      history.pushState({}, '', u);
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    // Poll for NAMED authed-page-content VT animations over ~800ms (WR-03 tightened).
    // Asserts that the count stays 0 — no named-group fade should fire on a searchParams change.
    // This asserts the D-01/D-02 architectural guarantee: template.tsx is keyed on the
    // segment, so searchParams changes never remount it and never trigger startViewTransition.
    const pollMs = 800;
    const intervalMs = 50;
    const deadline = Date.now() + pollMs;
    let maxNamedVtCount = 0;

    while (Date.now() < deadline) {
      const namedVtCount = await page.evaluate(() =>
        document
          .getAnimations()
          .filter(
            (a) =>
              typeof (a.effect as CSSEffect | null)?.pseudoElement === 'string' &&
              ((a.effect as CSSEffect).pseudoElement as string).includes('authed-page-content'),
          ).length,
      );
      if (namedVtCount > maxNamedVtCount) maxNamedVtCount = namedVtCount;
      await page.waitForTimeout(intervalMs);
    }

    expect(
      maxNamedVtCount,
      'Expected zero authed-page-content VT animations on a searchParams-only change (D-02: template.tsx does not remount on searchParams change)',
    ).toBe(0);

    // Pathname must be unchanged after the searchParams mutation.
    const pathnameAfter = await page.evaluate(() => location.pathname);
    expect(pathnameAfter).toBe(pathnameBefore);
  });
});

// TypeScript helper type: the Web Animations API `effect` property on Animation
// objects returned by document.getAnimations() can be a KeyframeEffect, which
// exposes a `pseudoElement` property. Cast is needed because the built-in
// AnimationEffect type does not expose pseudoElement.
type CSSEffect = { pseudoElement: string | null };
