---
phase: 03-update-path-reconciliation
verified: 2026-07-02T10:00:00Z
status: human_needed
score: 9/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Dry-run rollback on a test GCE VM"
    expected: "Cut a throwaway release tag, deploy via CD release trigger, then dispatch cd.yml with release_tag=<prior-tag>; /health returns 200 on the prior version. Record outcome."
    why_human: "Requires real GCE VM, GCE_SSH_PRIVATE_KEY secret, and live GitHub Actions run. Cannot verify without live infra + credentials."
---

# Phase 03: Update Path Reconciliation — Verification Report

**Phase Goal:** There is exactly one way that production gets new code, and operators have a tested rollback procedure.
**Verified:** 2026-07-02T10:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | install.sh no longer installs any auto-update cron or getvul-update binary | VERIFIED | `grep -c "getvul-update" install.sh` → 0; Step 8 replaced with a comment referencing GitHub Actions CD at line 94-96 |
| 2  | All three cloud startup scripts (gcp/aws/azure) no longer install the auto-update cron | VERIFIED | All three return 0 for `grep -c "getvul-update"`; cron blocks replaced with `# Auto-update cron removed (PROD-03)` comments |
| 3  | scripts/auto-update.sh no longer exists in the git tree | VERIFIED | `git ls-files scripts/auto-update.sh` returns empty; file confirmed deleted |
| 4  | No architecture/structure/troubleshooting doc points at the removed getvul-update command as a live mechanism | VERIFIED | `grep -c "CRON" docs/02-architecture.md` → 0; `grep -c "auto-update.sh" docs/07-project-structure.md` → 0; `grep -c "cron)" docs/07-project-structure.md` → 0; D3 in troubleshooting rewritten to document resolved status |
| 5  | A live-VM operator has a documented one-time cleanup for cron residue | VERIFIED | docs/17-troubleshooting.md §B1 at line 112: `sudo rm -f /etc/cron.d/getvul-update /usr/local/bin/getvul-update`; `grep -c "sudo rm -f /etc/cron.d/getvul-update" docs/17-troubleshooting.md` → 1 |
| 6  | CD checks out a specific release tag, not main HEAD | VERIFIED | `git checkout --force "refs/tags/$DEPLOY_TAG"` at line 77; `grep -c "reset --hard origin/main" cd.yml` → 0; `grep -c "checkout --force" cd.yml` → 1 |
| 7  | cd.yml resolves the deploy tag correctly whether triggered by a release or by manual workflow_dispatch | VERIFIED | "Resolve deploy tag" step binds `RELEASE_TAG_NAME` and `DISPATCH_TAG` to env vars, then resolves `DEPLOY_TAG="${RELEASE_TAG_NAME:-$DISPATCH_TAG}"` — avoids `github.ref_name` anti-pattern; `grep -c "github.ref_name" cd.yml` → 0 |
| 8  | A manual deploy/rollback is triggered by a release_tag string input, not a force boolean | VERIFIED | `grep -c "force:" cd.yml` → 0; `grep -c "release_tag:" cd.yml` → 1 |
| 9  | docs/13-deployment.md has a Rollback section with the exact gh commands to revert to a prior release tag, and prominently warns that a code rollback does NOT revert Alembic migrations | VERIFIED | `grep -c "## Rollback" docs/13-deployment.md` → 1; `grep -c "gh workflow run cd.yml" docs/13-deployment.md` → 1; `grep -c "DOES NOT REVERT DATABASE MIGRATIONS" docs/13-deployment.md` → 1; migration WARNING blockquote placed at Step 2 (before the trigger step) |
| 10 | Dry-run rollback confirmed on a live VM (SC#4 manual UAT) | UNCERTAIN | Cannot verify programmatically — requires live GCE infra and credentials |

**Score:** 9/10 truths verified (1 requires human)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `install.sh` | Provisioning without auto-update cron; Step 8 replaced with removal note referencing GitHub Actions CD | VERIFIED | Step 8 is a comment block at lines 94-96; zero `getvul-update` matches; `bash -n` parse passes |
| `infra/gcp/startup.sh` | GCE first-boot provisioning without the daily cron block | VERIFIED | Cron block replaced with `# Auto-update cron removed (PROD-03)` comment at line 73; zero `getvul-update` matches |
| `infra/aws/startup.sh` | AWS first-boot provisioning without the daily cron block | VERIFIED | Same treatment at line 97; zero `getvul-update` matches |
| `infra/azure/startup.sh` | Azure first-boot provisioning without the daily cron block | VERIFIED | Same treatment at line 75; zero `getvul-update` matches |
| `scripts/auto-update.sh` | Absent from git tree (deleted) | VERIFIED | `git ls-files scripts/auto-update.sh` → empty; commit 7128409 |
| `.github/workflows/cd.yml` | Tag-pinned CD with release_tag dispatch input, allowlist validation, quoted heredoc, refs/tags checkout | VERIFIED | Allowlist at line 42; quoted `'DEPLOY'` heredoc at line 62; `refs/tags/$DEPLOY_TAG` checkout at line 77; YAML parses cleanly |
| `docs/13-deployment.md` | §Rollback runbook with gh commands + migration caveat; §Release process describing single canonical path | VERIFIED | 4-step runbook at lines 727-766; migration WARNING blockquote at lines 741-752; `gh workflow run cd.yml --field release_tag=<prior-tag>` at line 757 |
| `docs/17-troubleshooting.md` | §B1 rewritten as one-time cron-residue cleanup | VERIFIED | §B1 heading "A migrated VM still has the old auto-update cron installed"; cleanup command `sudo rm -f /etc/cron.d/getvul-update` at line 112 |
| `docs/02-architecture.md` | CRON mermaid node and edges removed | VERIFIED | `grep -c "CRON" docs/02-architecture.md` → 0 |
| `docs/07-project-structure.md` | auto-update.sh entry removed; cron mention removed from install.sh description | VERIFIED | `grep -c "auto-update.sh" docs/07-project-structure.md` → 0; `grep -c "cron)" docs/07-project-structure.md` → 0 |
| `docs/12-pipelines-cicd.md` | CRON node removed; release_tag string input documented; PROD-03 known-issues resolved | VERIFIED | `grep -c "reset --hard origin/main" docs/12-pipelines-cicd.md` → 0; `grep -c "release_tag" docs/12-pipelines-cicd.md` → 3 |
| `docs/diagrams/pipelines-cicd.mmd` | CRON node removed; PULL node updated to tag checkout | VERIFIED | `grep -c "CRON" docs/diagrams/pipelines-cicd.mmd` → 0; `grep -c "reset --hard origin/main" docs/diagrams/pipelines-cicd.mmd` → 0 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cd.yml` Resolve step | `DEPLOY_TAG` env | `RELEASE_TAG_NAME:-$DISPATCH_TAG` (env var binding, not direct expression interpolation) | WIRED | Lines 28-48; `github.event.release.tag_name` and `inputs.release_tag` bound to env vars before shell evaluation — CR-01 fix confirmed |
| `cd.yml` Deploy step | `refs/tags/$DEPLOY_TAG` checkout | Quoted heredoc + remote env var `DEPLOY_TAG=...` + `git checkout --force "refs/tags/$DEPLOY_TAG"` | WIRED | Lines 62-77; heredoc is `'DEPLOY'` (quoted); tag verified via `git rev-parse --verify refs/tags/$DEPLOY_TAG^{commit}` before checkout — WR-01 fix confirmed |
| `docs/13-deployment.md §Rollback` | `cd.yml workflow_dispatch` | `gh workflow run cd.yml --field release_tag=<prior-tag>` | WIRED | Line 757; rollback triggers same CD path as production release |
| `install.sh` | absence of `getvul-update` | No cron install, no binary write, no summary line | VERIFIED ABSENT | `grep -c "getvul-update" install.sh` → 0 |
| `infra/gcp/startup.sh` | absence of `getvul-update` | No cp/chmod/crontab block | VERIFIED ABSENT | `grep -c "getvul-update" infra/gcp/startup.sh` → 0 |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase modifies provisioning scripts, a GitHub Actions workflow, and documentation. No React/Vue components, APIs, or data-rendering artifacts. The "data flow" is the deployment trigger → VM checkout path, verified via the key link section above.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| install.sh shell syntax valid | `bash -n install.sh` | exit 0 | PASS |
| infra/gcp/startup.sh shell syntax valid | `bash -n infra/gcp/startup.sh` | exit 0 | PASS |
| cd.yml is valid YAML | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/cd.yml'))"` | `yaml ok` | PASS |
| No getvul-update in provisioning files | `grep -c "getvul-update" install.sh infra/*/startup.sh` | all 0 | PASS |
| scripts/auto-update.sh absent | `git ls-files scripts/auto-update.sh` | empty | PASS |
| Rollback runbook has gh command | `grep -c "gh workflow run cd.yml" docs/13-deployment.md` | 1 | PASS |
| Migration caveat present | `grep -c "DOES NOT REVERT DATABASE MIGRATIONS" docs/13-deployment.md` | 1 | PASS |
| No reset --hard in cd.yml | `grep -c "reset --hard origin/main" .github/workflows/cd.yml` | 0 | PASS |
| Tag-only checkout enforced | `grep -c "refs/tags" .github/workflows/cd.yml` | 4 (including comment + guard + checkout) | PASS |
| Live rollback on VM (SC#4) | Manual UAT required | Not run | SKIP (needs live GCE infra) |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| PROD-03-01 | 03-01-PLAN.md | One canonical update mechanism chosen; install.sh no longer registers a competing cron | SATISFIED | `grep -c "getvul-update" install.sh` → 0; Step 8 replaced with GitHub Actions CD reference |
| PROD-03-02 | 03-01-PLAN.md | install.sh no longer registers a competing cron; auto-update.sh removed | SATISFIED | `git ls-files scripts/auto-update.sh` → empty; all three startup scripts cleaned; `grep -c "getvul-update"` → 0 on all |
| PROD-03-03 | 03-02-PLAN.md | CD flow uses git fetch + checkout tag, not git reset --hard origin/main | SATISFIED | cd.yml: `git fetch --tags --force` + `git checkout --force "refs/tags/$DEPLOY_TAG"`; `reset --hard` → 0; post-review fixes (CR-01 allowlist, WR-01 refs/tags enforcement) both present in commit 37c3a37 |
| PROD-03-04 | 03-02-PLAN.md | Rollback procedure documented in deployment doc | SATISFIED | docs/13-deployment.md §Rollback at line 727: 4-step runbook with `gh workflow run cd.yml --field release_tag=<prior-tag>`, migration WARNING blockquote, and verify step |

All four requirement IDs declared in the PLAN frontmatter (PROD-03-01, PROD-03-02 in Plan 01; PROD-03-03, PROD-03-04 in Plan 02) are covered. No orphaned requirements: REQUIREMENTS.md maps exactly these four IDs to Phase 3.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `install.sh` | 20, 37, 67, 71, 87, 91 | Inconsistent step counter denominators (`[1/5]`, `[2/6]`, `[6/7]`, `[7/7]`) | Info | Cosmetic — confusing to operators watching install, but does not affect function; flagged as IN-01 in code review |
| `docs/13-deployment.md` | ~155 | "8 steps" claim vs 7 actual steps enumerated | Info | Minor doc drift flagged as IN-02 in code review; does not block deployment |
| `.github/workflows/cd.yml` | 55 | `ssh-keyscan` paired with `StrictHostKeyChecking=no` — keyscan is decorative | Warning | Host-key trust absent; flagged as WR-04 in code review; does not affect phase goal (TOFU is the pre-existing posture, not a regression) |
| `docs/diagrams/pipelines-cicd.mmd` | 20-28 | CD subgraph does not clarify it has no CI precondition | Info | Flagged as IN-04 in code review; informational, no operational impact |

No anti-patterns were found that block the phase goal. The CR-01 (command injection) and WR-01 (branch-name bypass) findings from code review are **both fixed** in commit 37c3a37, which is present in the repository history.

---

### Human Verification Required

#### 1. Dry-Run Rollback on a Test VM (SC#4)

**Test:** On a real GCE VM with the deploy user and GCE_SSH_PRIVATE_KEY:
1. Cut a throwaway release tag (e.g. `v0.99.0-test`) and publish a GitHub release against it — this fires the CD workflow and deploys that tag to the VM.
2. Confirm `/health` returns `{"status":"ok"}` on that version.
3. Dispatch `cd.yml` via `gh workflow run cd.yml --field release_tag=<prior-tag>` (or GitHub UI) using an earlier tag.
4. Watch the Actions run complete. The "Verify deployment" step should confirm `/health` on the prior version.
5. Record the Actions run URL and outcome in this VERIFICATION.md.

**Expected:** The CD job resolves the `release_tag` input to `DEPLOY_TAG`, validates it against the allowlist, SSHes to the VM, verifies `refs/tags/$DEPLOY_TAG^{commit}` exists, checks out `refs/tags/$DEPLOY_TAG`, rebuilds, and health-checks — returning 200 on the prior version.

**Why human:** Requires live GCE VM, GCE_SSH_PRIVATE_KEY and GCE_VM_IP secrets, and a real GitHub Actions run. No programmatic substitute exists.

---

### Gaps Summary

No blocking gaps. All automated criteria pass. The single open item (human UAT SC#4) was always designated as a manual must-have in the plan and is not a regression or missing implementation — the mechanism is fully built and verified by code inspection; human confirmation of end-to-end execution on live infra is the only remaining step.

**Code review findings status:**
- CR-01 (command injection via unquoted heredoc): FIXED in commit 37c3a37 — `${{ }}` expressions bound to env vars, allowlist validates tag format, heredoc restored to quoted `'DEPLOY'`, DEPLOY_TAG passed as remote env var.
- WR-01 (branch-name bypass via `git checkout --force "$TAG"`): FIXED in commit 37c3a37 — checkout now uses `git checkout --force "refs/tags/$DEPLOY_TAG"` with `git rev-parse --verify refs/tags/$DEPLOY_TAG^{commit}` guard.
- WR-02, WR-03, WR-04, IN-01 through IN-04: Open warnings/info from code review; none block the phase goal. These can be addressed in a future hardening pass or as part of PROD-07 (health/observability).

---

_Verified: 2026-07-02T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
