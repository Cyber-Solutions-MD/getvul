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
  // Phase 41 (41-01, COV-01) — new /dashboard/coverage blind-spot list.
  '/dashboard/coverage',
] as const;

// Three-tier responsive nav (D-05):
//   <768px        → bottom-nav  (aria-label="Mobile navigation")
//   768–999px     → topbar hamburger opens a drawer (no always-visible nav landmark;
//                   the hamburger button is the persistent shell signal)
//   >=1000px      → sidebar     (aria-label="Primary navigation")
export const MOBILE_NAV = 'nav[aria-label="Mobile navigation"]';
export const DESKTOP_NAV = 'nav[aria-label="Primary navigation"]';
export const TABLET_HAMBURGER = 'button[aria-label="Open navigation menu"]';

/**
 * Navigate resiliently. Some pages (e.g. /dashboard/vulnerabilities) issue a
 * client-side router.replace to canonicalize filter state into the URL; on
 * WebKit this can fire during the *next* navigation and abort it with
 * "interrupted by another navigation". Retry once after a short settle.
 */
export async function gotoStable(page: Page, url: string) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      await page.goto(url);
      return;
    } catch (e) {
      if (attempt === 0 && /interrupted by another navigation/.test(String(e))) {
        await page.waitForTimeout(300);
        continue;
      }
      throw e;
    }
  }
}

/** Wait for the persistent shell signal for the current viewport tier. */
export async function waitForNav(page: Page, viewportWidth: number) {
  const selector =
    viewportWidth < 768
      ? MOBILE_NAV
      : viewportWidth < 1000
        ? TABLET_HAMBURGER
        : DESKTOP_NAV;
  await page.locator(selector).first().waitFor({ state: 'visible', timeout: 10_000 });
}

// Backend API base for detail-id discovery (the browser uses NEXT_PUBLIC_API_URL).
const API_BASE = process.env.E2E_API_URL || 'http://localhost:8000';

/**
 * Discover real [id] detail routes (/dashboard/assets/<id>, /dashboard/tickets/<id>)
 * via the backend list APIs rather than the UI. The UI does NOT navigate to these
 * routes from a simple row click — the tickets list opens an in-page drill panel
 * (?ticket=&open=drill) and the assets list pushes /assets/<id> (a 308 redirect) —
 * so clicking rows can't reliably reach the detail routes across viewports.
 *
 * Reads the JWT from the context storageState (no navigation required) and queries
 * the list endpoints with page.request. Returns one detail URL per resource that
 * has at least one row; resources with empty lists are omitted (callers sweep
 * whatever is returned). Never hardcodes an id (Plan 05 acceptance criteria).
 */
export async function discoverDetailRoutes(page: Page): Promise<string[]> {
  const state = await page.context().storageState();
  const origin = state.origins.find((o) => o.origin.includes('localhost:3000'));
  const token = origin?.localStorage.find((i) => i.name === 'getvul_token')?.value;
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const targets: Array<{ api: string; base: string }> = [
    { api: '/api/v1/assets?page=1', base: '/dashboard/assets' },
    { api: '/api/v1/tickets?page=1', base: '/dashboard/tickets' },
  ];

  const routes: string[] = [];
  for (const { api, base } of targets) {
    try {
      const res = await page.request.get(`${API_BASE}${api}`, { headers });
      if (!res.ok()) continue;
      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.items ?? data.data ?? []);
      const id = items?.[0]?.id;
      if (id) routes.push(`${base}/${id}`);
    } catch {
      // API unreachable or shape mismatch — omit this detail route from the sweep.
    }
  }
  return routes;
}
