// UX-D-02-06 — Add-connector wizard axe sweep (OPEN dialog) + vaul mobile render check.
//
// e2e/a11y-routes.spec.ts only sweeps /dashboard/connectors in its CLOSED (category-grid)
// state — 19-RESEARCH.md flagged this as a pre-existing coverage gap. This spec closes it
// by OPENING the wizard dialog and running the axe WCAG 2.1 AA sweep in both themes, plus
// asserting the wizard renders correctly inside the vaul mobile bottom sheet without
// regressing the fixed bottom-nav (UI-SPEC "Responsive (mobile vaul) Contract").
//
// Provider selection: rely on the first `[data-add-connector]` element rather than a
// hardcoded provider type — a fresh test tenant may have any subset of connector types
// already configured (rendering "+ {name}" cards, connectors/page.tsx ~L343) vs. entirely
// unconfigured (rendering the empty-state CTA, ~L308). Both markup paths carry the same
// `data-add-connector` attribute.
//
// Import: { test, expect } from './fixtures/axe' — provides makeAxeBuilder (blocking,
// WCAG 2.1 AA: wcag2a + wcag2aa + wcag21aa, zero critical/serious violations).

import type { Locator, Page } from '@playwright/test';
import { test, expect } from './fixtures/axe';
import { waitForNav, MOBILE_NAV } from './routes';

// --- Dark theme (default shipping theme) — open-wizard axe sweep (blocking) ---
test.describe('Add-connector wizard — axe sweep (open dialog), dark theme (blocking)', () => {
  test('open wizard reports zero critical/serious axe violations (dark)', async ({
    page,
    makeAxeBuilder,
  }) => {
    await page.goto('/dashboard/connectors');
    await waitForNav(page, 1280);

    await page.locator('[data-add-connector]').first().click();
    await page.getByRole('dialog').waitFor();
    await expect(page.getByRole('heading', { name: /Add connector · /i })).toBeVisible();

    const results = await makeAxeBuilder().analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );

    if (blocking.length > 0) {
      console.error(
        '[connector-wizard-a11y] BLOCKING violations (dark, open wizard):\n' +
          blocking
            .map(
              (v) =>
                `  [${v.impact}] ${v.id}: ${v.description} — ${v.nodes.length} node(s)`,
            )
            .join('\n'),
      );
    }

    expect(blocking, 'zero critical/serious axe on open wizard (dark)').toHaveLength(0);
  });
});

// --- Light theme — open-wizard axe sweep (blocking) ---
// Mirrors a11y-routes.spec.ts's light-theme forcing pattern: pre-seed localStorage via
// addInitScript (read by the FOUC bootstrap in layout.tsx before paint), then defensively
// re-assert/force data-theme="light" after goto (Pitfall 2 — bootstrap doesn't always take).
test.describe('Add-connector wizard — axe sweep (open dialog), light theme (blocking)', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.setItem('getvul_theme', 'light');
      } catch {
        /* storage unavailable — force-set after goto below */
      }
    });
  });

  test('open wizard reports zero critical/serious axe violations (light)', async ({
    page,
    makeAxeBuilder,
  }) => {
    await page.goto('/dashboard/connectors');
    await waitForNav(page, 1280);

    // Defensive: confirm the bootstrap actually applied light; force if not.
    const actualTheme = await page.locator('html').getAttribute('data-theme');
    if (actualTheme !== 'light') {
      await page.evaluate(() => {
        document.documentElement.setAttribute('data-theme', 'light');
      });
      await page.waitForTimeout(50); // allow the CSS cascade to repaint
    }

    await page.locator('[data-add-connector]').first().click();
    await page.getByRole('dialog').waitFor();
    await expect(page.getByRole('heading', { name: /Add connector · /i })).toBeVisible();

    const results = await makeAxeBuilder().analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );

    if (blocking.length > 0) {
      console.error(
        '[connector-wizard-a11y] BLOCKING violations (light, open wizard):\n' +
          blocking
            .map(
              (v) =>
                `  [${v.impact}] ${v.id}: ${v.description} — ${v.nodes.length} node(s)`,
            )
            .join('\n'),
      );
    }

    expect(blocking, 'zero critical/serious axe on open wizard (light)').toHaveLength(0);
  });
});

// --- Mobile vaul render (390×844, iPhone 14 Pro) — wizard inside the bottom sheet ---
// The wizard must render inside vaul's Drawer.Content (ResponsiveDialog mobile branch,
// <768px) without regressing the persistent fixed bottom-nav (Phase 15 contract). Axe is
// also run once here (blocking) since this is a genuinely distinct DOM/viewport combination
// (sticky footer, compact stepper) from the two desktop-viewport sweeps above.
test.describe('Add-connector wizard — mobile vaul sheet render (blocking)', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('wizard renders in the vaul sheet; bottom-nav stays visible; zero critical/serious axe', async ({
    page,
    makeAxeBuilder,
  }) => {
    await page.goto('/dashboard/connectors');
    await waitForNav(page, 390);

    await page.locator('[data-add-connector]').first().click();
    await page.getByRole('dialog').waitFor();

    // The wizard's stepper (net-new UI, UI-SPEC "Stepper Visual Spec") renders inside the
    // vaul sheet — proves the wizard content itself mounted, not just an empty drawer shell.
    await expect(page.locator('nav[aria-label="Wizard progress"]')).toBeVisible();

    // No regression to the fixed bottom-nav focus behavior (Phase 15 contract) — the
    // vaul overlay must not hide/remove the persistent mobile nav landmark underneath it.
    await expect(page.locator(MOBILE_NAV)).toBeVisible();

    const results = await makeAxeBuilder().analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );

    if (blocking.length > 0) {
      console.error(
        '[connector-wizard-a11y] BLOCKING violations (mobile vaul sheet):\n' +
          blocking
            .map(
              (v) =>
                `  [${v.impact}] ${v.id}: ${v.description} — ${v.nodes.length} node(s)`,
            )
            .join('\n'),
      );
    }

    expect(blocking, 'zero critical/serious axe on open wizard (mobile vaul sheet)').toHaveLength(
      0,
    );
  });
});

// ---------------------------------------------------------------------------
// Test step + Confirm step axe sweeps (Plan 22-02) — extends the OPEN-dialog
// coverage above from the Credentials step (step 2 only) to the two later
// in-dialog steps: Test (step 3) and Confirm (step 4), in both themes.
//
// POST /api/v1/connectors/test makes a real outbound call to the provider API
// (CrowdStrike/Nessus/Defender) with no sandbox mode, and POST /api/v1/connectors
// stores whatever it's given with no server-side re-validation (22-RESEARCH) —
// so both are driven deterministically via page.route(), mirroring the
// tickets-kanban.spec.ts:117 precedent. GET /connectors/types is hit for real
// (static metadata, no side effects) so the Confirm permission list sweeps
// true data, never mocked.
// ---------------------------------------------------------------------------

type Theme = 'dark' | 'light';

type AxeAnalyzeResult = {
  violations: Array<{
    impact?: string | null;
    id: string;
    description: string;
    nodes: unknown[];
  }>;
};
type MakeAxeBuilder = () => { analyze: () => Promise<AxeAnalyzeResult> };

/** Shared blocking-violation filter + diagnostic log + labeled assertion (mirrors lines 34-52 above). */
async function sweepBlocking(makeAxeBuilder: MakeAxeBuilder, label: string) {
  const results = await makeAxeBuilder().analyze();
  const blocking = results.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious',
  );

  if (blocking.length > 0) {
    console.error(
      `[connector-wizard-a11y] BLOCKING violations (${label}):\n` +
        blocking
          .map((v) => `  [${v.impact}] ${v.id}: ${v.description} — ${v.nodes.length} node(s)`)
          .join('\n'),
    );
  }

  expect(blocking, `zero critical/serious axe on ${label}`).toHaveLength(0);
}

/** Defensive light-theme re-assert (mirrors lines 77-84 above) — call AFTER goto. */
async function assertLightTheme(page: Page) {
  const actualTheme = await page.locator('html').getAttribute('data-theme');
  if (actualTheme !== 'light') {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'light');
    });
    await page.waitForTimeout(50); // allow the CSS cascade to repaint
  }
}

/**
 * Opens the wizard, fills every rendered credential input (provider-agnostic —
 * never hardcodes a connector type's field names, since a fresh tenant may
 * have any subset of fields configured), and clicks Next to reach the Test
 * step. Callers that need a specific `connectors/test` result must register
 * their `page.route()` mock BEFORE calling this helper.
 */
async function driveToTestStep(page: Page, theme: Theme) {
  await page.goto('/dashboard/connectors');
  await waitForNav(page, 1280);
  if (theme === 'light') await assertLightTheme(page);

  await page.locator('[data-add-connector]').first().click();
  await page.getByRole('dialog').waitFor();
  await expect(page.getByRole('heading', { name: /Add connector · /i })).toBeVisible();

  const dialog = page.getByRole('dialog');
  const inputs = dialog.locator('input');
  const count = await inputs.count();
  for (let i = 0; i < count; i++) {
    await inputs.nth(i).fill('test-value');
  }

  await dialog.getByRole('button', { name: 'Next', exact: true }).click();
}

/**
 * Extends `driveToTestStep` all the way to the Confirm step: mocks a passing
 * `POST /api/v1/connectors/test` result, clicks "Test connection", waits for
 * the success status block, then advances Next. Does NOT mock
 * `GET /connectors/types` — the Confirm permission list must render real
 * metadata.
 */
async function driveToConfirmStep(page: Page, theme: Theme) {
  await page.route('**/api/v1/connectors/test', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, message: 'Successfully authenticated' }),
    }),
  );

  await driveToTestStep(page, theme);

  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: /test connection/i }).click();
  await expect(dialog.getByRole('status')).toBeVisible();

  await dialog.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(dialog.getByRole('heading', { name: 'Confirm', exact: true })).toBeVisible();
}

/**
 * Polls the `disabled` DOM property directly on a captured element handle
 * rather than re-resolving `locator` (a `getByRole()` match) on every retry.
 * `getByRole` recomputes the page's accessibility tree per query, which can
 * take several hundred ms — slower than the mocked mutation's brief pending
 * window — so role-based polling can miss the transient disabled state
 * entirely. Reading the DOM property off a handle has no such overhead.
 */
async function waitForDisabled(locator: Locator, expected: boolean, timeout = 2000) {
  const handle = await locator.elementHandle();
  if (!handle) throw new Error('waitForDisabled: element not found');
  await expect
    .poll(() => handle.evaluate((el) => (el as HTMLButtonElement).disabled), { timeout })
    .toBe(expected);
}

/** Registers the addInitScript light-theme seed used by every light-theme test below. */
function useLightThemeInit() {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.setItem('getvul_theme', 'light');
      } catch {
        /* storage unavailable — assertLightTheme() force-sets after goto */
      }
    });
  });
}

// --- Test step (loader / success / error), both themes (blocking) ---
test.describe('Add-connector wizard — Test step axe sweep (both themes, blocking)', () => {
  test.describe('dark theme', () => {
    test('test-connection loader reports zero critical/serious axe violations (dark)', async ({
      page,
      makeAxeBuilder,
    }) => {
      // Delay the fulfill so the pending/disabled UI is present long enough to sweep.
      await page.route('**/api/v1/connectors/test', async (route) => {
        await new Promise((r) => setTimeout(r, 400));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, message: 'Successfully authenticated' }),
        });
      });

      await driveToTestStep(page, 'dark');

      const dialog = page.getByRole('dialog');
      const testButton = dialog.getByRole('button', { name: /test connection/i });
      await testButton.click();
      await waitForDisabled(testButton, true);

      await sweepBlocking(makeAxeBuilder, 'test step loader (dark)');

      // Let the mocked mutation settle before the test ends.
      await expect(dialog.getByRole('status')).toBeVisible();
    });

    test('test-connection success reports zero critical/serious axe violations (dark)', async ({
      page,
      makeAxeBuilder,
    }) => {
      await page.route('**/api/v1/connectors/test', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, message: 'Successfully authenticated' }),
        }),
      );

      await driveToTestStep(page, 'dark');

      const dialog = page.getByRole('dialog');
      await dialog.getByRole('button', { name: /test connection/i }).click();
      await expect(dialog.getByRole('status')).toBeVisible();

      await sweepBlocking(makeAxeBuilder, 'test step success (dark)');
    });

    test('test-connection error reports zero critical/serious axe violations (dark)', async ({
      page,
      makeAxeBuilder,
    }) => {
      await page.route('**/api/v1/connectors/test', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: false, message: 'Authentication failed: HTTP 401' }),
        }),
      );

      await driveToTestStep(page, 'dark');

      const dialog = page.getByRole('dialog');
      await dialog.getByRole('button', { name: /test connection/i }).click();
      await expect(dialog.getByRole('alert')).toBeVisible();

      await sweepBlocking(makeAxeBuilder, 'test step error (dark)');
    });
  });

  test.describe('light theme', () => {
    useLightThemeInit();

    test('test-connection loader reports zero critical/serious axe violations (light)', async ({
      page,
      makeAxeBuilder,
    }) => {
      await page.route('**/api/v1/connectors/test', async (route) => {
        await new Promise((r) => setTimeout(r, 400));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, message: 'Successfully authenticated' }),
        });
      });

      await driveToTestStep(page, 'light');

      const dialog = page.getByRole('dialog');
      const testButton = dialog.getByRole('button', { name: /test connection/i });
      await testButton.click();
      await waitForDisabled(testButton, true);

      await sweepBlocking(makeAxeBuilder, 'test step loader (light)');

      await expect(dialog.getByRole('status')).toBeVisible();
    });

    test('test-connection success reports zero critical/serious axe violations (light)', async ({
      page,
      makeAxeBuilder,
    }) => {
      await page.route('**/api/v1/connectors/test', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, message: 'Successfully authenticated' }),
        }),
      );

      await driveToTestStep(page, 'light');

      const dialog = page.getByRole('dialog');
      await dialog.getByRole('button', { name: /test connection/i }).click();
      await expect(dialog.getByRole('status')).toBeVisible();

      await sweepBlocking(makeAxeBuilder, 'test step success (light)');
    });

    test('test-connection error reports zero critical/serious axe violations (light)', async ({
      page,
      makeAxeBuilder,
    }) => {
      await page.route('**/api/v1/connectors/test', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: false, message: 'Authentication failed: HTTP 401' }),
        }),
      );

      await driveToTestStep(page, 'light');

      const dialog = page.getByRole('dialog');
      await dialog.getByRole('button', { name: /test connection/i }).click();
      await expect(dialog.getByRole('alert')).toBeVisible();

      await sweepBlocking(makeAxeBuilder, 'test step error (light)');
    });
  });
});

// --- Confirm step (permissions/sync review + submit-error), both themes (blocking) ---
test.describe('Add-connector wizard — Confirm step axe sweep (both themes, blocking)', () => {
  test.describe('dark theme', () => {
    test('confirm step permission/sync review reports zero critical/serious axe violations (dark)', async ({
      page,
      makeAxeBuilder,
    }) => {
      await driveToConfirmStep(page, 'dark');
      await sweepBlocking(makeAxeBuilder, 'confirm step permission/sync review (dark)');
    });

    test('confirm step submit-error reports zero critical/serious axe violations (dark)', async ({
      page,
      makeAxeBuilder,
    }) => {
      await driveToConfirmStep(page, 'dark');

      // 500 mock ensures create_connector is never reached — no unvalidated
      // credential row is persisted (22-RESEARCH; T-22-02-03 mitigation).
      await page.route('**/api/v1/connectors', (route) =>
        route.fulfill({ status: 500, contentType: 'application/json', body: '{}' }),
      );

      const dialog = page.getByRole('dialog');
      await dialog.getByRole('button', { name: /add connector/i }).click();
      await expect(dialog.getByRole('alert')).toBeVisible();

      await sweepBlocking(makeAxeBuilder, 'confirm step submit-error (dark)');
    });
  });

  test.describe('light theme', () => {
    useLightThemeInit();

    test('confirm step permission/sync review reports zero critical/serious axe violations (light)', async ({
      page,
      makeAxeBuilder,
    }) => {
      await driveToConfirmStep(page, 'light');
      await sweepBlocking(makeAxeBuilder, 'confirm step permission/sync review (light)');
    });

    test('confirm step submit-error reports zero critical/serious axe violations (light)', async ({
      page,
      makeAxeBuilder,
    }) => {
      await driveToConfirmStep(page, 'light');

      await page.route('**/api/v1/connectors', (route) =>
        route.fulfill({ status: 500, contentType: 'application/json', body: '{}' }),
      );

      const dialog = page.getByRole('dialog');
      await dialog.getByRole('button', { name: /add connector/i }).click();
      await expect(dialog.getByRole('alert')).toBeVisible();

      await sweepBlocking(makeAxeBuilder, 'confirm step submit-error (light)');
    });
  });
});
