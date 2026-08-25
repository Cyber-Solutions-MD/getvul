---
phase: 39
slug: exception-risk-acceptance-workflow
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-18
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + Playwright (frontend e2e) |
| **Config file** | backend/pyproject.toml / backend/pytest.ini |
| **Quick run command** | `cd backend && pytest tests/test_exceptions*.py` (per-file — see backend-pytest-env memory) |
| **Full suite command** | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest` |
| **Estimated runtime** | ~60–120 seconds (backend); e2e separate |

---

## Sampling Rate

- **After every task commit:** Run the exception-specific test file(s)
- **After every plan wave:** Run the full backend suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

*Seeded by plan-phase (draft). validate-phase / the planner fill task IDs, commands, and threat refs from the finalized PLAN.md files.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 1 | EXC-01 | T-39-01 / — | Only require_analyst can grant/revoke; tenant-scoped | unit | `pytest tests/test_exceptions_api.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_exceptions_api.py` — grant / list / revoke endpoint stubs for EXC-01, EXC-03
- [ ] `backend/tests/test_exceptions_exclusion.py` — compute-on-read exclusion join stubs for EXC-02, EXC-04
- [ ] Existing pytest infrastructure + conftest fixtures cover tenant/auth setup

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Exception form + list visual (expiring-soon badge, expiry sort/filter) | EXC-01 / D-19 | Visual/interaction fidelity per UI-SPEC | Follow UI-SPEC acceptance walkthrough; verify against sketch-findings-getvul |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
