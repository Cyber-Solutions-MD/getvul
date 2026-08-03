// Phase 28 UAT Test 1 — live axe + structural sweep of the admin AI usage &
// settings pane (AIE-04) at /dashboard/settings?category=ai.
//
// The general a11y-routes sweep only visits /dashboard/settings (default
// category) and never renders the AI pane. This spec drives the AI category
// explicitly, proves the configured 4-card layout renders (Status / Budget /
// Usage by capability / Key & model), and runs the blocking WCAG 2.1 AA axe
// sweep in both the shipping dark theme and the light theme.
//
// Prereq: a tenant with a configured ANTHROPIC connector so the pane renders
// the 4 cards (not the "AI isn't set up yet" empty state).

import { test, expect } from './fixtures/axe';
import { waitForNav } from './routes';

const AI_ROUTE = '/dashboard/settings?category=ai';
const CARD_HEADINGS = ['Status', 'Budget', 'Usage by capability', 'Key & model'];

async function assertFourCardLayout(page: import('@playwright/test').Page) {
  for (const heading of CARD_HEADINGS) {
    await expect(
      page.getByRole('heading', { name: heading, exact: true }),
      `card heading "${heading}" is present`,
    ).toBeVisible({ timeout: 15_000 });
  }
}

function blocking(results: { violations: Array<{ impact?: string | null }> }) {
  return results.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious',
  );
}

test.describe('AI usage pane — dark theme (blocking)', () => {
  test('4-card layout renders and axe WCAG 2.1 AA passes (dark)', async ({
    page,
    makeAxeBuilder,
    makeAxeBuilderReportOnly,
  }) => {
    await page.goto(AI_ROUTE);
    await waitForNav(page, 1280);
    await page.waitForLoadState('networkidle');

    await assertFourCardLayout(page);

    const results = await makeAxeBuilder().analyze();
    const crit = blocking(results);
    if (crit.length > 0) {
      console.error(
        `[ai-usage-pane] BLOCKING violations (dark):\n` +
          crit
            .map((v: any) => `  [${v.impact}] ${v.id}: ${v.description} — ${v.nodes.length} node(s)`)
            .join('\n'),
      );
    }
    expect(crit, 'Zero critical/serious axe violations on the AI pane (dark)').toHaveLength(0);

    const reportResults = await makeAxeBuilderReportOnly().analyze();
    if (reportResults.violations.length > 0) {
      console.warn(
        `[ai-usage-pane] WCAG 2.2 AA report-only (dark):\n` +
          reportResults.violations
            .map((v: any) => `  [${v.impact ?? 'unknown'}] ${v.id}: ${v.description}`)
            .join('\n'),
      );
    }
  });
});

test.describe('AI usage pane — light theme (blocking)', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.setItem('getvul_theme', 'light');
      } catch {
        /* storage unavailable — force-set after goto below */
      }
    });
  });

  test('4-card layout renders and axe WCAG 2.1 AA passes (light)', async ({
    page,
    makeAxeBuilder,
  }) => {
    await page.goto(AI_ROUTE);
    await waitForNav(page, 1280);
    await page.waitForLoadState('networkidle');

    const actualTheme = await page.locator('html').getAttribute('data-theme');
    if (actualTheme !== 'light') {
      await page.evaluate(() => {
        document.documentElement.setAttribute('data-theme', 'light');
      });
      await page.waitForTimeout(50);
    }

    await assertFourCardLayout(page);

    const results = await makeAxeBuilder().analyze();
    const crit = blocking(results);
    if (crit.length > 0) {
      console.error(
        `[ai-usage-pane] BLOCKING violations (light):\n` +
          crit
            .map((v: any) => `  [${v.impact}] ${v.id}: ${v.description} — ${v.nodes.length} node(s)`)
            .join('\n'),
      );
    }
    expect(crit, 'Zero critical/serious axe violations on the AI pane (light)').toHaveLength(0);
  });
});
