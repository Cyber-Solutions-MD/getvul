---
phase: 05-encryption-key-lifecycle
verified: 2026-07-08T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 4/4
  gaps_closed:
    - "python3 -m app.encryption rotate --new-key <key> --yes completes a full key rotation end-to-end (no NoReferencedTableError) when run as a standalone CLI process"
    - "Subprocess regression test test_rotate_cli_subprocess_completes_and_audits added and passes against fixed code"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run `docker compose exec -T backend python3 -m app.encryption verify` against a live instance"
    expected: "Command completes without traceback, prints 'N OK / M failing', exits 0 when all rows decrypt"
    why_human: "Requires a live Docker environment with Postgres, Redis, and a seeded ENCRYPTION_KEY that is not the placeholder"
  - test: "Start the backend with ENCRYPTION_KEY set to the placeholder value and ENVIRONMENT=production"
    expected: "Container refuses to start (uvicorn logs a RuntimeError and exits non-zero); no traffic is served"
    why_human: "Requires running uvicorn in production mode against a live container to confirm the RuntimeError actually terminates the process before the first request. The 6 unit tests prove _check_secrets_at_startup() raises RuntimeError in-process, but this confirms uvicorn propagates it through FastAPI's lifespan hook."
---

# Phase 5: Encryption Key Lifecycle Verification Report (Re-verification after Plan 03 gap closure)

**Phase Goal:** An operator can confidently lose, restore, and rotate ENCRYPTION_KEY without losing connector credentials.
**Verified:** 2026-07-08T00:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure plan 05-03 (rotate CLI NoReferencedTableError blocker)

## Re-verification Scope

The previous VERIFICATION.md (2026-07-06) had `status: human_needed` with 4/4 automated truths verified and two human verification items. Between that report and this one, UAT Test 5 exposed a blocker: the documented `python -m app.encryption rotate` CLI crashed with `sqlalchemy.exc.NoReferencedTableError` before completing, because the standalone CLI import graph never imported `app.tenants.models`, leaving SQLAlchemy unable to resolve `audit_logs.user_id -> users.id` and `audit_logs.tenant_id -> tenants.id` FK targets at mapper configuration time. Plan 05-03 fixed this.

**Re-verification focus:** Confirm the gap is genuinely closed — the fix is present, correctly placed, and the subprocess regression test passes against the fixed code with no regressions to the rest of the test file.

**Previously passing items:** Quick regression check only (existence + basic sanity).

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | docs/16-security.md has a section "Encryption Key Backup & Rotation" with concrete commands and an RTO statement | VERIFIED | `docs/16-security.md` line 141: exact `## Encryption Key Backup & Rotation` heading; line 160: `RTO: ≤ 15 minutes` — confirmed present, unchanged from initial verification |
| 2 | A rotation CLI exists (`python -m app.encryption rotate --new-key <key>`) that re-encrypts every connector_config.credentials_secret_arn row in a single transaction with verification | VERIFIED | `backend/app/encryption.py` line 162: `from app.tenants import models as _tenants_models  # noqa: F401` present function-locally inside `rotate_credentials()` before `db.add(log)`. Commit `dd72e40` (2026-07-07). Module-level count = 0 (function-local confirmed). The NoReferencedTableError gap is closed. |
| 3 | Backend startup logs a loud warning if settings.encryption_key matches the placeholder or is unset (and hard-fails in production) | VERIFIED | `backend/app/main.py` lines 44-91: `_check_secrets_at_startup()` + `ENCRYPTION_KEY_PLACEHOLDER` + `RuntimeError` in production — unchanged from initial verification |
| 4 | End-to-end test: encrypt with key A → rotate to key B → decrypt all rows → revert to key A → fail to decrypt | VERIFIED | `test_sc4_rotation_is_real` exists at line 312 with `pytest.raises(InvalidToken)` — unchanged. Additionally, new `test_rotate_cli_subprocess_completes_and_audits` (line 499) runs the documented operator CLI in a subprocess (real standalone import graph) and passes: 19 passed, 0 failed in full file run. |

**Score:** 4/4 truths verified

**Gap specifically closed — THE BLOCKER (UAT Test 5):**

The documented operator command `python3 -m app.encryption rotate --new-key <key> --yes` now completes end-to-end without error. Confirmed via `pytest tests/test_encryption_rotation.py -k "cli_subprocess" -x -q` → `1 passed`. The subprocess regression test invokes the real standalone import graph (no conftest masking), exercises the exact container-operator path, and asserts: exit 0, no `NoReferencedTableError` in stderr, `"Rotated 1 rows"` in stdout, one `encryption.key_rotated` AuditLog row with `user_email == "system:cli"`, credential re-encrypted under new key, no key material in stdout.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/encryption.py` | `rotate_credentials()` with function-local `from app.tenants import models` before AuditLog write | VERIFIED | Line 162: import present, function-local (0 module-level occurrences), placed before `from app.ticketing.models import ConnectorConfig`; existing AuditLog import at line 154 intact; file parses cleanly |
| `backend/tests/test_encryption_rotation.py` | `test_rotate_cli_subprocess_completes_and_audits` using `subprocess.run` invoking `python -m app.encryption rotate` | VERIFIED | Function defined at line 499; `subprocess.run` at line 533; `-m`, `app.encryption`, `rotate` pattern confirmed; `ENCRYPTION_KEY` set in subprocess env at line 529; `NoReferencedTableError` absence asserted at line 544; `os`/`subprocess`/`sys` imported at lines 16-18 |
| `backend/app/main.py` | `_check_secrets_at_startup()` invoked at top of lifespan | VERIFIED | Unchanged from initial verification — confirmed at line 91 |
| `docs/16-security.md` | "Encryption Key Backup & Rotation" runbook section with RTO | VERIFIED | Unchanged from initial verification — section at line 141, RTO at line 160 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `rotate_credentials()` | `app.tenants.models` (User + Tenant tables) | `from app.tenants import models as _tenants_models` inside function body before AuditLog write | VERIFIED | Line 162; confirmed function-local (not module-level); mapper registration side-effect resolves both `audit_logs.user_id -> users.id` and `audit_logs.tenant_id -> tenants.id` FKs |
| `test_rotate_cli_subprocess_completes_and_audits` | `python -m app.encryption rotate` (standalone process) | `subprocess.run([sys.executable, "-m", "app.encryption", "rotate", ...])` | VERIFIED | Line 533-540; subprocess runs from `backend/` directory (correct cwd); `ENCRYPTION_KEY` set to `key_a` in env; `--yes` skips prompts |
| subprocess test | AuditLog assertion | fresh `async_session_factory()` session at line 554 | VERIFIED | Opens a fresh session independent of `db_session` fixture; asserts `action == "encryption.key_rotated"` and `user_email == "system:cli"` |
| subprocess test | credential re-encryption assertion | `_fernet_for(key_b).decrypt(cmap["api_key"].encode())` at line 570 | VERIFIED | Asserts the seeded `"cli-subprocess-secret"` decrypts successfully with `key_b` after rotation |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Subprocess regression test passes (real standalone CLI, no conftest masking) | `cd backend && .venv/bin/pytest tests/test_encryption_rotation.py -k "cli_subprocess" -x -q` | `1 passed` | PASS |
| Full rotation test file — no regressions | `cd backend && .venv/bin/pytest tests/test_encryption_rotation.py -q --tb=short` | `19 passed, 1 warning` | PASS |
| `from app.tenants import models` present inside `rotate_credentials()` | `grep -n "from app.tenants import models" backend/app/encryption.py` | line 162 | PASS |
| Import is function-local (not module-level) | `grep -c "^from app.tenants import models" backend/app/encryption.py` | `0` | PASS |
| `test_rotate_cli_subprocess_completes_and_audits` definition exists | `grep -q "def test_rotate_cli_subprocess_completes_and_audits"` | found at line 499 | PASS |
| Gap-closure commits exist on main branch | `git log --oneline` | `dd72e40` (fix) and `6b5658f` (test) both present | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROD-05-01 | 05-02-PLAN | Documented backup procedure for ENCRYPTION_KEY (where it lives, who restores it, RTO) | SATISFIED | `docs/16-security.md` lines 141-206; `RTO: ≤ 15 minutes` at line 160; unchanged from initial verification |
| PROD-05-02 | 05-01-PLAN, 05-03-PLAN | Key rotation — generate new key, re-encrypt all connector credentials in a transaction, verify round-trip | SATISFIED | `rotate_credentials()` with tenants-models fix now completes without NoReferencedTableError in standalone CLI; `test_rotate_cli_subprocess_completes_and_audits` exercises the real operator path and passes; `test_sc4_rotation_is_real` proves full A→B→A rotation with InvalidToken assertion |
| PROD-05-03 | 05-01-PLAN, 05-03-PLAN | Optional CLI (`python -m app.encryption rotate`) implementing the rotation | SATISFIED | The documented command no longer crashes in the standalone CLI process; subprocess test proves it exits 0 and prints "Rotated 1 rows" |
| PROD-05-04 | 05-02-PLAN | Operator alert if `.env` is missing or contains a placeholder ENCRYPTION_KEY | SATISFIED | `_check_secrets_at_startup()` unchanged; hard-fails in production, warns in development; 6 unit tests pass |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/main.py` | 4-5 | Duplicate uuid import (IN-01, pre-existing) | Info | Cosmetic; deferred as non-blocking in prior code review |
| `backend/app/main.py` | 7 | Inconsistent UTC/timezone.utc usage (IN-02, pre-existing) | Info | Cosmetic; deferred as non-blocking in prior code review |

No new anti-patterns introduced by Plan 03 changes. The fix is a single function-local import with `noqa: F401`; the regression test adds no production code paths.

---

### Human Verification Required

These two items are carried forward unchanged from the initial verification — they are operational smoke-tests that require a live Docker environment, not evidence of missing implementation.

#### 1. Live `verify` command against a running instance

**Test:** On a running Docker Compose stack with at least one connector configured, run `docker compose exec -T backend python3 -m app.encryption verify`
**Expected:** Command prints `N OK / 0 failing`, exits 0; no traceback
**Why human:** Requires a live Postgres instance with seeded connector rows and a non-placeholder `ENCRYPTION_KEY` in the environment

#### 2. Production startup rejection with placeholder key

**Test:** Set `ENCRYPTION_KEY=CHANGE-ME-generate-with-python-c-from-cryptography.fernet-import-Fernet-Fernet.generate_key` and `ENVIRONMENT=production` in `.env`, then run `docker compose up backend`
**Expected:** The backend container exits with a non-zero code and logs `Backend refused to start: insecure secrets detected.`; no HTTP requests are served
**Why human:** The 6 unit tests prove `_check_secrets_at_startup()` raises RuntimeError in-process. This confirms that uvicorn propagates it through FastAPI's lifespan hook to a non-zero container exit — requires a live container boot to observe.

---

### Gaps Summary

**No programmatically-detectable gaps.** The Plan 03 blocker (UAT Test 5 — `NoReferencedTableError` in `rotate_credentials()` when run as a standalone CLI) is genuinely closed:

- The fix is confirmed present at `backend/app/encryption.py` line 162 inside `rotate_credentials()` before the AuditLog write, as required.
- The fix is function-local (not hoisted to module top), preserving the lazy-import pattern.
- The subprocess regression test `test_rotate_cli_subprocess_completes_and_audits` passes against the fixed code (`1 passed` directly; `19 passed` in full file run with 0 regressions).
- All four requirement IDs (PROD-05-01 through PROD-05-04) are satisfied.

The two human verification items are operational smoke-tests carried forward from the initial verification — they reflect the inherent need for a live Docker environment, not implementation gaps.

---

_Verified: 2026-07-08T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — after Plan 03 gap closure (rotate CLI NoReferencedTableError blocker)_
