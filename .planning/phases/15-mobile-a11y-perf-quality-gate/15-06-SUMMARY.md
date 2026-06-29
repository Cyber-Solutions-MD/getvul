---
phase: 15-mobile-a11y-perf-quality-gate
plan: 06
status: complete
completed: 2026-06-29
---

# Plan 15-06 Summary — Performance gate + verification artifacts

## What was built

- **`frontend/scripts/check-bundle-all.mjs`** — parses every route from one `next build`, asserts
  each route's First Load JS ≤ 250 KB; exits 1 over budget, 2 on parse-miss, 0 within budget.
- **`frontend/lhci.config.js`** — Lighthouse CI mobile preset, asserts ≥0.9 performance AND
  ≥0.9 accessibility on `/login` + `/dashboard`.
- **`15-PERF-REPORT.md`** — committed verification artifact (SC #6), now filled.
- **`15-HUMAN-UAT.md`** — the three manual-only checks.

## Results (live docker-compose stack, production build)

**Bundle budget — ✅ PASS (15/15 routes).** Largest `/dashboard/tickets` 166 KB (84 KB headroom).
Build only went green after the D-09 build fixes (commit `addb572`).

**Lighthouse mobile — ✅ PASS (UX-07-06):**
| URL | Performance | Accessibility |
|-----|------------|---------------|
| `/login` | 97 | 95 |
| `/dashboard` (authenticated) | 90 | 95 |

`/dashboard` measured with a JWT injected into localStorage (CORS requires the app origin on :3000).

**Human UAT (2 of 3 automated-verified):**
- Item 2 — focus-not-obscured by bottom-nav: ✅ PASS. Scripted tab-through (105 focusables across
  3 long lists at 360px) → 0 obscured after adding `scroll-padding-bottom` (was 22/40 before).
- Item 3 — no white flash on cold dark-OS `/login`: ✅ PASS. `data-theme="dark"` pre-paint, body
  bg `rgb(14,11,26)`, FOUC bootstrap in `<head>`.
- Item 1 — Safari.app severity-glyph legibility @14px: ⏳ PENDING HUMAN (real Safari.app per D-02;
  the WebKit smoke project covers glyph presence + axe, but real-DPR legibility needs a human eye).

## Decisions

- Lighthouse `/dashboard` requires an authenticated session; ran via injected JWT + same-origin
  browser session rather than lhci's default unauthenticated collect.
- The Lighthouse accessibility category (axe-based) corroborates the per-route Playwright axe gate.

## Notes / follow-ups

- Only the curated scores are committed; raw Lighthouse output is gitignored (T-15-11/12).
- Remaining human task: Safari.app glyph spot-check (does not block the automated gate).
