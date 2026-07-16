---
phase: 17
slug: page-transition-motion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-16
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `17-RESEARCH.md` §Validation Architecture. Motion/a11y claims on this
> milestone have historically gone unverified (see getvul memory: axe sweep never run
> during execution) — this phase requires REAL automated assertions, not claims.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright 1.61.1 (`@playwright/test`) |
| **Config file** | `frontend/e2e/playwright.config.ts` |
| **Quick run command** | `npx playwright test e2e/reduced-motion.spec.ts --project=chromium-a11y` |
| **Full suite command** | `npx playwright test --project=chromium-a11y --project=chromium-smoke --project=webkit-smoke --project=firefox-smoke` |
| **Estimated runtime** | ~60–120 seconds (full suite, all projects) |
| **Prerequisite** | Prod build running on `:3000` (admin user, :3000 CORS, kill next-server children — see getvul local-e2e memory) |

---

## Sampling Rate

- **After every task commit:** Run `npx playwright test e2e/reduced-motion.spec.ts --project=chromium-a11y`
- **After every plan wave:** Run `npx playwright test --project=chromium-a11y` (full a11y sweep + new transition spec)
- **Before `/gsd-verify-work`:** Full suite green across all 4 projects
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 0 | UX-D-06-01 | — | N/A (no attack surface) | e2e | `npx playwright test e2e/page-transitions.spec.ts --project=chromium-a11y` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 0 | UX-D-06-02 | — | N/A | e2e | `npx playwright test e2e/reduced-motion.spec.ts --project=chromium-a11y` | ✅ (EXTEND) | ⬜ pending |
| 17-02-01 | 02 | 1 | UX-D-06-01 | — | N/A | e2e | `npx playwright test e2e/page-transitions.spec.ts --project=chromium-a11y` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 1 | UX-D-06-02 | — | N/A | e2e | `npx playwright test e2e/reduced-motion.spec.ts --project=chromium-a11y` | ✅ (EXTEND) | ⬜ pending |
| 17-02-03 | 02 | 1 | UX-D-06-03 | — | N/A (no jank in Firefox fallback) | e2e | `npx playwright test e2e/smoke.spec.ts --project=firefox-smoke` | ✅ (VERIFY covers nav) | ⬜ pending |
| 17-02-04 | 02 | 1 | UX-D-06-05 | — | N/A | bundle | `npx next build 2>&1 \| grep "First Load JS"` | ✅ CI | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are indicative — planner assigns final IDs/waves. What matters: no 3 consecutive tasks without an automated verify.*

---

## Wave 0 Requirements

- [ ] `frontend/e2e/page-transitions.spec.ts` — NEW spec covering UX-D-06-01 (cross-fade fires on a real pathname change; searchParams change does NOT fade). Use the proxy/timing + pseudo-element detection approach from RESEARCH §Detailed Test Specifications.
- [ ] `frontend/e2e/reduced-motion.spec.ts` — EXTEND with a VT-pseudo-element suppression test for UX-D-06-02 (the existing spec only checks `.bg-gradient-mesh` / `.bg-severity-critical`; it does NOT cover `::view-transition-*`).

*No new test infrastructure needed — existing Playwright config, projects, and fixtures are sufficient.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visible ~320ms content cross-fade; chrome static | UX-D-06-01 / D-05 | Perceptual "feel" + chrome-stillness not reliably assertable via Playwright | Navigate Dashboard → Vulnerabilities → Assets. Confirm a visible ~320ms cross-fade of the content area while sidebar + topbar stay perfectly still. |
| DrillPanel Esc/clickaway does NOT fade; cross-route nav fades panel with content | UX-D-06-04 / D-11 | Cannot assert "a fade did NOT fire" reliably in e2e (searchParams change) | Open a Vuln DrillPanel, press Esc → confirm NO fade. Navigate to a different route with panel open → confirm panel fades WITH content. |
| Firefox fallback: gentle fade-in, no jank/broken paint | UX-D-06-03 | Perceptual jank/paint-break judgment | Open app in Firefox, navigate between routes. Confirm gentle CSS-keyframe fade-in, no jank, no broken paint. |
| No layout shift (chrome does not flicker/shift) | UX-D-06-04 | CLS is a Lighthouse metric, not a Playwright assertion | Navigate between routes watching sidebar + topbar — must not flicker, fade, or shift position. (Lighthouse CLS = 0 in the perf gate.) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers both MISSING references (new `page-transitions.spec.ts` + extended `reduced-motion.spec.ts`)
- [ ] No watch-mode flags in any command
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
