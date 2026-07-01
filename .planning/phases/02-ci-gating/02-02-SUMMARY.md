---
phase: 02-ci-gating
plan: 02
status: complete
requirements: [PROD-02-04]
completed: 2026-07-01
---

# 02-02 Summary — Branch Protection + Empirical Gate Verification

## What was built

Turned the armed CI (02-01) into an enforced merge gate on `main` and proved it blocks a bad merge.

- **Branch protection applied** to `Cyber-Solutions-MD/getvul` `main` via the committed body `.github/branch-protection.json` (operator-approved before the live PUT fired).
- **Empirical proof** that a PR with a red required check cannot merge.
- **Docs** for the gating policy in `docs/13-deployment.md` and corrected stale triggers in `docs/12-pipelines-cicd.md`.

## Task 1 — Branch protection (LIVE, operator-approved)

`main` was previously unprotected (HTTP 404). After showing the operator the exact JSON body and `gh api PUT` command, the PUT was fired. Live read-back via `python3 .github/verify-branch-protection.py Cyber-Solutions-MD/getvul` (exit 0):

- Required checks: **exactly** `['Backend', 'Frontend', 'Semgrep SAST', 'Terraform Validate']`
- `OWASP ZAP DAST`: **not** a required check (advisory)
- `strict: false`, `enforce_admins: false`, `required_pull_request_reviews` present (`required_approving_review_count: 0`)

## Task 2 — Empirical verification

**Part A — deliberate-failure PR (PROD-02-04 core proof):** A minimal test branch off `origin/main` carrying 02-01's armed `ci.yml` + one injected type error was opened as PR #13. Final check rollup:

| Required check | Conclusion |
|----------------|------------|
| Backend | FAILURE |
| Frontend | FAILURE |
| Terraform Validate | SUCCESS |
| Semgrep SAST | SUCCESS |
| OWASP ZAP DAST | SKIPPED |

`gh pr view` reported **`mergeStateStatus: BLOCKED`** — the merge could not proceed. PR #13 was closed without merging; the branch was deleted locally and on the remote. `main` was not touched.

> Note: `origin/main` is ~286 commits behind local `main`, and the armed CI is not yet on remote `main`. The test branch (off remote main + armed workflow) was the clean way to exercise the gate without a 286-commit PR or pushing to `main`.

**Part B — direct-push-to-main (research A1 / CONTEXT D-07):** **Not run — operator decision.** The active `gh` account holds repo admin and the policy sets `enforce_admins: false`, so a test `git push origin HEAD:main` would land on live `main` rather than being rejected. Whether `required_approving_review_count: 0` alone enforces PR-only pushes on this repo's plan is therefore **still empirically unresolved**. Documented in `docs/13` as an operator-verified item with the `enforce_admins: true` / ruleset escalation path.

**Part C — DAST off PR (PROD-02-03 cross-check):** `OWASP ZAP DAST` was `SKIPPED` on the PR-triggered run — confirmed not required and not executed on `pull_request`.

## Task 3 — Docs

- `docs/13-deployment.md`: new `## CI Gating & Branch Protection` section — triggers, the four required checks, advisory DAST, the mypy baseline gate, the reproducible `gh api` command referencing `.github/branch-protection.json`, the read-back verifier, and the empirical results (incl. the Part B caveat).
- `docs/12-pipelines-cicd.md`: corrected the "Pipeline at a glance" mermaid + Triggers section from "workflow_dispatch only" to push→main / PR→main / nightly schedule; updated the soft-fail footnote (masks removed, mypy baseline-gated).
- `.github/verify-docs.sh` (authored during planning, non-stub) passes: `docs OK`.

## Deviations & findings

- **mypy baseline filename (02-01 deviation, verified correct):** 02-01 committed the baseline as `backend/mypy-baseline.txt` (no leading dot), differing from this plan's `files_modified` (`.mypy-baseline.txt`). Verified against `mypy_baseline._config.Config`: the tool's default `baseline_path` is `Path('mypy-baseline.txt')` (no dot). The executor's filename is **correct** — it matches the tool default so `mypy-baseline filter` finds it with no extra flag. Docs reference the actual filename.
- Part B intentionally not exercised (see Task 2).

## Key files

- `.github/branch-protection.json` — applied protection body (4 checks, app_id -1, strict/enforce_admins false)
- `.github/verify-branch-protection.py` — live read-back verifier (exit 0)
- `.github/verify-docs.sh` — docs verifier (exit 0)
- `docs/13-deployment.md`, `docs/12-pipelines-cicd.md` — gating policy documented

## Verification

- `python3 .github/verify-branch-protection.py Cyber-Solutions-MD/getvul` → exit 0, four required checks, DAST absent
- Deliberate-failure PR #13 → `mergeStateStatus: BLOCKED`, closed unmerged, branch deleted
- `bash .github/verify-docs.sh` → `docs OK`, exit 0
- `git status --porcelain doc/deployment.md .github/workflows/cd.yml` → empty (boundary respected)
