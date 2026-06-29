// UX-07-01 — Horizontal-scroll quality gate.
//
// Sweeps every authenticated route across 4 viewport widths and asserts no
// horizontal overflow. Uses the auth storageState wired in playwright.config.ts
// (chromium-a11y project, which depends on the `setup` auth project).
//
// Pitfall 1 (RESEARCH.md): After page.goto, wait for the nav landmark to be
// visible before evaluating layout — auth redirects and client-side hydration
// mean DOMContentLoaded is not a reliable readiness signal.
//
// Pitfall 2 (RESEARCH.md): Use Math.max(documentElement.scrollWidth,
// body.scrollWidth) vs documentElement.clientWidth — WebKit measures scrollWidth
// at the body level while Chromium/Firefox report it on documentElement.

import { test, expect } from '@playwright/test';
import { STATIC_ROUTES, waitForNav, discoverDetailRoutes } from './routes';

// The 4 audited viewport widths × heights (Phase 15 quality gate spec).
const VIEWPORTS = [
  { width: 360, height: 812 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1280, height: 900 },
] as const;

for (const viewport of VIEWPORTS) {
  test.describe(`No horizontal scroll at ${viewport.width}×${viewport.height}`, () => {
    test.use({ viewport });

    test(`sweeps all routes at ${viewport.width}px`, async ({ page }) => {
      // Step 1: collect routes — static + discovered [id] detail pages (via API)
      const detailRoutes = await discoverDetailRoutes(page);
      if (detailRoutes.length === 0) {
        console.warn('[viewport-scroll] no detail routes discovered — sweeping static routes only');
      }
      const routes: string[] = [...STATIC_ROUTES, ...detailRoutes];

      // Step 2: navigate to each route and assert no horizontal scroll.
      // Poll until the layout settles: tables/grids can render one frame wider
      // than the viewport during hydration before responsive CSS applies (a
      // sub-100ms reflow, not a user-visible scrollbar). expect.poll passes as
      // soon as the SETTLED layout fits, and still fails if overflow persists.
      for (const route of routes) {
        await page.goto(route);
        await waitForNav(page, viewport.width);

        await expect
          .poll(
            // Pitfall 2: max across document root and body (WebKit differs)
            async () =>
              page.evaluate(() => {
                const docWidth = Math.max(
                  document.documentElement.scrollWidth,
                  document.body.scrollWidth,
                );
                return docWidth > document.documentElement.clientWidth;
              }),
            {
              message: `Horizontal scroll on ${route} at ${viewport.width}px`,
              timeout: 5_000,
            },
          )
          .toBe(false);
      }
    });
  });
}
