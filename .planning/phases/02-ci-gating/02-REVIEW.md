---
phase: 02-ci-gating
reviewed: 2026-07-24T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - .github/workflows/ci.yml
  - .github/workflows/cd.yml
  - .github/verify-branch-protection.py
  - .github/verify-docs.sh
  - .github/ci-verify.py
  - .github/branch-protection.json
  - backend/pyproject.toml
  - frontend/src/app/(authed)/dashboard/tickets/page.test.tsx
  - frontend/src/app/(authed)/dashboard/tickets/rules/page.test.tsx
  - docs/13-deployment.md
  - docs/12-pipelines-cicd.md
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
reconciliation:
  note: >-
    Re-review of shipped v1.0 phase against CURRENT code (2026-07-24). The prior
    REVIEW.md (2026-07-01, status "resolved") claimed WR-01/WR-02/WR-03 fixed in
    d8c1585 and WR-04/IN-01/IN-02/IN-03 accepted. Verified each below.
  fixed_confirmed: [WR-03]
  regressed: [WR-01, WR-02]
  still_open: [WR-04, IN-01, IN-02, IN-03]
  new: [IN-04, IN-05]
---

# Phase 2: Code Review Report (Re-review)

**Reviewed:** 2026-07-24 (placeholder timestamp)
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

This is a re-review of the shipped v1.0 CI-gating phase. The prior REVIEW.md
(2026-07-01) marked itself `resolved` — WR-01/WR-02/WR-03 "fixed" in commit
d8c1585, the rest accepted. Every prior finding was re-verified against the
**current** tree; results below.

**Bottom line:**

- **WR-03 (mypy pipefail) is genuinely fixed** — `ci.yml:70` now runs
  `set +o pipefail` before `mypy app/ | mypy-baseline filter --allow-unsynced`,
  so the required Backend check's exit code is the baseline filter's (green on
  baselined-only, red on new errors). Confirmed present. **Not re-reported.**
- **WR-01 and WR-02 have REGRESSED.** The d8c1585 docs/12 fix is NOT in the
  current tree: `docs/12-pipelines-cicd.md` again describes CI as
  `workflow_dispatch`-only and still lists the three `|| true` masks and the
  "Phase 2 cleanup target" checklist as pending — directly contradicting the
  now-armed `ci.yml`. This matches the known "GSD worktree stale-base" hazard
  (a later milestone's worktree silently reverted the Phase 2 docs edit).
  **Both re-reported as verified-against-current-code.**
- **WR-04, IN-01, IN-02, IN-03 still exist** in current code (previously
  accepted / deferred). Re-reported at their original severity, tagged
  verified-against-current-code.
- **Two new low-severity items** surfaced from the now-committed `cd.yml` and
  the verifier wiring (IN-04, IN-05).

The core Phase 2 wiring in `ci.yml`, `branch-protection.json`, `ci-verify.py`,
`pyproject.toml`, and the two frontend test files remains correct. No Critical
security issues, injection paths, or silent-bypass defects found in the
executable CI/CD; `cd.yml` is notably well-hardened against `${{ }}` and
tag-name injection (allowlisted tag, quoted heredoc, env-bound expressions).
The open findings are documentation drift plus verifier-hardening nits.

## Warnings

### WR-01: docs/12 has REGRESSED to the pre-Phase-2 state (masks + manual-dispatch trigger)

**File:** `docs/12-pipelines-cicd.md:10-11, 48-57, 70, 82-83, 122-138`
**Status:** verified-against-current-code — **regression** (prior fix in
d8c1585 is absent from the current tree).
**Issue:** `ci.yml` today arms `push`, `pull_request`, and `schedule`
(`ci.yml:5-10`) and has no `|| true` masks, but docs/12 still documents the old
world as current:
- Mermaid (lines 10-11): `manual dispatch / workflow_dispatch only / see PROD-02`.
- Triggers block (lines 48-57): shows `push`/`pull_request` commented out and
  line 57 asserts "**Today CI runs only on manual dispatch.** … PROD-02 … will
  re-enable them." — false; they are enabled.
- Line 70: `| Type check | mypy app/ \|\| true | ⚠ **soft** |` — the step is now
  `set +o pipefail; mypy app/ | mypy-baseline filter --allow-unsynced` (hard gate).
- Lines 82-83: `npm run lint || true` and `npx tsc --noEmit || true` shown as
  `⚠ soft` — both masks are gone (`ci.yml:107,109`, hard-fail).
- Lines 122-138: "Soft-fail summary (Phase 2 cleanup target)" + PROD-02-01..04
  listed as pending deliverables — but this phase *is* PROD-02 and shipped them.

Corroboration: the phase's own `verify-docs.sh:16` greps for `manual dispatch`
and would **FAIL** on the current docs/12 (line 57 matches). The regression is
machine-detectable; it simply isn't wired into CI (see IN-04).
**Fix:** Re-apply the d8c1585 docs/12 edit against the current file: update the
mermaid + triggers block to "runs on push / PR / nightly schedule", flip the
step tables to hard-fail (`mypy app/ | mypy-baseline filter --allow-unsynced`,
`npm run lint`, `npx tsc --noEmit`), and delete or mark-DONE the "Soft-fail
summary (Phase 2 cleanup target)" section + PROD-02 checklist. Keep only the
three ZAP `continue-on-error` masks (advisory by design).

### WR-02: docs/12 `ci.yml#Lnn` anchors are stale after the trigger/mask edits

**File:** `docs/12-pipelines-cicd.md:70, 82, 83, 115-117, 126-131`
**Status:** verified-against-current-code — still wrong (regressed alongside WR-01).
**Issue:** The armed trigger block shifted `ci.yml` line numbers, so every
deep-link anchor in docs/12 now points at the wrong line:
- mypy cited at `#L59` (lines 70, 126) → mypy `run:` is now `ci.yml:69-71`;
  `#L59` is `ruff format --check .`.
- lint `#L95` (lines 82, 127) → `npm run lint` is now `ci.yml:107`.
- tsc `#L97` (lines 83, 128) → `npx tsc --noEmit` is now `ci.yml:109`.
- ZAP `#L164 / #L173 / #L182` (lines 115-117, 129-131) → the three
  `continue-on-error: true` lines are now `ci.yml:177 / 186 / 195` (with the
  `uses:` at 171 / 180 / 189).

**Fix:** Recompute all `../.github/workflows/ci.yml#Lnn` anchors against the
current file, or switch to line-agnostic references (step names) so they don't
rot on the next trigger edit. Fold this into the WR-01 re-apply.

### WR-04: `Semgrep SAST` is a required merge gate coupled to an external SaaS + secret

**File:** `.github/workflows/ci.yml:134-144`, `.github/branch-protection.json:7`
**Status:** verified-against-current-code — still present (previously *accepted*
as out-of-scope architecture; re-surfaced, not re-litigated).
**Issue:** `Semgrep SAST` is one of the four *required* checks
(branch-protection.json line 7) and its only step is `semgrep ci` with
`SEMGREP_APP_TOKEN` from secrets (ci.yml:141-144), with no `continue-on-error`
fallback. If the token is unset/expired or semgrep.dev is unreachable, the
required check can hard-fail for reasons unrelated to code quality, blocking
every merge — unlike Backend/Frontend/Terraform which are self-contained.
**Fix (unchanged from prior review):** Either (a) run a self-contained local
scan for the gating check (`semgrep scan --config auto --error`, no app token)
and keep `semgrep ci` as a separate advisory publish step, or (b) explicitly
document the token as a hard merge-gate dependency and add token-expiry
alerting. At minimum confirm `semgrep ci` degrades gracefully without the token.

## Info

### IN-01: Branch-protection verifier does not assert `strict` / `enforce_admins` / review-count

**File:** `.github/verify-branch-protection.py:30-47`
**Status:** verified-against-current-code — still present.
**Issue:** The verifier checks the required-check set, DAST absence, and mere
*presence* of `required_pull_request_reviews`, but never asserts the rest of the
committed policy (`branch-protection.json`: `strict: false`,
`enforce_admins: false`, `required_approving_review_count: 0`). It prints
`enforce_admins` (line 47) for eyeballing but never fails on drift, so a repo
that silently flips `enforce_admins` or bumps the approval count still passes.
**Fix:** Extend `problems` to assert
`data["required_status_checks"]["strict"] is False`,
`data["enforce_admins"]["enabled"] is False`, and the review count, so the
verifier fully mirrors the committed JSON body.

### IN-02: Verifier assumes the `checks` shape and unguarded `c["context"]`

**File:** `.github/verify-branch-protection.py:30-31`
**Issue:** `checks = data.get("required_status_checks", {}).get("checks", [])`
then `{c["context"] for c in checks}`. The `.get(..., [])` handles disabled
protection (empty set correctly fails `EXPECTED`), but `c["context"]` raises an
uncaught `KeyError` (ugly traceback instead of the clean `FAIL:` message) if the
API ever returns a check entry without `context`. Low risk with today's API.
**Status:** verified-against-current-code — still present.
**Fix:** Use `c.get("context")` and filter `None`, or wrap the parse in
try/except to emit the consistent `branch protection FAIL:` format.

### IN-03: `verify-docs.sh` greps are substring matches, not anchored assertions

**File:** `.github/verify-docs.sh:7, 13-15`
**Issue:** `grep -qF "CI Gating & Branch Protection"` (line 7) matches the
substring anywhere in docs/13, not the `## CI Gating & Branch Protection`
heading; the `for s in "Backend" "Frontend" …` loop (lines 13-15) matches those
common words anywhere in an 800-line file, so it weakly asserts the
required-checks *table* exists.
**Status:** verified-against-current-code — still present.
**Fix:** Anchor the heading (`grep -qE '^## +CI Gating & Branch Protection'`)
and scope the check-name greps to the table region. Non-blocking.

### IN-04: None of the three Phase-2 verifier scripts are wired into any workflow

**File:** `.github/verify-docs.sh`, `.github/verify-branch-protection.py`,
`.github/ci-verify.py` (vs. `.github/workflows/ci.yml`)
**Status:** NEW (surfaced by this re-review; explains why WR-01/WR-02 regressed
undetected).
**Issue:** `ci.yml` never invokes `verify-docs.sh`, `verify-branch-protection.py`,
or `ci-verify.py` — they are operator-run-only tools. `verify-docs.sh` correctly
detects today's regressed docs/12 (it greps `manual dispatch`, which line 57
matches) and would exit 1, and `ci-verify.py` asserts the armed-CI invariants —
but because nothing runs them on push/PR, the WR-01/WR-02 doc regression shipped
silently. The guardrail exists but is disconnected from the gate.
**Fix:** Add a lightweight `verify` job (or steps in an existing job) that runs
`python3 .github/ci-verify.py` and `bash .github/verify-docs.sh` on push/PR so
doc/config drift fails CI. `verify-branch-protection.py` needs `gh` admin auth,
so keep it as a documented periodic operator check rather than an in-CI step.

### IN-05: `semgrep/semgrep` job container is unpinned (`:latest`) in a required gate

**File:** `.github/workflows/ci.yml:137-138`
**Status:** NEW (minor supply-chain note; related to but distinct from WR-04).
**Issue:** `container: image: semgrep/semgrep` pulls the floating `:latest` tag
for a *required* merge check. A breaking upstream image change (new default
rules, CLI behavior, or exit-code semantics) can flip the gate red or green
without any repo change, making the required check non-deterministic. The
GitHub Actions in this file are otherwise pinned to major versions (`@v5`,
`@v0.10.0`, etc.).
**Fix:** Pin the semgrep image to a specific tag or digest
(e.g. `semgrep/semgrep:1.XX.Y` or `@sha256:…`) and bump it deliberately, mirroring
the ruff/mypy version-pinning rationale already documented in
`backend/pyproject.toml:34-36`.

---

_Reviewed: 2026-07-24 (re-review of shipped v1.0 phase)_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
