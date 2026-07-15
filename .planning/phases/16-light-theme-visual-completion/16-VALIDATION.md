---
phase: 16
slug: light-theme-visual-completion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-15
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 16-RESEARCH.md § Validation Architecture. Frontend-only (CSS tokens + one e2e
> harness change + two component literal fixes) — the backend-pytest DB hazard does not apply.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright `^1.61.1` + `@axe-core/playwright ^4.12.1` (e2e) · vitest `^4.1.6` (unit) |
| **Config file** | `frontend/e2e/playwright.config.ts` |
| **Quick run command** | `cd frontend && npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` (runs dark + light sweeps) |
| **Full suite command** | `cd frontend && npx playwright test && npx vitest run` |
| **Estimated runtime** | ~60s (a11y sweep both themes) · ~3 min (full Playwright + unit) |

**Server prerequisite:** e2e requires a running dev server + backend (`npm run dev` + `docker compose up backend db`).

---

## Sampling Rate

- **After every task commit:** `cd frontend && npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` (both themes)
- **After every plan wave:** Full suite — `npx playwright test && npx vitest run`
- **Before `/gsd-verify-work`:** Full Playwright suite green (a11y both themes + smoke + reduced-motion) + `npx vitest run` green
- **Max feedback latency:** ~60s per-task; ~180s per-wave

---

## Per-Task Verification Map

> Task IDs assigned by the planner. Every requirement below maps to an automated check;
> per-route light-mode visual fidelity + `/login` gradient-mesh are human-UAT (see Manual-Only).

| Req / Criterion | Behavior | Test Type | Automated Command | File Exists | Status |
|-----------------|----------|-----------|-------------------|-------------|--------|
| UX-D-03-01 | No dark-only borders/shadows/hover/disabled artifacts on light routes | axe structural + manual visual | `cd frontend && npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` (light describe) | ❌ W0 | ⬜ pending |
| UX-D-03-02 | WCAG 2.1 AA contrast in light mode (4.5:1 text, 3:1 UI) on every route | axe (`color-contrast`, wcag2aa) | `cd frontend && npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` (light describe) | ❌ W0 | ⬜ pending |
| UX-D-03-03 | Severity/status/SLA pills + glyphs legible + distinct on light surfaces | axe contrast + manual glyph distinctness | axe light sweep (glyph distinctness → Manual-Only) | ❌ W0 | ⬜ pending |
| UX-D-03-04 | `text-muted`/`text-faint`/disabled + `-on-soft` pass AA on light; reconciled into design system | axe + grep gate | `grep -nE "color-text-faint\|color-violet-on-soft" frontend/src/app/globals.css` (light override present) + axe light sweep | ❌ W0 | ⬜ pending |
| UX-D-03-05 | `e2e/a11y-routes.spec.ts` runs light AND dark, both green | e2e | `cd frontend && npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` | ❌ W0 | ⬜ pending |
| Component literals | `status-pill.tsx` / `profile-pane.tsx` use `var(--color-*-on-soft)`, not dark hex JIT literals | grep gate | `! grep -rnE "text-\[#(C4B5FD\|F472B6)\]" frontend/src/components` | ❌ W0 | ⬜ pending |
| Theme toggle enabled | Light radio in `user-chip.tsx` is no longer `disabled` | grep/unit | `! grep -n "disabled" frontend/src/components/shell/user-chip.tsx` (light radio) | ❌ W0 | ⬜ pending |
| Bundle budget | 0 First-Load-JS delta; all routes ≤250 KB | script | `cd frontend && node scripts/check-bundle-all.mjs` | ✅ | ⬜ pending |
| Dark regression | Existing dark-mode a11y + reduced-motion + smoke still green | e2e | `cd frontend && npx playwright test` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements (must exist before implementation waves are green)

- [ ] `frontend/e2e/a11y-routes.spec.ts` — add `test.describe` light-theme axe sweep (pre-seed `localStorage getvul_theme=light` via `page.addInitScript` + `data-theme="light"`); the file exists, needs the new block.
- [ ] `frontend/src/app/globals.css` — `:root[data-theme="light"]` gains the ~20 missing tokens (severity ×5, semantic states, shadows/glows, `-on-soft` text shades) so the axe light sweep can pass.
- [ ] Component literal fixes: `status-pill.tsx` + `profile-pane.tsx` → `text-[var(--color-*-on-soft)]`.
- [ ] `user-chip.tsx` — remove `disabled` from the Light radio after tokens+components are green.
- [ ] Design-system skill reconciliation — light-mode token values written into `foundation.md` + `visual-language.md` + `sources/themes/sunset.css` (BL-04 mirror for light mode).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Per-route light-mode visual fidelity (no dark-only artifact the eye catches that axe misses) | UX-D-03-01 | axe measures contrast/structure, not "looks right" | Toggle to Light, walk all ~15 authed routes, compare against the sketch design intent |
| Severity glyph distinctness at 14px on light surfaces | UX-D-03-03 | Glyph legibility is a human-eye judgment (cf. BL-06 for dark) | Toggle Light, open `/dashboard/vulnerabilities`, confirm ■ ▲ ◆ ○ □ distinct |
| `/login` gradient-mesh acceptable in light mode | UX-D-03-01 | Decorative gradient is out of axe scope | Toggle Light, load `/login`, confirm mesh reads acceptably |

---

## Validation Sign-Off

- [ ] Every requirement has an automated command OR maps to a Manual-Only row
- [ ] Light-mode axe sweep added and green; dark sweep still green (no regression)
- [ ] Component literals grep-gate clean; toggle enabled
- [ ] Bundle budget: 0 JS delta
- [ ] Design-system reconciliation committed (skill files updated)
- [ ] `nyquist_compliant: true` set after checker validates

**Approval:** pending checker pass
