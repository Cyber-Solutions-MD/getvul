# Phase 3: Update Path Reconciliation — Research

**Researched:** 2026-07-01
**Domain:** GitHub Actions workflow triggers, git tag operations, cron removal, rollback runbooks
**Confidence:** HIGH (core mechanics verified against official GitHub docs and Context7; one item MEDIUM with annotation)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Release-triggered GitHub-Actions CD (`cd.yml`) is the single canonical update path. Cron is removed, not made conditional.
- **D-02:** Hard-remove the auto-update cron from `install.sh` (Step 8, lines 94–112), `infra/gcp/startup.sh` (lines 73–79), and `git rm scripts/auto-update.sh`. No opt-in flag, no dormant code.
- **D-03:** Remove all references to the deleted `getvul-update` command: `install.sh` line 122 ("Update:" summary line), any README mention, and deployment doc surfaces.
- **D-04:** CD deploys the released tag via `git fetch --tags --force && git checkout --force "$TAG"` (detached HEAD), not `git reset --hard origin/main`. Rebuild with `docker compose build --no-cache && docker compose up -d`.
- **D-05:** Rollback targets the previous release tag.
- **D-06:** Rollback is `workflow_dispatch` on `cd.yml` with a `ref`/tag input. The `force` boolean input is replaced with a tag/ref string input.
- **D-07:** Rollback runbook lives in `docs/13-deployment.md` §Rollback, replacing the "no scripted rollback" placeholder at line 788.
- **D-08:** This phase does NOT automate DB down-migrations. Runbook carries a callout: code rollback reverts code only; destructive migration needs `pg_dump` restore.

### Claude's Discretion

- Exact wording of the rollback runbook and migration caveat callout.
- Whether the `workflow_dispatch` input is named `ref`, `tag`, or `release_tag`, and its validation.
- How CD distinguishes a `release`-triggered run from a `workflow_dispatch` run when resolving which ref to check out.
- Release tag naming scheme going forward (only `v2.0` exists today).

### Deferred Ideas (OUT OF SCOPE)

- Pre-deploy `pg_dump` snapshot in CD.
- Reversible Alembic down-migrations.
- Build and push versioned image artifacts to a registry.
- Ephemeral-GCE-in-CI rollback test.
- Staging environment.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-03-01 | One canonical update mechanism chosen — CD over cron | D-01 locked; cron removal mechanics verified (§Cron Removal) |
| PROD-03-02 | `install.sh` no longer registers a competing cron | Idempotent removal pattern verified (§Cron Removal) |
| PROD-03-03 | CD uses `git fetch && git checkout <tag>`, not `git reset --hard origin/main` | Tag checkout mechanics verified (§Tag Checkout on VM) |
| PROD-03-04 | Rollback procedure documented in deployment doc | Runbook pattern verified; `gh release list` command confirmed (§Rollback Pattern) |
</phase_requirements>

---

## Summary

Phase 3 removes two competing update paths (hourly/daily cron + CD both deploying ungated `main` HEAD) and replaces them with a single auditable path: a GitHub Actions CD job triggered on `release:published`, deploying a specific git tag to the production VM. The same CD job, invoked via `workflow_dispatch` with an explicit tag input, serves as the rollback mechanism.

The primary research targets were the exact GitHub Actions expression mechanics for resolving the deployed tag across two trigger types, the git operations on the VM for a safe tag checkout, idempotent cron removal patterns, and the scope of documentation surfaces to update.

**Primary recommendation:** Use `${{ github.event.release.tag_name || inputs.release_tag }}` as the ref-resolution expression. The `inputs` context is empty string (not the input's default) when triggered by a non-`workflow_dispatch` event, so `||` short-circuits correctly to the release event's tag name. Name the input `release_tag` (descriptive, unambiguous, avoids conflict with the built-in `ref` concept).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Trigger deploy | GitHub Actions (CI/CD) | — | Operator cuts a GitHub release; the event fires the CD job |
| Tag resolution (which code to deploy) | GitHub Actions runner | — | Expression evaluated in the runner before any SSH; VM has no say |
| Checkout / fetch on VM | VM (git) | — | SSH heredoc runs on the GCE VM; the runner only sends commands |
| Cron removal | VM provisioning scripts (`install.sh`, `startup.sh`) | — | Cron lives on the VM OS layer, not in containers or the runner |
| Rollback discovery (find prior tag) | Operator CLI (`gh release list`) | GitHub UI | Human reads the list, then triggers CD via `workflow_dispatch` |
| DB migration caveat | Documentation | Operator | Code-only concern; no automation here per D-08 |

---

## Standard Stack

This phase does not introduce new libraries. It modifies existing files.

### Files Being Modified

| File | Change Type | Locked by |
|------|-------------|-----------|
| `.github/workflows/cd.yml` | Swap `force` input → `release_tag` input; add ref-resolution env var; swap `reset --hard` → `fetch --tags && checkout` | D-04, D-06 |
| `install.sh` | Remove Step 8 block (lines 94–112) + "Update:" summary line (122) | D-02, D-03 |
| `infra/gcp/startup.sh` | Remove cron block (lines 73–79) | D-02 |
| `scripts/auto-update.sh` | `git rm` entirely | D-02 |
| `docs/13-deployment.md` | Rewrite §Rollback, §Release process, §Production Checklist cron item, §Provisioning-Terraform divergence note | D-03, D-07 |
| `docs/12-pipelines-cicd.md` | Update mermaid diagram (remove CRON node, fix PULL step label), update §Known issues notes | D-03 |
| `docs/02-architecture.md` | Remove CRON node from mermaid diagram (line 197–202) | D-03 |
| `docs/07-project-structure.md` | Remove `auto-update.sh` entry (lines 198–199); update `install.sh` description (line 22) | D-03 |
| `docs/17-troubleshooting.md` | Remove or update §B1 "Hourly cron and CD both deploy" (lines 104–113) | D-03 |
| `infra/gcp/main.tf` | Update comment on line 2 ("auto-update" → "CD-based deploys") | D-03 |

---

## Architecture Patterns

### System Architecture: Before vs After

**Before:**
```
GitHub release → CD job → SSH → git reset --hard origin/main → docker compose up
Hourly cron → getvul-update → git pull → docker compose up  ← race condition
```

**After:**
```
GitHub release published  ─┐
                           ├─→ CD job → SSH → git fetch --tags --force
Manual workflow_dispatch  ─┘              → git checkout --force "$TAG"
                                          → docker compose build --no-cache
                                          → docker compose up -d
                                          → health-check loop (30 × 5s)
                                          → external verify
```

### Pattern 1: Ref Resolution Across Two Triggers

**What:** A single `cd.yml` must know WHICH tag to deploy whether triggered by `release:published` or `workflow_dispatch`.

**The key mechanics (VERIFIED):**

1. When triggered by `release:published`: `github.event.release.tag_name` = the tag of the release (e.g. `v1.0.0`). `inputs` context is an **empty string** (not the input default value) because the `inputs` context is only available for `workflow_dispatch` and reusable workflow triggers.

2. When triggered by `workflow_dispatch`: `github.event.release.tag_name` = empty string / absent. `inputs.release_tag` = the value the operator typed.

3. `github.ref_name` is SET for release events (equals the tag name without `refs/tags/` prefix) and for `workflow_dispatch` (equals the branch/tag the operator selected to run from). However, `github.ref_name` on `workflow_dispatch` reflects the *branch selected to run the workflow from* (typically `main`), NOT the `release_tag` input value — so `github.ref_name` is NOT a reliable fallback for this use case.

**Recommended expression:**
```yaml
env:
  DEPLOY_TAG: ${{ github.event.release.tag_name || inputs.release_tag }}
```

The `||` operator in GitHub Actions expressions short-circuits on the first truthy value. When triggered by `release`, `github.event.release.tag_name` is the tag string (truthy). When triggered by `workflow_dispatch`, it is empty string (falsy), so `inputs.release_tag` is used.

**Important gotcha:** `inputs` context returns empty string (not the default value) when the workflow is triggered by a non-`workflow_dispatch` event. This means: (a) the `||` expression is safe — the release event gets `github.event.release.tag_name`; (b) you must mark `release_tag` as `required: false` (not required) so the release trigger does not fail validation; (c) add a guard step that fails the job if `DEPLOY_TAG` is empty after resolution.

**cd.yml `workflow_dispatch` input change:**
```yaml
# OLD
workflow_dispatch:
  inputs:
    force:
      description: "Force deploy (skip CI check)"
      type: boolean
      default: false

# NEW
workflow_dispatch:
  inputs:
    release_tag:
      description: "Release tag to deploy (e.g. v1.0.0) — for normal deploys and rollbacks"
      type: string
      required: false
```

**Guard step (fail fast if tag is empty):**
```yaml
- name: Resolve deploy tag
  run: |
    DEPLOY_TAG="${{ github.event.release.tag_name || inputs.release_tag }}"
    if [ -z "$DEPLOY_TAG" ]; then
      echo "ERROR: No deploy tag resolved. Provide release_tag input for manual dispatch."
      exit 1
    fi
    echo "DEPLOY_TAG=$DEPLOY_TAG" >> "$GITHUB_ENV"
```

Then all subsequent steps reference `${{ env.DEPLOY_TAG }}`.

### Pattern 2: Tag Checkout on VM (Detached HEAD)

**What:** The deploy SSH block currently runs `git fetch origin main && git reset --hard origin/main`. This must change to a tag checkout.

**Verified command sequence:**
```bash
git fetch --tags --force
git checkout --force "$DEPLOY_TAG"
```

**Why each flag:**

- `git fetch --tags`: fetches all remote tag refs (not just the default branch refs). Without `--tags`, `git fetch origin main` does NOT automatically update local tag refs.
- `--force` on fetch: since git 2.20, updating an existing local tag ref requires `--force` (same semantics as push). If a tag was moved on the remote (e.g. re-tagging a release), `--force` ensures the local copy updates. Without it, stale local tags silently persist and the checkout lands on the wrong commit. This is idempotent and safe to run repeatedly. [VERIFIED: git-scm.com/docs/git-fetch]
- `git checkout --force "$DEPLOY_TAG"`: checks out the tag as a detached HEAD. The `--force` discards any dirty working-tree changes (e.g. from a previous partial deploy). Detached HEAD state is expected and correct for a deployed-tag VM — there is no branch to track. [VERIFIED: git-scm.com/docs/git-checkout]
- **Non-interactive SSH pitfall:** Detached HEAD produces no interactive warning in non-interactive SSH sessions. The shell does not prompt; `set -e` exits on the first non-zero command. This sequence is safe in the heredoc pattern already used by cd.yml.

**Full replace block (inside SSH heredoc):**
```bash
# Pull released tag
git fetch --tags --force
git checkout --force "$DEPLOY_TAG"

# Rebuild and restart
docker compose build --no-cache
docker compose up -d
```

**Idempotency:** Running the same sequence twice with the same tag is safe. The second run fetches (no-op if already current), checks out the same commit (no-op), and rebuilds (docker layer cache may accelerate this but the build is still correct).

**Prior tracking state:** The VM was previously tracking `origin/main` (from `git reset --hard origin/main`). After `git checkout --force "$DEPLOY_TAG"`, the working tree is in detached HEAD at the tag's commit. The `origin/main` remote tracking ref remains in the repo's ref store but is no longer HEAD. There are no behavioural consequences — subsequent CD runs do `git fetch --tags --force` which is independent of HEAD state.

### Pattern 3: Rollback = workflow_dispatch at Prior Tag

**What:** Rollback is re-running CD with `release_tag=<prior release tag>`. No separate rollback script.

**How operator finds the prior tag:**
```bash
# List releases in descending order (newest first); second entry is the prior release
gh release list --limit 5 --json tagName,publishedAt,isLatest \
  --jq '.[] | "\(.tagName)  \(.publishedAt)"'
```

Or via GitHub UI: Releases page, previous release.

**Triggering rollback from CLI:**
```bash
gh workflow run cd.yml --field release_tag=v1.0.0
```

Or via GitHub UI: Actions → CD workflow → Run workflow → enter `release_tag`.

**Why this is sound:** The prior release tag points to a commit that passed CI (4 required checks). The same CD job runs, checks out that tag on the VM, rebuilds, and health-checks. The Actions log records which tag was deployed and who triggered it. [ASSUMED — the "every release is CI-gated" invariant depends on Phase 2 branch protection holding; if a release was cut from a branch without PR protection, the prior tag may not be CI-gated. For this project, Phase 2 is complete and `main` is branch-protected, so releases cut from `main` are gated.]

**Runbook framing (recommended language for docs/13-deployment.md §Rollback):**

```markdown
## Rollback

Rollback is re-deploying a prior release tag via the CD workflow.

### Step 1: Identify the prior release tag

```bash
gh release list --limit 5
```

Or open the GitHub Releases page and note the previous version.

### Step 2: Verify the prior release does not have a destructive migration

> WARNING — DATABASE MIGRATIONS ARE NOT REVERTED BY A CODE ROLLBACK.
>
> If the bad release added an Alembic migration that dropped a column or table,
> checking out the prior code will NOT restore the data. You must restore from a
> `pg_dump` backup taken before the failed deploy. If no backup exists, data may
> be unrecoverable. Contact your DBA before proceeding.
>
> If the migration was purely additive (added a column, created a table), code
> rollback is safe — the prior code will ignore the new schema objects.

### Step 3: Trigger the CD workflow at the prior tag

```bash
gh workflow run cd.yml --field release_tag=v1.0.0
```

Or: GitHub UI → Actions → "CD — Deploy to GCE" → Run workflow → enter the prior tag.

### Step 4: Verify

The workflow's "Verify deployment" step checks `GET /health` externally. Watch the Actions run log. On success, the app is running the prior release.
```

### Pattern 4: Cron Removal (Idempotent)

**install.sh — Step 8 (lines 94–112):**

Replace the entire Step 8 block with a comment noting cron was removed:

```bash
# ── Step 8: Auto-update cron removed (PROD-03) ──
# Deployments are now managed exclusively via GitHub Actions CD.
# See: .github/workflows/cd.yml
```

Also remove line 122: `echo "  Update:  sudo /usr/local/bin/getvul-update"` from the Done banner.

**Idempotency consideration:** The existing install.sh Step 8 already has an `if [ ! -f /usr/local/bin/getvul-update ]` guard. Removing the block is safe on re-runs because if `getvul-update` was installed by a prior run, it will persist on the VM. The phase must also remove any already-installed artifacts from the live VM. The rollback runbook should note: "If migrating a VM that was previously provisioned with `install.sh`, manually clean up the residual cron and binary: `sudo rm -f /etc/cron.d/getvul-update /usr/local/bin/getvul-update`."

**infra/gcp/startup.sh — lines 73–79:**

Remove the cron block:
```bash
# ── Install auto-update cron ──        ← DELETE these 7 lines
echo "Setting up daily auto-update..."
cp scripts/auto-update.sh /usr/local/bin/getvul-update
chmod +x /usr/local/bin/getvul-update
(crontab -l 2>/dev/null | grep -v getvul-update; echo "0 3 * * * /usr/local/bin/getvul-update >> /var/log/${app_name}-update.log 2>&1") | crontab -
```

The crontab removal is already idempotent via the `grep -v getvul-update` pattern — running the modified script on a VM that previously installed the cron simply produces a crontab with that line absent.

**scripts/auto-update.sh:**

`git rm scripts/auto-update.sh` — removes from working tree and stages the deletion.

### Anti-Patterns to Avoid

- **DO NOT** use `github.ref_name` as the deploy tag: for `workflow_dispatch` it resolves to the *branch the workflow was triggered from* (e.g. `main`), not the `release_tag` input value. [VERIFIED: GitHub community discussion #64528]
- **DO NOT** rely on `inputs.release_tag` having its default value when triggered by a release event: `inputs` context is empty string (not the default) for non-dispatch triggers. [VERIFIED: GitHub community discussion #29242]
- **DO NOT** use `github.event.inputs.release_tag` as a replacement for `inputs.release_tag` — both resolve to the same value for dispatch, but the `inputs` context is preferred (it preserves boolean types; string inputs are equivalent). [CITED: docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions]
- **DO NOT** `git fetch origin main` before `git checkout "$TAG"`: fetching `origin main` does not update tag refs. You need `git fetch --tags --force`.
- **DO NOT** leave the `force` boolean input in `workflow_dispatch` alongside the new `release_tag` input — it was a "skip CI check" gate that no longer makes sense after the cron is gone.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tag-pinned deploy | Custom script that fetches a tag | `git fetch --tags --force && git checkout --force "$TAG"` | Two standard git commands; hand-rolling adds a failure surface |
| Rollback invocation | Separate rollback.sh script | `gh workflow run cd.yml --field release_tag=<tag>` | One code path for deploy and rollback; auditable; no script drift |
| Finding prior release | Custom git log parsing | `gh release list` | gh CLI lists only actual GitHub releases (not every tag), which is what you want |

---

## Common Pitfalls

### Pitfall 1: `inputs` Context Empty on Release Trigger

**What goes wrong:** Developer writes `${{ inputs.release_tag }}` without a fallback. When the workflow fires from a `release:published` event, `inputs.release_tag` is empty string. The `git checkout` command receives an empty string argument and fails, or worse, silently checks out an unexpected ref.

**Why it happens:** The `inputs` context is only populated for `workflow_dispatch` and reusable workflow calls. Release events do not set inputs. [VERIFIED: docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/accessing-contextual-information-about-workflow-runs]

**How to avoid:** Use `${{ github.event.release.tag_name || inputs.release_tag }}` and add an explicit guard step that exits 1 if the resolved value is empty.

**Warning signs:** Any expression that only reads `inputs.*` without a `||` fallback in a multi-trigger workflow.

### Pitfall 2: `git fetch` Without `--tags` Does Not Fetch Tag Refs

**What goes wrong:** Operator runs `git fetch origin main` (the current cd.yml pattern), then tries to `git checkout v1.0.0`. Git reports "pathspec 'v1.0.0' did not match any file(s) known to git" because the tag ref was never fetched.

**Why it happens:** `git fetch origin main` only updates `refs/remotes/origin/main` and the commits it references. Tag refs (`refs/tags/*`) are not fetched unless `--tags` is passed or the refspec explicitly includes them. [VERIFIED: git-scm.com/docs/git-fetch]

**How to avoid:** Always use `git fetch --tags --force` before a tag checkout in automation.

**Warning signs:** "pathspec 'vX.Y.Z' did not match any file(s)" error in the SSH deploy step.

### Pitfall 3: Stale Local Tag Points to Wrong Commit

**What goes wrong:** A tag was re-created on the remote (e.g. `v1.0.0` was deleted and recreated at a hotfix commit). `git fetch --tags` without `--force` silently refuses to update the local tag. `git checkout v1.0.0` lands on the old commit.

**Why it happens:** Since git 2.20, tag ref updates are rejected without `+` in the refspec or `--force`, matching push semantics. [VERIFIED: git-scm.com/docs/git-fetch]

**How to avoid:** Always use `git fetch --tags --force`.

### Pitfall 4: Residual Cron on Pre-Existing VM

**What goes wrong:** `install.sh` and `startup.sh` are updated to remove the cron block, but the cron is already installed on the live GCE VM from a prior provisioning run. The cron continues to deploy `main` HEAD hourly even after this phase ships.

**Why it happens:** Changing provisioning scripts doesn't retroactively modify the running VM's cron table.

**How to avoid:** The rollback runbook and deployment doc must include a one-time cleanup command for operators migrating existing VMs:
```bash
sudo rm -f /etc/cron.d/getvul-update /usr/local/bin/getvul-update
```

This is safe to run even if the files don't exist (`-f` suppresses the "no such file" error).

### Pitfall 5: DB Migration Caveat Not Prominent Enough

**What goes wrong:** Operator sees the rollback runbook, triggers CD at the prior tag, and assumes the database is also rolled back. A destructive migration (column drop) has already run; the prior code now crashes or silently corrupts data when it cannot find the column.

**Why it happens:** Code rollback via git tag is purely file-system/code level. Alembic migrations write to the `alembic_version` table and apply schema changes, but `git checkout <prior-tag>` does not run `alembic downgrade`. [ASSUMED — standard Alembic behavior; per D-08 this phase does not automate down-migrations]

**How to avoid:** The callout box in the rollback runbook must appear BEFORE "Step 3: Trigger the CD workflow" so operators read it before deploying. Use a blockquote with a WARNING prefix (see runbook framing above).

---

## Code Examples

### Final cd.yml Deploy Step (replace existing)

```yaml
# Source: pattern derived from github.com/actions/runner docs + git-scm.com
name: CD — Deploy to GCE

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      release_tag:
        description: "Release tag to deploy (e.g. v1.0.0) — use for manual deploys and rollbacks"
        type: string
        required: false

env:
  VM_HOST: ${{ secrets.GCE_VM_IP }}
  VM_USER: deploy

jobs:
  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Resolve deploy tag
        run: |
          DEPLOY_TAG="${{ github.event.release.tag_name || inputs.release_tag }}"
          if [ -z "$DEPLOY_TAG" ]; then
            echo "ERROR: No deploy tag resolved."
            echo "  - For release triggers: tag comes from github.event.release.tag_name"
            echo "  - For manual dispatch: provide release_tag input"
            exit 1
          fi
          echo "Deploying tag: $DEPLOY_TAG"
          echo "DEPLOY_TAG=$DEPLOY_TAG" >> "$GITHUB_ENV"

      - name: Configure SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.GCE_SSH_PRIVATE_KEY }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          ssh-keyscan -H ${{ env.VM_HOST }} >> ~/.ssh/known_hosts 2>/dev/null || true

      - name: Deploy to VM
        run: |
          ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no ${{ env.VM_USER }}@${{ env.VM_HOST }} << DEPLOY
            set -e
            cd /opt/getvul

            echo "=== Deploying GetVul ${{ env.DEPLOY_TAG }} \$(date) ==="

            # Fetch all tags (--force handles re-tagged releases)
            git fetch --tags --force

            # Checkout the specific release tag (detached HEAD — expected)
            git checkout --force "${{ env.DEPLOY_TAG }}"

            # Rebuild and restart
            docker compose build --no-cache
            docker compose up -d

            # Wait for health
            for i in \$(seq 1 30); do
              if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
                echo "Health check passed!"
                break
              fi
              echo "  waiting... (\$i/30)"
              sleep 5
            done

            # Verify
            curl -sf http://localhost:8000/health || exit 1

            # Cleanup
            docker image prune -f

            echo "=== Deploy complete \$(date) ==="
          DEPLOY

      - name: Verify deployment
        run: |
          sleep 5
          STATUS=$(curl -sf http://${{ env.VM_HOST }}/health | grep -o '"status":"ok"' || echo "FAILED")
          if [ "$STATUS" = '"status":"ok"' ]; then
            echo "Deployment verified — app is healthy at tag ${{ env.DEPLOY_TAG }}"
          else
            echo "Deployment verification failed"
            exit 1
          fi
```

**Note on heredoc quoting:** The outer heredoc uses `<< DEPLOY` (unquoted delimiter), which means `${{ env.DEPLOY_TAG }}` is expanded by the runner before SSH. Variable references inside that need to be evaluated on the VM use `\$` escaping (e.g. `\$(date)`, `\$(seq ...)`). This is the same pattern as the existing cd.yml; the only change is replacing `git fetch origin main && git reset --hard origin/main` with the tag operations.

### Idempotent Cron Removal in install.sh

```bash
# ── Step 8: Auto-update cron removed (PROD-03) ──
# Deployments are managed exclusively via GitHub Actions CD (.github/workflows/cd.yml).
# To remove a cron installed by a previous version of this script:
#   sudo rm -f /etc/cron.d/getvul-update /usr/local/bin/getvul-update
```

### Idempotent Cron Removal in infra/gcp/startup.sh

Remove lines 73–79 entirely. The `git pull origin main` on line 37–38 (the "already exists, pulling latest" block) may also need updating: the startup script is a one-time first-boot script, so this is lower priority, but aligning it with "clone to the latest release tag" rather than `main` is clean. That is a Claude's Discretion call.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `github.event.inputs` for dispatch inputs | `inputs` context (preserves booleans) | GitHub Actions ~2021 | Use `inputs.release_tag` not `github.event.inputs.release_tag`; both work for strings, but `inputs` is idiomatic |
| `git fetch` without `--tags` | `git fetch --tags --force` | git 2.20 (tag-update semantics tightened) | `--force` now required to update moved/re-created tags |
| Separate rollback scripts | `workflow_dispatch` re-run at prior tag | Community best practice | Eliminates drift between deploy and rollback code paths |

**Deprecated/outdated in this codebase:**
- `git reset --hard origin/main` in cd.yml: deploys `main` HEAD rather than a release tag. This is the core PROD-03-03 fix.
- `force` boolean input in `workflow_dispatch`: was a "skip CI check" gate. Replaced by `release_tag` string input.
- `scripts/auto-update.sh`: hardcodes `Cyber-Solutions-MD/getvul` repo — will break if the repo is transferred. Being deleted per D-02.

---

## Runtime State Inventory

> This is a code + provisioning change phase. Runtime state audit is required because cron entries live outside git.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no DB schema changes | None |
| Live service config | GCE VM: `/etc/cron.d/getvul-update` (hourly, installed by prior `install.sh` run) and `crontab` entry for root (daily, installed by prior `startup.sh` run) — these are on the live VM, not in git | One-time VM cleanup: `sudo rm -f /etc/cron.d/getvul-update /usr/local/bin/getvul-update`; for the startup.sh crontab entry: `crontab -l | grep -v getvul-update | crontab -` |
| OS-registered state | `/usr/local/bin/getvul-update` binary on live VM | Delete with `sudo rm -f /usr/local/bin/getvul-update` |
| Secrets/env vars | None — this phase adds no new secrets; existing `GCE_SSH_PRIVATE_KEY` and `GCE_VM_IP` secrets in GitHub remain unchanged | None |
| Build artifacts | `scripts/auto-update.sh` — staged for `git rm` | `git rm scripts/auto-update.sh` |

**Live VM cleanup is a Wave task, not just a code change.** The planner must include a task for cleaning up the existing VM's cron installation. This cannot be done purely by editing files in the repo.

---

## Open Questions (RESOLVED)

> All three questions were resolved during planning (Phase 3 plans 03-01 / 03-02).
> Q1 and Q2 are deferred as out-of-scope discretion items; Q3 is implemented.

1. **startup.sh `git pull origin main` on first boot (line 37–38)**
   - **RESOLVED:** Claude's Discretion — deferred. startup.sh is a one-time GCE first-boot metadata script; the `git pull` on VM re-use is low risk (fresh Terraform apply only) and out of Phase 3 scope. Converting it to a tag checkout is a clean follow-up, not required to meet PROD-03-01..04.
   - What we know: startup.sh clones the repo on first boot; if the repo already exists, it runs `git pull origin main`. After this phase, the canonical deploy is tag-based, not `main` HEAD.
   - What's unclear: startup.sh is a one-time GCE metadata startup script. New VMs will not have the cron. The `git pull origin main` on re-use of an existing VM is a residual concern.
   - Recommendation: Update the "already exists" branch to `git fetch --tags --force && git checkout --force <LATEST_TAG>` and document the tag as a Terraform variable. This is low priority for Phase 3 (the live VM is already running; startup.sh fires only on fresh Terraform apply), but is a clean improvement to consider.

2. **`release_tag` input validation depth**
   - What we know: GitHub Actions `type: string` inputs have no built-in pattern validation. A typo in the tag name will cause the `git checkout` step to fail with a clear error message, which is acceptable.
   - What's unclear: Should there be a pre-validation step that confirms the tag exists on the remote before SSHing to the VM? (`git ls-remote --tags origin "$DEPLOY_TAG"`)
   - Recommendation: The fail-fast guard (checking that `DEPLOY_TAG` is non-empty) is sufficient for Phase 3. A tag-existence check is a nice-to-have and can be added in a follow-up.
   - **RESOLVED:** out of scope — the non-empty `DEPLOY_TAG` fail-fast guard plus git's own unresolvable-ref rejection is sufficient for Phase 3. Optional `git ls-remote` pre-check deferred.

3. **docs/02-architecture.md mermaid diagram scope**
   - What we know: Lines 197–202 show a `CRON` node in the architecture mermaid diagram. This diagram lives in the architecture overview doc, not the pipeline doc.
   - What's unclear: CONTEXT.md §canonical_refs lists only `docs/13-deployment.md` and `docs/12-pipelines-cicd.md` explicitly. The `docs/02-architecture.md` and `docs/07-project-structure.md` cron references were found by grep and are in scope per D-03 ("clean up every reference").
   - Recommendation: Update `docs/02-architecture.md` and `docs/07-project-structure.md` as part of the D-03 doc cleanup wave.
   - **RESOLVED:** implemented — `docs/02-architecture.md`, `docs/07-project-structure.md`, and `docs/17-troubleshooting.md` are all in Plan 03-01 Task 2's `files_modified`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| GitHub CLI (`gh`) | Rollback runbook (`gh workflow run`, `gh release list`) | ✓ | 2.95.0 | GitHub web UI |
| `git` | VM tag checkout | ✓ (on GCE VM, confirmed by current cd.yml which runs git) | — | — |
| Docker Compose | VM rebuild | ✓ (current cd.yml runs `docker compose build`) | — | — |

---

## Validation Architecture

`workflow.nyquist_validation` is absent from `.planning/config.json` — treated as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (backend) + YAML linting (yamllint / actionlint for workflows) |
| Config file | `pyproject.toml` (pytest) |
| Quick run command | `yamllint .github/workflows/cd.yml` |
| Full suite command | `pytest backend/tests/ -v` (no new backend code this phase; YAML validity is the primary automated check) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-03-01 | No cron installed by `install.sh` after change | Smoke (grep-based) | `grep -c "getvul-update" install.sh` should return 0 | ✅ (install.sh exists) |
| PROD-03-02 | No cron installed by `startup.sh` after change | Smoke (grep-based) | `grep -c "getvul-update" infra/gcp/startup.sh` should return 0 | ✅ |
| PROD-03-03 | `cd.yml` uses `git checkout` not `git reset --hard origin/main` | Smoke (grep-based) | `grep -c "reset --hard origin/main" .github/workflows/cd.yml` should return 0 | ✅ |
| PROD-03-04 | Rollback doc section exists and is non-trivial | Manual review | Human UAT — SC#4 in ROADMAP.md is explicitly a human dry-run item | N/A |

### Sampling Rate

- **Per task commit:** `grep -c "reset --hard origin/main" .github/workflows/cd.yml && grep -c "getvul-update" install.sh infra/gcp/startup.sh`
- **Per wave merge:** Full grep suite above + YAML lint on `cd.yml`
- **Phase gate:** All grep checks return 0, `scripts/auto-update.sh` absent from git tree, rollback runbook section complete in `docs/13-deployment.md`

### Wave 0 Gaps

None — no new test files required. This phase modifies existing YAML and shell scripts; all verification is grep-based or manual UAT (SC#4 dry-run).

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — |
| V3 Session Management | No | — |
| V4 Access Control | Yes (deployment access) | GitHub Actions `secrets.*` for SSH key; deploy user on VM has limited scope |
| V5 Input Validation | Partial | `release_tag` input: empty-string guard validates presence; tag-existence check is optional |
| V6 Cryptography | No | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tag injection via `workflow_dispatch` input | Tampering | Input value passed to `git checkout` inside SSH heredoc; shell executes on VM as `deploy` user. Mitigation: `set -e` in heredoc; git will reject refs it cannot resolve. Optional: add `git ls-remote --tags origin "$DEPLOY_TAG"` pre-check. |
| Stale tag deploys wrong commit | Tampering | `git fetch --tags --force` ensures local tag is current before checkout |
| Cron re-deploys `main` after rollback | Elevation of Privilege | Hard-removal of cron (D-02) eliminates this class of threat |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Every release is CI-gated" — prior tags are safe to roll back to because Phase 2 branch protection holds | Rollback Pattern | If a release was cut from an unprotected branch, the prior tag may contain ungated code. Risk is LOW for this project given Phase 2 is complete. |
| A2 | `git checkout --force` on a VM that had an SSH-interrupted partial deploy will cleanly overwrite the working tree | Tag Checkout on VM | If the working tree has untracked files from a failed build, `git checkout --force` does not remove untracked files. Use `git clean -fd` after checkout for a fully clean state. Planner may add this as optional hardening. |
| A3 | Alembic `upgrade head` runs as a separate operator step on deployment (not in cd.yml) | DB migration caveat | If cd.yml were to add an automatic `alembic upgrade head`, the rollback runbook would need additional migration-state guidance. Current cd.yml does not run migrations. |

---

## Sources

### Primary (HIGH confidence)
- [docs.github.com/en/actions — contexts reference](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/accessing-contextual-information-about-workflow-runs) — `inputs` context availability, `github.event.release.tag_name`, `github.ref_name` definition
- [docs.github.com/en/actions — events that trigger workflows](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows) — release event `GITHUB_REF` = `refs/tags/<tag_name>`; workflow_dispatch input definitions
- [git-scm.com/docs/git-fetch](https://git-scm.com/docs/git-fetch) — `--tags`, `--force` semantics; git 2.20 tag-update behavior
- [git-scm.com/docs/git-checkout](https://git-scm.com/docs/git-checkout) — `--force` semantics, detached HEAD

### Secondary (MEDIUM confidence)
- [GitHub community discussion #29242](https://github.com/orgs/community/discussions/29242) — confirmed `inputs` defaults do NOT apply on non-dispatch triggers; returns empty string
- [GitHub community discussion #64528](https://github.com/orgs/community/discussions/64528) — `github.ref_name` behavior per trigger type; `workflow_dispatch` gives the branch selected, not the input tag
- [cli.github.com/manual/gh_release_list](https://cli.github.com/manual/gh_release_list) — `gh release list` JSON fields and flags

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — this phase modifies existing files, no new libraries
- Architecture (ref resolution pattern): HIGH — verified against official GitHub Actions docs and community discussions with official attribution
- Tag checkout mechanics: HIGH — verified against git-scm.com official docs
- Pitfalls: HIGH — three of five pitfalls verified against official sources; A2/A3 are standard Alembic/git behavior flagged as ASSUMED
- Rollback pattern: MEDIUM — the `gh workflow run` command is standard; the "all prior releases are CI-gated" invariant is an ASSUMED dependency on Phase 2

**Research date:** 2026-07-01
**Valid until:** 2026-08-01 (GitHub Actions expression semantics are stable; git tag mechanics are stable)
