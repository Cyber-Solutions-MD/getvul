---
phase: 44-natural-language-query-assistant
plan: 01
subsystem: api
tags: [anthropic, pydantic, fastapi, sse, redis, ai, nlq]

# Dependency graph
requires:
  - phase: 23-28 (v3.0 AI foundation)
    provides: BYOK key storage (tenant_keys.py), _run_explain_stream's precondition envelope + client factory + SSE helpers, cache.py (translation cache + inflight lock), budget.py (fail-closed breaker), audit.py (audit_log_ai_call), schemas.py (ExplainResponseBase + recheck_business_rules)
provides:
  - "POST /api/v1/ai/query -- SSE endpoint answering a vulnerabilities question end-to-end: translate -> execute (tenant-scoped, risk-ranked) -> results-first SSE -> narrate (grounded) -> done"
  - "NlqFilterResponse flat non-union filter contract (VulnFilterInput/AssetFilterInput/TicketFilterInput) + recheck_nlq_filter_exclusivity business-rule gate"
  - "build_query_translate_prompt / build_query_narrate_prompt: <user_question>/<query_results> untrusted-content-as-data isolation"
  - "query_assistant.py::_run_query_stream orchestrator + _call_structured shared retry loop + _resolve_hostname (ready for Plan 02's tickets entity)"
  - "audit_log_ai_call(action_prefix=...) -- additive, backward-compatible; ai.query.* audit vocabulary"
affects: [44-02 (predicate expansion + assets/tickets entities), 44-03/04/05 (frontend Ask page), 44-06 (evals/red-team)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-call orchestration sibling (translate -> execute -> narrate) reusing a single-call engine's constituent pieces by direct import, rather than parameterizing or duplicating the single-call engine itself"
    - "Flat, non-union Pydantic response schema (independently-optional fields + an explicit Python exclusivity recheck) as the Anthropic-structured-output-safe alternative to a discriminated union"
    - "on_attempt_failed callback threaded through a shared retry loop so every attempt (not just the terminal one) gets its own audit row"

key-files:
  created:
    - backend/app/ai/query_assistant.py
    - backend/app/api/v1/ai/query.py
    - backend/tests/test_ai_query_stream.py
    - backend/tests/test_ai_prompt_builder_query.py
  modified:
    - backend/app/ai/schemas.py
    - backend/app/ai/prompt_builder.py
    - backend/app/ai/audit.py
    - backend/app/api/v1/ai/__init__.py
    - backend/tests/test_ai_schemas.py
    - backend/app/ai/explain.py
    - backend/app/assets/service.py

key-decisions:
  - "VulnFilterInput carries NO asset_hostname field -- the vulnerabilities entity is never host-scoped (W3); host-scoped questions route to the tickets entity where TicketFilterInput.asset_hostname is resolved server-side"
  - "AssetFilterInput this plan carries only device_category (no internet_facing yet -- Plan 02 adds it once AssetFilter itself gains the field)"
  - "Cached translations skip recheck_nlq_filter_exclusivity re-verification (only ever cached after a successful recheck) and skip the per-call audit row (no LLM call happened, nothing to log)"
  - "Audit resource_type is 'translate'/'narrate' (not a generic 'query') with resource_id='pending' before the entity is known, then filter_resp.entity once resolved -- gives a directly-greppable ai.query.translate / ai.query.narrate audit trail"
  - "sort='triage' is hardcoded in _map_vuln_filter, never model-supplied -- the deterministic, risk-ranked ORDER BY that makes the top-N stable run-to-run (D-07)"

patterns-established:
  - "_call_structured(client, ..., recheck=None, on_attempt_failed=None): the reusable single-call-with-one-corrective-retry unit any future two-model-call AI capability can import directly"

requirements-completed: [NLQ-01, NLQ-02, NLQ-03]

# Metrics
duration: 42min
completed: 2026-08-25
---

# Phase 44 Plan 01: Natural-Language Query Tracer Summary

**POST /api/v1/ai/query streams question->translate->execute->results-first->narrate->done for the vulnerabilities entity, BYOK-gated and tenant-scoped, reusing the v3.0 AI scaffold's precondition/cache/budget/audit machinery verbatim.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-08-25T09:59:23Z (STATE.md, phase-execution start)
- **Completed:** 2026-08-25T10:41:00Z
- **Tasks:** 3
- **Files modified:** 11 (7 modified, 4 created)

## Accomplishments
- A vulnerabilities question ("critical KEV vulns older than 30 days") now flows end-to-end: LLM translates it into a schema-validated, `extra="forbid"` filter object; the backend executes `list_vulnerabilities` deterministically with the SAME risk-ranked `sort="triage"` ORDER BY the rest of the app uses; `interpreted`+`results` SSE frames land before the LLM narrates a grounded answer over exactly those rows+count.
- Proved the D-01 flat-schema-avoids-`oneOf` design empirically (not just by citation): `NlqFilterResponse.model_json_schema()` has zero `oneOf` keys and every `$ref` is self-contained.
- BYOK-inert (`no_key`), fail-closed budget, and a single shared inflight lock for the whole two-call flow (not one per model call) are all proven via keyless integration tests against a real Postgres+Redis.
- The translation-only D-19 cache (question->filter, never results/answer) is proven: a repeated question skips the second translate call entirely while still executing the query fresh and narrating current data.

## Task Commits

Each task was committed atomically:

1. **Task 1: NLQ schemas (flat non-union filter contract) + audit action_prefix** - `45f4202` (feat)
2. **Task 2: Query translate + narrate prompt builders (untrusted-question isolation)** - `88ccfc9` (feat)
3. **Task 3: query_assistant.py two-call orchestrator + POST /api/v1/ai/query route** - `4e34ecb` (feat)

**Plan metadata:** _pending — this commit_

## Files Created/Modified
- `backend/app/ai/schemas.py` - VulnFilterInput/AssetFilterInput/TicketFilterInput, NlqFilterResponse (flat non-union), NlqAnswerResponse, recheck_nlq_filter_exclusivity
- `backend/app/ai/audit.py` - `audit_log_ai_call(action_prefix="explain")` additive param
- `backend/app/ai/prompt_builder.py` - build_query_translate_prompt/build_query_narrate_prompt, SYSTEM_PROMPT_QUERY_TRANSLATE/NARRATE, FEW_SHOT_QUERY_TRANSLATE/NARRATE, query_translate/narrate_prompt_version
- `backend/app/ai/query_assistant.py` - `_run_query_stream` orchestrator, `_call_structured` shared retry loop, `_resolve_hostname`, `_map_vuln_filter`, local `_audit` wrapper
- `backend/app/ai/explain.py` - Rule 1: widened `_build_output_config`'s type hint from `type[ExplainResponseBase]` to `type[BaseModel]`
- `backend/app/api/v1/ai/query.py` - `POST /query` (SSE, require_analyst), `QueryRequest`
- `backend/app/api/v1/ai/__init__.py` - registered `query.router`
- `backend/app/assets/service.py` - Rule 1: `list_assets` now populates all of `AssetSummary`'s required fields
- `backend/tests/test_ai_schemas.py` - NLQ filter/exclusivity/no-oneOf tests + audit action_prefix tests
- `backend/tests/test_ai_prompt_builder_query.py` - translate/narrate prompt isolation + version tests
- `backend/tests/test_ai_query_stream.py` - 23 integration tests covering the full orchestrator + route

## Decisions Made
See `key-decisions` in frontmatter above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_build_output_config`'s type hint was too narrow for a genuinely generic helper**
- **Found during:** Task 3 (writing `_call_structured`, mypy check)
- **Issue:** `explain.py::_build_output_config(response_model: type[ExplainResponseBase], model: str)` only ever calls `.model_json_schema()` -- a plain `BaseModel` method with no `ExplainResponseBase`-specific behavior. `_call_structured` needs to call it with `NlqFilterResponse`, which is NOT an `ExplainResponseBase` subclass, so mypy flagged the mismatch. Every prior caller happened to pass an `ExplainResponseBase` subclass, so the over-narrow annotation was never exercised until now.
- **Fix:** Widened the parameter type to `type[BaseModel]` (added `BaseModel` to the module's pydantic import) -- zero behavior change; every existing `ExplainResponseBase` subclass IS a `BaseModel`.
- **Files modified:** `backend/app/ai/explain.py`
- **Verification:** `mypy app/ai/explain.py app/ai/query_assistant.py` clean; full existing `test_ai_explain_stream.py`/`test_ai_explain_*` suites (157+23 tests) still green.
- **Committed in:** `4e34ecb` (Task 3 commit)

**2. [Rule 1 - Bug] `assets/service.py::list_assets` never populated 5 of `AssetSummary`'s required fields**
- **Found during:** Task 3 (writing/testing `_resolve_hostname`, which calls `list_assets`)
- **Issue:** `AssetSummary.os_version`/`device_category`/`model`/`assigned_user`/`managed_by` have no default value (required fields), but `list_assets`'s `AssetSummary(...)` construction never passed them -- any call to this function raised a `pydantic.ValidationError`. This is a latent, always-broken code path: `app.assets.service.list_assets` has ZERO other callers anywhere in the codebase (the real `GET /api/v1/assets` route is a completely separate, self-contained implementation in `app/assets/router.py` that never calls this service function), so the bug was never previously exercised by any production path or existing test.
- **Fix:** Added the 5 missing keyword arguments, reading them off the `Asset` ORM row exactly like the other already-populated fields.
- **Files modified:** `backend/app/assets/service.py`
- **Verification:** New `_resolve_hostname` tests pass (resolve/unresolved/tenant-scoped); existing asset test suites (`test_asset_source_filter.py`, `test_assets_tags_and_os_family.py`, `test_asset_exposure.py`, `test_asset_groups.py`, `test_asset_owner_reassign.py` -- 69 tests total) unaffected.
- **Committed in:** `4e34ecb` (Task 3 commit)

**3. [Rule 2 - Missing critical] Restructured the retry loop's audit callback so every attempt is logged, not just the terminal one**
- **Found during:** Task 3, self-testing (`test_translate_two_malformed_responses_terminal_error_two_audit_rows` initially failed: 1 row instead of 2)
- **Issue:** My first draft only audited a `ValidationError`/`BusinessRuleError` outcome once, in the caller, after `_call_structured` finally raised on the terminal attempt -- silently dropping the audit row for every earlier failed-then-retried attempt. This violates AI-06 ("every attempt is audit-logged, no silent unlogged call"), a discipline the existing `_run_explain_stream` already proves with its own per-attempt audit call inside its loop.
- **Fix:** Added an `on_attempt_failed` callback parameter to `_call_structured`, invoked once per failed attempt (including the terminal one, right before it re-raises); the caller's own except-block no longer double-audits.
- **Files modified:** `backend/app/ai/query_assistant.py`
- **Verification:** `test_translate_two_malformed_responses_terminal_error_two_audit_rows` and `test_exclusivity_violation_retries_once_then_succeeds` both assert the exact per-attempt audit-row sequence and pass.
- **Committed in:** `4e34ecb` (Task 3 commit)

**4. [Rule 2 - Missing critical] Added `min_length=1` to `QueryRequest.question`**
- **Found during:** Task 3 (writing the route)
- **Issue:** The plan's acceptance criteria only named `Field(..., max_length=500)`; an accidentally-empty submission would still dispatch a billable model call for zero analytical value.
- **Fix:** Added `min_length=1` alongside `max_length=500` -- a request-body-level, FastAPI/Pydantic-enforced check (never model-call-dependent).
- **Files modified:** `backend/app/api/v1/ai/query.py`
- **Verification:** `test_post_query_rejects_empty_question` (422).
- **Committed in:** `4e34ecb` (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (2 pre-existing bugs surfaced by this task's own new code paths, 1 audit-completeness gap found via self-testing, 1 minor input-validation addition).
**Impact on plan:** All four are small, contained, and either fix a genuine defect this plan's own code depends on or close a gap in the exact guarantee (AI-06 audit completeness) the plan requires. No scope creep -- neither `explain.py` nor `assets/service.py` was in the plan's `files_modified` list, but both fixes are one-line-to-small, backward-compatible, and fully covered by existing + new tests.

## Issues Encountered
- Initial `ENCRYPTION_KEY=test-key-please-ignore-...` placeholder (copied verbatim from the plan's own `<verify>` blocks) is NOT a valid Fernet key and fails at `Fernet(key)` construction time for any test touching `encrypt_value`/`decrypt_value`. Worked around locally by generating a real key via `Fernet.generate_key()` per the existing MEMORY.md guidance (`getvul-backend-pytest-env`) -- the plan's own verify-block literal should be treated as illustrative, not copy-paste-safe.
- A class docstring on `NlqFilterResponse` that used the literal substring `"oneOf"` (to explain why it's structurally impossible) leaked into `model_json_schema()`'s own `description` field, causing `test_nlq_filter_schema_has_no_oneof` to false-fail against its own explanatory prose. Rephrased the docstring to avoid the literal substring while preserving the explanation.
- One prompt-builder isolation test initially picked a test `question` string that collided verbatim with `FEW_SHOT_QUERY_NARRATE`'s own illustrative example text, causing a false failure (the few-shot example legitimately IS part of the system prompt). Changed the test's fixture to a distinct, marker-tagged string.

## User Setup Required
None - no external service configuration required. BYOK Anthropic key configuration (existing v3.0 connector wizard) remains the only per-tenant setup, already covered by prior phases.

## Known Stubs

- **`query_assistant.py::_run_query_stream`** (both the non-`vulnerabilities`-entity dispatch and the `else` branch after `vuln_filter_input` resolution) yields a guarded `{"type": "refuse"}` placeholder for the `assets`/`tickets` entities instead of actually executing `list_assets`/`list_tickets`. This is explicitly the plan's own scoped intent (frontmatter: "For entity in (\"assets\",\"tickets\") this plan yields a guarded {\"type\":\"refuse\"} placeholder — Plan 02 replaces with real branches") -- the TRACER proves the D-01 spine on ONE entity at minimum blast radius before Plan 02 widens it. `_resolve_hostname` (the tickets-entity dependency) is already built and tested, ready for Plan 02 to wire in. Not a gap this plan's own goal requires closing.

## Threat Flags

None -- every new surface (the POST /api/v1/ai/query route, the translate/narrate model calls, the emitted filter's execution path) is already covered by the plan's own `<threat_model>` (T-44-01 through T-44-06). The two Rule-1 bug fixes (`explain.py`'s type hint, `assets/service.py`'s `list_assets`) touch no trust boundary and add no new externally-reachable surface -- `list_assets` remains tenant-scoped exactly as before, just now actually invocable.

## Next Phase Readiness
- The D-01 tool/filter contract is proven end-to-end (translate -> execute -> narrate) on the vulnerabilities entity with 100% keyless integration coverage (63 tests across the 3 new/modified test files, plus 157+69 regression tests green).
- `NlqFilterResponse`/`AssetFilterInput`/`TicketFilterInput` already structurally support the assets/tickets entities (schemas exist); Plan 02 needs to: (1) add `asset_internet_facing`/`sla_breached` to `VulnFilterInput` + `VulnerabilityFilter`, (2) add `internet_facing` to `AssetFilterInput`/`AssetFilter`, (3) replace the two `{"type":"refuse"}` guarded placeholders in `_run_query_stream`'s `else` branch and non-vulnerabilities dispatch with real `list_assets`/`list_tickets` executions (wiring `_resolve_hostname`, already built and tested, into the tickets branch), (4) extend `FEW_SHOT_QUERY_TRANSLATE`/`FEW_SHOT_QUERY_NARRATE` for the two new entities.
- No blockers. The translation-cache, inflight-lock, and audit-trail machinery is entity-agnostic and needs zero changes for Plan 02.

## Self-Check: PASSED

All 11 claimed created/modified files verified present on disk; all 3 task commit hashes (`45f4202`, `88ccfc9`, `4e34ecb`) verified present in `git log`.

---
*Phase: 44-natural-language-query-assistant*
*Completed: 2026-08-25*
