---
phase: 33
slug: risk-exposure-model-definition
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-11
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Planner populates the per-task map.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend) |
| **Config file** | backend/pyproject.toml · frontend/vitest.config.ts |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_risk_exposure.py -x` |
| **Full suite command** | per-file across touched risk/vuln/asset test files |
| **Estimated runtime** | ~5–20s per file |

Note: backend tests require a real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY, run per-file (MEMORY getvul-backend-pytest-env).

---

## Sampling Rate

- **After every task commit:** run the touched test file
- **After every plan wave:** run all Phase 33 test files (per-file)
- **Before `/gsd-verify-work`:** full Phase 33 suite green + `alembic upgrade head` clean
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Planner fills — every RISK-01..06 → ≥1 automated test. Fixtures REQUIRED for: KEV-floor (low-sev KEV > identical non-KEV), corroboration (1 vs 3 scanners), determinism (same inputs → same score), shadow (no automated consumer reads the new column).

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| (planner fills) | | | RISK-01..06 | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_risk_exposure.py` — determinism + KEV-floor + corroboration + native-scale normalization + asset rollup
- [ ] realistic fixtures for KEV-floor and 1-vs-3-scanner corroboration
- [ ] frontend `risk-exposure-breakdown.test.tsx` (DrillPanel breakdown, shadow-labeled)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DrillPanel breakdown visual ("why is this an 82"), shadow-labeled | RISK-05 | Visual on live stack | Confirm per-input breakdown renders + is clearly shadow/preview-labeled |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
