# Phase 2: CI Gating - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

A PR with a failing backend test, type error, or frontend lint/type error cannot be merged to `main`. This phase re-arms the existing CI workflow (currently manual-only) and enforces it via branch protection.

In scope:
- Re-enable `push` (to `main`) and `pull_request` (to `main`) triggers in [.github/workflows/ci.yml](../../../.github/workflows/ci.yml) (currently `workflow_dispatch:` only — push/PR commented out at lines 5–8)
- Remove the three `|| true` failure masks: `mypy app/` (line 59), `npm run lint` (line 95), `npx tsc --noEmit` (line 97)
- Decide and implement the ZAP DAST policy (SC#4)
- Configure branch protection on `main` requiring CI green (SC#5) + document it

Out of scope (other phases):
- Update-path / release-CD reconciliation — [.github/workflows/cd.yml](../../../.github/workflows/cd.yml) and the install.sh auto-update cron are **Phase 3** (PROD-03). Do not touch `cd.yml` here beyond what branch protection requires.
- Adding *new* tests to raise coverage — **Phase 8** (PROD-08). This phase enforces the gate on the tests that exist; it does not author new ones.
- Tag-pinned deploys / rollback runbook — **Phase 3**.

</domain>

<decisions>
## Implementation Decisions

### Triggers
- **D-01:** Uncomment and enable both triggers: `push:` on `branches: [main]` and `pull_request:` on `branches: [main]`. Keep `workflow_dispatch:` for manual runs. (ci.yml lines 4–8.)

### Failure masks
- **D-02:** Remove `|| true` from all three steps so a non-zero exit fails the job:
  - `mypy app/` (ci.yml:59) — in the `backend` job
  - `npm run lint` (ci.yml:95) — in the `frontend` job
  - `npx tsc --noEmit` (ci.yml:97) — in the `frontend` job
- **D-03 (REVISED 2026-06-30 after research sized the backlog):** Research found the mask was hiding **619 mypy errors across 76 files** (~442 mechanical annotation gaps, ~149 real type bugs). Frontend is clean (lint 0 errors; tsc 6 errors in 2 ticket test files only). Strategy by tool:
  - **Frontend lint + tsc:** remove `|| true` and fix outright. The 6 tsc errors are one root cause (TanStack Query v5 `UseQueryResult` mock casts in `tickets/page.test.tsx` + `tickets/rules/page.test.tsx`) — fix narrowly with `as unknown as UseQueryResult<T, Error>`.
  - **mypy:** adopt a **baseline gate** rather than driving all 619 to zero in this phase. Re-enable mypy in CI (remove `|| true`) but run it through a committed baseline (recommended tool: `mypy-baseline` on PyPI — `mypy app/ | mypy-baseline sync` to snapshot, `mypy app/ | mypy-baseline filter` in CI). Effect: **any NEW type error fails the build** (satisfies PROD-02-02's intent), while the 619 pre-existing errors are tracked in a committed baseline file and burned down incrementally in a follow-up phase. The baseline is line-specific and version-controlled — it is NOT a blanket `|| true` mask or a relaxation of `strict = true`. Do NOT relax `[tool.mypy] strict = true`.
- **D-03b:** The 619-error burn-down is a **deferred follow-up phase** (track separately; see Deferred Ideas). Rationale: 149 are real logic bugs and the test-coverage floor (Phase 8) is not yet in place, so a big-bang fix-all carries regression risk without a safety net. Baseline-now + incremental-later is the chosen path.

### ZAP DAST policy (SC#4) — **advisory, main + nightly**
- **D-04:** ZAP stays **non-blocking**. Keep `continue-on-error: true` on all three scans (ci.yml:164/173/182) and keep uploading the report artifacts. Rationale: DAST is slow, needs the app running, and is noisy — gating PR merges on it flakes.
- **D-05:** The `dast` job (ci.yml:134, `needs: [backend, frontend]`) must NOT run on `pull_request` events. Gate it with a job-level `if:` so it runs only on `push` to `main` and on a scheduled run. Add a `schedule:` cron trigger (nightly) to the workflow `on:` block for the DAST sweep.
- **D-06:** Because ZAP is advisory and off-PR, it is **not** a required status check (see D-08). Its value is the nightly/post-merge report, not merge-blocking.

### Branch protection (SC#5) — **configure now via gh API**
- **D-07:** Configure programmatically via `gh api` (operator has admin on `Cyber-Solutions-MD/getvul`; `viewerCanAdminister: true`), using the **legacy branch-protection API** (`PUT /repos/{owner}/{repo}/branches/main/protection`) — single reproducible call, easier to document than rulesets. Require a PR before merging to `main` and require the status checks below to pass. `enforce_admins: false` (admins may push directly in a pinch — operator decision 2026-06-30). `strict: false` (no force-rebase-before-merge). Capture the exact `gh api` invocation in the deployment doc so it's reproducible.
  - **Open item for the planner to resolve empirically:** `required_pull_request_reviews` with `required_approving_review_count: 0` may or may not actually enforce "PR required" on GitHub Free (research assumption A1). Test the resulting protection with a direct-push attempt; if count 0 doesn't enforce the PR requirement, document the working configuration.
- **D-08:** Required status checks (must be green to merge): **`backend`, `frontend`, `semgrep`, `terraform`**. Explicitly NOT required: **`dast`** (advisory per D-04..06).
  - Note for planning: GitHub matches required checks by **job name as reported** (the `name:` of each job/run). Verify the exact check names the runs report once triggers are live, and register those exact strings — a mismatch silently makes a check "not required."
- **D-09:** `terraform` is required but only meaningful when `infra/` changes. Planning should decide between (a) always-run + fast no-op when infra is unchanged, or (b) path-filtered with a required "passes-when-skipped" shim. Required checks that get skipped on unrelated PRs can block merges on some GitHub configs — resolve this explicitly rather than discovering it on the first frontend-only PR.

### Documentation
- **D-10:** Document branch protection (the required-checks set, the PR requirement, and the exact `gh api`/ruleset used) in the deployment doc. The repo relocated `doc/ → docs/`; the live file is [docs/13-deployment.md](../../../docs/13-deployment.md), not the `doc/deployment.md` path the ROADMAP SC#5 still names. Add a "CI Gating & Branch Protection" section there.

### Claude's Discretion
- Exact `schedule:` cron time for the nightly DAST run
- Whether mypy/lint/tsc fixes land as one commit per tool or grouped
- The `terraform` skip/no-op mechanism (D-09 options a vs b) — pick the one that's robust on this repo's GitHub plan
- Job-level `if:` expression syntax for gating DAST off PRs

</decisions>

<specifics>
## Specific Ideas

- The masks were added to keep a red CI from blocking the demo; the whole point of this phase is to pay that debt down, not re-hide it. Prefer real fixes over suppressions.
- Branch protection should be reproducible (scripted), not click-ops — so a fresh clone/fork or a re-provisioned repo can re-apply it from the documented command.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- [.planning/REQUIREMENTS.md](../../../.planning/REQUIREMENTS.md) — PROD-02-01..PROD-02-04 (the phase requirements)
- [.planning/ROADMAP.md](../../../.planning/ROADMAP.md) §"Phase 2: CI Gating" — goal, success criteria, dependency on Phase 1

### CI/CD surface
- [.github/workflows/ci.yml](../../../.github/workflows/ci.yml) — the workflow being re-armed; 5 jobs (`backend`, `frontend`, `terraform`, `semgrep`, `dast`); triggers at lines 4–8; masks at 59/95/97; ZAP `continue-on-error` at 164/173/182
- [.github/workflows/cd.yml](../../../.github/workflows/cd.yml) — **read for boundary awareness only**; reconciliation is Phase 3, not this phase

### Docs to update
- [docs/13-deployment.md](../../../docs/13-deployment.md) — add CI gating + branch protection section (this is the relocated `doc/deployment.md` the ROADMAP references)
- [docs/16-security.md](../../../docs/16-security.md) — check whether it asserts CI-enforced gating; keep claims true

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The CI workflow already exists and is fully written — backend (pytest + mypy), frontend (lint + tsc + vitest), terraform, semgrep, and dast jobs are all present. This phase **arms** what's there; it does not build CI from scratch.
- Phase 1 added backend integration tests (multi-replica Redis suite) that the `backend` job will now actually enforce.

### Established Patterns
- Jobs are named (`backend`, `frontend`, `terraform`, `semgrep`, `dast`) and `dast` already `needs: [backend, frontend]` — fan-in dependency exists.
- `continue-on-error: true` is the project's existing idiom for advisory steps (the ZAP scans) — D-04 keeps that idiom for DAST.

### Integration Points
- Branch protection ties GitHub repo settings to the job names reported by `ci.yml` runs — the coupling point is the exact check-name strings (D-08 note).
- Removing masks (D-02) couples this phase to the *current real* state of mypy/lint/tsc output — the true size of work is unknown until those run unmasked (D-03).

</code_context>

<deferred>
## Deferred Ideas

- **mypy 619-error burn-down to zero** — the baseline (D-03) blocks new errors now; clearing the 619 pre-existing errors (442 mechanical annotation gaps + 149 real type bugs across connectors/vulnerabilities/ticketing/assets/auth/etc.) is a **dedicated follow-up phase** to be added to the roadmap once Phase 2 ships. Sequence it before or alongside Phase 8 (test coverage) since the 149 real bugs need a test safety net. The baseline file shrinks as errors are fixed; the gate ratchets.
- **mypy version pin** (`mypy==2.1.*` in pyproject `[dev]`) for reproducible baseline/CI parity — fold into the burn-down phase or Plan during baseline setup if trivial.
- **Gate ZAP on a severity threshold** (fail build on High/Medium) — considered and rejected for now (D-04, advisory). Could revisit once DAST noise is characterized.
- **Update-path reconciliation** (cd.yml vs install.sh cron race; tag-pinned deploys; rollback runbook) — Phase 3 (PROD-03).
- **New test authoring to raise coverage floor** — Phase 8 (PROD-08).

</deferred>

---

*Phase: 02-ci-gating*
*Context gathered: 2026-06-30*
