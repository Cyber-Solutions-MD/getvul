---
phase: 05-encryption-key-lifecycle
reviewed: 2026-07-08T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - backend/app/encryption.py
  - backend/tests/test_encryption_rotation.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 05: Code Review Report (Gap-Closure Re-Review — Plan 05-03)

**Reviewed:** 2026-07-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

> **Scope note:** This report supersedes the prior full-phase review for the
> gap-closure pass. It reviews ONLY the plan 05-03 diff since `dd72e40^`: the
> function-local `from app.tenants import models` import added inside
> `rotate_credentials()` and the new subprocess regression test
> `test_rotate_cli_subprocess_completes_and_audits`.

## Summary

The fix is correct and well-justified. I traced the mapper-registration claim
end-to-end:

- `AuditLog` (`backend/app/audit.py:40-43`) declares string-based FKs to
  `tenants.id` and `users.id`.
- Both `Tenant` and `User` are defined in `backend/app/tenants/models.py`
  (lines 26 and 49) and own those tables.
- `rotate_credentials()` imports `app.audit` and `app.ticketing.models`, but
  neither transitively registers `app.tenants.models`: `app/audit.py` imports
  only `app.auth.schemas` and `app.db.base`, and `ConnectorConfig` references
  `tenants.id` via a **string** FK (`backend/app/ticketing/models.py:40`), which
  does not force the `Tenant` class to be imported/registered.

So in the standalone CLI process (`python -m app.encryption`) the `Tenant`/`User`
mappers are genuinely absent when SQLAlchemy configures the `AuditLog` mapper —
exactly what produced `NoReferencedTableError`. The added import registers both
classes and resolves the FKs. The `noqa: F401` and the "Do NOT remove" comment
are appropriate: this is a load-bearing import-for-side-effect, and the eager
conftest imports would otherwise mask a regression in unit tests. The import is
idempotent across the two `rotate_credentials()` calls the CLI makes (dry-run
count + real rotate) because `sys.modules` caches it.

The subprocess regression test is a strong design: it runs a fresh interpreter
with `cwd=backend/` and does NOT load `conftest.py`, so the conftest's eager
model imports cannot paper over the gap. It asserts operator-visible behavior
(exit 0, no `NoReferencedTableError`, rotation reported, audit row landed,
ciphertext re-encrypted under `key_b`, no key material in stdout). Transaction
visibility is sound: `db_session.commit()` (with `expire_on_commit=False`)
persists both the flushed `tenant_a` and the seeded `ConnectorConfig` before the
subprocess reads them, and the committed parent transaction holds no lock, so
there is no deadlock with the child's UPDATE.

One robustness concern with the new test (WR-01) and two minor info items follow.
No blockers.

## Warnings

### WR-01: Subprocess test silently depends on `DATABASE_URL` being exported into the process environment

**File:** `backend/tests/test_encryption_rotation.py:528-545`
**Issue:** The test builds the child environment via `env = os.environ.copy()`
and overrides only `ENCRYPTION_KEY` and `ENVIRONMENT`. It relies on `DATABASE_URL`
already being present in the parent process environment so the child CLI reaches
the same Postgres the fixtures seeded. But in tests `REDIS_URL` is injected via
`monkeypatch.setenv` (`conftest.py:54`), and the app's DB URL is read from config
at import time — it is not guaranteed to be an exported OS environment variable.
If `DATABASE_URL` lives only in a pytest-loaded `.env` / app config and is not
exported, the child connects to a different (or default) database, sees an empty
table, and prints `Rotated 0 rows`. The assertion `assert "Rotated 1 rows" in
proc.stdout` then fails with no message body — masquerading as a regression in
the mapper fix rather than an environment mismatch. That makes the regression
test brittle and its failures hard to diagnose, which undercuts its purpose.
**Fix:** Resolve the DB URL explicitly, assert it is present before spawning, and
pass it through so a misconfigured environment fails loudly with a clear reason:

```python
from app.config import settings as _settings
db_url = os.environ.get("DATABASE_URL") or getattr(_settings, "database_url", None)
assert db_url, "DATABASE_URL must be exported for the rotate CLI subprocess"
env = os.environ.copy()
env["DATABASE_URL"] = str(db_url)
env["ENCRYPTION_KEY"] = key_a
env["ENVIRONMENT"] = "development"
```

Also add the stdout to the count assertion so a 0-row outcome self-explains:
`assert "Rotated 1 rows" in proc.stdout, proc.stdout`.

## Info

### IN-01: Brittle exact-substring assertion couples the regression test to CLI copy

**File:** `backend/tests/test_encryption_rotation.py:545` (matches
`backend/app/encryption.py:427`)
**Issue:** `assert "Rotated 1 rows" in proc.stdout` matches the CLI's
`print(f"Rotated {result['rotated']} rows across ...")` verbatim (including the
grammatically off "1 rows"). Any future copy change — pluralization fix, rewording,
localization — silently breaks this test even though rotation still works. The
test's real intent is "rotation reported one row," not "this exact English string
printed." The durable outcome (audit row + re-encrypted ciphertext) is already
asserted against the DB, so the stdout check is the weakest link.
**Fix:** Loosen to intent, e.g. `import re; assert re.search(r"Rotated\s+1\b",
proc.stdout)`, or rely on the DB-level assertions already present.

### IN-02: Unused `import uuid` in the edited test module

**File:** `backend/tests/test_encryption_rotation.py:19`
**Issue:** `import uuid` is never referenced in the module. This is pre-existing
(not introduced by the 05-03 diff), so not a blocker for gap-closure, but it is
dead code in a just-edited file and will trip `F401` on any lint run.
**Fix:** Remove the `import uuid` line.

---

_Reviewed: 2026-07-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
