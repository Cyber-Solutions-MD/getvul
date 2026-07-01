# Phase 3: Update Path Reconciliation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-01
**Phase:** 3-update-path-reconciliation
**Areas discussed:** Canonical mechanism, Remove vs. opt-in, Tag pinning + rollback shape, DB migrations + dry-run

---

## Canonical mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Release CD | GitHub release → cd.yml SSH deploy; deliberate, gated by Phase 2 CI, tag-pinnable | ✓ |
| Auto-update cron | VM self-updates on a schedule; zero-touch but ungated main HEAD | |

**User's choice:** Release CD (recommended)
**Notes:** Phase 2's completed CI gating (4 required checks on main) makes release-triggered CD the only path that respects gating. Cron continuously deploys ungated main HEAD.

---

## Remove vs. opt-in (cron fate)

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-remove | Delete cron from install.sh + startup.sh + delete scripts/auto-update.sh | ✓ |
| Keep opt-in behind flag | Skip cron unless GETVUL_AUTOUPDATE=1 | |

**User's choice:** Hard-remove (recommended)
**Notes:** Security product going to a real customer — remove all cron surface so a race is structurally impossible. Also cleans up dangling `getvul-update` references.

---

## Tag pinning + rollback shape (3 sub-questions)

### CD target (PROD-03-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Checkout release tag | `git fetch --tags && git checkout <release.tag_name>`, rebuild | ✓ |
| Build + push image artifact | CI builds versioned image to registry; VM pulls | |

**User's choice:** Checkout release tag (recommended)

### Rollback target

| Option | Description | Selected |
|--------|-------------|----------|
| Previous release tag | Roll back to prior vX.Y.Z tag (known-good, CI-gated) | ✓ |
| Arbitrary previous SHA | Hand-pick a SHA from git log | |

**User's choice:** Previous release tag (recommended)

### Rollback delivery

| Option | Description | Selected |
|--------|-------------|----------|
| workflow_dispatch on cd.yml | Re-run CD with an older tag input; one path for deploy + rollback | ✓ |
| Standalone script on VM | scripts/rollback.sh / getvul-rollback over SSH | |
| Documented runbook only | Copy-paste commands, no automation | |

**User's choice:** workflow_dispatch on cd.yml (recommended)
**Notes:** Unifies deploy + rollback into one auditable, gated code path. cd.yml's `workflow_dispatch` input changes from `force` bool to a tag/ref input.

---

## DB migrations + dry-run (2 sub-questions)

### Migrations on rollback

| Option | Description | Selected |
|--------|-------------|----------|
| Document caveat, defer to PROD-05 | Runbook warns code rollback ≠ migration rollback; point to backups | ✓ |
| Add pre-deploy pg_dump to CD | Snapshot DB before build/up | |
| Full down-migration support | Reversible Alembic downgrades run on rollback | |

**User's choice:** Document caveat, defer to PROD-05 (recommended)

### SC#4 dry-run verification

| Option | Description | Selected |
|--------|-------------|----------|
| Human UAT item | Operator runs rollback on a real/ephemeral GCE, pastes log into verification | ✓ |
| Local docker-compose simulation | Reproduce checkout→rebuild→health locally | |
| Ephemeral GCE in CI | Throwaway VM via terraform, deploy→rollback→destroy | |

**User's choice:** Human UAT item (recommended)
**Notes:** No VM access or staging from this dev machine; SC#4's value is proving rollback works on a real VM, which can't be faked locally.

## Claude's Discretion

- Rollback runbook / migration-caveat wording
- `workflow_dispatch` input name (ref/tag/release_tag) + validation
- How CD resolves the ref for release vs workflow_dispatch runs
- Future release tag naming scheme (recommend semver vX.Y.Z)

## Deferred Ideas

- Pre-deploy pg_dump snapshot in CD (→ PROD-05 / Backups)
- Reversible Alembic down-migrations (own phase)
- Build + push versioned image artifacts to a registry (own phase)
- Ephemeral-GCE-in-CI rollback test (GCP spend + CI creds)
- Staging environment
