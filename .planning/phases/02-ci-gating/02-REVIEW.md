---
phase: 02-ci-gating
reviewed: 2026-07-01T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - .github/workflows/ci.yml
  - .github/verify-branch-protection.py
  - .github/verify-docs.sh
  - .github/branch-protection.json
  - backend/pyproject.toml
  - frontend/src/app/(authed)/dashboard/tickets/page.test.tsx
  - frontend/src/app/(authed)/dashboard/tickets/rules/page.test.tsx
  - docs/13-deployment.md
  - docs/12-pipelines-cicd.md
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: resolved
resolution:
  fixed: [WR-01, WR-02, WR-03]
  accepted: [WR-04, IN-01, IN-02, IN-03]
  resolved_in: d8c1585
---

> **Resolution (2026-07-01, commit d8c1585):**
> - **WR-03 (fixed, empirically verified):** the `mypy app/ | mypy-baseline filter` step leaked mypy's exit 1 under GitHub Actions' default `bash -eo pipefail`, failing the required Backend check on every run. Fixed with an inline `set +o pipefail`. Verified: baselined-only errors → step exit 0; a newly-injected type error → step exit 1 (gate still blocks).
> - **WR-01 / WR-02 (fixed):** `docs/12-pipelines-cicd.md` per-job tables still described the removed masks and listed PROD-02 as a pending cleanup target; corrected to hard-fail / baseline-gated, refreshed the drifted `ci.yml` line anchors, and marked PROD-02 complete.
> - **WR-04 (accepted):** Semgrep SAST depends on an external SaaS + token; this is the existing architecture (out of Phase 2 scope) and is noted, not changed.
> - **IN-01 / IN-02 / IN-03 (accepted / deferred):** minor verifier hardening (assert `strict`/`enforce_admins`/review-count, guard `c["context"]`, tighten `verify-docs.sh` greps) — low-priority, left for a follow-up.

# Phase 2: Code Review Report

**Reviewed:** 2026-07-01
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 2 re-enables push/PR/schedule CI triggers, removes three `|| true` soft-fail masks
(mypy, frontend lint, `tsc`), swaps the masked mypy step for a committed-baseline gate
(`mypy app/ | mypy-baseline filter` against `backend/mypy-baseline.txt`), pins ZAP actions
forward, gates DAST off PRs, adds a Python branch-protection read-back verifier + a bash docs
verifier + a committed branch-protection JSON body, and widens two frontend test mock casts to
`as unknown as`.

The core wiring is largely correct and matches the documented policy:

- **branch-protection.json** matches the documented policy exactly: 4 required checks
  (`Backend`, `Frontend`, `Semgrep SAST`, `Terraform Validate`), DAST absent from required
  checks, `strict: false`, `enforce_admins: false`, `required_pull_request_reviews` present
  with `required_approving_review_count: 0`. The verifier's `EXPECTED` set matches these four.
- The DAST `if: github.event_name != 'pull_request'` correctly keeps the advisory scan off PR
  runs while still running it on push/schedule/dispatch, and DAST is not a required check.
- `backend/mypy-baseline.txt` (no leading dot) correctly matches `mypy-baseline`'s default
  `baseline_path`, so `filter` finds it with no extra flag.
- The `as unknown as` cast widenings are the idiomatic TS fix for partial-mock shape mismatch;
  no test logic changed.

The findings below are concentrated in **documentation drift** (docs/12 still describes the
old masked state as current, with now-wrong line references) and two robustness concerns in the
CI type-check step and the verifier script. No security vulnerabilities or data-loss risks found.

## Warnings

### WR-01: docs/12 still documents the removed soft-fail masks as the current state

**File:** `docs/12-pipelines-cicd.md:74, 86-87, 126-142`
**Issue:** This phase removed the three `|| true` masks, but docs/12 still presents them as live:
- Line 74: `| Type check | \`mypy app/ \|\| true\` | ⚠ **soft** |` — the step now runs
  `mypy app/ | mypy-baseline filter`.
- Lines 86-87: `npm run lint || true` and `npx tsc --noEmit || true` shown as `⚠ soft` — both
  masks are gone.
- Lines 126-135 ("Soft-fail summary (Phase 2 cleanup target)") and lines 137-142 list PROD-02-01/02/03/04
  as pending deliverables — but this phase *is* PROD-02 and completed them.

This directly contradicts the same file's own line 61 narrative ("The soft-fail masks are gone")
and the `verify-docs.sh` intent (which only guards against a *stale trigger* note, not stale
mask/table content). A reader of the tables above line 61 is actively misled about CI behavior.
**Fix:** Update the docs/12 step tables to reflect current commands (`mypy app/ | mypy-baseline filter`
hard-fail, `npm run lint` hard-fail, `npx tsc --noEmit` hard-fail), and either delete the
"Soft-fail summary (Phase 2 cleanup target)" section + PROD-02 checklist or mark them DONE. The
only remaining `continue-on-error` masks are the three ZAP steps (advisory by design) — keep those.

### WR-02: docs/12 CI line-number references are now wrong after the trigger/mask edits

**File:** `docs/12-pipelines-cicd.md:74, 130, 131, 132, 119, 120, 121, 197, 199`
**Issue:** The trigger block additions shifted line numbers in `ci.yml`, so the anchored
references drifted:
- docs/12 cites mypy at `#L59` and `#L74`; mypy is now `ci.yml:61`.
- docs/12 cites lint `#L95` / tsc `#L97`; they are now `ci.yml:97` / `ci.yml:99`.
- docs/12 cites ZAP steps `#L164` / `#L173` / `#L182`; they are now `ci.yml:167` / `176` / `185`
  (`continue-on-error` lines) with the `uses:` at `161` / `170` / `179`.

Deep-links now point at the wrong lines (e.g. `#L59` is `ruff format --check`). Same drift
affects docs/13 line 62's implicit claims are fine, but docs/12 references are stale.
**Fix:** Recompute all `../.github/workflows/ci.yml#Lnn` anchors against the current file, or
switch to line-agnostic references (step names) so they don't rot on every trigger edit.

### WR-03: `mypy app/ | mypy-baseline filter` under GitHub Actions `pipefail` may fail on baselined-only errors

**File:** `.github/workflows/ci.yml:61`
**Issue:** GitHub Actions runs `run:` steps with `bash --noprofile --norc -eo pipefail {0}` —
`pipefail` is **on**. `mypy` exits non-zero whenever it reports *any* errors, including the 619
baselined pre-existing ones. With `pipefail`, a non-zero exit from the *left* side of the pipe
propagates even when `mypy-baseline filter` (right side) exits 0 after absorbing all errors into
the baseline. The intended semantics — "green when only baselined errors remain, red only on
new errors" — are precisely what mypy-baseline's exit code encodes, but `pipefail` can leak
mypy's non-zero and turn the step (a **required** check) red on every run, blocking all merges.
Whether this bites depends on the exact mypy/mypy-baseline exit-code contract for the
baselined-only case; it is not proven to fail here, but it is the documented failure mode for
this exact pattern and should be verified before relying on the gate.
**Fix:** Make the intent explicit and pipefail-safe, e.g.:
```yaml
- name: Type check (mypy)
  shell: bash
  run: |
    set +o pipefail
    mypy app/ | mypy-baseline filter
```
or capture mypy output first and feed the file to `mypy-baseline filter` so only the filter's
exit code gates the step. Confirm on a real run that a baselined-only tree is green and a newly
introduced error is red.

### WR-04: `Semgrep SAST` is a required merge gate but depends on an external service / secret

**File:** `.github/workflows/ci.yml:124-134`, `.github/branch-protection.json:7`
**Issue:** `Semgrep SAST` is one of the four *required* checks, and its only step is
`semgrep ci` with `SEMGREP_APP_TOKEN` from secrets. If the token is unset/expired, or
semgrep.dev is unreachable (`semgrep ci` contacts the app when a token is present), the required
check can fail for reasons unrelated to code quality — hard-blocking every merge with no
`continue-on-error` fallback. Unlike Backend/Frontend/Terraform (self-contained), this couples
the merge gate to a third-party SaaS and a live secret.
**Fix:** Either (a) pin semgrep to a self-contained local run for the gating check
(`semgrep scan --config auto --error` without requiring the app token, keep `semgrep ci` as a
separate advisory publish step), or (b) explicitly document/monitor the token as a hard
dependency of the merge gate and add alerting for token expiry. At minimum, verify `semgrep ci`
degrades gracefully (does not hard-fail) when the token is absent.

## Info

### IN-01: Branch-protection verifier does not assert `strict`/`enforce_admins`/review-count policy

**File:** `.github/verify-branch-protection.py:30-47`
**Issue:** The verifier checks the required-check set, absence of DAST, and mere *presence* of
`required_pull_request_reviews`, but does not assert the rest of the documented policy
(`strict: false`, `enforce_admins: false`, `required_approving_review_count: 0`). It prints
`enforce_admins` for the operator to eyeball but never fails on drift. So a repo that silently
flips `enforce_admins` or bumps the required approval count would still pass. This matches the
script's stated read-only "confirm the four checks + DAST-not-required" purpose, so it is not a
defect — just an incomplete guardrail against the committed JSON body drifting from live state.
**Fix:** Optionally extend `problems` to assert
`data["required_status_checks"]["strict"] is False`,
`data["enforce_admins"]["enabled"] is False`, and the review-count, so the verifier fully
mirrors `branch-protection.json`.

### IN-02: Verifier assumes the modern `checks` API shape and `context` key without guarding

**File:** `.github/verify-branch-protection.py:30-31`
**Issue:** `checks = data.get("required_status_checks", {}).get("checks", [])` then
`{c["context"] for c in checks}`. The `.get(..., [])` guards a missing `required_status_checks`
(protection disabled) by yielding an empty set — which correctly fails against `EXPECTED`. But
`c["context"]` will raise `KeyError` (uncaught traceback, not the clean `FAIL:` message) if the
API ever returns a check entry without `context`. Low risk with today's GitHub API, but the
error path is an ugly stack trace rather than a graceful exit 1.
**Fix:** Use `c.get("context")` and filter `None`, or wrap the parse in try/except to emit the
consistent `branch protection FAIL:` format on malformed payloads.

### IN-03: `verify-docs.sh` grep for the section header is loose enough to match prose

**File:** `.github/verify-docs.sh:7`
**Issue:** `grep -qF "CI Gating & Branch Protection"` matches the substring anywhere in
docs/13, not specifically the `## CI Gating & Branch Protection` heading. A passing mention in
running text (or in a link) would satisfy the check even if the section heading were removed or
renamed. Similarly the `for s in "Backend" ...` loop matches those very common words anywhere in
a 800-line file, so it is a weak assertion that the *required-checks table* exists.
**Fix:** Tighten to anchor the heading, e.g. `grep -qE '^## +CI Gating & Branch Protection'`,
and scope the required-check-name checks to the table region if stronger guarantees are wanted.
Non-blocking; the verifier still catches the primary regression it targets.

---

_Reviewed: 2026-07-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
