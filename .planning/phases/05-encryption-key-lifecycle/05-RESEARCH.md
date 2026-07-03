# Phase 5: Encryption Key Lifecycle — Research

**Researched:** 2026-07-03
**Domain:** Fernet key lifecycle, SQLAlchemy async, argparse CLI, structlog startup checks
**Confidence:** HIGH — all findings grounded in repo code with file:line references

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Rotation model**
- D-01: Hard cutover. Single atomic DB transaction. No MultiFernet, no grace-period dual-key. `ENCRYPTION_KEY` stays a single scalar env var.
- D-02: CLI reads OLD key from `settings.encryption_key`; NEW key passed via `--new-key`. On success, prints instruction to set `ENCRYPTION_KEY=<new>` in `.env` and restart. Tool does NOT write to `.env`.
- D-03: Abort-all-and-roll-back on any failure. Pre-flight decrypts every row with the old key first. Any failure → roll back entire transaction.
- D-04: Post-commit round-trip verification inside the same transaction before committing.
- D-05: `--dry-run` flag — runs full decrypt pass, reports row count and failures, writes nothing.
- D-06: Confirmation prompt `This will re-encrypt N rows across M tenants. Continue? [y/N]`, skippable with `--yes`.
- D-07: Backup reminder first, requires acknowledgement.
- D-08: Emit `encryption.key_rotated` audit event on success. No key material. NOTE: CLI runs outside request context — see §Audit-Event Attribution below.

**CLI command surface**
- D-09: Three subcommands: `rotate` (`--new-key`, `--dry-run`, `--yes`), `verify`/`check` (read-only decrypt-all), `generate-key` (wraps `encryption.generate_key()`).

**Startup check**
- D-10: Hard-fail in production (`settings.environment == "production"`), warn-and-continue in dev.
- D-11: Trigger conditions: (a) key equals placeholder literal; (b) empty/unset; (c) invalid Fernet key — validated by attempting `Fernet(key)` construction.
- D-12: Also check `jwt_secret_key` against its `CHANGE-ME-IN-PRODUCTION` placeholder. Same severity model.
- Home: `lifespan` startup path in `backend/app/main.py`.

**Backup runbook (docs/16-security.md)**
- D-13: Section title: "Encryption Key Backup & Rotation"
- D-14: RTO ≤ 15 minutes.
- D-15: Key storage in org secrets vault (1Password/Vault/cloud secrets manager) — off-box, not in repo, not on VM, not in DB.
- D-16: Lost-key recovery = generate fresh key + re-enter each connector's credentials through the UI.
- D-17: Document the single-key model explicitly (one global key, all tenants, rotation affects all).

**Testing**
- D-18: E2E rotation test uses real Postgres via existing `backend/tests` conftest DB fixture. Invokes rotation logic as a function (not subprocess). SC#4 sequence: encrypt A → rotate to B → decrypt all OK → revert to A → fail to decrypt.

### Claude's Discretion
- Exact structlog message wording for startup warning/error.
- Whether CLI lives as `__main__` block in `backend/app/encryption.py` or as `backend/app/encryption/__main__.py` package.
- argparse vs lightweight subcommand dispatcher.
- Precise audit-event actor/attribution mechanism for CLI context (flagged in D-08).

### Deferred Ideas (OUT OF SCOPE)
- MultiFernet grace-period / zero-downtime rotation
- Fallback-read secondary OLD key during rotation
- Cloud KMS / envelope encryption / per-tenant keys
- JWT secret rotation tooling (only startup warning in scope)
- Tool auto-rewriting `.env`
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-05-01 | Documented backup procedure for `ENCRYPTION_KEY` (where it lives, who restores it, RTO) | D-13..D-17 locked; write section in `docs/16-security.md` |
| PROD-05-02 | Key rotation runbook — generate new key, re-encrypt all connector credentials in a transaction, verify decrypt round-trip | D-01..D-08; rotation function design documented in §Rotation Logic; `credentials_secret_arn` JSON map structure confirmed |
| PROD-05-03 | Optional CLI command (`python -m app.encryption rotate`) implementing the rotation | D-09; CLI module structure analyzed in §CLI Module Structure; single-module approach recommended |
| PROD-05-04 | Operator alert if `.env` is missing or contains a placeholder `ENCRYPTION_KEY` | D-10..D-12; startup check design in §Startup Check; placeholder strings confirmed at `config.py:22` and `config.py:16` |
</phase_requirements>

---

## Summary

This phase is almost entirely an internal-codebase problem — no new dependencies and no external APIs. The CONTEXT.md captured every design decision; this research resolves the five genuine unknowns the planner needs: (1) how the audit event works from a CLI context given the FK constraint on `tenant_id`; (2) the exact refactor needed in `encryption.py` to support explicit-key operations; (3) whether `python -m app.encryption` requires a package or works with a single module; (4) the complete cross-tenant query shape for rotation; and (5) how the E2E test slots into the existing conftest.

**Primary recommendation:** Use the single-module approach (keep `encryption.py` as a single file, add `if __name__ == "__main__":` with argparse). The one existing importer (`connectors/service.py`) requires no change. For the audit event from CLI, construct a synthetic `CurrentUser`-like object with a real tenant UUID queried from the DB — this satisfies the `tenant_id` FK constraint while recording `user_email="system:cli"`.

**Scope confirmation:** Only `connector_configs.credentials_secret_arn` uses Fernet encryption. SMTP config (`tenants.smtp_config` JSONB) is NOT Fernet-encrypted and is out of scope for rotation.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Rotation CLI | API / Backend (CLI tool) | — | Runs directly against DB and `async_session_factory`; no HTTP layer |
| Startup validation check | API / Backend (`lifespan`) | — | Runs at process startup before traffic is served |
| Audit event emission | API / Backend (`audit.py`) | — | DB write to `audit_logs` table |
| Credential re-encryption | API / Backend (encryption module) | Database / Storage | Reads/writes `connector_configs` table in a single transaction |
| Backup runbook | Documentation (`docs/16-security.md`) | — | Human-readable procedure; no code |
| E2E rotation test | API / Backend (`tests/`) | Database / Storage | Real Postgres; invokes rotation logic as a function |

---

## Research Focus Findings

### 1. Audit-Event Attribution from CLI Context

**File:** `backend/app/audit.py`

**Key constraint — `tenant_id` FK is NOT NULL:**
```python
# audit.py:40-41 [VERIFIED: codebase]
tenant_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
)
```

`AuditLog.tenant_id` has a FK to `tenants.id` with `nullable=False`. When `audit()` is called with `user=None`, it substitutes `uuid.UUID(int=0)` (`"00000000-0000-0000-0000-000000000000"`) as the `tenant_id`. This will fail at commit time with a FK constraint violation because no tenant with that UUID exists in the database.

**`user_id` is nullable — no issue there:**
```python
# audit.py:43 [VERIFIED: codebase]
user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
```

**Resolution — synthetic CurrentUser with real tenant_id:**

The CLI rotation function must:
1. Open a DB session.
2. Query for the first (or any) tenant: `SELECT id FROM tenants LIMIT 1`.
3. Construct a synthetic `CurrentUser` object:
   ```python
   from app.auth.schemas import CurrentUser
   import uuid
   cli_actor = CurrentUser(
       id=uuid.UUID(int=0),      # user_id → None (field is nullable)
       tenant_id=<real_tenant_id>,  # FK satisfied
       email="system:cli",
       role="SYSTEM",
   )
   ```
4. Call `await audit(db, cli_actor, "encryption.key_rotated", "encryption_key", None, {"row_count": N})`.

**Why this works:** `user_id` is stored as `user.id if user else None` — but even if `uuid.UUID(int=0)` is passed for `id`, the SQLAlchemy mapping stores it as-is. Since there is no user with `id=UUID(int=0)`, the FK `SET NULL` constraint would fire on FK violation — but `user_id` uses `ondelete="SET NULL"` which governs DELETE cascades, not INSERT FK validation. An INSERT with `user_id=uuid.UUID(int=0)` would still fail FK validation if that UUID doesn't exist.

**Revised resolution — pass user=None, set tenant_id explicitly:**

The cleanest approach is to NOT use the `audit()` helper and instead write `AuditLog` directly, bypassing the `user → tenant_id` indirection:

```python
# [VERIFIED: codebase — app/audit.py:36-50 AuditLog model]
from app.audit import AuditLog
from datetime import UTC, datetime
import uuid

log = AuditLog(
    tenant_id=first_real_tenant_id,   # queried from DB
    user_id=None,                      # no authenticated user
    user_email="system:cli",
    action="encryption.key_rotated",
    resource_type="encryption_key",
    resource_id=None,
    details={"row_count": N, "dry_run": False},
    ip_address=None,
    created_at=datetime.now(UTC),
)
db.add(log)
await db.commit()
```

This avoids the `user → tenant_id` indirection entirely, satisfies the FK, and stores a meaningful `user_email` for SIEM/CEF output.

**If zero tenants exist (fresh DB with no data):** The rotation would have no rows to rotate anyway, so the audit row can be skipped in that edge case. The CLI should check `row_count > 0` before emitting the audit row, or handle the no-tenant case gracefully.

**Action for planner:** The rotation logic function should accept an `audit: bool = True` parameter, query the first tenant ID, and write `AuditLog` directly (not via the `audit()` helper) to avoid the FK sentinel issue. The existing `audit()` helper is designed for request-context use with a real `CurrentUser`.

---

### 2. Fernet Refactor for Explicit-Key Operations

**File:** `backend/app/encryption.py` (31 lines total)

**Current implementation:**
```python
# encryption.py:10-13 [VERIFIED: codebase]
def _get_fernet() -> Fernet:
    """Get Fernet instance from the configured encryption key."""
    key = settings.encryption_key.encode()
    return Fernet(key)

def encrypt_value(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()

def decrypt_value(ciphertext: str) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
```

**Problem:** `_get_fernet()` always reads `settings.encryption_key`. The rotate CLI needs to decrypt with an explicit OLD key and re-encrypt with an explicit NEW key — these may differ from `settings.encryption_key` (the new key has not been written to `.env` yet during rotation).

**Recommended minimal refactor — add `_fernet_for()` private helper:**

```python
# Add to encryption.py [VERIFIED: minimal change, preserves existing API]
def _fernet_for(key: str) -> Fernet:
    """Return a Fernet instance for an explicit key string."""
    return Fernet(key.encode())

# _get_fernet() stays unchanged — used by existing encrypt_value/decrypt_value
def _get_fernet() -> Fernet:
    key = settings.encryption_key.encode()
    return Fernet(key)
```

`encrypt_value` and `decrypt_value` remain unchanged. The rotation logic imports and calls `_fernet_for(old_key)` and `_fernet_for(new_key)` directly. This is a 4-line addition with zero risk of breaking the existing API.

**Alternative:** Add optional `key: str | None = None` parameters to `encrypt_value`/`decrypt_value`. Rejected — more invasive, changes the public API surface.

**Validation that the key is valid before rotation:**
```python
# [VERIFIED: python3 test — ValueError raised for all invalid key inputs]
try:
    Fernet(key.encode())
except ValueError:
    # key is not a valid 32-byte url-safe base64 Fernet key
    raise SystemExit("--new-key is not a valid Fernet key")
```

**`InvalidToken` for wrong-key decryption (D-03 pre-flight):**
```python
# [VERIFIED: python3 test]
from cryptography.fernet import Fernet, InvalidToken
# Decrypting ciphertext with the wrong key raises InvalidToken
# This is the exception type the pre-flight must catch per row
```

---

### 3. CLI Module Structure for `python -m app.encryption`

**Mechanics of `python -m`:**

`python -m app.encryption` works with either:
- A single module file `app/encryption.py` that has `if __name__ == "__main__":` block
- A package `app/encryption/` with `__main__.py`

Both are equivalent for the `python -m` invocation. The single-module approach is lower risk.

**Existing convention:**
`backend/create_admin.py` uses `if __name__ == "__main__": asyncio.run(create_admin())` and is invoked as `docker compose exec -T backend python3 /app/create_admin.py`. That is invoked by path, not by `-m`. For `python -m app.encryption`, the `-m` mechanism sets `__name__ == "__main__"` for the module — same result.

**Single-module recommendation:**

Add argparse subcommand dispatch at the bottom of `backend/app/encryption.py`:

```python
# At the bottom of encryption.py [ASSUMED: argparse structure; mechanics VERIFIED]
if __name__ == "__main__":
    import argparse, asyncio, sys

    parser = argparse.ArgumentParser(description="GetVul encryption key management")
    sub = parser.add_subparsers(dest="command", required=True)

    rot = sub.add_parser("rotate", help="Re-encrypt all connector credentials with a new key")
    rot.add_argument("--new-key", required=True)
    rot.add_argument("--dry-run", action="store_true")
    rot.add_argument("--yes", action="store_true")

    sub.add_parser("verify", help="Decrypt all connector credentials with the current key (read-only)")
    sub.add_parser("generate-key", help="Print a new Fernet key")

    args = parser.parse_args()

    if args.command == "generate-key":
        print(generate_key())
    elif args.command == "rotate":
        asyncio.run(_cmd_rotate(args))
    elif args.command == "verify":
        asyncio.run(_cmd_verify())
```

**Invocation:**
```bash
docker compose exec -T backend python3 -m app.encryption rotate --new-key <key>
docker compose exec -T backend python3 -m app.encryption verify
docker compose exec -T backend python3 -m app.encryption generate-key
```

**Why not package:** Package conversion requires creating `app/encryption/__init__.py` (moving existing module contents) and `app/encryption/__main__.py`. The one existing importer (`from app.encryption import decrypt_value, encrypt_value` in `connectors/service.py:17`) would still work because `__init__.py` would export the same names. However, this is additional file surgery with no functional benefit — the single-module approach is lower risk and matches the existing `create_admin.py` convention.

**`python -m` vs direct path note:** `install.sh:88` invokes CLIs as `python3 /app/create_admin.py` (by path). For consistency and because SC#2 mandates `python -m app.encryption`, document the `-m` invocation in the runbook. Both work; `-m` is slightly safer because it handles `sys.path` correctly from any working directory inside the container.

---

### 4. Cross-Tenant Connector Rotation Query

**Model:** `backend/app/ticketing/models.py:35-51` [VERIFIED: codebase]

`ConnectorConfig.credentials_secret_arn` (line 44): `Mapped[str | None] = mapped_column(Text)`. Stores JSON string of form `{"field_name": "<fernet_ciphertext>", ...}`.

**Encryption shape confirmed from `connectors/service.py:64`:**
```python
# [VERIFIED: codebase]
encrypted_creds = json.dumps({k: encrypt_value(v) for k, v in body.credentials.items()})
```
Each value in the JSON dict is an independent Fernet ciphertext. Re-encryption decrypts each value and re-encrypts it.

**Query for all rows across all tenants:**
```python
# [VERIFIED: scheduler.py:82 uses this pattern — VERIFIED: codebase]
result = await db.execute(
    select(ConnectorConfig).where(
        ConnectorConfig.credentials_secret_arn.isnot(None)
    )
)
connectors = result.scalars().all()
```
No `tenant_id` filter — rotation must affect every tenant's rows in one transaction.

**`get_decrypted_credentials` (connectors/service.py:132-140) swallows errors — MUST NOT be used for rotation:**
```python
# [VERIFIED: codebase — this is the silent path to AVOID]
def get_decrypted_credentials(connector: ConnectorConfig) -> dict[str, str]:
    if not connector.credentials_secret_arn:
        return {}
    try:
        encrypted_map = json.loads(connector.credentials_secret_arn)
        return {k: decrypt_value(v) for k, v in encrypted_map.items()}
    except Exception:
        return {}  # silently returns {} on decrypt failure
```

The rotation pre-flight and rotation itself must decrypt explicitly and let `InvalidToken` propagate:

```python
# Correct pattern for rotation [VERIFIED: derives from known Fernet API]
import json
from cryptography.fernet import InvalidToken

encrypted_map = json.loads(connector.credentials_secret_arn)
for field, ciphertext in encrypted_map.items():
    try:
        plaintext = _fernet_for(old_key).decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        failures.append((str(connector.id), connector.tenant_id, field))
```

**Row count for confirmation prompt:**

```python
count_q = await db.execute(
    select(func.count(ConnectorConfig.id)).where(
        ConnectorConfig.credentials_secret_arn.isnot(None)
    )
)
row_count = count_q.scalar_one()
tenant_count_q = await db.execute(
    select(func.count(ConnectorConfig.tenant_id.distinct())).where(
        ConnectorConfig.credentials_secret_arn.isnot(None)
    )
)
tenant_count = tenant_count_q.scalar_one()
```

---

### 5. Startup Check in `lifespan`

**File:** `backend/app/main.py:36-80` [VERIFIED: codebase]

`lifespan` runs before the app serves any traffic. The structlog `logger` is already imported at module level (`main.py:33`). The startup check should be inserted at the TOP of the `lifespan` function body, before the scheduler start and Redis initialization.

**`settings.environment` default:**
```python
# config.py:11 [VERIFIED: codebase]
environment: str = "production"
```
Default is `"production"` — so a misconfigured `.env` that omits `ENVIRONMENT=development` will hit the hard-fail path. This is intentional (safe default).

**Exact placeholder strings:**
```python
# config.py:16 [VERIFIED: codebase]
jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"

# config.py:22 [VERIFIED: codebase]
encryption_key: str = "CHANGE-ME-generate-with-python-c-from-cryptography.fernet-import-Fernet-Fernet.generate_key"
```

**Validation logic (D-11):**

```python
# [VERIFIED: Fernet constructor raises ValueError for all invalid key forms]
from cryptography.fernet import Fernet

ENCRYPTION_KEY_PLACEHOLDER = (
    "CHANGE-ME-generate-with-python-c-from-cryptography.fernet-import-Fernet-Fernet.generate_key"
)
JWT_SECRET_PLACEHOLDER = "CHANGE-ME-IN-PRODUCTION"

def _check_secrets_at_startup(logger) -> list[str]:
    """Return list of warning strings; raises RuntimeError in production if any found."""
    warnings = []

    # Encryption key checks
    enc_key = settings.encryption_key
    if not enc_key or enc_key == ENCRYPTION_KEY_PLACEHOLDER:
        warnings.append("ENCRYPTION_KEY is unset or uses the default placeholder")
    else:
        try:
            Fernet(enc_key.encode())
        except ValueError:
            warnings.append("ENCRYPTION_KEY is set but is not a valid Fernet key")

    # JWT key check
    if settings.jwt_secret_key == JWT_SECRET_PLACEHOLDER:
        warnings.append("JWT_SECRET_KEY uses the default placeholder")

    return warnings
```

**Hard-fail vs warn (D-10):**

```python
# Inside lifespan, before yield [VERIFIED: lifespan structure from main.py:37-74]
issues = _check_secrets_at_startup(logger)
if issues:
    for msg in issues:
        if settings.environment == "production":
            logger.critical("startup_secret_check_failed", issue=msg)
        else:
            logger.warning("startup_secret_check_warning", issue=msg)
    if settings.environment == "production":
        raise RuntimeError(
            "Backend refused to start: insecure secrets detected. "
            "Set ENCRYPTION_KEY and JWT_SECRET_KEY to non-placeholder values."
        )
```

`raise RuntimeError` inside `lifespan` propagates through FastAPI's startup and prevents uvicorn from serving traffic — this is the correct hard-fail mechanism. [VERIFIED: FastAPI lifespan exception behavior is standard Python asynccontextmanager semantics]

---

### 6. E2E Rotation Test Infrastructure

**File:** `backend/tests/conftest.py` [VERIFIED: codebase]

**Available fixtures for the E2E test:**

| Fixture | Scope | What it provides |
|---------|-------|-----------------|
| `db_session` | function | `AsyncSession` against live Postgres; skips if DB unreachable |
| `tenant_a` | function | Creates an isolated `Tenant`, yields `tenant_id: uuid.UUID` |
| `tenant_b` | function | Creates a second `Tenant`, yields `tenant_id: uuid.UUID` |
| `_reset_engine_pool` | function (autouse) | Disposes engine pool before each test — fixes event-loop binding |

**Important note on `db_session.commit()` and cleanup:**

From `conftest.py:163-166`:
> "Committed rows are NOT rolled back at fixture teardown — the rollback path only discards uncommitted state."

The conftest TRUNCATE covers: `audit_logs, vulnerabilities, assets, notifications, users, tenants, daily_snapshots`. It does NOT explicitly list `connector_configs`, but `connector_configs.tenant_id` has `ondelete="CASCADE"` (confirmed at `ticketing/models.py:40`). TRUNCATING `tenants` with `CASCADE` will cascade-delete all `connector_configs` rows. The E2E test's seeded rows are cleaned up automatically.

**E2E test structure (D-18):**

The rotation logic must be factored as a standalone async function callable from tests — NOT just a CLI `__main__` block. Recommended signature:

```python
# rotation_core.py or within encryption.py [ASSUMED: exact name is Claude's Discretion]
async def rotate_credentials(
    old_key: str,
    new_key: str,
    dry_run: bool = False,
) -> dict:
    """
    Returns: {"rotated": N, "failures": [...], "tenants": M}
    Raises: RotationPreflightError if any row fails pre-flight decrypt.
    """
    ...
```

**E2E test flow:**

```python
# tests/test_encryption_rotation.py [ASSUMED: file name]
@pytest.mark.asyncio
async def test_rotation_sc4_sequence(db_session, tenant_a):
    key_a = generate_key()
    key_b = generate_key()

    # Seed ConnectorConfig row encrypted with key_a
    creds = {"api_key": "secret123"}
    encrypted_with_a = json.dumps({k: _fernet_for(key_a).encrypt(v.encode()).decode()
                                   for k, v in creds.items()})
    connector = ConnectorConfig(
        tenant_id=tenant_a,
        connector_type="NESSUS",
        credentials_secret_arn=encrypted_with_a,
    )
    db_session.add(connector)
    await db_session.commit()  # must commit so rotation's own session sees the rows

    # SC#4 step 1: Rotate A → B
    result = await rotate_credentials(old_key=key_a, new_key=key_b)
    assert result["rotated"] == 1

    # SC#4 step 2: Decrypt with B — succeeds
    # ... reload connector, verify decrypts with key_b

    # SC#4 step 3: Revert — attempt rotate B → A
    await rotate_credentials(old_key=key_b, new_key=key_a)

    # SC#4 step 4: Attempt decrypt with B — must fail
    # ... reload connector, attempt Fernet(key_b).decrypt(...) → InvalidToken
```

**Key constraint:** Rotation's `async_session_factory()` session is independent from `db_session`. The test must `await db_session.commit()` before invoking rotation so the rows are visible to the rotation session.

---

## Standard Stack

### Core (no new dependencies needed)
| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| `cryptography` | ≥43.0 | Fernet encrypt/decrypt, `InvalidToken` | `backend/pyproject.toml` [VERIFIED] |
| `sqlalchemy[asyncio]` | existing | Cross-tenant `ConnectorConfig` query | existing dep [VERIFIED] |
| `structlog` | ≥24.0 | Startup warning / error logging | `backend/pyproject.toml` [VERIFIED] |
| `argparse` | stdlib | CLI subcommand dispatch | Python stdlib [VERIFIED] |

**No new packages to install.** All required libraries are already in `backend/pyproject.toml`.

---

## Architecture Patterns

### System Architecture Diagram

```
[CLI invocation]
  python -m app.encryption rotate --new-key <key>
        |
        v
[app/encryption.py __main__ block]
  argparse → _cmd_rotate(args)
        |
        v
[rotation_core function]
  1. _fernet_for(old_key) — validate old key
  2. _fernet_for(new_key) — validate new key
  3. async_session_factory() → DB session
  4. SELECT ConnectorConfig WHERE credentials_secret_arn IS NOT NULL
        |
        v
[Pre-flight: decrypt ALL rows with old key]
  For each row: json.loads(credentials_secret_arn) → {field: ciphertext}
  Fernet(old_key).decrypt(ciphertext) → plaintext or InvalidToken
  If ANY fail → roll back → report failures → sys.exit(1)
        |
        v
[Re-encrypt: write new ciphertexts within same transaction]
  For each row: {field: Fernet(new_key).encrypt(plaintext)}
  connector.credentials_secret_arn = json.dumps(new_encrypted_map)
        |
        v
[Post-commit verify: decrypt ALL rows with new key (D-04)]
  For each row: Fernet(new_key).decrypt(new_ciphertext) → plaintext
  If ANY fail → roll back → sys.exit(1)
        |
        v
[Commit transaction]
        |
        v
[Write AuditLog row directly to DB]
  tenant_id = first real tenant from DB
  user_email = "system:cli"
  action = "encryption.key_rotated"
  details = {"row_count": N}
        |
        v
[Print: "Set ENCRYPTION_KEY=<new> in .env and restart the backend"]


[app/main.py lifespan startup]
  → _check_secrets_at_startup()
  → Fernet(settings.encryption_key.encode()) → ValueError if invalid
  → compare to placeholder strings
  → warn (dev) or raise RuntimeError (production)
```

### Recommended Project Structure (changes only)

```
backend/
├── app/
│   └── encryption.py        # add _fernet_for() + rotate_credentials() async fn + __main__ block
├── tests/
│   └── test_encryption_rotation.py  # E2E rotation test (new)
└── docs/
    └── 16-security.md       # add "Encryption Key Backup & Rotation" section (D-13..D-17)
```

### Anti-Patterns to Avoid

- **Calling `get_decrypted_credentials()` in rotation:** It silently returns `{}` on decrypt failure (confirmed at `connectors/service.py:139`). Rotation must catch `InvalidToken` explicitly per field.
- **Using `audit(db, None, ...)` for the CLI audit event:** `uuid.UUID(int=0)` as `tenant_id` violates the `tenant_id` FK to `tenants.id`. Write `AuditLog` directly.
- **Using `settings.encryption_key` inside rotation functions:** The rotate command's old/new keys must be passed explicitly; they differ from `settings.encryption_key` during the rotation window.
- **Leaving `raise RuntimeError` inside an `except` block in lifespan without re-raising:** FastAPI's lifespan must actually propagate the exception to prevent startup; don't catch and swallow it.
- **Converting `encryption.py` to a package:** Only one importer exists (`connectors/service.py:17`), and the single-module approach carries zero conversion risk.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Key validity check | Custom base64/length validator | `Fernet(key.encode())` raising `ValueError` | Fernet's constructor does the authoritative check [VERIFIED] |
| Wrong-key detection | String comparison | `InvalidToken` from `cryptography.fernet` | Cryptographic verification, not string matching [VERIFIED] |
| New key generation | Custom entropy source | `Fernet.generate_key()` → `generate_key()` already in `encryption.py:28` | Already exists in codebase [VERIFIED] |
| Async DB session | Raw asyncpg | `async_session_factory()` from `app.db.session` | Established pattern in `create_admin.py` [VERIFIED] |

---

## Common Pitfalls

### Pitfall 1: `tenant_id` FK Violation When Emitting CLI Audit Event
**What goes wrong:** Calling `audit(db, None, ...)` uses `uuid.UUID(int=0)` as `tenant_id`, which has no matching row in `tenants`. The `await db.commit()` raises an IntegrityError and the rotation appears to succeed but the audit commit fails.
**Why it happens:** `audit()` was designed for request context with a real `CurrentUser`.
**How to avoid:** Write `AuditLog` directly (bypassing `audit()`) with a real `tenant_id` queried from the DB. [VERIFIED: codebase analysis]
**Warning signs:** `IntegrityError: insert or update on table "audit_logs" violates foreign key constraint`

### Pitfall 2: Rotation Logic Not Separated from CLI `__main__` Block
**What goes wrong:** D-18 requires invoking rotation as a function from the test. If all logic is in the `if __name__ == "__main__":` block, it can only be tested as a subprocess.
**Why it happens:** Following `create_admin.py`'s simple structure too literally.
**How to avoid:** Extract `rotate_credentials(old_key, new_key, dry_run)` as a standalone async function that is importable. The `__main__` block calls it.

### Pitfall 3: Seeding Test Rows Without Committing Before Rotation
**What goes wrong:** Test seeds `ConnectorConfig` rows via `db_session` but doesn't call `db_session.commit()`. The rotation's independent `async_session_factory()` session sees 0 rows. Rotation reports 0 rotated; the test's decrypt assertion operates on stale local state.
**Why it happens:** Relying on flush/rollback without committing.
**How to avoid:** Call `await db_session.commit()` after seeding, before invoking rotation. [VERIFIED: conftest.py:163 note about committed rows]

### Pitfall 4: `settings.environment` Default Causes Unexpected Hard-Fail in CI
**What goes wrong:** CI doesn't set `ENVIRONMENT=development`, so the default `"production"` triggers the hard-fail startup check, and the test suite can't start.
**Why it happens:** `config.py:11` defaults `environment` to `"production"`. [VERIFIED: codebase]
**How to avoid:** The startup check function must only run in the `lifespan`, not at import time. CI test environments (which call `create_app()` without setting `ENVIRONMENT`) must set `ENVIRONMENT=development` in their env, OR the test's `monkeypatch` must override `settings.environment`. Note the existing `redis_test_url` fixture (conftest.py:53-59) shows the pattern for patching settings.

### Pitfall 5: `_get_fernet()` Still Called with Placeholder Key After Startup Check
**What goes wrong:** In dev mode, startup check warns but continues. If an operator then calls `encrypt_value()`/`decrypt_value()`, `_get_fernet()` constructs `Fernet("CHANGE-ME-...")` which raises `ValueError` at encrypt/decrypt time (not startup), producing a confusing error.
**Why it happens:** The placeholder is not a valid Fernet key (confirmed via `python3` test).
**How to avoid:** This is acceptable behavior — the startup check explicitly warns the operator. The `ValueError` at runtime is a secondary signal. No additional change needed beyond D-11.

### Pitfall 6: Mixed-Key State if Transaction Rolls Back After Some Rows Written
**What goes wrong:** Partial writes if the session is flushed mid-loop and the DB commits individual rows.
**Why it happens:** SQLAlchemy `flush()` sends SQL to DB within the transaction but doesn't commit. As long as the rotation never calls `await db.commit()` mid-loop, the transaction is atomic. If `db.commit()` is called in a loop, rows are committed one-by-one.
**How to avoid:** D-01 and D-03 mandate a single transaction. Load all rows, re-encrypt all in-memory, run post-verify (D-04), then issue ONE `await db.commit()`. [VERIFIED: SQLAlchemy async session semantics]

---

## Code Examples

### _fernet_for() helper (add to encryption.py)
```python
# backend/app/encryption.py — minimal addition [VERIFIED: derives from existing _get_fernet]
def _fernet_for(key: str) -> Fernet:
    """Return a Fernet instance for an explicit key string.

    Raises ValueError if key is not a valid 32-byte url-safe base64 Fernet key.
    """
    return Fernet(key.encode())
```

### Startup check placement in lifespan
```python
# backend/app/main.py — insert at top of lifespan body, before scheduler start
# [VERIFIED: lifespan at main.py:37-74 is the correct location]
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # D-10..D-12: validate secrets before serving any traffic
    _check_secrets_at_startup()   # raises RuntimeError in production if bad

    if settings.environment in ("development", "production"):
        from app.connectors.scheduler import start_scheduler
        start_scheduler()
    ...
```

### Cross-tenant connector query (rotation pre-flight)
```python
# [VERIFIED: codebase — ConnectorConfig model at ticketing/models.py:35]
from sqlalchemy import select, func
from app.ticketing.models import ConnectorConfig

result = await db.execute(
    select(ConnectorConfig).where(
        ConnectorConfig.credentials_secret_arn.isnot(None)
    )
)
connectors = result.scalars().all()
```

### Direct AuditLog write for CLI context
```python
# [VERIFIED: AuditLog model at audit.py:36-50; FK analysis above]
from app.audit import AuditLog
from datetime import UTC, datetime

log = AuditLog(
    tenant_id=first_tenant_id,     # real UUID from SELECT tenants LIMIT 1
    user_id=None,
    user_email="system:cli",
    action="encryption.key_rotated",
    resource_type="encryption_key",
    resource_id=None,
    details={"row_count": rotated_count, "dry_run": False},
    ip_address=None,
    created_at=datetime.now(UTC),
)
db.add(log)
await db.commit()
```

---

## Validation Architecture

`workflow.nyquist_validation` is absent from `.planning/config.json` — treated as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio 0.24, `asyncio_mode = "auto"` |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `cd backend && pytest tests/test_encryption_rotation.py -x -q` |
| Full suite command | `cd backend && pytest tests/ -q --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-05-01 | Runbook section present in `docs/16-security.md` with RTO ≤ 15 min | manual / doc check | `grep -q "RTO" docs/16-security.md && echo PASS` | ❌ Wave 0 |
| PROD-05-02 | Rotation re-encrypts all rows, decrypt round-trip succeeds, reverted key fails | integration (real Postgres) | `pytest tests/test_encryption_rotation.py -x -q` | ❌ Wave 0 |
| PROD-05-03 | `python -m app.encryption rotate --dry-run` exits 0 with 0 rows when DB has no connectors | unit | `pytest tests/test_encryption_rotation.py::test_dry_run_no_rows -x` | ❌ Wave 0 |
| PROD-05-03 | `python -m app.encryption generate-key` outputs valid Fernet key | unit | `pytest tests/test_encryption_rotation.py::test_generate_key -x` | ❌ Wave 0 |
| PROD-05-03 | `python -m app.encryption verify` with all-OK rows returns N OK, 0 failing | integration | `pytest tests/test_encryption_rotation.py::test_verify_all_ok -x` | ❌ Wave 0 |
| PROD-05-04 | Startup with placeholder encryption key: warns in dev, raises in prod | unit | `pytest tests/test_encryption_rotation.py::test_startup_check_* -x` | ❌ Wave 0 |
| PROD-05-04 | Startup with placeholder JWT key: warns in dev, raises in prod | unit | `pytest tests/test_encryption_rotation.py::test_startup_check_jwt -x` | ❌ Wave 0 |

**SC#4 rotation test (PROD-05-02) is the critical integration test.** It requires real Postgres and uses `db_session` + `tenant_a` from conftest. It will be skipped if Postgres is unreachable (existing `_db_reachable()` skip pattern in conftest).

**Startup check tests (PROD-05-04) are unit-level** — they can monkeypatch `settings` without DB access and run fast.

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/test_encryption_rotation.py -x -q`
- **Per wave merge:** `cd backend && pytest tests/ -q --tb=short`
- **Phase gate:** Full suite green (including integration tests with real Postgres) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_encryption_rotation.py` — covers all PROD-05-01..04 assertions
- [ ] No framework install needed — pytest-asyncio already in `pyproject.toml` [VERIFIED]
- [ ] No conftest changes needed — `db_session`, `tenant_a`, `tenant_b`, `_reset_engine_pool` already present [VERIFIED]

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | partial | CLI is operator-only; no HTTP auth needed |
| V5 Input Validation | yes | Validate `--new-key` via `Fernet(key)` constructor before any DB writes |
| V6 Cryptography | yes | Use `Fernet.generate_key()` (32-byte random key) — never hand-roll |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Key material in audit log / structlog output | Information Disclosure | Never log key bytes; log only row counts and timestamps |
| Rotation leaving mixed-key state on failure | Tampering | D-01/D-03: single transaction, abort-all-or-nothing |
| `--new-key` value visible in `ps aux` | Information Disclosure | [ASSUMED] Document that operators should use env-var or stdin redirection in production environments |
| Backup key stored on same VM as the DB | Elevation of Privilege | D-15: prescribe off-box vault storage |

---

## Environment Availability

Step 2.6: No external tool dependencies for this phase. All libraries are existing Python packages in `backend/pyproject.toml`. Real Postgres is required for the integration test (PROD-05-02), same as Phase 1 and Phase 10 integration tests.

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| Postgres | E2E rotation test | ✓ (existing CI infra) | Uses existing conftest `db_session` fixture; skips if unreachable |
| `cryptography` ≥43 | Fernet operations | ✓ | `backend/pyproject.toml` [VERIFIED] |
| `structlog` ≥24 | Startup warning | ✓ | `backend/pyproject.toml` [VERIFIED] |
| `argparse` | CLI subcommands | ✓ | Python stdlib |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `argparse` is the right subcommand dispatcher (vs Click, Typer, etc.) | CLI Module Structure | Minimal — CONTEXT.md says "match the codebase; no CLI framework in use"; argparse is standard |
| A2 | `--new-key` passed as CLI arg exposes key in `ps aux` process list | Security Domain | Low for single-VM topology; document in runbook if confirmed a concern |
| A3 | The rotation core function should live in `encryption.py` rather than a separate `rotation.py` | Architecture | Low — either location works; single file is simpler for the single-module approach |

**All critical claims (FK constraint, Fernet exception types, placeholder strings, conftest fixtures, scheduler query shape) are VERIFIED against codebase source.**

---

## Open Questions

1. **Audit row when zero tenants exist**
   - What we know: The rotation would find 0 `ConnectorConfig` rows in a fresh DB; querying `tenants LIMIT 1` would return None.
   - What's unclear: Should the audit row be skipped, or should we use a fallback (e.g., `uuid.UUID(int=0)` with a comment)?
   - Recommendation: Skip the audit row if no tenants exist; log a structlog event instead. This edge case only occurs on a fresh, never-configured instance.

2. **SMTP config Fernet encryption scope**
   - What we know: `tenants.smtp_config` (JSONB) stores SMTP passwords but is NOT Fernet-encrypted (grep confirms only `connectors/service.py` uses `encrypt_value`/`decrypt_value`).
   - What's unclear: Is this intentional (SMTP passwords stored in plain JSONB) or an oversight?
   - Recommendation: Out of scope for this phase per CONTEXT.md. Note in runbook that SMTP credentials are not under `ENCRYPTION_KEY` protection.

---

## Sources

### Primary (HIGH confidence)
- `backend/app/audit.py` — audit function signature, AuditLog model, FK constraints verified
- `backend/app/encryption.py` — `_get_fernet()`, `encrypt_value`, `decrypt_value`, `generate_key` verified
- `backend/app/connectors/service.py` — credentials JSON structure, `get_decrypted_credentials` silent-swallow pattern verified
- `backend/app/ticketing/models.py:35-51` — `ConnectorConfig.credentials_secret_arn` type and FK cascade verified
- `backend/app/config.py:11,16,22` — exact placeholder strings and `environment` default verified
- `backend/app/main.py:36-74` — lifespan structure and structlog logger verified
- `backend/tests/conftest.py` — DB fixtures, TRUNCATE scope, `db_session` semantics verified
- `backend/create_admin.py` — CLI convention (`asyncio.run`, `async_session_factory`) verified
- `python3 -c ...` tests — Fernet `ValueError` on invalid key, `InvalidToken` on wrong-key decrypt, `uuid.UUID(int=0)` value verified

### Secondary (MEDIUM confidence)
- `backend/app/connectors/scheduler.py` — cross-tenant query pattern (`credentials_secret_arn.isnot(None)` without tenant filter) verified

---

## Metadata

**Confidence breakdown:**
- Audit FK constraint and resolution: HIGH — read actual model code and traced the null-user path
- Fernet refactor shape: HIGH — read existing `encryption.py`, verified exception types via python3
- CLI module structure: HIGH — confirmed single importer, verified `python -m` semantics
- Cross-tenant query: HIGH — confirmed against scheduler pattern and model FK definitions
- Startup check: HIGH — exact placeholder strings from `config.py`, `lifespan` location from `main.py`
- E2E test infra: HIGH — read full `conftest.py`, traced TRUNCATE cascade through FK

**Research date:** 2026-07-03
**Valid until:** 2026-08-03 (stable internal codebase; no external APIs)
