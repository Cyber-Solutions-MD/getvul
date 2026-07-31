---
phase: 26-prioritization-narrative
verified: 2026-07-31T15:42:36Z
status: passed
status_note: "PASSED WITH ACCEPTED DEBT. All 10 must-haves verified at code+test level; zero gaps, zero regressions (backend AI 243 + scheduler/batch/top-N 42 + connector-health 9, frontend 853, all green; live alembic round-trip clean; SDK-introspection-confirmed dict-access + no-rank schema + cross-tenant BYOK isolation). The 4 remaining human_verification items are the live browser + live 24h-Batches-round-trip checks the user EXPLICITLY WAIVED at the 26-05 tracer gate (proceed-on-trust, mirroring 24-06/25-05) and, on 2026-07-31, accepts as TRACKED DEBT rather than blocking. NOT observed — tracked in 26-UAT.md; close via /gsd-verify-work 26. Conscious user risk-acceptance, not live confirmation."
human_verification_disposition: waived-accepted-as-debt
score: 10/10 verifiable must-haves verified (4 live items accepted as debt)
overrides_applied: 1
human_verification:
  - test: "Live prioritization narrative render (real Anthropic key)"
    expected: "As Analyst, opening a top-N finding's drill panel and clicking 'Explain the priority' streams an 'Analyzing…' state then a cited narrative explaining KEV/exploit/CVSS/SLA/department drivers, with scanner_verbatim tint + ai_interpreted tags, and NEVER an independent priority number/verdict"
    why_human: "Requires a live Docker stack + a configured tenant Anthropic key + browser observation — the same class of live item explicitly waived at the 24-06/25-05 tracer gates and again at 26-05 (proceed-on-trust, no dev key provisioned)"
  - test: "Live no-AI-rank sweep across every list/table view (/vulnerabilities, dashboard, drill panel, tickets)"
    expected: "No AI-generated rank column, sort control, or numeric AI badge anywhere; the deterministic ASSET-02 score remains the one sortable number"
    why_human: "Visual/interaction confirmation in a live browser; the automated frontend/tests/no-ai-rank.test.ts CI check (verified green, see Anti-Patterns) covers the static-analysis half but not a live render sweep"
  - test: "Live end-to-end Message Batches round-trip: nightly submit -> up to 24h wait -> poll -> completed AiBatchJob row -> cache-hit narrative in the drill panel"
    expected: "An AiBatchJob row transitions in_progress -> completed with real Anthropic batch IDs, and the batch-warmed narrative renders identically to an on-demand one (same cache key)"
    why_human: "Requires a real Anthropic API key, real spend, and wall-clock time up to 24h; every automated test in this phase injects a fake client via the anthropic_client_factory seam — no live key is configured in this environment"
  - test: "Visual/accessibility spot-check of the new Clock-icon pending card and citation tinting (WCAG AA contrast)"
    expected: "The new pending/queued card and citation tiers meet the project's WCAG AA contrast bar"
    why_human: "Per project convention (no axe/Playwright a11y sweep was run against a live prod build during execution — treat WCAG AA claims as unproven until that sweep runs)"
---

# Phase 26: Prioritization Narrative Verification Report

**Phase Goal:** An analyst sees a "what to fix first and why" narrative from exploit/KEV/owner/SLA factors that AUGMENTS-NEVER-REPLACES the deterministic ASSET-02 risk score, pre-generated in bulk on a schedule via the Message Batches API using the tenant's own key, with an on-demand fallback.

**Verified:** 2026-07-31T15:42:36Z
**Status:** passed (with accepted debt — 4 waived live items, see status_note)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

All truths below were checked directly against the codebase (source reads, live grep, live pytest/vitest execution, a live alembic round-trip, and live Python introspection of the installed `anthropic` SDK) — SUMMARY.md claims were treated as hypotheses to falsify, not evidence.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | **SC1** — narrative built from exploit/KEV/owner/SLA structured facts (never raw free reasoning), cited, in the drill panel — AIP-01 | VERIFIED (code+test); live render → human_verification | `get_prioritization_context()` (backend/app/ai/grounding.py:330-386) SELECTs exactly cve_id + 8 D-04 factor columns + `Asset.department`; `build_explain_prioritization_prompt()` (prompt_builder.py:1214-1230) frames them as `<scanner_data source="prioritization">` data, never instructions; `AiExplanationSection resourceType="prioritization"` mounts between AI Explanation and Remediation in drill-content.tsx:306-312, reusing the unmodified `AiExplanationCitations` two-tier (scanner_verbatim/ai_interpreted) renderer. 46 backend + 93 frontend tests green (see Behavioral Spot-Checks). Live browser render explicitly waived by user at 26-05 (mirrors 24-06/25-05) — see Human Verification. |
| 2 | **SC2** — the deterministic ASSET-02 score remains the ONE sortable/authoritative number; NO independently-sortable AI-generated rank anywhere in the UI — AIP-01 | VERIFIED | `ExplainPrioritizationResponse(ExplainResponseBase): pass` (schemas.py:96-105) — live Python introspection confirms `model_fields == {summary, business_risk, citations, grounded}`, zero numeric field, no `priority`/`rank`/`score`/`ai_priority`/`ai_rank`/`ai_score` identifier. `frontend/tests/no-ai-rank.test.ts` (4/4 tests green) statically greps `components/**/*.tsx` + `lib/queries/**/*.ts`; independent broad `grep -rniE "ai[_-]?(rank|priority|score)\b"` across the ENTIRE `frontend/src/` (beyond the CI check's own scope) returns zero matches outside test/allowlisted files. `assets-table.tsx` still renders/sorts by `risk_score` unmodified. |
| 3 | **SC3** — prioritization narratives pre-generated in bulk on a schedule via the Message Batches API, dispatched via `asyncio.create_task` (never inline/stalling a sync tick), using only that tenant's own configured key — AIP-02 | VERIFIED | `scheduler.py::_dispatch_ai_batch_prewarm()` (24h-gated) and `_dispatch_ai_batch_poll()` (every tick) both call `asyncio.create_task(run_batch_prewarm())` / `asyncio.create_task(poll_pending_batches())` (lines 102, 124) — zero inline `await run_batch_prewarm`/`await poll_pending_batches`, zero `AsyncAnthropic` reference anywhere in scheduler.py. `run_batch_prewarm()`/`poll_pending_batches()` (batch.py) each resolve `get_tenant_anthropic_key()` per tenant/job and build a FRESH client via `_default_client_factory(key)` — `grep -c "AsyncAnthropic()" batch.py` == 0. Live end-to-end round-trip (real key, real 24h window) → human_verification. |
| 4 | NO-RANK schema+UI double-enforcement (Pitfall #7) | VERIFIED | Backend: schema has zero numeric fields (proven live, item 2). Frontend: `no-ai-rank.test.ts` exists, passes 4/4; CI mechanism proven non-vacuous by design (strips string contents before bare-word scan, so this phase's OWN locked prose "Explain the priority" doesn't trip it, while a real code-level identifier would). |
| 5 | OWNER-PII exclusion at query + prompt layers (D-04/D-15) | VERIFIED | Query layer: `get_prioritization_context()`'s SELECT (grounding.py:356-369) lists only 10 named columns; `assigned_user`/`managed_by`/`building`/`serial_number` absent from the SELECT (confirmed by isolating the function body and grepping — only docstring prose names them as excluded). Prompt layer: `AllowlistedPrioritization` (`model_config={"extra":"forbid"}`) built field-by-field via `_get_field()`, never a dict-spread. Tests `test_owner_pii_columns_never_selected` and the dict/attribute-object allowlist-exclusion tests are real (seed asset with `department="Finance"`, positively assert PII keys absent) — not vacuous. |
| 6 | Per-tenant BYOK client, never shared (T-24-19, the critical fix) | VERIFIED | `run_batch_prewarm()` (batch.py:210) and `poll_pending_batches()` (batch.py:390) both build `client = (anthropic_client_factory or _default_client_factory)(key)` INSIDE their per-tenant/per-job loop iteration, immediately after resolving that iteration's own key. `_default_client_factory(api_key)` (explain.py:115-121) constructs a fresh `AsyncAnthropic(api_key=api_key, max_retries=2)` — never a singleton. `grep -c "AsyncAnthropic()" batch.py` == 0 (bare/shared construction impossible). `test_run_batch_prewarm_uses_per_tenant_key` and `test_poll_uses_per_tenant_key` (both read in full) seed TWO tenants with DISTINCT keys and assert each tenant's submitted/retrieved batch used only its own key — genuinely non-vacuous, both pass. |
| 7 | Durable `AiBatchJob` registry (Postgres, not memory) | VERIFIED | `class AiBatchJob(Base, UUIDPrimaryKeyMixin, TimestampMixin)` (models.py:52-89) + migration `033_add_ai_batch_job.py`. Live `alembic upgrade head` -> `downgrade -1` -> `upgrade head` round-tripped cleanly (executed directly, not trusted from SUMMARY); `alembic heads` shows a single clean head (`033_add_ai_batch_job`). `poll_pending_batches()` selects `AiBatchJob.status == "in_progress"` directly from Postgres on every call (batch.py:375) — no in-memory dict anywhere in the retrieval path. |
| 8 | Scheduler dispatch discipline (never inline-await) | VERIFIED | Same evidence as truth #3; additionally `test_batch_blocks_are_non_blocking` (read in full) proves via an `asyncio.Event` set only after `await asyncio.sleep(0.05)` that both dispatchers return control BEFORE the slow fake completes — a genuine non-blocking proof, not just a grep. |
| 9 | Batch cost booked at 50% of interactive rate; budget pre-estimate fail-closed BEFORE `batches.create()` | VERIFIED | `estimate_batch_cost_usd()` (batch.py:157) and `validate_and_cache_batch_result()` (batch.py:507) both apply `* 0.5`. Code-order confirmed by line number: `est = await estimate_batch_cost_usd(...)` (line 259) -> `if await would_exceed_budget_for_batch(...)` (line 261, `continue`s with NO create on breach) -> `batch = await client.messages.batches.create(...)` (line 278, only reached if not exceeded). `would_exceed_budget_for_batch()` (budget.py) returns `True` (skip) iff a cap is configured and `spent + estimate >= cap`; `None` cap never skips. |
| 10 | Message Batches API is poll-only, whole-batch-atomic | VERIFIED | `poll_pending_batches()` gates `client.messages.batches.results(...)` (batch.py:402) strictly behind `refreshed.processing_status != "ended": continue` (line 392) — `results()` is never called on a still-in-progress batch. Live SDK introspection (anthropic==0.120.2 installed) confirms `Request`/`MessageCreateParamsNonStreaming` (construction side) are TypedDicts that instantiate as plain `dict` at runtime (attribute access raises `AttributeError`; dict-style access — `req["params"]["system"]` — works), while `MessageBatchIndividualResponse`/`MessageBatchSucceededResult` (retrieval side) genuinely subclass `pydantic.BaseModel` (attribute access is correct there). This confirms the documented "reversed" deviation (dict-style read in `estimate_batch_cost_usd`) is a **correct fix against the real installed SDK, not a defect** — verified directly, not trusted from the SUMMARY. |

**Score:** 10/10 truths VERIFIED at the code+test level. 4 live/manual items remain open (see Human Verification Required) — these are explicitly waived-at-the-tracer-gate items per user instruction, not failures.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/ai/grounding.py::get_prioritization_context()` | Tenant-scoped, PII-excluding, department-only-owner grounding query | VERIFIED | 330-386; 10-key dict, None-on-miss/cross-tenant, outer-joined asset tolerance |
| `backend/app/ai/schemas.py::ExplainPrioritizationResponse` | Zero-field no-rank schema | VERIFIED | 96-105; live introspection confirms 4 base fields, zero numeric |
| `backend/app/ai/prompt_builder.py` (5th quadruplet) | `PRIORITIZATION_ALLOWLIST`, `AllowlistedPrioritization`, `build_explain_prioritization_prompt`, `prioritization_prompt_version` | VERIFIED | 1032-1231; 10-field allowlist, `extra="forbid"`, D-08 no-verdict instruction literal in `SYSTEM_PROMPT_PRIORITIZATION` |
| `backend/app/api/v1/ai/explain_prioritization.py` | POST require_analyst SSE + GET require_viewer cache-check, `_is_finding_queued()` | VERIFIED | Full file read; registered in `__init__.py`; no `dangerous_pattern_check`, no pre-gen refuse gate (confirmed absent) |
| `frontend/src/components/ai/ai-explanation-section.tsx` | `isPrioritization` discriminator, Clock-icon queued branch before trigger branch | VERIFIED | Line 181 (`isPrioritization`), line 320 (`queued === true`) precedes line 343 (`isAnalystOrAbove` trigger) |
| `frontend/src/lib/queries/use-explain-cache.ts` | `queued?: boolean` on cache-miss arm | VERIFIED | Line 25 |
| `frontend/src/components/vulnerabilities/drill-content.tsx` | Prioritization section between AI Explanation and Remediation | VERIFIED | Lines 293-312; exactly 3 props, `onCopyToDescription` correctly omitted |
| `frontend/tests/no-ai-rank.test.ts` | Grep-provable No-Rank CI check | VERIFIED | Exists, 4/4 tests pass (executed live) |
| `backend/app/ai/models.py::AiBatchJob` + `alembic/versions/033_add_ai_batch_job.py` | Durable batch registry + migration | VERIFIED | Model read in full; migration round-tripped live (upgrade/downgrade/upgrade), single clean head |
| `backend/app/vulnerabilities/service.py::get_top_findings_for_ai_batch()` | D-01 top-N query (risk_score primary, KEV/CVSS/SLA tiebreak) | VERIFIED | Lines 527-571; `nulls_last(desc(Asset.risk_score))` primary, OPEN+IN_PROGRESS filter |
| `backend/app/ai/budget.py::would_exceed_budget_for_batch()` | Fail-closed pre-submission check | VERIFIED | Full file read; `check_tenant_budget()`'s contract provably unchanged (delegates to extracted `get_month_to_date_spend()`) |
| `backend/app/redis_client.py::get_redis_client()` | Non-request Redis factory, single construction site | VERIFIED | main.py lifespan calls it; `grep -c "redis.Redis(connection_pool" main.py` == 0 |
| `backend/app/ai/batch.py` | `estimate_batch_cost_usd`, `run_batch_prewarm`, `validate_and_cache_batch_result`, `poll_pending_batches` | VERIFIED | Full 521-line file read; all four present, no shared-client param on either public entry point |
| `backend/app/connectors/scheduler.py` | `_dispatch_ai_batch_prewarm`/`_dispatch_ai_batch_poll`, `_last_ai_batch_prewarm` global | VERIFIED | Lines 21, 72-126, 254-255 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `explain_prioritization.py` POST | `_run_explain_stream(resource_type="prioritization", ...)` | Shared engine reuse, no `dangerous_pattern_check` | WIRED | Confirmed by direct read; engine imported unchanged from `app.ai.explain` |
| `explain_prioritization.py` GET | `build_cache_key(..., "prioritization", ..., prioritization_prompt_version())` | Cache-check, no model call | WIRED | Same cache-key formula used by GET route and by `run_batch_prewarm()`/`poll_pending_batches()` — a batch-warmed narrative is a plain cache hit (D-06) |
| `explain_prioritization.py` GET miss | `_is_finding_queued()` -> `AiBatchJob` JSONB containment | Tenant-scoped `custom_id_hash_map.has_key(...)` | WIRED | Query read in full; scoped by `tenant_id` + `status="in_progress"` |
| `drill-content.tsx` | `AiExplanationSection resourceType="prioritization"` | Section mount between drill-ai-h and drill-remed-h | WIRED | Verified by line-number ordering (293 < 306 < 314) |
| `use-explain-cache.ts` | `GET /api/v1/ai/explain-prioritization/{id}` | Generic `resourceType`-interpolated fetch | WIRED | Hook path template matches the registered route path exactly |
| `run_batch_prewarm()` per-tenant loop | `get_tenant_anthropic_key()` -> fresh `_default_client_factory(key)` | Per-tenant BYOK client construction, inside the loop | WIRED | Proven by `test_run_batch_prewarm_uses_per_tenant_key` (two tenants, two distinct keys, distinct submitted batch IDs) |
| `poll_pending_batches()` per-job loop | `get_tenant_anthropic_key(job.tenant_id)` -> fresh client | Per-job BYOK client construction | WIRED | Proven by `test_poll_uses_per_tenant_key` |
| `scheduler.py::_scheduler_loop()` | `_dispatch_ai_batch_prewarm()` / `_dispatch_ai_batch_poll()` | Awaited inline (safe — thin wrappers only gate+create_task) | WIRED | Lines 254-255; wrappers themselves never inline-await the batch functions |
| `run_batch_prewarm()` cost estimate | `would_exceed_budget_for_batch()` -> `client.messages.batches.create()` | Fail-closed gate before spend | WIRED | Sequential line numbers confirmed: 259 -> 261 (skip-and-continue on breach) -> 278 |
| `poll_pending_batches()` succeeded result | `validate_and_cache_batch_result()` -> `set_cached()` | Single-pass validation, no retry | WIRED | `grep -c "range(2)\|for attempt"` batch.py == 0 (confirmed no retry loop) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `AiExplanationSection` (resourceType='prioritization') | `cacheQuery.data` / `state.data` | `useExplainCache` (real GET) / `useExplainStream` (real SSE POST) | Yes — both hit the real registered route, which queries `get_prioritization_context()` against real `Vulnerability`/`Asset` rows | FLOWING |
| `run_batch_prewarm()` requests list | `get_prioritization_context()` per finding | `get_top_findings_for_ai_batch()` (real DB query) | Yes — top-N selection is a real ORDER BY against real `Asset.risk_score`/`Vulnerability` columns, not a static list | FLOWING |
| `_is_finding_queued()` `queued` boolean | `AiBatchJob.custom_id_hash_map` JSONB containment | Real Postgres row written by `run_batch_prewarm()`'s own INSERT | Yes — same table both writer and reader touch; confirmed via the durable round-trip test in a fresh session | FLOWING |

No hollow props or disconnected data sources found — every artifact that renders or gates on data traces to a real query or a real upstream write, not a static/hardcoded value.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend Phase 26 unit suites (grounding, schema, prompt-builder, route, batch-job model) | `pytest tests/test_ai_grounding_prioritization.py tests/test_ai_schemas.py tests/test_ai_prompt_builder_prioritization.py tests/test_ai_explain_prioritization.py tests/test_ai_batch_job.py -q` | 46 passed | PASS |
| Backend batch submitter/poller, top-N query, budget, scheduler dispatch | `pytest tests/test_ai_batch.py tests/test_top_findings_for_ai_batch.py tests/test_ai_budget.py tests/test_scheduler_ai_batch.py -q` | 42 passed | PASS |
| Backend full AI wave-merge regression | `pytest tests/test_ai_*.py tests/test_scheduler_ai_batch.py tests/test_top_findings_for_ai_batch.py -q` | 243 passed | PASS |
| Connector-health regression (scheduler.py touched) | `pytest tests/test_connector_health.py -q` | 9 passed | PASS |
| Migration round-trip | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | Clean, no errors, single head `033_add_ai_batch_job` | PASS |
| mypy CI gate on touched files | `mypy app/ \| mypy-baseline filter --allow-unsynced` + isolated per-file greps | "3 new / 3 fixed" — independently diffed: all 6 lines are the pre-existing `types-python-jose` note-line-drift artifact (moved from `google_workspace.py` to `auth/dependencies.py`), zero real errors in any Phase-26-touched file | PASS |
| Live SDK introspection: Request/MessageCreateParamsNonStreaming runtime shape | `python -c "... type(Request(...))"` against installed `anthropic==0.120.2` | Confirmed `dict` at runtime, attribute access raises `AttributeError`, dict-style access works; response-side types confirmed `pydantic.BaseModel` | PASS (confirms documented deviation is correct, not a defect) |
| Frontend No-Rank CI check | `npx vitest run no-ai-rank` | 4 passed | PASS |
| Frontend Prioritization UI + drill-panel placement | `npx vitest run ai-explanation-section drill-panel` | 89 passed (3 files) | PASS |
| Frontend full regression | `npx vitest run` | 853 passed (131 files) | PASS |
| Git commit provenance | `git log --oneline --all \| grep -E "<16 claimed hashes>"` | All 16 task commits found | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| AIP-01 | 26-01, 26-02, 26-03, 26-04, 26-05 | Analyst sees a "what to fix first and why" narrative that augments/explains, never replaces, the deterministic score | SATISFIED (code+test level) | Truths #1, #2, #4, #5 above. **REQUIREMENTS.md checkbox note:** the checkbox is currently `[ ]` Pending — every plan in this phase deliberately deferred flipping it to phase-completion review (26-01 through 26-08-SUMMARY.md all document this explicitly, and 26-08-SUMMARY.md explicitly asks the verifier to make the call). Given the functional evidence above is complete and test-proven end-to-end, this appears to be a **stale documentation field, not a missing capability** — recommend flipping AIP-01 to Complete in REQUIREMENTS.md as part of phase closure. Not treated as a code gap. |
| AIP-02 | 26-06, 26-07, 26-08 | Prioritization suggestions generated in bulk via the scheduler using the Message Batches API, respecting the tenant's key | SATISFIED — confirmed genuinely end-to-end, not just checkbox-deep | Truths #3, #6, #7, #8, #9, #10 above. REQUIREMENTS.md's `[x]` mark is corroborated: durable registry exists, scheduler dispatches both halves via `create_task`, per-tenant BYOK isolation is test-proven on both submit and poll sides, budget is fail-closed before spend, and cost is booked at 50%. Only the LIVE wall-clock round-trip against the real Anthropic API is unproven (see Human Verification). |

**Orphaned requirements check:** `REQUIREMENTS.md`'s traceability table maps exactly AIP-01 and AIP-02 to Phase 26 — no additional requirement IDs are mapped to this phase that aren't already declared across the 8 plans' frontmatter. No orphans.

### Anti-Patterns Found

None. Scanned every file this phase modified (`grounding.py`, `schemas.py`, `prompt_builder.py`, `models.py`, `budget.py`, `redis_client.py`, `explain_prioritization.py`, `vulnerabilities/service.py`, `batch.py`, `scheduler.py`, plus the 6 frontend files) for `TODO|FIXME|XXX|HACK|PLACEHOLDER`, empty handlers, and hardcoded-empty stub patterns. The only hit (`_GENERIC_REMEDIATION_PLACEHOLDERS` in `grounding.py`) is pre-existing Phase-25 code unrelated to this phase's diff, not a stub introduced here.

**One item independently re-confirmed as correctly-NOT-a-finding** (per explicit task instruction, verified rather than assumed): `estimate_batch_cost_usd()` reads the Anthropic `Request`/`MessageCreateParamsNonStreaming` payload via dict-style access (`req["params"][...]`), not attribute access. Live introspection against the installed `anthropic==0.120.2` SDK confirms these ARE `TypedDict` subclasses that construct plain `dict` instances at runtime — attribute access genuinely raises `AttributeError`. This is the correct implementation against the real SDK; the PLAN's own literal instruction (and its own grep-based acceptance criterion) was wrong, and the executor's documented deviation is a bug fix, not a defect. `test_estimate_batch_cost_discount` passes.

### Human Verification Required

These items were explicitly waived by the user at the 26-05 tracer gate (proceed-on-trust, mirroring the 24-06/25-05 precedent) and remain open. They are reported here as required per instruction — NOT as gaps or failures. Every automated substitute (fake-client-injected tests, static CI greps, migration round-trips) that CAN be run without a live key/browser has been run and is green.

### 1. Live prioritization narrative render

**Test:** Configure a tenant's own Anthropic key via the connector wizard; as an Analyst, open a finding's drill panel and click "Explain the priority."
**Expected:** An "Analyzing…" state, then a plain-English cited narrative explaining the deterministic score's drivers (KEV/exploit/CVSS/EPSS/SLA/department), with `scanner_verbatim` tint and `ai_interpreted` tags, and no independent priority number ever rendered.
**Why human:** Requires a live Docker stack, a real Anthropic API key, and visual browser confirmation — code-level and automated-test evidence (46+93 tests) is complete, but the actual model call and its rendered output have not been observed live.

### 2. Live no-AI-rank sweep across every list/table view

**Test:** With the stack running, visually scan `/vulnerabilities`, the dashboard, the drill panel, and `/tickets` for any AI-derived rank column, sort control, or numeric badge.
**Expected:** None found anywhere; the deterministic ASSET-02 score is the only sortable number.
**Why human:** The static CI check (`no-ai-rank.test.ts`, 4/4 green) and an independent broad source-grep (zero matches project-wide) both pass, but neither is a substitute for a live visual sweep of rendered pages.

### 3. Live end-to-end Message Batches round-trip

**Test:** Trigger (or wait for) the nightly `run_batch_prewarm()` against a real tenant with a configured key; confirm an `AiBatchJob` row is created, transitions to `completed` after the poller runs, and that the resulting narrative renders as a cache hit in the drill panel.
**Expected:** A real submitted batch (`anthropic_batch_id` populated), completion within the documented up-to-24h window, and a batch-warmed narrative that renders identically to an on-demand one.
**Why human:** This is an asynchronous, potentially 24h-long round-trip against the real Anthropic Batches API, requiring real spend and wall-clock time. Every test in this phase (`test_ai_batch.py`, `test_scheduler_ai_batch.py`) injects a fake client via the `anthropic_client_factory` seam — this is by design (mirrors every prior AI phase's accepted gap) and is not fixable without a live key.

### 4. WCAG AA contrast of the new pending card + citation tiers

**Test:** Run an axe/Playwright accessibility sweep against a live prod build covering the new Clock-icon pending card and the reused citation tinting.
**Expected:** AA contrast compliance.
**Why human:** Per established project convention (no axe sweep was run against a live prod build during this phase's execution) — WCAG AA claims are treated as unproven until that sweep runs, consistent with how prior AI phases (24, 25) were verified.

### Gaps Summary

No code-level gaps were found. Every observable truth resolved to VERIFIED against direct evidence: source reads of the actual implementation (not SUMMARY prose), live pytest/vitest execution (46+42+243+9 backend, 4+89+853 frontend, all green), a live `alembic upgrade/downgrade/upgrade` round-trip, and live Python introspection of the installed `anthropic==0.120.2` SDK that independently confirmed the one documented "reversed" implementation detail (dict-style Request access) is correct against the real SDK rather than a defect.

The phase's stated status is `human_needed`, not `passed`, solely because four items require a live browser/live key/wall-clock time that this environment does not have — consistent with the user's explicit instruction to report these as human_verification rather than gaps, and consistent with the precedent already accepted at the 24-06/25-05/26-05 tracer gates. There is no evidence of a stub, a hollow prop, an unwired artifact, or a cross-tenant key leak anywhere in this phase's diff.

One non-blocking documentation note: `REQUIREMENTS.md`'s AIP-01 checkbox remains `[ ]` Pending despite the underlying capability being code-complete and test-proven end-to-end (every plan in this phase deliberately deferred this exact decision to phase verification). Recommend flipping it to Complete as part of phase closure — this is a documentation-sync action, not a code gap, and does not block progressing past this phase.

---

_Verified: 2026-07-31T15:42:36Z_
_Verifier: Claude (gsd-verifier)_
