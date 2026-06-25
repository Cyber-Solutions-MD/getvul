---
phase: 15-mobile-a11y-perf-quality-gate
plan: "01"
subsystem: frontend/e2e
tags: [playwright, axe-core, eslint, a11y, testing, infrastructure]
dependency_graph:
  requires: []
  provides:
    - frontend/e2e/playwright.config.ts (Playwright config — 5 projects, 4 viewport widths documented)
    - frontend/e2e/auth/setup.ts (auth storageState setup project)
    - frontend/e2e/fixtures/auth.ts (thin test/expect re-export)
    - frontend/e2e/fixtures/axe.ts (blocking + report-only axe WCAG factory fixtures)
    - frontend/.eslintrc.json (jsx-a11y rules at error level)
    - frontend/.gitignore (protects JWT credential and test artifacts)
  affects:
    - All Phase 15 plans (15-02..15-06) that require the e2e harness and eslint config
tech_stack:
  added:
    - "@playwright/test ^1.61.1 — E2E browser automation"
    - "@axe-core/playwright ^4.12.1 — WCAG axe injection for Playwright"
    - "@lhci/cli ^0.15.1 — Lighthouse CI scripted runner"
    - "Chromium 1228, Firefox 1532, WebKit 2311 — browser binaries via playwright install"
  patterns:
    - "Playwright multi-project config with setup dependency chain"
    - "localStorage JWT auth via storageState capture (Pattern 3 from RESEARCH.md)"
    - "axe.extend fixture with separate blocking/report-only WCAG tag sets (D-03)"
    - "ESLint legacy config (.eslintrc.json) extending next/core-web-vitals"
key_files:
  created:
    - frontend/e2e/playwright.config.ts
    - frontend/e2e/auth/setup.ts
    - frontend/e2e/fixtures/auth.ts
    - frontend/e2e/fixtures/axe.ts
    - frontend/e2e/.auth/.gitkeep
    - frontend/.gitignore
    - frontend/.eslintrc.json
  modified:
    - frontend/package.json (added @playwright/test, @axe-core/playwright, @lhci/cli; added test:e2e, perf:budget, perf:lh scripts)
    - frontend/package-lock.json
decisions:
  - "Used --legacy-peer-deps for npm install: lucide-react 0.383.0 declares peer react@^18 but project uses React 19; this is a known pre-existing condition in the project's devDep install pattern"
  - "Playwright 1.61.1 installed (plan specified ~1.60; 1.61.1 is a compatible minor bump, no API changes)"
  - "@axe-core/playwright 4.12.1 installed (plan specified ~4.11; 4.12.1 is a compatible minor bump)"
  - "auth/setup.ts uses testMatch: /auth\\/setup\\.ts/ not testMatch: /.*\\.setup\\.ts/ — avoids accidentally matching .setup.ts files from other directories"
  - "Viewport widths (360/390/768/1280) documented as comment in config, not baked into project use.viewport per plan instruction"
  - "No violations fixed in .eslintrc.json task — Plan 04 owns all jsx-a11y lint fix work (D-09)"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-25"
  tasks_completed: 3
  files_created: 7
  files_modified: 2
---

# Phase 15 Plan 01: Playwright + ESLint Infrastructure Summary

Installed the full Phase 15 quality-gate harness from scratch: @playwright/test + @axe-core/playwright + @lhci/cli devDependencies + 3 browser engines (Chromium/WebKit/Firefox), Playwright config (5 projects with storageState auth), localStorage JWT auth capture setup fixture, WCAG-split axe factories (blocking wcag2a/2aa/21aa + report-only wcag22aa per D-03), and .eslintrc.json elevating jsx-a11y to error level for Plan 04's violation sweep.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Install Playwright + axe + Lighthouse CLI | 994ead6 | frontend/package.json, frontend/package-lock.json |
| 2 | Create Playwright config + auth + axe fixtures + gitignore | 4301ca1 | frontend/e2e/playwright.config.ts, frontend/e2e/auth/setup.ts, frontend/e2e/fixtures/auth.ts, frontend/e2e/fixtures/axe.ts, frontend/e2e/.auth/.gitkeep, frontend/.gitignore |
| 3 | Create .eslintrc.json elevating jsx-a11y to error | a318e3e | frontend/.eslintrc.json |

## Verification Results

- `npx playwright --version` → Version 1.61.1 (exit 0)
- `npx playwright test --list --config=e2e/playwright.config.ts` → lists `[setup] › auth/setup.ts:18:6 › authenticate`; 5 project names defined in config (setup, chromium-a11y, chromium-smoke, webkit-smoke, firefox-smoke)
- `git check-ignore frontend/e2e/.auth/state.json` → returns path (JWT credential is gitignored — T-15-01 mitigated)
- `npx eslint --print-config src/app/layout.tsx` → `jsx-a11y/alt-text: ['error', ...]` (resolves at error level)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] npm install peer conflict on React 19**
- **Found during:** Task 1
- **Issue:** `lucide-react@0.383.0` declares peer `react@^18` but the project uses React 19. Standard `npm install` failed with ERESOLVE.
- **Fix:** Added `--legacy-peer-deps` flag. This is the established pattern for React 19 projects with packages that haven't updated peer declarations. The existing `overrides` in package.json (`picomatch`, `brace-expansion`) confirm this project already uses override strategies for peer conflicts.
- **Files modified:** No new files; install flag only.
- **Commit:** 994ead6

**2. [Rule 1 - Minor Version Resolution] Playwright 1.61.1 vs plan's ~1.60**
- **Found during:** Task 1
- **Issue:** npm resolved `@playwright/test` to 1.61.1 (plan specified ~1.60 as researched-current). The RESEARCH.md verified 1.60.0 on 2026-06-03; 1.61.1 is the current release.
- **Fix:** Accepted 1.61.1 — it is API-compatible, no breaking changes. Plan states "do not downgrade below" the researched version, so 1.61.1 satisfies the constraint.
- **Impact:** None — all Playwright APIs used (defineConfig, devices, test as setup, AxeBuilder) are stable across 1.60+.

## Known Stubs

None — this plan creates only tooling infrastructure (config files, devDependency installs). No UI components, no data wiring, no stubs.

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced. The plan's T-15-01/T-15-02/T-15-03 threats are all mitigated:
- T-15-01: `e2e/.auth/state.json` gitignored via `frontend/.gitignore` (verified by `git check-ignore`)
- T-15-02: Test credentials (`admin@getvul.local`) read from `process.env.E2E_EMAIL`/`E2E_PASSWORD` first; fallback is test-only dev admin, documented in code comment
- T-15-03: `test-results/`, `playwright-report/`, `blob-report/` all gitignored

## Self-Check: PASSED

Created files exist:
- frontend/e2e/playwright.config.ts: FOUND
- frontend/e2e/auth/setup.ts: FOUND
- frontend/e2e/fixtures/auth.ts: FOUND
- frontend/e2e/fixtures/axe.ts: FOUND
- frontend/e2e/.auth/.gitkeep: FOUND
- frontend/.gitignore: FOUND
- frontend/.eslintrc.json: FOUND

Commits exist:
- 994ead6 (Task 1 — install): FOUND
- 4301ca1 (Task 2 — config + fixtures): FOUND
- a318e3e (Task 3 — eslint): FOUND
