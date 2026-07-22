---
phase: 22-kanban-wizard-test-coverage
plan: 02
subsystem: testing
tags: [e2e, a11y, axe, playwright, wizard, connectors]

# Dependency graph
requires:
  - phase: 19-add-connector-wizard
    provides: the AddConnectorWizard component tree (TestStep/ConfirmStep/useWizardState) and the original connector-wizard-a11y.spec.ts (open-dialog-only coverage)
provides:
  - "Test step" axe sweep (loader/success/error x dark/light) in connector-wizard-a11y.spec.ts, driven via page.route() mocks of POST /connectors/test
  - "Confirm step" axe sweep (permission/sync review + submit-error x dark/light), driven via page.route() mocks of POST /connectors/test (pass) and POST /connectors (500)
  - a reusable ElementHandle-based `waitForDisabled()` pattern for asserting brief mutation-pending UI states without racing getByRole's accessibility-tree recompute cost
affects: [22-kanban-wizard-test-coverage (this phase's own coverage-closure milestone), future wizard e2e specs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "page.route() mocking of POST /connectors/test and POST /connectors to drive wizard steps deterministically (no real outbound provider call, no DB row created) — extends the tickets-kanban.spec.ts:117 precedent"
    - "ElementHandle + expect.poll() for asserting a DOM property directly, bypassing getByRole's per-query accessibility-tree recompute when the state window is short-lived"

key-files:
  created: []
  modified:
    - frontend/e2e/connector-wizard-a11y.spec.ts

key-decisions:
  - "getByRole()-based polling for `disabled` state is unreliable on this machine (accessibility-tree recompute can take 500-800ms per query, longer than a mutation's pending window) — fixed by capturing an ElementHandle once and polling the raw DOM property"
  - "Shared driveToTestStep/driveToConfirmStep/sweepBlocking/waitForDisabled helpers factored once and reused across Test-step and Confirm-step blocks rather than duplicating the filter+assert pattern inline per test"
  - "GET /connectors/types deliberately left unmocked in both new blocks — the Confirm permission list sweeps real backend metadata"

patterns-established:
  - "Pattern: when asserting a mutation's transient pending/disabled UI in Playwright, prefer an ElementHandle + expect.poll() over a getByRole locator re-resolved on every retry"

requirements-completed: [UX-D-02-06]

# Metrics
duration: ~55min
completed: 2026-07-22
---

# Phase 22 Plan 02: Wizard Test-step + Confirm-step Axe Coverage Summary

**Extended `connector-wizard-a11y.spec.ts` from a single open-dialog-only axe sweep to full coverage of the wizard's Test step (loader/success/error) and Confirm step (permission/sync review + submit-error), in both themes, all driven deterministically via `page.route()` mocks — closing the Phase-19 coverage warning with a live-verified, 14/14-passing prod-build run.**

## Performance

- **Duration:** ~55 min (includes a live debugging investigation into a genuine test-authoring flakiness bug, not a production defect)
- **Completed:** 2026-07-22
- **Tasks:** 3/3
- **Files modified:** 1 (`frontend/e2e/connector-wizard-a11y.spec.ts`)

## Accomplishments

- Added a "Test step" describe block: fills every rendered credential input (provider-agnostic), advances to the Test step, and mocks `POST /api/v1/connectors/test` to sweep the loader (button disabled), success (`role="status"`), and error (`role="alert"`) states — 6 tests (3 states x 2 themes), all 0 serious/critical axe violations.
- Added a "Confirm step" describe block: mocks a passing test result to reach Confirm, sweeps the permission/sync review (rendered against **real** `GET /connectors/types` metadata, never mocked) and a submit-error state (`POST /api/v1/connectors` mocked to 500) — 4 tests (2 states x 2 themes), all 0 serious/critical axe violations.
- Ran the **full** `connector-wizard-a11y.spec.ts` (all 4 describe blocks, including the pre-existing Credentials-step and mobile-vaul sweeps) live against a real production build: 14/14 passed, 0 failed.
- Confirmed `/dashboard/connectors` stays at 156 kB First Load JS (unchanged, well under the 250 kB budget) — no production code was touched.

## Task Commits

1. **Task 1: Add "Test step" axe sweep (loader/success/error x dark/light)** - `a33eccc` (test)
2. **Task 2: Add "Confirm step" axe sweep (permissions/sync/submit-error x dark/light)** - `d2d3287` (test)
3. **Task 3: Live prod-build gate run of the full wizard a11y spec + pasted evidence** - no additional commit (verification-only task; evidence below)

_Note: this plan is test-authoring only; Task 3 produced live evidence but no further code changes to commit._

## Files Created/Modified

- `frontend/e2e/connector-wizard-a11y.spec.ts` - Added `driveToTestStep`/`driveToConfirmStep`/`sweepBlocking`/`assertLightTheme`/`useLightThemeInit`/`waitForDisabled` shared helpers, a "Test step" describe block (6 tests), and a "Confirm step" describe block (4 tests). No production source files modified.

## Decisions Made

- Reused a single `sweepBlocking()` helper (blocking-filter + diagnostic log + labeled `toHaveLength(0)` assertion) across all 10 new tests rather than duplicating the ~15-line pattern inline per test, matching the existing spec's filter logic exactly while keeping the file DRY.
- `GET /connectors/types` is never mocked in either new block — the Confirm step's "Required access" permission list renders true backend metadata, per the plan's explicit requirement.
- The submit-error mock (`POST /api/v1/connectors` → 500) is registered only after `driveToConfirmStep()` completes, immediately before the CTA click, to avoid any risk of it incidentally intercepting an earlier `GET /api/v1/connectors` list fetch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test-step loader assertion needed an ElementHandle-based check instead of the plan's literal `getByRole(...).toBeDisabled()` snippet**
- **Found during:** Task 1 (live Playwright run)
- **Issue:** The plan's interface snippet suggested clicking "Test connection" then `await expect(button).toBeDisabled()` against a `page.getByRole('button', {...})` locator, with a ~400ms mocked delay. Live runs against this environment consistently failed with "Received: enabled" even though the network request was demonstrably still in flight (confirmed via request/response timing logs: response arrived ~400ms after the request, exactly matching the mock's artificial delay). Root cause, confirmed via targeted instrumentation of `test-step.tsx`'s `testMutation.isPending`/`status` transitions (temporarily added, then fully reverted — no production diff remains): `getByRole()` locators recompute the page's full accessibility tree on every re-resolution, which took roughly 500-800ms per query in this environment — slower than the ~400ms window the mutation stays pending. Each retry attempt effectively "skipped over" the transient disabled state because resolving the locator itself consumed more wall time than the state lasted.
- **Fix:** Added a `waitForDisabled(locator, expected, timeout)` helper that captures a Playwright `ElementHandle` **once** (a single accessibility query) and then polls the `disabled` DOM property directly via `elementHandle.evaluate()` inside `expect.poll()` — no further accessibility-tree cost per retry. This is a pure test-authoring fix; `test-step.tsx` (the production component) was never actually changed in the final diff (confirmed via `git diff --stat` showing zero production files touched).
- **Files modified:** `frontend/e2e/connector-wizard-a11y.spec.ts` only.
- **Verification:** Both loader tests (dark + light) now pass reliably and quickly (~800-870ms each, well within a single test run), confirmed across three independent full-suite runs (Task 1 isolated run, Task 2 combined run, Task 3 full-spec run) with 0 flakes observed.
- **Committed in:** `a33eccc` (Task 1 commit).

---

**Total deviations:** 1 auto-fixed (1 blocking/test-flakiness fix)
**Impact on plan:** Test-authoring fix only — no change to what's being asserted (0 critical/serious axe violations while the mutation is genuinely pending), no production code touched, no scope creep. The investigation confirmed `test-step.tsx`'s mutation-pending lifecycle behaves correctly (`isPending` flips true synchronously at `mutate()` and stays true for the full network round-trip) — the bug was purely in how the *test* observed that state.

## Issues Encountered

During the loader-test investigation, a live debugging session (temporary `console.log` instrumentation added to both the spec and `test-step.tsx`) was required to distinguish "environment-driven test flakiness" from "a genuine isPending bug in production." The instrumentation proved the production behavior was correct (isPending held true for the full ~400ms mocked network delay, matching request/response timestamps exactly) and was fully reverted before the final commit — `git diff --stat` against `test-step.tsx` shows zero changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `connector-wizard-a11y.spec.ts` now covers all three in-dialog wizard steps (Credentials, Test, Confirm) plus the mobile-vaul render check, in both themes — the Phase-19 coverage warning (UX-D-02-06) is closed with live-verified evidence, not merely authored tests.
- No blockers. This closes the last queued item in the 22-kanban-wizard-test-coverage phase's plan set (22-01 kanban CR-01/WR-02 coverage was already complete; 22-02 closes the wizard side).

## Live Evidence (Task 3)

### Full spec run — `npx playwright test e2e/connector-wizard-a11y.spec.ts --config=e2e/playwright.config.ts --project=chromium-a11y` (unedited transcript)

```
npm notice run getvul-frontend@0.1.0 npx
npm notice run 'playwright' test e2e/connector-wizard-a11y.spec.ts --config=e2e/playwright.config.ts --project=chromium-a11y

Running 14 tests using 1 worker

  ✓   1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (655ms)
  ✓   2 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:24:7 › Add-connector wizard — axe sweep (open dialog), dark theme (blocking) › open wizard reports zero critical/serious axe violations (dark) (685ms)
  ✓   3 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:71:7 › Add-connector wizard — axe sweep (open dialog), light theme (blocking) › open wizard reports zero critical/serious axe violations (light) (652ms)
  ✓   4 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:120:7 › Add-connector wizard — mobile vaul sheet render (blocking) › wizard renders in the vaul sheet; bottom-nav stays visible; zero critical/serious axe (603ms)
  ✓   5 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:301:9 › Add-connector wizard — Test step axe sweep (both themes, blocking) › dark theme › test-connection loader reports zero critical/serious axe violations (dark) (822ms)
  ✓   6 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:328:9 › Add-connector wizard — Test step axe sweep (both themes, blocking) › dark theme › test-connection success reports zero critical/serious axe violations (dark) (771ms)
  ✓   7 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:349:9 › Add-connector wizard — Test step axe sweep (both themes, blocking) › dark theme › test-connection error reports zero critical/serious axe violations (dark) (726ms)
  ✓   8 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:374:9 › Add-connector wizard — Test step axe sweep (both themes, blocking) › light theme › test-connection loader reports zero critical/serious axe violations (light) (834ms)
  ✓   9 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:399:9 › Add-connector wizard — Test step axe sweep (both themes, blocking) › light theme › test-connection success reports zero critical/serious axe violations (light) (749ms)
  ✓  10 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:420:9 › Add-connector wizard — Test step axe sweep (both themes, blocking) › light theme › test-connection error reports zero critical/serious axe violations (light) (695ms)
  ✓  11 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:446:9 › Add-connector wizard — Confirm step axe sweep (both themes, blocking) › dark theme › confirm step permission/sync review reports zero critical/serious axe violations (dark) (755ms)
  ✓  12 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:454:9 › Add-connector wizard — Confirm step axe sweep (both themes, blocking) › dark theme › confirm step submit-error reports zero critical/serious axe violations (dark) (826ms)
  ✓  13 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:477:9 › Add-connector wizard — Confirm step axe sweep (both themes, blocking) › light theme › confirm step permission/sync review reports zero critical/serious axe violations (light) (795ms)
  ✓  14 [chromium-a11y] › e2e/connector-wizard-a11y.spec.ts:485:9 › Add-connector wizard — Confirm step axe sweep (both themes, blocking) › light theme › confirm step submit-error reports zero critical/serious axe violations (light) (851ms)

  14 passed (11.4s)
```

Environment: Docker backend healthy on :8000 (postgres+redis+backend), production frontend build (`npm run build && npm run start`) served on :3000, admin@getvul.local seeded. Both the Test-step and Confirm-step tests ran (not skipped) in both dark and light themes, as required.

### Bundle budget — `npm run perf:budget` (unedited transcript)

```
npm notice run getvul-frontend@0.1.0 perf:budget
npm notice run node scripts/check-bundle-all.mjs
npm notice run getvul-frontend@0.1.0 npx
npm notice run 'next' build
PASS  /  102.0 kB
PASS  /_not-found  103.0 kB
PASS  /change-password  143.0 kB
PASS  /dashboard  138.0 kB
PASS  /dashboard/assets  130.0 kB
PASS  /dashboard/assets/[id]  161.0 kB
PASS  /dashboard/connectors  156.0 kB
PASS  /dashboard/cspm  157.0 kB
PASS  /dashboard/settings  156.0 kB
PASS  /dashboard/tickets  167.0 kB
PASS  /dashboard/tickets/[id]  138.0 kB
PASS  /dashboard/tickets/rules  126.0 kB
PASS  /dashboard/users  129.0 kB
PASS  /dashboard/vulnerabilities  158.0 kB
PASS  /dev/primitives  102.0 kB
PASS  /login  146.0 kB

Routes checked: 16
Largest route:  /dashboard/tickets  167.0 kB
Budget:         250 kB gzipped per route (First Load JS)

check-bundle-all: OK — all 16 routes within 250 kB budget.
```

`/dashboard/connectors` = **156.0 kB**, unchanged from before this plan, well under the 250 kB budget.

The production server on :3000 was stopped after this run (port freed).

---
*Phase: 22-kanban-wizard-test-coverage*
*Completed: 2026-07-22*

## Self-Check: PASSED

- FOUND: frontend/e2e/connector-wizard-a11y.spec.ts
- FOUND: .planning/phases/22-kanban-wizard-test-coverage/22-02-SUMMARY.md
- FOUND commit: a33eccc (Task 1)
- FOUND commit: d2d3287 (Task 2)

---

## Gap-closure addendum (2026-07-22, commit fcf9d25)

Phase verification (`22-VERIFICATION.md`) re-ran the full spec 5× and found the original single-run "14 passed" transcript above reflected one lucky run of a gate that was **not deterministically green**. Two full-suite-only flakes surfaced, both fixed **test-only** (zero production diff, confirmed via `git diff --stat` = 1 file, +43 lines):

1. **Confirm-step submit-error (dark) axe flake (~40% under full-suite load).** The mocked 500 fires a global error Toast (`ToastProvider` portal, `role="alert"`, `transition-all duration-200`) that axe sometimes sampled mid-fade, reading a false serious `color-contrast` violation (3.58:1) even though the toast's settled contrast is ~7.65:1 (AA-compliant). **Fix:** a `waitForToastSettled(page)` helper that polls the toast's computed `opacity` to `1` before `sweepBlocking()` in both submit-error tests (dark + light) — deterministic, not a fixed timeout.

2. **Launch-page click stall (~18%): `[data-add-connector]` click 30s timeout.** The connectors page gates `[data-add-connector]` behind `connectorsQuery.isPending → SkeletonTable` (connectors/page.tsx:208). Under Playwright's default parallel workers all hammering the one Docker backend, the real `GET /api/v1/connectors` list query occasionally stalled past the 30s action timeout, leaving the CTA unrendered. **Fix:** `driveToTestStep` now stubs the LIST query (`GET /api/v1/connectors`) to `[]` (read-only, NOT a swept surface; the add CTA still renders from the REAL types query). `GET /connectors/types` stays real (Confirm permissions); `POST /connectors` is left to each test's own 500 handler via `route.fallback()`.

**Determinism evidence — 10/10 full-suite reruns, 0 failed** (post-fix, against the same prod build; spec-only change requires no rebuild):

```
Run 1: PASS ->   14 passed (11.9s)
Run 2: PASS ->   14 passed (11.8s)
Run 3: PASS ->   14 passed (11.8s)
Run 4: PASS ->   14 passed (11.8s)
Run 5: PASS ->   14 passed (11.7s)
Run 6: PASS ->   14 passed (11.7s)
Run 7: PASS ->   14 passed (11.9s)
Run 8: PASS ->   14 passed (11.8s)
Run 9: PASS ->   14 passed (11.8s)
Run 10: PASS ->  14 passed (11.8s)
======================================
FINAL: 10 passed-runs / 0 failed-runs (out of 10)
```

The pre-fix 41s stall runs are gone (all runs now ~11.8s). `/dashboard/connectors` bundle unaffected (156 kB — no production source changed).
