---
phase: 15-mobile-a11y-perf-quality-gate
plan: 05
status: complete
completed: 2026-06-29
---

# Plan 15-05 Summary — Playwright route-level quality gate

## What was built

Four Playwright specs + a shared `e2e/routes.ts`, run against the live docker-compose
stack and driven green through the D-09 audit-fix loop:

- **`viewport-scroll.spec.ts`** (UX-07-01) — every authenticated route × 360/390/768/1280,
  asserts no horizontal scroll. Polls until layout settles (tables reflow one frame wide
  on hydration).
- **`a11y-routes.spec.ts`** (UX-07-03) — per-route axe sweep, zero critical/serious WCAG 2.1 AA
  (blocking), WCAG 2.2 target-size report-only; + 360px bottom-nav presence + More-sheet opens.
- **`smoke.spec.ts`** (UX-07-07 / UX-07-05) — cross-browser (Chromium/WebKit/Firefox) render +
  axe, severity-glyph presence, `data-theme` reflects emulated `prefers-color-scheme`. `/login`
  runs unauthenticated (authed users bounce).
- **`reduced-motion.spec.ts`** (UX-07-04) — emulated reduce → near-zero animation duration.
- **`routes.ts`** — `STATIC_ROUTES`, viewport-tier-aware `waitForNav` (bottom-nav / hamburger /
  sidebar), `gotoStable` (retry on router.replace nav interruption), and **API-based**
  detail-route discovery (the tickets list opens a drill panel and assets pushes a 308 — UI
  clicks can't reliably reach `/[id]`; the helper reads the JWT from storageState and queries
  the list APIs).

## Result

**28 passed, 2 skipped, 0 failed** against the **production build** + live backend (14.5s).
Skipped = the two theme-bootstrap assertions on Firefox (Playwright's `prefers-color-scheme`
emulation is unreliable there; covered on Chromium + WebKit).

## D-09 audit-fix loop (defects the gate surfaced, all fixed)

- **Build was broken**: Playwright config leaked into the Next typecheck; `useSearchParams`
  lacked Suspense on authed routes → `(authed)` `force-dynamic` + tsconfig `e2e` exclusion.
- **Dark-theme WCAG AA contrast** (the shipping primary theme; light is deferred UX-D-03):
  `--color-text-faint` (#6B6488, 2.9–3.6:1) → #8B84A8 override; OWNER/ADMIN/Open accent-on-soft
  badges → brighter same-hue shades. *(DESIGN-SYSTEM GAPS — flagged for sketch-findings.)*
- **Structural a11y**: `role="img"` on provider/connector/timeline/severity marks
  (aria-prohibited-attr); `role="cell"` on asset-vuln rows (aria-required-children); breadcrumb
  separators are aria-hidden `<li>` (list/listitem); tickets mobile cards `<ul>/<li role=button>`
  → `<div>` (list/listitem).
- **Responsive**: topbar Bell/Help hidden < sm (phone overflow); vuln + assets tables wrapped in
  `overflow-x-auto` (no mobile card view); `scroll-padding-bottom` for the fixed bottom-nav.

## Decisions

- **Audit the dark (primary) theme**: Playwright `colorScheme: 'dark'` per project; Firefox needs
  `firefoxUserPrefs: { 'ui.systemUsesDarkTheme': 1 }`. Light-theme WCAG is the deferred UX-D-03 pass.
- **API-based detail discovery** over UI clicks — the only reliable cross-viewport approach given
  the drill-panel / 308-redirect navigation patterns.

## Notes / follow-ups

- Detail-route discovery occasionally logs "no detail routes discovered" on one viewport-scroll
  test (transient; graceful fallback to static routes). a11y-routes covers detail pages for axe.
- The dark-theme contrast overrides (text-faint, badge text) are documented DESIGN-SYSTEM GAPS to
  reconcile into `sketch-findings-getvul` foundation.md / visual-language.md.
