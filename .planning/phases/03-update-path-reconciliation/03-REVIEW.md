---
phase: 03-update-path-reconciliation
reviewed: 2026-07-23T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - .github/workflows/cd.yml
  - docs/02-architecture.md
  - docs/07-project-structure.md
  - docs/12-pipelines-cicd.md
  - docs/13-deployment.md
  - docs/17-troubleshooting.md
  - docs/diagrams/pipelines-cicd.mmd
  - infra/aws/main.tf
  - infra/aws/startup.sh
  - infra/azure/main.tf
  - infra/azure/startup.sh
  - infra/gcp/main.tf
  - infra/gcp/startup.sh
  - install.sh
findings:
  critical: 0
  warning: 1
  info: 5
  total: 6
status: issues_found
---

# Phase 3: Code Review Report (Re-Review / Reconciliation)

**Reviewed:** 2026-07-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

This is a **re-review** of a SHIPPED phase (v1.0). The prior `03-REVIEW.md` (2026-07-02)
reported 10 findings (1 critical, 5 warning, 4 info). Every prior finding was
re-verified against the **current** code. The bulk of the substantive findings have since
been fixed:

- **CR-01 (command injection in `cd.yml`) — FIXED.** The untrusted `release_tag` /
  `github.event.release.tag_name` are now bound to env vars (`RELEASE_TAG_NAME`,
  `DISPATCH_TAG`) in the "Resolve deploy tag" step, validated against an allowlist regex
  (`^[A-Za-z0-9][A-Za-z0-9._-]*$`), and the SSH heredoc is **quoted** (`<< 'DEPLOY'`) with
  `DEPLOY_TAG` passed as a remote environment variable. No workflow expression is expanded
  into the script body host-side or VM-side. Not reported.
- **WR-01 (checkout could resolve a branch/SHA, not a tag) — FIXED.** The remote script now
  verifies `git rev-parse -q --verify "refs/tags/$DEPLOY_TAG^{commit}"` and checks out
  `refs/tags/$DEPLOY_TAG`, refusing anything that is not an existing tag. The allowlist also
  forbids `/`, blocking `refs/..`-style traversal. Not reported.
- **WR-02 (`set -e` in heredoc doesn't fail the job) — RESOLVED in practice.** The remote
  body runs via `ssh ... bash -s`, so a `set -e` abort propagates as the remote exit status,
  which `ssh` returns and the step fails on. Combined with the deterministic post-loop check
  below, the original risk no longer materializes. Not reported.
- **WR-03 (health loop swallowed the failure signal) — FIXED.** After the loop, line 94 runs
  `curl -sf http://localhost:8000/health || exit 1` (a deterministic never-came-up failure),
  and a separate "Verify deployment" step (lines 102–111) curls the external `/health` and
  fails on anything but `"status":"ok"`. Not reported.
- **WR-05 (stale troubleshooting entry D3) — FIXED.** `docs/17-troubleshooting.md` D3 now
  correctly describes the tag-pinned behavior ("resolves a `DEPLOY_TAG` ... checks out
  `refs/tags/$DEPLOY_TAG`") and notes branch names are rejected. Not reported.

What genuinely **still exists** in the current code: one Warning (SSH host-key trust is
decorative — `ssh-keyscan ... || true` paired with `StrictHostKeyChecking=no`), and four/five
Info-level doc/script hygiene items (install.sh step-counter denominators still disagree; a
`docs/13-deployment.md` "8 steps" / `NEXT_PUBLIC_API_URL=""` drift; a non-Fernet openssl
fallback key in `install.sh`; a soft diagram ambiguity about CD/CI gating). One new Info item
was surfaced (startup.sh still `git pull origin main` on re-provision, mildly at odds with the
tag-pinned deploy intent). The Terraform modules (`infra/{aws,gcp,azure}/main.tf`) are clean:
SSH ingress is gated on `var.ssh_allowed_cidrs`, AWS enforces IMDSv2, no hardcoded secrets.

## Warnings

### WR-01: SSH host-key trust is decorative — `ssh-keyscan` failure ignored and `StrictHostKeyChecking=no` on deploy

**File:** `.github/workflows/cd.yml:55`, `:62` (verified against current code)
**Issue:**
The "Configure SSH" step runs
`ssh-keyscan -H ${{ env.VM_HOST }} >> ~/.ssh/known_hosts 2>/dev/null || true` (line 55),
which suppresses all errors, and the "Deploy to VM" step then connects with
`-o StrictHostKeyChecking=no` (line 62). The combination means the runner will hand the
deploy SSH key to — and execute the deploy script (and read `DEPLOY_TAG`) on — whatever host
answers on `GCE_VM_IP`, with **no host-key verification**. `ssh-keyscan` is trust-on-first-use
to begin with; pairing it with `StrictHostKeyChecking=no` makes the `known_hosts` write purely
decorative. An attacker who can spoof/hijack that IP gets a MITM position on production deploys
(harvest the deploy key, or serve attacker-controlled responses to the VM-side commands).
**Fix:** Store the VM's known host key in a secret and write it to `known_hosts`, then use
`StrictHostKeyChecking=yes` (or `accept-new`):
```yaml
      - name: Configure SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.GCE_SSH_PRIVATE_KEY }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          echo "${{ secrets.GCE_KNOWN_HOSTS }}" >> ~/.ssh/known_hosts
      - name: Deploy to VM
        run: |
          ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=yes \
            "${{ env.VM_USER }}@${{ env.VM_HOST }}" DEPLOY_TAG="$DEPLOY_TAG" bash -s << 'DEPLOY'
          ...
```
At minimum, drop the `|| true` so a keyscan failure is visible, and do not combine keyscan
with `StrictHostKeyChecking=no`.

## Info

### IN-01: `install.sh` step-counter denominators are internally inconsistent

**File:** `install.sh:20`, `:32`, `:37`, `:45`, `:50`, `:63`, `:67`, `:71`, `:87`, `:91` (verified against current code)
**Issue:**
Step 1 prints `[1/5]` (lines 20, 32), Steps 2–5 print `[2/6]`, `[3/6]`, `[4/6]`, `[5/6]`, and
Steps 6–7 print `[6/7]`, `[7/7]`. The `/5`, `/6`, and `/7` denominators never agree, so an
operator watching the install sees a counter that appears to reset/expand. There are 7 real
steps now that the cron is gone (Docker, TLS, .env, build, health-wait, admin, seed).
**Fix:** Renumber all labels to a single denominator, e.g. `[1/7]` … `[7/7]`.

### IN-02: `docs/13-deployment.md` says "8 steps" but lists 7, and claims an unwritten `NEXT_PUBLIC_API_URL=""`

**File:** `docs/13-deployment.md:155-163` (verified against current code)
**Issue:**
Line 155 states "The install script runs 8 steps automatically" but only items 1–7 are
enumerated. Line 158 says step 3 creates `.env` "with auto-generated secrets (JWT key,
encryption key, `NEXT_PUBLIC_API_URL=""`)" — but `install.sh` (lines 51–60) only writes
`DATABASE_URL`, `REDIS_URL`, `ENVIRONMENT`, `DEBUG`, `JWT_SECRET_KEY`, and `ENCRYPTION_KEY`.
It never writes `NEXT_PUBLIC_API_URL`. Doc/code drift left over from the cron removal.
(By contrast, `docs/13-deployment.md:348`, `:503` and `docs/07-project-structure.md:22`
correctly say "7 steps"/"7-step" — only the Azure section's enumerated list is wrong.)
**Fix:** Change "8 steps" to "7 steps" and drop the `NEXT_PUBLIC_API_URL=""` claim (or add
the variable to `install.sh` if it is actually required for prod).

### IN-03: `install.sh` `ENCRYPTION_KEY` fallback produces a non-Fernet key

**File:** `install.sh:59` (verified against current code)
**Issue:**
`ENCRYPTION_KEY=$(python3 -c "...Fernet.generate_key()..." 2>/dev/null || openssl rand -base64 32)`.
The fallback `openssl rand -base64 32` uses the **standard** base64 alphabet (may contain `+`
and `/`), whereas Fernet requires a 32-byte **url-safe** base64 key. If `python3`/cryptography
is unavailable at install time, the app writes an unusable key and fails later at runtime with
`ValueError: Fernet key must be 32 url-safe base64-encoded bytes` / `InvalidToken` rather than
failing loudly at install. (Not introduced by this phase, but in scope as a reviewed file.)
**Fix:** Translate to the url-safe alphabet, e.g. `openssl rand -base64 32 | tr '+/' '-_'`, or
hard-fail the install if a valid Fernet key cannot be produced instead of writing a broken one.

### IN-04: `docs/diagrams/pipelines-cicd.mmd` can imply CI gates CD (it does not)

**File:** `docs/diagrams/pipelines-cicd.mmd:17-30` (verified against current code)
**Issue:**
CD is triggered independently by `release: published` and manual dispatch with **no dependency
on CI passing**. The CD subgraph and the adjacent "backend/frontend now hard-fail" note sit
close together; a reader may infer CI-green is a precondition for CD. The diagram doesn't state
this outright, but an explicit annotation would prevent a false sense of gating.
**Fix:** Add a one-line note in the CD subgraph, e.g. "CD has no CI precondition — gating is via
branch protection (PROD-02)."

### IN-05: `startup.sh` still `git pull origin main` on re-provision, mildly at odds with tag-pinned deploys

**File:** `infra/gcp/startup.sh:61`, `infra/aws/startup.sh:61`, `infra/azure/startup.sh:39` (verified against current code)
**Issue:**
This phase removed the auto-update cron so a provisioned VM no longer fights CD by redeploying
`main` HEAD on a timer. The `else` branch of the clone check in all three startup scripts still
does `cd "$APP_DIR" && git pull origin main`. On a fresh VM this branch is dead (the directory
does not exist yet, so the script clones), but if the startup script is ever re-run on an
existing VM it pulls `main` rather than the deployed release tag — a latent re-introduction of
the exact "runs main HEAD, not the released tag" behavior PROD-03 set out to eliminate.
**Fix:** In the "already exists" branch, avoid moving the checkout: either leave the working
tree untouched (let CD manage the ref) or `git fetch --tags --force` without checking out
`main`. At minimum, add a comment clarifying that CD — not this script — owns the deployed ref
after first boot.

---

_Reviewed: 2026-07-23T00:00:00Z (re-review / reconciliation of 2026-07-02 report)_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
