# Phase 5: Encryption Key Lifecycle - Context

**Gathered:** 2026-07-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Give operators confidence to **back up, restore, and rotate** the Fernet `ENCRYPTION_KEY`
without losing connector credentials. Delivers four things:

1. A **rotation CLI** (`python -m app.encryption …`) that re-encrypts every connector
   credential row transactionally, with verification.
2. A **startup check** that flags a placeholder / unset / invalid encryption key (and the
   JWT secret placeholder).
3. A **backup & rotation runbook** in `docs/16-security.md` with concrete commands and an
   RTO statement.
4. An **end-to-end rotation test** proving rotation actually rotates.

**Out of scope (do NOT expand into these):**
- Changing how credentials are stored (they stay as JSON `{field: fernet_ciphertext}` in
  `ConnectorConfig.credentials_secret_arn`).
- Any cloud KMS / AWS Secrets Manager backend — Phase 4 removed boto3/Secrets Manager
  entirely; the key lives in `.env`. Do not reintroduce cloud key management.
- Rotating any secret other than `ENCRYPTION_KEY` (the JWT check is a startup-warning add
  only — no JWT rotation tooling).
- Per-tenant keys / envelope encryption — the model is one global key for all tenants.

</domain>

<decisions>
## Implementation Decisions

### Rotation model
- **D-01:** **Hard cutover.** Rotation is a single atomic DB transaction: decrypt every
  connector credential row with the old key, re-encrypt with the new key, commit. No
  MultiFernet, no grace-period dual-key state. `ENCRYPTION_KEY` stays a single scalar env
  var (do NOT introduce an `ENCRYPTION_KEYS` list or a fallback-read key).
- **D-02:** **Key flow:** the CLI reads the OLD key from `settings.encryption_key` (current
  `.env`); the NEW key is passed via `--new-key`. On success the CLI prints an instruction
  to set `ENCRYPTION_KEY=<new>` in `.env` and restart the backend. The tool does NOT write
  to `.env` itself (no secrets written to disk by the tool; explicit operator control).
- Rationale: single-VM topology, syncs run on 15-min intervals (not constant), so a brief
  re-encrypt window is acceptable. Matches SC#2 "single transaction."

### Rotation safety
- **D-03:** **Abort-all-and-roll-back on any failure.** Pre-flight: attempt to decrypt every
  row with the old key first. If a single row fails, abort the whole rotation, roll back the
  transaction, and report which rows failed. Never leave a half-rotated / mixed-key state
  (the scalar-key model cannot represent one).
- **D-04:** **Post-commit round-trip verification.** After re-encrypting, decrypt every row
  again with the NEW key inside the same transaction before committing. If any fails, roll
  back. (Satisfies SC#2 "with verification.")
- **D-05:** **`--dry-run` flag.** Runs the full decrypt-all-with-old + would-re-encrypt pass,
  reports row count and any failures, writes nothing.
- **D-06:** **Confirmation prompt.** Interactive `This will re-encrypt N rows across M
  tenants. Continue? [y/N]`, skippable with `--yes`.
- **D-07:** **Backup reminder first.** Before doing anything, the CLI prints a reminder to
  back up the current `ENCRYPTION_KEY` and take a DB snapshot, and requires acknowledgement.
- **D-08:** **Emit an audit event on success:** `encryption.key_rotated`, recording that
  rotation happened, the row count, and a timestamp — **no key material**. Consistent with
  the app's existing audit-event pattern. NOTE for planner: the CLI runs outside a request
  context (no tenant/user actor) — research how to attribute a system/CLI actor to the audit
  event (see `backend/app/audit.py`).

### CLI command surface
- **D-09:** Three subcommands: **`rotate`** (with `--new-key`, `--dry-run`, `--yes`),
  **`verify`/`check`** (read-only: decrypt every row with the current key, report N OK / M
  failing, rotate nothing — reuses the rotation pre-flight decrypt-all logic), and
  **`generate-key`** (prints a fresh Fernet key, wrapping the existing
  `encryption.generate_key()`; referenced by the backup runbook).

### Startup check
- **D-10:** **Hard-fail in production, warn-and-continue in dev.** If
  `settings.environment == "production"` and the key is bad, raise on startup and refuse to
  boot. In development, log a loud structlog warning but continue (keeps zero-config
  dev/test/CI working on the default key).
- **D-11:** **Trigger conditions** (any of): (a) key equals the literal `CHANGE-ME-…`
  placeholder in `config.py`; (b) key is empty / unset; (c) key is set but is not a valid
  Fernet key — validate by attempting `Fernet(key)` construction (catches typos/truncation).
- **D-12:** **Also check `jwt_secret_key`** against its `CHANGE-ME-IN-PRODUCTION` placeholder
  in the same startup gate (same severity model: hard-fail in prod, warn in dev). This is a
  deliberate small scope extension — the JWT default is an identical footgun next to the
  encryption key. No JWT rotation tooling, just the placeholder warning.
- Home: the check belongs in the `lifespan` startup path in `backend/app/main.py` (structlog
  `logger` already present there).

### Backup runbook (docs/16-security.md)
- **D-13:** Section title: **"Encryption Key Backup & Rotation"** (matches SC#1 intent).
- **D-14:** **RTO ≤ 15 minutes.** Restore = paste the backed-up key into `.env` and restart
  the backend container; 15 min gives margin to locate the key in the vault. Honest for a
  config-file restore (not a data restore).
- **D-15:** **Key storage:** prescribe storing the backup in the org's existing secrets
  vault / password manager (1Password, HashiCorp Vault, cloud secrets manager) — off-box,
  access-controlled, NOT in the repo, NOT on the same VM, NOT in the DB backup. Name who owns
  the vault entry.
- **D-16:** **Lost-key recovery story:** state plainly that connector credentials are
  cryptographically **unrecoverable** without the key; the operator must generate a fresh key
  and **re-enter each connector's credentials through the UI** (which re-encrypts under the
  new key). Include the exact recovery steps.
- **D-17:** **Document the single-key model explicitly:** the runbook states that one global
  `ENCRYPTION_KEY` encrypts every tenant's connector credentials — so rotation affects all
  tenants at once and a lost key impacts everyone.

### Testing
- **D-18:** **E2E rotation test uses a real Postgres** via the existing `backend/tests`
  conftest DB fixture (same infra Phase 1's integration tests used). Seed connector rows,
  invoke the rotation logic as a function, and assert the SC#4 sequence: encrypt with key A →
  rotate to key B → decrypt all rows successfully → revert to key A → **fail** to decrypt
  (proving rotation actually rotated). Not a subprocess test.

### Claude's Discretion
- Exact structlog message wording for the startup warning/error.
- Whether the CLI lives as a `__main__` block in `backend/app/encryption.py` or as a
  `backend/app/encryption/__main__.py` package (must support `python -m app.encryption` per
  SC#2 either way).
- argparse vs. a lightweight subcommand dispatcher (match the codebase — no CLI framework is
  currently used; `create_admin.py` uses plain `asyncio.run` + no args).
- Precise audit-event actor/attribution mechanism for the CLI context (flagged in D-08).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` §"Encryption Key Lifecycle (PROD-05)" — PROD-05-01..04.
- `.planning/ROADMAP.md` §"Phase 5: Encryption Key Lifecycle" — goal + 4 success criteria.
  NOTE: the roadmap/requirements refer to `doc/security.md`, which does not exist — the
  canonical security doc is `docs/16-security.md` (stale drift; write the runbook there).

### Encryption implementation (existing code)
- `backend/app/encryption.py` — Fernet `encrypt_value` / `decrypt_value` / `generate_key`;
  single global key from `settings.encryption_key`. CLI target module.
- `backend/app/connectors/service.py` §64, §99, §132 — how creds are encrypted on
  create/update and the `get_decrypted_credentials` reader (currently **swallows decrypt
  errors → returns `{}`**; rotation must not rely on this silent path).
- `backend/app/ticketing/models.py:44` — `ConnectorConfig.credentials_secret_arn: str | None`
  stores JSON `{field: ciphertext}`.
- `backend/app/config.py:22` — `encryption_key` default placeholder string (exact match
  target for D-11); `:16` — `jwt_secret_key` placeholder (D-12); `:11` `environment` default
  `"production"` (D-10).

### Startup & CLI conventions
- `backend/app/main.py:36-80` — `lifespan` startup path + `structlog` logger (home for the
  startup check, D-10..D-12).
- `backend/create_admin.py` — CLI convention: standalone module, `asyncio.run()`,
  `async_session_factory()`, run via `docker compose exec backend python3 …`.
- `backend/app/audit.py` — audit-event pattern for D-08 (`encryption.key_rotated`).

### Docs & tests
- `docs/16-security.md` — target for the backup/rotation runbook (SC#1). Phase 4 already
  edits this file.
- `backend/tests/conftest.py` — DB fixture the E2E rotation test reuses (D-18).

### Prior context
- `.planning/phases/04-doc-code-parity/04-CONTEXT.md` — Phase 4 Secrets Manager / boto3
  removal decision that anchors "key lives in `.env`, no cloud KMS."

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `encryption.generate_key()` — wrap directly for the `generate-key` subcommand.
- `encrypt_value` / `decrypt_value` — the rotate/verify logic composes these; rotation needs
  a way to decrypt with an explicit key (old) and encrypt with an explicit key (new), so a
  small refactor to parameterize the Fernet instance (or a private `_fernet_for(key)` helper)
  is likely — current `_get_fernet()` reads only `settings.encryption_key`.
- `async_session_factory()` (`app.db.session`) — CLI DB access, per `create_admin.py`.
- `structlog.get_logger()` already imported in `main.py`.

### Established Patterns
- CLI scripts are plain modules with `if __name__ == "__main__": asyncio.run(...)`, invoked
  via `docker compose exec -T backend python3 …` (install.sh). No CLI framework in use.
- Credentials are per-connector JSON maps of Fernet ciphertexts, all under one global key,
  spanning all tenants — rotation iterates every `ConnectorConfig` with a non-null
  `credentials_secret_arn` across all tenants.
- Integration tests boot against real dependencies (Phase 1 pattern) — the DB fixture exists.

### Integration Points
- Rotation writes to `ConnectorConfig.credentials_secret_arn` for every tenant's rows in one
  transaction.
- Startup check hooks into `main.py` `lifespan` before the app serves traffic.
- Audit event integrates with `app/audit.py`.
- Runbook lands in `docs/16-security.md` (Phase 4 territory).

</code_context>

<specifics>
## Specific Ideas

- CLI entrypoint contract is fixed by SC#2: `python -m app.encryption rotate --new-key <key>`.
- Startup check must be "loud" (SC#3) — structlog warning in dev, hard boot failure in prod.
- The revert-fails assertion in the E2E test is the proof that rotation is real, not a no-op
  (SC#4).

</specifics>

<deferred>
## Deferred Ideas

- **MultiFernet grace-period / zero-downtime rotation** — considered and rejected for this
  phase (D-01). If continuous-sync workloads ever make the re-encrypt window unacceptable,
  revisit as a future enhancement (`ENCRYPTION_KEYS` list + lazy re-encrypt).
- **Fallback-read (secondary OLD key) during rotation** — considered, rejected; the single-VM
  15-min-sync topology doesn't need it.
- **Cloud KMS / envelope encryption / per-tenant keys** — explicitly out (Phase 4 removed
  cloud secret management; single global key is the model).
- **JWT secret rotation tooling** — only the JWT placeholder *startup warning* is in scope
  (D-12); actual JWT rotation would be its own phase.
- **Tool auto-rewriting `.env`** — considered for key flow, rejected (D-02) to keep the tool
  out of secrets-file editing.

*No pending todos matched this phase.*

</deferred>

---

*Phase: 05-encryption-key-lifecycle*
*Context gathered: 2026-07-03*
