---
phase: 34
slug: historical-recompute-consumer-cutover
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-11
---

# Phase 34 — Validation Strategy

> Highest-risk phase. Planner populates the per-task map. Fixture-level validation only (no live/at-scale data here).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend, if any) |
| **Config file** | backend/pyproject.toml |
| **Quick run** | `cd backend && ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_risk_recompute.py -x` |
| **Full suite** | per-file across touched recompute/cutover/trend/alert/sort/ai-batch test files |
| **Estimated runtime** | ~5–30s per file |

Note: real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY required; run per-file (MEMORY getvul-backend-pytest-env).

---

## Sampling Rate

- **After every task commit:** run the touched test file
- **After every wave:** run all Phase 34 test files (per-file)
- **Before `/gsd-verify-work`:** full Phase 34 suite green + `alembic upgrade head` clean + cutover-flag-OFF gate grep (no consumer reads the new score with the flag off)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Planner fills — every RISK-07..10 → ≥1 automated test. Fixtures REQUIRED for: kill-mid-run-and-resume (RISK-07), single-VM load (RISK-07), flag-OFF vs flag-ON consumer behavior (RISK-08), version-boundary spanning cutover with no alert-storm/trend-cliff (RISK-10), pre/post threshold diff + ack gating (RISK-09).

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| (planner fills) | | | RISK-07..10 | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_risk_recompute.py` — idempotency + resume-from-cursor (kill-mid-run) + throttle + per-tenant isolation + fixture load test
- [ ] `backend/tests/test_risk_cutover.py` — flag-OFF (old score) vs flag-ON (new score) for sort="triage", trend, AI-batch selector; SLA stays severity-keyed
- [ ] `backend/tests/test_risk_boundary_guard.py` — spike-notification + trend across a risk_model_version boundary: no storm, no cliff
- [ ] threshold pre/post diff + per-tenant ack fixture (RISK-09)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real at-scale per-tenant backfill | RISK-07 | No live/at-scale data in env | Run the backfill on a real stack; confirm idempotent/resumable/throttled at production row counts |
| Live consumer cutover flip | RISK-08 | Flag stays OFF here (user decision) | Flip the cutover flag on a validated live stack; confirm sort/trend/AI-batch read the new score, SLA unchanged |

---

## Validation Sign-Off

- [ ] Every RISK-07..10 maps to ≥1 automated (fixture) test
- [ ] kill-mid-run-and-resume + load fixtures present (RISK-07)
- [ ] flag-OFF gate proven (no consumer reads new score with flag off)
- [ ] boundary fixture proves no storm / no cliff (RISK-10)
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
