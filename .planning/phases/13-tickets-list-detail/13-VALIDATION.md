---
phase: 13
slug: tickets-list-detail
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-01
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest/jest (frontend — confirm in Wave 0) |
| **Config file** | `backend/pyproject.toml` / frontend test config (planner to confirm) |
| **Quick run command** | `cd backend && pytest tests/ticketing -q` |
| **Full suite command** | `cd backend && pytest -q` + `cd frontend && npm test` |
| **Estimated runtime** | ~60–120 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command for the affected subsystem
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | UX-05-01..06 | TBD | TBD | unit/integration | TBD | ❌ W0 | ⬜ pending |

*Planner fills this map from the final PLAN.md task IDs. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Confirm backend ticketing test module + fixtures (`backend/tests/ticketing/`)
- [ ] Confirm frontend test runner config + component test seam
- [ ] Migration test seam (alembic upgrade/downgrade round-trip for 026/027/028)

*Planner refines after reading RESEARCH.md Validation Architecture section.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Provider gradient marks render correct tint | UX-05-02 | Visual | Open `/tickets`, confirm Jira blue / Asana coral / GitHub violet marks |
| Two-column detail layout + sticky 340px rail | UX-05-04 | Visual/responsive | Open `/tickets/[id]`, verify rail stickiness + 900px stack breakpoint |
| Status/SLA pill colors match locked contract | UX-05-03 | Visual | Verify pill color families distinct from severity |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
