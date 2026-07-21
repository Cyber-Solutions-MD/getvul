---
phase: 21
slug: page-transition-verification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-21
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright (e2e) — existing |
| **Config file** | `frontend/e2e/playwright.config.ts` |
| **Quick run command** | `cd frontend && npx playwright test e2e/page-transitions.spec.ts` |
| **Full suite command** | `cd frontend && npx playwright test` (prod build + :3000 + admin login per memory `getvul-local-e2e-perf-gate`) |
| **Estimated runtime** | ~60–120 seconds (single spec); full e2e gate longer |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the touched spec
- **After every plan wave:** Run the full e2e suite (chromium + firefox projects)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 21-01-* | 01 | 1 | UX-D-06-01 | — / — | N/A (test hardening) | e2e | `npx playwright test e2e/page-transitions.spec.ts` | ✅ | ⬜ pending |
| 21-01-* | 01 | 1 | UX-D-06-04 | — / — | N/A (close-race guard) | e2e | `npx playwright test e2e/page-transitions.spec.ts` | ✅ | ⬜ pending |
| 21-01-* | 01 | 1 | UX-D-06-01 (Firefox fallback) | — / — | N/A | e2e (firefox project) | `npx playwright test --project=firefox e2e/page-transitions.spec.ts` | ✅ / ❌ (project testMatch must be broadened — see Pitfall 2) | ⬜ pending |
| 21-02-* | 02 | 2 | UX-D-06-03 | — / — | N/A (human sign-off) | manual (human-action checkpoint) | perceptual checklist recorded in `17-HUMAN-UAT.md` | ❌ W0 (authored this phase) | ⬜ pending |
| 21-02-* | 02 | 2 | UX-D-06-01..05 | — / — | N/A (doc closure) | goal-backward verify | `17-VERIFICATION.md` authored + evidence links | ❌ W0 (authored this phase) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing e2e infrastructure (`page-transitions.spec.ts` polling harness, Firefox project, reduced-motion.spec.ts) covers all automated phase requirements — no framework install needed.
- **Blocking prerequisite (not a test file):** the Firefox Playwright project's `testMatch` currently scopes to `smoke.spec.ts` only. The Firefox fallback assertion (D-04) will silently not run unless the project config is broadened or a dedicated project is added. This is a plan task, verified by observing the assertion actually execute under `--project=firefox`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cross-fade *feel* (snappy 220–320ms pure-opacity, no drift) | UX-D-06-03 | Perceptual — no automated proxy for "feel" | Stand up prod build, navigate between authed pages, confirm smooth opacity cross-fade |
| Chrome stillness (sidebar/topbar do not move/fade on route change) | UX-D-06-03 | Perceptual | Watch persistent chrome during a pathname change |
| DrillPanel-during-transition (open drill fades out cleanly, no stuck/ghost panel) | UX-D-06-03 | Perceptual | Open a DrillPanel, navigate to a new pathname, watch the fade |
| Firefox CSS-fallback *feel* (equivalent cross-fade under keyframe path) | UX-D-06-03 | Perceptual | Repeat the above in Firefox |

*Recorded in `17-HUMAN-UAT.md` as a `human-action` checkpoint (autonomous: false).*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or documented manual checkpoint
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (Firefox testMatch prerequisite)
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
