---
phase: 05
slug: encryption-key-lifecycle
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-06
audited_by: gsd-security-auditor
verdict: SECURED
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Result: SECURED — 8/8 threats closed, `threats_open: 0`.**

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator shell → CLI | Operator passes `--new-key` on the command line; may be malformed or leaked via shell history / `ps aux` | Fernet key material |
| CLI → Postgres | Rotation reads/writes every tenant's `connector_configs.credentials_secret_arn` in one transaction | Encrypted connector credentials (all tenants) |
| CLI → structlog / stdout / audit_logs | Rotation emits an audit row + prints operator instructions | Audit metadata — must never carry key material |
| operator `.env` → backend process | `ENCRYPTION_KEY` / `JWT_SECRET_KEY` cross into the process at startup; placeholder/unset is a silent footgun | Secret configuration |
| backup key → storage location | Where the backed-up key rests determines blast radius if the VM is compromised | Fernet key material at rest |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-05-01 | Information Disclosure | audit `details` / structlog / return values in `rotate_credentials`/`verify_credentials` | mitigate | Audit `details` limited to `{row_count, tenant_count, dry_run}`; restart instruction prints `<new key>` placeholder, not the value. `encryption.py:264-268`, `:422`; `test_audit_event` asserts no key bytes in details (`test_encryption_rotation.py:303-306`). | closed |
| T-05-02 | Tampering | mixed-key state after a partial rotation | mitigate | Single transaction, no mid-loop commit; pre-flight decrypt-all + post-verify decrypt-all; any failure → `db.rollback()` + raise. `encryption.py:162,210-211,249-250,274,279-283`; `test_rotate_aborts_on_bad_row` (`test_encryption_rotation.py:125-170`). | closed |
| T-05-03 | Information Disclosure | `--new-key` visible in `ps aux` / shell history | accept | Operational, not code-blockable. Runbook documents env-var invocation + cleared history. `docs/16-security.md:190-195`. | closed |
| T-05-04 | Elevation of Privilege | wrong / malformed `--new-key` corrupting all rows | mitigate | Both keys validated via `_fernet_for()` before any DB write; CLI validates `--new-key` and exits pre-DB; post-verify round-trip before commit. `encryption.py:158-160,360-364,236-250`. | closed |
| T-05-05 | Spoofing / weak default | placeholder `ENCRYPTION_KEY`/`JWT_SECRET_KEY` shipped to production | mitigate | `_check_secrets_at_startup()` hard-fails boot in production for unset/placeholder/invalid keys; dev logs loud structlog warning. `main.py:38-41,54-66,76-80,91`; 6 unit tests (`test_encryption_rotation.py:407-485`). | closed |
| T-05-06 | Information Disclosure | logging the key value while reporting the startup issue | mitigate | Startup check logs only the issue string via `issue=msg`; never `settings.encryption_key`/`jwt_secret_key`. `main.py:68-73`. | closed |
| T-05-07 | Elevation of Privilege | backup key stored on the same VM as the DB | mitigate (doc) | Runbook prescribes off-box vault storage, named owner, not in repo/VM/DB backup. `docs/16-security.md:147-154`. | closed |
| T-05-08 | Information Disclosure | `--new-key` visible in `ps aux` / shell history during rotation | accept | Same operational risk as T-05-03; runbook documents safer env-var invocation. `docs/16-security.md:190-195`. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-05-01 | T-05-03 | `--new-key` value visible in `ps aux` / shell history on a shared VM. Cannot be prevented in code without removing the CLI flag; safer env-var invocation documented in `docs/16-security.md:190-195`. | Phase 05 threat model (05-01-PLAN) | 2026-07-06 |
| R-05-02 | T-05-08 | Duplicate of R-05-01 for the rotation invocation path — same operational risk, same mitigation. | Phase 05 threat model (05-02-PLAN) | 2026-07-06 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-06 | 8 | 8 | 0 | gsd-security-auditor |

**Unregistered flags:** None. `05-01-SUMMARY.md` reports no new attack surface; `05-02-SUMMARY.md:122-124` explicitly states "None."

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-06
