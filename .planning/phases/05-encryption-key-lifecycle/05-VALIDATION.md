---
phase: 5
slug: encryption-key-lifecycle
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-03
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio 0.24 (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `cd backend && pytest tests/test_encryption_rotation.py -x -q` |
| **Full suite command** | `cd backend && pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~30s quick / ~2–4 min full (integration needs real Postgres) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_encryption_rotation.py -x -q`
- **After every plan wave:** Run `cd backend && pytest tests/ -q --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green (including the real-Postgres SC#4 rotation test)
- **Max feedback latency:** ~30 seconds (quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | PROD-05-02 | — | `_fernet_for(key)` builds Fernet from explicit key; invalid key raises `ValueError` | unit | `cd backend && pytest tests/test_encryption_rotation.py::test_fernet_for -x` | ❌ W0 | ⬜ pending |
| 5-01-02 | 01 | 1 | PROD-05-02 | T-5 (key material) | Rotate re-encrypts all rows in one txn; pre-flight decrypt-all bypasses silent `get_decrypted_credentials`; abort+rollback on any failure | integration | `cd backend && pytest tests/test_encryption_rotation.py::test_rotate_all_rows -x` | ❌ W0 | ⬜ pending |
| 5-01-03 | 01 | 1 | PROD-05-02 | — | Post-commit round-trip decrypt with NEW key verifies before commit | integration | `cd backend && pytest tests/test_encryption_rotation.py::test_rotate_verifies -x` | ❌ W0 | ⬜ pending |
| 5-01-04 | 01 | 1 | PROD-05-03 | — | `--dry-run` writes nothing, reports row/tenant count | unit/integration | `cd backend && pytest tests/test_encryption_rotation.py::test_dry_run_no_rows -x` | ❌ W0 | ⬜ pending |
| 5-01-05 | 01 | 1 | PROD-05-03 | — | `verify` reports N OK / M failing, rotates nothing | integration | `cd backend && pytest tests/test_encryption_rotation.py::test_verify_all_ok -x` | ❌ W0 | ⬜ pending |
| 5-01-06 | 01 | 1 | PROD-05-03 | — | `generate-key` prints a valid Fernet key | unit | `cd backend && pytest tests/test_encryption_rotation.py::test_generate_key -x` | ❌ W0 | ⬜ pending |
| 5-01-07 | 01 | 1 | PROD-05-02 | — | Success emits `encryption.key_rotated` audit row (no key material), system CLI actor | integration | `cd backend && pytest tests/test_encryption_rotation.py::test_audit_event -x` | ❌ W0 | ⬜ pending |
| 5-01-08 | 01 | 1 | PROD-05-02 | — | SC#4: A→B rotate, decrypt-all OK, revert to A fails to decrypt | integration | `cd backend && pytest tests/test_encryption_rotation.py::test_sc4_rotation_is_real -x` | ❌ W0 | ⬜ pending |
| 5-02-01 | 02 | 1 | PROD-05-04 | T-5 (weak default key) | Startup with placeholder/unset/invalid encryption key: warn in dev, raise in prod | unit | `cd backend && pytest tests/test_encryption_rotation.py::test_startup_check_encryption -x` | ❌ W0 | ⬜ pending |
| 5-02-02 | 02 | 1 | PROD-05-04 | — | Startup with placeholder JWT secret: warn in dev, raise in prod | unit | `cd backend && pytest tests/test_encryption_rotation.py::test_startup_check_jwt -x` | ❌ W0 | ⬜ pending |
| 5-02-03 | 02 | 1 | PROD-05-01 | — | Runbook section present with RTO statement + concrete commands | doc check | `grep -q "Encryption Key Backup & Rotation" docs/16-security.md && grep -qi "RTO" docs/16-security.md && echo PASS` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_encryption_rotation.py` — new test file covering all PROD-05-01..04 assertions above
- [x] No framework install needed — pytest + pytest-asyncio already in `backend/pyproject.toml` [VERIFIED by research]
- [x] No conftest changes needed — `db_session`, `tenant_a`, `tenant_b`, `_reset_engine_pool` fixtures already present [VERIFIED by research]

*The single new test file is the only Wave 0 dependency; it is created inside Plan 01 as the executor writes each rotation feature.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Runbook commands are operationally correct (paste-key-and-restart restore, RTO ≤ 15 min) | PROD-05-01 | Prose/runbook quality can't be asserted by grep beyond section+RTO presence | Reviewer reads `docs/16-security.md` "Encryption Key Backup & Rotation": confirms concrete `python -m app.encryption` commands, lost-key recovery via UI re-entry, off-box vault storage, single-key model note |
| Lost-key recovery (re-enter credentials via UI) actually re-encrypts under new key | PROD-05-01 | Requires a running stack + UI interaction; out of automated scope | Optional smoke: on a test VM, generate a fresh key, restart, re-enter one connector's creds in UI, confirm sync succeeds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`test_encryption_rotation.py`)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
