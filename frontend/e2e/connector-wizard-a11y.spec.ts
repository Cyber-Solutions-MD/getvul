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
