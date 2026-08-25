---
phase: 44
slug: natural-language-query-assistant
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-24
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `44-RESEARCH.md` §Validation Architecture. Per-Task Verification Map populated by plan-phase.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing `backend/tests/`) + DeepEval 4.1.5 (`deepeval test run`); Vitest/Testing Library (frontend co-located `*.test.tsx`) |
| **Config file** | `backend/pyproject.toml` (pytest), `.github/workflows/ci.yml` (job wiring), `.github/branch-protection.json` (required-check names) |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=… JWT_SECRET_KEY=test pytest tests/test_ai_query_stream.py tests/test_ai_prompt_builder_query.py tests/test_ai_schemas.py -v` |
| **Full suite command** | `pytest -v --cov=app --cov-report=xml` + `deepeval test run tests/evals/test_nlq_golden_evals.py` + `pytest tests/test_ai_injection_redteam.py -v` + frontend `npx vitest run` |
| **Estimated runtime** | ~120 seconds |

> Backend pytest env (project memory): set `ENCRYPTION_KEY` + `JWT_SECRET_KEY` and run per-file, not the whole `tests/` dir, to avoid false failures.

---

## Sampling Rate

- **After every task commit:** `cd backend && ENCRYPTION_KEY=… JWT_SECRET_KEY=test pytest tests/test_ai_query_stream.py tests/test_ai_prompt_builder_query.py tests/test_ai_schemas.py -v` (backend) / `npx vitest run <changed test>` (frontend)
- **After every plan wave:** `deepeval test run tests/evals/test_nlq_golden_evals.py` + `pytest tests/test_ai_injection_redteam.py -v` + frontend `npx vitest run`
- **Before `/gsd-verify-work`:** Full suite green (both existing `ai-evals` / `ai-redteam-injection` CI jobs, extended, still green)
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 44-01-01 | 01 | 1 | NLQ-02 | T-44-03 | Filter schema rejects unknown field (extra=forbid) + single-entity exclusivity recheck; no oneOf in schema | unit | `pytest tests/test_ai_schemas.py -k "nlq or action_prefix" -x` | ❌ W0 | ⬜ pending |
| 44-01-02 | 01 | 1 | NLQ-02 | T-44-01 | Question text isolated to `<user_question>`, never in system prompt | unit | `pytest tests/test_ai_prompt_builder_query.py -x` | ❌ W0 | ⬜ pending |
| 44-01-03 | 01 | 1 | NLQ-01/02/03 | T-44-02/05/06 | no_key never 500; results-first SSE order; tenant_id never from model; both calls audited ai.query.* | integration | `pytest tests/test_ai_query_stream.py -x` | ❌ W0 | ⬜ pending |
| 44-02-01 | 02 | 2 | NLQ-01 | T-44-08 | New vuln predicates (asset_internet_facing join no-double-join, sla_breached stored column); asset native; ticket wrapper | unit | `pytest tests/test_vulnerabilities_filters.py -x` | ❌ W0 | ⬜ pending |
| 44-02-02 | 02 | 2 | NLQ-01 | T-44-07 | assets/tickets branches; server-side hostname→UUID; unresolvable host = zero-results | integration | `pytest tests/test_ai_query_stream.py -x` | ❌ W0 | ⬜ pending |
| 44-03-01 | 03 | 3 | NLQ-01 | T-44-10 | useQueryStream POSTs body; results-first phases before narrative; DegradedCard exported | unit | `npx vitest run src/lib/ai/use-query-stream.test.ts` | ❌ W0 | ⬜ pending |
| 44-03-02 | 03 | 3 | NLQ-01 | — | query-box/starter/interpreted render with sunset tokens + verbatim copy; E1/E3/E4 backstops | typecheck/lint | `npx tsc --noEmit && npx eslint src/components/ai/ask` | ❌ W0 | ⬜ pending |
| 44-03-03 | 03 | 3 | NLQ-01 | T-44-09 | result-table entity-dispatch over existing primitives; {topN} of {total} caption | unit | `npx vitest run src/components/ai/ask/result-table.test.tsx` | ❌ W0 | ⬜ pending |
| 44-05-01 | 05 | 3 | NLQ-01 | T-44-11 | boolean/numeric URL-state clamp; buildNlqDeepLink param names match backend filter fields | unit | `npx vitest run src/lib/ai/nlq-deep-link.test.ts src/hooks/use-url-state-scalar.test.ts` | ❌ W0 | ⬜ pending |
| 44-05-02 | 05 | 3 | NLQ-01 | T-44-11 | list pages read full D-17 param set, clamped | typecheck/lint | `npx tsc --noEmit && npx eslint "src/app/(authed)/dashboard/vulnerabilities/page.tsx"` | ❌ W0 | ⬜ pending |
| 44-06-01 | 06 | 3 | NLQ-02 | T-44-03 | translate filter-correctness goldens + narrate structural metrics; refuse/hallucination cases | eval | `deepeval test run tests/evals/test_nlq_golden_evals.py` | ❌ W0 | ⬜ pending |
| 44-06-02 | 06 | 3 | NLQ-02 | T-44-01/13 | 6th red-team CAPABILITY_CASES entry (all 17 payloads); ci.yml runs NLQ evals | red-team, keyless, CI-blocking | `pytest tests/test_ai_injection_redteam.py -k query_translate -x` | ❌ W0 | ⬜ pending |
| 44-04-01 | 04 | 4 | NLQ-01/03 | T-44-14 | Configure-AI inert state; empty/refuse/zero/budget/error states; Open-in deep-link; nav entry | component | `npx vitest run "src/app/(authed)/dashboard/ask/page.test.tsx"` | ❌ W0 | ⬜ pending |
| 44-04-02 | 04 | 4 | NLQ-01/03 | T-44-14 | Live end-to-end flow (inert→configure→results-first→streaming→deep-link) | checkpoint:human-verify | manual (see plan) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_ai_query_stream.py` — NLQ-01/02/03 orchestration behavior; reuse the `anthropic_client_factory` test seam from `test_ai_explain_stream.py` (created in Plan 01)
- [ ] `backend/tests/test_ai_prompt_builder_query.py` — new prompt-builder isolation contract at unit level (Plan 01)
- [ ] `backend/tests/test_ai_schemas.py` — NLQ schema additions (Plan 01)
- [ ] `backend/tests/test_vulnerabilities_filters.py` — D-03 predicate coverage (Plan 02)
- [ ] `backend/tests/evals/goldens/nlq_translate/*.json` + `nlq_narrate/*.json` — new golden fixture dirs (Plan 06)
- [ ] `backend/tests/evals/test_nlq_golden_evals.py` — new eval file; reuse 5 narrate metrics + 1 FilterCorrectnessMetric (Plan 06)
- [ ] Extend `backend/tests/test_ai_injection_redteam.py` `CAPABILITY_CASES` with a 6th entry (Plan 06)
- [ ] Extend `.github/workflows/ci.yml` `ai-evals` step to run `tests/evals/test_nlq_golden_evals.py` (Plan 06)
- [ ] Frontend `*.test.tsx`: use-query-stream (Plan 03), result-table (Plan 03), nlq-deep-link + use-url-state-scalar (Plan 05), ask/page.test.tsx (Plan 04)

*(No framework install needed — pytest/DeepEval/Vitest already configured and running in CI. Test files are created within the plan whose Nyquist command references them — no separate Wave 0 plan.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live adversarial red-team (real question-phrasing injection, LLM-graded) | NLQ-02 | Key-gated (`DEV_ANTHROPIC_API_KEY` absent — same accepted gap as Phase 28); non-blocking CI tier | `npx promptfoo@0.121.20 redteam run -c redteam/promptfooconfig.yaml` after adding NLQ scenarios (Plan 06) |
| Full live Ask flow (inert → configure → results-first → streaming → deep-link) | NLQ-01/03 | Visual/interactive SSE + BYOK live-key flow | 44-04-PLAN.md Task 2 `checkpoint:human-verify` |

*All other phase behaviors have automated (keyless CI) verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or a checkpoint/Wave-0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (validate-phase §6 sets `status: validated`)
