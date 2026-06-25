import { defineConfig, devices } from '@playwright/test';

// Audited viewport widths for Phase 15 quality gate:
// 360 (small Android), 390 (iPhone 14 Pro), 768 (tablet/iPad), 1280 (desktop)
// These are iterated per-test in viewport-scroll.spec.ts via test.use({ viewport }).
// Do NOT bake them into project-level `use.viewport` here.

export default defineConfig({
  testDir: '.',
  baseURL: 'http://localhost:3000',

  reporter: [['list'], ['html', { open: 'never' }]],

  use: {
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
        storageState: 'e2e/.auth/state.json',
      },
      dependencies: ['setup'],
    },

    // Cross-browser smoke tests — 3 engines
    {
      name: 'chromium-smoke',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/state.json',
      },
      testMatch: /smoke\.spec\.ts/,
      dependencies: ['setup'],
    },
    {
      name: 'webkit-smoke',
      use: {
        ...devices['Desktop Safari'],
        storageState: 'e2e/.auth/state.json',
      },
      testMatch: /smoke\.spec\.ts/,
      dependencies: ['setup'],
    },
    {
      name: 'firefox-smoke',
      use: {
        ...devices['Desktop Firefox'],
        storageState: 'e2e/.auth/state.json',
      },
      testMatch: /smoke\.spec\.ts/,
      dependencies: ['setup'],
    },
  ],
});
