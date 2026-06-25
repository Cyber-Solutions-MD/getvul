// axe WCAG fixture factories for Phase 15 quality gate.
//
// D-03 (CONTEXT.md): axe blocking bar = WCAG 2.1 AA.
//   Blocking tags: wcag2a, wcag2aa, wcag21aa — zero critical/serious violations.
//   Report-only: wcag22aa — target-size (SC 2.5.8, 24×24 min) is report-only only.
//
// Usage in a spec:
//   import { test, expect } from './fixtures/axe';
//   test('no a11y violations', async ({ page, makeAxeBuilder }) => {
//     await page.goto('/dashboard');
//     await page.waitForLoadState('networkidle');
//     const results = await makeAxeBuilder().analyze();
//     const blocking = results.violations.filter(
//       v => v.impact === 'critical' || v.impact === 'serious',
//     );
//     expect(blocking).toHaveLength(0);
//   });

import { test as base } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

export const test = base.extend<{
  makeAxeBuilder: () => AxeBuilder;
  makeAxeBuilderReportOnly: () => AxeBuilder;
}>({
  // BLOCKING: WCAG 2.0 A/AA + WCAG 2.1 AA — assert zero critical/serious violations
  makeAxeBuilder: async ({ page }, use) => {
    const factory = () =>
      new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']);
    await use(factory);
  },

  // REPORT-ONLY: WCAG 2.2 AA — target-size (SC 2.5.8) rule only in axe-core 4.12
  // Per D-03: wcag22aa MUST NOT be in the blocking assertion.
  // Log violations as warnings; do not fail the test.
  makeAxeBuilderReportOnly: async ({ page }, use) => {
    const factory = () =>
      new AxeBuilder({ page }).withTags(['wcag22aa']);
    await use(factory);
  },
});

export { expect } from '@playwright/test';
