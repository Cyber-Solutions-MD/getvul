---
phase: 44-natural-language-query-assistant
plan: 06
subsystem: testing
tags: [deepeval, pytest, ci, evals, redteam, promptfoo, ai, nlq]

# Dependency graph
requires:
  - phase: 44-01/44-02 (NLQ backend)
    provides: "build_query_translate_prompt/build_query_narrate_prompt, NlqFilterResponse/VulnFilterInput/AssetFilterInput/TicketFilterInput (extra=forbid), NlqAnswerResponse, recheck_nlq_filter_exclusivity -- the exact contract this plan's gates assert against"
  - phase: 28-eval-cost-observability-gate
    provides: "The two CI-blocking keyless gates being extended: test_golden_evals.py's 5 structural DeepEval metrics (metrics.py) + test_ai_injection_redteam.py's consolidated adversarial-payload x capability suite; the ai-evals/ai-redteam-injection CI jobs; the deliberately-unscaffolded ai-live-eval-optin tier + redteam/promptfooconfig.yaml placeholder"
provides:
  - "backend/tests/evals/test_nlq_golden_evals.py -- a NEW FilterCorrectnessMetric (calls the real NlqFilterResponse.model_validate_json + recheck_nlq_filter_exclusivity gates) for nlq_translate, and the 5 EXISTING structural metrics reused verbatim for nlq_narrate"
  - "9 hand-authored golden fixtures: 6 nlq_translate (north-star + 3 UI-SPEC starters + a D-14 honest-refusal + hallucinated-field + cross-tenant-reach rejection cases) and 3 nlq_narrate (grounded/zero-results/tickets-entity)"
  - "test_ai_injection_redteam.py's 6th CAPABILITY_CASES entry (build_query_translate_prompt) -- all 17 adversarial payloads now also run against the NLQ translate prompt (102 total cases)"
  - "ci.yml's ai-evals step now also runs test_nlq_golden_evals.py in the same keyless job"
  - "redteam/promptfooconfig.yaml -- the first-ever content in this previously-unscaffolded file (Phase 28 left it deliberately absent); NLQ intent-plugin scenarios covering question-phrasing injection / cross-tenant reach / hallucinated field-enum, still fully inert without a DEV_ANTHROPIC_API_KEY secret"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A capability's own dedicated goldens/<capability>/ auto-discovery function, scoped to just that capability (not a bare GOLDENS_DIR.iterdir()) -- lets a NEW eval file (test_nlq_golden_evals.py) own SIBLING directories under the SAME goldens/ root as an existing, unrelated eval file (test_golden_evals.py) without either file's discovery colliding with the other's capability-to-metric mapping."
    - "A response-model-agnostic structural metric (FilterCorrectnessMetric) that switches between 'must validate + exact-match a golden' and 'must be REJECTED' modes via one fixture-level flag (expect_valid) -- generalizes GroundingTraceabilityMetric's own 'call the real production gate directly' discipline to a schema-rejection assertion, not just a schema-success assertion."
    - "A per-capability close_tag parameter threaded through a previously-single-tag-hardcoded adversarial test function -- lets one generic (payload x capability) test generalize across builders that wrap their untrusted content in DIFFERENT tag names (<scanner_data> vs <user_question>)."

key-files:
  created:
    - backend/tests/evals/test_nlq_golden_evals.py
    - backend/tests/evals/goldens/nlq_translate/north_star.json
    - backend/tests/evals/goldens/nlq_translate/sla_breach.json
    - backend/tests/evals/goldens/nlq_translate/tickets_hostname.json
    - backend/tests/evals/goldens/nlq_translate/active_exploit.json
    - backend/tests/evals/goldens/nlq_translate/refuse_groupby.json
    - backend/tests/evals/goldens/nlq_translate/hallucinated_field.json
    - backend/tests/evals/goldens/nlq_translate/cross_tenant_reach.json
    - backend/tests/evals/goldens/nlq_narrate/grounded.json
    - backend/tests/evals/goldens/nlq_narrate/zero_results.json
    - backend/tests/evals/goldens/nlq_narrate/tickets_hostname_resolved.json
    - redteam/promptfooconfig.yaml
  modified:
    - backend/tests/evals/metrics.py
    - backend/tests/evals/test_golden_evals.py
    - backend/tests/test_ai_injection_redteam.py
    - .github/workflows/ci.yml

key-decisions:
  - "FilterCorrectnessMetric lives in test_nlq_golden_evals.py itself (not metrics.py) -- keeps metrics.py's existing 5 Explain*-shaped metrics untouched except for one additive _RESPONSE_MODELS dict entry, minimizing blast radius on the already-green ai-evals gate"
  - "nlq_translate/nlq_narrate goldens live as SIBLING dirs under the SAME backend/tests/evals/goldens/ root test_golden_evals.py already scans (matching the plan's literal file path) -- required fixing test_golden_evals.py's own _load_goldens() to scope to registered _ALLOWLISTS capabilities only, rather than moving the new dirs to an unlisted separate root"
  - "Golden fixture content for north_star/sla_breach/tickets_hostname is a byte-for-byte copy of FEW_SHOT_QUERY_TRANSLATE's own recorded input/output (prompt_builder.py) -- ties the golden's claimed ground truth to the SAME source of truth the shipped prompt uses, so a future prompt/golden drift is structurally impossible to introduce silently"
  - "hallucinated_field.json and cross_tenant_reach.json fixtures are DELIBERATELY schema-invalid (an owner_email field inside VulnFilterInput; a top-level tenant_id on NlqFilterResponse) -- expect_valid=false flips FilterCorrectnessMetric into asserting the REJECTION itself, proving extra='forbid' actually fires for exactly these two attack shapes"
  - "build_query_translate_prompt's record_factory (_query_record) is an identity function -- unlike the other 5 capabilities (which poison one field inside a larger fixed dict), the translate prompt takes the raw question string directly, so the ENTIRE input is the poisoned field"

patterns-established: []

requirements-completed: [NLQ-02]

# Metrics
duration: ~25min
completed: 2026-08-25
---

# Phase 44 Plan 06: NLQ Eval + Red-Team Gate Expansion Summary

**test_nlq_golden_evals.py (a new FilterCorrectnessMetric + the 5 existing structural metrics reused verbatim) and a 6th test_ai_injection_redteam.py capability make NLQ-02's safe-schema/injection/hallucination/cross-tenant guarantees CI-blocking, keylessly, extending the two existing Phase 28 gates additively -- no parallel eval pipeline.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-25T12:30:00Z
- **Completed:** 2026-08-25T12:55:00Z
- **Tasks:** 2
- **Files modified:** 15 (11 created, 4 modified)

## Accomplishments
- Both existing keyless CI-blocking gates (Phase 28's `ai-evals` and `ai-redteam-injection` jobs) now cover NLQ: `test_nlq_golden_evals.py` runs inside `ai-evals`'s existing `deepeval test run` invocation; the extended `test_ai_injection_redteam.py` runs inside `ai-redteam-injection`'s existing whole-file `pytest` invocation -- zero new CI jobs, zero new pipelines.
- The north-star question and 3 of the 4 UI-SPEC starter questions golden-match `FEW_SHOT_QUERY_TRANSLATE`'s own recorded output verbatim (no independently-typed duplicate that could drift); the 4th starter ("active exploit") is hand-authored since it has no few-shot precedent yet.
- Proved empirically (not just asserted) that `NlqFilterResponse`'s `extra="forbid"` actually rejects both a hallucinated owner-PII field (`owner_email`) and a cross-tenant-reach attempt (`tenant_id`) -- `FilterCorrectnessMetric`'s `expect_valid=False` mode asserts the `pydantic.ValidationError` fires, not merely that it theoretically should.
- Widened the red-team suite from 17x5=85 to 17x6=102 keyless cases by adding `build_query_translate_prompt` as a 6th capability -- required generalizing a previously-hardcoded `</scanner_data>` close-tag into a per-capability parameter, since the NLQ translate prompt wraps its untrusted content in `<user_question>` instead.
- Authored `redteam/promptfooconfig.yaml` for the first time ever (Phase 28 deliberately left it non-existent) with NLQ `intent`-plugin scenarios spanning all three attack categories the plan named -- still fully inert without a `DEV_ANTHROPIC_API_KEY` secret; the two CI-blocking gates above are the real NLQ-02 arbiter, this is supplementary.

## Task Commits

Each task was committed atomically:

1. **Task 1: NLQ golden evals -- translate filter-correctness + narrate structural reuse** - `d12c672` (feat)
2. **Task 2: extend the red-team injection suite + CI wiring + inert promptfoo scenarios** - `b62b935` (feat)

**Plan metadata:** _pending -- this commit_

## Files Created/Modified
- `backend/tests/evals/test_nlq_golden_evals.py` - `FilterCorrectnessMetric` (new) + reuse of the 5 existing structural metrics for `nlq_narrate`; its own scoped `_load_nlq_goldens()` auto-discovery
- `backend/tests/evals/goldens/nlq_translate/*.json` (6) - north_star, sla_breach, tickets_hostname, active_exploit, refuse_groupby, hallucinated_field, cross_tenant_reach
- `backend/tests/evals/goldens/nlq_narrate/*.json` (3) - grounded, zero_results, tickets_hostname_resolved
- `backend/tests/evals/metrics.py` - added `NlqAnswerResponse` to `_RESPONSE_MODELS` (Rule 3: `SchemaValidMetric` couldn't otherwise resolve the name)
- `backend/tests/evals/test_golden_evals.py` - `_load_goldens()` now scopes to registered `_ALLOWLISTS` capabilities only (Rule 1: prevents the new sibling `nlq_translate`/`nlq_narrate` dirs from `KeyError`-ing the existing gate)
- `backend/tests/test_ai_injection_redteam.py` - 6th `CAPABILITY_CASES` entry (`build_query_translate_prompt`, field `"question"`, `_query_record` identity factory, close tag `</user_question>`); generalized the previously-hardcoded `</scanner_data>` tag into a `close_tag` parameter (Rule 3)
- `.github/workflows/ci.yml` - `ai-evals` step now runs `tests/evals/test_golden_evals.py tests/evals/test_nlq_golden_evals.py`
- `redteam/promptfooconfig.yaml` (new) - NLQ `intent`-plugin scenarios (question-phrasing injection / cross-tenant reach / hallucinated field-enum), opt-in/key-gated/non-blocking tier only

## Decisions Made
See `key-decisions` in frontmatter above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_golden_evals.py::_load_goldens()` would have `KeyError`'d on the new sibling goldens dirs**
- **Found during:** Task 1, while designing where `goldens/nlq_translate/` and `goldens/nlq_narrate/` should live
- **Issue:** The plan's own `files_modified` places the new golden dirs directly under `backend/tests/evals/goldens/` -- the SAME root `test_golden_evals.py`'s `_load_goldens()` already scans via a bare `GOLDENS_DIR.iterdir()`. That function unconditionally looks up `_ALLOWLISTS[capability_dir.name]` for every subdirectory it finds; `"nlq_translate"`/`"nlq_narrate"` are not keys in `_ALLOWLISTS`, and even if they were, `NlqFilterResponse`/`NlqAnswerResponse` aren't `ExplainResponseBase`-shaped in the way the 5 existing structural metrics assume. Left unfixed, the very first push after this plan would have made the EXISTING, already-green `ai-evals` job start failing with a `KeyError` -- a real regression the plan's own `<verification>` explicitly requires not to happen ("existing ai-evals/ai-redteam-injection jobs still green").
- **Fix:** Changed `_load_goldens()` to iterate only capabilities registered in `_ALLOWLISTS` (looking up `GOLDENS_DIR / capability` for each, skipping if absent) instead of blindly iterating every subdirectory. Zero behavior change for the 5 existing capabilities (all already keys in `_ALLOWLISTS`); the two new dirs are now invisible to this file and are exclusively owned by `test_nlq_golden_evals.py`'s own separately-scoped discovery function.
- **Files modified:** `backend/tests/evals/test_golden_evals.py`
- **Verification:** `deepeval test run tests/evals/test_golden_evals.py` -- 10/10 still pass (unchanged); `deepeval test run tests/evals/test_golden_evals.py tests/evals/test_nlq_golden_evals.py` (the exact CI invocation) -- 20/20 pass together.
- **Committed in:** `d12c672` (Task 1 commit)

**2. [Rule 3 - Blocking] `SchemaValidMetric` couldn't resolve `"NlqAnswerResponse"` without a `metrics.py` change**
- **Found during:** Task 1, wiring the reused structural metrics for `nlq_narrate`
- **Issue:** The plan says to reuse the 5 existing narrate metrics "verbatim." `SchemaValidMetric.__init__(response_model: str)` resolves that string against `metrics.py`'s own `_RESPONSE_MODELS` dict, which only listed the 5 `Explain*Response` classes -- passing `"NlqAnswerResponse"` would `KeyError` at test-collection time, blocking Task 1 entirely.
- **Fix:** Added `NlqAnswerResponse` (imported from `app.ai.schemas`) as a 6th `_RESPONSE_MODELS` entry, same pattern as the existing 5. `NlqAnswerResponse` is an `ExplainResponseBase` subclass with zero added fields (schemas.py's own docstring), so this is a pure additive registration, not a new code path.
- **Files modified:** `backend/tests/evals/metrics.py`
- **Verification:** `SchemaValidMetric(response_model="NlqAnswerResponse")` passes against all 3 `nlq_narrate` fixtures.
- **Committed in:** `d12c672` (Task 1 commit)

**3. [Rule 3 - Blocking] The generic red-team assertion function hardcoded `</scanner_data>`, which `build_query_translate_prompt` never emits**
- **Found during:** Task 2, adding the 6th `CAPABILITY_CASES` entry
- **Issue:** `test_injection_payload_isolated_to_scanner_data_block` parsed the untrusted-content block by hardcoding `user_text.rindex("</scanner_data>")`. `build_query_translate_prompt` wraps its content in `<user_question>...</user_question>`, not `<scanner_data>...</scanner_data>` (prompt_builder.py) -- the hardcoded tag would either raise `ValueError` (tag not found) or, worse, silently mis-parse the block boundary for every one of the 17 payloads against this capability.
- **Fix:** Added a `close_tag` field to each `CAPABILITY_CASES` tuple (`"</scanner_data>"` for the 5 existing capabilities, `"</user_question>"` for `query_translate`) and threaded it through the test function in place of the literal.
- **Files modified:** `backend/tests/test_ai_injection_redteam.py`
- **Verification:** `pytest tests/test_ai_injection_redteam.py -q` -- 102/102 pass (85 pre-existing + 17 new); `pytest tests/test_ai_injection_redteam.py -k query_translate -q` -- 17/17 pass in isolation.
- **Committed in:** `b62b935` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug that would have regressed an already-green gate, 2 Rule 3 blocking issues discovered while wiring "verbatim" reuse across a shape/tag boundary the reused code never anticipated).
**Impact on plan:** All three are small, contained, and each is a direct precondition for the plan's own explicit "existing gates still green" / "reuses metrics verbatim" / "runs all 17 existing adversarial payloads" requirements. No scope creep -- `metrics.py`/`test_golden_evals.py` weren't in this plan's `files_modified`, but both fixes are minimal, additive, and fully covered by the existing + new test runs.

## Issues Encountered
- `redteam/promptfooconfig.yaml` did not exist anywhere in the repo or git history prior to this plan (confirmed via `git log --all -- redteam/promptfooconfig.yaml` and a full-tree search) -- Phase 28 deliberately left it unscaffolded pending a `DEV_ANTHROPIC_API_KEY` secret (28-05-SUMMARY.md, 28-VERIFICATION.md, STATE.md's own Deferred Items table). This plan authors it for the first time; verified the `intent`-plugin YAML shape against promptfoo's own current docs (via the ctx7 documentation-lookup fallback, not training memory) rather than guessing the schema.

## User Setup Required
None - no external service configuration required. `redteam/promptfooconfig.yaml`'s scenarios only ever execute if a developer later configures a `DEV_ANTHROPIC_API_KEY` repository secret (pre-existing Phase 28 deferred item, unchanged by this plan) to exercise the opt-in `ai-live-eval-optin` job.

## Known Stubs
None. Both new test files exercise real production code paths (`NlqFilterResponse.model_validate_json`, `recheck_nlq_filter_exclusivity`, the real `build_query_translate_prompt`) end-to-end; no hardcoded empty values or placeholder copy were introduced.

## Threat Flags
None -- every new surface (the 6th red-team capability, the two new golden-fixture dirs, the promptfoo NLQ scenarios) is coverage FOR the plan's own threat model (T-44-01/T-44-02/T-44-03/T-44-13), not new attack surface of its own. No new network endpoint, auth path, or schema change was introduced.

## Next Phase Readiness
- NLQ-02 is now provable in CI: the safe-schema constraint (isolation, no cross-tenant reach, no hallucinated field) is enforced by the two existing keyless CI-blocking gates, extended additively, plus hand-authored golden filter-correctness -- exactly the plan's own success criteria.
- Phase 44's remaining plan (44-04, Ask page composition) is independent of this eval/red-team gate work and can proceed or has already proceeded separately per STATE.md's phase map.
- No blockers.

## Self-Check: PASSED

Verified all 11 created files exist on disk at their claimed paths; verified both task commit hashes (`d12c672`, `b62b935`) are present in `git log --oneline`; re-ran `deepeval test run tests/evals/test_golden_evals.py tests/evals/test_nlq_golden_evals.py` (20/20 pass) and `pytest tests/test_ai_injection_redteam.py -q` (102/102 pass) as a final confirmation, matching the exact commands `.github/workflows/ci.yml` now runs.

---
*Phase: 44-natural-language-query-assistant*
*Completed: 2026-08-25*
