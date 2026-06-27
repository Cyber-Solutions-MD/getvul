---
phase: 15-mobile-a11y-perf-quality-gate
plan: 06
status: partial — stopped at Task 3 (human checkpoint)
tasks_complete: 2/3
---

# Phase 15 Plan 06 — Execution Progress

> Plan 06 executes Tasks 1 and 2 headlessly (no live build/server needed).
> Task 3 is a blocking human-verify checkpoint: it requires `next build` and a
> live Docker stack, which cannot run headlessly. This file documents what was
> created and the exact commands for Task 3.

---

## Tasks Executed

### Task 1: check-bundle-all.mjs (all-routes <=250 KB budget)

**Commit:** `5b2b1ab` — `feat(15-06): add check-bundle-all.mjs all-routes 250 KB budget gate`

**File created:** `frontend/scripts/check-bundle-all.mjs`

**What it does:**
- Reads `next build` output from stdin (piped) or runs `npx next build` directly
- Strips ANSI, splits into lines, finds every route line (path starts with `/`, skips "shared by all" footer)
- Reuses `check-bundle.mjs` internals: `stripAnsi`, the tightened size-token regex `/(?<![A-Za-z])(\d+(?:\.\d+)?)\s*(kB|MB|B)\b/g`, LAST-token = First Load JS heuristic, 1024 multiplier
- `MAX_KB = 250`, `MAX_BYTES = 250 * 1024 = 256000 bytes`
- Prints `PASS|FAIL  <route>  <kB>` per route; summary footer with total checked, largest route, budget
- Exit 0 all within budget; exit 1 any route over 250 KB; exit 2 on build failure or zero routes parsed

**Fixture verify results (all passed):**

| Fixture | Expected exit | Actual | Status |
|---------|--------------|--------|--------|
| stdin: route with 999 kB (over budget) | 1 | 1 | OVER_BUDGET_FAILS_OK |
| stdin: all routes under 250 kB | 0 | 0 | UNDER_BUDGET_PASSES_OK |
| stdin: empty (zero routes) | 2 | 2 | EMPTY_EXITS_2_OK |

---

### Task 2: lhci.config.js + 15-PERF-REPORT.md + 15-HUMAN-UAT.md

**Commit:** `17e4111` — `feat(15-06): add lhci.config.js, 15-PERF-REPORT.md, and 15-HUMAN-UAT.md`

**Files created:**

1. **`frontend/lhci.config.js`** — Lighthouse CI config (CommonJS `module.exports`):
   - `ci.collect`: numberOfRuns=1, startServerCommand='npm run start', startServerReadyPattern='ready'
   - URLs: `http://localhost:3000/login` and `http://localhost:3000/dashboard`
   - settings: preset='perf', formFactor='mobile', throttling={rttMs:150, throughputKbps:1600, cpuSlowdownMultiplier:4}
   - `ci.assert.assertions`: `categories:performance` and `categories:accessibility` both `['error', {minScore: 0.9}]`
   - `ci.upload`: target='filesystem', outputDir='./lighthouse-results' (gitignored per Plan 01)

2. **`.planning/phases/15-mobile-a11y-perf-quality-gate/15-PERF-REPORT.md`** — Committed SC#6 artifact:
   - Header with run-date/commit placeholder
   - Bundle Budget table: 14 routes (/, /login, /dashboard, /dashboard/vulnerabilities, /dashboard/assets, /dashboard/assets/[id], /dashboard/tickets, /dashboard/tickets/[id], /dashboard/tickets/rules, /dashboard/cspm, /dashboard/connectors, /dashboard/users, /dashboard/settings, /dev/primitives), all cells `(pending)`
   - Lighthouse Mobile section: /login + /dashboard rows for Performance + Accessibility scores, all cells `(pending)`
   - Verification sign-off checklist

3. **`.planning/phases/15-mobile-a11y-perf-quality-gate/15-HUMAN-UAT.md`** — Three manual verifications with Pass/Fail slots:
   - Item 1: Severity glyphs (■ ▲ ◆ ○ □) legible at 14px in real Safari.app (UX-07-07 / D-02)
   - Item 2: Focus-not-obscured by fixed bottom-nav at <768px (UX-07-03 / WCAG 2.4.11)
   - Item 3: No white flash on cold dark-OS /login load (UX-07-05 / D-10)

**Headless verify results:** `node -c lhci.config.js` exits 0; `grep -q "categories:performance"`, `grep -q "minScore"`, `grep -q "0.9"` all pass; `grep -q "Lighthouse"` and `grep -q "250"` in PERF-REPORT pass; `grep -q "Safari"` in HUMAN-UAT passes. Verify prints `OK`.

---

## Task 3 — HUMAN CHECKPOINT (blocking)

Task 3 requires a live Next.js build and Docker stack. The agent stopped here per instructions.

### Step 1: Bundle budget check

```bash
# From the project root:
cd frontend && npm run perf:budget
```

This runs `next build` then pipes output to `check-bundle-all.mjs`.

**Expected:** exit 0 (all 14 routes <= 250 KB). If any route fails, per D-09 fix it (code-split / trim) and re-run before filling the table.

Fill the "Bundle Budget" table in:
`.planning/phases/15-mobile-a11y-perf-quality-gate/15-PERF-REPORT.md`

---

### Step 2: Lighthouse mobile audit

```bash
# Start the full stack first (backend + Redis required for /dashboard auth):
docker-compose up -d

# OR let lhci manage the Next.js server lifecycle (lhci.config.js uses startServerCommand):
cd frontend && npm run perf:lh
```

**If using lhci's startServerCommand:** lhci will run `npm run start` (which requires a prior `npm run build`), wait for "ready" on stdout, then audit the two URLs. Ensure no server is already running on :3000.

**If pre-starting manually:**
```bash
cd frontend && npm run build && npm run start &
# wait until "ready on http://localhost:3000"
cd frontend && npm run perf:lh
```

**Expected:** >= 90 performance AND >= 90 accessibility on both /login and /dashboard. If below 90, per D-09 fix and re-run.

Fill the "Lighthouse Mobile" section in:
`.planning/phases/15-mobile-a11y-perf-quality-gate/15-PERF-REPORT.md`

---

### Step 3: Manual UAT items

Complete all three items in:
`.planning/phases/15-mobile-a11y-perf-quality-gate/15-HUMAN-UAT.md`

1. Safari.app severity glyphs legible at 14px (UX-07-07)
2. Focus-not-obscured by bottom-nav at <768px (UX-07-03)
3. No white flash on cold dark-OS /login load (UX-07-05)

Each item has step-by-step instructions and a Pass/Fail/Notes slot.

---

### Step 4: Confirm completion

After all three steps:

- `15-PERF-REPORT.md` must have NO remaining `(pending)` cells
- `15-HUMAN-UAT.md` must have all three items marked Pass (or Fail with notes for backend-deferred)
- No credentials or JWT pasted into either file

Then type `"approved"` to resume the GSD agent for phase 15 completion.

---

## Threat Model Notes

- **T-15-11:** `15-PERF-REPORT.md` is committed — record only route names, byte sizes, Lighthouse scores. No credentials or JWT.
- **T-15-12:** `lighthouse-results/` raw JSON is gitignored (Plan 01). Do not commit it.
