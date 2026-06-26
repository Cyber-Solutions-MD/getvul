// Shared route definitions for Phase 15 spec suite.
//
// ALL_ROUTES lists every authenticated route. 9 are static; 2 are dynamic
// ([id] segments for assets and tickets). Dynamic routes must be discovered
// at runtime by visiting the list page and clicking the first row — never
// hardcode an id (Plan 05 acceptance criteria).

import type { Page } from '@playwright/test';

// The 9 static authenticated routes swept by all specs.
export const STATIC_ROUTES = [
  '/dashboard',
  '/dashboard/vulnerabilities',
  '/dashboard/assets',
  '/dashboard/tickets',
  '/dashboard/tickets/rules',
  '/dashboard/cspm',
  '/dashboard/connectors',
  '/dashboard/users',
  '/dashboard/settings',
] as const;

// Nav-landmark selectors per viewport.
// At <768px the three-tier nav shows the mobile bottom-nav; at >=768px the sidebar/drawer.
export const MOBILE_NAV = 'nav[aria-label="Mobile navigation"]';
export const DESKTOP_NAV = 'nav[aria-label="Primary navigation"]';

/** Wait for the appropriate nav landmark based on the current viewport width. */
export async function waitForNav(page: Page, viewportWidth: number) {
  const selector = viewportWidth < 768 ? MOBILE_NAV : DESKTOP_NAV;
  await page.locator(selector).waitFor({ state: 'visible', timeout: 10_000 });
}

/**
 * Discover the URL of the first row in a list page by navigating to
 * `listRoute` and clicking the first row link. Returns null (and issues
 * test.skip) if the list is empty.
 *
 * Usage:
 *   const assetUrl = await discoverDetailRoute(page, '/dashboard/assets', 'a[href*="/dashboard/assets/"]');
 */
export async function discoverDetailRoute(
  page: Page,
  listRoute: string,
  rowSelector: string,
): Promise<string | null> {
  await page.goto(listRoute);
  // Wait for page to settle — at least the nav landmark visible at desktop
  await page.locator(DESKTOP_NAV).waitFor({ state: 'visible', timeout: 10_000 });

  const firstRow = page.locator(rowSelector).first();
  const count = await firstRow.count();
  if (count === 0) {
    // List is empty — caller should test.skip
    return null;
  }
  // Click the first row to navigate to the detail page
  await firstRow.click();
  await page.waitForURL('**/' + listRoute.split('/').pop() + '/**', { timeout: 10_000 });
  return page.url().replace(page.context().browser()?.contexts()[0].pages()[0]?.url() ?? '', '') || page.url();
}

/**
 * Resolve the full set of routes to sweep. Visits the assets and tickets list
 * pages to discover real [id] detail URLs. Falls back to static routes only if
 * the lists are empty, returning the discovered url or null for each.
 *
 * Returns an array of string URLs to visit.
 */
export async function resolveAllRoutes(
  page: Page,
  viewportWidth = 1280,
): Promise<string[]> {
  const routes: string[] = [...STATIC_ROUTES];

  // Discover /dashboard/assets/<id>
  const assetUrl = await discoverDetailRouteByClick(page, '/dashboard/assets', viewportWidth);
  if (assetUrl) routes.push(assetUrl);

  // Discover /dashboard/tickets/<id>
  const ticketUrl = await discoverDetailRouteByClick(page, '/dashboard/tickets', viewportWidth);
  if (ticketUrl) routes.push(ticketUrl);

  return routes;
}

/**
 * Internal helper: navigate to a list page and click the first clickable
 * table row or link to discover the detail URL. Returns null if list is empty.
 */
async function discoverDetailRouteByClick(
  page: Page,
  listRoute: string,
  viewportWidth: number,
): Promise<string | null> {
  await page.goto(listRoute);
  await waitForNav(page, viewportWidth);

  // Try common row-link selectors used in the GetVul table pattern:
  // vuln-table uses <tr> with an onClick; assets/tickets use anchor links in rows.
  const selectors = [
    'table tbody tr a[href]',
    'table tbody tr[data-href]',
    'tbody tr td a[href]',
  ];

  for (const sel of selectors) {
    const el = page.locator(sel).first();
    const found = await el.count();
    if (found > 0) {
      const href = await el.getAttribute('href');
      if (href && href.startsWith('/dashboard/')) {
        return href;
      }
      // Click to navigate if href not directly readable
      await el.click();
      const newUrl = page.url();
      const base = 'http://localhost:3000';
      const path = newUrl.startsWith(base) ? newUrl.slice(base.length) : newUrl;
      if (path !== listRoute) return path;
    }
  }

  // Fallback: look for any row click that changes URL beyond the list route
  const rowLink = page.locator(`a[href*="${listRoute}/"]`).first();
  const found = await rowLink.count();
  if (found > 0) {
    const href = await rowLink.getAttribute('href');
    return href;
  }

  return null;
}
