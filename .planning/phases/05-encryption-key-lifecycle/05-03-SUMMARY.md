---
phase: 05-encryption-key-lifecycle
plan: "03"
subsystem: backend/encryption
tags: [encryption, key-rotation, cli, sqlalchemy, mapper-config, regression, backend, gap-closure]
dependency_graph:
  requires:
    - 05-01 (rotate_credentials() + CLI)
    - 05-02 (_check_secrets_at_startup + startup guard)
  provides:
    - rotate_credentials() resolves audit_logs FKs in standalone CLI process
    - subprocess regression test guards against mapper-config regression
  affects:
    - backend/app/encryption.py (rotate_credentials import block)
    - backend/tests/test_encryption_rotation.py (new subprocess test)
tech_stack:
  added: []
  patterns:
    - function-local import for SQLAlchemy mapper registration side-effect
    - subprocess regression test (fresh interpreter, no conftest masking)
key_files:
  modified:
    - backend/app/encryption.py
    - backend/tests/test_encryption_rotation.py
decisions:
  - D-08 direct AuditLog write preserved unchanged; only the import block was extended
  - Import kept function-local (not hoisted to module top-level) to preserve lazy-import pattern throughout encryption.py
  - noqa F401 applied because the import exists solely for SQLAlchemy mapper registration side-effect
  - Subprocess test uses os.environ.copy() and overrides ENCRYPTION_KEY so the CLI reads the correct OLD key
metrics:
  duration: "~10 minutes"
  completed: "2026-07-07"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 05 Plan 03: Rotate CLI Mapper-Config Gap Closure Summary

**One-liner:** Function-local `from app.tenants import models` inside `rotate_credentials()` registers User + Tenant tables before the AuditLog write, fixing the NoReferencedTableError that made the documented `python -m app.encryption rotate` command non-functional in standalone CLI context; a subprocess regression test guards against recurrence.

## What Was Built

### Task 1: Register User + Tenant models inside rotate_credentials()

Added a function-local import `from app.tenants import models as _tenants_models` (with `noqa: F401`) to the existing lazy-import block inside `rotate_credentials()` in `backend/app/encryption.py`, placed before the `from app.ticketing.models import ConnectorConfig` line and before any `db.add(log)` call.

**Root cause addressed:** `AuditLog` (in `app/audit.py`) carries two foreign keys — `user_id -> users.id` and `tenant_id -> tenants.id`. Both `users` and `tenants` tables are defined in `app/tenants/models.py`. When `rotate_credentials()` runs via the standalone CLI (`python -m app.encryption`), only `ConnectorConfig` and `AuditLog` were imported into the process. Persisting `AuditLog` triggered SQLAlchemy mapper configuration which must resolve those FK targets — but since `app.tenants.models` was never imported, the `users`/`tenants` tables were absent from the SQLAlchemy registry, causing `NoReferencedTableError` before any commit. The eager imports in `conftest.py` (lines 44–49) masked this in the test suite.

**Fix:** One import. `from app.tenants import models as _tenants_models` registers both `User.__tablename__ == "users"` and `Tenant.__tablename__ == "tenants"` as a side effect, resolving both FK targets. Import kept function-local (not module-level) to preserve the existing lazy-import pattern throughout `encryption.py`.

### Task 2: Subprocess regression test

Appended `test_rotate_cli_subprocess_completes_and_audits` to `backend/tests/test_encryption_rotation.py` and added `import os`, `import subprocess`, `import sys` at the top of the file.

The test:
1. Seeds one `ConnectorConfig` row with `{"api_key": "cli-subprocess-secret"}` encrypted under `key_a`
2. Invokes `python -m app.encryption rotate --new-key key_b --yes` in a subprocess (`subprocess.run`) from the `backend/` directory, passing `ENCRYPTION_KEY=key_a` in the env
3. Asserts `proc.returncode == 0`, `"NoReferencedTableError" not in proc.stderr`, `"Rotated 1 rows" in proc.stdout`
4. Opens a FRESH async session to assert one `encryption.key_rotated` AuditLog row with `user_email == "system:cli"` exists
5. Asserts the row's credential was re-encrypted under `key_b` (can decrypt to `"cli-subprocess-secret"`)
6. Asserts neither `key_a` nor `key_b` appear in `proc.stdout` (T-05-01 key-echo discipline)

The test uses the existing `db_session` + `tenant_a` fixtures, so it skips cleanly when Postgres is unreachable (consistent with the rest of the file).

**Why this is a valid regression guard:** The subprocess is a fresh Python interpreter that does NOT import `conftest.py`. This is the exact import graph a container operator hits with `docker exec ... python -m app.encryption rotate`. A test that called `rotate_credentials()` directly in-process would falsely pass on the broken code because conftest's eager imports paper over the gap.

## Verification Results

- `grep -q "from app.tenants import models" backend/app/encryption.py` — PASS
- Import inside `rotate_credentials()` before `db.add(log)` — PASS (verified via awk)
- `python3 -c "import ast; ast.parse(...)"` — PASS (no syntax errors)
- Existing `from app.audit import AuditLog` intact — PASS
- No module-level tenants import added — PASS (count = 0)
- `pytest tests/test_encryption_rotation.py -k "cli_subprocess" -x -q` — **1 passed**
- `pytest tests/test_encryption_rotation.py -q --tb=short` — **19 passed, 1 warning**

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations Addressed

| Threat ID | Status |
|-----------|--------|
| T-05-09 (DoS: rotate CLI aborts before commit) | Mitigated — Task 1 fix |
| T-05-10 (Repudiation: rotation lands without audit row) | Mitigated — Task 2 asserts AuditLog row |
| T-05-01 (Info Disclosure: key material in child stdout) | Mitigated — Task 2 asserts no key in stdout |

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary surface introduced. The fix is a single function-local import.

## Known Stubs

None — no hardcoded empty values or placeholder data in the modified code paths.

## Self-Check: PASSED

- `backend/app/encryption.py` exists and contains `from app.tenants import models`
- `backend/tests/test_encryption_rotation.py` exists and contains `def test_rotate_cli_subprocess_completes_and_audits`
- Commit `dd72e40` exists (Task 1 fix)
- Commit `6b5658f` exists (Task 2 regression test)
- All 19 rotation tests pass
