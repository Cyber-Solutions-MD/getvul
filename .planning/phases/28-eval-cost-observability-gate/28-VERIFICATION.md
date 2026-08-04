---
phase: 28-eval-cost-observability-gate
verified: 2026-08-03T13:10:00Z
status: passed
canonicalized: 2026-08-04T08:53:23Z
canonicalized_note: "human_needed → passed via /gsd-verify-work 28 UAT. Item 1 (pane visual/a11y) satisfied live (axe WCAG 2.1 AA clean both themes, G-28-1 fixed). Item 5 (golden-fixture provenance) decided: accept hand-authored fallback. Items 2/3/4 require external infra (GitHub secret+CI, synced-origin PR, live BYOK key) unprovisionable in this environment — user-waived 2026-08-04 as accepted overrides. No code defects."
score: 13/14 must-haves verified (1 partial accepted via override — see Gaps Summary)
overrides_applied: 4
overrides:
  - must_have: "Golden fixtures are seeded from REAL Phase 24-27 model outputs"
    reason: "GETVUL_DEV_ANTHROPIC_KEY absent in this environment (pre-existing since Phase 24-01); hand-authored fixtures pass the identical production validation gates (model_validate_json + recheck_business_rules) a real capture would, and capture_ai_goldens.py is built + documented to regenerate them the moment a key is available. Independently proven: a corrupted fixture fails NoRankInvariantMetric/GroundingTraceabilityMetric exactly as a real bad capture would, so the gate's discriminating power is fixture-provenance-independent."
    accepted_by: "Igor Chemencedji"
    accepted_at: "2026-08-04T08:53:23Z"
  - human_verification_item: "human-verification-item-2"
    test: "Opt-in key-gated live CI tier (ai-live-eval-optin) — real run"
    reason: "Requires a real DEV_ANTHROPIC_API_KEY repo secret + live GitHub Actions run + the intentionally-unscaffolded test_llm_judge_evals.py / promptfooconfig.yaml. Structural YAML correctness (key-gating, fork-guard, continue-on-error non-blocking) proven from source in 28-VERIFICATION.md. Cannot be observed in this environment; not a code defect."
    accepted_by: "Igor Chemencedji"
    accepted_at: "2026-08-04T08:53:23Z"
  - human_verification_item: "human-verification-item-3"
    test: "Merge-blocking observed on a real GitHub PR"
    reason: "Requires a real PR against a synced origin; local main is ~400+ commits ahead of origin/main (project memory getvul-origin-behind-local-main), so a PR would be unmergeable. branch-protection.json verified byte-correct vs ci.yml job names; the repo's own non-required-docs-job precedent proves the merge-block mechanism. Cannot be observed here; not a code defect."
    accepted_by: "Igor Chemencedji"
    accepted_at: "2026-08-04T08:53:23Z"
  - human_verification_item: "human-verification-item-4"
    test: "Live budget-exceeded degradation end-to-end"
    reason: "Requires a live Anthropic BYOK key spending real inference to trip the fail-closed breaker across the running stack (BYOK absent since Phase 24-01). Guard-before-dispatch ordering (explain.py:308 before :339), batch-path gating (batch.py), frontend budget_exceeded handling, and the non-tautological no-bypass coverage test (11/11, with under-budget falsifiability control) were all confirmed in isolation. Full live cross-stack flow cannot be exercised here; not a code defect."
    accepted_by: "Igor Chemencedji"
    accepted_at: "2026-08-04T08:53:23Z"
must_haves:
  truths:
    - "SC1/AIE-01: DeepEval pytest-native eval suite runs in CI against golden sets and fails the build on schema/grounding/citation regression, never brittle prose"
    - "AIE-01 sub: golden fixtures are seeded from REAL Phase 24-27 model outputs"
    - "AIE-01 sub: metrics call production validation gates directly, never re-implement them"
    - "AIE-01 sub: one-time dev-key capture script exists, documented, reproducible"
    - "SC2/AIE-02: red-team job runs as its own CI check alongside semgrep/ZAP, asserts injection resistance across every AI capability shipped so far"
    - "SC3/AIE-03: fail-closed cost breaker halts AI calls over budget and degrades to deterministic-score-only, never silently overspending"
    - "AIE-03 sub: no-bypass coverage test proves no explain route/batch path reaches billed Anthropic dispatch over budget, non-tautologically"
    - "AIE-03 sub: breaker_tripped exposed to frontend, computed with check_tenant_budget's IDENTICAL comparison"
    - "SC4/AIE-04: tenant admin can view AI usage/cost and manage key/model/budget settings in the UI"
    - "AIE-04 sub: usage endpoint is admin-gated and tenant-scoped (no cross-tenant leakage)"
    - "AIE-04 sub: batch vs on-demand split keys on user_email, never status"
    - "AIE-04 sub: admin pane renders all 4 cards across every UI-SPEC state, admin-only via existing mechanism, composed from inherited primitives + exactly 1 new"
    - "Both new CI jobs are genuinely merge-blocking (ci.yml job names registered byte-for-byte in branch-protection.json)"
    - "Eval job invokes deepeval test run (never bare pytest) with telemetry opt-out; red-team job runs both the injection suite and the budget-coverage test together; an opt-in key-gated non-blocking live tier exists, fork-guarded, never required"
gaps:
  - truth: "Golden fixtures are seeded from REAL Phase 24-27 model outputs (ROADMAP SC1 / REQUIREMENTS.md AIE-01 literal wording)"
    status: partial
    reason: "GETVUL_DEV_ANTHROPIC_KEY is confirmed absent in this environment (a pre-existing, documented blocker since Phase 24-01, predating Phase 28). The 10 committed golden fixtures were hand-authored to pass the identical production gates (model_validate_json + recheck_business_rules) a real capture would need to pass, rather than captured from a live model call. This was pre-authorized in 28-01-PLAN.md's own <objective>/<action> text (not a silent post-hoc deviation), and does not weaken the eval's discriminating power for the 5 structural properties it actually asserts (independently verified: a corrupted fixture copy fails NoRankInvariantMetric/GroundingTraceabilityMetric exactly as a real bad capture would)."
    artifacts:
      - path: "backend/tests/evals/goldens/**/*.json"
        issue: "capture_method: \"hand_authored\" in all 10 fixtures, not a genuine model capture"
    missing:
      - "A real GETVUL_DEV_ANTHROPIC_KEY-driven run of backend/scripts/capture_ai_goldens.py to replace the hand-authored fixtures with genuinely model-captured ones (the script and re-capture procedure are fully built and documented; only the key is missing)"
human_verification:
  - test: "Open /dashboard/settings?category=ai as a tenant admin in a live browser (light + dark theme) and visually confirm the 4-card layout, spacing, and breaker-banner anchor position match 28-UI-SPEC.md"
    expected: "Pane matches the design system pixel/token-level (no unverified visual claims per project lesson getvul-axe-sweep-not-run-during-exec)"
    why_human: "Only jsdom unit tests were run this phase (10/10 pass); no live browser render, screenshot, or Playwright+axe accessibility sweep was executed"
  - test: "Configure a DEV_ANTHROPIC_API_KEY repository secret, author the still-nonexistent backend/tests/evals/test_llm_judge_evals.py and redteam/promptfooconfig.yaml, and observe a real run of the ai-live-eval-optin CI job"
    expected: "Job runs the real DeepEval LLM-judge suite + real promptfoo redteam, continue-on-error true, never blocks, never runs on fork PRs"
    why_human: "Requires a real secret + files that are deliberately left unscaffolded by design; only structural YAML correctness (gating, fork-guard, non-blocking flag) was provable from this sandbox"
  - test: "Push this branch and open a real PR on GitHub against Cyber-Solutions-MD/getvul to observe the 2 new required checks actually blocking merge on a genuine regression"
    expected: "A deliberately-broken golden fixture or injection-isolation regression causes 'AI Golden-Set Evals (DeepEval)' / 'AI Prompt-Injection Red-Team (static)' to fail and the PR to be blocked from merging"
    why_human: "local main is ~400+ commits ahead of origin/main (memory: getvul-origin-behind-local-main); the branch-protection.json config is verified byte-correct and the repo's own 'docs job is deliberately non-required' precedent proves the mechanism, but a live block has not been observed"
  - test: "In a live tenant session, exceed the configured AI budget and confirm every AI surface (explain vuln/host/remediation/remediation-guidance/prioritization, ticket drafting) actually degrades to deterministic-score-only in the running UI, and that the admin pane's breaker banner appears within the same session"
    expected: "All AI surfaces show their existing budget_exceeded degraded state; admin pane shows 'AI paused — budget exceeded' banner reflecting the same underlying state"
    why_human: "Backend guard ordering (explain.py:308 before :339) and frontend budget_exceeded handling (ai-explanation-section.tsx:258) were independently confirmed in isolation/unit tests, and the coverage test proves no route bypasses the guard, but the full live end-to-end user flow across a running frontend+backend stack was not exercised in this verification pass"
  - test: "Human decision: is the hand-authored (non-model-captured) golden-fixture provenance acceptable to close AIE-01, or should milestone close be gated on a real capture-script run first?"
    expected: "Developer accepts the documented fallback via a formal override, or schedules a follow-up task to run capture_ai_goldens.py with a real key"
    why_human: "Policy/scope decision, not a code-correctness question — the mechanism is proven robust either way (see gaps entry above)"
---

# Phase 28: Eval + Cost + Observability Gate Verification Report

**Phase Goal:** The milestone closes with a real, CI-enforced quality gate — evals, red-team injection resistance, a fail-closed cost breaker, and admin-visible usage — seeded from real usage data now that every capability exists.
**Verified:** 2026-08-03T13:10:00Z
**Status:** passed (canonicalized 2026-08-04 via UAT — see frontmatter `overrides`)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1/AIE-01: DeepEval pytest-native eval suite runs in CI, fails build on schema/grounding/citation regression, never brittle prose | ✓ VERIFIED | Ran `DEEPEVAL_TELEMETRY_OPT_OUT=1 deepeval test run tests/evals/test_golden_evals.py` locally keylessly (no `ANTHROPIC_API_KEY` in env): 10/10 passed, exit 0. `grep` confirms zero `evaluation_model=`/`GEval`/`FaithfulnessMetric`/`api_key` references in `metrics.py`. Independently corrupted a fixture copy in-process (injected `"priority": 5`) — `NoRankInvariantMetric` correctly scored 0.0 while the real fixture scores 1.0, proving the gate is discriminating, not tautological. |
| 2 | AIE-01 sub: golden fixtures seeded from REAL Phase 24-27 model outputs | ⚠ PARTIAL | All 10 fixtures' `capture_method` field reads `"hand_authored"`, not a live capture. `GETVUL_DEV_ANTHROPIC_KEY` confirmed absent (pre-existing, documented since Phase 24-01, predates this phase). See Gaps Summary — pre-authorized in the plan itself, does not weaken the gate's structural discrimination, fully reproducible remediation path exists. |
| 3 | AIE-01 sub: metrics call production gates directly, never re-implement | ✓ VERIFIED | Read `backend/tests/evals/metrics.py` in full: `SchemaValidMetric`/`GroundingTraceabilityMetric` import and call `ExplainResponseBase.model_validate_json()` / `recheck_business_rules()` from `app.ai.schemas` directly. `grep -v '^#' metrics.py \| grep -c recheck_business_rules` = 4 (non-commented calls). Independently poisoned a citation `source_field` with `'directory_user'` (not in `PRIORITIZATION_ALLOWLIST`) — `GroundingTraceabilityMetric` correctly scored 0.0 via the real `recheck_business_rules` raising `BusinessRuleError`. |
| 4 | AIE-01 sub: one-time dev-key capture script exists, documented, reproducible | ✓ VERIFIED | `backend/scripts/capture_ai_goldens.py` (16,677 bytes) exists; docstring contains "one-time", "NOT ... run in CI", "GETVUL_DEV_ANTHROPIC_KEY", and an explicit re-capture procedure. Calls the real `build_explain_*_prompt()` + `_build_output_config()` + the same two validation gates. |
| 5 | SC2/AIE-02: red-team job runs as its own CI check alongside semgrep/ZAP, covers every AI capability shipped so far | ✓ VERIFIED | `backend/tests/test_ai_injection_redteam.py`: 17 payloads × 5 capabilities = 85 parametrized cases, ran green (`85 passed in 0.22s`). Confirms only 5 real `build_explain_*_prompt` functions exist in `prompt_builder.py` (no 6th uncovered capability — "ticket-draft" reuses existing rows, has no separate prompt builder). Consolidated cleanly: `grep -c` for all 5 superseded single-payload function names returns 0 in the 4 source files; sibling suites still pass (50/50). CI-blocking tier deliberately uses pytest (not literal `promptfoo`, which cannot run keylessly) — this divergence is explicitly documented in 28-02-PLAN.md's Open Question 1 and was pre-cleared by this verification's own task instructions as intended design, not a shortfall; real `promptfoo` runs in the separate opt-in key-gated tier. |
| 6 | SC3/AIE-03: fail-closed breaker halts AI calls over budget, degrades to deterministic-score-only, never silently overspending | ✓ VERIFIED | Read `app/ai/explain.py:297-339` directly: `check_tenant_budget()` check at line 308 returns early with `status="budget_exceeded"` at line 323, strictly BEFORE the client is constructed at line 339 — confirmed in source, not just from tests. `app/ai/budget.py:60-80`: `check_tenant_budget` returns `spent < monthly_cap_usd` (fail-closed). Frontend `ai-explanation-section.tsx:258` still handles `state.kind === 'budget_exceeded'` (Phase 24 behavior, unmodified and intact). |
| 7 | AIE-03 sub: no-bypass coverage test proves no route/batch path reaches billed dispatch over budget, non-tautologically | ✓ VERIFIED | Ran `backend/tests/test_ai_budget_coverage.py` against real Postgres+Redis (exact CI env/command): 11/11 passed — 5 over-budget routes (`mock_cls.call_count == 0`), 5 under-budget regression controls (`call_count >= 1`, proving the assertion is falsifiable), 1 batch-path test (`batches_created == 0` while `count_tokens_calls >= 1`, proving the construct-then-count-then-gate asymmetry). Independently confirmed `app.ai.batch.py` source: client constructed (:210) and `count_tokens` called (:259) before the gate (:261), `.batches.create()` (:278) only after. |
| 8 | AIE-03 sub: breaker_tripped exposed to frontend, computed with check_tenant_budget's IDENTICAL comparison | ✓ VERIFIED | `backend/app/api/v1/ai/usage.py:70`: `breaker_tripped = monthly_cap_usd is not None and spent >= monthly_cap_usd` — the exact inverse of `budget.py`'s `spent < monthly_cap_usd`. `ai-usage-pane.tsx:234` reads `data.breaker_tripped` directly with zero client-side re-derivation. |
| 9 | SC4/AIE-04: tenant admin can view usage/cost and manage key/model/budget in the UI | ✓ VERIFIED | `GET /api/v1/ai/usage` confirmed mounted (`/api/v1/ai/usage` in `app.routes`). `ai-usage-pane.tsx` renders it via `useAiUsage()`; "Manage in Connectors" links to `/dashboard/connectors`, confirmed a real, functional destination — `connector-form.tsx` already supports editing `model`/`monthly_budget_usd` for the ANTHROPIC connector (built in Phase 24-01), so the link-out is not a dead end. |
| 10 | AIE-04 sub: usage endpoint admin-gated + tenant-scoped | ✓ VERIFIED | `usage.py:64`: `Depends(require_admin)`. Every aggregation query filtered by `AuditLog.tenant_id == user.tenant_id`. Ran `test_ai_usage.py`: 9/9 passed, including explicit viewer/analyst→403, admin→200, and a cross-tenant isolation assertion. |
| 11 | AIE-04 sub: batch vs on-demand split keys on user_email, never status | ✓ VERIFIED | `usage.py:83-86`: `AuditLog.user_email == / != "system:scheduler"`, no `status LIKE 'batch_%'` split logic anywhere. `test_batch_prioritization_counted_in_batch_row_not_on_demand` passed. |
| 12 | AIE-04 sub: admin pane renders all 4 cards across every state, admin-only, inherited chrome + 1 new primitive | ✓ VERIFIED | Ran `npx vitest run ai-usage-pane`: 10/10 passed (6-row backstop, breaker-banner-as-anchor, no-cap-no-meter, zero-usage-all-zero-rows, no-key replacement, error banner, model enum label, no stray delta). `grep -cE '#[0-9A-Fa-f]{6}'` == 0 (no freehand hex); `progress.tsx` uses `bg-surface-2`, no `bg-primary`. `'ai'` confirmed present in both `ALL_CATEGORIES` and `ADMIN_ONLY` in `settings-sidebar-shell.tsx`. |
| 13 | Both new CI jobs are genuinely merge-blocking | ✓ VERIFIED | Scripted check: `ci.yml` job names `'AI Golden-Set Evals (DeepEval)'` and `'AI Prompt-Injection Red-Team (static)'` match byte-for-byte against `branch-protection.json`'s `required_status_checks.checks[]` (both present); `'AI Live Eval + Red-Team (opt-in, non-blocking)'` confirmed absent from that list. Neither blocking job has `continue-on-error`; the opt-in job has `continue-on-error: true`. |
| 14 | Eval job runs `deepeval test run` (not bare pytest); red-team job runs both suites; opt-in tier is key-gated/fork-guarded | ✓ VERIFIED | `ci.yml` `ai-evals` step: `deepeval test run tests/evals/test_golden_evals.py` with `DEEPEVAL_TELEMETRY_OPT_OUT: "1"`. `ai-redteam-injection` step: `pytest tests/test_ai_injection_redteam.py tests/test_ai_budget_coverage.py -v`, backend-shaped with real Postgres/Redis services + migration step. `ai-live-eval-optin`: `env.HAS_DEV_KEY` derived from `secrets.DEV_ANTHROPIC_API_KEY != ''`, `if: github.event.repository.fork == false`, `continue-on-error: true`. |

**Score:** 13/14 truths fully verified; 1 partial (see Gaps Summary) — no truth FAILED outright.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/tests/evals/metrics.py` | 5 non-LLM BaseMetric subclasses calling production gates | ✓ VERIFIED | 279 lines, fully read; substantive, wired (imported by test_golden_evals.py), no network/model calls |
| `backend/tests/evals/test_golden_evals.py` | parametrized assert_test over 10 goldens × 5 metrics | ✓ VERIFIED | 90 lines; ran green (10/10, exit 0) |
| `backend/tests/evals/goldens/**/*.json` (10 files) | golden fixtures passing production gates | ✓ VERIFIED (provenance caveat) | All 10 exist, pass `model_validate_json`+`recheck_business_rules`; hand-authored not model-captured (see Gap #1) |
| `backend/scripts/capture_ai_goldens.py` | one-time dev-key capture mechanism | ✓ VERIFIED | 16,677 bytes; substantive, documented, reuses real production code paths |
| `backend/pyproject.toml` (`deepeval==4.1.5`) | pinned dev dependency | ✓ VERIFIED | `grep -c 'deepeval==4.1.5'` = 1; `import deepeval` succeeds, version 4.1.5 |
| `backend/tests/test_ai_injection_redteam.py` | consolidated 85-case red-team suite | ✓ VERIFIED | 247 lines; ran green (85/85) |
| `backend/tests/test_ai_budget_coverage.py` | no-bypass coverage suite | ✓ VERIFIED | 301 lines; ran green against real Postgres+Redis (11/11) |
| `backend/app/api/v1/ai/usage.py` | require_admin usage aggregation endpoint | ✓ VERIFIED | 136 lines; mounted, wired into `ai_router`, matches locked response shape |
| `backend/tests/test_ai_usage.py` | RBAC + tenant-scope + batch-split + breaker tests | ✓ VERIFIED | ran green (9/9) |
| `frontend/src/lib/queries/use-ai-usage.ts` | useAiUsage() hook | ✓ VERIFIED | 41 lines; wired to real `/api/v1/ai/usage`, field names match backend exactly |
| `frontend/src/components/ui/progress.tsx` | restyled shadcn progress primitive | ✓ VERIFIED | no `bg-primary`; `bg-surface-2` track; caller-driven indicator color |
| `frontend/src/components/settings/ai-usage-pane.tsx` | AIE-04 admin pane, 4 cards | ✓ VERIFIED | 358 lines; consumes real hook data, all UI-SPEC states implemented |
| `frontend/src/components/settings/ai-usage-pane.test.tsx` | pane test suite | ✓ VERIFIED | ran green (10/10) |
| `.github/workflows/ci.yml` (+3 jobs) | ai-evals, ai-redteam-injection, ai-live-eval-optin | ✓ VERIFIED | valid YAML; all 3 jobs present with correct shape |
| `.github/branch-protection.json` (+2 checks) | 2 new required checks | ✓ VERIFIED | valid JSON; byte-for-byte match confirmed via script |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `metrics.py` | `app.ai.schemas` | `recheck_business_rules` + `model_validate_json` | ✓ WIRED | 4 non-commented call sites; independently proven discriminating |
| `test_golden_evals.py` | `app.ai.prompt_builder` allowlists | `import VULN_ALLOWLIST` etc. | ✓ WIRED | `_ALLOWLISTS` dict maps all 5 capabilities |
| `test_ai_injection_redteam.py` | `build_explain_*_prompt` (all 5) | direct in-process call | ✓ WIRED | `CAPABILITY_CASES` references all 5 builder functions |
| `test_ai_budget_coverage.py` | `app.ai.explain.AsyncAnthropic` + `anthropic_client_factory=` seam | `patch(...)` / DI injection | ✓ WIRED | Confirmed module-local bound name patched (not the tautological top-level SDK patch); DI seam used for batch path |
| `usage.py` | `app.ai.budget` | `get_month_to_date_spend` + comparison reuse | ✓ WIRED | Exact comparison match confirmed by direct source read |
| `app/api/v1/ai/__init__.py` | `usage.router` | `ai_router.include_router(usage.router)` | ✓ WIRED | Confirmed present, last in include order |
| `ai-usage-pane.tsx` | `/api/v1/ai/usage` | `useAiUsage()` | ✓ WIRED | Data renders directly from hook's `data` object |
| `settings/page.tsx` | `AiUsagePane` | `case 'ai': return <AiUsagePane />` | ✓ WIRED | Confirmed present with import |
| `settings-sidebar-shell.tsx` | `ADMIN_ONLY` set | append `'ai'` | ✓ WIRED | Confirmed in both `ALL_CATEGORIES` and `ADMIN_ONLY` |
| `ci.yml` (`ai-evals` job) | `tests/evals/test_golden_evals.py` | `deepeval test run` | ✓ WIRED | Exact command confirmed in job step |
| `branch-protection.json` | `ci.yml` job `name:` strings | `required_status_checks.checks[].context` | ✓ WIRED | Byte-for-byte match scripted-confirmed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `ai-usage-pane.tsx` | `data` (from `useAiUsage()`) | `GET /api/v1/ai/usage` → real SQL aggregation (`func.count`/`func.sum` over `AuditLog`, tenant-scoped) | Yes — read `usage.py` source directly; no static/empty fallback | ✓ FLOWING |
| `ai-usage-pane.tsx` | `data.breaker_tripped` | Backend-derived boolean, identical `check_tenant_budget` comparison | Yes — no client-side re-derivation, single source of truth | ✓ FLOWING |
| `ai-evals` CI job | fixture JSON | Committed `goldens/**/*.json`, hand-authored (not live-model-produced) | Structurally real (passes real Pydantic + business-rule validation); not organically model-generated | ⚠ STATIC (by design, documented) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Keyless golden eval suite | `deepeval test run tests/evals/test_golden_evals.py` (no `ANTHROPIC_API_KEY`) | 10/10 passed, exit 0 | ✓ PASS |
| No-rank gate discriminates | corrupted fixture (`priority: 5` injected in-process) vs clean | corrupt=0.0, clean=1.0 | ✓ PASS |
| Grounding gate discriminates | poisoned `source_field='directory_user'` (non-allowlisted) | scored 0.0, `BusinessRuleError` raised | ✓ PASS |
| Consolidated red-team suite | `pytest tests/test_ai_injection_redteam.py -q` | 85 passed | ✓ PASS |
| Sibling prompt-builder suites (post-consolidation regression) | `pytest tests/test_ai_prompt_builder*.py -q` | 50 passed | ✓ PASS |
| No-bypass budget coverage (real DB) | `pytest tests/test_ai_budget_coverage.py -v` against real Postgres+Redis | 11/11 passed | ✓ PASS |
| Usage endpoint mounted | `create_app()`; assert path in `app.routes` | `/api/v1/ai/usage` present | ✓ PASS |
| Usage endpoint tests | `pytest tests/test_ai_usage.py -v` | 9/9 passed | ✓ PASS |
| Frontend pane suite | `npx vitest run ai-usage-pane` | 10/10 passed | ✓ PASS |
| Frontend full regression | `npx vitest run` | 899/899 passed, 133/133 files | ✓ PASS |
| Frontend type check | `npx tsc --noEmit` | clean | ✓ PASS |
| Frontend lint (phase files) | `npx eslint <phase-28-files>` | clean | ✓ PASS |
| Backend collection | `pytest --collect-only -q` | 733 tests collected, 0 errors | ✓ PASS |
| Backend lint/format | `ruff check .` / `ruff format --check <new files>` | clean / 8 files already formatted | ✓ PASS |
| Backend type check (real CI scope) | `mypy app/ \| mypy-baseline filter --allow-unsynced` | pre-existing `note 27 -3 +6` drift, confirmed via clean-HEAD control to be unrelated to Phase 28 files (jwt.py/service.py, last touched Phase 6) | ✓ PASS (pre-existing noise) |
| CI wiring byte-for-byte | scripted YAML+JSON introspection | both blocking names present in branch-protection, opt-in absent | ✓ PASS |
| Git commit integrity | `git log --oneline --all \| grep <10 claimed hashes>` | all 10 hashes found | ✓ PASS |
| Working tree cleanliness | `git status --short <all phase-28 files>` | no output (fully committed) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|-------------|--------|----------|
| AIE-01 | 28-01, 28-05 | DeepEval harness runs in CI against golden sets, fails build on schema/grounding/citation regression | ✓ SATISFIED (1 partial sub-item) | Eval suite genuinely CI-blocking, discriminating, structural; fixture provenance is hand-authored not real-captured (see Gap) |
| AIE-02 | 28-02, 28-05 | Red-team job runs as separate CI check, asserts injection resistance across every AI capability | ✓ SATISFIED | 85-case suite, own CI job, merge-blocking; pytest-not-literal-promptfoo divergence pre-cleared by task instructions |
| AIE-03 | 28-02, 28-03, 28-05 | Fail-closed budget breaker halts AI calls, product degrades to deterministic-score-only | ✓ SATISFIED | Guard-before-dispatch confirmed in source; no-bypass coverage test green with falsifiable regression control; frontend exposure wired |
| AIE-04 | 28-03, 28-04 | Tenant admin views usage/cost, manages key/model/budget in UI | ✓ SATISFIED | Endpoint + pane both wired and tested; "manage" link-out to Connectors confirmed functional (pre-existing model/budget edit UI) |

No orphaned requirements: REQUIREMENTS.md maps only AIE-01..04 to Phase 28, and all 4 are declared across the 5 plans' frontmatter (`28-01: [AIE-01]`, `28-02: [AIE-02,AIE-03]`, `28-03: [AIE-03,AIE-04]`, `28-04: [AIE-04]`, `28-05: [AIE-01,AIE-02,AIE-03]`). REQUIREMENTS.md shows all 4 as `[x] Complete`, consistent with codebase evidence above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/tests/evals/goldens/**/*.json` | all 10 | `capture_method: "hand_authored"` — fixtures not seeded from real Phase 24-27 outputs as ROADMAP SC1/REQUIREMENTS.md AIE-01 literally state | ⚠️ Warning | Pre-authorized in-plan fallback (absent dev key); does not weaken structural discrimination (independently verified); fully reproducible remediation exists |
| `.github/workflows/ci.yml` | 90-96 (`backend` job) | Pre-existing `backend` job's "Run tests" step has no `ENCRYPTION_KEY`, unlike the new `ai-redteam-injection` job which had to add one | ⚠️ Warning | Out of Phase 28's scope (files_modified didn't include the `backend` job); will cause 5 pre-existing Phase 24-27 test files to fail the next time this job runs for real against `origin/main`; already transparently logged in `deferred-items.md` (28-05 entry) with a suggested fix |
| `backend/app/auth/jwt.py`, `service.py` | n/a | Pre-existing `mypy-baseline` `note`-line drift (`27 -3 +6`) | ℹ️ Info | Confirmed via clean-HEAD control test to be unrelated to any Phase 28 file (these files last touched in Phase 6); does not represent a new type violation |
| `backend/tests/test_ai_explain_remediation_guidance.py`, `test_ai_schemas.py`, `test_connectors/test_rapid7_connector.py` | n/a | Pre-existing `ruff format --check` drift | ℹ️ Info | Confirmed pre-existing via git log (last touched Phase 23/25/26); logged in `deferred-items.md`, not caused by Phase 28 |

No blocker-level anti-patterns found. No TODO/FIXME/stub-return/empty-handler patterns found in any Phase 28 file (all "placeholder" grep hits were legitimate documentation, e.g., describing a loading-pulse UI element or explicitly noting a value is "NOT a placeholder string").

### Human Verification Required

### 1. Visual/accessibility fidelity of the admin pane

**Test:** Open `/dashboard/settings?category=ai` as a tenant admin in a live browser, both light and dark theme.
**Expected:** 4-card layout, spacing, and breaker-banner anchor position match `28-UI-SPEC.md` pixel/token-level; passes an axe accessibility sweep.
**Why human:** Only jsdom unit tests ran this phase (10/10 pass); no live browser render, screenshot, or Playwright+axe sweep was executed (consistent with this project's own documented lesson that AA/visual claims need a live render, not just unit tests).

### 2. Opt-in live-eval CI tier end-to-end behavior

**Test:** Configure a `DEV_ANTHROPIC_API_KEY` repo secret, author `backend/tests/evals/test_llm_judge_evals.py` + `redteam/promptfooconfig.yaml` (both deliberately left unscaffolded), and observe a real run of `ai-live-eval-optin`.
**Expected:** Job runs the real LLM-judge suite + real promptfoo red-team, remains non-blocking, never runs on fork PRs.
**Why human:** Requires a real secret and files that don't exist yet by design; only the job's YAML structure (gating, fork-guard, non-blocking flag) was provable from this sandbox.

### 3. Real GitHub merge-blocking enforcement

**Test:** Push and open a real PR against the GitHub repo; deliberately break a golden fixture or an injection-isolation assertion and confirm the PR is blocked from merging.
**Expected:** "AI Golden-Set Evals (DeepEval)" / "AI Prompt-Injection Red-Team (static)" fail and block merge.
**Why human:** Local `main` is ~400+ commits ahead of `origin/main` (project memory), so this has never been observed live; the config is verified byte-correct and the repo's own "docs job is deliberately non-required" precedent proves the mechanism works, but a live block hasn't been witnessed.

### 4. Full live degrade-to-deterministic-only user flow

**Test:** In a live tenant session, exceed the configured AI budget and confirm every AI surface degrades to deterministic-score-only in the running UI, with the admin pane's breaker banner reflecting the same state.
**Expected:** All AI surfaces show their existing `budget_exceeded` degraded state; admin pane shows the amber banner.
**Why human:** Backend guard ordering and frontend handling were both independently confirmed in isolation (source read + unit/integration tests), but the full live end-to-end flow across a running stack was not exercised in this pass.

### 5. Policy decision on golden-fixture provenance

**Test:** Decide whether hand-authored (non-model-captured) golden fixtures are acceptable to consider AIE-01 fully closed, or whether milestone close should wait on a real `capture_ai_goldens.py` run.
**Expected:** Either a formal override accepting the current state, or a scheduled follow-up task.
**Why human:** This is a policy/scope decision, not a code-correctness question — the eval mechanism is independently proven robust either way.

**This looks intentional and well-engineered.** To accept the golden-fixture-provenance deviation, add to this file's frontmatter:

```yaml
overrides:
  - must_have: "Golden fixtures are seeded from REAL Phase 24-27 model outputs"
    reason: "GETVUL_DEV_ANTHROPIC_KEY absent in this environment (pre-existing since Phase 24-01); hand-authored fixtures pass the identical production validation gates a real capture would, and the capture script is ready to regenerate them the moment a key is available."
    accepted_by: "{your name}"
    accepted_at: "{current ISO timestamp}"
```

## Gaps Summary

Phase 28 delivers a genuinely functioning, independently-verified, CI-enforced quality gate. Every automatable truth checked out: the DeepEval suite runs keyless and truly discriminates good/bad structural output (proven by deliberately corrupting fixtures in-process, not just trusting the SUMMARY); the consolidated red-team suite covers all 5 real AI capabilities with 85 cases; the no-bypass budget coverage test is non-tautological (an under-budget control proves the over-budget assertion is falsifiable) and matches the actual fail-closed ordering read directly from `explain.py`/`batch.py` source; the usage endpoint and admin pane are fully wired end-to-end with real data flow (not hardcoded/static); and both new CI jobs are registered byte-for-byte in `branch-protection.json`, making them genuinely merge-blocking (not merely CI-visible, mirroring the repo's own "docs job" counter-example).

One real, disclosed gap exists: the 10 committed golden fixtures are hand-authored synthetic data, not literally "seeded from real Phase 24-27 outputs" as ROADMAP SC1 and REQUIREMENTS.md's AIE-01 both state verbatim. This was pre-authorized in 28-01-PLAN.md's own text (an explicit contingency for the already-documented absent-dev-key environment, not a shortfall discovered after the fact), and does not weaken the actual gate mechanism — the 5 metrics assert JSON-shape/business-rule STRUCTURAL properties (never prose quality), and a hand-authored fixture that must pass the same real `model_validate_json()`/`recheck_business_rules()` gates is equally valid evidence for those specific properties. A fully-built, documented, reproducible capture script exists to regenerate real fixtures the moment a `GETVUL_DEV_ANTHROPIC_KEY` becomes available. This is classified as a WARNING requiring a human policy decision (accept via override, or schedule a real-capture follow-up), not a BLOCKER — it does not prevent the phase's actual goal (a real, CI-enforced quality gate) from being achieved.

Separately, an out-of-phase-28-scope but real finding: the pre-existing `backend` CI job (the "Backend" required check, untouched by this phase) still lacks an `ENCRYPTION_KEY` env var its own "Run tests" step needs, and will fail the next time it runs for real in CI against 5 other Phase 24-27 test files that seed encrypted AI credentials. This is transparently logged in `deferred-items.md` (28-05 entry) with a suggested one-line fix, confirmed pre-existing and unrelated to any file this phase modified — flagged here for visibility only, not counted against Phase 28's own goal achievement.

The initial status was `human_needed` because of the four live/visual/policy items above (Step 9's rule: human-verification items take priority over a full pass score) — none of which represents a broken or missing capability, but all of which require either a live stack, a live GitHub PR cycle, a real secret, or a human policy call that cannot be settled by static codebase inspection alone.

**Canonicalized to `passed` on 2026-08-04 via `/gsd-verify-work 28`.** Of the four human-verification items: item 1 (admin pane visual/a11y) was satisfied against a live browser — a new Playwright + axe sweep passed WCAG 2.1 AA clean in both themes after fixing a real `aria-progressbar-name` violation (resolved gap G-28-1); item 5 (golden-fixture provenance policy) was decided in favour of accepting the documented hand-authored fallback. Items 2, 3, and 4 require external infrastructure that cannot be provisioned in this environment (a `DEV_ANTHROPIC_API_KEY` GitHub secret + live CI run, a PR against a synced origin, and a live spending BYOK key, respectively) and were formally **waived by the user as accepted overrides** (see frontmatter `overrides`). None is a code defect. Phase 28 therefore achieves its goal — a real, CI-enforced quality gate — and is verified passed.

---

*Verified: 2026-08-03T13:10:00Z*
*Verifier: Claude (gsd-verifier)*
