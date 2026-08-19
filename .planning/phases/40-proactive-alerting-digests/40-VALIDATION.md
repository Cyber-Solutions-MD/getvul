---
phase: 40
slug: proactive-alerting-digests
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-19
---

# Phase 40 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest (frontend) |
| **Config file** | backend/pyproject.toml (pytest) / frontend vitest config |
| **Quick run command** | `ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest backend/tests/test_alerts_kev_epss.py` (per-file — see backend pytest env memory) |
| **Full suite command** | `ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest backend/tests/` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the affected per-file test (`pytest backend/tests/test_<file>.py`)
- **After every plan wave:** Run the full backend suite + affected vitest tests
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Seeded by plan-phase; the planner/executor fill exact task IDs and commands during planning/execution.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-00-01 | 00 | 0 | ALERT-01/02/03 | — | N/A (test scaffolding) | unit | `pytest backend/tests/test_alerts_kev_epss.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_alerts_kev_epss.py` — stubs for ALERT-01 (new-KEV / high-EPSS asset-match firing)
- [ ] `backend/tests/test_digests.py` — stubs for ALERT-02 (scheduled digest delivery, send-hour gate, SLA due/breaching content)
- [ ] `backend/tests/test_alerting_settings.py` — stubs for ALERT-03 (tenant-configurable rules/channels + audit)
- [ ] Frontend vitest test for the alerting settings pane / digest surfaces
- [ ] Shared fixtures for tenant + asset + enrichment seeding (extend existing conftest)

*Note: no `test_alerts.py` exists today — Wave 0 must create the alerting test files.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Slack/Teams/email message actually renders/delivers to a live channel | ALERT-01, ALERT-02 | External delivery to third-party services can't be asserted in unit tests (dispatch is SSRF-guarded + mocked in tests) | Configure a real channel in a test tenant, trigger an alert/digest, confirm receipt and formatting |

*Automated tests assert dispatch fan-out, payload shape, and gating; live delivery is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
