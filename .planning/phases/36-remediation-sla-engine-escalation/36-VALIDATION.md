---
phase: 36
slug: remediation-sla-engine-escalation
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-13
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from RESEARCH.md ## Validation Architecture. The planner refines the
> Per-Task Verification Map once PLAN.md task IDs exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest/RTL (frontend) |
| **Config file** | backend/pyproject.toml; frontend/vitest config |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest tests/test_sla_tier_service.py -q` (per-file — see memory: getvul-backend-pytest-env) |
| **Full suite command** | `cd backend && pytest -q` then `cd frontend && npm test` |
| **Estimated runtime** | ~60–120 seconds (backend per-file); full suite longer |

---

## Sampling Rate

- **After every task commit:** Run the relevant per-file pytest (backend) / vitest file (frontend)
- **After every plan wave:** Run the full backend suite for touched modules
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

> Populated by the planner against real task IDs. Rows below are the requirement-level
> validation targets lifted from RESEARCH.md ## Validation Architecture — the planner maps
> each to concrete task IDs + commands.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 36-01-T1/T2 | 01 | 1 | SLA-01, SLA-02 | T-36-01/02 | Tier boundaries exact (80/50/20, <20→not_tracked D-12); approaching-% scales per tier; NULL-score→severity fallback (D-03); default policy applied | unit | `pytest tests/test_sla_tier_service.py -q` | ✅ | ✅ green (29) |
| 36-01-T3 | 01 | 1 | SLA-02 | T-36-01 | list+detail responses carry sla_state/sla_due_at; SlaPill renders server state on the row (D-11), never re-derived client-side | api+component | `pytest tests/test_sla_tier_service.py -q && npx vitest run src/components/tickets/sla-pill.test.tsx` | ✅ | ✅ green (29 + sla-pill) |
| 36-02-T2/T3 | 02 | 2 | SLA-03 | T-36-esc-ssrf/leak | Channel payloads match vendor contracts (Slack/Teams-Workflows/PagerDuty/SMTP); https-only SSRF guard + follow_redirects=False; failed POST returns dict not raise; migration up+down | unit | `pytest tests/test_escalation_channels.py -q` | ✅ | ✅ green (33) |
| 36-05-T1/T2 | 05 | 2 | SLA-01, SLA-03 | T-36-sec-atrest/readback/rbac | Policy CRUD persists to Tenant.sla_config; secrets Fernet-encrypted at rest + masked on read + keep-on-masked-write; GET admin/PATCH owner 403s; validation rejects bad input; audit lands | unit+api | `pytest tests/test_sla_policy.py -q` | ✅ | ✅ green (16) |
| 36-03-T1/T2 | 03 | 3 | SLA-03 | T-36-fire-once/dup/audit | Exactly-once per (finding,to_state,channel) under double-tick; tier-floor + per-transition routing gating; every fire audited; one breach=one in-app signal (D-08); history endpoint tenant-scoped | unit+integration | `pytest tests/test_escalation_engine.py -q` | ✅ | ✅ green (7) |
| 36-04-T2/T3 | 04 | 4 | SLA-04 | T-36-mttr-drop/tenant/rbac | remediation-event written at all 6 REMEDIATED sites via one helper; tier-at-remediation frozen (NULL/low-score deterministic); MTTR-by-tier aggregate + endpoint; migration up+down | unit+api | `pytest tests/test_mttr.py -q` | ✅ | ✅ green (13) |
| 36-06-T1/T2 | 06 | 4 | SLA-01, SLA-02, SLA-03 | T-36-ui-secret/rbac | SLA & Escalation pane renders+saves (useDirtyState/SaveBar), touched-only secrets, RBAC-gated, loading/empty/error present; SlaPill 3-state on drill; escalation-history list (failed row audit-only, no retry, D-08) | component | `npx vitest run src/components/settings/sla-escalation-pane.test.tsx src/components/vulnerabilities/drill-panel.test.tsx src/components/vulnerabilities/drill-panel-mobile.test.tsx` | ✅ | ✅ green (pane + drill-panel + drill-panel-mobile) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `backend/tests/test_sla_tier_service.py` — tier-state computation incl. approaching-% scaling, NULL-score fallback, sub-MEDIUM on-track (D-12) — 29 passed
- [x] `backend/tests/test_sla_policy.py` — policy CRUD + RBAC (admin/owner only) — 16 passed
- [x] `backend/tests/test_escalation_engine.py` — exactly-once transition firing + D-08 reconciliation + audit coverage — 7 passed
- [x] `backend/tests/test_escalation_channels.py` — per-channel payload shaping (Slack/Teams-Workflows/PagerDuty/SMTP) + Fernet encryption/masking + failure handling — 33 passed
- [x] `backend/tests/test_mttr.py` — remediation-event capture across all REMEDIATED sites + MTTR-by-tier aggregate — 13 passed
- [x] Shared fixtures: scored + NULL-score findings, tenant with tier policy, mock channel HTTP (httpx mock)

*Frameworks already present (pytest, vitest) — no install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real webhook delivery to a live Slack/Teams/PagerDuty endpoint | SLA-03 | Third-party delivery cannot be asserted in CI without live creds | Configure a real webhook in a scratch tenant; force an approaching transition; confirm message arrives with correct formatting |
| PagerDuty manual-resolution limitation (D-13) | SLA-03 | Documented limitation, not a firing behavior | Confirm admin-pane copy states PagerDuty incidents require manual resolution |

*All in-app behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-08-18 (all 7 Per-Task Map rows COVERED — 98 backend + 81 frontend tests green)

---

## Validation Audit 2026-08-18

Reconciled stale pre-execution seed (all rows were `⬜ pending`, `status: draft`,
`nyquist_compliant: false`). Confirmed every requirement's test file exists on disk and runs
green — no MISSING gaps, so no auditor spawn was required.

**Backend (per-file pytest, ENCRYPTION_KEY/JWT_SECRET_KEY set per memory `getvul-backend-pytest-env`):**
`test_sla_tier_service` 29 · `test_escalation_channels` 33 · `test_escalation_engine` 7 ·
`test_sla_policy` 16 · `test_mttr` 13 = **98 passed**.
**Frontend (vitest):** `sla-pill` + `sla-escalation-pane` + `drill-panel` + `drill-panel-mobile` = **81 passed**.

Fixed test-file reference drift on the 36-06 row: replaced the non-existent
`src/components/vulnerabilities/drill-content.test.tsx` with the real
`drill-panel.test.tsx` + `drill-panel-mobile.test.tsx` (noted in 36-VERIFICATION.md Known
Coverage Notes).

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Manual-only (unchanged) | 2 (live webhook delivery; PagerDuty manual-resolution copy) |
