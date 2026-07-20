---
phase: 19-add-connector-wizard
plan: 04
subsystem: testing
tags: [playwright, axe-core, a11y, vitest, connectors, wizard, vaul, bundle-budget]

# Dependency graph
requires:
  - phase: 19-03
    provides: "AddConnectorWizard assembled + wired into connectors/page.tsx (add→wizard, edit→ConnectorForm), data-add-connector e2e hooks"
provides:
  - "connector-wizard-a11y.spec.ts — e2e axe sweep of the OPEN wizard dialog in both themes + mobile vaul render check (closes the pre-existing closed-grid-only coverage gap RESEARCH flagged)"
  - "Full phase-gate evidence: unit (35/35), lint (clean), build (156 kB connectors route), bundle budget (16/16 PASS), e2e (both themes, wizard open+closed)"
affects: ["gsd-verify-work"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Isolate a single route from a shared multi-route axe-sweep test via an ad-hoc diagnostic spec when the shared test bails at an earlier-array-order failing route, without modifying the shared spec"

key-files:
  created:
    - frontend/e2e/connector-wizard-a11y.spec.ts
  modified: []

key-decisions:
  - "next/dynamic({ssr:false}) NOT applied to the wizard — /dashboard/connectors measured 156 kB First-Load JS (baseline 153 kB, +3 kB delta from the wizard), well inside the 250 KB budget with 94 kB headroom remaining. Static imports kept as-is (RESEARCH Pitfall 3 recommendation)."
  - "A pre-existing, unrelated color-contrast failure on /dashboard/vulnerabilities (light theme, severity-High badge, last touched Phase 11) was discovered during the full-gate e2e run. Logged to 19-add-connector-wizard/deferred-items.md per SCOPE BOUNDARY rather than fixed — it is not caused by, and does not block, this phase's UX-D-02-06 requirement. Verified /dashboard/connectors itself IS axe-clean in light theme via an isolated diagnostic run (the shared a11y-routes.spec.ts light-theme test throws on the first failing route in STATIC_ROUTES array order, which is vulnerabilities, before it ever reaches connectors)."

requirements-completed: [UX-D-02-06]  # Task 3 human-verify checkpoint APPROVED by user 2026-07-20

# Metrics
duration: 56min (Tasks 1-2); Task 3 human-verify approved 2026-07-20
completed: 2026-07-20
---

# Phase 19 Plan 04: Quality Gate (UX-D-02-06) Summary — COMPLETE

**Added the missing open-wizard e2e axe coverage (dark + light + mobile vaul) and ran the full phase gate against a live local stack (Postgres/Redis/backend in Docker, frontend prod build on :3000): unit 35/35, lint clean, build 156 kB (`/dashboard/connectors`, +3 kB over the 153 kB baseline), bundle budget 16/16 routes PASS, and the e2e axe sweep green in both themes for the wizard-open and wizard-closed states — no `next/dynamic` needed. Task 3 (human-verify checkpoint) is outstanding; this plan is NOT complete.**

## Performance

- **Duration:** 56 min (Tasks 1–2; Task 3 checkpoint not started)
- **Started:** 2026-07-20T13:53:25+03:00 (previous plan's completion commit)
- **Completed:** N/A — checkpoint pending
- **Tasks:** 2/3 completed (Task 3 is a `checkpoint:human-verify` gate, intentionally not auto-approved)
- **Files modified:** 1 created (`connector-wizard-a11y.spec.ts`), 1 created (`deferred-items.md`, documentation only)

## Accomplishments
- `frontend/e2e/connector-wizard-a11y.spec.ts` — 3 new blocking e2e tests: open-wizard axe sweep in dark theme, open-wizard axe sweep in light theme (mirrors `a11y-routes.spec.ts`'s `getvul_theme` localStorage-forcing pattern), and a 390×844 mobile-viewport check that the wizard's `nav[aria-label="Wizard progress"]` stepper renders inside the vaul bottom sheet without hiding the persistent `nav[aria-label="Mobile navigation"]` bottom-nav — plus a third axe run in that mobile state. All 3 pass with zero critical/serious violations.
- Brought up a live local stack to produce genuine (not fabricated) gate evidence: `docker compose up -d postgres redis backend`, seeded `admin@getvul.local` / `Admin123!`, built the frontend with `NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build`, served it via `npm run start` on :3000 (backend CORS allowlists exactly this origin in debug mode).
- Full gate evidence (see below) confirms UX-D-02-06's three technical claims — axe both themes, ≤250 KB, vaul mobile render — are all satisfied by automation. The remaining, genuinely-manual claims (focus/SR announcement feel, reduced-motion, dismissal feel) are deferred to Task 3's human-verify checkpoint, which this plan explicitly does NOT self-approve.
- Discovered and correctly triaged a pre-existing, out-of-scope axe failure on `/dashboard/vulnerabilities` (light theme) that predates this phase by 8 phases (Phase 11) — logged to `deferred-items.md`, not fixed, per the SCOPE BOUNDARY rule. Verified via an isolated diagnostic (created, run, then deleted — not part of the committed deliverable) that `/dashboard/connectors` itself is unaffected and axe-clean in light theme.

## Task Commits

Each completed task was committed atomically:

1. **Task 1: E2E spec — axe-sweep the OPEN wizard in both themes + mobile render** - `d8c9fd9` (test)
2. **Task 2: Full gate run with pasted evidence** - `c44c6c3` (docs — `deferred-items.md`; no source changes were needed since bundle/build/lint/unit were all already green)

**Task 3 (checkpoint:human-verify):** APPROVED by user on 2026-07-20 — manual sign-off on desktop/mobile happy path, test gate (D-05/D-07), re-test invalidation (D-08), focus/SR announcement, reduced-motion, dismissal (D-13), and edit-unchanged (D-11). No issues reported.

## Files Created/Modified
- `frontend/e2e/connector-wizard-a11y.spec.ts` — new e2e spec: open-wizard axe sweep (dark + light) + mobile vaul render/axe check
- `.planning/phases/19-add-connector-wizard/deferred-items.md` — logs the pre-existing, out-of-scope `/dashboard/vulnerabilities` light-theme contrast failure (documentation only, no source fix)

## Gate Evidence (pasted, not paraphrased)

### 1. Unit suite — `npm test -- src/components/connectors --run`
```
 Test Files  9 passed (9)
      Tests  35 passed (35)
   Duration  1.37s (transform 685ms, setup 2.12s, import 1.37s, tests 567ms, environment 3.95s)
```
(One benign jsdom console error from axe-core's internal `HTMLCanvasElement.getContext` probe during a component a11y test — not a test failure, pre-existing jsdom limitation, all 9 files / 35 tests still passed.)

### 2. Lint — `npm run lint`
Exits 0. Only pre-existing warnings in unrelated files (`dashboard/users/page.tsx`, `change-password/page.tsx`, `login/page.tsx` ×3, `lib/auth.tsx`) — none touched by this phase, none new.

### 3. Build — `NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build`
```
Route (app)                                 Size  First Load JS
├ ƒ /dashboard/connectors                14.2 kB         156 kB
```
`/dashboard/connectors` First-Load JS = **156 kB** (was 153 kB per 19-RESEARCH.md baseline — the wizard added **+3 kB**, well inside the 97 kB headroom RESEARCH measured).

### 4. Bundle budget — `npm run perf:budget`
```
PASS  /dashboard/connectors  156.0 kB
...
Routes checked: 16
Largest route:  /dashboard/tickets  167.0 kB
Budget:         250 kB gzipped per route (First Load JS)
check-bundle-all: OK — all 16 routes within 250 kB budget.
```
`next/dynamic` was **NOT needed** — confirmed per RESEARCH Pitfall 3's recommendation (static imports, measure first).

### 5. E2E — `npm run test:e2e -- a11y-routes connector-wizard-a11y` (both themes, closed grid + open wizard)
```
✓  [chromium-a11y] connector-wizard-a11y.spec.ts › dark theme … open wizard reports zero critical/serious axe violations (dark) (664ms)
✓  [chromium-a11y] connector-wizard-a11y.spec.ts › light theme … open wizard reports zero critical/serious axe violations (light) (702ms)
✓  [chromium-a11y] connector-wizard-a11y.spec.ts › mobile vaul sheet render … zero critical/serious axe (614ms)
✓  [chromium-a11y] a11y-routes.spec.ts › WCAG 2.1 AA axe sweep — all routes (blocking) › sweeps all routes … (5.7s)
✘  [chromium-a11y] a11y-routes.spec.ts › WCAG 2.1 AA axe sweep — light theme (blocking) › sweeps all routes … in light mode
     Error: Zero critical/serious axe violations (light) on /dashboard/vulnerabilities
     [serious] color-contrast … "text-severity-high" #ea580c on #f7f2ea, ratio 3.19 (needs 4.5:1), 5 nodes
✓  [chromium-a11y] a11y-routes.spec.ts › tickets board view (dark)
✓  [chromium-a11y] a11y-routes.spec.ts › tickets board view (light)
✓  [chromium-a11y] a11y-routes.spec.ts › Bottom-nav visibility … 360px
✓  [chromium-a11y] a11y-routes.spec.ts › clicking "More" button …

9 passed, 1 failed (out of 10)
```
**All 3 new `connector-wizard-a11y.spec.ts` tests pass** (dark, light, mobile-vaul — the actual UX-D-02-06 deliverable). The 1 failure is the **pre-existing, unrelated** `/dashboard/vulnerabilities` light-theme contrast issue (see `deferred-items.md`) — NOT introduced by this phase, and NOT `/dashboard/connectors`. Because the shared light-theme test iterates `STATIC_ROUTES` in array order and throws on the first failure (`/dashboard/vulnerabilities` precedes `/dashboard/connectors` in the array), the shared test never independently re-confirms connectors' light-theme cleanliness in this exact run — so an isolated one-off diagnostic (written, run, and deleted; not part of the committed deliverable) was used to confirm `/dashboard/connectors` (closed grid) is axe-clean in light theme (0 violations). Combined with the new spec's own light-theme open-wizard test (also 0 violations), UX-D-02-06's "both themes" claim for `/dashboard/connectors` — both open and closed — is genuinely, not paraphrastically, verified.

**Overall command exit code:** 1 (due to the one pre-existing, out-of-scope failure above). This is disclosed rather than suppressed, per the gate_environment_notes instruction not to claim a sweep passed that did not actually run clean.

## Decisions Made
- Kept the wizard on static imports (no `next/dynamic`) — the 156 kB measurement (94 kB headroom) doesn't justify the added loading-flash/focus-landing complexity inside an already-open dialog that dynamic-import would introduce (RESEARCH Pitfall 3).
- Logged rather than fixed the pre-existing `/dashboard/vulnerabilities` light-theme contrast failure — out of this phase's file/route blast radius (Phase 11 code, unrelated to connectors/wizard), consistent with the SCOPE BOUNDARY rule and the v2.0 closeout notes' already-acknowledged light-theme WCAG debt.

## Deviations from Plan

None affecting the plan's own deliverable — the e2e spec and gate evidence were produced exactly as specified. One out-of-scope discovery (see above) was logged, not fixed, per the SCOPE BOUNDARY rule (not a Rule 1-3 auto-fix, since the affected file/route is untouched by any Phase 19 wave).

## Issues Encountered
- No local dev stack was running at session start — stood one up from scratch (`docker compose up -d postgres redis backend`, seeded the `admin@getvul.local` test user per project memory, built+served the frontend on :3000) specifically so the gate evidence pasted above reflects a real run, not a fabricated one (per `gate_environment_notes` and the project's "Axe sweep not run during execution" memory item).
- `next start` printed an advisory warning that it "does not work with output: standalone configuration" — verified empirically that it still serves correctly (curl 200s on `/login`, `/dashboard/connectors`, and a `_next/static` chunk) since `.next/static` is unaffected by the standalone server-bundling optimization; no functional impact on the gate run.

## User Setup Required
None — the docker-compose stack and admin seed used here are local-only, test-run infrastructure, not a permanent user-facing configuration change.

## Next Phase Readiness

**This plan is COMPLETE.** Task 3's `checkpoint:human-verify` gate — covering the genuinely-manual claims automation cannot assert: focus/SR announcement on step change (including inside the vaul mobile sheet — the RESEARCH Assumption A3 new precedent), `prefers-reduced-motion` behavior (stepper fill instant, spinner static), the D-08 re-test invalidation feel, and D-13 dismissal feel (backdrop no-op, X/Esc immediate, bottom-nav undisturbed) — was **APPROVED by the user on 2026-07-20 with no issues reported**. UX-D-02-06 is fully satisfied (automated gate + human sign-off).

STATE.md/ROADMAP.md/REQUIREMENTS.md updates and phase completion are orchestrator-owned and handled after this SUMMARY is finalized.

---
*Phase: 19-add-connector-wizard*
*Completed: 2026-07-20 — Task 3 human-verify checkpoint APPROVED*

## Self-Check: PASSED

- FOUND: frontend/e2e/connector-wizard-a11y.spec.ts
- FOUND: .planning/phases/19-add-connector-wizard/deferred-items.md
- FOUND commit: d8c9fd9
- FOUND commit: c44c6c3
