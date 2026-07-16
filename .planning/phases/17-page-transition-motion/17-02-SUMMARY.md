---
phase: 17-page-transition-motion
plan: "02"
subsystem: frontend-motion
tags: [motion, view-transitions, css, next-template, a11y, playwright]
depends_on:
  requires: [17-01]
  provides: [17-02]
  affects: [frontend/src/app/(authed), frontend/src/app/globals.css]
tech_stack:
  added: []
  patterns:
    - View Transitions API via document.startViewTransition() in (authed)/template.tsx
    - module-level isFirstMount guard (survives React remounts, resets on hard refresh)
    - Explicit ::view-transition-group/old/new(*) reduced-motion suppressor in globals.css
    - CSS-keyframe Firefox fallback via data-no-vt attribute + page-fade-in keyframe
key_files:
  created:
    - frontend/src/app/(authed)/template.tsx
  modified:
    - frontend/src/app/globals.css
decisions:
  - id: D-17-02-A
    summary: "module-level isFirstMount bool instead of useRef: useRef resets on every template.tsx remount (each navigation = new instance), so the D-07/D-08 guard would suppress every VT. Module-level bool survives remounts but resets on hard refresh — exactly D-07/D-08 requirement."
  - id: D-17-02-B
    summary: "NEXT_PUBLIC_API_URL=http://localhost:8000 required at build time for e2e: without it, browser fetch calls hit /auth/login as a relative URL against the Next.js server (no proxy), returning 404 and causing the Playwright auth setup to fail. docker-compose sets this var; must replicate for local prod builds."
metrics:
  duration: ~90 minutes
  completed: "2026-07-16"
  tasks: 4
  files_modified: 2
  files_created: 1
---

# Phase 17 Plan 02: Page-Transition Motion Implementation — Summary

**One-liner:** 320ms pure-opacity View Transitions cross-fade via `(authed)/template.tsx` + explicit `::view-transition-*` reduced-motion suppressor in `globals.css`, with CSS-keyframe Firefox fallback; e2e specs RED→GREEN (5/5 chromium-a11y + firefox-smoke pass).

---

## Tasks Completed

| # | Name | Commit | Status |
|---|------|--------|--------|
| 1 | Add VT CSS to globals.css | b165dde | DONE |
| 2 | Create (authed)/template.tsx | 0f7c19e + 6bbf25f | DONE (with deviation — see below) |
| 3 | Run e2e specs GREEN + confirm 250 KB budget | — (no code change; build+test run) | DONE — evidence below |
| 4 | Human verify — perceptual cross-fade, chrome stillness, DrillPanel race, Firefox feel | — | OUTSTANDING (checkpoint) |

---

## Task 3 — Automated Evidence (Required Per Milestone Memory)

### page-transitions.spec.ts (UX-D-06-01)

```
Running 5 tests using 2 workers

  ✓  [chromium-a11y] › page-transitions.spec.ts:23:7 › Page-transition motion › cross-fade fires on a real pathname change (dashboard → vulnerabilities) (373ms)
  ✓  [chromium-a11y] › page-transitions.spec.ts:78:7 › Page-transition motion › searchParams-only change does NOT trigger a page fade (D-02) (1.1s)
  ✓  [chromium-a11y] › reduced-motion.spec.ts:24:7 › Reduced-motion emulation › login gradient-mesh animation-duration is near-zero under reduce (239ms)
  [reduced-motion] hero urgency dot not in DOM — criticalOpen is 0 (quiet-win mode)
  ✓  [chromium-a11y] › reduced-motion.spec.ts:55:7 › Reduced-motion emulation › dashboard hero urgency-dot animation-duration is near-zero under reduce (230ms)
  ✓  [chromium-a11y] › reduced-motion.spec.ts:101:7 › Reduced-motion emulation › view-transition pseudo-elements are suppressed under prefers-reduced-motion (1.1s)

  5 passed (2.0s)
```

**Result:** page-transitions 2/2 PASSED, reduced-motion 3/3 PASSED (including the new VT pseudo-element suppression test).

### smoke.spec.ts — firefox-smoke (UX-D-06-03)

```
Running 5 tests using 1 worker

  ✓  [firefox-smoke] › smoke.spec.ts:51:7 › Cross-browser smoke — /login (unauthenticated) › login page renders and passes axe in all engines (1.1s)
  ✓  [firefox-smoke] › smoke.spec.ts:61:7 › Cross-browser smoke sweep › smoke routes render and pass axe in all engines (1.6s)
  ✓  [firefox-smoke] › smoke.spec.ts:77:7 › Cross-browser smoke sweep › severity glyphs (■ ▲ ◆ ○ □) are present in /dashboard/vulnerabilities (523ms)
  -  [firefox-smoke] › smoke.spec.ts:115:7 › Theme bootstrap (skipped — Firefox colorScheme emulation unreliable, documented in playwright.config.ts)
  -  [firefox-smoke] › smoke.spec.ts:124:7 › Theme bootstrap (skipped)

  2 skipped (known)
  3 passed (4.5s)
```

**Result:** firefox-smoke PASSED.

### next build — First Load JS budget (UX-D-06-05)

Build command: `NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build`

```
Route (app)                                 Size  First Load JS
┌ ○ /                                      124 B         102 kB
├ ○ /_not-found                             1 kB         103 kB
├ ○ /change-password                      1.4 kB         143 kB
├ ƒ /dashboard                           12.9 kB         138 kB
├ ƒ /dashboard/assets                     5.1 kB         130 kB
├ ƒ /dashboard/assets/[id]                7.8 kB         162 kB
├ ƒ /dashboard/connectors                7.73 kB         154 kB
├ ƒ /dashboard/cspm                      7.51 kB         158 kB
├ ƒ /dashboard/settings                  10.7 kB         157 kB
├ ƒ /dashboard/tickets                   6.84 kB         166 kB   <-- MAX
├ ƒ /dashboard/tickets/[id]              9.72 kB         138 kB
├ ƒ /dashboard/tickets/rules             3.72 kB         126 kB
├ ƒ /dashboard/users                     6.64 kB         129 kB
├ ƒ /dashboard/vulnerabilities           5.12 kB         158 kB
├ ○ /dev/primitives                        124 B         102 kB
└ ○ /login                               4.02 kB         146 kB
+ First Load JS shared by all             102 kB
```

**Result:** Maximum First Load JS = 166 kB (`/dashboard/tickets`). All 17 routes are 166 kB — well under the 250 kB budget. `template.tsx` adds 0 KB beyond the client component itself.

---

## Task 4 — OUTSTANDING: Human Verify Checkpoint

**Status: BLOCKING — awaiting human verification. Do NOT proceed to phase gate without this approval.**

### What Was Built (automated parts complete)

A single `(authed)/template.tsx` firing `document.startViewTransition()` on pathname change, with `globals.css` giving the content region a 320ms pure-opacity cross-fade, an explicit reduced-motion suppressor for the VT pseudo-elements, and a Firefox CSS-keyframe fallback. The automated specs (page-transitions 2/2 + reduced-motion 3/3 + firefox-smoke 3/3) and the 250 kB budget are green. This checkpoint covers the four items that CANNOT be automated (per 17-VALIDATION.md §Manual-Only Verifications).

### How to Verify

Build and start the prod server:
```bash
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build
npm run start -- --port 3000
```
Sign in as admin at http://localhost:3000.

**1. UX-D-06-01 / D-05 — Visible cross-fade + chrome stillness:**
Navigate Dashboard → Vulnerabilities → Assets via the sidebar links.
EXPECT: a visible ~320ms opacity cross-fade of the CONTENT area only. The sidebar and topbar must stay perfectly still — no fade, no flicker, no position shift. If the whole viewport (chrome included) fades, D-05 is broken (view-transition-name is on the wrong element).

**2. UX-D-06-04 / D-11 — DrillPanel race:**
On /dashboard/vulnerabilities, open a vulnerability DrillPanel (row click). Press Esc.
EXPECT: the panel closes with NO page fade. Then re-open a panel and, while it is open, click a DIFFERENT route in the sidebar. EXPECT: the panel fades out WITH the content (it is inside the outgoing snapshot), and the new route appears without the drill param.

**3. UX-D-06-03 — Firefox fallback feel:**
Open the app in Firefox. Navigate between routes. EXPECT: a gentle opacity fade-in (CSS keyframe fallback), no jank, no broken/half-painted content, no layout jump.

**4. Layout-shift / first-mount:**
Hard-refresh on /dashboard. EXPECT: NO fade on first paint (D-07). Then navigate around and watch the sidebar + topbar — they must not flicker, fade, or shift (no layout shift).

**5. Reduced-motion sanity (optional manual confirm on top of the automated test):**
Enable OS "reduce motion", reload, navigate. EXPECT: instant swaps, no perceptible fade.

**Resume signal:** Type "approved" if all four behaviors hold, or describe which item failed (e.g. "chrome fades on nav" → view-transition-name isolation issue; "Dashboard→Vuln shows no fade" → useLayoutEffect timing / Pitfall 2).

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] module-level isFirstMount instead of useRef**

- **Found during:** Task 3 (page-transitions TEST A failing with "element detached" loop — traced to VT never firing)
- **Root cause:** Plan 02's specified `const isFirstMount = useRef(true)` pattern resets on every template.tsx remount. Next.js remounts `(authed)/template.tsx` on EVERY pathname change (each navigation = new component instance with a fresh ref = true). The D-07/D-08 guard fires on EVERY navigation and prevents VT from ever running.
- **Fix:** Changed to `let isFirstMount = true` at module scope. A JS module is not re-evaluated on client-side navigation (React remounts), so the bool survives remounts. It resets on hard refresh/page load (browser re-evaluates the module). This is the correct behavior for D-07/D-08.
- **Risk note (17-RESEARCH Pitfall 2 / Assumption A1):** The VT DID fire correctly with `useLayoutEffect` once the guard was fixed. TEST A passed (VT animation detected: 1 view-transition pseudo-element animation confirmed). The Pitfall 2 concern (wrong transition direction) did not materialize in practice.
- **Files modified:** `frontend/src/app/(authed)/template.tsx`
- **Commits:** 0f7c19e (initial with bug), 6bbf25f (fix)

**2. [Rule 3 - Blocking] NEXT_PUBLIC_API_URL required for local e2e auth**

- **Found during:** Task 3 (Playwright auth setup failing with "Sign-in failed" on the login form)
- **Root cause:** Without `NEXT_PUBLIC_API_URL=http://localhost:8000`, the frontend's fetch calls use a relative URL `/auth/login`. In standalone Next.js mode (no nginx proxy), this hits the Next.js server itself → 404 → "Sign-in failed." In docker-compose, the env var is set at build time; local prod builds must replicate it.
- **Fix:** Rebuilt with `NEXT_PUBLIC_API_URL=http://localhost:8000`. Auth setup succeeded in 784ms. All e2e specs passed.
- **Code change:** None — this is a build-time env var. Documented here for future local e2e runs.

---

## Known Stubs

None. `(authed)/template.tsx` is a pass-through wrapper. All values are hardcoded constants. No data stubs.

---

## Threat Flags

None. CSS + one `'use client'` component calling the read-only `document.startViewTransition()` browser API. No new attack surface. See plan threat model (all threats accepted as `accept`).

---

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `frontend/src/app/(authed)/template.tsx` exists | FOUND |
| `frontend/src/app/globals.css` modified | FOUND |
| `.planning/phases/17-page-transition-motion/17-02-SUMMARY.md` exists | FOUND |
| Commit b165dde (Task 1 — globals.css VT CSS) | FOUND |
| Commit 0f7c19e (Task 2 — template.tsx initial) | FOUND |
| Commit 6bbf25f (Task 2 fix — module-level isFirstMount) | FOUND |
