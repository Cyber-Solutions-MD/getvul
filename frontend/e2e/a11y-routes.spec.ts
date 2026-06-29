// UX-07-03 — Axe-core accessibility quality gate.
//
// For every authenticated route:
//   - BLOCKING: axe WCAG 2.1 AA sweep (wcag2a + wcag2aa + wcag21aa tags).
//     Zero critical/serious violations required to pass.
//   - REPORT-ONLY: axe WCAG 2.2 AA sweep (wcag22aa tag — target-size SC 2.5.8).
//     Violations are logged as console.warn, never fail the test (D-03).
//
// UX-07-02 — Bottom-nav presence + More-sheet opens at 360px:
//   - At viewport 360×812, asserts nav[aria-label="Mobile navigation"] is visible.
//   - Clicking the "More" button opens the vaul drawer (Drawer.Content with
//     aria-label "More navigation").
//
// Import: { test, expect } from './fixtures/axe' — provides makeAxeBuilder and
// makeAxeBuilderReportOnly fixtures (Plan 01, 15-01-SUMMARY.md).

import { test, expect } from './fixtures/axe';
import { STATIC_ROUTES, waitForNav, discoverDetailRoutes } from './routes';

// --- Blocking WCAG 2.1 AA sweep across ALL authenticated routes ---
test.describe('WCAG 2.1 AA axe sweep — all routes (blocking)', () => {
  test('sweeps all routes for critical/serious violations', async ({ page, makeAxeBuilder, makeAxeBuilderReportOnly }) => {
    // Build the full route list: static + discovered [id] detail pages (via API)
    const detailRoutes = await discoverDetailRoutes(page);
    if (detailRoutes.length === 0) {
      console.warn('[a11y-routes] no detail routes discovered — sweeping static routes only');
    }
    const routes: string[] = [...STATIC_ROUTES, ...detailRoutes];

    // Default viewport for this describe is the project default (Desktop Chrome at 1280px)
    for (const route of routes) {
      await page.goto(route);
      await waitForNav(page, 1280);

      // BLOCKING: WCAG 2.0 A/AA + WCAG 2.1 AA
      const results = await makeAxeBuilder().analyze();
      const blocking = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious',
      );

      if (blocking.length > 0) {
        // Log details for debuggability — rule id, impact, affected nodes
        console.error(
          `[a11y-routes] BLOCKING violations on ${route}:\n` +
            blocking
              .map(
                (v) =>
                  `  [${v.impact}] ${v.id}: ${v.description} — ${v.nodes.length} node(s)`,
              )
              .join('\n'),
        );
      }

      expect(blocking, `Zero critical/serious axe violations on ${route}`).toHaveLength(0);

      // REPORT-ONLY: WCAG 2.2 AA (target-size — SC 2.5.8)
      const reportResults = await makeAxeBuilderReportOnly().analyze();
      if (reportResults.violations.length > 0) {
        console.warn(
          `[a11y-routes] WCAG 2.2 AA report-only on ${route}:\n` +
            reportResults.violations
              .map(
                (v) =>
                  `  [${v.impact ?? 'unknown'}] ${v.id}: ${v.description}`,
              )
              .join('\n'),
        );
      }
      // Do NOT assert on reportResults — this is intentionally report-only (D-03)
    }
  });
});

// --- UX-07-02 — Mobile bottom-nav presence + More-sheet opens at 360px ---
test.describe('Bottom-nav visibility + More-sheet at 360px', () => {
  test.use({ viewport: { width: 360, height: 812 } });

  test('nav[aria-label="Mobile navigation"] is visible on /dashboard at 360px', async ({ page }) => {
    await page.goto('/dashboard');
    // At 360px the three-tier nav renders the bottom-nav (min-[768px]:hidden hides it at >=768px)
    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(mobileNav).toBeVisible();
  });

  test('clicking "More" button opens the "More navigation" sheet', async ({ page }) => {
    await page.goto('/dashboard');

    // Confirm bottom-nav is visible first
    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(mobileNav).toBeVisible();

    // Click the More button (aria-label="More navigation" on the <button>)
    const moreButton = page.getByRole('button', { name: /more/i });
    await moreButton.click();

    // The vaul NavMoreSheet renders Drawer.Content with aria-label="More navigation"
    // vaul wraps Drawer.Content in role=dialog implicitly (tested via the aria-label attribute)
    const moreSheet = page.locator('[aria-label="More navigation"]').last();
    await expect(moreSheet).toBeVisible({ timeout: 5_000 });
  });
});
