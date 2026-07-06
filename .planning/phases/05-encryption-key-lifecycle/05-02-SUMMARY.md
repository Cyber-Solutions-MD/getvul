---
phase: 05-encryption-key-lifecycle
plan: "02"
subsystem: backend/startup + docs
tags: [encryption, startup-check, structlog, runbook, backend, docs, tdd]
requires:
  - 05-01
provides:
  - _check_secrets_at_startup()
  - ENCRYPTION_KEY_PLACEHOLDER + JWT_SECRET_PLACEHOLDER constants
  - startup lifespan wiring
  - docs/16-security.md runbook section
affects:
  - backend/app/main.py
  - backend/tests/test_encryption_rotation.py
  - docs/16-security.md
tech_stack:
  added: []
  patterns:
    - Startup check function called inside lifespan body (not at import time — avoids test collection breakage)
    - Structlog critical/warning by environment, never logging key material
    - Hard-fail RuntimeError in production, warn-and-continue in development
key_files:
  created: []
  modified:
    - backend/app/main.py
    - backend/tests/test_encryption_rotation.py
    - docs/16-security.md
decisions:
  - "D-10 hard-fail: RuntimeError in production when ENCRYPTION_KEY or JWT_SECRET_KEY is insecure"
  - "D-11 ENCRYPTION_KEY check: empty OR placeholder string → issue; non-placeholder non-Fernet → issue"
  - "D-12 JWT_SECRET_KEY check: placeholder string → issue"
  - "Pitfall 4 compliance: check lives inside lifespan body only, not at module import time"
  - "T-05-06 mitigation: only issue string logged, never key material"
  - "D-14 RTO <= 15 minutes: retrieve from vault + paste into .env + restart container"
  - "D-17 single-key model: one global ENCRYPTION_KEY covers all tenants' connector credentials"
metrics:
  duration: "~28 minutes"
  completed: "2026-07-06T00:00:00Z"
  tasks_completed: 2
  files_modified: 3
---

# Phase 05 Plan 02: Startup Secrets Check + Runbook Summary

Startup hard-fail for placeholder/invalid `ENCRYPTION_KEY`/`JWT_SECRET_KEY` in production (warns in development), plus the "Encryption Key Backup & Rotation" runbook in docs/16-security.md covering single-key model, off-box vault backup, ≤15-min RTO, rotate command sequence, and lost-key UI re-entry recovery.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing startup-check tests | 7667d3b | backend/tests/test_encryption_rotation.py |
| 1 (GREEN) | Implement _check_secrets_at_startup() + lifespan wiring | b4be320 | backend/app/main.py |
| 2 | Write Encryption Key Backup & Rotation runbook | 6879db7 | docs/16-security.md |

## What Was Built

### `_check_secrets_at_startup() -> list[str]` (backend/app/main.py)

Validates two secrets at startup:

1. **ENCRYPTION_KEY**: checks for empty/unset, placeholder literal match, and Fernet validity via `Fernet(key.encode())`. Invalid key appended as an issue string — key material never logged.
2. **JWT_SECRET_KEY**: checks for the placeholder literal `CHANGE-ME-IN-PRODUCTION`.

Behavior by environment:
- **development**: logs each issue as `structlog.warning("startup_secret_check_warning", issue=msg)`, returns issues list without raising.
- **production**: logs each issue as `structlog.critical("startup_secret_check_failed", issue=msg)`, then raises `RuntimeError` if any issues found.

Module-level constants `ENCRYPTION_KEY_PLACEHOLDER` and `JWT_SECRET_PLACEHOLDER` are copied verbatim from `config.py` defaults for reliable comparison.

### Lifespan wiring (backend/app/main.py)

`_check_secrets_at_startup()` is called as the **first statement** inside the `lifespan` async context manager body, before the scheduler start and Redis connection. A production RuntimeError propagates through FastAPI startup and prevents uvicorn serving traffic.

### Startup-check unit tests (backend/tests/test_encryption_rotation.py, appended)

6 tests appended to the existing Plan 01 test file, covering:
- Dev mode + placeholder encryption_key → issues returned, no raise
- Prod mode + placeholder encryption_key → RuntimeError raised
- Prod mode + invalid Fernet key → RuntimeError raised (ValueError path)
- Prod mode + valid key + non-placeholder JWT → empty list, no raise
- Prod mode + valid key + placeholder JWT → RuntimeError raised
- Dev mode + valid key + placeholder JWT → issues returned, no raise

All 6 pass. No DB dependency (fast unit tests).

### "Encryption Key Backup & Rotation" section (docs/16-security.md)

Inserted immediately after `## Credential Encryption` and before `## Audit Logging`. Covers:
- **Single-key model (D-17)**: one global `ENCRYPTION_KEY` covers connector credentials in `connector_configs.credentials_secret_arn` across all tenants; scope is connector credentials specifically (not SMTP).
- **Backup procedure (D-15)**: off-box vault (1Password / HashiCorp Vault / AWS/Azure Secrets Manager), named platform/security owner, not in repo/VM/DB backup.
- **RTO statement (D-14)**: ≤ 15 minutes — vault retrieval + paste into `.env` + container restart.
- **Rotation runbook**: exact 6-step sequence with `generate-key`, `rotate --dry-run`, `rotate --new-key`, `docker compose restart`, `verify`.
- **Atomic transaction note**: single transaction, abort-all-or-nothing, no mixed-key state.
- **Operational safety (T-05-08)**: ps-aux exposure note + env-var invocation alternative.
- **Lost-key recovery (D-16)**: ciphertexts are unrecoverable; re-generate key, restart, re-enter credentials via Settings > Connectors UI.

## Tests

| Test | Type | Status |
|------|------|--------|
| test_startup_check_encryption_placeholder_dev | unit | PASS |
| test_startup_check_encryption_placeholder_prod | unit | PASS |
| test_startup_check_encryption_invalid_prod | unit | PASS |
| test_startup_check_valid_key_ok | unit | PASS |
| test_startup_check_jwt_placeholder_prod | unit | PASS |
| test_startup_check_jwt_placeholder_dev | unit | PASS |
| (Plan 01 unit tests) | unit | PASS (4 tests) |
| (Plan 01 integration tests) | integration | SKIPPED (no Postgres) |

## Deviations from Plan

None — plan executed exactly as written.

## Security Notes

- T-05-05 (Spoofing / weak default): `_check_secrets_at_startup()` hard-fails boot in production for unset/placeholder/invalid keys. Dev logs loud structlog warning.
- T-05-06 (Information Disclosure — logging key value): Only issue string is logged, never `settings.encryption_key` or `settings.jwt_secret_key`.
- T-05-07 (Elevation of Privilege — backup key on same VM): Runbook prescribes off-box vault storage with named owner.
- T-05-08 (Information Disclosure — `--new-key` in ps aux): Runbook documents env-var invocation as safer alternative; accepted as operational risk per threat model.

## Threat Flags

None — all surfaces in this plan (startup check, docs) are within the threat model defined in 05-02-PLAN.md.

## Self-Check: PASSED

Files exist:
- `backend/app/main.py` — confirmed (contains `_check_secrets_at_startup`, lifespan wiring, placeholder constants)
- `backend/tests/test_encryption_rotation.py` — confirmed (6 startup-check tests appended)
- `docs/16-security.md` — confirmed (contains `## Encryption Key Backup & Rotation`)

Commits exist:
- `7667d3b` — test(05-02): failing startup-check tests (RED)
- `b4be320` — feat(05-02): _check_secrets_at_startup() implementation (GREEN)
- `6879db7` — docs(05-02): security runbook

Acceptance criteria verified:
- `grep -q "def _check_secrets_at_startup" backend/app/main.py` — PASS
- `grep -q "_check_secrets_at_startup()" backend/app/main.py` — PASS (inside lifespan)
- `grep -q "CHANGE-ME-generate-with-python" backend/app/main.py` — PASS
- `grep -q "CHANGE-ME-IN-PRODUCTION" backend/app/main.py` — PASS
- `grep -q 'settings.environment == "production"' backend/app/main.py` — PASS
- `grep -q "raise RuntimeError" backend/app/main.py` — PASS
- All 6 startup-check tests pass — PASS
- `grep -q "## Encryption Key Backup & Rotation" docs/16-security.md` — PASS
- `grep -qi "RTO" docs/16-security.md` — PASS
- `grep -qi "15 min" docs/16-security.md` — PASS
- `grep -q "python3 -m app.encryption generate-key" docs/16-security.md` — PASS
- `grep -q "python3 -m app.encryption rotate --new-key" docs/16-security.md` — PASS
- `grep -q "python3 -m app.encryption verify" docs/16-security.md` — PASS
- `grep -qi "vault\|1Password\|secrets manager" docs/16-security.md` — PASS
- `grep -qi "unrecoverable\|re-enter" docs/16-security.md` — PASS
- `grep -qi "one global\|single.*key\|all tenants" docs/16-security.md` — PASS
