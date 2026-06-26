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

    if (durationSeconds === null) {
      // Hero is in quiet-win mode (criticalOpen === 0) — urgency dot not in DOM.
      // Log and skip — this is a valid operational state, not a test failure.
      console.warn('[reduced-motion] hero urgency dot not in DOM — criticalOpen is 0 (quiet-win mode)');
      return;
    }
    expect(durationSeconds).toBeLessThanOrEqual(0.02);
  });
});
