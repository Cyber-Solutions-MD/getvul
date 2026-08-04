---
phase: 30
slug: correlation-schema-fix
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-04
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio, `asyncio_mode = "auto"` (backend/pyproject.toml:74-82) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret ENVIRONMENT=test pytest tests/test_correlation_service.py -v` (per-file only — repo memory: whole-tests/ dir flakes) |
| **Full suite command** | `cd backend && alembic upgrade head && pytest -v --cov=app --cov-report=xml` (matches CI ci.yml:86-96) |
| **Estimated runtime** | ~10-20 seconds (single test file) |

Migration must be applied first: `alembic upgrade head` (CI runs this as a separate step before pytest — the test DB schema comes from migrations, not model reflection).

---

## Sampling Rate

- **After every task commit:** Run the quick run command (`pytest tests/test_correlation_service.py -v`)
- **After every plan wave:** `pytest tests/test_correlation_service.py tests/test_vuln_source_filter.py tests/test_vulnerabilities.py -v` (adjacent vulnerability-domain files — catches accidental `sources_count`/`service.py` read regressions at lines 194/227/475)
- **Before `/gsd-verify-work`:** Full suite green + `alembic upgrade head` exit 0 against a fresh postgres:16-alpine
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 1 | CORR-01 / CORR-03 | — | RED SC#4 test; tenant_a-scoped seed | unit/integration | `pytest tests/test_correlation_service.py -v` (expect RED) | ❌ W0 (new file) | ⬜ pending |
| 30-01-02 | 01 | 1 | CORR-01 | T-30-01 / T-30-02 | checkpoint:decision — gate irreversible FK-column drop | manual (gate) | N/A (blocking checkpoint) | — | ⬜ pending |
| 30-01-03 | 01 | 1 | CORR-01 / CORR-03 | T-30-01 / T-30-02 / T-30-03 | tenant-scoped queries preserved; require_viewer unchanged | integration | `alembic upgrade head && pytest tests/test_correlation_service.py::test_qualys_rapid7_only_correlation_no_longer_silently_dropped -x -q` | ❌ W0 (migration+service new) | ⬜ pending |
| 30-02-01 | 02 | 2 | CORR-02 / CORR-03 | T-30-05 / T-30-06 | per-tenant loop; COALESCE zero-loss; no global aggregate | static/unit | `python -c "…ast.parse + COALESCE/compute_risk_scores/is_active asserts…"` | ❌ W0 (new script) | ⬜ pending |
| 30-02-02 | 02 | 2 | CORR-02 / CORR-03 | T-30-05 | bands + count-invariant + cross-tenant isolation | integration | `pytest tests/test_correlation_service.py -x -q` | ✅ (extends 30-01-01) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_correlation_service.py` — does not exist today (confirmed via grep). Created in task 30-01-01 (SC#4 regression), extended in 30-02-02 (bands/invariant/tenant-scope).
- [ ] `backend/alembic/versions/034_add_correlation_sources.py` — new migration (task 30-01-03). CI's `alembic upgrade head` step is its own gate, separate from pytest.
- [ ] `backend/scripts/recorrelate_all_tenants.py` — new script (task 30-02-01); required before SC#2 can be verified per-tenant in any real (non-fixture) environment.

Shared fixtures (`db_session`, `tenant_a`, `tenant_b`) already exist in `backend/tests/conftest.py` — no new fixtures needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Post-deploy per-tenant zero-loss against real production data | CORR-02 | The dev DB has 0 rows; true zero-loss can only be observed against production-scale data after the one-time script runs | After `alembic upgrade head`, run `docker compose exec backend python scripts/recorrelate_all_tenants.py`; confirm every `recorrelated_tenant` log line shows `inconsistent_rows_after=0`. Never run the zero-loss query between the migration and the script (RESEARCH Pitfall 5). |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
