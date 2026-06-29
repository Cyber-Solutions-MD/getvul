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
import { discoverDetailRoutes, waitForNav, gotoStable } from './routes';

// Smoke route set: login, dashboard, vulnerabilities, and one discovered detail page.
// Defined as a function so the detail-page discovery runs inside each test.

const SMOKE_AUTHED = ['/dashboard', '/dashboard/vulnerabilities'] as const;

/** Assert a route renders and has zero critical/serious axe violations. */
async function expectNoBlockingAxe(
  route: string,
  makeAxeBuilder: () => { analyze: () => Promise<{ violations: { impact?: string | null; id: string; description: string }[] }> },
) {
  const results = await makeAxeBuilder().analyze();
  const blocking = results.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious',
  );
  if (blocking.length > 0) {
    console.error(
      `[smoke] BLOCKING axe violations on ${route}:\n` +
        blocking.map((v) => `  [${v.impact}] ${v.id}: ${v.description}`).join('\n'),
    );
  }
  expect(blocking, `Zero critical/serious axe violations on ${route} (smoke)`).toHaveLength(0);
}

// --- /login smoke (UX-07-07) — runs UNAUTHENTICATED ---
// The login page bounces already-authed users (D-50), so the smoke projects'
// storageState would redirect us away. Override to an empty session for /login.
test.describe('Cross-browser smoke — /login (unauthenticated)', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('login page renders and passes axe in all engines', async ({ page, makeAxeBuilder }) => {
    await page.goto('/login');
    await page.locator('h2').first().waitFor({ state: 'visible', timeout: 10_000 });
    await expect(page.locator('h2').first()).toBeVisible();
    await expectNoBlockingAxe('/login', makeAxeBuilder);
  });
});

// --- Authed smoke sweep (UX-07-07) ---
test.describe('Cross-browser smoke sweep', () => {
  test('smoke routes render and pass axe in all engines', async ({ page, makeAxeBuilder }) => {
    // Discover one detail page for the smoke run (via API — see routes.ts)
    const detailRoutes = await discoverDetailRoutes(page);
    const routes: string[] = [...SMOKE_AUTHED, ...detailRoutes.slice(0, 1)];

    for (const route of routes) {
      await gotoStable(page, route);
      await waitForNav(page, 1280);
      await expect(page.locator('nav[aria-label="Primary navigation"]')).toBeVisible();
      await expectNoBlockingAxe(route, makeAxeBuilder);
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
  // The bootstrap logic (read prefers-color-scheme → data-theme) is browser-agnostic
  // app behavior; Chromium + WebKit cover it. Firefox's prefers-color-scheme
  // emulation is unreliable under Playwright (needs ui.systemUsesDarkTheme, which then
  // prevents per-test light override), so skip it there.
  test.skip(({ browserName }) => browserName === 'firefox', 'Firefox colorScheme emulation unreliable in Playwright');

  // Remove any stored preference BEFORE the bootstrap script runs on every
  // navigation, so the head bootstrap resolves purely from the emulated
  // prefers-color-scheme. addInitScript runs pre-paint on each goto, which is
  // more reliable than goto→removeItem→goto (Firefox restores storageState
  // localStorage on each navigation).
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.removeItem('getvul_theme');
      } catch {
        /* localStorage may be unavailable — bootstrap defaults apply */
      }
    });
  });

  test('data-theme is "dark" when colorScheme is emulated dark', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto('/login');
    await page.locator('h2').first().waitFor({ state: 'visible', timeout: 10_000 });

    const theme = await page.locator('html').getAttribute('data-theme');
    expect(theme, 'html[data-theme] should be "dark" under dark color-scheme emulation').toBe('dark');
  });

  test('data-theme is "light" when colorScheme is emulated light', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/login');
    await page.locator('h2').first().waitFor({ state: 'visible', timeout: 10_000 });

    const theme = await page.locator('html').getAttribute('data-theme');
    expect(theme, 'html[data-theme] should be "light" under light color-scheme emulation').toBe('light');
  });
});
