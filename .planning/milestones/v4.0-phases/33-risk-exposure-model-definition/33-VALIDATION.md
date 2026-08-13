---
phase: 33
slug: risk-exposure-model-definition
status: draft
nyquist_compliant: true
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
| **Quick run (backend)** | `cd backend && ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_risk_exposure_service.py -x` |
| **Quick run (frontend)** | `cd frontend && npx vitest run src/components/vulnerabilities/drill-panel.test.tsx src/components/vulnerabilities/drill-panel-mobile.test.tsx` |
| **Full suite command** | per-file across touched risk/vuln/asset test files; frontend `npm test` at wave gate |
| **Estimated runtime** | ~5–20s per backend file; ~5s per frontend file |

Note: backend tests require a real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY, run per-file (MEMORY getvul-backend-pytest-env). Frontend WCAG AA claims are unproven without the Playwright axe sweep (MEMORY getvul-axe-sweep-not-run-during-exec) — reason about token contrast manually; the RISK-05 section is verified visually at the human-verify checkpoint.

---

## Sampling Rate

- **After every task commit:** run the touched test file
- **After every plan wave:** run all Phase 33 test files (per-file); frontend `npm test` after wave 3
- **Before `/gsd-verify-work`:** full Phase 33 suite green + `alembic upgrade head` clean (heads = 043) + zero-consumer grep gate
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Every RISK-01..06 → ≥1 automated test. Fixtures REQUIRED for: KEV-floor (low-sev KEV > identical non-KEV), corroboration (1 vs 3 scanners), determinism (same inputs → same score), shadow (no automated consumer reads the new column — grep gate).

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 33-01 T1 | 01 | 1 | RISK-01 (determinism) | unit | `pytest tests/test_risk_exposure_service.py -x -k deterministic` | ⬜ pending |
| 33-01 T1 | 01 | 1 | RISK-03 (KEV floor, fixture) | unit fixture | `pytest tests/test_risk_exposure_service.py -x -k kev_floor` | ⬜ pending |
| 33-01 T2 | 01 | 1 | RISK-02 (per-finding persist) | integration | `pytest tests/test_risk_exposure_service.py -x -k persists` | ⬜ pending |
| 33-01 T3 | 01 | 1 | RISK-05 (response fields wired) + RISK-06 (version stamped) | integration | `pytest tests/test_risk_exposure_service.py -x -k "returns_risk_fields or persists"` | ⬜ pending |
| 33-01 T3 | 01 | 1 | RISK-06 (zero-consumer gate) | static grep | `grep -rn "risk_exposure_score\|risk_exposure_breakdown" backend/app --include="*.py" \| grep -v risk_exposure_service.py` (only models/schemas/service/sync) | ⬜ pending |
| 33-02 T1/T2 | 02 | 2 | RISK-01 (full formula, native per-source) | unit | `pytest tests/test_risk_exposure_service.py -x -k "native or all_components"` | ⬜ pending |
| 33-02 T1/T2 | 02 | 2 | RISK-04 (corroboration, fixture 1 vs 3) | unit fixture | `pytest tests/test_risk_exposure_service.py -x -k corroboration` | ⬜ pending |
| 33-02 T1/T2 | 02 | 2 | RISK-03 (KEV floor under full formula) | unit fixture | `pytest tests/test_risk_exposure_service.py -x -k kev_floor` | ⬜ pending |
| 33-03 T1/T2 | 03 | 3 | RISK-02 (asset MAX rollup + sortable index) | integration | `pytest tests/test_risk_exposure_service.py -x -k rollup` + `alembic heads` = 043 | ⬜ pending |
| 33-03 T1/T3 | 03 | 3 | RISK-06 (tier centralization, zero behavior change) | characterization regression | `pytest tests/test_risk_tier_distribution.py -x` (green before AND after refactor) | ⬜ pending |
| 33-04 T2 | 04 | 3 | RISK-05 (DrillPanel breakdown, shadow-labeled) | unit RTL | `npx vitest run src/components/vulnerabilities/drill-panel.test.tsx src/components/vulnerabilities/drill-panel-mobile.test.tsx` | ⬜ pending |
| 33-04 T3 | 04 | 3 | RISK-05 (live visual, shadow-labeled) | human-verify | checkpoint (live stack) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Coverage check:** RISK-01 ✓ (33-01 T1, 33-02) · RISK-02 ✓ (33-01 T2, 33-03) · RISK-03 ✓ (33-01/33-02 fixtures) · RISK-04 ✓ (33-02 fixture) · RISK-05 ✓ (33-01 T3 wire, 33-04 RTL + human-verify) · RISK-06 ✓ (33-01 version+grep gate, 33-03 characterization).

---

## Wave 0 Requirements

- [ ] `backend/tests/test_risk_exposure_service.py` (33-01 T1) — determinism + KEV-floor fixture + per-finding persistence + response-shape; extended in 33-02 (native per-source + corroboration fixture + all-components + soft-null) and 33-03 (asset MAX rollup).
- [ ] `backend/tests/test_risk_tier_distribution.py` (33-03 T1) — characterization regression for the 3 distribution-bucket endpoints (must pass before AND after the centralization refactor).
- [ ] RTL cases in `drill-panel.test.tsx` + `drill-panel-mobile.test.tsx` (33-04 T2) — Risk Exposure section renders (score + breakdown rows + preview label + conditional KEV chip + null-safe). No standalone drill-content.test.tsx (DrillContent tested via both wrappers).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DrillPanel breakdown visual ("why is this an 82"), shadow-labeled, KEV-floor chip, desktop + mobile | RISK-05 | Visual on live stack | 33-04 Task 3 checkpoint — confirm per-input breakdown renders, is clearly shadow/preview-labeled, KEV chip matches CISA-KEV styling, and NO list/dashboard sort or count changed |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies (33-04 T3 is a human-verify following the RTL-covered T2)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] No watch-mode flags
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Every RISK-01..06 maps to ≥1 automated test (see Coverage check)

**Approval:** planner-populated 2026-08-11
