---
phase: 44
slug: natural-language-query-assistant
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-24
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `44-RESEARCH.md` §Validation Architecture. The planner populates the
> Per-Task Verification Map; validate-phase §6 sets `status: validated`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing `backend/tests/`) + DeepEval 4.1.5 (`deepeval test run`); Vitest/Testing Library (frontend co-located `*.test.tsx`) |
| **Config file** | `backend/pyproject.toml` (pytest), `.github/workflows/ci.yml` (job wiring), `.github/branch-protection.json` (required-check names) |
| **Quick run command** | `pytest tests/test_ai_query_stream.py tests/test_ai_prompt_builder_query.py tests/test_ai_schemas.py -v` |
| **Full suite command** | `pytest -v --cov=app --cov-report=xml` + `deepeval test run tests/evals/test_nlq_golden_evals.py` + `pytest tests/test_ai_injection_redteam.py -v` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_ai_query_stream.py tests/test_ai_prompt_builder_query.py tests/test_ai_schemas.py -v`
- **After every plan wave:** Run `deepeval test run tests/evals/test_nlq_golden_evals.py` + `pytest tests/test_ai_injection_redteam.py -v` + frontend `vitest run`
- **Before `/gsd-verify-work`:** Full suite must be green (both existing `ai-evals` / `ai-redteam-injection` CI jobs, extended, still green)
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {N}-01-01 | 01 | 1 | NLQ-{XX} | T-44-01 / — | {expected secure behavior or "N/A"} | unit | `{command}` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Planner: populate this map from `44-RESEARCH.md` §Validation Architecture "Phase Requirements → Test Map".*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_ai_query_stream.py` — NLQ-01/02/03 orchestration behavior; reuse the `anthropic_client_factory` test seam from `test_ai_explain_stream.py`
- [ ] `backend/tests/test_ai_prompt_builder_query.py` — new prompt-builder isolation contract at unit level
- [ ] `backend/tests/evals/goldens/nlq_translate/*.json` + `backend/tests/evals/goldens/nlq_narrate/*.json` — new golden fixture dirs
- [ ] `backend/tests/evals/test_nlq_golden_evals.py` — new eval file; reuse the 5 existing narrate metrics verbatim, add one `FilterCorrectnessMetric` for translate fixtures
- [ ] Extend `backend/tests/test_ai_injection_redteam.py` `CAPABILITY_CASES` with a 6th entry (`build_query_translate_prompt`, poisoned `question` field)
- [ ] Extend `.github/workflows/ci.yml` `ai-evals` step to run `tests/evals/test_nlq_golden_evals.py`
- [ ] `frontend/src/app/(authed)/dashboard/ask/page.test.tsx` — mirror `campaigns/page.test.tsx` co-located convention

*(No framework install needed — pytest/DeepEval/Vitest already configured and running in CI.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live adversarial red-team (real question-phrasing injection, LLM-graded) | NLQ-02 | Key-gated (`DEV_ANTHROPIC_API_KEY` absent — same accepted gap as Phase 28); non-blocking CI tier | `npx promptfoo@0.121.20 redteam run -c redteam/promptfooconfig.yaml` after adding NLQ scenarios |

*All other phase behaviors have automated (keyless CI) verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
