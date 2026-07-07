---
status: testing
phase: 05-encryption-key-lifecycle
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md]
started: 2026-07-06T15:00:45Z
updated: 2026-07-06T15:12:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running backend/service and clear ephemeral state (containers, caches). Start the stack from scratch (`docker compose up`) with a valid Fernet ENCRYPTION_KEY. Backend boots with no errors or tracebacks, `_check_secrets_at_startup()` passes silently, and a primary request (health check or an authenticated API call) returns live data.
result: pass
note: "Full stack booted from stopped state (postgres+redis+backend). Alembic migrations applied, scheduler + daily snapshots ran, startup secret check passed silently (dev + valid keys). GET /health returned HTTP 200 {\"status\":\"ok\",\"service\":\"getvul-api\"}."

### 2. Generate a New Key
expected: `docker compose exec -T backend python3 -m app.encryption generate-key` prints a single fresh Fernet key on stdout (44-char base64), with no traceback. The key is a valid Fernet key (usable in the rotate step).
result: pass
note: "Printed a 44-char base64 key; confirmed valid Fernet key that encrypt/decrypt round-trips."

### 3. Verify Command Against Running Stack
expected: `docker compose exec -T backend python3 -m app.encryption verify` runs against a stack with seeded connector rows and prints `N OK / M failing` with no traceback; exits 0 when all rows decrypt with the current key.
result: pass
note: "Live verify in container against dev DB printed '0 OK / 0 failing' exit 0 (no encrypted-cred rows seeded). Against isolated getvul_test DB with one seeded encrypted connector, printed '1 OK / 0 failing' exit 0. No traceback."

### 4. Rotate Dry-Run
expected: `python3 -m app.encryption rotate --new-key <key> --dry-run` shows a backup reminder and prints the count of rows / tenants that would be rotated, then rolls back without writing anything. No credentials are actually re-encrypted; a follow-up `verify` still passes with the old key.
result: pass
note: "Dry-run printed backup reminder + '[dry-run] Would rotate 1 rows across 1 tenants' + '[dry-run] No changes were written', exit 0. Follow-up verify with old key still '1 OK / 0 failing' — nothing written."

### 5. Full Key Rotation
expected: `python3 -m app.encryption rotate --new-key <newkey> --yes` re-encrypts all connector credentials in a single transaction, prints a restart instruction WITHOUT echoing the actual key value, and does NOT modify `.env`. After updating ENCRYPTION_KEY in .env and restarting, `verify` prints all rows OK with the new key.
result: issue
reported: "The documented full rotation command crashes before completing. `python3 -m app.encryption rotate --new-key <key> --yes` raises sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'audit_logs.user_id' could not find table 'users'. Rotation never completes. Reproduced in the real container deployment path, not just locally. verify/dry-run work because they don't write an audit row; the actual rotate does (D-08) and fails."
severity: blocker

### 6. Rotation Aborts on Bad Data (Abort-All-or-Nothing)
expected: If any row cannot be decrypted with the old key during rotation, the whole operation rolls back with a RotationPreflightError — no rows are left in a mixed-key state. Good rows remain decryptable with the original key afterward (no partial re-encryption).
result: pass
note: "Integration test test_rotate_aborts_on_bad_row and test_rotate_aborts_on_malformed_json_shapes PASS against live Postgres. Independently confirmed: when the Test 5 rotate crashed, the transaction rolled back cleanly — old key still verified '1 OK', no mixed-key state. Abort-all-or-nothing integrity holds."

### 7. Production Startup Rejection — Placeholder/Invalid ENCRYPTION_KEY
expected: With `ENVIRONMENT=production` and `ENCRYPTION_KEY` set to the placeholder (or unset/invalid), the backend container fails to start — uvicorn propagates the `RuntimeError` from `_check_secrets_at_startup()` to a non-zero container exit — and never serves traffic. A structlog `startup_secret_check_failed` critical line is logged (without the key value).
result: pass
note: "Drove _check_secrets_at_startup() directly: production + placeholder / empty / invalid-Fernet ENCRYPTION_KEY all raised RuntimeError and logged critical 'startup_secret_check_failed' with only the issue string (no key material). Positive control (prod + valid) returned []."

### 8. Production Startup Rejection — Placeholder JWT_SECRET_KEY
expected: With `ENVIRONMENT=production`, a valid ENCRYPTION_KEY, but `JWT_SECRET_KEY` left as the `CHANGE-ME-IN-PRODUCTION` placeholder, the backend container fails to start with a RuntimeError and never serves traffic.
result: pass
note: "production + valid ENCRYPTION_KEY + placeholder JWT_SECRET_KEY raised RuntimeError, logged critical. Confirmed via direct invocation."

### 9. Development Warn-and-Continue
expected: With `ENVIRONMENT=development` and a placeholder/invalid ENCRYPTION_KEY or JWT_SECRET_KEY, the backend logs a loud structlog `startup_secret_check_warning` for each issue but still starts and serves traffic (no hard fail in dev).
result: pass
note: "development + placeholder ENCRYPTION_KEY and development + placeholder JWT each logged 'startup_secret_check_warning' and returned the issues list WITHOUT raising. No hard fail in dev."

### 10. Rotation Runbook Documentation
expected: `docs/16-security.md` contains an "Encryption Key Backup & Rotation" section describing the single global-key model, off-box vault backup with a named owner, a ≤15-minute RTO, the exact generate-key → rotate --dry-run → rotate --new-key → restart → verify sequence, and lost-key recovery (re-enter credentials via Settings > Connectors).
result: pass
note: "Section present with all elements: single global-key model ('one global'), off-box vault backup, RTO ≤15 min, full generate-key → rotate --new-key <KEY> --dry-run → rotate --new-key <KEY> → docker compose restart → verify sequence, unrecoverable/re-enter recovery."

## Summary

total: 10
passed: 9
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "python3 -m app.encryption rotate --new-key <key> completes a full key rotation, re-encrypting all connector credentials in a single transaction"
  status: failed
  reason: "User reported: The documented full rotation command crashes with sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'audit_logs.user_id' could not find table 'users'. Rotation never completes. Reproduced in the container deployment path. verify/dry-run work; the real rotate fails at the audit write (D-08)."
  severity: blocker
  test: 5
  root_cause: "rotate_credentials() writes an AuditLog row directly (decision D-08). When run via the standalone CLI `python -m app.encryption`, only ConnectorConfig is imported (from app.ticketing.models). Persisting AuditLog triggers SQLAlchemy mapper configuration, which must resolve the audit_logs.user_id -> users.id foreign key. The User model is never imported in the CLI process, so the 'users' table is absent from the registry/metadata and mapper config raises NoReferencedTableError before any commit. Integration test test_audit_event masks this because conftest.py eagerly imports all models (assets, audit, notifications, tenants, vulnerabilities) at load time."
  artifacts:
    - path: "backend/app/encryption.py"
      issue: "AuditLog write in rotate_credentials() has no guarantee the User model (and other models referenced by audit_logs FKs) is imported/registered when run as a standalone CLI; mapper config fails."
    - path: "backend/tests/test_encryption_rotation.py"
      issue: "test_audit_event runs under conftest's eager model imports, so it never exercises the standalone-CLI import graph that real operators use — the failure is invisible to the suite."
  missing:
    - "Import the User model (and any other models referenced by AuditLog foreign keys) inside encryption.py / rotate_credentials() before the audit write, so SQLAlchemy mapper configuration can resolve audit_logs.user_id -> users.id in a standalone CLI process."
    - "Add a regression test that invokes the rotate CLI in a subprocess (or with a minimal import graph, not conftest's eager imports) against a seeded encrypted row, asserting the rotation completes and writes an AuditLog — reproducing the real operator path."
  debug_session: ""
