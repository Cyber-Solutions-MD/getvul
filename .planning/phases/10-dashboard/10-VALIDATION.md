---
phase: 10
slug: dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Sourced from `10-RESEARCH.md` → Validation Architecture. Nyquist enabled (9 dimensions: 8 standard + project-specific `visual-fidelity-to-sketch-002`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Frontend test runner** | `vitest ^4.1.6` (already wired in `frontend/vitest.config.ts`) |
| **Frontend a11y matcher** | `vitest-axe ^0.1.0` (wired in `frontend/vitest.setup.ts`) |
| **Frontend DOM env** | `jsdom ^25.0.1` |
| **Component test lib** | `@testing-library/react ^16.3.2` |
| **Backend test runner** | `pytest >=8.3` + `pytest-asyncio >=0.24` + `asgi-lifespan >=2.1` |
| **Backend fixtures** | `backend/tests/conftest.py` (Phase 9 + Phase 1 conventions) |
| **Quick run command (frontend)** | `cd frontend && npm run test -- --run` |
| **Quick run command (backend)** | `cd backend && pytest -x` |
| **Full suite command** | `cd frontend && npm run test -- --run && npm run build && cd ../backend && pytest` |
| **Bundle measurement** | `cd frontend && npm run build` — read "First Load JS" column on `/dashboard` row (budget: ≤ 180 kB per D-Perf-01) |
| **Visual fidelity check** | Manual UAT against `.claude/skills/sketch-findings-getvul/sources/002-dashboard-sunset/index.html` variant B |
| **Estimated runtime** | ~90 seconds (frontend vitest ~30s + backend pytest ~20s + next build ~40s) |

---

## Sampling Rate

- **After every task commit:** `cd frontend && npm run test -- --run` AND/OR `cd backend && pytest -x` (whichever side the task touched)
- **After every plan wave:** Full suite — vitest + pytest + `npm run build` (verifies First-Load JS budget); smoke open `/dashboard` in `npm run dev`
- **Before `/gsd-verify-work`:** Full suite must be green + HUMAN UAT against sketch 002 variant B
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

> Filled by Wave-0 of the plan. Each entry maps a phase requirement to a concrete automated command. Status updated as tasks complete.

| Req ID | Behavior | Dimension(s) | Test Type | Automated Command | File Status | Status |
|--------|----------|--------------|-----------|-------------------|-------------|--------|
| UX-02-01 | Hero renders pulsing dot + headline + sub-line + CTAs | behavioral, visual-fidelity | unit | `vitest run frontend/src/components/dashboard/hero.test.tsx` | ❌ W0 | ⬜ |
| UX-02-01 | Snooze CTA fires POST `/snooze` + invalidates 3 cache keys | behavioral, integration | unit | `vitest run frontend/src/lib/mutations/use-snooze.test.tsx` | ❌ W0 | ⬜ |
| UX-02-01 | POST `/snooze` endpoint sets status=SUPPRESSED + audit event | behavioral, integration, security | pytest | `pytest backend/tests/test_snooze.py` | ❌ W0 | ⬜ |
| UX-02-02 | StatStrip renders 4 tiles with delta indicators (▲/▼ + count + "from yesterday") | behavioral, visual-fidelity | unit | `vitest run frontend/src/components/ui/stat-strip.test.tsx` | ❌ W0 | ⬜ |
| UX-02-02 | StatStrip handles `delta=null` gracefully ("Δ —") | behavioral, regression | unit | (in stat-strip.test.tsx) | ❌ W0 | ⬜ |
| UX-02-02 | `/stats.dashboard_tiles` returns 4 tiles + delta_7d computed from `DailySnapshot` | behavioral, integration | pytest | `pytest backend/tests/test_dashboard_tiles.py` | ❌ W0 | ⬜ |
| UX-02-03 | TrendChart renders stacked bars with 4 severity colors via CSS variables | behavioral, regression | unit | `vitest run frontend/src/components/ui/trend-chart.test.tsx` | ❌ W0 | ⬜ |
| UX-02-03 | TrendChart visually-hidden `<table>` (30 rows × 4 severities + totals) | accessibility | unit + axe | (same file, axe block) | ❌ W0 | ⬜ |
| UX-02-03 | Recharts route-split — absent from `/dashboard` main chunk | performance | manual + script | `cd frontend && npm run build && node scripts/check-bundle.mjs --route /dashboard --max-kb 180` | ❌ W0 (script) | ⬜ |
| UX-02-03 | Range toggle URL-syncs (`?range=7d`) + clamps invalid input | behavioral, integration, security | unit | `vitest run frontend/src/hooks/use-url-state.test.ts` | ❌ W0 | ⬜ |
| UX-02-03 | `/trends?days=30` returns `severity_trends: {date: {c,h,m,l}, …}` length 30 | behavioral, integration | pytest | `pytest backend/tests/test_severity_trends.py` | ❌ W0 | ⬜ |
| UX-02-04 | Top5Card renders 5 rows: severity glyph + CVE mono + asset + score + SLA pill | behavioral, visual-fidelity | unit | `vitest run frontend/src/components/dashboard/top5-card.test.tsx` | ❌ W0 | ⬜ |
| UX-02-04 | `?sort=triage&limit=5` returns rows in KEV → CVSS desc → SLA-asc order | behavioral, integration | pytest | `pytest backend/tests/test_triage_sort.py` | ❌ W0 | ⬜ |
| UX-02-05 | ActivityFeed renders 5 items with category-tinted icons (pink/amber/violet/success) | behavioral, visual-fidelity | unit | `vitest run frontend/src/components/ui/activity-feed.test.tsx` | ❌ W0 | ⬜ |
| UX-02-05 | Existing `/notifications?page=1&page_size=5` shape unchanged | behavioral, regression | pytest | `pytest backend/tests/test_notifications.py` | ✅ existing | ⬜ |
| UX-02-06 | Quiet-win swap when `critical_open.value=0` — hero shows "Nothing critical right now" | behavioral | unit | `vitest run frontend/src/components/dashboard/hero.test.tsx -t "quiet-win"` | ❌ W0 | ⬜ |
| UX-02-06 | `onboarding_state='no_scanners'` renders full-page panel + "Connect a scanner" CTA | behavioral, integration | unit | `vitest run frontend/src/components/dashboard/onboarding-panel.test.tsx` | ❌ W0 | ⬜ |
| UX-02-06 | `/stats.onboarding_state` detects 'no_scanners' / 'no_data_yet' / 'ready' | behavioral, integration | pytest | `pytest backend/tests/test_onboarding_state.py` | ❌ W0 | ⬜ |
| UX-02-06 | Every section has loading state + error block | behavioral, regression | unit | `vitest run frontend/src/app/(authed)/dashboard/page.test.tsx` | ❌ W0 | ⬜ |
| Cross-cutting | axe-core reports 0 violations on the full dashboard | accessibility | integration | `vitest run frontend/src/app/(authed)/dashboard/dashboard.a11y.test.tsx` | ❌ W0 | ⬜ |
| Cross-cutting | First-Load JS on `/dashboard` ≤ 180 kB | performance | manual + script | (same as bundle-check above) | ❌ W0 | ⬜ |
| Cross-cutting | Reduce-motion: chart animations disabled when `prefers-reduced-motion: reduce` | accessibility | unit | `vitest run frontend/src/components/ui/trend-chart.motion.test.tsx` | ❌ W0 | ⬜ |
| Cross-cutting | Forced-colors: chart conveys severity via glyphs (tooltip + visually-hidden table) | accessibility | manual UAT | DevTools "Emulate CSS media feature forced-colors: active" | manual | ⬜ |
| Cross-cutting | `queryClient.clear()` called on logout — next-user shows no stale data | security, regression | unit | `vitest run frontend/src/lib/auth.logout.test.tsx` | ❌ W0 | ⬜ |
| Cross-cutting | 401 → `tryRefreshToken` → retry → if-fail → `/login` chain | security, behavioral | unit | `vitest run frontend/src/lib/api.test.ts` | ❌ W0 (extend Phase 9) | ⬜ |
| Cross-cutting | Visual fidelity to sketch 002 variant B | visual-fidelity | manual UAT | side-by-side at 1280px against `sources/002-dashboard-sunset/index.html` | manual | ⬜ |
| Cross-cutting | Document title updates to `(N) Dashboard · GetVul` when critical>0 | behavioral | unit | `vitest run frontend/src/hooks/use-document-title.test.ts` | ❌ W0 | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Dimension Coverage Matrix

| Dimension | Covered By |
|-----------|-----------|
| **Structural** | `npm run build` passes; `tsc --noEmit` passes; pydantic schemas validate; no unused exports |
| **Behavioral** | All per-requirement unit + integration tests above |
| **Integration** | Frontend hits real backend via vitest msw OR pytest-driven backend fixtures; full e2e via HUMAN UAT |
| **Regression** | Phase 9 test suite passes (53 tests verified in `09-HUMAN-UAT.md`); legacy `/dashboard/{vulnerabilities,assets,cspm,tickets,users,settings}` v1 styling preserved per CONTEXT.md `<domain>` |
| **Performance** | First-Load JS ≤ 180 kB measured via `next build`; CLS < 0.1 verified in DevTools Performance trace during HUMAN UAT |
| **Accessibility** | axe-core via vitest-axe on every section; visually-hidden table for chart; reduce-motion test; forced-colors HUMAN UAT; keyboard nav HUMAN UAT |
| **Security** | `queryClient.clear()` test; 401 chain test; error messages don't leak server-side detail (Phase 9 `api.ts`); CSRF/cookie handling unchanged; snooze bounded to ≤ 30 days; tenant_id filter on snooze (IDOR mitigation) |
| **Visual fidelity (project-specific)** | Manual checklist against `sources/002-dashboard-sunset/index.html` variant B — palette, typography, severity glyphs, SLA chips, hover states, gradient CTA, pulsing dot |

---

## Wave 0 Requirements

Files Wave 0 of the plan MUST create before any feature task runs. Tests start red; feature tasks turn them green.

**Sampling-rate concession for primitive tests (Warning 10 — option b):** Primitive test files (`card.test.tsx`, `stat.test.tsx`, `stat-strip.test.tsx`, `activity-feed.test.tsx`, `error-boundary.test.tsx`, `trend-chart.test.tsx`, `trend-chart.motion.test.tsx`) are created **tdd-within-task** by Wave 1 plans (10-03, 10-04). Tests + implementation land in the same commit. Sampling continuity is preserved because no 3 consecutive Wave 1 tasks are testless — every primitive task carries its own `.test.tsx` per `<task tdd="true">` contract. The Wave 0 list below reflects this: those primitive tests are no longer pre-created in a separate RED-only Wave 0 step.

- [ ] `frontend/src/components/dashboard/hero.test.tsx` — UX-02-01 + UX-02-06 (quiet-win)
- [ ] `frontend/src/components/dashboard/top5-card.test.tsx` — UX-02-04
- [ ] `frontend/src/components/dashboard/onboarding-panel.test.tsx` — UX-02-06
- [ ] `frontend/src/components/ui/card.test.tsx` · `stat.test.tsx` · `stat-strip.test.tsx` · `activity-feed.test.tsx` · `trend-chart.test.tsx` · `trend-chart.motion.test.tsx` · `error-boundary.test.tsx`  *(created tdd-within-task by Plans 10-03/10-04, not pre-created here — Warning 10 concession)*
- [ ] `frontend/src/lib/mutations/use-snooze.test.tsx`
- [ ] `frontend/src/lib/queries/use-stats.test.tsx` · `use-trends.test.tsx` · `use-top-triage.test.tsx` · `use-recent-notifications.test.tsx`
- [ ] `frontend/src/hooks/use-document-title.test.ts` · `use-url-state.test.ts` · `use-prefers-reduced-motion.test.ts`
- [ ] `frontend/src/lib/api.test.ts` — extend if Phase 9 didn't cover 401 retry-after-refresh
- [ ] `frontend/src/components/ui/toast.test.tsx` — asserts Toast `duration` + `action` slot + sunset CSS variables + reduce-motion (Plan 02 Task 0 — Blocker 1)
- [ ] `frontend/src/lib/mutations/use-undo-snooze.test.tsx` — asserts unsnooze POST + 3-key invalidation (Plan 02 — Blocker 1 + D-H-08)
- [ ] `frontend/src/components/dashboard/trend-section.test.tsx` — asserts severity_trends → TrendDatum[] reshape + h2 (Plan 05 Task 2 — Warning 7)
- [ ] `frontend/src/components/dashboard/stat-strip-wired.test.tsx` — asserts 4-tile icon mapping + h2 (Plan 05 Task 2 — Warning 7)
- [ ] `frontend/src/components/shell/sidebar-cache.test.tsx` — asserts single-fetch invariant (Plan 06 Task 3 — Warning 15)
- [ ] `backend/tests/test_unsnooze.py` — asserts symmetric unsnooze endpoint (Plan 01 — Blocker 1 backend)
- [ ] `frontend/src/lib/auth.logout.test.tsx` — asserts `queryClient.clear()` called
- [ ] `frontend/src/app/(authed)/dashboard/dashboard.a11y.test.tsx` — full-page axe scan
- [ ] `frontend/src/app/(authed)/dashboard/page.test.tsx` — page-level integration (loading + partial-failure)
- [ ] `frontend/scripts/check-bundle.mjs` — parses `next build` output and asserts `/dashboard` First-Load JS ≤ 184320 bytes (= 180 kB exactly per D-Perf-01; "184" earlier referenced raw bytes-per-kB which conflated bytes with kB — the budget is 180 kB and `--max-kb 180`)
- [ ] `backend/tests/test_dashboard_tiles.py` · `test_severity_trends.py` · `test_triage_sort.py` · `test_top_vuln.py` · `test_snooze.py` · `test_onboarding_state.py`
- [ ] `frontend/src/components/dashboard/microcopy.ts` — extracted dashboard strings per `copy-voice.md`
- [ ] `.planning/phases/10-dashboard/10-HUMAN-UAT.md` — manual checklist (sketch fidelity, forced-colors, keyboard nav)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual fidelity to sketch 002 variant B | All (UX-02-01..06) | Pixel-eye-checking; axe + vitest can't catch palette drift or rhythm errors | Open `/dashboard` at 1280px side-by-side with `.claude/skills/sketch-findings-getvul/sources/002-dashboard-sunset/index.html` — verify hero gradient, severity glyphs, SLA chip colors, activity rail icon variants, monospace identifiers, pulse animation feel |
| Forced-colors mode | UX-02-03, Cross-cutting (accessibility) | Browser DevTools toggle, no automated way that exercises real OS HC theme | Chrome DevTools → Rendering → Emulate CSS media feature `forced-colors: active`. Verify severity colors fall back to glyphs in chart tooltip + visually-hidden table; CTA still readable; pulsing dot still visible |
| Keyboard navigation flow | Cross-cutting | Tab order + focus rings require human judgment | Tab from skip-link → hero CTAs → stat tiles (skip — not interactive) → range toggle → top-5 rows → activity rail rows. Verify focus rings visible against sunset palette; Enter activates CTAs; Esc closes any popovers |
| Reduce-motion subjective feel | D-Ax-04 | "Color stays, animation stops" must look intentional | macOS System Settings → Accessibility → Display → Reduce motion → enabled. Reload `/dashboard`. Verify pulsing dot is solid (no pulse); chart bars render at final height; tile counters show final number; CTA hover still works (no animation) |
| CLS measurement | Cross-cutting (performance) | Requires DevTools Performance trace | DevTools → Performance → Record load → Stop at first paint complete. Verify CLS < 0.1. Common offenders: skeleton-to-real-data swap shifting layout |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references above
- [ ] No watch-mode flags (`vitest run` / `pytest -x`, not `vitest` / `pytest --watch`)
- [ ] Feedback latency < ~90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
