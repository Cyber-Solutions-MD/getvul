---
phase: 42
slug: risk-trend-analytics-burndown
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-21
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) / vitest + Playwright (frontend) |
| **Config file** | backend/pyproject.toml · frontend/vitest.config.ts · frontend/playwright.config.ts |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest tests/test_analytics_*.py` |
| **Full suite command** | `cd backend && pytest` · `cd frontend && npm run test` |
| **Estimated runtime** | ~60 seconds (per-file backend) / ~90 seconds (frontend unit) |

---

## Sampling Rate

- **After every task commit:** Run the relevant per-file quick command
- **After every plan wave:** Run the full suite for the touched surface (backend or frontend)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

> Seeded by plan-phase; the planner and executor fill exact task IDs/commands per PLAN.md. TREND-03 (version-boundary) requires a synthetic multi-version fixture — see Manual-Only / Wave 0.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 42-01-01 | 01 | 1 | TREND-01 | — | analytics endpoint returns tenant-scoped trend series only | unit | `pytest tests/test_analytics_service.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_analytics_service.py` — stubs for TREND-01/02/03
- [ ] `backend/tests/conftest.py` — reuse existing DailySnapshot fixture builder; add a **multi-version** snapshot fixture (varying `risk_model_version_snapshot`) to make TREND-03 verifiable (RESEARCH pitfall: `RISK_MODEL_VERSION` has been `"v1"` forever)
- [ ] Existing pytest + vitest + Playwright infrastructure covers the rest

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Version-boundary annotation renders as a labeled marker, not a false cliff | TREND-03 | Requires synthetic multi-version history to observe visually; production data is single-version | Seed a tenant with snapshots spanning ≥2 `risk_model_version_snapshot` values, open the trend dashboard, confirm the boundary is a `ReferenceLine` marker and the line segments do not blend across the boundary |
| Loading / empty / error states on the trend dashboard | TREND-01/02 | Visual states mandated by project rules | Load with no history (empty), slow network (loading), forced 500 (error) |

*Automated coverage carries the rest.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
