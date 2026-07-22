---
phase: 22
slug: kanban-wizard-test-coverage
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-22
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `22-RESEARCH.md` §Validation Architecture. This is a TEST-COVERAGE phase — the
> deliverables ARE tests, so the "tests" and the "artifacts" coincide; the arbiter is the live run.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright 1.61.x (e2e) |
| **Config file** | `frontend/e2e/playwright.config.ts` (projects: setup, chromium-a11y, chromium/webkit/firefox-smoke, firefox-transitions) |
| **Quick run command** | `cd frontend && npx playwright test e2e/tickets-kanban.spec.ts --config=e2e/playwright.config.ts --project=chromium-a11y` |
| **Full suite command** | `cd frontend && npx playwright test e2e/tickets-kanban.spec.ts e2e/connector-wizard-a11y.spec.ts --config=e2e/playwright.config.ts --project=chromium-a11y` |
| **Estimated runtime** | ~15-25 seconds (both specs, one worker) against a live prod build on :3000 |

> **Prerequisite (recurring anti-pattern guard):** every run above requires a PRODUCTION build + a running server on :3000 + backend on :8000 + admin login, per memory `getvul-local-e2e-perf-gate`. Authoring a spec is NOT evidence — only a live green run is.

---

## Sampling Rate

- **After every task commit:** Run the quick command for the spec touched by that task.
- **After every plan wave:** Run the full suite command above against a live prod build.
- **Before `/gsd-verify-work`:** Both specs green live (0 serious/critical axe violations; CR-01/WR-02 assertions pass).
- **Max feedback latency:** ~25 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 22-01-xx | 01 | 1 | UX-D-01-02 | — | Enter-key drag changes ticket status AND does NOT open the DrillPanel (CR-01); assert via real `page.keyboard.press('Enter')` + status column change + `[data-drill-panel]` count 0 | e2e | `npx playwright test e2e/tickets-kanban.spec.ts --config=e2e/playwright.config.ts --project=chromium-a11y` | ✅ (extends existing tickets-kanban.spec.ts) | ⬜ pending |
| 22-01-xx | 01 | 1 | UX-D-01-02 | — | A gated no-op drop announces the correct SR wording in `[id^="DndLiveRegion"]` (WR-02) — assert live-region text content, NOT `getByRole('status')` (collides with EmptyState) | e2e | same as above | ✅ | ⬜ pending |
| 22-02-xx | 02 | 1 | UX-D-02-06 | — | `connector-wizard-a11y.spec.ts` axe-sweeps the Test step (loader/success/error via `page.route()` mock) in dark + light — 0 serious/critical | e2e | `npx playwright test e2e/connector-wizard-a11y.spec.ts --config=e2e/playwright.config.ts --project=chromium-a11y` | ✅ (extends existing spec) | ⬜ pending |
| 22-02-xx | 02 | 1 | UX-D-02-06 | — | Same spec axe-sweeps the Confirm step (permission list / sync display against real `GET /connectors/types`; submit-error via mock) in dark + light — 0 serious/critical | e2e | same as above | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*(Exact task IDs assigned by the planner; the two plans are independent — different spec files, no shared production code — so they may run in the same wave.)*

---

## Wave 0 Requirements

- Existing infrastructure covers all phase requirements. Playwright is installed, `e2e/tickets-kanban.spec.ts` and `e2e/connector-wizard-a11y.spec.ts` already exist and pass; this phase EXTENDS them. No framework install, no new config, no RED scaffold plan needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

*All phase behaviors have automated verification. RESEARCH confirmed (against installed `@dnd-kit/core` v6.3.1 source) that CR-01 (Enter fires a trusted `preventDefault`) and WR-02 (live-region DOM text) are fully assertable by Playwright's keyboard driver — no VoiceOver/NVDA human pass is required, closing the Phase-18 "needs human sign-off" gap.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify (all e2e, run live against prod build)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (N/A — existing specs extended)
- [x] No watch-mode flags (Playwright runs are one-shot, not `--watch`)
- [x] Feedback latency < 25s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-22 (plan-checker VERIFICATION PASSED, iteration 2 — all 11 dimensions incl. Dimension 8 Nyquist)
