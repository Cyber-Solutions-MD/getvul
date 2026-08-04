---
phase: 28
slug: eval-cost-observability-gate
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-01
validated: 2026-08-04
---

# Phase 28 — Validation Strategy

> Per-phase validation contract. This phase IS largely about validation infrastructure (evals + red-team + breaker coverage), so its own tests are the deliverable.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest 7.x (+ DeepEval for evals) · Frontend: vitest · CI: GitHub Actions (.github/workflows/ci.yml) |
| **Config file** | backend: `backend/pyproject.toml` · frontend: `frontend/vitest.config.ts` · CI: `.github/workflows/ci.yml` |
| **Quick run command** | backend: `cd backend && ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test python -m pytest tests/evals tests/test_ai_injection_redteam.py tests/test_ai_budget_coverage.py -q` · frontend: `cd frontend && npx vitest run ai-usage settings` |
| **Full suite command** | backend: `cd backend && python -m pytest tests/test_ai_*.py tests/evals -q` · frontend: `cd frontend && npx vitest run` |
| **Estimated runtime** | ~60-90s backend (keyless deterministic eval + red-team + coverage); ~90s frontend |

> KEYLESS-CI constraint (D-01): the CI-BLOCKING eval + red-team tiers make ZERO model calls — they assert over captured golden fixtures + built prompts. The opt-in LLM-judge/live-promptfoo tier is `if: secrets.<KEY>` guarded and NON-blocking. getvul backend pytest env: real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY, per-file runs. Postgres + Redis up.

---

## Sampling Rate

- **After every task commit:** quick run for the touched side
- **After every plan wave:** full suite command(s)
- **Before `/gsd-verify-work`:** full suite green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

*Reconciled by validate-phase against the 5 shipped SUMMARY files (28-01..05) — the placeholder `TBD` planner row was a pre-execution artifact, replaced below with the real per-requirement coverage.*

| Req | Plan(s) | Behavior Verified | Test Type | Test File(s) / Artifact | Automated Command | Status |
|-----|---------|-------------------|-----------|-------------------------|-------------------|--------|
| AIE-01 | 28-01, 28-05 | Keyless DeepEval golden-set eval harness (5 non-LLM structural metrics calling production schema/business-rule gates directly) runs in CI, fails build on schema/grounding/citation/no-rank/no-PII regression; one-time dev-key capture script exists | unit + CI-gate | `backend/tests/evals/test_golden_evals.py` (10 goldens), `backend/tests/evals/metrics.py`, `backend/scripts/capture_ai_goldens.py`, `ai-evals` job in `.github/workflows/ci.yml` + `branch-protection.json` | `cd backend && DEEPEVAL_TELEMETRY_OPT_OUT=1 deepeval test run tests/evals/test_golden_evals.py` | ✅ green (10/10, re-run keyless 2026-08-04) |
| AIE-02 | 28-02, 28-05 | Consolidated keyless prompt-injection red-team (17-payload corpus × 5 capabilities = 85 cases) asserts injection stays inside `<scanner_data>`, never leaks to system prompt, never breaks the tag boundary; runs as its own blocking CI check | integration + CI-gate | `backend/tests/test_ai_injection_redteam.py` (85 cases), `ai-redteam-injection` job + `branch-protection.json` | `cd backend && pytest tests/test_ai_injection_redteam.py -q` | ✅ green (85/85, re-run keyless 2026-08-04) |
| AIE-03 | 28-02, 28-03, 28-05 | Fail-closed budget breaker: no explain route or batch path reaches billed Anthropic dispatch over budget (non-tautological, with under-budget falsifiability control); `breaker_tripped` exposed to frontend via `check_tenant_budget()`'s identical comparison | integration + CI-gate | `backend/tests/test_ai_budget_coverage.py` (11 cases), `breaker_tripped` derivation cases in `backend/tests/test_ai_usage.py`, ran inside `ai-redteam-injection` job | `cd backend && ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test-secret pytest tests/test_ai_budget_coverage.py -q` | ✅ green (11/11 per 28-02/28-05 SUMMARY; needs Postgres+Redis) |
| AIE-04 | 28-03, 28-04 | `GET /api/v1/ai/usage` is admin-gated + tenant-scoped (no cross-tenant leakage), batch/on-demand split on `user_email` not `status`, `degraded_calls_count` formula; admin pane renders 4 UI-SPEC cards + all non-populated states, breaker anchor banner, 6-row backstop, enum model label | unit (backend+frontend) | `backend/tests/test_ai_usage.py` (9 cases), `frontend/src/components/settings/ai-usage-pane.test.tsx` (10 cases), `frontend/src/components/settings/settings-sidebar-shell.test.tsx` (RBAC category gating) | `cd backend && pytest tests/test_ai_usage.py -q` · `cd frontend && npx vitest run ai-usage-pane settings-sidebar-shell` | ✅ green (9 backend + 10 frontend per 28-03/28-04 SUMMARY) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- New: `backend/tests/evals/` (DeepEval keyless structural metrics + golden fixtures), `tests/test_ai_injection_redteam.py` (consolidated keyless red-team), `tests/test_ai_budget_coverage.py` (no-bypass coverage), `.github/workflows/ci.yml` job additions. Golden fixtures are captured once (dev-key, redacted) and committed — a documented one-time op, not a CI dependency.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live admin AI usage/cost pane visual + a11y fidelity (4-card layout, spacing, breaker-banner anchor, both themes) | AIE-04 | Pixel/token fidelity + axe sweep need a live browser (jsdom-only during exec) | Open `/dashboard/settings?category=ai` as admin in light + dark; Playwright + axe sweep. **✅ Done live 2026-08-04** (UAT Test 1): axe WCAG 2.1 AA clean both themes after fixing `aria-progressbar-name` (G-28-1) via `frontend/e2e/ai-usage-pane-a11y.spec.ts` |
| Live cost breaker degrades every AI surface end-to-end when a tenant exceeds budget | AIE-03 | Requires a live BYOK key spending real inference to trip the fail-closed breaker across the running stack (BYOK absent since Phase 24-01) | Force budget-exceeded with a live key; confirm every AI surface degrades to deterministic-only. **User-waived 2026-08-04** (VERIFICATION override — guard-before-dispatch ordering + non-tautological no-bypass coverage proven in isolation; not a code defect) |
| Opt-in key-gated live LLM-judge eval + real promptfoo red-team (`ai-live-eval-optin` tier) | AIE-01/AIE-02 | Requires a `DEV_ANTHROPIC_API_KEY` repo secret + the intentionally-unscaffolded `test_llm_judge_evals.py` / `promptfooconfig.yaml`; non-blocking CI tier | Configure the secret + author the opt-in files, run the key-gated job. **User-waived 2026-08-04** (VERIFICATION override — YAML gating/fork-guard/non-blocking structure proven from source) |
| Merge-blocking observed on a real GitHub PR | AIE-01/AIE-02/AIE-03 | Requires a PR against a synced origin; local main is ~400+ commits ahead of origin/main ([[getvul-origin-behind-local-main]]) | Push a synced branch + open a PR; observe the 2 required checks block merge. **User-waived 2026-08-04** (VERIFICATION override — `branch-protection.json` verified byte-correct vs `ci.yml` job names) |

*The CI-BLOCKING tiers (deterministic evals, keyless red-team, breaker coverage, usage RBAC/tenant-scope) are fully automated + green; the live-observation + key-gated items are manual and were formally accepted as overrides in 28-VERIFICATION.md (status: passed).*

---

## Validation Sign-Off

- [x] All requirements have `<automated>` verify (AIE-01/02/03/04 each map to committed green tests)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (evals dir, red-team + coverage tests, usage endpoint tests, ci.yml jobs, golden fixtures) — all exist on disk
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-08-04 (validate-phase) — all CI-blocking automated coverage present + green; live/key-gated items are manual and user-waived in 28-VERIFICATION.md.

---

## Validation Audit 2026-08-04

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

**Method:** State-A audit reconciling the stale pre-execution draft (placeholder `TBD` Per-Task Map row, `status: draft`) against the 5 shipped SUMMARY files. Every requirement (AIE-01/02/03/04) was already covered by committed automated tests wired into CI — no automatable gap remained, so no `gsd-nyquist-auditor` spawn was required. Re-ran the two keyless CI-blocking suites locally to substantiate green: `tests/evals/test_golden_evals.py` + `tests/test_ai_injection_redteam.py` → **95 passed** (0.23s, zero model calls). The budget-coverage/usage suites are documented green in 28-02/28-03/28-05 SUMMARYs and confirmed by the `passed` 28-VERIFICATION.md (13/14 must-haves; 4 live/infra items user-accepted as overrides). No test files generated; reconciliation only.
