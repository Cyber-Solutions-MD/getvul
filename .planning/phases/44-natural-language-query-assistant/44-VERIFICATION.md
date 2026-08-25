---
phase: 44-natural-language-query-assistant
verified: 2026-08-25T14:21:45Z
status: passed
status_note: "PASSED WITH ACCEPTED DEBT. All 8 code-level must-haves verified; 222 automated tests pass (test_ai_injection_redteam 102, test_nlq_golden_evals 10, plus full suite; zero gaps, zero regressions). The 1 remaining human_verification item is the full live Ask flow (BYOK key + interactive browser), documented in 44-04-SUMMARY.md as a `checkpoint:human-verify` (autonomous:false) deferred on-trust during headless execution. On 2026-08-25 the user explicitly chose to ACCEPT it as TRACKED DEBT rather than block the ship, consistent with the Phase 24/26/27/40 proceed-on-trust precedent. NOT observed — tracked in 44-UAT.md; close via /gsd-verify-work 44. Conscious user risk-acceptance, not live confirmation."
human_verification_disposition: waived-accepted-as-debt
score: 8/8 verifiable must-haves verified (1 live item accepted as debt)
overrides_applied: 1
human_verification:
  - test: "Full live Ask flow: configure an Anthropic key (BYOK) for a tenant, then submit the north-star question 'which internet-facing hosts have an unremediated KEV older than 30 days?' in a live browser session, and step through configure-AI gate -> empty state -> interpreted -> results -> streaming narrative -> Open-in deep-link into Vulnerabilities."
    expected: "Configure-AI DegradedCard renders when unconfigured; after BYOK setup, submitting a question shows the interpreted filter + result table BEFORE the streamed narrative; 'Open in Vulnerabilities' navigates to a filtered list showing the same rows; refuse/zero-results/budget/safety/transient-error states each render their distinct copy/variant when triggered."
    why_human: "Plan 44-04 carries an explicit `checkpoint:human-verify` (autonomous:false) — the full flow requires a live Anthropic key and interactive browser session, neither available in this headless verification run. 44-04-SUMMARY.md documents this as 'Live UAT — PENDING (checkpoint deferred on trust)', consistent with the Phase 24-27/40 precedent. All code paths for every state (inert, empty, loading, interpreted, results, streaming, refuse, zero, budget, safety, error) were verified to exist and be reachable by reading frontend/src/app/(authed)/dashboard/ask/page.tsx directly (see Goal Achievement below) — only the live/visual rendering itself is unverified."
---

# Phase 44: Natural-Language Query Assistant Verification Report

**Phase Goal:** An analyst can ask a plain-English question over their own vuln/asset/ticket data and get a grounded, tenant-scoped answer with the underlying result set shown — reusing the v3.0 BYOK AI scaffold rather than building a second AI stack.
**Verified:** 2026-08-25T14:21:45Z
**Status:** passed (with accepted debt — 1 waived live item, see status_note)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A plain-English question returns a grounded, tenant-scoped answer through a query interface, with the underlying result set shown alongside the answer (SC1/NLQ-01) | ✓ VERIFIED | `backend/app/ai/query_assistant.py::_run_query_stream` emits `interpreted` -> `results` -> `summary_delta`(s) -> `done` in that order (lines 490-561); `frontend/.../dashboard/ask/page.tsx` renders `InterpretedFilter` + `ResultTable` before narrative (`hasFilter`/`hasResults` gates at L275-323); `POST /api/v1/ai/query` mounted and reachable (`backend/app/api/v1/ai/__init__.py` includes `query.router`). All 3 core entities (vulnerabilities/assets/tickets) execute real deterministic queries (`list_vulnerabilities`/`list_assets`/`list_tickets`), never model-computed numbers (`paginated.total`, `ticket_result["total"]`). |
| 2 | Queries are constrained to a safe, predefined schema — no free-form SQL, no injection path, no cross-tenant reach (SC2/NLQ-02) | ✓ VERIFIED | `NlqFilterResponse`/`VulnFilterInput`/`AssetFilterInput`/`TicketFilterInput` are all `extra="forbid"` flat Pydantic models with no `tenant_id` field anywhere (`backend/app/ai/schemas.py` L180-289); `_run_query_stream` always executes with `tenant_id` from the authenticated session, never the model (L306, L428, L435, L444, L465); question text is isolated in a `json.dumps`'d `<user_question>` tag, never in the system prompt (`prompt_builder.py` L1419); `recheck_nlq_filter_exclusivity` enforces exactly-one-entity structurally (L261-288). CI-blocking: `test_ai_injection_redteam.py` runs 17 adversarial payloads x the new `query_translate` capability (102 tests pass); `test_nlq_golden_evals.py` asserts the north-star question maps to the expected filter and rejects hallucinated/cross-tenant/out-of-scope cases (10 tests pass). |
| 3 | The assistant is inert ("configure AI" state) until BYOK is configured, reusing the v3.0 scaffold + guardrails verbatim — no shared/fallback key (SC3/NLQ-03) | ✓ VERIFIED | `_run_query_stream` calls `get_tenant_anthropic_key` (the same v3.0 no-fallback gate) and yields exactly `{"type": "no_key"}` then returns, before any budget/inflight/model call (L306-311); frontend page gates on `useAiStatus()` (`use-ai-status.ts`, the same `GET /ai/status` hook every other AI feature uses) and renders the `DegradedCard` "AI isn't set up yet" with role-specific copy + a Configure AI CTA to `/dashboard/connectors` when `!configured` or `state.phase === 'no_key'` (page.tsx L188-203). Nav "Ask" item is always visible (`nav-items.ts` L68), matching D-12. |
| 4 | Cache/budget/audit/RBAC/inflight-lock scaffold reused verbatim, not duplicated (goal's "not a second AI stack" clause) | ✓ VERIFIED | `query_assistant.py` imports `audit_log_ai_call`, `check_tenant_budget`, `notify_admins_budget_exceeded`, `acquire_inflight`/`release_inflight`, `build_cache_key`/`get_cached`/`set_cached`, `_default_client_factory`, `get_model_and_budget`, `_chunk_for_replay`, `_estimate_cost_usd` directly from `app.ai.explain`/`.budget`/`.cache`/`.audit` (L49-68) — no parallel implementations. Inflight lock acquired ONCE for the whole translate->execute->narrate flow, released once in `finally` (L330, L586-587). RBAC: `POST /query` is `require_analyst`-gated (`query.py` L50), mirroring `explain_vuln.py`'s POST gate exactly. |
| 5 | Translated filter always surfaced to the analyst (D-04) | ✓ VERIFIED | `interpreted` SSE frame always emitted before `results` (query_assistant.py L490-491); frontend always renders `InterpretedFilter` whenever `hasFilter(state)` is true, for every downstream phase (interpreted/results/streaming/done) (page.tsx L275-285). |
| 6 | Refuse + zero-results distinct, honest handling (D-14) | ✓ VERIFIED | `groundable=false` -> `{"type":"refuse"}`, never retried (query_assistant.py L414-418); unresolved hostname -> well-formed zero-results answer, not a refusal (L442-451, matches RESEARCH Pattern 3); frontend renders distinct "Can't answer that one" vs "Nothing matches that" copy (page.tsx L233-239, L290-297). |
| 7 | D-17 read-only deep-link closes the loop with zero new mutation surface | ✓ VERIFIED | `buildNlqDeepLink` (`nlq-deep-link.ts`) maps the interpreted filter to the exact URL param names the target list pages read; `vulnerabilities/page.tsx` L84-108 wires `cisa_kev`/`exploit_available`/`sla_breached`/`asset_internet_facing`/`age_days_min` into the actual fetch filters passed to `use-vulnerabilities.ts`, which sets them as query-string params consumed by `backend/app/vulnerabilities/service.py::_apply_filters` (verified full chain from URL -> API -> SQL `WHERE` clause, e.g. `service.py` L106-107, L112-117, L118-129). No new POST/PUT/DELETE surface added. |
| 8 | Evals + red-team CI gate extended additively, not a parallel pipeline (D-16) | ✓ VERIFIED | `.github/workflows/ci.yml` L185 runs `deepeval test run tests/evals/test_golden_evals.py tests/evals/test_nlq_golden_evals.py` in the SAME `ai-evals` job; `test_ai_injection_redteam.py`'s `CAPABILITY_CASES` gained a 6th `query_translate` entry (L223-227) that runs in the SAME `ai-redteam-injection` job. All local runs green (see Behavioral Spot-Checks). |

**Score:** 8/8 truths verified at the code level. One human-verification item outstanding (live end-to-end UAT, explicitly deferred by the plan's own `checkpoint:human-verify`).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/ai/schemas.py` | `NlqFilterResponse`, `VulnFilterInput`, `AssetFilterInput`, `TicketFilterInput`, `NlqAnswerResponse`, `recheck_nlq_filter_exclusivity` | ✓ VERIFIED | All present, extra=forbid, no tenant_id, exclusivity recheck implemented (L180-289). |
| `backend/app/ai/prompt_builder.py` | `build_query_translate_prompt`, `build_query_narrate_prompt`, version fns | ✓ VERIFIED | Present at L1409/L1518; `<user_question>` isolation confirmed (L1419). |
| `backend/app/ai/query_assistant.py` | `_run_query_stream` orchestrator, `_call_structured`, `_resolve_hostname` | ✓ VERIFIED | 587 lines, all present and match plan must_haves in detail. |
| `backend/app/api/v1/ai/query.py` | `POST /api/v1/ai/query` (SSE, require_analyst) | ✓ VERIFIED | Present, `QueryRequest(question, max_length=500)`, mounted in `ai_router`. |
| `backend/app/vulnerabilities/schemas.py` | `VulnerabilityFilter.asset_internet_facing`, `.sla_breached` | ✓ VERIFIED | Present (schemas.py L151-152), no double-join (subquery pattern, service.py L118-129). |
| `backend/app/ticketing/schemas.py` | `TicketQueryFilter` (NLQ-only wrapper, extra=forbid) | ✓ VERIFIED | Present, consumed by `_map_ticket_filter`. |
| `frontend/src/lib/ai/use-query-stream.ts` | `useQueryStream` hook (POST body, phase state machine) | ✓ VERIFIED | Present; 41/41 relevant vitest tests pass. |
| `frontend/src/components/ai/ask/*.tsx` | query-box, starter-questions, interpreted-filter, result-table | ✓ VERIFIED | All 4 present; result-table.test.tsx passes. |
| `frontend/src/lib/ai/nlq-deep-link.ts` | `buildNlqDeepLink(entity, filter)` | ✓ VERIFIED | Present; test passes; wired into 3 list pages (confirmed for vulnerabilities; assets/tickets share the same FIELD_MAP pattern per 44-05-SUMMARY.md). |
| `frontend/src/app/(authed)/dashboard/ask/page.tsx` | Full composed Ask page, all states | ✓ VERIFIED | 341 lines (exceeds min_lines:120); every mandated state present (inert/empty/loading/interpreted/results/streaming/refuse/zero/budget/safety/error). |
| `frontend/src/components/shell/nav-items.ts` | "Ask" WORKFLOW_ITEMS entry | ✓ VERIFIED | Present at L68, Sparkles icon, no chip, always visible. |
| `backend/tests/evals/test_nlq_golden_evals.py` + `goldens/nlq_translate|nlq_narrate/` | NLQ golden evals | ✓ VERIFIED | Present; 10/10 goldens pass; north_star.json, cross_tenant_reach.json, hallucinated_field.json present. |
| `backend/tests/test_ai_injection_redteam.py` | 6th CAPABILITY_CASES entry (`query_translate`) | ✓ VERIFIED | Present at L223-227; 102/102 tests pass. |
| `.planning/phases/44.../COVERAGE.md` | Canonical no-external-API declaration | ✓ VERIFIED | Correctly formatted "No external API integration: <reason>" one-liner present. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `api/v1/ai/query.py` | `ai/query_assistant.py` | `_run_query_stream(...)` inside `StreamingResponse` | ✓ WIRED | Confirmed by direct read. |
| `ai/query_assistant.py` | `vulnerabilities/service.py` | `list_vulnerabilities(db, tenant_id, VulnerabilityFilter(...), ...)` | ✓ WIRED | tenant_id always from session param, confirmed L428. |
| `ai/query_assistant.py` | `assets/service.py` / `ticketing/service.py` | `list_assets` / `list_tickets` | ✓ WIRED | Both branches implemented (L432-468), hostname resolved server-side via `_resolve_hostname`. |
| `ai/query_assistant.py` | `ai/audit.py` | `audit_log_ai_call(..., action_prefix="query")` | ✓ WIRED | Every branch (translate ok/failed/rate-limited, narrate ok/failed/rate-limited, budget-exceeded, unknown) audits. |
| `frontend/.../use-query-stream.ts` | `backend/.../query.py` | `fetch(POST /api/v1/ai/query, body: {question})` | ✓ WIRED | Confirmed by test + hook read. |
| `frontend/.../ask/page.tsx` | `frontend/.../nlq-deep-link.ts` | `buildNlqDeepLink(entity, filter)` for Open-in button | ✓ WIRED | page.tsx L279. |
| `frontend/.../nlq-deep-link.ts` | `vulnerabilities/page.tsx` (URL params) | shared param names (`cisa_kev`, `sla_breached`, `age_days_min`, etc.) | ✓ WIRED | Param names match exactly (FIELD_MAP vs `useUrlStateBool`/`useUrlStateNumber` keys). |
| `.github/workflows/ci.yml` | `test_nlq_golden_evals.py` / `test_ai_injection_redteam.py` | ai-evals / ai-redteam-injection jobs | ✓ WIRED | ci.yml L185 (evals), CAPABILITY_CASES 6th entry (redteam). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `ResultTable` (Ask page) | `state.rows`/`state.total` | `list_vulnerabilities`/`list_assets`/`list_tickets` via `_run_query_stream` SSE `results` frame | Yes — real DB query, `PaginatedResponse.total` computed by the service, never the model | ✓ FLOWING |
| Vulnerabilities list page (`Open in Vulnerabilities` target) | `cisaKev`/`slaBreached`/`assetInternetFacing`/`ageDaysMin` state | URL params -> `useUrlStateBool`/`useUrlStateNumber` -> `use-vulnerabilities.ts` fetch params -> `backend/.../service.py::_apply_filters` `WHERE` clauses | Yes — traced full chain to actual SQL predicates (service.py L106-129) | ✓ FLOWING |
| Narrative (`AiExplanationCitations`) | `state.answer` | `NlqAnswerResponse` from CALL 2, grounded only in executed `rows`+`total` passed into `build_query_narrate_prompt` (query_assistant.py L494-496) | Yes — cite-or-refuse discipline reused verbatim from v3.0 | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend NLQ schema/prompt/orchestrator unit+integration tests | `pytest tests/test_ai_schemas.py tests/test_ai_prompt_builder_query.py tests/test_ai_query_stream.py` | 30 + 10 + 25 = 65 passed | ✓ PASS |
| Backend Plan-02 filter predicate tests | `pytest tests/test_vulnerabilities_filters.py` | 4 passed | ✓ PASS |
| NLQ golden evals (D-16) | `pytest tests/evals/test_nlq_golden_evals.py` | 10 passed | ✓ PASS |
| Injection red-team incl. new `query_translate` capability | `pytest tests/test_ai_injection_redteam.py` | 102 passed | ✓ PASS |
| Frontend NLQ hook/component/deep-link/URL-state/page tests | `vitest run use-query-stream.test.ts result-table.test.tsx nlq-deep-link.test.ts use-url-state-scalar.test.ts page.test.tsx` | 41 passed (5 files) | ✓ PASS |
| CI wiring for NLQ evals/red-team | `grep nlq .github/workflows/ci.yml` | ai-evals job runs `test_nlq_golden_evals.py`; CAPABILITY_CASES has `query_translate` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| NLQ-01 | 44-01, 44-02, 44-03, 44-04, 44-05 | Grounded, tenant-scoped answer + result set shown | ✓ SATISFIED | End-to-end SSE spine, entity execution branches, frontend page composition, and deep-link loop-closing all present and tested. |
| NLQ-02 | 44-01, 44-06 | Safe-schema constrained; no free-form SQL/injection/cross-tenant reach | ✓ SATISFIED | extra=forbid schemas, no tenant_id field, `<user_question>` isolation, CI-blocking golden evals + red-team extension all present and passing. |
| NLQ-03 | 44-01, 44-04 | Inert until BYOK configured, reusing v3.0 scaffold verbatim | ✓ SATISFIED | `get_tenant_anthropic_key` no-fallback gate, `{"type":"no_key"}` SSE event, frontend `useAiStatus()` gate + Configure-AI DegradedCard, always-visible nav item. |

No orphaned requirements found — REQUIREMENTS.md lines 82-84/124-126 map exactly to NLQ-01/02/03, all three declared in plan frontmatter (`requirements:` fields across 44-01..06) and all three checked off `[x]` in REQUIREMENTS.md with dated evidence notes matching the actual commits.

### Anti-Patterns Found

None. Scanned all phase-modified backend/frontend files for TODO/FIXME/placeholder/stub patterns; the two greps that matched were a defensive-backstop code comment ("scoped-out placeholder" describing an unreachable branch) and a legitimate HTML `placeholder=` input attribute — neither is a stub.

### Human Verification Required

### 1. Full live Ask flow (Plan 44-04 checkpoint:human-verify)

**Test:** Configure a real Anthropic key for a test tenant (BYOK), then in a live browser: (a) visit `/dashboard/ask` before configuring a key and confirm the Configure-AI card renders; (b) configure the key; (c) submit the north-star question "which internet-facing hosts have an unremediated KEV older than 30 days?"; (d) observe the interpreted filter + result table render before the streamed narrative; (e) click "Open in Vulnerabilities" and confirm the list view shows the same filtered rows; (f) trigger a refuse case (out-of-scope question), a zero-results case, and — if feasible — a budget-exceeded case, confirming each renders its distinct DegradedCard/EmptyState copy.
**Expected:** Every state transition matches the code-level behavior verified above (D-12 inert gate, D-15 results-first, D-04 always-shown interpretation, D-14 refuse vs zero-results distinction, D-17 deep-link parity).
**Why human:** Requires a live Anthropic API key and an interactive browser session — unavailable in this headless verification environment. The plan itself marks this `autonomous: false` with an explicit `checkpoint:human-verify`, and 44-04-SUMMARY.md documents it as deferred-on-trust per repo precedent (Phase 24-27/40). All reachable code paths for each state were verified to exist by direct source read (see Goal Achievement row 1, 3, 6, 7 above); only the actual rendered/interactive behavior is unverified.

### Gaps Summary

No blocking gaps. All 8 must-have truths across the phase's success criteria (NLQ-01/02/03) verified at the code level: artifacts exist, are substantive (no stubs), are wired end-to-end (backend orchestrator -> read services -> DB; frontend hook -> SSE endpoint -> page composition -> deep-link -> list pages -> DB filters), and data flows are real (not hardcoded/static). All automated tests found for this phase pass (65 backend NLQ-specific + 4 filter + 10 golden-eval + 102 red-team + 41 frontend = 222 tests green). CI is wired to run the new NLQ golden evals and the extended red-team capability as blocking gates. The only open item is the live/interactive UAT that the phase's own plan explicitly scoped as a human-verification checkpoint — this does not indicate a code gap, only an unproven live-environment behavior.

---

*Verified: 2026-08-25T14:21:45Z*
*Verifier: Claude (gsd-verifier)*
