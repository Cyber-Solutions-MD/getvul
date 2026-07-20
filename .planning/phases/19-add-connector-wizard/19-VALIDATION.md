---
phase: 19
slug: add-connector-wizard
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-20
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest (unit/component) + `vitest-axe` (component a11y) + Playwright `@axe-core/playwright` (e2e) |
| **Config file** | `frontend/vitest.config.mts` (unit) · `frontend/e2e/playwright.config.ts` (e2e) |
| **Quick run command** | `cd frontend && npm test -- <touched-file-glob> --run` |
| **Full suite command** | `cd frontend && npm test -- src/components/connectors --run && npm run lint && npm run build && npm run perf:budget && npm run test:e2e -- a11y-routes connector-wizard-a11y` |
| **Estimated runtime** | ~20s targeted Vitest · ~2–4 min full (build + e2e per the local e2e setup: prod build + server) |

---

## Sampling Rate

- **After every task commit:** Run the task's quick command (`npm test -- <file> --run`, or `npx tsc --noEmit` for pure UI/wiring tasks).
- **After every plan wave:** Run `npm test -- src/components/connectors --run` + `npm run lint` + `npm run build`.
- **Before `/gsd-verify-work`:** Full suite green, including `npm run perf:budget` (≤250 KB) and `npm run test:e2e` axe in BOTH themes (closed grid + open wizard).
- **Max feedback latency:** ~20s (targeted Vitest). E2E/bundle run at wave-merge + phase-gate only (heavier: prod build required).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-00-01 | 00 | 0 | UX-D-02-01 | — | N/A (copy) | static | `npx tsc --noEmit` (microcopy) + grep WIZARD_COPY | ✅ (creates) | ⬜ pending |
| 19-00-02 | 00 | 0 | UX-D-02-01, UX-D-02-02 | T-19-01 / T-19-02 | Untested/stale creds not advanceable; sentinel never in add body | unit (TDD) | `npm test -- use-wizard-state --run` | ❌ W0 (creates) | ⬜ pending |
| 19-00-03 | 00 | 0 | UX-D-02-01 | — | RED scaffolds define GREEN targets | unit (RED) | `npm test -- src/components/connectors/wizard/{credentials,confirm,add-connector}-* --run` (expect RED) | ❌ W0 (creates) | ⬜ pending |
| 19-01-01 | 01 | 1 | UX-D-02-02 | — | Stepper display-only, no false-interactive affordance | static+grep | `npx tsc --noEmit` + grep aria-current / no button | ❌ W0 → | ⬜ pending |
| 19-01-02 | 01 | 1 | UX-D-02-03 | T-19-02 / T-19-03 | No `••••••` in add path; secret fields masked | unit | `npm test -- credentials-step --run` | ❌ W0 → | ⬜ pending |
| 19-01-03 | 01 | 1 | UX-D-02-02, UX-D-02-05 | T-19-01 | Test fires only on explicit click (no auto-fire) | static+grep | `npx tsc --noEmit` + grep no useEffect+mutate | ❌ W0 → | ⬜ pending |
| 19-02-01 | 02 | 1 | UX-D-02-04, UX-D-02-05 | T-19-01 / T-19-02 | Scopes shown pre-submit; creds never rendered | unit | `npm test -- confirm-step --run` | ❌ W0 → | ⬜ pending |
| 19-02-02 | 02 | 1 | UX-D-02-04 | T-19-04 | Color-only; edit/sentinel path unchanged | unit | `npm test -- connector-form --run` | ✅ existing | ⬜ pending |
| 19-03-01 | 03 | 2 | UX-D-02-01, UX-D-02-02, UX-D-02-06 | T-19-01 | Next gated by real click-guard (not aria alone) | unit+a11y | `npm test -- add-connector-wizard --run` | ❌ W0 → | ⬜ pending |
| 19-03-02 | 03 | 2 | UX-D-02-01, UX-D-02-06 | T-19-05 | Edit path (D-11) + admin gating unchanged | static+lint | `npx tsc --noEmit` + `npm run lint` | ✅ existing | ⬜ pending |
| 19-04-01 | 04 | 3 | UX-D-02-06 | T-19-06 | Open-dialog axe clean, both themes | e2e | `npm run build && npm run test:e2e -- connector-wizard-a11y` | ❌ W0 (creates) | ⬜ pending |
| 19-04-02 | 04 | 3 | UX-D-02-06 | T-19-06 | ≤250 KB + axe both themes evidence | build+e2e | `npm run perf:budget && npm run test:e2e -- a11y-routes connector-wizard-a11y` | ✅ existing scripts | ⬜ pending |
| 19-04-03 | 04 | 3 | UX-D-02-06 | T-19-01 | Manual: D-08 invalidation, focus, reduced-motion, vaul, D-11/D-13 | manual | checkpoint:human-verify | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/components/connectors/wizard/use-wizard-state.ts` + `use-wizard-state.test.ts` — gating state machine + Pitfall-4 bounce (UX-D-02-01, UX-D-02-02)
- [ ] `frontend/src/components/connectors/wizard/credentials-step.test.tsx` — UX-D-02-03 RED target
- [ ] `frontend/src/components/connectors/wizard/confirm-step.test.tsx` — UX-D-02-04 RED target (incl. empty-permissions)
- [ ] `frontend/src/components/connectors/wizard/add-connector-wizard.test.tsx` — UX-D-02-01, UX-D-02-05 RED target
- [ ] `frontend/src/components/connectors/wizard/add-connector-wizard.a11y.test.tsx` — component-level vitest-axe RED target
- [ ] `frontend/src/components/connectors/microcopy.ts` — WIZARD_COPY strings
- No new test-framework install needed — Vitest, vitest-axe, Playwright, @axe-core/playwright all already configured (RESEARCH Environment Availability).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Focus moves to step heading + SR announces on step change, inside the vaul mobile sheet | UX-D-02-06 | RESEARCH Assumption A3 (MEDIUM): vaul's post-open focus behavior on internal content swap is not verifiable in jsdom; needs a real mobile-viewport + VoiceOver check | 19-04 checkpoint step 4 |
| Reduced-motion: stepper fill instant, spinner static | UX-D-02-06 | `prefers-reduced-motion` visual behavior not asserted by axe | 19-04 checkpoint step 5 |
| D-13 dismissal feel (backdrop no-op, X/Esc immediate, bottom-nav undisturbed) | UX-D-02-06 | Interaction feel; partially covered by existing ResponsiveDialog tests but the mobile bottom-nav interplay is visual | 19-04 checkpoint step 6 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or a Wave 0 dependency (manual checkpoint 19-04-03 is the only non-automated task and is explicitly listed above)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (5 test files + hook + copy)
- [x] No watch-mode flags (all Vitest runs use `--run`)
- [x] Feedback latency < 20s (targeted Vitest)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-20
