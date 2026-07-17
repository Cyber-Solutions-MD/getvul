// UX-07-04 — Reduced-motion quality gate.
//
// Emulates `prefers-reduced-motion: reduce` and asserts that the animated
// elements on key pages report a near-zero computed animation-duration
// (globals.css blanket: animation-duration: 0.01ms !important).
//
// The test uses chromium-a11y project (default for non-smoke specs).
// storageState is set at the project level in playwright.config.ts.
//
// Spec context (Plan 03, 15-03-SUMMARY.md):
//   - login/page.tsx: .bg-gradient-mesh uses motion-safe:animate-gradient-drift
//     The globals.css blanket reduces it to 0.01ms under prefers-reduced-motion.
//   - hero.tsx: .bg-severity-critical urgency dot uses motion-safe:animate-pulse
//     Same blanket applies.
//
// Assert: computed animationDuration parses to <= 0.02 seconds.
// (0.01ms = 0.00001s << 0.02s threshold; any real animation would be >> 0.5s)

import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

test.describe('Reduced-motion emulation', () => {
  test('login gradient-mesh animation-duration is near-zero under reduce', async ({ page }) => {
    // Emulate prefers-reduced-motion: reduce BEFORE navigation
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/login');

    // Wait for the page to render — login has no nav landmark, wait for h2
    await page.locator('h2').first().waitFor({ state: 'visible', timeout: 10_000 });

    // The gradient-drift element is only visible at lg (1024px+), but its
    // animation-duration is set by the globals.css blanket regardless of
    // visibility. We evaluate on the DOM element directly.
    const durationSeconds = await page.evaluate(() => {
      const el = document.querySelector('.bg-gradient-mesh');
      if (!el) return null;
      const raw = getComputedStyle(el).animationDuration;
      // animationDuration is like "0.01ms" or "none" or "0s"
      if (!raw || raw === 'none' || raw === 'initial') return 0;
      // Parse value: may be in ms or s
      const msMatch = raw.match(/^([\d.]+)ms$/);
      const sMatch = raw.match(/^([\d.]+)s$/);
      if (msMatch) return parseFloat(msMatch[1]) / 1000;
      if (sMatch) return parseFloat(sMatch[1]);
      return 0;
    });

    // durationSeconds can be null if the element is not in the DOM at this viewport
    // (lg:flex means it is only rendered at >= 1024px). At 1280px it IS rendered.
    expect(durationSeconds, 'bg-gradient-mesh animationDuration must be <= 0.02s under reduced motion').not.toBeNull();
    expect(durationSeconds!).toBeLessThanOrEqual(0.02);
  });

  test('dashboard hero urgency-dot animation-duration is near-zero under reduce', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/dashboard');

    // Wait for nav landmark to confirm auth + hydration
    await page.locator('nav[aria-label="Primary navigation"]').waitFor({ state: 'visible', timeout: 10_000 });

    // The urgency dot is .bg-severity-critical.motion-safe:animate-pulse
    // Under reduced motion the globals.css blanket forces animationDuration to 0.01ms.
    // The motion-safe: prefix already gates the class — under reduce, animate-pulse
    // class is NOT applied. Either way: duration should be near-zero.
    const durationSeconds = await page.evaluate(() => {
      // Select the urgency dot: a span with bg-severity-critical and rounded-full
      // in the hero section. The urgency dot renders only when criticalOpen > 0.
      const el = document.querySelector('span.bg-severity-critical.rounded-full');
      if (!el) return null;
      const raw = getComputedStyle(el).animationDuration;
      if (!raw || raw === 'none' || raw === 'initial') return 0;
      const msMatch = raw.match(/^([\d.]+)ms$/);
      const sMatch = raw.match(/^([\d.]+)s$/);
      if (msMatch) return parseFloat(msMatch[1]) / 1000;
      if (sMatch) return parseFloat(sMatch[1]);
      return 0;
    });

    // IN-02 fix: make the absent-element case visible in the report rather than a
    // silent pass. test.skip() marks the test as intentionally skipped (criticalOpen=0,
    // quiet-win mode) so it is clearly visible, not buried in console.warn output.
    if (durationSeconds === null) {
      test.skip(true, '[IN-02] hero urgency dot not in DOM — criticalOpen is 0 (quiet-win mode). Seed fixture with criticalOpen > 0 for full coverage.');
      return;
    }
    expect(durationSeconds).toBeLessThanOrEqual(0.02);
  });

  // UX-D-01-06 (Pitfall 2) — Board DragOverlay drop-tween suppression guard.
  //
  // @dnd-kit's DragOverlay drop animation uses the Web Animations API
  // (element.animate()), which the globals.css CSS blanket does NOT touch. The board
  // must explicitly gate `dropAnimation={reduced ? null : undefined}` on <DragOverlay>
  // (usePrefersReducedMotion()) for this to hold. RED now — the board doesn't exist yet
  // (Wave 2, 18-03, must wire the gate for this to turn GREEN).
  test('board drag drop animation is suppressed under prefers-reduced-motion', async ({ page }) => {
    // Emulate prefers-reduced-motion: reduce BEFORE navigation.
    await page.emulateMedia({ reducedMotion: 'reduce' });

    await page.goto('/dashboard/tickets?view=board');
    await page.locator('nav[aria-label="Primary navigation"]').waitFor({ state: 'visible', timeout: 10_000 });

    const cards = page.locator('[data-ticket-id]');
    const cardCount = await cards.count();
    if (cardCount === 0) {
      test.skip(true, '[board] no seeded tickets — cannot exercise drag-drop tween suppression');
      return;
    }

    const sourceCard = cards.first();
    const sourceBox = await sourceCard.boundingBox();
    if (!sourceBox) {
      test.skip(true, '[board] source card has no bounding box');
      return;
    }

    // A no-op read-only→read-only drop still triggers the DragOverlay drop tween.
    await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(sourceBox.x + sourceBox.width / 2 + 15, sourceBox.y + sourceBox.height / 2 + 15, {
      steps: 5,
    });
    await page.mouse.up();

    // Poll ~500ms for any in-flight animation attributable to the drag overlay.
    const pollMs = 500;
    const intervalMs = 50;
    const deadline = Date.now() + pollMs;
    let maxDurationMs = 0;

    while (Date.now() < deadline) {
      const durations = await page.evaluate(() =>
        document.getAnimations().map((a) => {
          const timing = a.effect?.getComputedTiming?.();
          const d = timing?.duration;
          return typeof d === 'number' ? d : 0;
        }),
      );
      const maxThisTick = durations.length > 0 ? Math.max(...durations) : 0;
      if (maxThisTick > maxDurationMs) maxDurationMs = maxThisTick;
      await page.waitForTimeout(intervalMs);
    }

    // No in-flight animation attributable to the drag overlay should run longer than 20ms
    // — the board must pass dropAnimation={reduced ? null : undefined}.
    expect(
      maxDurationMs,
      `Board drag-drop animation duration must be <= 20ms under prefers-reduced-motion (got ${maxDurationMs}ms).`,
    ).toBeLessThanOrEqual(20);
  });

  // UX-D-06-02 — VT pseudo-element reduced-motion suppression guard.
  //
  // WR-03 fix: the poll filter now targets the NAMED 'authed-page-content' group
  // (::view-transition-group/old/new(authed-page-content)) instead of any pseudo-element
  // containing 'view-transition'. The generic match also catches the default root animations
  // and cannot detect WR-01/WR-02. The named-group filter only fires if the content wrapper
  // has a real box and the named transition actually formed.
  //
  // Two acceptable suppressed states:
  //   a) Named authed-page-content VT animations exist but are <= 20ms (suppress working).
  //   b) No named group animations appear (instant swap — also valid suppressed state).
  test('view-transition pseudo-elements are suppressed under prefers-reduced-motion', async ({ page }) => {
    // Emulate prefers-reduced-motion: reduce BEFORE navigation (matching the existing pattern).
    await page.emulateMedia({ reducedMotion: 'reduce' });

    // Navigate to dashboard and wait for auth + hydration.
    await page.goto('/dashboard');
    await page.locator('nav[aria-label="Primary navigation"]').waitFor({ state: 'visible', timeout: 10_000 });

    // Trigger a client-side pathname change by clicking the Vulnerabilities nav link.
    // This is exactly what would fire a VT animation under normal motion.
    // Under prefers-reduced-motion: reduce, the explicit VT suppressor rule pinned
    // the duration to 0.01ms — so any named authed-page-content VT animation that fires
    // should be near-instant.
    const vulnLink = page
      .locator('nav[aria-label="Primary navigation"]')
      .getByRole('link', { name: /vulnerab/i });
    await vulnLink.click();

    // Assert suppression via a bounded poll (~800ms).
    // WR-03: filter on pseudoElement containing 'authed-page-content' to match only the
    // named group (::view-transition-group(authed-page-content), -old(...), -new(...)).
    // This is tighter than the previous 'view-transition' substring which matched root too.
    const pollMs = 800;
    const intervalMs = 50;
    const deadline = Date.now() + pollMs;

    let maxVtDurationMs = 0; // Tracks the maximum named-group VT animation duration seen
    let vtAnimationEverSeen = false;

    while (Date.now() < deadline) {
      const vtDurations = await page.evaluate(() => {
        return document
          .getAnimations()
          .filter(
            (a) =>
              typeof (a.effect as VTEffect | null)?.pseudoElement === 'string' &&
              ((a.effect as VTEffect).pseudoElement as string).includes('authed-page-content'),
          )
          .map((a) => {
            // getComputedTiming().duration returns a number in ms (or the string 'auto').
            const timing = (a.effect as VTEffect).getComputedTiming();
            const d = timing.duration;
            return typeof d === 'number' ? d : 0;
          });
      });

      if (vtDurations.length > 0) {
        vtAnimationEverSeen = true;
        const maxThisTick = Math.max(...vtDurations);
        if (maxThisTick > maxVtDurationMs) maxVtDurationMs = maxThisTick;
      }

      await page.waitForTimeout(intervalMs);
    }

    // If any named authed-page-content VT animations were observed, assert their
    // duration is near-zero (<= 20ms) — the explicit reduce suppressor pinned to 0.01ms.
    if (vtAnimationEverSeen) {
      expect(
        maxVtDurationMs,
        `Named authed-page-content VT animation duration must be <= 20ms under prefers-reduced-motion (got ${maxVtDurationMs}ms).`,
      ).toBeLessThanOrEqual(20);
    }
    // If no named VT animations were seen at all, the test passes:
    // instant swap with no animation is also a valid suppressed state.

    // Confirm the destination rendered without unexpected delay.
    // A 320ms fade would still leave the nav landmark visible (it fades content, not chrome),
    // but a timeout of 500ms confirms no unexpected delay.
    await page.locator('nav[aria-label="Primary navigation"]').waitFor({ state: 'visible', timeout: 500 });
  });
});

// TypeScript helper type: KeyframeEffect exposes pseudoElement and getComputedTiming(),
// but the base AnimationEffect type in lib.dom.d.ts does not include pseudoElement.
// CSSEffect is used in page-transitions.spec.ts; VTEffect is this file's alias.
type VTEffect = { pseudoElement: string | null; getComputedTiming: () => { duration: number | 'auto' } };
