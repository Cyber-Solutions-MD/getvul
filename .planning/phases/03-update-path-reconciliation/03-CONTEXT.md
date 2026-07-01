# Phase 3: Update Path Reconciliation - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Production gets new code exactly one way, and operators have a tested rollback procedure. This phase picks **one** canonical update mechanism from the several that exist today, removes the others, fixes CD so it deploys a released tag (not `main` HEAD), and documents + dry-runs a rollback.

**In scope:** the update/deploy path race (PROD-03-01/02), tag-pinned CD checkout (PROD-03-03), rollback runbook + dry-run (PROD-03-04).

**Out of scope:** DB down-migration automation, backup policy (PROD-05), building/pushing image artifacts to a registry, a staging environment. New deployment capabilities belong in other phases.

</domain>

<decisions>
## Implementation Decisions

### Canonical update mechanism (PROD-03-01)
- **D-01:** **Release-triggered GitHub-Actions CD** ([.github/workflows/cd.yml](../../../.github/workflows/cd.yml)) is the single canonical path to production. Chosen because Phase 2 now gates PRs/main with 4 required checks — releases are trustworthy, whereas the cron deploys ungated `main` HEAD continuously, defeating the CI gate.
- Deploys are deliberate (an operator cuts a release); there is no zero-touch auto-patching, by design.

### Removal of the cron mechanism (PROD-03-02)
- **D-02:** **Hard-remove** the auto-update cron everywhere — no opt-in flag, no dormant code. A race becomes structurally impossible.
  - Remove the cron-install block from [install.sh:94-112](../../../install.sh#L94-L112) (Step 8).
  - Remove the cron-install block from [infra/gcp/startup.sh:73-79](../../../infra/gcp/startup.sh#L73-L79).
  - `git rm` [scripts/auto-update.sh](../../../scripts/auto-update.sh).
- **D-03:** Clean up every reference to the deleted `getvul-update` command so nothing points at it: install.sh's final "Update:" summary line ([install.sh:122](../../../install.sh#L122)), any README mention, and the deployment doc's Release-process / Production-checklist / Terraform-provisioning notes.

### Tag pinning (PROD-03-03)
- **D-04:** CD deploys the released tag, not `main` HEAD. On the VM: `git fetch --tags --force && git checkout --force "${{ github.event.release.tag_name }}"` (detached HEAD), then `docker compose build --no-cache && docker compose up -d`. Replaces the current `git fetch origin main && git reset --hard origin/main`.
- Keeps the existing build-on-VM pattern (no registry/artifact rework — that would be its own phase).

### Rollback (PROD-03-04)
- **D-05:** Rollback targets the **previous release tag** (a known-good, CI-gated commit) — matches SC#3's "revert to the prior release."
- **D-06:** Rollback is delivered by **`workflow_dispatch` on cd.yml** with a `ref`/tag input. One code path for deploy AND rollback; auditable in the Actions log; no separate script to drift. The runbook documents triggering CD with `ref=<prior-tag>`.
  - This means cd.yml's `workflow_dispatch` inputs change from the current `force` boolean to a tag/ref input that both normal manual deploys and rollbacks use.
- **D-07:** Rollback runbook lives in [docs/13-deployment.md](../../../docs/13-deployment.md) §Rollback (replacing the current "no scripted rollback" placeholder at line 788), with exact commands.

### DB migrations on rollback
- **D-08:** This phase does **not** automate DB down-migrations. The rollback runbook carries a prominent callout: code rollback reverts code only; a destructive migration requires a restore from `pg_dump`. Defer real migration/backup safety to PROD-05 (Encryption Key Lifecycle) / the future backup policy.

### Claude's Discretion
- Exact wording of the rollback runbook and migration caveat callout.
- Whether the `workflow_dispatch` input is named `ref`, `tag`, or `release_tag`, and its validation.
- How CD distinguishes a `release`-triggered run (tag = `github.event.release.tag_name`) from a `workflow_dispatch` run (tag = input) when resolving which ref to check out.
- Release tag naming scheme going forward (only `v2.0` exists today) — recommend semver `vX.Y.Z` but not a locked requirement.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & phase definition
- `.planning/REQUIREMENTS.md` §Update Path Reconciliation (PROD-03) — PROD-03-01..04 acceptance criteria
- `.planning/ROADMAP.md` §Phase 3 — goal + 4 success criteria (SC#4 dry-run is a human UAT item)

### The competing update surfaces (to reconcile)
- `install.sh` §Step 8 (lines 94-112) — inline `getvul-update` script + **hourly** `/etc/cron.d/getvul-update`; also the "Update:" summary line (122) to clean up
- `infra/gcp/startup.sh` (lines 73-79) — copies `scripts/auto-update.sh`, installs a **daily** 03:00 UTC crontab entry
- `scripts/auto-update.sh` — GH-API polling updater that `reset --hard origin/main` (to be deleted); note it hardcodes repo `Cyber-Solutions-MD/getvul`
- `.github/workflows/cd.yml` — release/`workflow_dispatch` CD; currently `git reset --hard origin/main` (the survivor, to be hardened)

### Deployment & pipeline docs (to update)
- `docs/13-deployment.md` §Release process (line 779), §Rollback (line 788), §Production Checklist (line 740, cron line 752), §Provisioning-Terraform (line 757, divergence note 777) — all reference the cron/rollback and must be reconciled to the single CD path
- `docs/12-pipelines-cicd.md` §CD — `cd.yml` (line 137), the mermaid `reset --hard origin/main` node (line 27), and the explicit PROD-03-01/03/04 notes (lines 188-191)

### Prior-phase context (locks that shaped this phase)
- `.planning/phases/02-ci-gating/02-CONTEXT.md` — Phase 2 scoped "cd.yml / update-path = Phase 3"; CI now gates 4 required checks on main (the basis for choosing release CD)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **cd.yml deploy job**: already SSHes to the GCE VM, health-checks `/health`, prunes images, and verifies — keep the whole shape; only swap the checkout step (main HEAD → tag) and the trigger inputs (force bool → ref/tag).
- **cd.yml `workflow_dispatch`**: already present — repurpose its input from `force` to a tag/ref so manual deploy and rollback share the path.
- **Health-check loop** (`curl -sf .../health`, 30 tries): reuse verbatim for post-rollback verification.

### Established Patterns
- **Build-on-VM**: production builds images on the VM via `docker compose build`. Tag-checkout + rebuild stays consistent with this; no registry exists.
- **Deploy user**: CD SSHes as `deploy@$GCE_VM_IP`; VM app dir is `/opt/getvul`.
- **Single deployed target**: GCP is the only active production target; AWS/Azure terraform modules validate in CI but aren't deployed — so cron removal in `infra/gcp/startup.sh` is the only infra path that matters for the live VM.

### Integration Points
- `install.sh` and `infra/gcp/startup.sh` are the two provisioning entry points that install the cron today — both must drop it.
- `docs/13-deployment.md` + `docs/12-pipelines-cicd.md` are the doc surfaces that describe the (soon-removed) cron and the (soon-fixed) rollback.

</code_context>

<specifics>
## Specific Ideas

- Unify deploy and rollback into one auditable path: a rollback is just "run CD again pointing at an older release tag." No bespoke rollback script to maintain or test separately.
- Every rollback must land on a real, CI-gated release tag — never an arbitrary hand-picked SHA.
- The rollback doc must loudly state the migration caveat so an operator doesn't assume a code rollback undoes a schema change.

</specifics>

<deferred>
## Deferred Ideas

- **Pre-deploy `pg_dump` snapshot in CD** — a same-host restore point before build/up. Overlaps backup policy → PROD-05 / Backups.
- **Reversible Alembic down-migrations** — full DB rollback support; large, its own hardening effort.
- **Build + push versioned image artifacts to a registry** — reproducible deploys without git-on-VM; significant rework, separate phase.
- **Ephemeral-GCE-in-CI rollback test** — truest automated dry-run, but real GCP spend + CI creds; SC#4 handled as a human UAT item instead for this phase.
- **Staging environment** — CD goes straight to production today; a staging tier is out of scope here.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 03-update-path-reconciliation*
*Context gathered: 2026-07-01*
