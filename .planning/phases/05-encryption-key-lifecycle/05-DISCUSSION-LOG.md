# Phase 5: Encryption Key Lifecycle - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-03
**Phase:** 05-encryption-key-lifecycle
**Areas discussed:** Rotation model, Rotation safety, Startup check, Backup runbook, CLI surface, E2E test, Audit event, Single-key documentation

---

## Rotation model

| Option | Description | Selected |
|--------|-------------|----------|
| Hard cutover | Single atomic transaction; ENCRYPTION_KEY stays scalar | ✓ |
| MultiFernet grace period | ENCRYPTION_KEYS comma-list; decrypt-any/encrypt-first, lazy re-encrypt | |
| Hard cutover + fallback read | Cutover + transparent secondary OLD_ENCRYPTION_KEY fallback | |

**User's choice:** Hard cutover
**Notes:** Single-VM topology, 15-min sync intervals make a brief re-encrypt window acceptable.

### Follow-up: Key flow

| Option | Description | Selected |
|--------|-------------|----------|
| Old from .env, new from flag | OLD from settings.encryption_key, NEW via --new-key, operator updates .env after | ✓ |
| Both via flags | --old-key and --new-key explicit, ignore .env | |
| Tool rewrites .env | CLI re-encrypts and rewrites ENCRYPTION_KEY line automatically | |

**User's choice:** Old from .env, new from flag
**Notes:** Tool writes no secrets to disk; explicit operator control.

---

## Rotation safety

### Failure mode

| Option | Description | Selected |
|--------|-------------|----------|
| Abort all, roll back | Pre-flight decrypt-all; any failure aborts + rolls back the whole rotation | ✓ |
| Skip + report | Rotate clean rows, leave failing rows on old key | |

**User's choice:** Abort all, roll back
**Notes:** Scalar-key model can't represent a mixed-key state.

### Safeguards (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Post-commit round-trip verify | Decrypt every row with NEW key before commit; roll back on failure | ✓ |
| --dry-run mode | Full decrypt/would-re-encrypt pass, writes nothing | ✓ |
| Confirmation prompt | Interactive [y/N] unless --yes | ✓ |
| Print backup reminder first | Require backup/snapshot acknowledgement before running | ✓ |

**User's choice:** All four.

---

## Startup check

### Severity

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-fail in prod, warn in dev | Refuse boot in production on bad key; warn+continue in dev | ✓ |
| Warn everywhere, never block | Always warn, never prevent boot | |
| Hard-fail everywhere | Refuse boot in any environment | |

**User's choice:** Hard-fail in prod, warn in dev
**Notes:** Keeps zero-config dev/test/CI working on the default key.

### Conditions (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Exact placeholder match | Key equals CHANGE-ME-… default | ✓ |
| Empty / unset | Key is empty or missing | ✓ |
| Invalid Fernet key | Non-placeholder but not a valid Fernet key (Fernet(key) fails) | ✓ |
| Also check JWT secret | Extend placeholder check to jwt_secret_key | ✓ |

**User's choice:** All four.
**Notes:** JWT check is a startup-warning add only — no JWT rotation tooling.

---

## Backup runbook

### RTO

| Option | Description | Selected |
|--------|-------------|----------|
| ≤ 15 minutes | Paste backed-up key into .env + restart | ✓ |
| ≤ 1 hour | More conservative buffer | |
| Best-effort, no number | No RTO commitment (misses SC#1) | |

**User's choice:** ≤ 15 minutes

### Key storage

| Option | Description | Selected |
|--------|-------------|----------|
| Prescribe secrets manager / vault | Mandate off-box vault storage, name owner | ✓ |
| Operator's choice, list requirements | State requirements, don't name a tool | |

**User's choice:** Prescribe a secrets manager / password vault

### Lost key

| Option | Description | Selected |
|--------|-------------|----------|
| Document unrecoverable + re-enter path | Unrecoverable; generate new key + re-enter creds via UI, with steps | ✓ |
| Just state it's unrecoverable | Note permanence without re-entry procedure | |

**User's choice:** Document unrecoverable + re-enter path

---

## CLI surface (multi-select + disambiguation)

| Option | Description | Selected |
|--------|-------------|----------|
| verify / check | Read-only decrypt-all health report | ✓ |
| generate-key | Print a fresh Fernet key | ✓ |
| rotate only | Just the rotate command | (contradictory pick) |

**User's choice (disambiguated):** rotate + verify + generate-key
**Notes:** Initial multi-select included the contradictory "rotate only"; confirmed via
follow-up that the intended surface is all three subcommands.

---

## E2E test

| Option | Description | Selected |
|--------|-------------|----------|
| Real Postgres via existing fixture | Seed rows, invoke rotation as a function, assert SC#4 sequence | ✓ |
| Invoke CLI as subprocess | Shell out to python -m app.encryption rotate | |

**User's choice:** Real Postgres via existing fixture

---

## Audit event

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — emit encryption.key_rotated | Audit event with row count + timestamp, no key material | ✓ |
| No — stdout report only | Print summary only | |

**User's choice:** Yes — emit encryption.key_rotated

---

## Single-key model documentation

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — state it in the runbook | Explicitly note one global key encrypts all tenants' creds | ✓ |
| No — implied by procedure | Skip explicit callout | |

**User's choice:** Yes — state it in the runbook

---

## Claude's Discretion

- structlog message wording for the startup warning/error.
- CLI module layout (`encryption.py __main__` vs `encryption/__main__.py` package).
- argparse vs. lightweight subcommand dispatcher.
- Precise audit-event actor attribution for the CLI (no request context).

## Deferred Ideas

- MultiFernet grace-period / zero-downtime rotation.
- Fallback-read secondary OLD key during rotation.
- Cloud KMS / envelope encryption / per-tenant keys.
- JWT secret rotation tooling (only the placeholder startup warning is in scope).
- Tool auto-rewriting `.env`.
