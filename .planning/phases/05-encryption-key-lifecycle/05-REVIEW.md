---
phase: 05-encryption-key-lifecycle
reviewed: 2026-07-23T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - backend/app/encryption.py
  - backend/tests/test_encryption_rotation.py
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 05: Code Review Report (Re-Review of SHIPPED v1.0 Phase)

**Reviewed:** 2026-07-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

> **Re-review note:** This supersedes the 2026-07-08 gap-closure review. Each prior
> finding was re-verified against the CURRENT code. One item (IN-02) has been fixed
> and is dropped. Two items remain and are marked verified-against-current-code. No
> new Critical/Warning issues were found in the rotation/key-handling logic.

## Summary

The encryption/rotation code is in good shape for a shipped v1.0 phase. I re-verified
the security-sensitive properties end-to-end against `backend/app/encryption.py`:

- **No secret exposure.** Neither Fernet keys nor decrypted plaintext are ever
  printed. `_print_rotation_failure()` (lines 354-359) emits only connector/tenant/field
  identifiers; the post-rotation restart hint (line 428) prints a literal `<new key>`
  placeholder, not the key; the audit `details` payload (lines 268-272) carries only
  counts. The subprocess test even asserts no key material reaches child stdout (line 558).
- **Rotation correctness.** Both keys are validated up front (lines 166-167). The flow
  is single-transaction abort-all-or-nothing with an explicit pre-flight decrypt (old key),
  post-verify decrypt (new key), and rollback on any failure or unexpected exception
  (lines 214-216, 252-254, 280-287). Dry-run rolls back and writes nothing (lines 223-230).
- **Secure key generation.** `generate_key()` delegates to `Fernet.generate_key()` (line 38).
- **Edge shapes handled.** Non-dict JSON and non-string field values are caught and
  routed to controlled preflight failures rather than crashing (lines 101-104, 196-198,
  203-205). Empty `{}` maps are excluded from `rotated_count` (line 220).

**Reconciliation of prior findings:**

- **WR-01** (subprocess test env / opaque assertion) — RETAINED. Code unchanged; still
  valid at reduced confidence (see nuance below). Verified against current code.
- **IN-01** (brittle exact-substring `"Rotated 1 rows"` assertion) — RETAINED. Line
  unchanged (now `test_encryption_rotation.py:532`). Verified against current code.
- **IN-02** (unused `import uuid`) — FIXED / DROPPED. The current test module imports
  only `json`, `os`, `subprocess`, `sys` (lines 15-18); there is no `import uuid`.

## Warnings

### WR-01: Subprocess regression test asserts row count with no failure message and does not pin `DATABASE_URL`

**File:** `backend/tests/test_encryption_rotation.py:515-532` (verified against current code)
**Issue:** The child environment is built via `env = os.environ.copy()` overriding only
`ENCRYPTION_KEY` and `ENVIRONMENT`, and success is checked with a bare
`assert "Rotated 1 rows" in proc.stdout` (line 532) that carries no message body. If the
child ever rotates 0 rows — for any reason — the assertion fails opaquely, masquerading as
a regression in the mapper-registration fix rather than surfacing the real cause (empty
stdout/stderr are not attached).

**Nuance vs. the 2026-07-08 report:** The original finding claimed the child could connect
to a *different* database if `DATABASE_URL` lived only in a pytest-loaded `.env`. That risk
is largely mitigated in practice: the child re-imports `app.config`, which reconstructs
`settings` from the same `.env`/OS environment as the parent, and conftest monkeypatches
only `REDIS_URL` (`conftest.py:54`), not `DATABASE_URL`. So parent and child resolve the
same DB deterministically. The durable concern that remains is **diagnosability**: the
count assertion has no message, so a 0-row outcome self-obscures.

**Fix:** Attach stdout/stderr to the count assertion (and optionally pin the DB URL for a
loud, explicit failure):

```python
assert "Rotated 1 rows" in proc.stdout, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
```

## Info

### IN-01: Exact-substring assertion couples the regression test to CLI copy

**File:** `backend/tests/test_encryption_rotation.py:532` (verified against current code;
matches `backend/app/encryption.py:426`)
**Issue:** `assert "Rotated 1 rows" in proc.stdout` matches the CLI's
`print(f"Rotated {result['rotated']} rows across ...")` verbatim, including the
grammatically-off "1 rows". Any future copy change (pluralization fix, rewording,
localization) silently breaks this test even though rotation still works. The durable
outcome — the audit row and the re-encrypted ciphertext — is already asserted against the
DB (lines 542-555), making this stdout check the weakest link.
**Fix:** Loosen to intent, e.g. `import re; assert re.search(r"Rotated\s+1\b", proc.stdout)`,
or rely on the DB-level assertions already present.

---

_Reviewed: 2026-07-23T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
