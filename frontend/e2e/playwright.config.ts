import { defineConfig, devices } from '@playwright/test';

// Audited viewport widths for Phase 15 quality gate:
// 360 (small Android), 390 (iPhone 14 Pro), 768 (tablet/iPad), 1280 (desktop)
// These are iterated per-test in viewport-scroll.spec.ts via test.use({ viewport }).
// Do NOT bake them into project-level `use.viewport` here.

export default defineConfig({
  testDir: '.',

  reporter: [['list'], ['html', { open: 'never' }]],

  use: {
    // Base URL so specs can use relative navigation (page.goto('/login'))
    baseURL: 'http://localhost:3000',
    // Audit the shipping PRIMARY theme (dark, sunset palette). Light-theme visual
    // QA — including light-mode WCAG contrast — is the explicitly deferred UX-D-03
    // polish pass (see 15-CONTEXT.md "Deferred Ideas"). Theme-bootstrap specs
    // override colorScheme per-test to assert both modes resolve correctly.
    colorScheme: 'dark',
    // Collect traces on retry for debugging
    trace: 'on-first-retry',
  },

  projects: [
    // Auth setup project — runs once, captures localStorage JWT to .auth/state.json
    {
      name: 'setup',
      testMatch: /auth\/setup\.ts/,
    },

    // Full viewport + axe sweep — Chromium only (for a11y-routes and viewport-scroll specs)
    {
      name: 'chromium-a11y',
      use: {
        ...devices['Desktop Chrome'],
        colorScheme: 'dark',
        storageState: 'e2e/.auth/state.json',
      },
      dependencies: ['setup'],
    },

    // Cross-browser smoke tests — 3 engines
    {
      name: 'chromium-smoke',
      use: {
        ...devices['Desktop Chrome'],
        colorScheme: 'dark',
        storageState: 'e2e/.auth/state.json',
      },
      testMatch: /smoke\.spec\.ts/,
      dependencies: ['setup'],
    },
    {
      name: 'webkit-smoke',
      use: {
        ...devices['Desktop Safari'],
        colorScheme: 'dark',
        storageState: 'e2e/.auth/state.json',
      },
      testMatch: /smoke\.spec\.ts/,
      dependencies: ['setup'],
    },
    {
      name: 'firefox-smoke',
      use: {
        ...devices['Desktop Firefox'],
        colorScheme: 'dark',
        // Firefox in Playwright does not honor colorScheme emulation for
        // prefers-color-scheme unless the OS-dark signal is forced via this pref.
        // Per-test emulateMedia({ colorScheme: 'light' }) still overrides it.
        launchOptions: { firefoxUserPrefs: { 'ui.systemUsesDarkTheme': 1 } },
        storageState: 'e2e/.auth/state.json',
      },
      testMatch: /smoke\.spec\.ts/,
      dependencies: ['setup'],
    },
  ],
});
