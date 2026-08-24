# Phase 44: Natural-Language Query Assistant - Context

**Gathered:** 2026-08-24
**Status:** Ready for planning

<domain>
## Phase Boundary

An analyst types a **plain-English question over their own tenant's vuln / asset / ticket data** and gets a **grounded, tenant-scoped answer with the underlying result set shown**. The question is translated into a **safe, predefined query** (no free-form SQL, no injection path, no cross-tenant reach), executed deterministically, and the answer narrates only what the query returned. The whole capability is built on the **shipped v3.0 BYOK AI scaffold** — reusing its key storage, guardrails, cache/budget/audit, and streaming discipline verbatim — and is **inert ("configure AI") until the tenant configures their own Anthropic key** (BYOK, no shared/fallback key).

Delivers NLQ-01 (grounded tenant-scoped answers + result set), NLQ-02 (safe-schema constrained, no injection / cross-tenant reach), NLQ-03 (BYOK-inert, reusing v3.0 scaffold + guardrails). This is the AINL-01 item deferred from v3.1.

**Explicitly NOT this phase (how-to-implement boundary — no new capabilities):**
- **Free-form SQL / text-to-SQL / a new query grammar** — D-01 tool-calls existing filter services; NLQ-02 forbids free-form SQL.
- **Multi-turn / conversational refinement** — D-11 ships single-shot; carried conversation state is deferred.
- **Objects beyond the core three** — D-05 is vuln/asset/ticket only; SLA/exception/campaign/coverage/compliance/analytics answering is deferred.
- **Group-by / aggregation result shapes** — D-06 is filtered-lists-plus-count only; breakdown/aggregation queries are deferred.
- **Persisted or saved question history** — D-19 ships stateless; a saved-questions store is its own increment.
- **New mutation surface from results** — D-17 closes the loop via a read-only deep-link into existing list views; no bulk actions.
- **A second AI stack** — reuse the v3.0 scaffold; do not build parallel key storage, cache, budget, or audit machinery.

</domain>

<decisions>
## Implementation Decisions

### Translation & safe-schema (the NLQ-02 mechanism)
- **D-01:** **Tool-call the LLM into the existing tenant-scoped read services.** The model is given a catalog of the already-shipped list services (`list_vulnerabilities` + `VulnerabilityFilter`, `list_assets` + `AssetFilter`, `list_tickets`) as tools and emits a **schema-validated filter object** (`extra="forbid"`, mirroring v3.0's `AllowlistedFinding`); the backend executes it deterministically. No free-form SQL, no query grammar. Reuses the tenant-scoping + Pydantic validation already proven in v3.0. — **Reversibility:** costly — the tool/filter contract becomes the assistant's whole query surface; swapping to a DSL later re-authors translation + validation + execution.
- **D-02:** **One primary result entity per question + cross-object predicates on that entity's filter.** A question resolves to a single result entity (e.g. vulnerabilities), and the filter carries whatever cross-object predicates the service already supports (e.g. asset-exposure / KEV / age columns on the vuln query). The model picks the entity and fills exactly one filter → one clean result table. No model-side multi-tool join/composition this phase.
- **D-03:** **Extend the existing filter objects additively where a predicate gap is material.** When the target query set needs a predicate the current filter doesn't express (e.g. an "older than 30 days" age/date-window filter), add it to `VulnerabilityFilter` / `AssetFilter` so **both NLQ and the normal list UI** gain it — one filter contract. Research inventories the representative query set against existing filter columns; extend only where the coverage gap is real. Additive, not a new capability. — **Reversibility:** reversible — additive optional filter fields on existing filter objects. **Coupling note:** these new predicates must also be expressible in the list view's `useUrlState`/ChipBar params so D-17's deep-link works.
- **D-04:** **Always surface the translated filter back to the analyst.** Render a human-readable summary of the applied filter alongside the answer (e.g. "Interpreted as: severity=Critical, KEV=true, first_seen > 30 days ago, exposure=internet-facing") so a misread is visible and the tool is trustworthy. Fits the cite-or-refuse honesty discipline.

### Query surface & result types
- **D-05:** **Core three objects only in v1 — vulnerabilities, assets, tickets** (exactly what NLQ-01 names). Each has a mature list service + filter to tool-call. SLA / exception / campaign / coverage / compliance / analytics answering is deferred (their services exist and are the obvious next increment). — **Reversibility:** reversible — adding a tool is additive.
- **D-06:** **Filtered lists + exact count only.** Every question resolves to a filtered list of records; "how many…" is answered by returning that list and stating its size. No group-by / aggregation shapes this phase. One code path (list service + filter); the result set is always the concrete rows.
- **D-07:** **Deterministic exact count + bounded top-N to the model.** The backend runs the query, computes the **exact total count deterministically**, and passes only a bounded top-N (e.g. first page, risk-ranked) to the model to narrate. UI shows the top-N table + "N of M total". Keeps token / cost / PII / injection surface bounded; the count is never the model's guess. Exact cap + ranking is planner discretion within the bounded-cost + allowlist discipline.
- **D-08:** **Render the result set with the existing sunset-design list-row primitives.** Because the result is always one of vuln/asset/ticket, reuse the same row/table components the Vulnerabilities/Assets/Tickets lists use, each row linking to its real drill panel / detail. No second table pattern (sketch-findings warns against that).

### Entry point & interaction
- **D-09:** **New top-level "Ask" nav page** (query box + interpretation + result set), mirroring the Coverage (Phase 41) / Analytics (Phase 42) / Compliance (Phase 43) new-page precedent and their `nav-items.ts` pattern. Route naming is planner discretion (e.g. `/dashboard/ask`).
- **D-10:** **Single-shot per question.** Each question is independent: ask → interpret → result set + answer, no carried conversation state. Refine by editing the question. Deterministic and low-risk; multi-turn refinement is deferred.
- **D-11:** **Curated example questions as the empty/first-run state.** The empty state shows clickable starter questions reflecting the *actual* supported surface (e.g. "Which internet-facing hosts have an unremediated KEV older than 30 days?", "Show critical vulns breaching SLA", "Open tickets for asset X"). Sets expectations for the bounded schema, drives adoption, and satisfies the mandatory empty-state (state-patterns.md). Exact copy per copy-voice.md.
- **D-12:** **Nav always visible; unconfigured page shows a "Configure AI" CTA.** The "Ask" nav item is always present; when the tenant has no Anthropic key, the page renders the inert "Configure AI" state (reusing `GET /api/v1/ai/status` → `{configured}` and the same pattern the other AI features use) linking to the connector wizard. Discoverable — analysts learn the capability exists and how to enable it. Consistent with v3.0 (NLQ-03).

### Answer behavior & grounding
- **D-13:** **Narrate executed results only (cite-or-refuse).** The DB executes the translated query deterministically; the LLM narrates ONLY the returned top-N + exact count, never computing numbers itself or adding facts not in the result set. The result table is authoritative; the prose explains it. This is the grounding guarantee — matches v3.0's remediation cite-or-refuse and augment-never-replace stance.
- **D-14:** **Refuse + guide on out-of-scope / unmappable questions.** If a question can't map to the safe schema (out of scope, or no valid filter), the assistant declines honestly and points to what it CAN answer (reuse the D-11 starter examples). Never fabricates a query or answer. Combined with D-04 (always-show-interpretation), a partial/best-effort map is visible so the analyst sees exactly what was and wasn't understood.
- **D-15:** **Results first, narrative streams.** Show the interpretation + result table as soon as the query executes (fast, deterministic), then stream the narrative answer after via the reused buffer-then-validate SSE pattern. Best perceived speed — the authoritative data lands immediately, prose fills in.
- **D-16:** **Extend the CI eval + red-team gate with NLQ cases.** Add NLQ golden-set evals (correct filter for representative questions) + promptfoo red-team cases (injection via question text, attempts to reach another tenant, hallucinated field/enum → must reject) to the existing DeepEval/promptfoo required CI checks. Directly proves NLQ-02; matches the "evals are the arbiter" discipline. Eval dimensions are eval-planner's detail.

### Loop-closing, RBAC, caching, history
- **D-17:** **Read-only "Open these in <list>" deep-link.** Each answer offers an action that applies the *same translated filter* to the real Vulnerabilities/Assets/Tickets list view via the existing `useUrlState`/ChipBar filter params — turning an answer into a workflow with zero new mutation surface. Per-row links to individual drill/detail remain too. (Depends on D-03's predicates being URL-expressible.)
- **D-18:** **RBAC — analyst+ to ask, viewer+ for cached/status reads.** Mirror v3.0 exactly: the model-calling ask requires `require_analyst` (it spends the tenant's key); cheap cached/status reads are `require_viewer`. Reuse the fail-closed per-tenant budget breaker + the `ai:inflight:{tenant_id}` concurrency lock. — **Reversibility:** reversible — a route-guard choice.
- **D-19:** **Cache the translation, run the query live.** Cache only the question→filter translation (tenant-scoped, keyed on normalized question + model + `prompt_version`, reusing the `cache.py` key discipline) so repeat/similar asks skip the LLM cost; **always execute the query fresh** so results/counts are never stale, and narrate the fresh top-N. Do NOT cache full answers/result sets (staleness would break grounding). — **Reversibility:** reversible.
- **D-20:** **Stateless v1 — no persisted question history.** No history store or saved-questions this phase; the D-11 curated examples + browser session cover discovery/re-run. A saved/recent-questions store (client-only or persisted) is a clean later increment.

### Claude's Discretion
- Exact route naming/layout for the "Ask" page (D-09) and how the interpretation summary + streaming narrative are laid out relative to the result table.
- The top-N cap size and result ranking passed to the model (D-07).
- Which specific additive filter predicates to add and to which filter object (D-03) — bounded by the representative query set research surfaces.
- Exact starter-question copy and count (D-11), per copy-voice.md.
- Whether the ask path reuses the existing `_run_explain_stream` engine parameterized for the new prompt/response model, or a sibling stream function — as long as the buffer-then-validate + audit discipline holds (D-13/D-15).
- The precise NLQ eval/red-team case set (D-16) — eval-planner's call.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 44: Natural-Language Query Assistant" (lines ~313–323) — goal, 3 success criteria, dependency (extends the v3.0 AI scaffold; sequenced after 36–41 for answer coverage).
- `.planning/REQUIREMENTS.md` — NLQ-01, NLQ-02, NLQ-03 (lines ~80–84; dependency map ~124–126: all three depend on the shipped v3.0 AI scaffold).
- `.planning/milestones/v5.0-PROPOSAL.md` §"Phase 44" (lines ~60–63) — the AINL-01 framing + the canonical example query ("which internet-facing hosts have an unremediated KEV older than 30 days?").

### v3.0 BYOK AI scaffold — REUSE VERBATIM (do NOT build a second AI stack)
- `backend/app/ai/tenant_keys.py` §L31 `get_tenant_anthropic_key(db, tenant_id) -> str | None` — the single BYOK source of truth; returns None (never raises, never falls back) when unconfigured. The inert-state gate (NLQ-03).
- `backend/app/ai/explain.py` — `_run_explain_stream()` §L258 (buffer-then-validate-then-replay SSE engine, parameterized by `build_prompt` + `response_model`); `_default_client_factory` §L115 (fresh per-request `AsyncAnthropic`, cross-tenant leak defense); `DEFAULT_MODEL="claude-sonnet-5"` §L76; `get_model_and_budget()` §L206; `MAX_TOKENS=1024` §L80; `_estimate_cost_usd` §L185; one-shot `CORRECTIVE_TURN` retry §L107/L195. **NOTE:** this engine is single-record (fetch one → explain); NLQ needs a new question→query mapping layer on top of these services, reusing this streaming discipline.
- `backend/app/ai/prompt_builder.py` — `<scanner_data>`-isolation discipline (untrusted text as data, never in system prompt), `VULN_ALLOWLIST` §L54, `AllowlistedFinding` `extra="forbid"` §L84, `_get_field` §L110, `prompt_version()` (feeds cache key). The prompt + allowlist pattern D-01's filter-emission mirrors.
- `backend/app/ai/schemas.py` — `ExplainResponseBase` + `model_validate_json()` + `recheck_business_rules()` §L129 (schema validation gate; Anthropic strips maxLength so business rules are re-checked explicitly). Pattern for the NLQ filter + answer validation.
- `backend/app/ai/cache.py` — tenant-first cache key `build_cache_key` §L38 (`ai:...:{tenant_id}:...`), `record_hash()` §L59, `get_cached`/`set_cached` §L31, in-flight lock `acquire_inflight`/`release_inflight` §L97/L114 (`ai:inflight:{tenant_id}`, 120s TTL). D-19 caches the translation with this key discipline; D-18 reuses the inflight lock.
- `backend/app/ai/budget.py` — fail-closed monthly budget: `check_tenant_budget()` §L60, `get_month_to_date_spend()` §L41, `would_exceed_budget_for_batch()` §L83, `notify_admins_budget_exceeded()` §L109. Reused by D-18.
- `backend/app/ai/audit.py` §L26 `audit_log_ai_call()` — one AuditLog row per attempt; status vocabulary (`ok`, `validation_failed`, `grounded_retry`, `injection_flagged`, `rate_limited`, `budget_exceeded`, `unsafe_denylisted`, `unknown`). NLQ calls audit through this (add an `ai.query.*` action).
- `backend/app/ai/safety.py` — `contains_dangerous_pattern()` §L55 (denylist; reference for the injection/red-team mindset, though NLQ emits filters not commands).
- `backend/app/api/v1/ai/__init__.py` (router mount, prefix `/api/v1/ai`), `backend/app/api/v1/ai/status.py` §L31 (`GET /ai/status` → `{configured}`, `require_viewer`) — the D-12 inert-state check. `explain_vuln.py` etc. — POST `require_analyst` / GET `require_viewer` split D-18 mirrors.
- `backend/app/connectors/schemas.py` §L340 (ANTHROPIC connector: `api_key` secret, `model` select, `monthly_budget_usd`) + `backend/app/connectors/tester.py` §L473 (live-key smoke test). Where BYOK is configured (D-12 CTA target).

### Read/query services to tool-call (D-01 — core three, v1)
- `backend/app/vulnerabilities/service.py` — `list_vulnerabilities` §L116, `VulnerabilityFilter` + `_apply_filters` §L44, `get_facets` §L634, `get_dashboard_stats` §L787. The primary NLQ query tool; D-03 extends the filter here.
- `backend/app/assets/service.py` — `list_assets` §L44 + `AssetFilter`, `get_asset` §L96.
- `backend/app/ticketing/service.py` — `list_tickets` §L709, `get_ticket_stats` §L1059.
- Domain Pydantic schemas: `backend/app/vulnerabilities/schemas.py`, `backend/app/assets/schemas.py`, `backend/app/ticketing/schemas.py` — the filter + row shapes the tool catalog and result rendering bind to.

### Deferred-object services (NOT v1 — context for the deferred surface, D-05)
- `backend/app/vulnerabilities/sla_service.py` (`get_sla_metrics` §L119), `backend/app/exceptions/service.py` (`list_exceptions` §L400), `backend/app/campaigns/service.py` (`list_campaigns` §L218), `backend/app/coverage/service.py` (`get_coverage_summary` §L169), `backend/app/compliance/service.py`, `backend/app/analytics/service.py`.

### Eval / red-team gate to extend (D-16)
- The v3.0 DeepEval golden-set + promptfoo prompt-injection red-team CI checks (shipped Phase 28, AIE-01..04). Research must locate the exact test/config paths (backend eval suite + promptfoo config) to add NLQ cases.

### Frontend AI scaffold to reuse (D-08/D-12/D-15)
- `frontend/src/lib/ai/use-explain-stream.ts` — SSE streaming hook (`fetch` + manual ReadableStream parser, Bearer auth); `resourceType` interpolated into the URL so a new NLQ stream reuses it.
- `frontend/src/components/ai/ai-explanation-section.tsx` §L146 (view-agnostic streaming panel), `ai-explanation-citations.tsx` (two-tier citation rendering).
- `frontend/src/lib/queries/use-ai-status.ts` — the D-12 configured-check hook.
- `frontend/src/components/shell/nav-items.ts` — single source of truth for nav; where the "Ask" entry (D-09) is added.
- `frontend/src/lib/state/useUrlState` + the ChipBar pattern (Phases 41/42 precedent) — the D-17 deep-link target for the filtered list views.
- List-row primitives in `frontend/src/components/vulnerabilities/`, `frontend/src/components/assets/`, `frontend/src/components/tickets/` — reused for the result set (D-08).

### Precedent (mirror these new-page patterns)
- `frontend/src/app/(authed)/dashboard/coverage/page.tsx` (Phase 41), `.../analytics/page.tsx` (Phase 42), `.../compliance/page.tsx` (Phase 43) — the new-top-level-nav-page + honest-empty-state pattern D-09/D-11 mirror.
- `.planning/phases/43-executive-compliance-reporting/43-CONTEXT.md` — recent new-page + reuse-services-directly precedent.

### Design system (the "Ask" page is UI — ROADMAP "UI hint: yes")
- `.claude/skills/sketch-findings-getvul/` — `references/page-layouts.md` (new-page), `references/state-patterns.md` (mandatory empty/loading/error — the D-11 empty state + D-14 refuse state + D-12 inert state), `references/visual-language.md` (severity/SLA/status colors in the result rows), `references/copy-voice.md` (starter-question + refusal copy — no generic SaaS voice).

### Project-level guardrails (locked, apply verbatim)
- `.planning/PROJECT.md` §"Key Decisions" — BYOK-only (no shared/fallback key); untrusted scanner text as data, schema-validated output; AI augments never replaces; evals + red-team required CI, cost breaker fails closed; every query tenant-scoped; audit events for new actions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`tenant_keys.get_tenant_anthropic_key`** — the BYOK no-fallback gate; drives the D-12 inert state and every NLQ model call.
- **`_run_explain_stream` + `prompt_builder` + `schemas.recheck_business_rules`** — the buffer-then-validate-then-replay streaming + allowlist + schema-validation discipline D-01/D-13/D-15 reuse (parameterized with a new prompt + response model).
- **`cache.py` (tenant-first key + inflight lock), `budget.py` (fail-closed breaker), `audit.py` (`audit_log_ai_call`)** — reused by D-18/D-19; add an `ai.query.*` audit action.
- **`list_vulnerabilities`/`VulnerabilityFilter`, `list_assets`/`AssetFilter`, `list_tickets`** — the tenant-scoped read services the LLM tool-calls (D-01); `VulnerabilityFilter` is where D-03 adds predicates.
- **`use-explain-stream.ts` + `ai-explanation-section.tsx`** — the frontend SSE scaffold the "Ask" page reuses.
- **`nav-items.ts` + Coverage/Analytics/Compliance page precedent** — the new "Ask" page shell (D-09).
- **`useUrlState`/ChipBar** — the D-17 "open these in the list" deep-link target.

### Established Patterns
- **BYOK-inert AI feature** (status check → configure-CTA) — D-12.
- **Tool-emit → schema-validate (`extra="forbid"`) → execute deterministically** — the v3.0 output-validation pattern generalized to a filter object (D-01).
- **Reusable service functions callable by both HTTP route and other callers** — the read services are called directly (D-01), no HTTP round-trip.
- **New top-level nav page for a distinct workflow** (Coverage/Analytics/Compliance) — D-09.
- **Grounded, cite-or-refuse AI output; augment never replace** — D-13/D-14.
- **Evals/red-team as the arbiter, required CI** — D-16.

### Integration Points
- New `POST /api/v1/ai/query` (SSE, `require_analyst`) + a cheap `GET` cached/status path (`require_viewer`) under the existing `ai_router` (D-15/D-18).
- A new question→filter translation + tool catalog layer over the three read services (D-01/D-02) — the core new backend asset.
- Additive predicate fields on `VulnerabilityFilter`/`AssetFilter` (D-03), also wired into the list views' URL params for D-17.
- New "Ask" nav entry + `/dashboard/ask` route + result-set rendering reusing list-row primitives (D-08/D-09).
- NLQ eval/red-team cases added to the existing DeepEval + promptfoo CI suites (D-16).

</code_context>

<specifics>
## Specific Ideas

- The canonical target question is **"which internet-facing hosts have an unremediated KEV older than 30 days?"** (from v5.0-PROPOSAL.md) — a multi-predicate query crossing asset exposure + vuln KEV/age. It is the north-star for D-02 (one primary entity + joins) and D-03 (which additive predicates are actually needed).
- The value is an analyst getting a **trustworthy** answer over their *own* data — hence D-04 (show the interpretation), D-07 (deterministic exact count, never a model guess), D-13 (narrate results only), and D-14 (refuse + guide, never fabricate). Trust is the product here, not fluent prose.
- Reuse over rebuild is explicit in the goal ("reusing the v3.0 BYOK AI scaffold rather than building a second AI stack") — every new asset should sit *on top of* `ai/` + the read services, not beside them.
- D-17's deep-link ("open these in Vulnerabilities") is the moment the assistant stops being a novelty and becomes part of the triage loop.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-turn / conversational refinement** ("now just the internet-facing ones", "sort by risk") — D-10 ships single-shot; carried context is a clean later increment.
- **Answering over SLA / exception / campaign / coverage / compliance / analytics** — D-05 is core-three-only; the services exist and are the obvious next objects to add as tools.
- **Group-by / aggregation result shapes** ("count by severity/status/owner") — D-06 is filtered-lists-plus-count; reusing the facet/stats services for breakdowns is deferred.
- **Persisted / saved question history** (recent, shareable, cross-device) — D-20 is stateless v1; a store + CRUD UI is its own increment.
- **Bulk actions on results** (bulk-create tickets, export the result set) — D-17 stays read-only (deep-link only); mutation from the Ask page is deferred.
- **NL mode inside Cmd+K global search** — considered for the entry point; D-09 chose a dedicated page. A lightweight Cmd+K "Ask AI: …" deep-link into the page is a later nicety.

None of the above blocks Phase 44.

</deferred>

---

*Phase: 44-natural-language-query-assistant*
*Context gathered: 2026-08-24*
