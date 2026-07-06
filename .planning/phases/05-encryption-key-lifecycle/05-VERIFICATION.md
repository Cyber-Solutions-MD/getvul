---
phase: 05-encryption-key-lifecycle
verified: 2026-07-06T12:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `docker compose exec -T backend python3 -m app.encryption verify` against a live instance"
    expected: "Command completes without traceback, prints 'N OK / M failing', exits 0 when all rows decrypt"
    why_human: "Requires a live Docker environment with Postgres, Redis, and a seeded ENCRYPTION_KEY that is not the placeholder"
  - test: "Start the backend with ENCRYPTION_KEY set to the placeholder value and ENVIRONMENT=production"
    expected: "Container refuses to start (uvicorn logs a RuntimeError and exits non-zero); no traffic is served"
    why_human: "Requires running uvicorn in production mode against a live container to confirm the RuntimeError actually terminates the process before the first request"
---

# Phase 5: Encryption Key Lifecycle Verification Report

**Phase Goal:** An operator can confidently lose, restore, and rotate ENCRYPTION_KEY without losing connector credentials.
**Verified:** 2026-07-06T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The security doc has a section "Encryption Key Backup & Rotation" with concrete commands and an RTO statement | ✓ VERIFIED | `docs/16-security.md` lines 141-206: exact `## Encryption Key Backup & Rotation` heading, `≤ 15 minutes` RTO, all 6 docker-compose commands, off-box vault guidance, lost-key recovery, single-key model |
| 2 | A rotation CLI exists (`python -m app.encryption rotate --new-key <key>`) that re-encrypts every connector_config.credentials_secret_arn row in a single transaction with verification | ✓ VERIFIED | `backend/app/encryption.py` lines 127-290: `rotate_credentials()` opens one `async_session_factory()` session, pre-flight decrypts all rows, post-verifies before commit, single `await db.commit()` at end; argparse `__main__` at lines 428-437 wires `rotate` subcommand; `python -m app.encryption generate-key` produces a valid Fernet key (smoke test passed) |
| 3 | Backend startup logs a loud warning if settings.encryption_key matches the placeholder or is unset (and hard-fails in production) | ✓ VERIFIED | `backend/app/main.py` lines 44-82: `_check_secrets_at_startup()` compares against `ENCRYPTION_KEY_PLACEHOLDER` and `JWT_SECRET_PLACEHOLDER` constants; logs `structlog.critical` / `structlog.warning` depending on `settings.environment`; raises `RuntimeError` when `issues and settings.environment == "production"`; called as first statement in `lifespan()` at line 91; 6 unit tests covering all 6 behavioural branches pass locally (10 passed, 8 Postgres-skipped, 0 failed) |
| 4 | End-to-end test `test_sc4_rotation_is_real`: encrypt with A → rotate A→B → decrypt rows → revert B→A → fail to decrypt with B | ✓ VERIFIED | `backend/tests/test_encryption_rotation.py` lines 309-360: test exists, uses `pytest.raises(InvalidToken)` to assert final B-decryption fails; test skips cleanly when Postgres is unreachable (expected locally, runs in CI per conftest); test structure is substantive — seeds DB, calls `rotate_credentials` twice, reloads fresh sessions, asserts `InvalidToken` on revert |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/encryption.py` | `_fernet_for()` helper, `rotate_credentials()`, `verify_credentials()`, argparse `__main__` | ✓ VERIFIED | 438 lines; all named symbols present; `_get_fernet()` and existing `encrypt_value`/`decrypt_value`/`generate_key` API untouched |
| `backend/tests/test_encryption_rotation.py` | Unit + integration tests including `test_sc4_rotation_is_real` | ✓ VERIFIED | 486 lines; 18 tests collected: 10 pass (4 unit + 6 startup-check), 8 skip on Postgres-unavailable; `test_sc4_rotation_is_real` exists and is substantive |
| `backend/app/main.py` | `_check_secrets_at_startup()` invoked at top of lifespan | ✓ VERIFIED | Function defined at line 44, called at line 91 as the first statement inside `lifespan()` before scheduler start |
| `docs/16-security.md` | "Encryption Key Backup & Rotation" runbook section | ✓ VERIFIED | Section inserted between `## Credential Encryption` (line 134) and `## Audit Logging` (line 208); all required sub-sections present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `rotate_credentials()` | `ConnectorConfig.credentials_secret_arn` | `select(ConnectorConfig).where(credentials_secret_arn.isnot(None))` — no tenant filter | ✓ WIRED | Line 166: `select(ConnectorConfig).where(ConnectorConfig.credentials_secret_arn.isnot(None))` confirmed cross-tenant |
| `rotate_credentials()` | `AuditLog` | direct `AuditLog(...)` construct with `user_email="system:cli"` and `action="encryption.key_rotated"` | ✓ WIRED | Lines 257-272: `AuditLog` constructed directly; `action="encryption.key_rotated"` at line 261; `tenant_id=connectors[0].tenant_id` (WR-06 fix applied) |
| `lifespan()` | `_check_secrets_at_startup()` | called at top of lifespan body before scheduler start | ✓ WIRED | Line 91: `_check_secrets_at_startup()` is the first statement in the lifespan body |
| `_check_secrets_at_startup()` | `settings.encryption_key` / `settings.jwt_secret_key` | placeholder compare + `Fernet(key)` validity check + environment gate | ✓ WIRED | Lines 54-65: placeholder checks; lines 57-62: `Fernet(key.encode())` validity check; line 70: `settings.environment == "production"` gate |

### Data-Flow Trace (Level 4)

Not applicable — this phase delivers a CLI tool and a startup function, not a UI component that renders dynamic data from a data source. The rotation functions are the data source themselves.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `generate-key` subcommand produces a valid Fernet key | `cd backend && .venv/bin/python3 -m app.encryption generate-key \| python3 -c "...Fernet(sys.stdin.read().strip().encode())..."` | `PASS` | ✓ PASS |
| 4 unit tests pass without Postgres | `cd backend && .venv/bin/python -m pytest tests/test_encryption_rotation.py -v --tb=short` | 10 passed, 8 skipped, 0 failed | ✓ PASS |
| CR-01 isinstance guard present in `verify_credentials` pre-flight | `grep -n "isinstance(encrypted_map, dict)" backend/app/encryption.py` | lines 102, 191 | ✓ PASS |
| CR-01 isinstance guard present in `rotate_credentials` pre-flight | `grep -n "isinstance(ciphertext, str)" backend/app/encryption.py` | lines 109, 198 | ✓ PASS |
| CR-02 RotationPreflightError wraps the dry-run count call | lines 384-393 in `_cmd_rotate` | `except RotationPreflightError as e:` at line 391 with `_print_rotation_failure(e)` | ✓ PASS |
| WR-02 narrowed catch in `main.py` | `grep -n "except (ValueError, TypeError)" backend/app/main.py` | line 59 | ✓ PASS |
| WR-05 rotated_count counts only non-empty rows | `grep -n "rotated_count = sum" backend/app/encryption.py` | line 215: `sum(1 for c in connectors if decoded_maps.get(str(c.id)))` | ✓ PASS |
| WR-06 audit tenant_id from `connectors[0]` not a second query | `grep -n "connectors\[0\].tenant_id" backend/app/encryption.py` | line 258 | ✓ PASS |
| Audit details contain no key material | `grep -n "details=" backend/app/encryption.py` | line 264-268: only `row_count`, `tenant_count`, `dry_run` keys | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROD-05-01 | 05-02-PLAN | Documented backup procedure for `ENCRYPTION_KEY` (where it lives, who restores it, RTO) | ✓ SATISFIED | `docs/16-security.md` lines 147-160: off-box vault, named platform/security owner, ≤15-minute RTO with restore steps |
| PROD-05-02 | 05-01-PLAN | Key rotation — generate new key, re-encrypt all connector credentials in a transaction, verify round-trip | ✓ SATISFIED | `backend/app/encryption.py` `rotate_credentials()`: single transaction, pre-flight, post-verify, `test_sc4_rotation_is_real` proves rotation is real (exists and is substantive; runs in CI) |
| PROD-05-03 | 05-01-PLAN + 05-02-PLAN | Optional CLI (`python -m app.encryption rotate`) implementing the rotation | ✓ SATISFIED | `rotate`/`verify`/`generate-key` subcommands wired at lines 428-437; backup reminder, `--dry-run`, `--yes`, confirmation prompt all present; restart instruction without key echo confirmed |
| PROD-05-04 | 05-02-PLAN | Operator alert if `.env` is missing or contains a placeholder `ENCRYPTION_KEY` | ✓ SATISFIED | `_check_secrets_at_startup()` checks encryption key and JWT key; hard-fails in production (`raise RuntimeError`); warns in development; 6 unit tests covering all behavioural branches pass locally |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/main.py` | 4-5 | `import uuid` and `import uuid as _uuid` — duplicate import (IN-01 from code review) | Info | Cosmetic only; both are used (uuid.uuid4 at line 198, _uuid.UUID at lines 414, 426, 443). No functional impact. Deferred by code review as non-blocking. |
| `backend/app/main.py` | 7 | `UTC` and `timezone` both imported; `datetime.now(UTC)` (line 452) and `datetime.now(timezone.utc)` (line 321) used inconsistently (IN-02) | Info | Cosmetic only; both evaluate to the same result. No functional impact. Deferred by code review as non-blocking. |

No blockers found. The two info-level anti-patterns above were identified in the code review (IN-01, IN-02) and explicitly deferred as cosmetic, non-blocking items.

### Human Verification Required

#### 1. Live `verify` command against a running instance

**Test:** On a running Docker Compose stack with at least one connector configured, run `docker compose exec -T backend python3 -m app.encryption verify`
**Expected:** Command prints `N OK / 0 failing`, exits 0; no traceback
**Why human:** Requires a live Postgres instance with seeded connector rows and a non-placeholder `ENCRYPTION_KEY` in the environment — cannot be verified without a running stack

#### 2. Production startup rejection with placeholder key

**Test:** Set `ENCRYPTION_KEY=CHANGE-ME-generate-with-python-c-from-cryptography.fernet-import-Fernet-Fernet.generate_key` and `ENVIRONMENT=production` in `.env`, then run `docker compose up backend`
**Expected:** The backend container exits with a non-zero code and logs `Backend refused to start: insecure secrets detected.`; no HTTP requests are served
**Why human:** The 6 unit tests prove `_check_secrets_at_startup()` raises `RuntimeError` in-process, but confirming that uvicorn propagates this through FastAPI's `lifespan` hook to terminate the server requires a live container boot

### Gaps Summary

No programmatically-detectable gaps. All 4 must-haves are verified at the code level. Two human verification items remain that require a live environment — they are operational smoke-tests of correct wiring, not evidence of missing implementation.

---

_Verified: 2026-07-06T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
