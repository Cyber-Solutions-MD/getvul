---
phase: 05-encryption-key-lifecycle
reviewed: 2026-07-06T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - backend/app/encryption.py
  - backend/app/main.py
  - backend/tests/test_encryption_rotation.py
  - docs/16-security.md
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: resolved
resolved_commit: fix(05) harden rotation abort contract + address code review
---

> **Resolution (2026-07-06):** Both blockers (CR-01, CR-02) and WR-01, WR-02, WR-05,
> WR-06, IN-03 fixed inline; WR-03 addressed via runbook maintenance-window note.
> Deferred (documented behavior, low risk): WR-04 (double decrypt pass in confirm flow),
> IN-01/IN-02 (cosmetic import dedup in main.py), IN-04 (runbook ordering of the safer
> env-var invocation). See the `fix(05)` commit.

# Phase 5: Code Review Report

**Reviewed:** 2026-07-06T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 5 adds a Fernet key-rotation CLI (`rotate_credentials` / `verify_credentials` / `_fernet_for` + argparse in `encryption.py`), a startup secrets check (`_check_secrets_at_startup` in `main.py`), and a rotation runbook (`docs/16-security.md`).

The design intent is sound: single-transaction abort-all-or-nothing rotation, pre-flight and post-verify decryption passes, no key material in audit rows, and no key echoing in the CLI. On those headline requirements the implementation is largely correct — the audit row carries only counts, the CLI never prints the key, and the transaction rolls back on failure.

However, the abort-all-or-nothing guarantee has a real hole: several malformed-row shapes (non-dict credential JSON, non-string ciphertext values) raise an **uncaught `AttributeError`** rather than being collected as a controlled pre-flight failure. That both crashes rotation with a raw traceback and defeats the "clean, friendly abort" contract the runbook promises. Separately, the confirmation-flow dry-run call in the CLI is not wrapped in the `RotationPreflightError` handler, so a genuinely broken dataset surfaces as an unhandled exception before the operator ever reaches the guarded path. Test coverage is broad but two assertions (`pytest.raises((RotationPreflightError, Exception))`) are effectively unfalsifiable and would pass on the very bugs above.

## Critical Issues

### CR-01: Malformed credential JSON raises uncaught `AttributeError`, bypassing the abort-all-or-nothing contract

**File:** `backend/app/encryption.py:181-186` (also `:103-105`, `:224-226`)

**Issue:** The pre-flight loop only guards `json.loads` with `except (json.JSONDecodeError, TypeError)`. It does **not** guard the subsequent `encrypted_map.items()` / `ciphertext.encode()` calls. Two real-world shapes escape the guard:

1. `credentials_secret_arn` is valid JSON but **not an object** (e.g. `"5"`, `'"str"'`, `"[1,2]"`). `json.loads` succeeds, then `encrypted_map.items()` raises `AttributeError` — not caught.
2. A field value is **not a string** (e.g. `'{"api_key": 5}'`). `ciphertext.encode()` raises `AttributeError` — not caught.

Confirmed empirically: `(5).encode()`, `(5).items()`, `["x"].items()`, `"s".items()` all raise `AttributeError`, which is **not** a subclass of `json.JSONDecodeError` or `TypeError`.

Consequences: the exception propagates out of `rotate_credentials` mid-transaction. The `async with async_session_factory()` block exits without an explicit `rollback()` on this path, and the caller (`_cmd_rotate`) only catches `RotationPreflightError`, so the operator sees a raw traceback. This directly contradicts the documented guarantee ("if any row fails ... the entire operation aborts and rolls back — no mixed-key state is ever written") and the CLI promise "No rows were modified." A single garbage row turns a controlled abort into an unhandled crash.

**Fix:** Treat any non-dict map or non-string field as a controlled failure. Widen the guards and validate shape:

```python
for connector in connectors:
    try:
        encrypted_map = json.loads(connector.credentials_secret_arn)  # type: ignore[arg-type]
    except (json.JSONDecodeError, TypeError):
        preflight_failures.append((str(connector.id), str(connector.tenant_id), "<json_parse>"))
        continue

    if not isinstance(encrypted_map, dict):
        preflight_failures.append((str(connector.id), str(connector.tenant_id), "<not_object>"))
        continue

    row_plains: dict[str, str] = {}
    for field, ciphertext in encrypted_map.items():
        if not isinstance(ciphertext, str):
            preflight_failures.append((str(connector.id), str(connector.tenant_id), field))
            continue
        try:
            row_plains[field] = old_fernet.decrypt(ciphertext.encode()).decode()
        except (InvalidToken, ValueError):
            preflight_failures.append((str(connector.id), str(connector.tenant_id), field))
    decoded_maps[str(connector.id)] = row_plains
```

Apply the same `isinstance` hardening to `verify_credentials` (lines 96-108) and the post-verify loop (lines 219-228). Consider a broad `except Exception` with `await db.rollback()` around the whole mutation body as defense-in-depth so no code path can leave the session mid-transaction.

### CR-02: Confirmation-flow dry-run call is outside the `RotationPreflightError` handler

**File:** `backend/app/encryption.py:353-383`

**Issue:** For a real (non-dry-run) rotation, `_cmd_rotate` first calls `rotate_credentials(..., dry_run=True, audit=False)` at lines 354-359 to fetch the row/tenant counts for the confirmation prompt. That call runs the **full pre-flight** — including decryption of every row — and raises `RotationPreflightError` on any bad row. But it is **not** wrapped in `try/except`; only the second (real) call at lines 372-377 is. So if the dataset contains a row that fails pre-flight, the operator gets an unhandled `RotationPreflightError` traceback at the counting step, never reaching the friendly "No rows were modified. The old key is still active." message. The tool becomes unusable precisely in the failure scenario it was built to handle gracefully.

**Fix:** Wrap the dry-run count call in the same handler, or restructure so a single guarded call produces both the count and the rotation:

```python
    if not args.dry_run:
        try:
            dry_result = await rotate_credentials(
                old_key=settings.encryption_key,
                new_key=args.new_key,
                dry_run=True,
                audit=False,
            )
        except RotationPreflightError as e:
            print(f"Rotation failed ({e.phase}):")
            for connector_id, tenant_id, field in e.failures:
                print(f"  connector={connector_id} tenant={tenant_id} field={field}")
            print("No rows were modified. The old key is still active.")
            sys.exit(1)
        ...
```

Better: extract the print-failures block into a helper and call it from both sites to avoid duplicating the message.

## Warnings

### WR-01: Test `pytest.raises((RotationPreflightError, Exception))` is unfalsifiable and hides CR-01/CR-02

**File:** `backend/tests/test_encryption_rotation.py:153`

**Issue:** `with pytest.raises((RotationPreflightError, Exception))` accepts *any* exception because `Exception` is the base of nearly everything. The test therefore passes whether rotation aborts cleanly (`RotationPreflightError`) or crashes with the uncaught `AttributeError` from CR-01. It provides no assurance that the abort was controlled. The whole point of `test_rotate_aborts_on_bad_row` is to prove the clean-abort contract, and this assertion cannot fail for the right reason.

**Fix:** Assert the specific exception and, ideally, the phase:

```python
with pytest.raises(RotationPreflightError) as exc_info:
    await rotate_credentials(key_a, key_b)
assert exc_info.value.phase == "preflight"
```

Also add a dedicated case seeding a non-dict `credentials_secret_arn` (e.g. `json.dumps(5)`) and a non-string field value to lock in the CR-01 fix.

### WR-02: `except (ValueError, Exception)` — `ValueError` is dead and the pattern silently swallows everything

**File:** `backend/app/main.py:59`

**Issue:** `except (ValueError, Exception)` is equivalent to `except Exception`; `ValueError` is a subclass and is unreachable/redundant, which misleads readers into thinking only two narrow error types are handled. It also swallows unexpected errors (e.g. `KeyboardInterrupt` is spared since it's `BaseException`, but any programming error in the try body is silently converted into "not a valid Fernet key"). Fernet's failure modes are `ValueError` and `binascii.Error` (a subclass of `ValueError`), so a precise catch is possible.

**Fix:**

```python
        try:
            Fernet(settings.encryption_key.encode())
        except (ValueError, TypeError):
            issues.append("ENCRYPTION_KEY is set but is not a valid Fernet key")
```

If you truly want a catch-all, write `except Exception:` explicitly and drop the misleading `ValueError`.

### WR-03: Rotation not isolated against concurrent connector writes (lost-update / mixed-key window)

**File:** `backend/app/encryption.py:153-263`

**Issue:** `rotate_credentials` loads all rows, re-encrypts, and commits, but takes no row locks (`with_for_update`) and relies on default transaction isolation. If a connector is created or its credentials updated (via `create_connector` / `update_connector` in `connectors/service.py`, which encrypt with the *old* key) between this transaction's `SELECT` and `COMMIT`, that row is either missed by rotation (left under the old key while the operator believes rotation is complete and swaps the env var → row becomes undecryptable) or overwrites the rotated value. The runbook implies operators restart the backend after rotation, but the API remains live during rotation. This is a correctness/data-integrity risk, not merely performance.

**Fix:** Add `.with_for_update()` to the load query and document that rotation should run during a maintenance window, or explicitly gate connector writes during rotation. At minimum, the runbook should state that no connector create/update may occur while rotation runs.

### WR-04: `audit=False` dry-run count triggers a second full decrypt pass; pre-flight runs twice

**File:** `backend/app/encryption.py:353-377`

**Issue:** For a real rotation the CLI decrypts every row twice: once in the dry-run count call, once in the real call. Beyond the wasted work, the two calls operate on independent sessions/snapshots, so the count shown in the confirmation prompt can differ from what the real call actually rotates (see WR-03). The operator confirms "N rows" but a different N may be written.

**Fix:** Return the count from a single guarded rotation, or compute the count with a lightweight `SELECT count(*)` (already available as `tenant_count` logic) rather than a full decrypt pass, and perform the confirming count inside the same transaction that mutates.

### WR-05: `rotated_count = len(connectors)` counts empty/no-op credential maps as "rotated"

**File:** `backend/app/encryption.py:194`

**Issue:** `rotated_count` is the total row count, including rows whose credential map is empty (`"{}"`) or whose decrypt produced no plaintext fields. Those rows are re-serialized to `"{}"` and reported as rotated. The audit `row_count` and the operator-facing "Rotated N rows" then overstate what actually changed, which undermines the audit trail's accuracy for a security-sensitive operation.

**Fix:** Count only rows that had at least one field re-encrypted, e.g. track `rows_with_fields = sum(1 for c in connectors if decoded_maps.get(str(c.id)))`, and report that (or report both total and mutated counts distinctly).

### WR-06: `audit` guard uses `rotated_count > 0` but derives tenant_id from a fresh query that can disagree

**File:** `backend/app/encryption.py:235-260`

**Issue:** The audit block re-queries for `first_tenant_id` and skips writing the audit row if it is `None`. Because `rotated_count > 0` guarantees `connectors` is non-empty, `first_tenant_id` should never be `None` here — but if it somehow is (row deleted mid-transaction under low isolation, WR-03), the rotation commits the re-encryption **without an audit record**, silently. A key rotation with no audit trail is a compliance gap. Additionally, the audit `details` hardcodes `"dry_run": False`, which is correct only because this block is unreachable in dry-run — but it is fragile if the control flow is later refactored.

**Fix:** Reuse a tenant_id already loaded in `connectors` (`connectors[0].tenant_id`) instead of a second query, and treat "cannot write audit row" as a hard failure (rollback + raise) rather than a silent skip:

```python
    if audit and rotated_count > 0:
        log = AuditLog(
            tenant_id=connectors[0].tenant_id,
            ...
        )
        db.add(log)
```

## Info

### IN-01: Redundant duplicate import of `uuid`

**File:** `backend/app/main.py:4-5`

**Issue:** `import uuid` and `import uuid as _uuid` both import the same module under two names. Only cosmetic, but it invites confusion about whether they differ.

**Fix:** Use a single alias throughout (`import uuid` and reference `uuid.UUID(...)`), and drop `import uuid as _uuid`.

### IN-02: `datetime` import includes both `UTC` and `timezone`

**File:** `backend/app/main.py:7`

**Issue:** The module imports `UTC`, `datetime`, and `timezone`, then uses `datetime.now(UTC)` in one place (line 450) and `datetime.now(timezone.utc)` in another (line 319). Two spellings of the same value reduce consistency.

**Fix:** Standardize on `datetime.now(UTC)` throughout and drop the `timezone` import.

### IN-03: Weak final assertion in audit-no-key-material test

**File:** `backend/tests/test_encryption_rotation.py:261-263`

**Issue:** The assertion `assert "key" not in details_str.lower() or all(k not in details_str for k in [key_a, key_b])` is trivially satisfied by the right-hand `all(...)` even when `"key"` *is* present, so the left operand is dead. It does not meaningfully test anything beyond the two explicit `assert key_a not in details_str` lines above it.

**Fix:** Drop the confusing compound assertion; the two preceding explicit checks already assert no key material. If you want to assert the raw Fernet keys are absent regardless of substring, keep only:

```python
assert key_a not in details_str
assert key_b not in details_str
```

### IN-04: Runbook shows `--new-key <NEW_KEY>` on the command line while warning it leaks via `ps aux`

**File:** `docs/16-security.md:172-176` vs `:188-193`

**Issue:** Steps 3 and 4 of the primary runbook pass `--new-key <NEW_KEY>` directly on the command line, then a note below (T-05-08) explains this leaks through `ps aux` and recommends an env-var indirection. Operators copy the first block they see; the safer form should be the default, not a footnote.

**Fix:** Make the env-var form (lines 191-193) the primary runbook steps and demote the literal `<NEW_KEY>` form to "less safe alternative," or add an inline warning directly on step 4.

---

_Reviewed: 2026-07-06T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
