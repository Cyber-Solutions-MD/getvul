# Phase 15: Mobile + a11y + Perf Quality Gate — Research

**Researched:** 2026-06-03
**Domain:** Playwright E2E + axe-core, ESLint jsx-a11y elevation, responsive navigation, vaul bottom-sheets, Lighthouse CI, reduced-motion audit
**Confidence:** HIGH (all key claims verified against installed packages, official docs, or codebase ground truth)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Full Playwright — `@playwright/test` + `@axe-core/playwright`. Three browser projects (Chromium, WebKit, Firefox). One automated suite sweeps every authenticated route × 4 viewport widths (360/390/768/1280), asserting (a) no horizontal scroll and (b) zero critical/serious axe violations. Cross-browser smoke covers `/login` + `/dashboard` + `/vulnerabilities` + one detail page across all three engines.
- **D-02:** Safari = WebKit automated gate + manual Safari.app spot-check. Short manual Safari.app pass on smoke routes recorded in `15-HUMAN-UAT.md`, specifically confirming severity glyphs (■ ▲ ◆ ○ □) render legibly at 14px on real Safari DPR.
- **D-03:** axe blocking bar = WCAG 2.1 AA. Tags: `wcag2a`, `wcag2aa`, `wcag21aa` as build-blocking set (zero critical/serious). Also run WCAG 2.2 AA checks (`wcag22aa`) — surface as report/warnings only.
- **D-04:** Elevate `eslint-plugin-jsx-a11y` to `error` level (currently transitive via `eslint-config-next` at `warn`). Fix any violations this surfaces.
- **D-05:** Three responsive tiers: `<768px` → 4-slot bottom-nav with `env(safe-area-inset-bottom)`; `768–999px` → topbar hamburger → slide-in drawer; `≥1000px` → existing 220px sidebar.
- **D-06:** Bottom-nav "More" slot opens a vaul bottom sheet listing remaining destinations (Assets, CSPM, Connectors, Users, Settings). Active route uses gradient-strip indicator.
- **D-07:** All app modals/dialogs convert to vaul bottom sheets on mobile. Audit and convert: `ConfirmModal`, the connector credential form, reassign-owner, settings dialogs.
- **D-08:** Scripted local run + committed report. npm script runs Lighthouse CI (mobile preset) against `/login` + `/dashboard` (must report ≥90 performance AND ≥90 accessibility); `scripts/check-bundle.mjs` extended to assert ≤250 KB gzipped initial JS across ALL routes from `next build`. Results committed as `15-PERF-REPORT.md`. No CI infra dependency.
- **D-09:** Fix everything the audit surfaces before the phase closes. Only exception: defects requiring backend changes are logged to v1.x backlog with a risk note.
- **D-10:** UX-07-05 (theme/FOUC) is verify-only. `theme.tsx` + `layout.tsx` head bootstrap already implemented. Verify: no white flash on cold `/login` load in dark-OS mode, localStorage persistence, `prefers-color-scheme` honoring.
- **D-11:** UX-07-04 (reduced-motion) is an audit, not a build. The hook exists. Audit that EVERY motion site honors `prefers-reduced-motion: reduce`.

### Claude's Discretion

- Exact Playwright config structure, test-file organization, and route-enumeration approach.
- Which specific Lighthouse CI package/runner to use.
- How `check-bundle.mjs` is extended to iterate all routes.
- Drawer slide-in animation specifics and bottom-nav icon choices (lucide-react, already a dep).
- Whether existing `vitest-axe` component tests are retained alongside Playwright route tests (recommended: keep component-level, add route-level — they're complementary).

### Deferred Ideas (OUT OF SCOPE)

- **UX-D-03** — Light-theme visual polish pass (verify toggle works, not full per-screen light-mode QA sweep).
- **UX-D-06** — Page-transition motion (cross-fade between routes; deferred).
- **Backend-requiring defects:** logged to v1.x backlog, not fixed in this phase.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-07-01 | Every screen tested at 360/390/768/1280 viewport widths. No horizontal scroll. Sidebar collapses to hamburger below 1000px. Tables collapse to card view. | Playwright viewport matrix + scroll assertion; sidebar already hidden at `max-[999px]`. |
| UX-07-02 | 4-slot bottom-nav on mobile with safe-area handling. Modals convert to bottom sheets via `vaul`. | Bottom-nav build; vaul 1.1.2 already in deps; D-07 conversion audit. |
| UX-07-03 | WCAG 2.1 AA public commitment, WCAG 2.2 AA internal target. `eslint-plugin-jsx-a11y` at error; axe-core in Playwright per route. | D-04 ESLint elevation; D-01/D-03 Playwright+axe harness. |
| UX-07-04 | `prefers-reduced-motion: reduce` substitutes — cross-fade only, skip mount-stagger, no pulses. | Audit of 7 motion sites; globals.css blanket override is in place but 2 gaps confirmed. |
| UX-07-05 | `prefers-color-scheme` honored on first visit; user toggle persists in `localStorage`; FOUC-prevention blocking script before hydration. | Verify-only — `theme.tsx` + `layout.tsx` head bootstrap confirmed in codebase. |
| UX-07-06 | Lighthouse mobile target ≥90 perf + ≥90 a11y on `/login` and `/dashboard`. JS budget ≤250 KB gzipped per route initial. Charts code-split verified. | `@lhci/cli` + extended `check-bundle.mjs` (all-route mode). |
| UX-07-07 | Cross-browser tested (Chrome, Safari, Firefox) on the smoke test suite. Severity glyphs (■ ▲ ◆ ○ □) render legibly at 14px and below. | D-01 Playwright projects; D-02 manual Safari.app spot-check. |
</phase_requirements>

---

## Summary

Phase 15 is the milestone closer for v2.0 UI/UX Redesign. All 10 authenticated screens across 11 routes are already built (Phases 9–14); this phase installs the quality gate on top of them. Research reveals the work is firmly bounded and mostly additive tooling + bounded UI build.

The **toolchain gap is large**: no Playwright config or tests exist today; no ESLint config file exists (Next.js lint uses auto-generated defaults); the `check-bundle.mjs` script handles only one `--route` at a time. All three need new infrastructure. In contrast, the **codebase already has strong foundations**: vaul 1.1.2 is pinned, lucide-react is installed, the `DrillPanelMobile` vaul precedent is robust and can be generalized, and the globals.css blanket reduced-motion rule covers most animation sites.

Two concrete gaps were discovered during the motion audit:
1. `animate-gradient-drift` on the login page left panel lacks a `motion-safe:` guard (relying only on the globals.css `!important` blanket override, which should work but is fragile)
2. `animate-pulse` on `hero.tsx` pulsing-dot and skeleton states uses the same globals.css blanket — the comment says "honors via globals.css" but using `motion-safe:animate-pulse` would be belt-and-suspenders

The reassign-owner surface is an **inline combobox**, not a modal, so D-07 conversion does not apply to it. The D-07 audit list is: `ConfirmModal` (used in connectors + settings pages) + connector credential form (inline `role="dialog"` div, custom focus trap).

The authentication strategy for Playwright is straightforward: the app uses `localStorage("getvul_token")` JWT storage, so a `setup.ts` global that logs in via the email/password API and saves `context.storageState()` will work cleanly.

**Primary recommendation:** Organize work as five waves — (0) Playwright + ESLint infrastructure, (1) axe harness + horizontal-scroll sweep, (2) mobile nav build, (3) vaul modal conversions + motion gap fixes, (4) Lighthouse + budget gate + verification artifacts.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Playwright E2E test harness | CI / Test Runner | — | Route-level browser automation; jsdom cannot test real layout (horizontal scroll, viewport media queries) |
| axe WCAG scan | CI / Test Runner | — | Route-level real-DOM injection; `vitest-axe` component-level stays complementary |
| eslint-plugin-jsx-a11y | Build / Lint | — | Static analysis at author-time; no runtime tier needed |
| Mobile navigation (bottom-nav, drawer) | Browser / Client | — | Responsive CSS + React state; no server involvement |
| vaul bottom-sheet conversions | Browser / Client | — | Client-side modal replacement; pure UI |
| Lighthouse perf audit | Local script | — | Run against live dev server or production build; no CI infra this phase |
| Bundle budget enforcement | Build | — | `next build` output parsing; extends existing check-bundle.mjs script |
| Reduced-motion audit | Browser / Client | CSS | Hook exists; some sites use globals.css blanket, others use `motion-safe:` prefix |
| Theme/FOUC verification | Browser / Client | — | Verify-only; `layout.tsx` head bootstrap already runs synchronously |

---

## Standard Stack

### Core (already in package.json — install only new items)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@playwright/test` | 1.60.0 (current) | E2E browser automation, multi-project viewport matrix, storageState auth | Official Playwright test runner; deepest Next.js App Router support [VERIFIED: npm view] |
| `@axe-core/playwright` | 4.11.3 (current) | Inject axe-core into live Playwright page, WCAG tag filtering | Official Deque integration for Playwright [VERIFIED: npm view] |
| `vaul` | 1.1.2 (pinned in package.json) | Bottom-sheets, NestedRoot for confirm within drill | Already exact-pinned; `Drawer.Root`, `Drawer.NestedRoot`, `Drawer.Content`, `Drawer.Portal` all verified in package [VERIFIED: codebase] |
| `lucide-react` | ^0.383.0 | Bottom-nav + hamburger icons | Already a dep; consistent with all other icon usage in the app [VERIFIED: package.json] |
| `@lhci/cli` | 0.15.1 (current) | Scripted Lighthouse CI mobile runs, `lhci collect` + `lhci assert` | Local CLI runner; `--startServerCommand` support; no server upload needed [VERIFIED: npm view + npx test] |

### Supporting (already in package.json — no new installs)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `axe-core` | 4.12.0 (bundled in @axe-core/playwright) | WCAG rule engine | Consumed transitively; `wcag22aa` tag covers `target-size` (24×24 minimum, SC 2.5.8) [VERIFIED: node -e getRules] |
| `vitest-axe` | ^0.1.0 | Existing component-level axe tests (jsdom) | Keep for component tests; Playwright route-level is additive |
| `eslint-plugin-jsx-a11y` | (via eslint-config-next) | Static a11y lint | Elevation to `error` in `.eslintrc.json`; already installed transitively [VERIFIED: node_modules] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@lhci/cli` | Raw `lighthouse` CLI | `lhci` adds `collect`/`assert`/`upload` subcommands + JSON report output; raw `lighthouse` is simpler but no built-in assertion layer |
| `motion-safe:` Tailwind prefix | `usePrefersReducedMotion` hook | Hook is more flexible (can stop animation vs. just skip via CSS); CSS prefix is zero-JS; use hook for chart bars, CSS prefix for CSS keyframe animations |
| `vaul` Drawer for all modals | Radix Dialog | vaul already pinned; `DrillPanelMobile` precedent exists; consistent gesture model across the app |

**Installation (net-new devDependencies only):**
```bash
cd frontend
npm install --save-dev @playwright/test @axe-core/playwright @lhci/cli
npx playwright install --with-deps
```

**Version verification:**
```bash
npm view @playwright/test version   # → 1.60.0 [VERIFIED: 2026-06-03]
npm view @axe-core/playwright version  # → 4.11.3 [VERIFIED: 2026-06-03]
npm view @lhci/cli version  # → 0.15.1 [VERIFIED: 2026-06-03]
```

---

## Architecture Patterns

### System Architecture Diagram

```
next dev (port 3000)
        │
        ├─── Playwright test suite ──────────────────────────────────────────┐
        │    frontend/e2e/                                                    │
        │      playwright.config.ts                                           │
        │      ├── auth/setup.ts → POST /auth/login → storageState.json     │
        │      ├── fixtures/axe.ts → AxeBuilder factory (WCAG 2.1 AA tags)  │
        │      │                                                              │
        │      ├── viewport-scroll.spec.ts                                   │
        │      │   ALL_ROUTES × [360,390,768,1280] → no horizontal scroll    │
        │      │                                                              │
        │      ├── a11y-routes.spec.ts                                       │
        │      │   ALL_ROUTES × Chromium → zero axe critical/serious         │
        │      │                                                              │
        │      └── smoke.spec.ts                                             │
        │          [/login,/dashboard,/vulnerabilities,/assets/sample]       │
        │          × [Chromium,WebKit,Firefox] → renders + no axe violations │
        │                                                                    │
        ├─── ESLint gate ─────────────────────────────────────────────────── │
        │    .eslintrc.json (created by this phase)                          │
        │    extends: "next" → jsx-a11y rules elevated to error             │
        │                                                                    │
        ├─── Bundle budget gate ──────────────────────────────────────────── │
        │    scripts/check-bundle.mjs (extended all-routes mode)            │
        │    next build output → parse ALL routes → assert ≤250 KB each     │
        │                                                                    │
        └─── Lighthouse gate ─────────────────────────────────────────────── │
             lhci.config.js (mobile preset)                                  │
             npm run perf:lh → lhci collect (URLs) + lhci assert (≥90/≥90) │
             → 15-PERF-REPORT.md (committed artifact)                        │

AppShell (authed layout)
  ├── ≥1000px: <Sidebar> (existing, unchanged)
  ├── 768–999px: <Topbar> with hamburger → <NavDrawer> (new, vaul Drawer)
  └── <768px: <BottomNav> (new, 4-slot) + "More" → vaul Drawer bottom sheet

Dialogs (D-07 vaul conversion):
  ConfirmModal → <ResponsiveDialog> wrapper
    desktop: current fixed-centered div (unchanged internals)
    mobile (<768px): vaul Drawer.Root bottom sheet wrapper
  ConnectorForm → same ResponsiveDialog wrapper pattern
```

### Recommended Project Structure

```
frontend/
├── e2e/                              # Playwright E2E (new — separate from src/)
│   ├── playwright.config.ts          # 3 browser projects, storageState, baseURL
│   ├── auth/
│   │   └── setup.ts                 # global setup: login → .auth/state.json
│   ├── fixtures/
│   │   ├── auth.ts                  # workerStorageState fixture
│   │   └── axe.ts                   # makeAxeBuilder factory (wcag2a,wcag2aa,wcag21aa)
│   ├── viewport-scroll.spec.ts      # ALL_ROUTES × 4 widths, no horizontal scroll
│   ├── a11y-routes.spec.ts          # ALL_ROUTES axe sweep (Chromium only)
│   └── smoke.spec.ts                # smoke × 3 browsers
│
├── scripts/
│   ├── check-bundle.mjs             # existing — extend to accept --all-routes mode
│   └── check-bundle-all.mjs         # OR: new wrapper that reads next build output once
│                                    # and checks every route against 250 KB
│
├── lhci.config.js                   # Lighthouse CI config (mobile preset, 2 URLs)
│
└── src/
    ├── components/
    │   └── shell/
    │       ├── app-shell.tsx        # extend: add BottomNav + NavDrawer at breakpoints
    │       ├── bottom-nav.tsx       # new: 4-slot bottom-nav
    │       ├── nav-drawer.tsx       # new: slide-in drawer (tablet hamburger)
    │       └── nav-more-sheet.tsx   # new: vaul bottom sheet for "More" destinations
    │   └── ui/
    │       └── responsive-dialog.tsx # new: desktop dialog / mobile vaul bottom sheet
    │
    └── .eslintrc.json               # new: extends "next", elevates jsx-a11y to error
```

### Pattern 1: Playwright Multi-Project Viewport Matrix

**What:** One spec file iterates `ALL_ROUTES` × `VIEWPORTS` with a `test.use({ viewport })` fixture loop.
**When to use:** For UX-07-01 (horizontal scroll check) across all 11 authenticated routes.

```typescript
// Source: https://playwright.dev/docs/emulation#viewport (Context7 /microsoft/playwright.dev)
// e2e/viewport-scroll.spec.ts
import { test, expect } from './fixtures/auth';

const VIEWPORTS = [
  { width: 360, height: 812 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1280, height: 900 },
];

const ALL_ROUTES = [
  '/dashboard',
  '/dashboard/vulnerabilities',
  '/dashboard/assets',
  '/dashboard/assets/some-id',  // seed or known asset
  '/dashboard/tickets',
  '/dashboard/tickets/some-id',
  '/dashboard/tickets/rules',
  '/dashboard/cspm',
  '/dashboard/connectors',
  '/dashboard/users',
  '/dashboard/settings',
];

for (const viewport of VIEWPORTS) {
  test.describe(`viewport ${viewport.width}×${viewport.height}`, () => {
    test.use({ viewport });
    for (const route of ALL_ROUTES) {
      test(`no horizontal scroll — ${route}`, async ({ page }) => {
        await page.goto(route);
        // Wait for hydration / navigation guard to settle
        await page.waitForLoadState('networkidle');
        const scrollWidth = await page.evaluate(
          () => document.documentElement.scrollWidth,
        );
        const clientWidth = await page.evaluate(
          () => document.documentElement.clientWidth,
        );
        expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
      });
    }
  });
}
```

### Pattern 2: Playwright axe Fixture with Tag Filtering

**What:** A shared `makeAxeBuilder` fixture pre-configured for WCAG 2.1 AA blocking, plus a separate WCAG 2.2 report-only run.
**When to use:** Per-route axe sweep in `a11y-routes.spec.ts` and in smoke.

```typescript
// Source: https://playwright.dev/docs/accessibility-testing (Context7 /microsoft/playwright.dev)
// e2e/fixtures/axe.ts
import { test as base } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

export const test = base.extend<{
  makeAxeBuilder: () => AxeBuilder;
  makeAxeBuilderReportOnly: () => AxeBuilder;
}>({
  makeAxeBuilder: async ({ page }, use) => {
    // BLOCKING: WCAG 2.0 A/AA + 2.1 AA — zero critical/serious violations
    const factory = () =>
      new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']);
    await use(factory);
  },
  makeAxeBuilderReportOnly: async ({ page }, use) => {
    // REPORT-ONLY: WCAG 2.2 AA — target-size (24×24 min) rule
    const factory = () =>
      new AxeBuilder({ page }).withTags(['wcag22aa']);
    await use(factory);
  },
});
export { expect } from '@playwright/test';
```

**Filtering to critical/serious only:**
```typescript
// In the spec, assert no critical or serious violations:
const results = await makeAxeBuilder().analyze();
const blocking = results.violations.filter(
  v => v.impact === 'critical' || v.impact === 'serious',
);
expect(blocking).toEqual([]);

// WCAG 2.2 — log but do not fail:
const wcag22Results = await makeAxeBuilderReportOnly().analyze();
if (wcag22Results.violations.length > 0) {
  console.warn('WCAG 2.2 AA report-only violations:', wcag22Results.violations.map(v => v.id));
}
```

### Pattern 3: Playwright storageState Authentication (localStorage JWT)

**What:** Global setup logs in via email/password API, saves context.storageState() including localStorage tokens to `.auth/state.json`. All authed tests use this file via `storageState`.
**When to use:** Accessing `/dashboard/*` routes which redirect to `/login` when `getvul_token` is absent from localStorage.

```typescript
// Source: https://playwright.dev/docs/auth (Context7 /microsoft/playwright.dev)
// e2e/auth/setup.ts
import { test as setup, expect } from '@playwright/test';
import path from 'path';

const authFile = path.join(__dirname, '../.auth/state.json');

setup('authenticate', async ({ page }) => {
  // Navigate to login — triggers client-side redirect on authed routes
  await page.goto('/login');
  await page.fill('input[type="email"]', process.env.E2E_EMAIL ?? 'admin@getvul.local');
  await page.fill('input[type="password"]', process.env.E2E_PASSWORD ?? 'Admin123!');
  await page.click('button[type="submit"]');
  // Wait for redirect to /dashboard (auth sets localStorage("getvul_token"))
  await page.waitForURL('**/dashboard');
  // Persist localStorage + cookies into storageState
  await page.context().storageState({ path: authFile });
});
```

```typescript
// playwright.config.ts — wire storageState for authed projects
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  baseURL: 'http://localhost:3000',
  globalSetup: './e2e/auth/setup.ts',
  projects: [
    // Auth setup (runs once)
    { name: 'setup', testMatch: /.*\.setup\.ts/ },

    // Full viewport + axe sweep — Chromium only
    {
      name: 'chromium-a11y',
      use: { ...devices['Desktop Chrome'], storageState: 'e2e/.auth/state.json' },
      dependencies: ['setup'],
    },

    // Cross-browser smoke — 3 engines
    {
      name: 'chromium-smoke',
      use: { ...devices['Desktop Chrome'], storageState: 'e2e/.auth/state.json' },
      testMatch: /smoke\.spec\.ts/,
      dependencies: ['setup'],
    },
    {
      name: 'webkit-smoke',
      use: { ...devices['Desktop Safari'], storageState: 'e2e/.auth/state.json' },
      testMatch: /smoke\.spec\.ts/,
      dependencies: ['setup'],
    },
    {
      name: 'firefox-smoke',
      use: { ...devices['Desktop Firefox'], storageState: 'e2e/.auth/state.json' },
      testMatch: /smoke\.spec\.ts/,
      dependencies: ['setup'],
    },
  ],
});
```

**Critical gotcha:** `useAuth()` in the app reads `localStorage("getvul_token")` on mount and immediately redirects to `/login` if missing. The `storageState` fixture must include localStorage (it does — Playwright's `storageState()` captures both cookies and localStorage by default). [VERIFIED: codebase auth.tsx]

### Pattern 4: ESLint jsx-a11y Elevation

**What:** Create `.eslintrc.json` that extends `"next"` (which provides jsx-a11y transitively) and overrides all jsx-a11y rules to `"error"`.
**When to use:** D-04 — No ESLint config file currently exists in `frontend/`. ESLint 8 is installed (^8.57.0). Creating `.eslintrc.json` is the correct legacy-config format.

```json
// frontend/.eslintrc.json (new file)
{
  "extends": "next/core-web-vitals",
  "rules": {
    "jsx-a11y/alt-text": "error",
    "jsx-a11y/aria-props": "error",
    "jsx-a11y/aria-proptypes": "error",
    "jsx-a11y/aria-unsupported-elements": "error",
    "jsx-a11y/role-has-required-aria-props": "error",
    "jsx-a11y/role-supports-aria-props": "error",
    "jsx-a11y/anchor-is-valid": "error",
    "jsx-a11y/click-events-have-key-events": "error",
    "jsx-a11y/interactive-supports-focus": "error",
    "jsx-a11y/no-noninteractive-element-interactions": "error",
    "jsx-a11y/label-has-associated-control": "error",
    "jsx-a11y/no-autofocus": "warn"
  }
}
```

**Why `next/core-web-vitals` (not just `"next"`):** `next/core-web-vitals` is the superset recommended by Next.js for new projects; it includes all Next.js rules plus stricter Core Web Vitals enforcement. [CITED: eslint-config-next/index.js in node_modules]

**Pre-elevation warning:** `eslint-config-next` currently configures only 6 jsx-a11y rules at `warn` (alt-text, aria-props, aria-proptypes, aria-unsupported-elements, role-has-required-aria-props, role-supports-aria-props). The elevation adds ~10 additional `error`-level rules that are currently silent. Expect violations to surface when the `.eslintrc.json` is first applied — D-09 requires fixing them all.

### Pattern 5: Bottom-Nav (mobile) + Slide-in Drawer (tablet)

**What:** `app-shell.tsx` currently renders `<Sidebar>` (hidden at `max-[999px]`) + `<Topbar>` + `<main>`. Extend it with two new nav components that appear at sub-1000px breakpoints.
**When to use:** D-05 responsive tiers.

```tsx
// frontend/src/components/shell/app-shell.tsx (extended)
'use client';
import type { ReactNode } from 'react';
import { Sidebar } from './sidebar';
import { Topbar } from './topbar';
import { BottomNav } from './bottom-nav';      // new
import { NavDrawer } from './nav-drawer';       // new

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-bg text-text">
      <div className="flex">
        <Sidebar />
        <div className="flex-1 min-w-0">
          {/* Topbar: shows hamburger icon at 768–999px breakpoint */}
          <Topbar />
          <NavDrawer />  {/* Tablet slide-in drawer — renders portal, hidden until open */}
          <main className="px-6 py-6 lg:px-8 lg:py-8 pb-[calc(64px+env(safe-area-inset-bottom))] min-[768px]:pb-6">
            {children}
          </main>
        </div>
      </div>
      {/* Bottom-nav: phone only (<768px) */}
      <BottomNav />
    </div>
  );
}
```

**Bottom-nav safe-area pattern:**
```tsx
// src/components/shell/bottom-nav.tsx (new)
// Position: fixed bottom-0, z-50, full width
// Height: 56px + env(safe-area-inset-bottom)
// The 4 slots: Dashboard (Home icon), Vulnerabilities (Bug), Tickets (Ticket), More (MoreHorizontal)
// Active: gradient-strip on top edge (matching sidebar active indicator pattern)

<nav
  className="min-[768px]:hidden fixed bottom-0 inset-x-0 z-50 bg-bg-darker border-t border-border"
  style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
  aria-label="Mobile navigation"
>
  {/* 4-slot grid: minTouch targets ≥48x48px actual tap area */}
</nav>
```

**Touch target sizing:** D-03 requires 24×24 px WCAG 2.2 minimum (report-only). Design convention is ≥48×48px actual touch area (via padding) even when icon is 20×20px. The interaction-patterns.md does not specify a bottom-nav touch target size explicitly, so defer to WCAG 2.2 SC 2.5.8 (24×24 minimum) as the internal target. [CITED: CONTEXT.md D-03 + REQUIREMENTS-v2.md UX-07-03] [ASSUMED: 48×48px target area; consistent with Apple/Google mobile HIG conventions]

**Drawer slide-in for tablet (768–999px):**
```tsx
// NavDrawer uses vaul with direction="right" (side drawer) OR a custom CSS slide-in
// vaul's primary design is for bottom-drawers; for a side-sliding hamburger drawer
// a simpler approach is: CSS transform + transition with a backdrop overlay
// This is per Claude's Discretion (CONTEXT.md)
```

**Note on direction:** vaul supports `direction="right"` for side drawers as of vaul 1.x. The existing `DrillPanelMobile` uses `direction="bottom"`. Using vaul for the tablet hamburger drawer is possible but the slide-in tablet nav is straightforward enough to build with Tailwind transitions + a portal. This is Claude's Discretion territory — vaul works, so does a lightweight CSS solution. Recommendation: use vaul for consistency since it's already a dep and handles focus trapping, Esc, and backdrop automatically.

### Pattern 6: vaul Responsive Dialog Wrapper (D-07)

**What:** A single `ResponsiveDialog` component that renders a centered modal on desktop and a vaul Drawer bottom-sheet on mobile (`<768px`). All existing modals swap their outer shell for this component, keeping their inner content unchanged.
**When to use:** D-07 conversion of `ConfirmModal`, connector credential form, settings dialogs.

```tsx
// src/components/ui/responsive-dialog.tsx (new)
'use client';
import { useMediaQuery } from '@/hooks/use-media-query';
import { Drawer } from 'vaul';

interface ResponsiveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ariaLabel: string;
  children: React.ReactNode;
}

export function ResponsiveDialog({
  open, onOpenChange, ariaLabel, children,
}: ResponsiveDialogProps) {
  const isMobile = useMediaQuery('(max-width: 767px)');

  if (isMobile) {
    // Mobile: vaul bottom sheet (matching DrillPanelMobile pattern)
    if (!open) return null;
    return (
      <Drawer.Root open={open} onOpenChange={onOpenChange} direction="bottom">
        <Drawer.Portal>
          <Drawer.Overlay className="fixed inset-0 z-[9000] bg-bg-darker/60" />
          <Drawer.Content
            className="fixed inset-x-0 bottom-0 z-[9001] max-h-[80dvh] rounded-t-lg border-t border-border-subtle bg-surface"
            aria-label={ariaLabel}
          >
            <Drawer.Title className="sr-only">{ariaLabel}</Drawer.Title>
            {children}
          </Drawer.Content>
        </Drawer.Portal>
      </Drawer.Root>
    );
  }

  // Desktop: existing centered modal behavior
  if (!open) return null;
  return (
    <div role="dialog" aria-modal="true" aria-label={ariaLabel}
      className="fixed inset-0 z-[9000] flex items-center justify-center">
      <div className="absolute inset-0 bg-bg-darker/60" onClick={() => onOpenChange(false)} />
      <div className="relative z-[9001] bg-surface rounded-lg border border-border-subtle ...">
        {children}
      </div>
    </div>
  );
}
```

**D-07 conversion scope (confirmed in codebase):**
- `ConfirmModal` — used in `connectors/page.tsx` (delete confirm) and `settings/page.tsx` (unsaved-changes guard). Has its own focus trap + Esc handler; these can be removed in the mobile path since vaul handles them.
- Connector credential form — inline `role="dialog"` div in `connectors/page.tsx` (refs: `formDialogRef`, `formTitleId`). Custom `trapTabKey` + Esc handler. Same conversion pattern.
- `reassign-owner` — NOT a modal. The `ReassignCombobox` is an inline combobox in the `OwnerCard`. No D-07 conversion needed. [VERIFIED: codebase owner-card.tsx + reassign-combobox.tsx]
- Settings dialogs — `ConfirmModal` already captured above.

### Pattern 7: check-bundle.mjs All-Routes Extension

**What:** New `--all-routes` flag (or a new `check-bundle-all.mjs` script) that: runs `next build` once, captures the full output, parses EVERY route line, and asserts each is ≤250 KB.
**When to use:** D-08 — extend existing check-bundle.mjs per Claude's Discretion.

```javascript
// scripts/check-bundle-all.mjs (new companion script)
// Runs `next build` once, parses all route lines, checks each ≤250 KB (256000 bytes).
// Reports pass/fail per route and exits 1 if any route exceeds budget.
// Reuses parseRouteLine logic from check-bundle.mjs as a shared utility.
//
// Known routes from `next build` output (all have ○ or ● prefix):
// /, /login, /dashboard, /dashboard/vulnerabilities, /dashboard/assets,
// /dashboard/assets/[id], /dashboard/tickets, /dashboard/tickets/[id],
// /dashboard/tickets/rules, /dashboard/cspm, /dashboard/connectors,
// /dashboard/users, /dashboard/settings, /dev/primitives
//
// The per-route "First Load JS" already includes the shared bundle (~87 kB from
// Phase 10 measurements). The 250 KB budget is the TOTAL (shared + per-route).
```

### Anti-Patterns to Avoid

- **Nesting `<nav>` landmarks inside `<nav>`:** `sidebar.tsx` already avoids this correctly (inner sections are `<div>`, not `<nav>`). Apply the same rule to `BottomNav` and `NavDrawer`.
- **Running axe against the jsdom-rendered component:** jsdom cannot test real horizontal scroll or viewport-dependent CSS. Route-level Playwright is additive to `vitest-axe`, not a replacement.
- **Using `useState` without `suppressHydrationWarning` for isMobile:** `useMediaQuery` is a client-side hook that returns `false` on SSR. The bottom-nav and nav-drawer components must be `'use client'` with no SSR mismatch. The current `DrillPanelMobile` uses `useMediaQuery` correctly — follow its pattern.
- **Calling `npx playwright install` inside the test run:** Install browsers once as a Wave 0 task; not on every CI run.
- **Using `wcag22aa` tag in the BLOCKING axe assertion:** Only `target-size` is in `wcag22aa` today (axe-core 4.12.0). It must be report-only per D-03. [VERIFIED: node -e getRules]
- **Assuming `focus-not-obscured` is automated by axe:** axe-core 4.12 has no `focus-not-obscured` rule (WCAG 2.4.11). This must be verified manually — the bottom-nav being `position: fixed` at the bottom means it could obscure focused elements scrolled near it. Manual verification required.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Browser-level a11y scanning | Custom rule engine | `@axe-core/playwright` | Deque's engine is the industry standard; covers 50+ WCAG rules with precise impact levels |
| Focus trapping in bottom sheets | Custom `trapTabKey` + keydown handlers | vaul (built-in) | vaul uses Radix Dialog primitives under the hood, which handle focus trap, Esc, ARIA modal; `ConfirmModal`'s custom focus-trap code can be removed for the mobile path |
| Lighthouse performance scoring | Custom perf metrics | `@lhci/cli` | Lighthouse audit requires Chrome DevTools Protocol; `lhci` wraps it with assertion support |
| Cross-browser browser launch | Manual browser installs | `npx playwright install --with-deps` | Playwright manages Chromium/WebKit/Firefox downloads with matched versions |
| Horizontal-scroll detection | CSS overflow audit scripts | Playwright `scrollWidth <= clientWidth` assertion | Tests real browser rendering, not computed styles |
| WCAG tag management | Custom axe rule lists | `AxeBuilder.withTags()` | Official API; tags map to exact WCAG success criteria |

**Key insight:** The tools in this phase are all security/quality enforcement infrastructure — the cost of a wrong custom implementation is false confidence in the quality gate, not just a bug.

---

## Common Pitfalls

### Pitfall 1: Auth Redirect Timing in Playwright
**What goes wrong:** Tests navigate to `/dashboard` and immediately get redirected to `/login` because `useAuth()` hasn't loaded `localStorage("getvul_token")` yet — `waitForLoadState('networkidle')` fires before React hydrates and the auth guard runs.
**Why it happens:** The auth redirect is client-side (`router.replace('/login?next=...')` in `useAuth()`). The page HTML loads first (networkidle), then React hydrates, then useAuth fires the redirect.
**How to avoid:** After navigating, wait for the expected page content: `await expect(page.locator('nav[aria-label="Primary navigation"]')).toBeVisible()` OR use `waitForURL('**/dashboard*')`. The storageState approach should prevent the redirect entirely if localStorage is populated correctly before hydration.
**Warning signs:** Tests always redirect to `/login`; check that `storageState` JSON includes `localStorage` entries for `getvul_token`.

### Pitfall 2: scrollWidth > clientWidth Due to Fixed-Position Children
**What goes wrong:** `document.documentElement.scrollWidth` reports wider than the viewport because a fixed-position element (toast, bottom-nav, overlay) extends beyond the viewport.
**Why it happens:** Fixed-position elements with `right: 0` or `inset: 0` don't cause layout overflow, but elements that have `width: 200%` or translate off-screen CAN affect scrollWidth in some browsers.
**How to avoid:** Scope the horizontal-scroll check to `document.body.scrollWidth` and compare against `document.body.clientWidth`. Also check `document.documentElement.scrollWidth` — use `Math.max(scrollWidth, bodyScrollWidth)`. The actual test should use body-level scroll measurement.
**Warning signs:** Test fails only in WebKit but not Chromium (WebKit is stricter about what contributes to scrollWidth).

### Pitfall 3: vaul Direction="right" vs. CSS Slide-in for Tablet Nav
**What goes wrong:** Using vaul `direction="right"` for the tablet hamburger drawer and having it compete with the existing sidebar's `max-[999px]:hidden` rule, causing double-render.
**Why it happens:** AppShell renders `<Sidebar>` unconditionally; the `max-[999px]:hidden` class hides it. If `NavDrawer` also renders the full sidebar HTML, there are two nav structures.
**How to avoid:** `NavDrawer` renders a SEPARATE nav element with the same 9 destinations but different chrome (no brand mark, full-width, slide-in). It does NOT reuse `<Sidebar>`. Source-of-truth for nav items: export the `TRIAGE_ITEMS`, `WORKFLOW_ITEMS`, `UNLABELED_ITEMS` arrays from `sidebar.tsx` so `BottomNav` and `NavDrawer` import from the same source.
**Warning signs:** Two `aria-label="Primary navigation"` landmarks on the same page at 1000px+ — triggers axe `landmark-unique` rule.

### Pitfall 4: Lighthouse Requiring a Running Server
**What goes wrong:** `lhci collect` runs against localhost but the Next.js dev server isn't started; tests error on connection refused.
**Why it happens:** Lighthouse CI needs an HTTP server to audit; it can't audit `next build` output directly (the static HTML doesn't include runtime JS execution).
**How to avoid:** Use `lhci collect --startServerCommand="npm run start" --startServerReadyPattern="ready"` to let lhci manage the server lifecycle, OR run `npm run build && npm run start` first and run `lhci collect` against the already-running server. The `--startServerCommand` approach is more reproducible. [VERIFIED: lhci --help output]
**Warning signs:** `lhci collect` returns ECONNREFUSED immediately.

### Pitfall 5: Bottom-Nav `pb-safe` Obscuring Page Content
**What goes wrong:** Page content at the bottom gets hidden behind the fixed bottom-nav on mobile.
**Why it happens:** `position: fixed` bottom-nav doesn't participate in normal flow; page content scrolls under it.
**How to avoid:** Add `padding-bottom: calc(64px + env(safe-area-inset-bottom))` to the `<main>` element — but only when `<768px`. The AppShell `<main>` already gets `pb-` class; extend it with a responsive variant: `pb-[calc(64px+env(safe-area-inset-bottom))] min-[768px]:pb-6`.
**Warning signs:** Bottom of page lists are unreachable on mobile (last row hidden behind nav).

### Pitfall 6: eslint-plugin-jsx-a11y `no-noninteractive-element-interactions` False Positives
**What goes wrong:** Elevating jsx-a11y to `error` causes a cascade of new errors on table rows that have `onClick` handlers.
**Why it happens:** `jsx-a11y/no-noninteractive-element-interactions` flags `<tr onClick={...}>` as a violation. The correct pattern is to make the row keyboard-navigable with `role="button"` or `tabIndex={0}` + `onKeyDown`.
**How to avoid:** After elevating to `error`, run `next lint` and triage violations. Table rows in `VulnTable`, `TicketsTable`, etc. already have `tabIndex={0}` + `onKeyDown` from Phase 11 keyboard-nav implementation — verify those satisfy the rule. If not, add `role="row"` explicitly.
**Warning signs:** 20+ lint errors on first `next lint` run, clustered in table and list components.

### Pitfall 7: `animate-pulse` on Skeleton Elements and D-11 Coverage
**What goes wrong:** `hero.tsx` skeleton state (loading: `animate-pulse`) and multiple other `animate-pulse` usages rely on the globals.css blanket `animation-duration: 0.01ms !important` rather than the explicit `motion-safe:animate-pulse` pattern used in `sync-status-pill.tsx`.
**Why it happens:** The globals.css blanket DOES work (`!important` overrides the animation duration to near-zero), but it's fragile: a future inline style or `!important` on an animation duration could override it. Two approaches exist in the codebase: globals.css blanket (correct but implicit) and `motion-safe:` Tailwind prefix (explicit).
**How to avoid:** Per D-11, audit every `animate-pulse` usage and confirm coverage. Convert bare `animate-pulse` to `motion-safe:animate-pulse` for belt-and-suspenders. The login `animate-gradient-drift` also lacks a `motion-safe:` prefix but relies on the globals.css blanket.
**Warning signs:** DevTools > Rendering > Emulate prefers-reduced-motion still shows animations running.

---

## Code Examples

### Horizontal Scroll Assertion (Playwright)
```typescript
// Source: Pattern derived from Playwright evaluate API (CITED: playwright.dev/docs)
test('no horizontal scroll at 360px', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 812 });
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');

  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
```

### axe Route Sweep
```typescript
// Source: CITED: playwright.dev/docs/accessibility-testing
test('no axe violations', async ({ page, makeAxeBuilder }) => {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  const results = await makeAxeBuilder().analyze();
  const blocking = results.violations.filter(
    v => v.impact === 'critical' || v.impact === 'serious',
  );
  // Surface violations with context for easier debugging
  if (blocking.length > 0) {
    console.error('Blocking axe violations:', JSON.stringify(blocking, null, 2));
  }
  expect(blocking).toHaveLength(0);
});
```

### vaul Drawer.Root (matching DrillPanelMobile precedent)
```tsx
// Source: VERIFIED: vaul 1.1.2 node_modules + existing drill-panel-mobile.tsx
<Drawer.Root open={open} onOpenChange={(o) => { if (!o) onClose(); }} direction="bottom">
  <Drawer.Portal>
    <Drawer.Overlay className="fixed inset-0 z-[9000] bg-bg-darker/60" />
    <Drawer.Content
      className="fixed inset-x-0 bottom-0 z-[9001] rounded-t-lg border-t border-border-subtle bg-surface"
      aria-label={ariaLabel}
    >
      <Drawer.Title className="sr-only">{ariaLabel}</Drawer.Title>
      {children}
    </Drawer.Content>
  </Drawer.Portal>
</Drawer.Root>
```

### lhci.config.js (Lighthouse CI mobile preset)
```javascript
// Source: CITED: lhci --help output (verified 2026-06-03)
// frontend/lhci.config.js
module.exports = {
  ci: {
    collect: {
      numberOfRuns: 1,  // local run — 3 runs would be too slow
      startServerCommand: 'npm run start',
      startServerReadyPattern: 'ready',
      url: ['http://localhost:3000/login', 'http://localhost:3000/dashboard'],
      settings: {
        preset: 'perf',     // mobile: emulates Moto G4, 150ms RTT, 1.6x CPU slowdown
        formFactor: 'mobile',
        throttling: { rttMs: 150, throughputKbps: 1600, cpuSlowdownMultiplier: 4 },
      },
    },
    assert: {
      assertions: {
        'categories:performance': ['error', { minScore: 0.9 }],
        'categories:accessibility': ['error', { minScore: 0.9 }],
      },
    },
    upload: {
      target: 'filesystem',
      outputDir: './lighthouse-results',
    },
  },
};
```

### check-bundle-all.mjs (new all-routes mode)
```javascript
// scripts/check-bundle-all.mjs — runs `next build` once, checks every route ≤250 KB
// Parses ALL route lines from build output using the same parseRouteLine logic
// Reports: PASS/FAIL per route, exits 1 if any route exceeds budget
// The DYNAMIC routes ([id]) show placeholder text like /dashboard/assets/[id]
// in build output — they are static shell routes and share the route's JS budget
const MAX_KB = 250;  // 250 KB gzipped per route initial load (D-08)
// Implementation: read full build output, split by lines, find lines matching
// the route regex from check-bundle.mjs, collect ALL route→bytes pairs, assert each
```

### Bottom-nav active indicator (gradient-strip)
```tsx
// Matching the sidebar's gradient-strip active indicator (sidebar.tsx pattern)
// Source: VERIFIED: sidebar.tsx gradient-strip implementation
{active && (
  <span
    aria-hidden
    className="absolute top-0 inset-x-0 h-[3px] rounded-b bg-gradient-sunset-vertical"
  />
)}
// Note: sidebar uses left-edge strip (left-0, vertical); bottom-nav uses top-edge strip
// (top-0, horizontal) since the nav is at the bottom. `gradient-sunset-vertical` token
// may need orientation adjustment — confirm with foundation.md motion token or use
// `bg-gradient-sunset` at the horizontal axis.
```

---

## Runtime State Inventory

Not applicable — this is a frontend-only phase with no rename/refactor/migration work. There are no stored data, live service config, OS-registered state, secrets, or build artifacts that need updating.

---

## Reduced-Motion Audit Findings

This section documents the D-11 audit result from source inspection so the planner can include targeted fix tasks.

### globals.css Blanket Rule (confirmed present)
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```
This blanket rule covers ALL CSS keyframe animations app-wide. [VERIFIED: globals.css line 47-54]

### Motion Sites — Status

| File | Animation | Protection | Status |
|------|-----------|------------|--------|
| `app/login/page.tsx:110` | `animate-gradient-drift` (24s drift loop) | globals.css blanket only | GAP — lacks `motion-safe:` prefix; relying on `!important` blanket |
| `components/dashboard/hero.tsx:28` | `animate-pulse` (skeleton state) | globals.css blanket only | Acceptable — skeleton is transient loading state |
| `components/dashboard/hero.tsx:116` | `animate-pulse` (pulsing urgency dot) | Comment says "honors via globals.css" | GAP — comment documents intent but lacks explicit `motion-safe:animate-pulse` |
| `components/ui/trend-chart.tsx:220` | Bar entry animation | `usePrefersReducedMotion()` hook | COVERED — hook disables animation |
| `components/states/skeleton-table.tsx:51` | `animate-shimmer` | `motion-safe:animate-shimmer` | COVERED — explicit Tailwind prefix |
| `components/connectors/sync-status-pill.tsx:44` | `animate-pulse` (in-progress dot) | `motion-safe:animate-pulse` | COVERED |
| `components/cspm/cspm-status-pill.tsx:63` | `animate-pulse` (IN_PROGRESS) | `motion-safe:animate-pulse` | COVERED |
| `components/ui/Toast.tsx:78,81,111` | Slide-in transition | `motion-reduce:transition-none` | COVERED |
| `components/settings/save-bar.tsx:43` | `animate-in slide-in-from-bottom-2` | globals.css blanket | Acceptable — tailwindcss-animate classes, covered by globals.css |
| `components/ui/dropdown-menu.tsx:50,69` | `animate-in/out` (Radix Dropdown) | globals.css blanket | Acceptable |
| `components/dashboard/stat-strip-wired.tsx:26` | `animate-pulse` (skeleton) | globals.css blanket | Acceptable — skeleton transient |
| `components/dashboard/activity-rail.tsx:30` | `animate-pulse` (skeleton) | globals.css blanket | Acceptable — skeleton transient |

**Confirmed gaps requiring explicit fix (D-11):**
1. `login/page.tsx` — add `motion-safe:animate-gradient-drift` to the gradient-mesh div
2. `dashboard/hero.tsx` — change `animate-pulse` on the urgency dot to `motion-safe:animate-pulse`

All other animation sites are either covered by explicit mechanisms or are skeleton loading states where the globals.css blanket is the documented approach.

---

## Theme/FOUC Verification Guide (D-10)

The FOUC blocking script in `layout.tsx` is confirmed present and correct:

```typescript
// VERIFIED: layout.tsx THEME_BOOTSTRAP_SCRIPT
const THEME_BOOTSTRAP_SCRIPT = `(function(){
  try {
    var stored = localStorage.getItem('getvul_theme');
    var theme = stored || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();`;
```

**Verify procedure for D-10 (manual, DevTools):**
1. Open Chrome DevTools > Rendering > Emulate CSS media feature `prefers-color-scheme: dark`
2. Clear localStorage, hard-reload `/login` — should render dark theme immediately with no white flash
3. Click theme toggle in sidebar → confirm `data-theme` attribute changes on `<html>` → reload → confirm persisted
4. Set `prefers-color-scheme: light` in DevTools → clear localStorage → reload → should render light theme on first visit

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | All tooling | ✓ | v26.0.0 | — |
| `@playwright/test` | D-01 Playwright harness | ✗ (not installed) | — | Install via npm |
| Playwright browsers (Chromium/WebKit/Firefox) | D-01 cross-browser | ✗ (no cache at `~/.cache/ms-playwright`) | — | `npx playwright install --with-deps` |
| `@axe-core/playwright` | D-01 axe harness | ✗ (not installed) | — | Install via npm |
| `@lhci/cli` | D-08 Lighthouse gate | ✓ (via npx) | 0.15.1 | Already accessible |
| `lighthouse` | D-08 alternative | ✓ (via npx) | 13.3.0 | Use lhci instead |
| `eslint-plugin-jsx-a11y` | D-04 lint elevation | ✓ (transitive via eslint-config-next) | in node_modules | — |
| `vaul` (1.1.2) | D-06, D-07 | ✓ (in package.json, pinned) | 1.1.2 | — |
| `lucide-react` | D-05/D-06 nav icons | ✓ (in package.json) | ^0.383.0 | — |
| Running backend API | Playwright auth fixture | ✗ (not verified running) | — | Tests need `docker-compose up` or mock login |
| `.env.local` | `NEXT_PUBLIC_API_URL` | ✓ (file exists) | n/a | — |

**Missing dependencies requiring Wave 0 action:**
- `@playwright/test` + `@axe-core/playwright` + browser binaries — must be installed before any Playwright spec can run
- Running backend — Playwright auth fixture (`e2e/auth/setup.ts`) calls `POST /auth/login`; backend must be reachable at `http://localhost:8000` during test runs

**Test credentials:** Default admin is `admin@getvul.local` / `Admin123!` per `backend/create_admin.py`. [VERIFIED: codebase]

---

## Validation Architecture

This section maps each Success Criterion (#1–#7 from ROADMAP.md) to its automated validation method.

### Test Framework
| Property | Value |
|----------|-------|
| E2E framework | Playwright 1.60.0 (`@playwright/test`) |
| Unit/component framework | Vitest 4.1.6 + `vitest-axe` (existing, unchanged) |
| Playwright config | `frontend/e2e/playwright.config.ts` (Wave 0 gap) |
| Quick Playwright run | `npx playwright test --project=chromium-a11y --grep "axe"` |
| Full suite | `npx playwright test` |
| Lint gate | `cd frontend && npm run lint` |
| Bundle gate | `node scripts/check-bundle-all.mjs` |
| Perf gate | `npm run perf:lh` |

### Success Criterion → Validation Map

| SC # | Criterion | Validation Method | Automated Command |
|------|-----------|-------------------|-------------------|
| SC #1 | Every screen passes viewport audit at 360/390/768/1280; no horizontal scroll; sidebar collapses; tables collapse to card | `viewport-scroll.spec.ts` — Playwright assertion `scrollWidth <= clientWidth` per route per viewport | `npx playwright test viewport-scroll.spec.ts` |
| SC #2 | 4-slot bottom-nav renders on mobile; modals render as bottom sheets on mobile | `a11y-routes.spec.ts` at 360px viewport — assert nav landmark visible; check `BottomNav` renders + vaul Drawer opens on "More" click | `npx playwright test a11y-routes.spec.ts --project=chromium-a11y` |
| SC #3 | axe-core passes on every route (no critical/serious); `eslint-plugin-jsx-a11y` at error; 24×24 touch min on bottom-nav; focus-visible not obscured | `a11y-routes.spec.ts` — `AxeBuilder.withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()` filter critical/serious; `npm run lint` for jsx-a11y; `target-size` rule (wcag22aa, report-only); focus-not-obscured is manual | `npx playwright test a11y-routes.spec.ts` + `npm run lint` |
| SC #4 | `prefers-reduced-motion: reduce` honored — gradient-mesh stops, urgency dot static, stagger skips | DevTools Rendering panel → emulate prefers-reduced-motion → verify visually. Playwright `page.emulateMedia({ reducedMotion: 'reduce' })` + assert animation-duration computed style ≤ 0.02s | Manual + `npx playwright test` (emulated reduced-motion assertions in spec) |
| SC #5 | `prefers-color-scheme` honored first visit; theme toggle persists; no white flash on cold `/login` | Manual DevTools: clear localStorage, emulate `prefers-color-scheme: dark`, reload `/login` → assert `data-theme="dark"` pre-paint (DevTools Performance panel / Screenshot at first frame). Playwright can assert `page.locator('html').getAttribute('data-theme')` === 'dark' after load | `npx playwright test smoke.spec.ts --grep "theme"` + manual cold-load check |
| SC #6 | Lighthouse ≥90 perf + ≥90 a11y on `/login` and `/dashboard`; per-route initial JS ≤250 KB; `15-PERF-REPORT.md` committed | `npm run perf:lh` → `lhci collect` + `lhci assert` → exits 0 on pass; `node scripts/check-bundle-all.mjs` → exits 0 | `npm run perf:budget && npm run perf:lh` |
| SC #7 | Cross-browser smoke — Chrome/Safari/Firefox work on smoke routes; severity glyphs legible at 14px | `smoke.spec.ts` runs across all 3 Playwright projects (chromium-smoke, webkit-smoke, firefox-smoke). Manual Safari.app spot-check for glyph DPR rendering documented in `15-HUMAN-UAT.md` | `npx playwright test smoke.spec.ts` + manual UAT |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-07-01 | No horizontal scroll, 4 viewports × all routes | E2E Playwright | `npx playwright test viewport-scroll.spec.ts` | ❌ Wave 0 |
| UX-07-02 | Bottom-nav renders mobile; modals → bottom sheets | E2E Playwright + manual | `npx playwright test a11y-routes.spec.ts` | ❌ Wave 0 |
| UX-07-03 | axe WCAG 2.1 AA, jsx-a11y error, 24×24 targets | E2E Playwright + lint | `npx playwright test a11y-routes.spec.ts && npm run lint` | ❌ Wave 0 |
| UX-07-04 | prefers-reduced-motion honored at all sites | Manual + Playwright emulated | `npx playwright test` (reduced-motion spec) | ❌ Wave 0 |
| UX-07-05 | FOUC prevention, localStorage persistence, prefers-color-scheme | Manual + Playwright assertion | Playwright `data-theme` assertion after load | ❌ Wave 0 |
| UX-07-06 | Lighthouse ≥90 + JS ≤250 KB all routes | npm scripts | `npm run perf:lh && npm run perf:budget` | ❌ Wave 0 (extend check-bundle.mjs) |
| UX-07-07 | Cross-browser smoke pass, severity glyphs at 14px | E2E Playwright + manual | `npx playwright test smoke.spec.ts` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd frontend && npm run lint` (ESLint gate fast, < 15s)
- **Per wave merge:** `npx playwright test --project=chromium-a11y` (axe sweep on Chromium, ~2–5 min)
- **Phase gate:** Full Playwright suite (`npx playwright test`) + `npm run perf:lh` + `npm run perf:budget` — all green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `frontend/e2e/playwright.config.ts` — Playwright configuration, 3 browser projects
- [ ] `frontend/e2e/auth/setup.ts` — global auth setup (login → storageState)
- [ ] `frontend/e2e/fixtures/axe.ts` — AxeBuilder fixture with WCAG tag config
- [ ] `frontend/e2e/.auth/.gitkeep` — directory for storageState (gitignore the JSON file)
- [ ] `frontend/e2e/viewport-scroll.spec.ts` — SC #1 horizontal scroll matrix
- [ ] `frontend/e2e/a11y-routes.spec.ts` — SC #3 per-route axe sweep
- [ ] `frontend/e2e/smoke.spec.ts` — SC #7 cross-browser smoke
- [ ] `frontend/.eslintrc.json` — ESLint config (D-04 jsx-a11y elevation)
- [ ] `frontend/lhci.config.js` — Lighthouse CI config (D-08)
- [ ] `frontend/scripts/check-bundle-all.mjs` — all-routes budget check (D-08)
- [ ] Install: `npm install --save-dev @playwright/test @axe-core/playwright @lhci/cli && npx playwright install --with-deps`

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual a11y auditing | `@axe-core/playwright` automated per-route scan | Industry standard as of 2022+ | Deterministic, repeatable, CI-able |
| `eslint-plugin-jsx-a11y` as `warn` via eslint-config-next | Explicit `error` level in project `.eslintrc.json` | This phase (D-04) | Blocks builds on a11y violations |
| Single-route bundle check (`--route /dashboard`) | All-routes bundle check (new `check-bundle-all.mjs`) | This phase (D-08) | Catches route bundle bloat anywhere |
| No mobile navigation (sidebar hidden ≤999px, nothing replaces it) | Three-tier responsive nav (bottom-nav / drawer / sidebar) | This phase (D-05) | Mobile usable without hamburger dead-end |
| jsdom-only a11y tests (`vitest-axe`) | jsdom component-level + Playwright route-level | This phase (D-01) | jsdom misses real-layout horizontal-scroll; Playwright catches it |
| localStorage-based auth without Playwright auth fixture | storageState-based Playwright auth (captures localStorage JWT) | This phase | Enables authenticated route testing without complex mocking |

**Deprecated/outdated:**
- Running `next lint` without a `.eslintrc.json` (relies on Next.js default config — not self-documenting, harder to extend)
- Using `check-bundle.mjs --route /dashboard` alone as the perf gate (too narrow — only checks one route)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 48×48 px touch target area is appropriate for bottom-nav slots (beyond the 24×24 WCAG 2.2 minimum) | Standard Stack + Pattern 5 | If wrong: smaller targets could fail manual a11y review; WCAG 2.2 minimum (24×24) is the hard floor per D-03 |
| A2 | `lhci collect --startServerCommand="npm run start"` is the right approach for local Lighthouse runs (vs. pointing at a running dev server) | Pattern (lhci.config.js) | If wrong: need to run `npm run build && npm run start` manually before `npm run perf:lh` |
| A3 | Playwright `storageState()` captures localStorage entries containing `getvul_token` | Pattern 3 | If wrong: all authed tests will be unauthenticated; fallback is to use `page.evaluate(() => localStorage.setItem(...))` in a fixture instead of storageState |
| A4 | The default test admin `admin@getvul.local` / `Admin123!` will be available in the local dev environment when Playwright runs | Pattern 3 | If wrong: need `.env.local` test credentials set as `E2E_EMAIL`/`E2E_PASSWORD` env vars |
| A5 | `vaul` `direction="right"` works for the tablet slide-in hamburger drawer | Pattern 5 | If wrong: use CSS transform + Tailwind transition for the tablet drawer (simpler, still accessible if focus-trap is added manually) |

---

## Open Questions

1. **Backend availability for Playwright auth fixture**
   - What we know: Playwright's `setup.ts` calls `POST /auth/login` against `http://localhost:8000`
   - What's unclear: The planning docs don't specify whether tests run against `docker-compose up` or a standalone Next.js + mock API
   - Recommendation: Wave 0 plan should include a note in `15-HUMAN-UAT.md` about the prerequisite: `docker-compose up -d postgres redis backend frontend` before running `npx playwright test`

2. **`/dashboard/assets/[id]` and `/dashboard/tickets/[id]` in the viewport sweep**
   - What we know: Dynamic routes need a real ID to test (can't visit `/dashboard/assets/[id]` literally)
   - What's unclear: Whether seeded test data exists with known IDs
   - Recommendation: The smoke spec should use IDs from the fixture login's data response, OR the viewport sweep can use a fallback strategy (navigate to the list, click first row if it exists, assert no horizontal scroll)

3. **Playwright browser installation in project vs. system**
   - What we know: Playwright browsers are not installed (`~/.cache/ms-playwright` absent)
   - What's unclear: Whether this is a personal dev machine or a shared machine where system-level browser installs are preferred
   - Recommendation: Wave 0 runs `npx playwright install chromium webkit firefox` (no `--with-deps` if on macOS where system WebKit is used, but `--with-deps` is safer cross-platform)

---

## Project Constraints (from CLAUDE.md)

- Fonts: Inter + JetBrains Mono locked — bottom-nav and drawer must use `var(--font-sans)` / `var(--font-mono)` only
- Colors: Use CSS variables from `foundation.md` — NO freehand hex in bottom-nav or drawer components
- State patterns: Every new component with a loading/empty/error state must use the established patterns (SkeletonTable, EmptyState, PartialFailureBanner) — bottom-nav slots are always visible so no loading state; the drawer uses `useStats()` for count chips and must handle loading/error via `—` fallback (same pattern as sidebar)
- No `!important` anywhere (UX-F-02 contract) — the globals.css reduced-motion `!important` is the only explicit exception per the existing comment
- No Tailwind admin-template patterns
- lucide-react for all icons (already followed in sidebar.tsx; bottom-nav must use same icons)
- Auto-load `sketch-findings-getvul` references for any UI implementation — bottom-nav and drawer must follow `interaction-patterns.md` touch-target sizing and `app-shell.md` nav item patterns

---

## Sources

### Primary (HIGH confidence)
- VERIFIED in codebase: `frontend/package.json`, `frontend/src/components/shell/app-shell.tsx`, `frontend/src/components/shell/sidebar.tsx`, `frontend/src/components/shell/topbar.tsx`, `frontend/src/lib/theme.tsx`, `frontend/src/app/layout.tsx`, `frontend/src/hooks/use-prefers-reduced-motion.ts`, `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx`, `frontend/scripts/check-bundle.mjs`, `frontend/src/app/(authed)/dashboard/dashboard.a11y.test.tsx`, `frontend/src/app/globals.css`, `frontend/tailwind.config.ts`, `frontend/node_modules/eslint-config-next/index.js`
- VERIFIED via npm: `@playwright/test@1.60.0`, `@axe-core/playwright@4.11.3`, `@lhci/cli@0.15.1`, `lighthouse@13.3.0`, `axe-core@4.12.0`
- VERIFIED via node: axe-core `wcag22aa` tag covers only `target-size` rule; no `focus-not-obscured` rule exists in 4.12; `wcag21aa` covers 6 rules; vaul 1.1.2 exports Root/NestedRoot/Content/Overlay/Trigger/Portal/Handle/Close/Title/Description

### Secondary (MEDIUM confidence)
- CITED: Context7 /microsoft/playwright.dev — `storageState` auth pattern, multi-project config, axe fixture pattern, `withTags()` API
- CITED: Context7 /emilkowalski/vaul — `Drawer.Root`, `snapPoints`, `direction` prop API
- CITED: `lhci --help` output (0.15.1) — `collect` / `assert` / `--startServerCommand` options

### Tertiary (LOW confidence)
- ASSUMED: 48×48px minimum tap target (beyond WCAG 2.2 minimum); see Assumptions Log A1

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified via npm view + installed module inspection
- Architecture: HIGH — based on ground-truth codebase read of all referenced files
- Pitfalls: HIGH — most are drawn from direct code inspection (animation sites, auth pattern, scrollWidth)
- Motion audit: HIGH — all 7 identified call sites inspected in source

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (30 days — Playwright and axe-core release frequently but breaking changes are unlikely)
