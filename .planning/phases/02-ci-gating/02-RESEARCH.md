# Phase 2: CI Gating — Research

**Researched:** 2026-06-30
**Domain:** GitHub Actions workflow hardening, branch protection, type-checking backlog triage
**Confidence:** HIGH (all findings verified by running tools locally or against live GitHub API)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Uncomment and enable `push: branches: [main]` and `pull_request: branches: [main]`. Keep `workflow_dispatch`.
- **D-02:** Remove `|| true` from mypy (ci.yml:59), `npm run lint` (ci.yml:95), `npx tsc --noEmit` (ci.yml:97).
- **D-03:** Drive surfaced errors to zero — real fixes or narrow, commented ignores. No blanket suppressions.
- **D-04:** ZAP stays non-blocking. Keep `continue-on-error: true`. Keep artifact uploads.
- **D-05:** `dast` job must NOT run on `pull_request`. Gate with job-level `if:` (push-to-main + schedule only). Add nightly `schedule:` cron.
- **D-06:** ZAP not a required status check.
- **D-07:** Configure branch protection via `gh api`. Operator has admin (`viewerCanAdminister: true`). Document in `docs/13-deployment.md`.
- **D-08:** Required checks: `Backend`, `Frontend`, `Semgrep SAST`, `Terraform Validate`. Explicitly NOT required: `OWASP ZAP DAST`.
- **D-09:** Resolve terraform-required-but-skipped problem explicitly (path-filter + shim vs always-run).
- **D-10:** Document in `docs/13-deployment.md` (not `doc/deployment.md`). Add "CI Gating & Branch Protection" section.

### Claude's Discretion

- Exact `schedule:` cron time for the nightly DAST run
- Whether mypy/lint/tsc fixes land as one commit per tool or grouped
- The `terraform` skip/no-op mechanism (D-09 options a vs b) — pick the one that's robust on this repo's GitHub plan
- Job-level `if:` expression syntax for gating DAST off PRs

### Deferred Ideas (OUT OF SCOPE)

- Gate ZAP on a severity threshold (fail on High/Medium)
- Update-path reconciliation (cd.yml / install.sh cron race) — Phase 3
- New test authoring to raise coverage — Phase 8
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-02-01 | Re-enable ci.yml push + pull_request triggers | Triggers are commented out at lines 4–8; exact YAML to uncomment is in ci.yml |
| PROD-02-02 | Remove `\|\| true` from mypy (line 59), npm lint (line 95), tsc (line 97) | Backlog sized: 619 mypy errors, 0 lint errors (warnings only), 6 tsc errors |
| PROD-02-03 | ZAP policy: advisory (decided as non-blocking, nightly+push-to-main only) | DAST job-level `if:` expression and `schedule:` syntax researched |
| PROD-02-04 | Branch protection on `main` requires CI green, documented | `gh api` PUT endpoint verified; exact check name strings confirmed |
</phase_requirements>

---

## Summary

This phase re-arms an already-written CI workflow. The mechanical changes are small (uncomment 3 lines, remove 3 `|| true` tokens, add one `if:` on the dast job, and one `gh api` call). The bulk of the work is the backlog that the masks have been hiding: **619 mypy errors across 76 files** in the backend.

The frontend is in much better shape. ESLint exits 0 (4 warnings, no errors). TypeScript has exactly **6 errors, all in two test files** (`tickets/page.test.tsx` and `tickets/rules/page.test.tsx`), all the same root cause: TanStack Query v5 tightened `UseQueryResult` mock casting in tests.

The mypy backlog is the phase-shaping finding. Of 619 errors: ~442 are annotation gaps (`type-arg`, `no-untyped-def`, `no-untyped-call`, `import-untyped`) — these are mechanical to fix but numerous. ~149 are real type bugs (`assignment`, `arg-type`, `attr-defined`, etc.) requiring logic inspection. The volume warrants splitting into at least two waves: Wave A (triggers + frontend tsc + branch protection structure) and Wave B+ (mypy fix-and-verify iterations).

**Primary recommendation:** Plan 02-01 handles triggers, frontend fixes, ZAP policy, and branch protection skeleton. Plans 02-02 and 02-03 systematically fix the mypy backlog by module group, with CI unblocked progressively using narrowly-scoped per-file `# type: ignore[code]` only where warranted. The gate opens when all four required jobs pass clean.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Workflow triggers | CI (GitHub Actions) | — | ci.yml `on:` block; no app-tier involvement |
| Failure masks removal | CI (GitHub Actions) | Backend/Frontend code | The masks hide errors in app code — both layers need changes |
| ZAP scheduling + gating | CI (GitHub Actions) | — | `schedule:` and `if:` in ci.yml; no app change |
| Branch protection | GitHub repo settings | CI check names | `gh api` writes repo policy; policy references job `name:` fields |
| mypy error fixes | Backend (app/) | CI (no mask) | 619 errors in backend source; CI just surfaces them |
| tsc error fixes | Frontend (test files) | CI (no mask) | 6 errors in `*.test.tsx`; CI surfaces them |
| Documentation | docs/ | — | `docs/13-deployment.md` and `docs/12-pipelines-cicd.md` |

---

## Critical Research Finding 1: The Backlog (PROD-02-02)

This is the highest-priority planning input. The masks have hidden a substantial backend backlog.

### Backend — mypy (619 errors, 76 files)

**Tool:** `.venv/bin/mypy app/` with `strict = true` in `pyproject.toml`
**Version confirmed:** mypy 2.1.0 (in `.venv`); pyproject requires `>=1.13`

**Important note on mypy 2.x:** The venv has mypy 2.1.0. CI installs `mypy>=1.13` from `pyproject.toml`. The first CI run after removing the mask may resolve a different version. mypy 2.x enforces stricter type narrowing than 1.x. The error count may shift slightly between versions; the categories below are directionally accurate. [VERIFIED: ran `.venv/bin/mypy app/` locally]

**Error breakdown by type:**

| Category | Code | Count | Fix Difficulty |
|----------|------|-------|----------------|
| Missing generic type args | `[type-arg]` | 251 | Low — add `[Any]` or specific type args (e.g., `dict[str, Any]`) |
| Missing function annotations | `[no-untyped-def]` | 175 | Low-Medium — add `-> ReturnType` and param types to FastAPI route handlers |
| SQLAlchemy `Result[Any].rowcount` | `[attr-defined]` | 19 | Medium — SQLAlchemy 2.x `CursorResult.rowcount` exists but `Result[Any]` generic does not expose it; requires `.rowcount` to be accessed on the concrete `CursorResult` not `Result` |
| Other `attr-defined` bugs | `[attr-defined]` | 21 | Medium — includes `NormalizedVulnerability` missing attributes (real schema drift), `"str" has no attribute "isoformat"` (real bugs) |
| Incompatible type assignments | `[assignment]` | 40 | Medium — includes CORS config assigning `list[str]` to `str` typed field in `app/main.py`, SQLAlchemy column assignment type drift |
| Incompatible argument types | `[arg-type]` | 29 | Medium — includes `UUID` vs `str`, `Sequence` vs `list`, real API surface issues |
| Missing return type annotations | `[no-any-return]` | 21 | Low — add explicit cast or proper return type |
| Missing required call args | `[call-arg]` | 15 | Medium — e.g., `AssetSummary`/`AssetResponse` constructors missing new fields added in v2.0 (mdm_details, os_version etc.) |
| Untyped function calls | `[no-untyped-call]` | 12 | Low — install stubs or add `# type: ignore[no-untyped-call]` with comment |
| None-union attribute access | `[union-attr]` | 11 | Medium — `AsyncClient \| None` accessed without None-check; real null-safety bugs |
| Operator errors | `[operator]` | 6 | Medium — type mismatch on `+`, `-` operators |
| Missing type annotations | `[var-annotated]` | 5 | Low — add annotation |
| Undefined names | `[name-defined]` | 4 | Medium — forward reference issues (`Asset`, `Vulnerability` names not defined at annotation time) |
| Missing stubs | `[import-untyped]` | 4 | Low — install `types-python-jose` (`python3 -m pip install types-python-jose`) |
| Method signature incompatibility | `[override]` | 2 | Medium — `BaseConnector.authenticate` signature differs from Wiz/Jamf subclasses |

**Errors by module (top clusters):**

| Module | Errors | Notes |
|--------|--------|-------|
| `app/connectors/` | 165 | All connector implementations; heavy on `type-arg` + real bugs |
| `app/vulnerabilities/` | 95 | Mostly `type-arg` + `rowcount` pattern |
| `app/ticketing/` | 91 | Mix of `type-arg`, `no-untyped-def`, real bugs |
| `app/assets/` | 62 | Includes `call-arg` (missing new fields in schema constructors) |
| `app/auth/` | 47 | `no-untyped-def` (router functions), `import-untyped` (jose) |
| `app/tenants/` | 30 | Mostly `type-arg`, `no-untyped-def` |
| `app/cspm/` | 26 | `rowcount` + `type-arg` |
| Other modules | ~103 | `app/main.py` (21), `app/export.py` (16), `app/reports.py` (12), etc. |

**Special note — `app/main.py` CORS config (lines 238-252):**
`app/main.py` assigns `list[str]` and `bool` to a variable typed as `str` — likely a starlette CORS middleware dict being built with `str`-typed variable stubs. This is a real type error and needs inspection. [VERIFIED: mypy output]

**Annotation-gap vs real-bug split:**
- ~442 errors (71%) are annotation gaps: no code logic changes needed, just add type annotations or generic args.
- ~149 errors (24%) are real type bugs: require inspecting logic, fixing mismatched types, or adding null-guards.
- ~28 errors (4%) are no_any_return / no-untyped-call / import-untyped: install stubs or add targeted ignores.

**Planning implication:** At ~2-3 minutes per file and 76 files, this is 2–4 days of focused work depending on bug depth. The mypy backlog should be split across 2–3 plans by module cluster, not shoved into one giant commit.

### Frontend — ESLint (0 errors)

ESLint exits 0. There are 4 warnings (`react-hooks/exhaustive-deps` and `jsx-a11y/no-autofocus`) but these do not fail the workflow. Removing the `|| true` from `npm run lint` will have no effect on green/red status — it will still pass immediately. [VERIFIED: ran `npm run lint` locally, exit code 0]

### Frontend — TypeScript tsc (6 errors, 2 test files)

All 6 errors are in test files. Root cause: TanStack Query v5 tightened `UseQueryResult<T, E>` — mock objects cast with `as UseQueryResult<...>` now fail because `UseQueryResult` is a discriminated union of `QueryObserver*Result` variants, each requiring 20+ properties (isError, isLoadingError, isRefetchError, isSuccess, etc.) not present in the minimal mock objects.

**Files affected:**
- `src/app/(authed)/dashboard/tickets/page.test.tsx` (lines 61, 90, 105, 128) — 4 errors
- `src/app/(authed)/dashboard/tickets/rules/page.test.tsx` (lines 69, 122) — 2 errors

**Fix pattern (two options):**
1. Cast through `unknown`: `as unknown as UseQueryResult<T, E>` — works but is a broader escape hatch.
2. Build a helper factory: `mockQuery<T>(partial)` that merges partial props with a complete `QueryObserverSuccessResult` base object. Cleaner but requires defining ~20 required properties.

Option 1 is the narrow, targeted fix appropriate for this phase (D-03: narrow ignores are acceptable when clean fix is out of scope). Option 2 is the right long-term pattern (Phase 8 coverage work).

**Planning implication:** Frontend tsc fixes are a 30-minute task. Can land in Plan 02-01 alongside trigger re-enablement.

---

## Critical Research Finding 2: GitHub Branch Protection — Exact Mechanics

### Rulesets vs Legacy Branch Protection

Both APIs are available for this public repo (public repos on GitHub Free support both). [VERIFIED: `gh api repos/Cyber-Solutions-MD/getvul/rulesets` returns `[]` — no rulesets exist; `gh api repos/Cyber-Solutions-MD/getvul/branches/main/protection` returns 404 "Branch not protected"]

**Recommendation: use the legacy branch protection API** (`PUT /repos/{owner}/{repo}/branches/{branch}/protection`).

Rationale:
- The operator asked for a reproducible `gh api` command (D-07) — the legacy API is a single PUT call, easier to reason about and document.
- Rulesets offer more layering but add complexity for a single-branch, single-repo use case.
- The legacy API has been stable since GitHub Free was established and is not being removed.
- If migrating to rulesets later (Phase N+), it's additive, not destructive.

### Exact `gh api` Command

```bash
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  repos/Cyber-Solutions-MD/getvul/branches/main/protection \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": false,
    "checks": [
      { "context": "Backend",          "app_id": -1 },
      { "context": "Frontend",         "app_id": -1 },
      { "context": "Semgrep SAST",     "app_id": -1 },
      { "context": "Terraform Validate", "app_id": -1 }
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false,
    "require_last_push_approval": false
  },
  "restrictions": null
}
EOF
```

**Field notes:**
- `app_id: -1` — permits any GitHub App (including the native Actions app) to satisfy the check. Do not use a specific app ID; the Actions check reporter varies. [CITED: GitHub REST API docs for branch protection]
- `strict: false` — "require branch to be up to date before merging" is NOT needed for this phase. `strict: true` would require every PR to rebase before merge, which is operationally heavy for a solo-operator repo.
- `required_approving_review_count: 0` — the CONTEXT only requires CI green + PR-before-merge, not a code review approver. Setting count to 0 satisfies the "require PR before merging" requirement: a PR must be created, but no approvals are needed. [ASSUMED: this is the minimum-friction interpretation of D-07; verify with operator if explicit approval count is desired]
- `enforce_admins: false` — allows the admin account to push directly if truly needed. Set to `true` for harder enforcement. [ASSUMED: false is correct for a single-operator repo; adjust if policy differs]
- `restrictions: null` — no push restriction needed.

### How Required Check Names Map to Job `name:` Fields

The check name registered in branch protection MUST match the `name:` field of the workflow job as it appears in GitHub's check suite, not the job key.

From `ci.yml` (verified by inspecting a live workflow run `23743367028`):

| Job key | `name:` field | Check name to register |
|---------|--------------|----------------------|
| `backend` | `Backend` | `Backend` |
| `frontend` | `Frontend` | `Frontend` |
| `terraform` | `Terraform Validate` | `Terraform Validate` |
| `semgrep` | `Semgrep SAST` | `Semgrep SAST` |
| `dast` | `OWASP ZAP DAST` | NOT registered (advisory) |

[VERIFIED: `gh run view 23743367028` shows `Frontend`, `Backend`, `Semgrep SAST`, `Terraform Validate`, `OWASP ZAP DAST` as job display names]

**Important:** Required check strings are case-sensitive and space-sensitive. The strings above must match exactly.

**First-run bootstrap requirement:** Required checks must have been reported at least once before they appear in the branch protection autocomplete dropdown in the GitHub UI. Since CI has only run on `workflow_dispatch` (not on PRs), the check names may be unknown to the protection API's check registry until the first triggered run. The `app_id: -1` approach in the `gh api` call bypasses this requirement — it registers the check by name regardless of prior history. [CITED: GitHub REST API docs for `required_status_checks.checks`]

---

## Critical Research Finding 3: The Terraform Required-but-Skipped Problem

### Current situation

The `terraform` job in `ci.yml` has **no path filter** — it runs on every workflow trigger regardless of what changed. When we add `push/pull_request` triggers, `terraform` will run on every PR. At ~7 seconds, this is fast and cheap.

**Decision: keep terraform always-running (no path filter).**

Rationale:
- Adding a `paths:` filter to terraform would create the "required check never triggered" deadlock: GitHub workflow-level path filtering causes the workflow to be skipped entirely, which leaves required checks in "Pending" state forever, blocking the PR indefinitely. [VERIFIED: GitHub Docs — "if a workflow is skipped due to path filtering, checks will remain Pending"]
- Job-level `if:` conditions (not workflow-level path filters) report "skipped" which GitHub treats as "passing" for required check purposes. But this means the check would pass without running, defeating the purpose.
- Terraform runs in 7 seconds (`fmt -check`, `init -backend=false`, `validate`). There is no performance reason to filter.
- `infra/` changes infrequently but the check enforces that it stays valid — running it always is the correct policy.

**Conclusion for D-09:** Choose option (a) — keep terraform always-running on all PRs. No path filter, no shim needed.

---

## Critical Research Finding 4: DAST Advisory Scheduling — Exact YAML

### Schedule trigger for nightly DAST

Add to the `on:` block:

```yaml
on:
  workflow_dispatch:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 3 * * *'   # 03:00 UTC nightly
```

The cron time `0 3 * * *` (03:00 UTC) is Claude's discretion per the CONTEXT. 03:00 UTC is off-peak for most US timezones and avoids overlapping with typical PR activity windows.

### Job-level `if:` to skip DAST on pull_request events

```yaml
  dast:
    name: OWASP ZAP DAST
    runs-on: ubuntu-latest
    needs: [backend, frontend]
    if: github.event_name != 'pull_request'
```

**Why this is safe for branch protection:** A job with an `if:` that evaluates to false is reported as "Skipped" to GitHub's check suite. Per GitHub documentation, a required check that reports "Skipped" counts as passing for merge purposes. Since `OWASP ZAP DAST` is explicitly NOT in the required checks list (D-06/D-08), this is doubly safe — the dast job is neither required nor blocking. [CITED: GitHub Actions "Using conditions to control job execution" docs]

**Full expression options (all equivalent, choose most readable):**
- `if: github.event_name != 'pull_request'` — runs on push + schedule + workflow_dispatch
- `if: github.event_name == 'push' || github.event_name == 'schedule'` — explicit allowlist (excludes workflow_dispatch; probably not desired)
- Recommended: `if: github.event_name != 'pull_request'` — simplest, also preserves manual dispatch testing of DAST

---

## Critical Research Finding 5: Redis in CI — Backend Integration Tests

**The question:** Phase 1 added Redis integration tests. Will CI's backend job actually run them now that the trigger is live?

**Answer: Yes — Redis is already a service in the `backend` job.** [VERIFIED: ci.yml lines 18-40]

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ...
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 5s
      --health-timeout 3s
      --health-retries 5
```

The backend job passes `REDIS_URL: redis://localhost:6379/0` to the `pytest` step. The Phase 1 integration tests will run in CI with no infra changes needed.

**No action required on this front.** This is good news — the concern raised in the additional context is already resolved by the existing ci.yml.

---

## Additional Finding: ZAP Action Versions (Node 20 Deprecation)

The CI run annotations showed: `zaproxy/action-api-scan@v0.9.0` and `zaproxy/action-baseline@v0.14.0` use Node 20, which GitHub is deprecating (forced Node 24 default from June 2, 2026; Node 20 removed September 16, 2026).

Newer versions are available: [VERIFIED: GitHub API]
- `zaproxy/action-api-scan` latest: `v0.10.0` (published 2025-10-24)
- `zaproxy/action-baseline` latest: `v0.15.0` (published 2025-10-24)

**Recommendation:** Update ZAP action pins as part of Plan 02-01 while touching the dast job for the `if:` condition. This is a 2-line change in the same block. Not a PROD-02 requirement but avoids future CI warnings that may become errors.

---

## Recommended Plan Structure

Based on the backlog sizing, this phase requires **3 plans** (not the 2 suggested in the ROADMAP):

### Plan 02-01 — Triggers, Frontend, ZAP policy, Branch Protection skeleton
**Scope:**
- Re-enable `push` + `pull_request` triggers (PROD-02-01)
- Remove `|| true` from `npm run lint` and `npx tsc --noEmit` (PROD-02-02 partial)
- Fix the 6 frontend tsc errors in ticket test files
- Add `schedule:` cron and `if: github.event_name != 'pull_request'` to dast job + update ZAP action pins (PROD-02-03)
- Run `gh api` branch protection command (PROD-02-04 partial — skeleton with required checks registered)
- Update `docs/13-deployment.md` and `docs/12-pipelines-cicd.md` (D-10)
- **Keep `mypy app/ || true` in place** until backlog is fixed; remove it in Plan 02-03

**Rationale:** This plan can pass CI immediately (frontend is green, backend pytest passes, terraform is clean). It makes CI real but avoids a red-on-merge state.

### Plan 02-02 — mypy Wave 1: annotation gaps (modules: connectors, vulnerabilities, ticketing)
**Scope:**
- Fix `[type-arg]`, `[no-untyped-def]`, `[import-untyped]` errors in the top-3 error clusters
- `app/connectors/` (~165 errors), `app/vulnerabilities/` (~95 errors), `app/ticketing/` (~91 errors)
- Install `types-python-jose` stub (4 errors across auth/*)
- Target: reduce from 619 to ~200 errors

**Rationale:** These are mechanical annotation additions. High volume but low cognitive risk.

### Plan 02-03 — mypy Wave 2: real bugs + final mask removal (remaining modules)
**Scope:**
- Fix real type bugs: `[assignment]`, `[attr-defined]`, `[arg-type]`, `[call-arg]`, `[union-attr]` in remaining modules
- `app/assets/` (62), `app/auth/` (47), `app/tenants/` (30), `app/cspm/` (26), `app/main.py`, `app/export.py`, `app/reports.py`, etc.
- Address `rowcount` pattern (19 errors) — use `CursorResult` cast or `# type: ignore[attr-defined]` with comment
- Remove `mypy app/ || true` (PROD-02-02 final)
- Verify CI passes with all four required checks green
- Phase gate: all PROD-02-01 through PROD-02-04 verified

---

## Standard Stack

### Tools in use

| Tool | Version (verified) | Purpose |
|------|--------------------|---------|
| mypy | `>=1.13` (pin in pyproject.toml); `2.1.0` in local venv | Backend type checking |
| ruff | `>=0.8` | Backend lint + format (already unmasked, passes clean) |
| ESLint (next lint) | Next.js built-in | Frontend lint (already passes, 0 errors) |
| TypeScript tsc | Per tsconfig.json | Frontend type check |
| `gh` CLI | `2.95.0` (verified) | Branch protection configuration |
| GitHub Actions | — | CI orchestration |
| ZAP actions | `action-api-scan@v0.10.0`, `action-baseline@v0.15.0` (recommended upgrade) | DAST |

### Key mypy configuration facts

```toml
[tool.mypy]
python_version = "3.12"
plugins = ["pydantic.mypy"]
strict = true
```

`strict = true` enables all strictness flags including `--disallow-any-generics` (causes `[type-arg]`), `--disallow-untyped-defs` (causes `[no-untyped-def]`), `--warn-return-any` (causes `[no-any-return]`), etc.

**Do not change the mypy config to relax `strict = true`.** Per D-03, fix the violations. Relaxing strict would defeat the gate's purpose and is explicitly excluded by "no blanket suppressions."

---

## Architecture Patterns

### ci.yml Trigger Block (after Phase 2)

```yaml
on:
  workflow_dispatch:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 3 * * *'   # nightly DAST sweep
```

### DAST Job Condition

```yaml
  dast:
    name: OWASP ZAP DAST
    runs-on: ubuntu-latest
    needs: [backend, frontend]
    if: github.event_name != 'pull_request'
    steps:
      ...
      - name: ZAP API Scan (OpenAPI)
        uses: zaproxy/action-api-scan@v0.10.0
        ...
        continue-on-error: true
      - name: ZAP Baseline Scan (Backend)
        uses: zaproxy/action-baseline@v0.15.0
        ...
        continue-on-error: true
      - name: ZAP Baseline Scan (Frontend)
        uses: zaproxy/action-baseline@v0.15.0
        ...
        continue-on-error: true
```

### mypy Acceptable Narrow Ignore Pattern (D-03)

```python
# type: ignore[attr-defined]  # SQLAlchemy Result[T].rowcount — CursorResult has it; async Result[Any] does not
result.rowcount  # type: ignore[attr-defined]
```

Targeted ignores must:
1. Use the specific error code (e.g. `[attr-defined]`, not `# type: ignore` with no code)
2. Include an inline comment explaining why it's acceptable
3. Not appear in a blanket at the module or file level

### Frontend tsc Fix Pattern

```typescript
// Option A (quick fix for this phase):
vi.spyOn(useTicketsModule, 'useTickets').mockReturnValue(
  { data: { items: [...], ... }, isPending: false, ... } as unknown as UseQueryResult<TicketsResponse, Error>
);

// Option B (proper fix for Phase 8):
function mockQueryResult<T>(overrides: Partial<UseQueryResult<T, Error>>): UseQueryResult<T, Error> {
  return { isError: false, isLoadingError: false, isRefetchError: false, isSuccess: true,
           isPending: false, isLoading: false, isStale: false, isPlaceholderData: false,
           isFetching: false, isFetchedAfterMount: false, isFetched: true, isRefetching: false,
           isInitialLoading: false, status: 'success', fetchStatus: 'idle', failureCount: 0,
           failureReason: null, errorUpdateCount: 0, dataUpdatedAt: 0, errorUpdatedAt: 0,
           refetch: vi.fn(), error: null, data: undefined as unknown as T,
           ...overrides } as UseQueryResult<T, Error>;
}
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Branch protection | Custom webhook enforcement | `gh api PUT .../protection` | Native GitHub API; reproducible; one command |
| Type stub installation | Vendoring type definitions | `pip install types-python-jose` | Official stub packages maintained by typeshed contributors |
| DAST scheduling | Separate cron VM | GitHub Actions `schedule:` trigger | Already in ci.yml ecosystem; no extra infra |
| mypy ignore management | Disabling `strict = true` globally | Targeted `# type: ignore[code]` with comment | Preserves gate value; blanket relaxation is a silent regression |

---

## Common Pitfalls

### Pitfall 1: Check Name Mismatch in Branch Protection

**What goes wrong:** You register `backend` (lowercase, the job key) instead of `Backend` (the `name:` field). The required check never matches the reported check. PRs appear as "waiting for status" indefinitely even when the job passes.

**Why it happens:** The GitHub UI and API both use the `name:` display field, not the workflow job key. The job key (`backend`) is what you see in YAML; the check name (`Backend`) is what gets reported to the check suite.

**How to avoid:** Register `Backend`, `Frontend`, `Semgrep SAST`, `Terraform Validate` (exact strings, case-sensitive) as shown in the `gh api` command above.

**Warning signs:** After adding branch protection, a passing CI run does not unblock a PR's merge button.

### Pitfall 2: Removing All Three `|| true` in One Commit Before Fixing Errors

**What goes wrong:** Remove all masks, push. CI immediately turns red on `main`. No PR can merge. This breaks the CI gate before it's useful.

**How to avoid:** Plan 02-01 removes `|| true` only from the two frontend steps (which already pass). The `mypy || true` mask stays until the mypy backlog is fixed (Plans 02-02 and 02-03). Remove the mypy mask only in the final plan that zeros the error count.

### Pitfall 3: Workflow-Level Path Filter on Terraform Causes Permanent Block

**What goes wrong:** You add `paths: ['infra/**']` to the `push/pull_request` triggers (or as a job-level paths filter). A frontend-only PR skips the terraform workflow entirely. GitHub reports the required check `Terraform Validate` as "Pending". The PR can never merge.

**Why it happens:** Workflow-level `paths:` filter causes the workflow to not run at all — GitHub sees the check as "never reported" rather than "passed". This is different from a job-level `if:` which reports "Skipped" (treated as passing).

**How to avoid:** Do not add path filters to the `terraform` job. It runs in 7 seconds, always. This is the chosen approach for D-09.

### Pitfall 4: `app_id: -1` vs Omitting `app_id`

**What goes wrong:** Using the `contexts` array (legacy) instead of `checks` + `app_id: -1` can result in the API accepting the request but not registering the check correctly with the GitHub Actions runner app.

**How to avoid:** Use the `checks` array format with `app_id: -1` as shown in the command above. The value `-1` explicitly means "any app can satisfy this check." [CITED: GitHub REST API docs for `required_status_checks`]

### Pitfall 5: `strict: true` in Required Status Checks

**What goes wrong:** Setting `strict: true` in `required_status_checks` requires every PR branch to be up to date with `main` before merging. On a solo-operator repo with no CI history, this creates friction on the first PR (must rebase before merge button appears).

**How to avoid:** Use `strict: false` (default). Enable `strict: true` only if branch drift protection is explicitly desired.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `required_approving_review_count: 0` satisfies "require PR before merging" without requiring actual approvals | Branch Protection Command | If GitHub requires count ≥ 1 to enable the PR requirement, the operator must set count to 1 and approve their own PRs (not possible), or disable `required_pull_request_reviews` entirely |
| A2 | `enforce_admins: false` is appropriate for this solo-operator repo | Branch Protection Command | If operator wants to prevent accidental force-pushes from admin account, should set to `true` |
| A3 | mypy 2.1.0 (venv) produces the same error categories as the mypy version CI will install | Backlog Sizing | Minor count variance possible; categories will be the same |

---

## Open Questions

1. **Does the operator want `enforce_admins: true` or `false`?**
   - What we know: `enforce_admins: false` allows admin to bypass; `true` enforces on all including admins.
   - What's unclear: Operator preference.
   - Recommendation: Default to `false` in the plan; document the option explicitly in the deployment docs.

2. **mypy version pinning in CI**
   - What we know: `pyproject.toml` specifies `mypy>=1.13`; the venv has `2.1.0`. CI will resolve the latest >=1.13 version.
   - What's unclear: Whether to pin `mypy==2.1.*` in pyproject.toml for reproducibility.
   - Recommendation: Pin to `mypy==2.1.*` in the CI/dev dependencies after verifying the backlog fix against 2.1.0.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `gh` CLI | Branch protection via `gh api` | ✓ | 2.95.0 | — |
| Backend `.venv` with mypy | Running mypy locally to verify fixes | ✓ | mypy 2.1.0 | `pip install -e ".[dev]"` in a fresh venv |
| `types-python-jose` stub | Fixing `[import-untyped]` for jose | ✗ (not in venv) | — | `pip install types-python-jose` (add to `[dev]` deps in pyproject.toml) |
| GitHub repo admin access | `gh api PUT .../protection` | ✓ | authenticated as `chemencedji` | — |
| Node 20 / npm | Frontend tsc/lint runs | ✓ | per CI config | — |
| Redis service | Backend CI job integration tests | ✓ (in ci.yml already) | redis:7-alpine | — |

**Missing dependencies with no fallback:**
- None.

**Missing dependencies with fallback:**
- `types-python-jose`: must be added to `pyproject.toml [project.optional-dependencies] dev` and installed. One-line change.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend unit/integration | pytest + pytest-cov (already configured, ci.yml line 70) |
| Frontend unit | vitest (vitest.config.mts) |
| CI gate test | Live `gh api` call + PR attempt with deliberate failure |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-02-01 | CI runs on push and PR triggers | Smoke (live CI run) | `git push` to a test branch + check `gh run list` | ✅ (ci.yml exists) |
| PROD-02-02 | mypy/lint/tsc failures block CI | Smoke (deliberate error) | Introduce a type error, push, verify CI fails | ✅ (via CI) |
| PROD-02-03 | DAST runs on push+schedule, skips on PR | Inspection | `gh run view <run-id>` — dast job absent on PR run | ✅ (via CI) |
| PROD-02-04 | Branch protection blocks bad merge | Integration (live PR) | Open PR with failing tsc; verify merge button blocked | ✅ (via gh API) |

### Success Criterion Verification Commands

```bash
# SC1: CI runs on push/PR
gh run list --repo Cyber-Solutions-MD/getvul --limit 5
# Expect: runs triggered by push and pull_request events (not just workflow_dispatch)

# SC2: mypy blocks on type errors
# In a branch, add: x: int = "oops"  to any backend file
# Push and verify: gh run view <run-id> -- backend job = failure

# SC3: Lint/tsc block on frontend errors
# In a branch, change a test mock cast to trigger tsc error
# Push and verify: gh run view <run-id> -- frontend job = failure

# SC4: ZAP policy in place
# Merge a PR; verify in gh run list that a push-to-main run exists with dast job present
# On the PR run itself, dast job should be absent

# SC5: Branch protection
gh api repos/Cyber-Solutions-MD/getvul/branches/main/protection \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    checks = d['required_status_checks']['checks']; \
    print([c['context'] for c in checks])"
# Expect: ['Backend', 'Frontend', 'Semgrep SAST', 'Terraform Validate']
```

### Wave 0 Gaps

None — no new test files need to be created. All verification is through live CI runs and the `gh api` calls above.

---

## Security Domain

This phase is CI/workflow infrastructure. ASVS categories do not directly apply. The security value of this phase is enforcement (CI gate prevents merging broken code) rather than application-level security controls.

| ASVS Category | Applies | Note |
|---------------|---------|------|
| V1 Architecture | Tangentially | Branch protection enforces that untested code cannot reach production |
| V5 Input Validation | No | Not applicable to CI config changes |
| V14 Configuration | Yes (low) | CI workflow files are security-relevant configuration; ensuring they are gated protects the pipeline integrity |

---

## Sources

### Primary (HIGH confidence — verified by tool execution)
- Local execution of `.venv/bin/mypy app/` — 619 errors, exit code 1
- Local execution of `npm run lint` — exit code 0 (warnings only)
- Local execution of `npx tsc --noEmit` — 6 errors, exit code 2
- `gh api repos/Cyber-Solutions-MD/getvul/branches/main/protection` — 404 (not protected)
- `gh api repos/Cyber-Solutions-MD/getvul/rulesets` — `[]` (no rulesets)
- `gh run view 23743367028` — confirmed job display names: Backend, Frontend, Semgrep SAST, Terraform Validate, OWASP ZAP DAST
- `gh api repos/zaproxy/action-api-scan/releases/latest` — v0.10.0 (2025-10-24)
- `gh api repos/zaproxy/action-baseline/releases/latest` — v0.15.0 (2025-10-24)

### Secondary (MEDIUM confidence — official docs)
- GitHub REST API docs: `PUT /repos/{owner}/{repo}/branches/{branch}/protection` schema — `required_status_checks.checks` array with `context` + `app_id: -1` [CITED: docs.github.com/en/rest/branches/branch-protection]
- GitHub Docs on skipped jobs: "a job that is skipped due to an `if:` condition reports Skipped, which counts as passing for required check purposes" [CITED: docs.github.com/en/actions/using-workflows/events-that-trigger-workflows]
- GitHub Docs on path filter behavior: "if a workflow is skipped due to path filtering, checks remain Pending and block PRs" [CITED: docs.github.com/en/pull-requests/collaborating-with-pull-requests/troubleshooting-required-status-checks]

---

## Metadata

**Confidence breakdown:**
- Backlog sizing (mypy/tsc/lint): HIGH — verified by running the tools locally
- Branch protection mechanics: HIGH — verified against live repo + official docs
- DAST YAML syntax: HIGH — documented pattern from GitHub Actions docs
- Plan structure recommendation: MEDIUM — based on error count estimate; actual fix time depends on complexity of real bugs

**Research date:** 2026-06-30
**Valid until:** 2026-07-30 (branch protection API is stable; mypy error count is live state of repo)
