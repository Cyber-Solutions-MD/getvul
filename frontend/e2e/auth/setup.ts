// Prereq: docker-compose up -d postgres redis backend frontend must be running.
// The backend must have the default admin created via backend/create_admin.py:
//   admin@getvul.local / Admin123!
//
// This setup project logs in via the login form, waits for the /dashboard redirect,
// then saves the full context storageState (including localStorage getvul_token) to
// e2e/.auth/state.json. All authed Playwright projects use this file via storageState.
// The state.json is gitignored (T-15-01) — never committed.
//
// Override credentials via env vars in CI:
//   E2E_EMAIL=<email> E2E_PASSWORD=<password> npx playwright test

import { test as setup } from '@playwright/test';
import path from 'path';

const authFile = path.join(__dirname, '../.auth/state.json');

setup('authenticate', async ({ page }) => {
  // Navigate to login page — triggers client-side auth guard on /dashboard routes
  await page.goto('/login');

  // Fill login form — selectors match frontend/src/app/login/page.tsx
  await page.fill('input[type="email"]', process.env.E2E_EMAIL ?? 'admin@getvul.local');
  await page.fill('input[type="password"]', process.env.E2E_PASSWORD ?? 'Admin123!');
  await page.click('button[type="submit"]');

  // Wait for redirect to /dashboard — confirms login succeeded and
  // getvul_token was written to localStorage by useAuth()
  await page.waitForURL('**/dashboard');

  // Persist localStorage (getvul_token) + cookies to storageState
  // Playwright captures both cookies and localStorage — the JWT is included
  await page.context().storageState({ path: authFile });
});
