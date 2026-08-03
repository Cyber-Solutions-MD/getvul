---
phase: 28-eval-cost-observability-gate
plan: 05
subsystem: ci
tags: [github-actions, deepeval, pytest, branch-protection, ci-cd, keyless-ci, byok]

# Dependency graph
requires:
  - phase: 28-01
    provides: "backend/tests/evals/test_golden_evals.py -- the keyless DeepEval golden-set harness this plan's ai-evals job invokes via `deepeval test run`"
  - phase: 28-02
    provides: "backend/tests/test_ai_injection_redteam.py + backend/tests/test_ai_budget_coverage.py -- the consolidated red-team suite + no-bypass budget coverage test this plan's ai-redteam-injection job runs together"
provides:
  - "ai-evals CI job (\"AI Golden-Set Evals (DeepEval)\") -- keyless, blocking, runs deepeval test run tests/evals/test_golden_evals.py with DEEPEVAL_TELEMETRY_OPT_OUT=1"
  - "ai-redteam-injection CI job (\"AI Prompt-Injection Red-Team (static)\") -- keyless, blocking, backend-shaped with the backend job's exact Postgres/Redis services + migrations, runs both test_ai_injection_redteam.py and test_ai_budget_coverage.py"
  - "ai-live-eval-optin CI job (\"AI Live Eval + Red-Team (opt-in, non-blocking)\") -- key-gated via HAS_DEV_KEY env-indirection, continue-on-error: true, fork-guarded (never runs on untrusted fork PRs)"
  - "branch-protection.json required_status_checks.checks[] gains the 2 new blocking job names byte-for-byte, making AIE-01/02/03 genuinely merge-blocking (not just CI-visible)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GitHub Actions secrets-in-if: env-indirection gate (env: HAS_DEV_KEY: ${{ secrets.X != '' }}, then if: env.HAS_DEV_KEY == 'true') to avoid the documented secrets-in-if inconsistency"
    - "branch-protection.json required_status_checks.checks[] registration is the actual merge-blocking mechanism on this repo -- a ci.yml job alone (see the pre-existing, deliberately-non-required docs job) only makes a check CI-visible, not merge-blocking"
    - "Disposable, non-secret, hardcoded test-only Fernet key in a CI job's step env (mirrors the existing JWT_SECRET_KEY: test-secret convention) for tests that must round-trip real Fernet-encrypted credentials against an ephemeral per-run CI Postgres"

key-files:
  created: []
  modified:
    - .github/workflows/ci.yml
    - .github/branch-protection.json
    - .planning/phases/28-eval-cost-observability-gate/deferred-items.md

key-decisions:
  - "ai-evals and ai-redteam-injection mirror the backend job's shape (working-directory backend, setup-python v6, pip install -e \".[dev]\"), not semgrep's container shape -- both need app.ai.* importable"
  - "ai-redteam-injection copies the backend job's Postgres/Redis services block AND its migration step verbatim (not just DB/Redis env vars) -- test_ai_budget_coverage.py's `client` fixture starts a real create_app()+lifespan against a real schema; verified the local getvul_test DB was stale (missing migrations 030-033) before this was caught"
  - "[Rule 3 - Blocking] Added a disposable, non-secret, hardcoded test-only Fernet key to ai-redteam-injection's env only -- test_ai_budget_coverage.py seeds a real Fernet-encrypted ANTHROPIC connector credential, and Settings.encryption_key's class-level default is a literal placeholder (not a valid Fernet key) with no .env anywhere on disk or in a fresh CI runner (confirmed via gh secret list/gh variable list against the real repo: only SEMGREP_APP_TOKEN exists)"
  - "The identical ENCRYPTION_KEY gap in the pre-existing backend job (affecting 5 other Phase 24-27 test files that also seed encrypted AI credentials) was logged to deferred-items.md, not fixed -- out of this plan's file/task scope, never yet exercised in real CI since local main is far ahead of origin/main"
  - "ai-live-eval-optin's referenced tests/evals/test_llm_judge_evals.py and redteam/promptfooconfig.yaml deliberately left non-existent (skip-no-op via the HAS_DEV_KEY-gated steps), not scaffolded -- per the plan's own explicit instruction"
  - "AIE-01/AIE-02/AIE-03 all marked [x] Complete in REQUIREMENTS.md -- this is the final contributing plan for all 3 (mirrors the AID-01/AIE-01 precedent of holding a multi-plan requirement open until CI wiring lands)"

requirements-completed: [AIE-01, AIE-02, AIE-03]

coverage:
  - id: D1
    description: "ai-evals CI job runs the keyless DeepEval golden-set harness (deepeval test run, not bare pytest) with telemetry opt-out, no ANTHROPIC_API_KEY, no continue-on-error"
    requirement: "AIE-01"
    verification:
      - kind: other
        ref: "cd backend && DEEPEVAL_TELEMETRY_OPT_OUT=1 deepeval test run tests/evals/test_golden_evals.py (exact CI command, run locally)"
        status: pass
      - kind: other
        ref: "python yaml-based acceptance-criteria script (deepeval test run present, steps non-empty, no continue-on-error, no ANTHROPIC_API_KEY)"
        status: pass
    human_judgment: false
  - id: D2
    description: "ai-redteam-injection CI job runs BOTH the consolidated red-team suite and the no-bypass budget coverage test together, backend-shaped with real Postgres/Redis + migrations, no ANTHROPIC_API_KEY, no continue-on-error"
    requirement: "AIE-02"
    verification:
      - kind: other
        ref: "cd backend && DATABASE_URL=... REDIS_URL=... JWT_SECRET_KEY=test-secret ENVIRONMENT=test ENCRYPTION_KEY=<test-key> pytest tests/test_ai_injection_redteam.py tests/test_ai_budget_coverage.py -v (exact CI command, run locally against migrated getvul_test DB) -- 96 passed"
        status: pass
      - kind: other
        ref: "python yaml-based acceptance-criteria script (both test file paths present in run:, Postgres/Redis services byte-identical to the backend job's own services block, no continue-on-error)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The fail-closed cost breaker's no-bypass coverage test (part of ai-redteam-injection) is genuinely wired into a blocking CI check, closing AIE-03's own 'enforced as a CI gate' wording"
    requirement: "AIE-03"
    verification:
      - kind: other
        ref: "same ai-redteam-injection local run (96 passed, includes all 11 test_ai_budget_coverage.py cases: 5 over-budget + 5 under-budget-regression-control + 1 batch-path)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The 2 new blocking job names are registered byte-for-byte in branch-protection.json's required_status_checks.checks[], making them genuinely merge-blocking (not merely CI-visible); the opt-in live tier is deliberately absent from that list"
    verification:
      - kind: other
        ref: "python json-based acceptance-criteria script asserting both context strings present + no 'opt-in' substring anywhere in checks[]"
        status: pass
    human_judgment: false
  - id: D5
    description: "ai-live-eval-optin is opt-in, key-gated (HAS_DEV_KEY env-indirection), non-blocking (continue-on-error: true), and never runs against untrusted fork PRs"
    verification:
      - kind: other
        ref: "python yaml-based acceptance-criteria script asserting continue-on-error is True, if: contains fork==false, and env.HAS_DEV_KEY derives from secrets.DEV_ANTHROPIC_API_KEY"
        status: pass
    human_judgment: true
    rationale: "The job's structural correctness (gating, fork-guard, non-blocking flag) is fully proven by direct YAML introspection. What is NOT provable from this sandbox: whether the job actually behaves correctly end-to-end when a real DEV_ANTHROPIC_API_KEY secret is later configured on GitHub (the referenced test_llm_judge_evals.py/redteam/promptfooconfig.yaml files don't exist yet, by design) -- that requires a human/future session to configure the secret, author those opt-in-tier files, and observe a real run."

# Metrics
duration: 19min
completed: 2026-08-03
status: complete
---

# Phase 28 Plan 05: Keyless AI Eval/Red-Team CI Gates — Genuinely Merge-Blocking Summary

**Wired 2 keyless DeepEval/pytest CI jobs into `ci.yml` and registered their names byte-for-byte in `branch-protection.json`'s `required_status_checks.checks[]` — closing the gap where a CI job alone (proven by the pre-existing, deliberately-non-required `docs` job) never actually blocks a merge on this repo; added a 3rd opt-in, key-gated, fork-guarded, non-blocking live-eval tier.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-08-03T09:28:36Z (continuity from Plan 04's completion)
- **Completed:** 2026-08-03T09:47:22Z
- **Tasks:** 1 (the plan's only task)
- **Files modified:** 3 (`.github/workflows/ci.yml`, `.github/branch-protection.json`, `deferred-items.md`)

## Accomplishments

- Added `ai-evals` ("AI Golden-Set Evals (DeepEval)") to `ci.yml`: backend-shaped, fully keyless, runs `deepeval test run tests/evals/test_golden_evals.py` with `DEEPEVAL_TELEMETRY_OPT_OUT=1`, no `continue-on-error`, no `ANTHROPIC_API_KEY` anywhere — verified green-by-construction locally (10/10 fixtures passed, exit 0)
- Added `ai-redteam-injection` ("AI Prompt-Injection Red-Team (static)") to `ci.yml`: backend-shaped with the `backend` job's Postgres/Redis services + migration step copied verbatim, runs BOTH `tests/test_ai_injection_redteam.py` and `tests/test_ai_budget_coverage.py` together, no `continue-on-error` — verified green-by-construction locally (96/96 tests passed: 85 injection-redteam + 11 budget-coverage)
- Added `ai-live-eval-optin` ("AI Live Eval + Red-Team (opt-in, non-blocking)") to `ci.yml`: `needs: [backend]`, `continue-on-error: true`, `HAS_DEV_KEY` env-indirection gate on `secrets.DEV_ANTHROPIC_API_KEY != ''` (avoids the documented secrets-in-`if:` gotcha), `if: github.event.repository.fork == false` so it never runs against untrusted fork PRs or exposes the dev key
- Registered `"AI Golden-Set Evals (DeepEval)"` and `"AI Prompt-Injection Red-Team (static)"` byte-for-byte in `.github/branch-protection.json`'s `required_status_checks.checks[]` — this is what actually makes them merge-blocking (a workflow job alone doesn't, per the existing `docs` job's own deliberately-non-required precedent); the opt-in job's name is deliberately absent
- Found and fixed one real Rule 3 blocking issue during local green-by-construction verification: `ai-redteam-injection`'s budget-coverage test seeds a real Fernet-encrypted ANTHROPIC connector credential via `encrypt_value()`, and `Settings.encryption_key`'s class-level default is a literal placeholder string, not a valid 32-byte url-safe base64 Fernet key — with no `.env` file present anywhere (confirmed absent + gitignored on disk, and confirmed via `gh secret list`/`gh variable list` against the real `Cyber-Solutions-MD/getvul` repo that only `SEMGREP_APP_TOKEN` exists). Fixed by adding one disposable, non-secret, hardcoded test-only Fernet key scoped to just this job's step env, mirroring the existing `JWT_SECRET_KEY: test-secret` convention
- Logged the identical, pre-existing `ENCRYPTION_KEY` gap in the unmodified `backend` job (affecting 5 other Phase 24-27 test files that also seed encrypted AI credentials — `test_ai_batch.py`, `test_ai_explain_remediation_guidance.py`, `test_ai_cache_isolation.py`, `test_ai_explain_stream.py`, `test_ai_status.py`) to `deferred-items.md` — out of this plan's narrow file scope to fix, but flagged as a real gap that will surface the next time `origin/main` actually runs the full backend suite in real CI

## Task Commits

1. **Task 1: Add 3 AI CI jobs + register the 2 blocking checks in branch-protection** - `7046135` (feat)

**Plan metadata:** (this commit) `docs(28-05): complete AIE-01/02/03 CI wiring plan`

_Note: This plan had exactly 1 task per its own frontmatter — no TDD, no multi-task decomposition needed for a CI-config-only change._

## Files Created/Modified

- `.github/workflows/ci.yml` - Added 3 new jobs (`ai-evals`, `ai-redteam-injection`, `ai-live-eval-optin`) sibling to `semgrep`, following the `backend`/`dast` job shapes exactly
- `.github/branch-protection.json` - Appended 2 new required-check entries matching the new blocking job names byte-for-byte
- `.planning/phases/28-eval-cost-observability-gate/deferred-items.md` - Logged the pre-existing `backend` job `ENCRYPTION_KEY` gap (unrelated to this plan's scope, not fixed)

## Decisions Made

See `key-decisions` in frontmatter. In summary: mirror the `backend` job's exact shape (not `semgrep`'s container shape) for both new blocking jobs since they need `app.ai.*` importable; copy the `backend` job's Postgres/Redis services + migration step verbatim for `ai-redteam-injection` since the budget-coverage test needs a real, migrated schema; add a disposable test-only Fernet key scoped to just the new job (Rule 3 fix) rather than touching the pre-existing `backend` job's identical latent gap (out of scope); leave the opt-in tier's referenced files as skip-no-op rather than scaffolding them, per the plan's own explicit instruction; mark AIE-01/02/03 all Complete in REQUIREMENTS.md as the final contributing plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ai-redteam-injection` needs `ENCRYPTION_KEY` to actually pass**
- **Found during:** Task 1, local green-by-construction verification of the exact CI command (per the critical_constraints instruction to run the exact keyless commands Wave-1 shipped)
- **Issue:** `backend/tests/test_ai_budget_coverage.py` (from Plan 02) seeds a real encrypted `ANTHROPIC` `ConnectorConfig` row via `encrypt_value()` → `Fernet(settings.encryption_key)`. Running with the exact env the existing `backend` job's own "Run tests" step declares (no `ENCRYPTION_KEY`) fails immediately with `ValueError: Fernet key must be 32 url-safe base64-encoded bytes.`, since `Settings.encryption_key`'s class-level default (`app/config.py:22`) is a literal placeholder string, and no `.env` file exists anywhere (confirmed absent on disk + gitignored; confirmed via `gh secret list`/`gh variable list` against the real GitHub repo that only `SEMGREP_APP_TOKEN` is configured).
- **Fix:** Added a disposable, non-secret, hardcoded test-only Fernet key (`ENCRYPTION_KEY: "9ynx6kK8mLb2ag-LhSCjA1L7oGWg873tk6dIQ45FBIA="`) to `ai-redteam-injection`'s test-running step env only, mirroring the existing `JWT_SECRET_KEY: test-secret` convention (a throwaway value scoped to the ephemeral per-run CI Postgres, zero production sensitivity).
- **Files modified:** `.github/workflows/ci.yml`
- **Verification:** Ran the exact command locally before and after: without the key, all 11 `test_ai_budget_coverage.py` cases failed with the Fernet `ValueError`; with the key, all 96 tests (85 injection-redteam + 11 budget-coverage) passed, exit 0.
- **Committed in:** `7046135` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for the new blocking CI job to actually be green-by-construction rather than failing on its very first real run. No scope creep — the fix is scoped entirely to the new job's own env block; the identical pre-existing gap in the unrelated `backend` job was explicitly NOT touched and instead logged to `deferred-items.md`.

## Issues Encountered

- The local `getvul_test` Postgres database (created by an earlier plan's executor session) was missing migrations 030–033 (columns like `connector_configs.last_error`), causing an initial `test_ai_budget_coverage.py` failure unrelated to the CI job's design. Resolved by running `alembic upgrade head` against it locally before re-verifying — this is exactly why the plan's own design (and this job) includes a "Run migrations" step before running tests, not a defect in the new job itself.
- `gh secret list`/`gh variable list` against the real `Cyber-Solutions-MD/getvul` repo confirmed no `DEV_ANTHROPIC_API_KEY` secret exists yet — this is expected and by design (the opt-in tier's whole point is to no-op cleanly until a developer configures their own key); not a blocker for this plan.

## User Setup Required

None - no external service configuration required for this plan. (Separately, and out of this plan's scope: a developer who later wants to exercise the `ai-live-eval-optin` tier will need to configure a `DEV_ANTHROPIC_API_KEY` repository secret and author `backend/tests/evals/test_llm_judge_evals.py` + `redteam/promptfooconfig.yaml` — both deliberately left unscaffolded per this plan's own instruction.)

## Next Phase Readiness

- **Phase 28 is now 5/5 plans complete.** AIE-01, AIE-02, AIE-03, and AIE-04 are all `[x]` Complete in `REQUIREMENTS.md`. This is the v3.0 AI-Assisted Triage milestone's closing phase (Phases 23–28) — the entire milestone is now fully executed at the plan level.
- **What is proven vs. not yet provable from this sandbox:** All of this plan's acceptance criteria are CONFIG-correctness assertions (valid YAML/JSON, exact job/step shapes, exact command invocations) — every one was verified via direct scripted assertion AND by running the exact commands locally against real Postgres/Redis, matching this codebase's own "the sweep is the arbiter" discipline. What is genuinely NOT provable without an actual push + PR cycle on GitHub: whether these 2 new required checks actually block a merge in practice on a real pull request. Per project memory (`getvul-origin-behind-local-main`), local `main` is ~400+ commits ahead of `origin/main`, and pushing is a separate, deliberate deployment decision outside this plan's scope — so this remains an honestly-flagged, not-yet-observed fact rather than a claimed one.
- Recommended next steps: `/gsd-verify-work 28` (phase verification), then likely `/gsd-complete-milestone` for v3.0 once Phase 28 (and the still-outstanding Phase 24 re-verification item, unrelated to this plan) are both clean.
- The pre-existing `backend` job's own `ENCRYPTION_KEY` gap (affecting 5 Phase 24-27 test files) is logged in `deferred-items.md` as a real, if currently dormant, risk for the next time this repo's CI actually runs against `origin/main`.

---
*Phase: 28-eval-cost-observability-gate*
*Completed: 2026-08-03*

## Self-Check: PASSED

- `[ -f .github/workflows/ci.yml ]` → FOUND
- `[ -f .github/branch-protection.json ]` → FOUND
- `[ -f .planning/phases/28-eval-cost-observability-gate/deferred-items.md ]` → FOUND
- `git log --oneline --all | grep -q 7046135` → FOUND (`7046135 feat(28-05): wire keyless AI eval/red-team CI gates as genuinely merge-blocking`)
- Re-ran all 5 plan-level acceptance criteria + the plan's own automated verify script: all PASS (see Task Commits / Accomplishments above for exact commands and results)
