// UX-07-07 + UX-07-05 — Cross-browser smoke + theme assertion.
//
// This file is matched by the three smoke Playwright projects defined in
// playwright.config.ts: chromium-smoke, webkit-smoke, firefox-smoke.
// It therefore runs in Chromium, WebKit (Safari engine), and Firefox.
//
// Per-test coverage:
//   UX-07-07: Each smoke route renders a known landmark/heading in all three engines.
//             Quick makeAxeBuilder() sweep asserts zero critical/serious violations.
//   UX-07-05 (automatable): data-theme on <html> reflects emulated prefers-color-scheme.
//             Emulate 'dark' → assert data-theme === 'dark'.
//             Emulate 'light' → assert data-theme === 'light'.
//             The pre-paint white-flash check is MANUAL (Plan 06 HUMAN-UAT).
//   Severity-glyph presence: on /dashboard/vulnerabilities, assert at least one of
//             ■ ▲ ◆ ○ □ appears in the page text content.
//             Legibility at 14px on real Safari DPR is the MANUAL Safari.app check
//             (Plan 06 HUMAN-UAT); automated check only confirms DOM presence.

import { test, expect } from './fixtures/axe';
import { discoverDetailRoute, waitForNav } from './routes';

// Smoke route set: login, dashboard, vulnerabilities, and one discovered detail page.
// Defined as a function so the detail-page discovery runs inside each test.

const SMOKE_STATIC = ['/login', '/dashboard', '/dashboard/vulnerabilities'] as const;

// --- Cross-browser smoke sweep (UX-07-07) ---
test.describe('Cross-browser smoke sweep', () => {
  test('smoke routes render and pass axe in all engines', async ({ page, makeAxeBuilder }) => {
    // Discover an asset detail page for the smoke run
    let detailRoute: string | null = null;
    try {
      detailRoute = await discoverDetailRoute(
        page,
        '/dashboard/assets',
        'a[href*="/dashboard/assets/"]',
      );
    } catch {
      console.warn('[smoke] Could not discover asset detail route — skipping detail smoke');
    }

    const routes: string[] = [...SMOKE_STATIC, ...(detailRoute ? [detailRoute] : [])];

    for (const route of routes) {
      await page.goto(route);

      if (route === '/login') {
        // Login page has no nav landmark — wait for an h2 heading
        await page.locator('h2').first().waitFor({ state: 'visible', timeout: 10_000 });
        const heading = page.locator('h2').first();
        await expect(heading).toBeVisible();
      } else {
        // Authed pages — wait for the desktop nav landmark
        await waitForNav(page, 1280);
        const nav = page.locator('nav[aria-label="Primary navigation"]');
        await expect(nav).toBeVisible();
      }

      // Quick axe check — blocking WCAG 2.1 AA
      const results = await makeAxeBuilder().analyze();
      const blocking = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious',
      );
      if (blocking.length > 0) {
        console.error(
          `[smoke] BLOCKING axe violations on ${route}:\n` +
            blocking
              .map((v) => `  [${v.impact}] ${v.id}: ${v.description}`)
              .join('\n'),
        );
      }
      expect(blocking, `Zero critical/serious axe violations on ${route} (smoke)`).toHaveLength(0);
    }
  });

  // Severity-glyph presence (UX-07-07 — automated DOM presence check)
  // Checks that at least one of the five severity glyphs (■ ▲ ◆ ○ □) from
  // visual-language.md is rendered in the page text.
  test('severity glyphs (■ ▲ ◆ ○ □) are present in /dashboard/vulnerabilities', async ({ page }) => {
    await page.goto('/dashboard/vulnerabilities');
    await waitForNav(page, 1280);

    const bodyText = await page.locator('body').textContent();
    const glyphs = ['■', '▲', '◆', '○', '□'];
    const found = glyphs.some((g) => bodyText?.includes(g));

    expect(
      found,
      `At least one severity glyph (■ ▲ ◆ ○ □) must appear in /dashboard/vulnerabilities`,
    ).toBe(true);
  });
});

// --- Theme assertion: data-theme reflects emulated prefers-color-scheme (UX-07-05) ---
test.describe('Theme bootstrap — data-theme reflects emulated color-scheme', () => {
  test('data-theme is "dark" when colorScheme is emulated dark', async ({ page }) => {
    // Emulate dark BEFORE navigation so the bootstrap script reads it on page load
    await page.emulateMedia({ colorScheme: 'dark' });
    // Clear localStorage so there is no stored preference overriding the OS signal
    await page.goto('/login');
    await page.evaluate(() => localStorage.removeItem('getvul_theme'));
    // Navigate again to trigger the bootstrap script with the cleared state
    await page.goto('/login');
    await page.locator('h2').first().waitFor({ state: 'visible', timeout: 10_000 });

    const theme = await page.locator('html').getAttribute('data-theme');
    expect(theme, 'html[data-theme] should be "dark" under dark color-scheme emulation').toBe('dark');
  });

  test('data-theme is "light" when colorScheme is emulated light', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/login');
    await page.evaluate(() => localStorage.removeItem('getvul_theme'));
    await page.goto('/login');
    await page.locator('h2').first().waitFor({ state: 'visible', timeout: 10_000 });

    const theme = await page.locator('html').getAttribute('data-theme');
    expect(theme, 'html[data-theme] should be "light" under light color-scheme emulation').toBe('light');
  });
});
