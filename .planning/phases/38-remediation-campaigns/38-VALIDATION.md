---
phase: 38
slug: remediation-campaigns
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-17
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 8.3+ / pytest-asyncio 0.24+ `[VERIFIED: backend/pyproject.toml]` |
| **Framework (frontend)** | Vitest 4.1.6 (unit/component) + Playwright 1.61.1 (e2e, seed-gated) `[VERIFIED: frontend/package.json]` |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` (line 74); frontend `vitest.config.ts` |
| **Quick run command (backend)** | `cd backend && ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test-secret pytest tests/test_campaigns.py -x` |
| **Quick run command (frontend)** | `cd frontend && npm run test -- campaigns` |
| **Full suite command (backend)** | Run **per-file** (project memory `getvul-backend-pytest-env` — whole `tests/` dir gives false failures): `ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test-secret pytest tests/test_campaigns.py -x` |
| **Full suite command (frontend)** | `cd frontend && npm run test && npm run build` (bundle budget) |
| **Estimated runtime** | backend `test_campaigns.py` ~15s; frontend campaigns unit ~10s + build ~60s |

---

## Sampling Rate

- **After every task commit:** backend `pytest tests/test_campaigns.py -x` (with env vars) / frontend `npm run test -- <file>`
- **After every plan wave:** full per-file backend suite + `npm run test` + `npm run build`
- **Before `/gsd-verify-work`:** full suite green + the Plan 05 human-verify lifecycle checkpoint approved
- **Max feedback latency:** ~60s (backend) / ~90s (frontend incl. build)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01-02 | 01 | 1 | CAMP-01 | T-38-06 | DB-level rejection of a 2nd active campaign per (tenant, remediation_id) | unit | `pytest tests/test_campaigns.py::test_campaign_unique_active_index -x` | ❌ W0 | ⬜ pending |
| 38-01-02 | 01 | 1 | CAMP-01 | — | closed campaign's remediation_id accepts a new active campaign | unit | `pytest tests/test_campaigns.py::test_new_campaign_after_close -x` | ❌ W0 | ⬜ pending |
| 38-01-03 | 01 | 1 | CAMP-01 | T-38-02/04 | create new; require_analyst | unit | `pytest tests/test_campaigns.py::test_create_campaign_new -x` | ❌ W0 | ⬜ pending |
| 38-01-03 | 01 | 1 | CAMP-01 | T-38-06 | re-launch opens existing, no dup, no 2nd audit | unit | `pytest tests/test_campaigns.py::test_create_campaign_reopens_existing -x` | ❌ W0 | ⬜ pending |
| 38-01-03 | 01 | 1 | CAMP-03 | — | REMEDIATED counted in done (Pitfall 2) | unit | `pytest tests/test_campaigns.py::test_progress_counts_include_remediated -x` | ❌ W0 | ⬜ pending |
| 38-01-03 | 01 | 1 | CAMP-03 | — | zero-member 0%, no 500 (Pitfall 5) | unit | `pytest tests/test_campaigns.py::test_progress_zero_member_no_crash -x` | ❌ W0 | ⬜ pending |
| 38-01-03 | 01 | 1 | CAMP-04 | T-38-01/04 | viewer 403 write / 200 read; cross-tenant 404 | integration | `pytest tests/test_campaigns.py::test_campaign_rbac -x` | ❌ W0 | ⬜ pending |
| 38-02-01 | 02 | 2 | CAMP-02 | — | one ticket per owner (D-04) | unit | `pytest tests/test_campaigns.py::test_bulk_assign_one_ticket_per_owner -x` | ❌ W0 | ⬜ pending |
| 38-02-01 | 02 | 2 | CAMP-02 | — | owner-less → unassigned bucket (D-08) | unit | `pytest tests/test_campaigns.py::test_bulk_assign_unassigned_bucket -x` | ❌ W0 | ⬜ pending |
| 38-02-01 | 02 | 2 | CAMP-02 | — | adopt existing ticket (D-06) | unit | `pytest tests/test_campaigns.py::test_bulk_assign_adopts_existing_ticket -x` | ❌ W0 | ⬜ pending |
| 38-02-01 | 02 | 2 | CAMP-02 | — | re-run tickets only newcomers (D-10) | integration | `pytest tests/test_campaigns.py::test_bulk_assign_idempotent_rerun -x` | ❌ W0 | ⬜ pending |
| 38-02-01 | 02 | 2 | CAMP-02 | — | owner derivation == ticketing/service.py (D-05) | unit | `pytest tests/test_campaigns.py::test_owner_derivation_matches_ticketing_service -x` | ❌ W0 | ⬜ pending |
| 38-02-02 | 02 | 2 | CAMP-04 | T-38-03/04 | bulk_assign audited every run; viewer 403 | integration | `pytest tests/test_campaigns.py::test_bulk_assign_audited_every_run -x` | ❌ W0 | ⬜ pending |
| 38-03-01 | 03 | 3 | CAMP-03 | — | MTTR = avg member RemediationEvent durations (D-12) | unit | `pytest tests/test_campaigns.py::test_campaign_mttr_average -x` | ❌ W0 | ⬜ pending |
| 38-03-01 | 03 | 3 | CAMP-03 | — | live membership grows (D-03) | integration | `pytest tests/test_campaigns.py::test_live_membership_grows -x` | ❌ W0 | ⬜ pending |
| 38-03-02 | 03 | 3 | CAMP-04 | T-38-03/04 | create/bulk_assign/close each audited | integration | `pytest tests/test_campaigns.py::test_campaign_actions_audited -x` | ❌ W0 | ⬜ pending |
| 38-03-02 | 03 | 3 | CAMP-04 | T-38-05/08 | auto-complete audited exactly once | integration | `pytest tests/test_campaigns.py::test_auto_complete_audited_once -x` | ❌ W0 | ⬜ pending |
| 38-03-02 | 03 | 3 | CAMP-03 | T-38-05 | reopen reactivates (D-14); manual close sticky (D-17) | integration | `pytest tests/test_campaigns.py::test_reopen_reactivates_campaign -x` | ❌ W0 | ⬜ pending |
| 38-04-01 | 04 | 2 | CAMP-01 | T-38-09 | hooks staleTime:0; status pill violet/green not severity | component | `npm run test -- use-campaigns campaign-status-ribbon` | ❌ W0 | ⬜ pending |
| 38-04-02 | 04 | 2 | CAMP-01 | T-38-09 | list columns + singularization + empty state + row-click fires onRowClick (nav to /campaigns/{id}) | component | `npm run test -- campaigns-table` | ❌ W0 | ⬜ pending |
| 38-05-01 | 05 | 4 | CAMP-01 | T-38-09 | entry point + Start campaign + D-11 redirect | component | `npm run test -- remediations-table` | ❌ W0 | ⬜ pending |
| 38-05-02 | 05 | 4 | CAMP-03 | T-38-09 | burndown 0/0 no-crash; MTTR/breakdown copy | component | `npm run test -- campaign-burndown-card` | ❌ W0 | ⬜ pending |
| 38-05-03 | 05 | 4 | CAMP-01/02/03 | T-38-04 | full create→bulk-assign→close lifecycle | manual | human-verify (seed-gated e2e) | ❌ manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_campaigns.py` — new file; covers all CAMP-01..04 rows above (seeded across Plans 01–03). `conftest.py` fixture surface (`db_session`, `tenant_a`, `analyst_user`, `viewer_user`, `client`) already covers everything — zero new fixtures.
- [ ] `backend/app/campaigns/` module — new (`__init__.py`/`models.py`/`schemas.py`/`service.py`/`router.py`, Plan 01).
- [ ] `backend/alembic/versions/049_add_campaigns.py` — new migration (Plan 01).
- [ ] Frontend component/hook test files — new (Plans 04/05): `use-campaigns.test.ts`, `campaign-status-ribbon.test.tsx`, `campaigns-table.test.tsx`, `remediations-table.test.tsx`, `campaign-burndown-card.test.tsx`, mirroring `RiskRing.test.tsx`/`severity-ribbon` conventions.
- [ ] `backend` pytest env: `ENCRYPTION_KEY` (real Fernet) + `JWT_SECRET_KEY` set; run per-file (project memory).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full create→bulk-assign→close lifecycle incl. 100%-remediated auto-complete | CAMP-01/02/03 | E2E is seed-gated + destructive per project memory `getvul-kanban-e2e-seed-gated-destructive`; the shared dev seed can't deterministically drive 100%-remediated auto-complete, and the suite persists mutations to the live backend. The auto-complete path is otherwise covered at the service/API level (`test_auto_complete_audited_once`) by driving `mark_vulnerability_remediated()` directly. | Plan 05 Task 3 human-verify steps 2–8 (Start campaign, D-11 redirect, Create N tickets + adopt re-run, burndown, danger-dialog close, status-family colors). |
| Visual design-system conformance (status palette, mono numerics, sunset-gradient ring, spacing) | CAMP-01/03 | Axe/visual sweeps require a prod build + server and aren't run inline (project memory `getvul-axe-sweep-not-run-during-exec`); token contrast reasoned manually + confirmed at human-verify. | Observe pills/ring/breakdown use violet/amber/green (never severity), JetBrains Mono + tabular-nums on numerics, foundation.md variables (no freehand hex). |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (manual-only lifecycle documented + backed by service-level auto tests)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every backend/frontend task has an automated command; only the final Plan 05 checkpoint is manual)
- [x] Wave 0 covers all MISSING references (`test_campaigns.py`, `app/campaigns/`, migration 049, frontend test files)
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter (flip at validate-phase once test files exist + green)

**Approval:** pending
