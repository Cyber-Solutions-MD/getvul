---
phase: 36
slug: remediation-sla-engine-escalation
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| **Quick run command** | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest tests/test_sla_engine.py -q` (per-file — see memory: getvul-backend-pytest-env) |
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
| TBD | 01 | 1 | SLA-01 | — | Policy CRUD persists to `Tenant.sla_config`; PATCH is RBAC-gated to admin/owner; non-admin → 403 | unit+api | `pytest tests/test_sla_policy.py -q` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SLA-02 | — | Per-tier state (on-track/approaching/breached) computed correctly; approaching-% scales per tier (80% of 7d vs 90d); NULL-score → severity fallback; score<20 → always on-track (D-12) | unit | `pytest tests/test_sla_engine.py -q` | ❌ W0 | ⬜ pending |
| TBD | 02 | 2 | SLA-03 | T-36-esc | One transition fires exactly one escalation-event per (finding,transition,channel); re-tick does NOT re-fire; old `_check_sla_breaches` reconciled → no double-fire (D-08); every fire audited via fail-closed `audit()` | unit+integration | `pytest tests/test_escalation_engine.py -q` | ❌ W0 | ⬜ pending |
| TBD | 02 | 2 | SLA-03 | T-36-sec | Channel secrets Fernet-encrypted at rest (D-14) + masked on read; failed channel POST audited + surfaced, does not block the transition record | unit | `pytest tests/test_escalation_channels.py -q` | ❌ W0 | ⬜ pending |
| TBD | 03 | 2 | SLA-04 | — | remediation-event row written on every REMEDIATED path (all 6 sites); MTTR-by-tier aggregate query returns correct grouped durations (tier-at-remediation) | unit | `pytest tests/test_mttr.py -q` | ❌ W0 | ⬜ pending |
| TBD | 04 | 3 | SLA-01/02 | — | SLA & Escalation settings pane renders + saves (useDirtyState/SaveBar); SlaPill renders 3-state on row+drill; loading/empty/error states present | component | `npm test -- sla` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_sla_engine.py` — tier-state computation incl. approaching-% scaling, NULL-score fallback, sub-MEDIUM on-track (D-12)
- [ ] `backend/tests/test_sla_policy.py` — policy CRUD + RBAC (admin/owner only)
- [ ] `backend/tests/test_escalation_engine.py` — exactly-once transition firing + D-08 reconciliation + audit coverage
- [ ] `backend/tests/test_escalation_channels.py` — per-channel payload shaping (Slack/Teams-Workflows/PagerDuty/SMTP) + Fernet encryption/masking + failure handling
- [ ] `backend/tests/test_mttr.py` — remediation-event capture across all REMEDIATED sites + MTTR-by-tier aggregate
- [ ] Shared fixtures: scored + NULL-score findings, tenant with tier policy, mock channel HTTP (httpx mock)

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
