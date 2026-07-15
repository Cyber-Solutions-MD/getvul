---
phase: 15
slug: mobile-a11y-perf-quality-gate
status: complete
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-03
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright (`@playwright/test`) route-level + `vitest` (existing, component-level) |
| **Config file** | none yet — Wave 0 installs `@playwright/test`, `@axe-core/playwright`, `@lhci/cli` and creates `playwright.config.ts` |
| **Quick run command** | `npx vitest run` (existing unit/component) |
| **Full suite command** | `npx playwright test` (route × viewport × axe sweep, 3 browser projects) |
| **Estimated runtime** | ~120–180 seconds (full Playwright sweep across 3 engines) |

---

## Sampling Rate

- **After every task commit:** Run `npx vitest run` (fast) and/or the targeted Playwright spec for the touched route
- **After every plan wave:** Run `npx playwright test` (full route sweep)
- **Before `/gsd-verify-work`:** Full Playwright suite green + Lighthouse ≥90/≥90 + bundle budget ≤250 KB on all routes
- **Max feedback latency:** ~180 seconds

---

## Per-Task Verification Map

> Populated by the planner from RESEARCH.md's Validation Architecture and the per-plan task lists.

> Reconciled 2026-07-15 (BL-05): the pre-execution single-row placeholder was expanded to the
> six shipped quality-gate checks (Playwright e2e specs + bundle budget + Lighthouse), each
> cross-referenced to its committed spec/config. e2e/perf commands are not re-run here (they
> need a live server); the spec + config files are verified present and green per 15-VERIFICATION.md.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 15-01 | 01 | 0 | UX-07-01..07 | — | Playwright + axe + jsx-a11y lint infrastructure | infra | `cd frontend && npx playwright --version && test -f e2e/playwright.config.ts` | ✅ | ✅ green |
| 15-05a | 05 | 4 | UX-07-01 | — | No horizontal scroll at 360/390/768/1280 | e2e | `cd frontend && npx playwright test e2e/viewport-scroll.spec.ts` | ✅ | ✅ green |
| 15-05b | 05 | 4 | UX-07-03 | — | axe WCAG 2.1 AA = 0 serious/critical across routes; bottom-nav @360px | e2e+axe | `cd frontend && npx playwright test e2e/a11y-routes.spec.ts` | ✅ | ✅ green |
| 15-03 | 03 | 2 | UX-07-04 | — | animation-duration ≤0.02s under prefers-reduced-motion | e2e | `cd frontend && npx playwright test e2e/reduced-motion.spec.ts` | ✅ | ✅ green |
| 15-05c | 05 | 4 | UX-07-07 | — | Cross-browser (Chromium/WebKit/Firefox) + theme + severity glyph DOM | e2e | `cd frontend && npx playwright test e2e/smoke.spec.ts` | ✅ | ✅ green |
| 15-06a | 06 | 5 | UX-07 perf | — | First-Load JS ≤250 KB on every route | script | `cd frontend && node scripts/check-bundle-all.mjs` | ✅ | ✅ green |
| 15-06b | 06 | 5 | UX-07 perf | — | Lighthouse mobile ≥90 perf / ≥90 a11y (/login, /dashboard) | perf | `cd frontend && npx lhci autorun --config=lhci.config.js` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `@playwright/test` + `@axe-core/playwright` + `@lhci/cli` installed; `npx playwright install` run
- [ ] `playwright.config.ts` — 3 browser projects (Chromium, WebKit, Firefox), 4 viewport widths (360/390/768/1280)
- [ ] `e2e/setup.ts` — auth storageState fixture (login via `POST /auth/login`, save `localStorage("getvul_token")` to `.auth/state.json`)
- [ ] `frontend/.eslintrc.json` — extends `next/core-web-vitals`, elevates jsx-a11y rules to `error`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Severity glyphs (■ ▲ ◆ ○ □) legible at 14px on real Safari DPR | UX-07-07 | Real-device rendering; WebKit-in-Playwright is a proxy only (D-02) | Open smoke routes in Safari.app, confirm glyphs legible; record in 15-HUMAN-UAT.md |
| Focus-not-obscured by fixed bottom-nav | UX-07-03 | axe-core 4.12 has no WCAG 2.4.11/2.4.12 rule (research finding #5) | Tab through phone-width screens, confirm focused element never hidden behind bottom-nav |
| No white flash on cold dark-OS `/login` load | UX-07-05 | FOUC is pre-hydration timing; not assertable in jsdom (D-10 verify-only) | DevTools → emulate dark OS → hard reload `/login`, observe no white flash |

*Refined during planning.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

## Validation Audit 2026-07-15 (BL-05)

The Per-Task Map shipped with a single infra-only row. Reconciled it to the six shipped
quality-gate checks (4 Playwright e2e specs + bundle-budget script + Lighthouse), each
cross-referenced to its committed spec/config and confirmed green in `15-VERIFICATION.md`.

| Metric | Count |
|--------|-------|
| Automated rows | 7 |
| Covered (green) | 7 |
| Gaps found | 0 |
| New tests written | 0 |
| Escalated to manual-only | 1 (Safari.app glyph legibility → BL-06, `15-HUMAN-UAT.md`) |

Evidence: 28/28 Playwright tests + 683/683 vitest green · 15/15 routes under 250 KB bundle
budget · Lighthouse /login 97/95, /dashboard 90/95 · 0 eslint errors. e2e/perf commands not
re-run in this audit (need a live server) — verified via committed specs + 15-PERF-REPORT.md.
**Nyquist-compliant** (one human-only glyph check tracked as BL-06).
