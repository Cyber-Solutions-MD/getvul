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
import { STATIC_ROUTES, waitForNav, discoverDetailRoute } from './routes';

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
      // Step 1: collect routes — static + 2 discovered detail pages
      const routes: string[] = [...STATIC_ROUTES];

      // Discover /dashboard/assets/<id>
      const assetHref = await discoverDetailRoute(
        page,
        '/dashboard/assets',
        'a[href*="/dashboard/assets/"]',
      );
      if (assetHref) {
        routes.push(assetHref);
      } else {
        console.warn('[viewport-scroll] assets list is empty — skipping assets detail');
      }

      // Discover /dashboard/tickets/<id>
      const ticketHref = await discoverDetailRoute(
        page,
        '/dashboard/tickets',
        'a[href*="/dashboard/tickets/"]',
      );
      if (ticketHref) {
        routes.push(ticketHref);
      } else {
        console.warn('[viewport-scroll] tickets list is empty — skipping tickets detail');
      }

      // Step 2: navigate to each route and assert no horizontal scroll
      for (const route of routes) {
        await page.goto(route);
        await waitForNav(page, viewport.width);

        // Pitfall 2: max across both document root and body to catch WebKit differences
        const hasHorizontalScroll = await page.evaluate(() => {
          const docWidth = Math.max(
            document.documentElement.scrollWidth,
            document.body.scrollWidth,
          );
          const clientWidth = document.documentElement.clientWidth;
          return docWidth > clientWidth;
        });

        expect(hasHorizontalScroll, `Horizontal scroll on ${route} at ${viewport.width}px`).toBe(false);
      }
    });
  });
}
