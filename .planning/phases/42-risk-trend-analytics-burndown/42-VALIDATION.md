---
phase: 42
slug: risk-trend-analytics-burndown
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-21
validated: 2026-08-22
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Reconciled against the finalized 3-plan / 6-task structure (commit `a7cbe32`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ / pytest-asyncio `asyncio_mode="auto"` (backend) · vitest (frontend unit) · Playwright (e2e, optional) |
| **Config file** | backend/pyproject.toml · frontend/vitest.config.ts · frontend/playwright.config.ts |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=test-key-do-not-use-in-prod-000000000000 JWT_SECRET_KEY=test-jwt-secret uv run pytest tests/test_analytics.py -x` |
| **Full suite command** | `cd backend && ... uv run pytest tests/ -x` (per-file env vars) · `cd frontend && npm test` |
| **Estimated runtime** | ~30–60 s (backend single-file) / ~60–90 s (frontend unit) |

---

## Sampling Rate

- **After every task commit:** backend tasks → `uv run pytest tests/test_analytics.py -x`; frontend tasks → `npx vitest run "src/app/(authed)/dashboard/analytics/page.test.tsx"` + `npx tsc --noEmit`
- **After every plan wave:** run both the backend single-file and the frontend page test green
- **Before `/gsd-verify-work`:** full suites green — `cd backend && uv run pytest tests/ -x` and `cd frontend && npm test`
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

> All backend tests live in `backend/tests/test_analytics.py`; all frontend unit tests in `frontend/src/app/(authed)/dashboard/analytics/page.test.tsx`. The synthetic multi-version DailySnapshot fixture is hand-built inline (per 42-PATTERNS.md precedent), not via conftest.py. Checkpoint tasks are human-verify gates (no automated command).

| Task ID | Plan | Wave | Requirement | Threat Ref | Test Type | Automated Command | Status |
|---------|------|------|-------------|------------|-----------|-------------------|--------|
| 42-01-T1 (tracer, backend) | 01 | 1 | TREND-01, TREND-03 | T-42-01..03 (cross-tenant, RBAC, DoS) | unit | `uv run pytest tests/test_analytics.py -x` | ✅ green |
| 42-01-T2 (tracer, frontend) | 01 | 1 | TREND-01, TREND-03 | — | unit | `npx vitest run ".../analytics/page.test.tsx"` + `npx tsc --noEmit` | ✅ green |
| 42-01-T3 (checkpoint:human-verify) | 01 | 1 | TREND-01, TREND-03 | — | manual | tracer human-verify gate | ✅ approved |
| 42-02-T1 (backend aging/burndown) | 02 | 2 | TREND-02 | T-42-04.. (exclusion/DoS) | unit | `uv run pytest tests/test_analytics.py -x` | ✅ green |
| 42-02-T2 (frontend aging chart + burndown tile) | 02 | 2 | TREND-02 | — | unit | `npx vitest run ".../analytics/page.test.tsx"` + `npx tsc --noEmit` | ✅ green |
| 42-02-T3 (checkpoint:human-verify) | 02 | 2 | TREND-02 | — | manual | human-verify gate | ✅ approved |
| 42-03-T1 (backend group-scope + IDOR + multi-boundary) | 03 | 3 | TREND-01, TREND-03 | T-42-.. (IDOR 404, span cap) | unit | `uv run pytest tests/test_analytics.py -x` | ✅ green |
| 42-03-T2 (frontend scope/date controls + truncation + markers) | 03 | 3 | TREND-01 | — | unit | `npx vitest run ".../analytics/page.test.tsx"` + `npx tsc --noEmit` | ✅ green |
| 42-03-T3 (checkpoint:human-verify) | 03 | 3 | TREND-01, TREND-03 | — | manual | human-verify gate | ✅ approved |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `backend/tests/test_analytics.py` — new test file covering TREND-01/02/03 (created inside 42-01-T1, TDD-first). **809 lines, 17 `async def test_` functions** on disk, names match all 3 SUMMARY coverage refs exactly.
- [x] Inline synthetic multi-version DailySnapshot fixture (varying `metrics["risk_model_version_snapshot"]`) — makes TREND-03 verifiable (RESEARCH Pitfall 1: `RISK_MODEL_VERSION` has been `"v1"` forever). Includes a **3-version (v1→v2→v3) → 2-boundary** case (W2 fix, Plan 03) via `test_multiple_version_boundaries_each_marked`.
- [x] `frontend/src/app/(authed)/dashboard/analytics/page.test.tsx` — new page/state test file (created inside 42-01-T2). **540 lines**, all state branches present; **18/18 re-run green in VERIFICATION.md**.
- [x] Existing pytest + vitest + Playwright infrastructure covers the rest (no framework install needed)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Version-boundary renders as a labeled `ReferenceLine` marker, never a false cliff | TREND-03 | Production data is single-version; needs synthetic multi-version history to observe visually (automated coverage exists via the inline fixture) | Seed a tenant with snapshots spanning ≥2 `risk_model_version_snapshot` values; open `/dashboard/analytics`; confirm segments don't blend across the boundary and each in-window boundary gets its own marker |
| Loading / empty / error states on the analytics dashboard | TREND-01/02 | Visual states mandated by project rules (verified by human at each plan's human-verify checkpoint) | Load with no history (empty), throttled network (loading), forced 500 (error) |
| Empty-membership group renders the guided D-04 EmptyState (coverage **D9**, escalated) | TREND-01 | **Escalated backstop-tier item, not a test gap.** `page.tsx`'s `isBelowMinHistory = trend.length < MIN_HISTORY_POINTS` is a row-COUNT check; a zero-current-member group still returns one all-`None` row per snapshot day, so it renders the populated branch with an honest all-null line instead of the guided EmptyState. Closing it properly requires an impl change (an all-rows-`None` gate) — out of scope for validate-phase (never modifies impl). Accepted via override in 42-VERIFICATION.md; aging/burndown half correctly hits the zero-open-backlog path (`test_aging_zero_open_renders_three_zero_buckets`). | Seed a tenant with an AssetGroup that has zero current members but historical snapshots; open `/dashboard/analytics`, scope to that group; confirm the trend renders a guided EmptyState (currently: all-null line). Track for `/gsd-verify-work 42` or a Phase 43 polish pass. |

*Automated coverage carries every requirement (TREND-01/02/03); the rows above are visual/synthetic supplements plus the single escalated D9 backstop.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (all 6 auto-tasks green; 3 T3 checkpoints are by-design human-verify gates, all approved)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test file + inline multi-version fixture + frontend test file all on disk)
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-08-22 — all 3 requirements automated-covered and green; one escalated backstop (D9) documented in Manual-Only.

---

## Validation Audit 2026-08-22

State A audit (reconciliation). VALIDATION.md carried stale pre-execution frontmatter (`status: draft`, `nyquist_compliant: false`, all task rows `⬜ pending`) — the recurring "never flipped back after execution" pattern (cf. v2.1 BL-05). No new tests generated: every requirement already has real, green automated coverage on disk, cross-referenced against `backend/tests/test_analytics.py` (17 tests) and `page.test.tsx` (18 assertions, re-run green in VERIFICATION.md). Auditor not spawned — no MISSING/PARTIAL automated gaps to fill.

| Metric | Count |
|--------|-------|
| Gaps found | 1 (D9, backstop-tier, escalated — impl-behavior, not a test gap) |
| Resolved | 0 (no auto-fillable gaps) |
| Escalated | 1 (D9 → Manual-Only; requires impl change, out of validate-phase scope) |
| Task rows reconciled ⬜→✅ | 9 (6 green + 3 approved checkpoints) |
