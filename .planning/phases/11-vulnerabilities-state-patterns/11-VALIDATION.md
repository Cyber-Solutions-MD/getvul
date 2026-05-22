---
phase: 11
slug: vulnerabilities-state-patterns
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-22
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1.6 + @testing-library/react 16.3.2 + vitest-axe 0.1.0 (frontend) · pytest (backend) |
| **Config file** | `frontend/vitest.config.ts` (confirm `environment: 'jsdom'` + `setupFiles: ['./vitest-setup.ts']`); `backend/pyproject.toml` pytest config |
| **Quick run command** | `cd frontend && npx vitest run --reporter=dot <path>` — or — `cd backend && pytest <path> -x` |
| **Full suite command** | `cd frontend && npm test` (all suites) — and — `cd backend && pytest backend/tests/ -x` |
| **Estimated runtime** | ~45s frontend full · ~25s backend full · ~3s per single file |

---

## Sampling Rate

- **After every task commit:** Run `npx vitest run --reporter=dot <path/to/touched.test.tsx>` (or pytest equivalent for backend tasks)
- **After every plan wave:** Run `npm test` (frontend) + `pytest backend/tests/test_vulnerabilities*.py backend/tests/test_tickets*.py` (backend)
- **Before `/gsd-verify-work`:** Full suite green + axe assertions passing on the 5 state/vuln primitives + page-level integration green
- **Max feedback latency:** < 60 seconds (per-task); < 90 seconds (per-wave full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 backend | 0 | UX-03-02 (sort), UX-03-05 (group) | — | `require_viewer` enforced; severity allow-list rejects bad input | pytest | `pytest backend/tests/test_vuln_sort.py -x` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 backend | 0 | UX-03-01 (facets), D-F-02 | T-IDOR | Facet counts respect tenant scoping; `require_viewer` enforced | pytest | `pytest backend/tests/test_vuln_facets.py -x` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 backend | 0 | UX-03-05, D-V-01 | T-IDOR | `?group=host` respects tenant scope; pagination math correct | pytest | `pytest backend/tests/test_vuln_group_host.py -x` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 backend | 0 | UX-03-03 (action: create ticket), D-P-04 | T-CSRF, T-AuthZ | `POST /tickets` requires `require_analyst`; 401 surfaces clean | pytest | `pytest backend/tests/test_tickets_create.py -x` | ⚠️ verify exists | ⬜ pending |
| 11-02-01 | 02 hooks | 1 | UX-03-04, D-F-05 | T-XSS | `useUrlStateList` XSS-clamps via allow-list before any render | unit | `npx vitest run hooks/use-url-state-list.test.ts` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 hooks | 1 | UX-S-03, D-S-03 | — | `useQueryErrors` re-renders only on error transitions (snapshot fingerprint) | unit | `npx vitest run lib/queries/use-query-errors.test.tsx` | ❌ W0 | ⬜ pending |
| 11-02-03 | 02 hooks | 1 | UX-03-01..03, D-F-02 | — | `useVulnerabilities` keys include filters; 401 retry restricted (Phase 10 BL-06) | unit | `npx vitest run lib/queries/use-vulnerabilities.test.tsx` | ❌ W0 | ⬜ pending |
| 11-02-04 | 02 hooks | 1 | UX-03-03 action, D-P-04 | T-CSRF, T-AuthN | `useCreateTicketMutation` throws `Session expired during mutation` on 401 (no retry) | unit | `npx vitest run lib/mutations/use-create-ticket.test.tsx` | ❌ W0 | ⬜ pending |
| 11-03-01 | 03 states | 1 | UX-S-01, D-S-01 | — | `SkeletonTable` honors `prefers-reduced-motion`; forced-colors safe | unit + axe | `npx vitest run components/states/skeleton-table.test.tsx` | ❌ W0 | ⬜ pending |
| 11-03-02 | 03 states | 1 | UX-S-02, D-S-02 | — | `EmptyState` compound API; `role="status"`; axe-clean | unit + axe | `npx vitest run components/states/empty-state.test.tsx` | ❌ W0 | ⬜ pending |
| 11-03-03 | 03 states | 1 | UX-S-03, D-S-03 | — | `PartialFailureBanner` hybrid mode; `role="alert"`; axe-clean; HTTP+request-id surfaced | unit + axe | `npx vitest run components/states/partial-failure-banner.test.tsx` | ❌ W0 | ⬜ pending |
| 11-03-04 | 03 states | 1 | D-V-02 | — | `PerSourceStatusStrip` `aria-live="polite"`; composes connectors + facets | unit + axe | `npx vitest run components/states/per-source-status-strip.test.tsx` | ❌ W0 | ⬜ pending |
| 11-04-01 | 04 vuln components | 2 | UX-03-01, D-F-01/02/03/05 | T-XSS | `ChipBar` debounce search 250ms; chips sync URL immediately; XSS clamp on display | unit | `npx vitest run components/vulnerabilities/chip-bar.test.tsx` | ❌ W0 | ⬜ pending |
| 11-04-02 | 04 vuln components | 2 | UX-03-02, UX-07-03, D-T-01/02/04, D-V-04 | — | 7 columns + 4 sortable; keyboard (Enter/Space/↑↓/Home/End/Esc); stale-row tint | unit | `npx vitest run components/vulnerabilities/vuln-table.test.tsx` | ❌ W0 | ⬜ pending |
| 11-04-03 | 04 vuln components | 2 | UX-03-03, D-P-01/02/05/06 | — | Drill panel desktop: close × / Esc / outside-click / row-swap; focus on close button | unit | `npx vitest run components/vulnerabilities/drill-panel.test.tsx` | ❌ W0 | ⬜ pending |
| 11-04-04 | 04 vuln components | 2 | UX-03-06, D-P-03 | — | Mobile drill via vaul bottom-sheet at <900px; matchMedia mock | unit | `npx vitest run components/vulnerabilities/drill-panel-mobile.test.tsx` | ❌ W0 | ⬜ pending |
| 11-04-05 | 04 vuln components | 2 | UX-03-05, D-V-01 | — | `ViewToggle` swaps mode without losing filter state | unit | `npx vitest run components/vulnerabilities/view-toggle.test.tsx` | ❌ W0 | ⬜ pending |
| 11-05-01 | 05 page rewrite | 2 | UX-03-01..06, UX-S-01..04 | — | Page renders chip-bar + table + panel; URL ↔ state round-trip; loading/empty/partial-failure paths | integration | `npx vitest run app/.../vulnerabilities/page.test.tsx` | ❌ W0 | ⬜ pending |
| 11-06-01..06 | 06 phase-10 retrofit | 3 | D-S-06, UX-S-01..03 | — | Each retrofit site renders canonical primitive; dashboard visual continuity preserved | unit | per-component test reruns | per-site | ⬜ pending |
| 11-07-01 | 07 dev primitives | 3 | UX-S-01..03 (showcase) | — | `/dev/primitives` lazy-loads new state primitives without bundling into prod | unit | `npx vitest run app/dev/primitives` | ❌ W0 | ⬜ pending |
| 11-08-01 | 08 a11y + UAT | 3 | UX-07-03 (slice) | — | Manual keyboard + screen-reader walkthrough on `/vulnerabilities` | manual | HUMAN-UAT checklist | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Frontend test files to scaffold (RED tests in Wave 0 before any implementation):

- [ ] `frontend/src/components/states/skeleton-table.test.tsx` — UX-S-01 + axe
- [ ] `frontend/src/components/states/empty-state.test.tsx` — UX-S-02 + axe + compound API
- [ ] `frontend/src/components/states/partial-failure-banner.test.tsx` — UX-S-03 + axe + hybrid mode
- [ ] `frontend/src/components/states/per-source-status-strip.test.tsx` — D-V-02 + axe + aria-live
- [ ] `frontend/src/hooks/use-url-state-list.test.ts` — D-F-05 + XSS clamp
- [ ] `frontend/src/lib/queries/use-query-errors.test.tsx` — D-S-03 + subscription model
- [ ] `frontend/src/lib/queries/use-vulnerabilities.test.tsx` — query key shape + filter composition
- [ ] `frontend/src/lib/mutations/use-create-ticket.test.tsx` — 401 surface (Phase 10 BL-06 carryover)
- [ ] `frontend/src/components/vulnerabilities/chip-bar.test.tsx` — UX-03-01 + debounce
- [ ] `frontend/src/components/vulnerabilities/vuln-table.test.tsx` — UX-03-02 + UX-07-03 keyboard + stale-row
- [ ] `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — UX-03-03 + D-P-01..06 focus
- [ ] `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — UX-03-06 + vaul
- [ ] `frontend/src/components/vulnerabilities/view-toggle.test.tsx` — UX-03-05
- [ ] `frontend/src/app/(authed)/dashboard/vulnerabilities/page.test.tsx` — page-level integration

Backend test files:

- [ ] `backend/tests/test_vuln_facets.py` — facet endpoint contextual math + tenant scope
- [ ] `backend/tests/test_vuln_group_host.py` — `?group=host` pagination + grouping math
- [ ] `backend/tests/test_vuln_sort.py` — expanded sort fields (severity, cve_id, cvss_v3_score, sla_due_at)
- [ ] (Verify exists) `backend/tests/test_tickets_create.py` — `POST /tickets` 201 + 401

Infrastructure:

- [ ] Confirm `frontend/vitest-setup.ts` exists and imports `vitest-axe/matchers` + extends `expect` (add if missing)
- [ ] `npm install vaul@1.1.2 --save-exact` (Wave 0 install — required by drill-panel-mobile tests)

*If none: "Existing infrastructure covers all phase requirements." — N/A; significant Wave 0 work above.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sunset-token visual continuity on Phase 10 retrofit | D-S-06 | CSS visual diff; automated test asserts presence but not visual fidelity | Open dashboard at 1440×900, screenshot before/after, diff against Phase 10 baseline screenshots |
| 420px drill panel layout fidelity to sketch-003 variant C | UX-03-03 | Pixel-exact mapping to mockup is a human judgment call | Open `?cve=CVE-2024-3094&open=drill`, compare to `.claude/skills/sketch-findings-getvul/sources/003-vulnerabilities-sunset/index.html` |
| vaul bottom-sheet smoothness on real mobile device | UX-03-06 | jsdom can't validate touch gestures, swipe-to-close, or render perf on iOS Safari | Open `/vulnerabilities` on iPhone Safari + Android Chrome, swipe drill open/closed |
| Empty-state copy voice + tone | UX-S-02 + copy-voice.md | Tone is judgment per `copy-voice.md`; automated tests assert presence not voice | Read each empty-state copy aloud; verify against `.claude/skills/sketch-findings-getvul/references/copy-voice.md` rules |
| Screen-reader announcement of `aria-live="polite"` per-source updates | D-V-02 | jsdom doesn't have real SR engine | VoiceOver (macOS) + NVDA (Windows) walkthrough on Phase 11 page-load + retry cycle |
| Forced-colors-mode preservation | Phase 9 a11y carryover | jsdom doesn't render `@media (forced-colors: active)` | Windows High Contrast mode + Firefox `prefers-contrast` devtools toggle |
| Reduce-motion shimmer suppression | Phase 9 a11y carryover | jsdom CSS animation gates unreliable | OS-level reduce-motion + verify skeleton shimmer stops |
| Real-world filter+pagination perf @ 2k vulns | D-T-03 | Synthetic load + render-time profile is judgment | Seed 2k vulns in dev DB, profile with React DevTools |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING test references (17 frontend + 3 backend = 20 new test files)
- [ ] No watch-mode flags (CI uses `vitest run`, not `vitest`)
- [ ] Feedback latency < 60s per task
- [ ] axe-core assertions present on all 4 state primitives + EmptyState compound + page integration
- [ ] `nyquist_compliant: true` set in frontmatter after planner confirms every task has `<automated>` block

**Approval:** pending
