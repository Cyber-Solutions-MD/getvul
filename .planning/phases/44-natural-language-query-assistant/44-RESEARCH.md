# Phase 44: Natural-Language Query Assistant - Research

**Researched:** 2026-08-24
**Domain:** LLM tool-calling / structured-output translation layer over existing tenant-scoped read services (FastAPI + Anthropic Python SDK + SSE), reusing a shipped v3.0 BYOK AI scaffold
**Confidence:** HIGH (backend scaffold, predicate inventory, CI/eval gate — all directly verified by reading the real source) / MEDIUM (exact two-call orchestration shape, Anthropic structured-output schema limits — verified against official docs but not spiked against a live key)

## Summary

This phase is almost entirely a **composition problem**, not a build problem. Every canonical_ref file path and line number in 44-CONTEXT.md was verified against the real source this session and resolves exactly (see Sources) — the context document is trustworthy and current. The three genuinely new pieces of engineering are: (1) a question→filter **translation** layer that emits a schema-validated, `extra="forbid"` filter object via Anthropic structured outputs (not native tool-calling — see Pitfall 2), (2) a small, well-scoped set of **additive filter fields** on `VulnerabilityFilter`/`AssetFilter` plus a lightweight translation-only wrapper schema for `list_tickets` (which has no `TicketFilter` object at all today), and (3) a **two-call orchestration** (translate, then execute the deterministic query, then narrate) that does not fit inside the existing single-record `_run_explain_stream()` unchanged — it needs a new sibling orchestrator that reuses `_run_explain_stream`'s constituent pieces (key/budget/inflight checks, client factory, cache, audit, validate-retry loop) rather than calling that function itself.

The good news, concretely verified this session: most of the north-star query's predicates **already exist** on `VulnerabilityFilter` (`cisa_kev`, `age_days_min`, `status`, `exploit_available`) — only an asset-exposure (`internet_facing`) join-based predicate and an SLA-breach predicate are missing, and both have low-risk, precedented implementations. The CI eval/red-team gate CONTEXT.md calls "the promptfoo gate" is actually **two separate, keyless, CI-blocking pytest/DeepEval jobs** (`ai-evals`, `ai-redteam-injection`) — real promptfoo only runs in a non-blocking, key-gated, currently-inert opt-in tier. And the frontend's `useExplainStream`/`AiExplanationSection` — while conceptually the right scaffold — do not literally fit NLQ's shape (no stable `resourceId`, no request body support, question-driven not click-driven) and need small, well-scoped new siblings rather than direct reuse.

**Primary recommendation:** Build a new `backend/app/ai/query_assistant.py` orchestrator (imports, does not modify, `explain.py`'s primitives) that runs two independent single-turn structured-output calls — translate (question → flat, non-union filter object) then narrate (filter + results → `ExplainResponseBase`-shaped answer, zero new fields) — around ONE shared precondition/audit/cache envelope; add `internet_facing` (join) and `sla_breached` (stored-column reuse) to `VulnerabilityFilter`; add a thin `TicketQueryFilter` translation wrapper (not a `list_tickets` refactor); and extend the two existing CI-blocking gates additively rather than inventing new ones.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Question text intake + submit UX | Browser/Client | — | Local input state; no server round-trip until submit |
| Question → filter translation (LLM call 1) | API/Backend | — | Needs the tenant's decrypted BYOK key + budget/audit; never runs client-side |
| Filter schema + business-rule validation | API/Backend | — | Mirrors `recheck_business_rules()` — Anthropic's schema translator strips constraints server-side must re-check |
| Hostname→asset_id resolution (for "asset X" questions) | API/Backend | Database | Deterministic, non-model lookup; must run in Python/SQL, never trust the model to know a UUID |
| Tenant-scoped deterministic query execution | API/Backend | Database | Reuses `list_vulnerabilities`/`list_assets`/`list_tickets`; tenant_id always session-supplied, never model-supplied |
| Exact count + bounded top-N selection | Database | API/Backend | Already a solved problem — `PaginatedResponse.create()` + `PaginationParams` already compute this for every existing list endpoint |
| Result narration (LLM call 2) | API/Backend | — | Same BYOK/budget/audit envelope as translation |
| SSE event streaming | API/Backend | Browser/Client | Backend produces `bytes` frames (`_sse_event`); frontend's `fetch()` + `ReadableStream` reader consumes |
| Interpreted-filter chips + result table rendering | Browser/Client | — | Reuses existing list-row primitives (D-08) |
| Narrative prose + citation rendering | Browser/Client | — | Reuses `AiExplanationCitations` IF the narrate response mirrors `ExplainResponseBase` |
| Deep-link into Vulnerabilities/Assets/Tickets list (D-17) | Browser/Client | — | Pure URL construction via `useUrlState`/`useUrlStateList` — no new backend endpoint |
| BYOK key resolution/decryption | API/Backend | Database | `tenant_keys.get_tenant_anthropic_key` — zero changes needed |
| Translation cache (D-19) | API/Backend | Redis | `cache.py`'s tenant-first key discipline, reused verbatim |
| Per-tenant budget + inflight concurrency guard | API/Backend | Database/Redis | `budget.py` + `cache.py`'s `acquire_inflight`/`release_inflight`, reused verbatim |
| Audit logging | API/Backend | Database | `audit.py`'s `audit_log_ai_call`, needs one small additive parameter (see Pitfall 4) |
| CI eval/red-team gate | API/Backend (test suite) | CI/CD | Out of the request path entirely — extends two existing GitHub Actions jobs |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Translation & safe-schema (the NLQ-02 mechanism)**
- **D-01:** Tool-call the LLM into the existing tenant-scoped read services. The model is given a catalog of the already-shipped list services (`list_vulnerabilities` + `VulnerabilityFilter`, `list_assets` + `AssetFilter`, `list_tickets`) as tools and emits a schema-validated filter object (`extra="forbid"`, mirroring v3.0's `AllowlistedFinding`); the backend executes it deterministically. No free-form SQL, no query grammar. — Reversibility: costly.
- **D-02:** One primary result entity per question + cross-object predicates on that entity's filter. A question resolves to a single result entity, and the filter carries whatever cross-object predicates the service already supports. No model-side multi-tool join/composition this phase.
- **D-03:** Extend the existing filter objects additively where a predicate gap is material — one filter contract for both NLQ and the normal list UI. Additive, not a new capability. — Reversibility: reversible. Coupling note: new predicates must also be expressible in the list view's `useUrlState`/ChipBar params so D-17's deep-link works.
- **D-04:** Always surface the translated filter back to the analyst (e.g. "Interpreted as: severity=Critical, KEV=true, first_seen > 30 days ago, exposure=internet-facing").

**Query surface & result types**
- **D-05:** Core three objects only in v1 — vulnerabilities, assets, tickets. SLA/exception/campaign/coverage/compliance/analytics answering deferred. — Reversibility: reversible.
- **D-06:** Filtered lists + exact count only. No group-by/aggregation shapes this phase.
- **D-07:** Deterministic exact count + bounded top-N to the model. Exact cap + ranking is planner discretion.
- **D-08:** Render the result set with the existing sunset-design list-row primitives. No second table pattern.

**Entry point & interaction**
- **D-09:** New top-level "Ask" nav page, mirroring Coverage/Analytics/Compliance's new-page precedent. Route naming is planner discretion (e.g. `/dashboard/ask`).
- **D-10:** Single-shot per question. No carried conversation state.
- **D-11:** Curated example questions as the empty/first-run state (4 starter questions, exact copy per UI-SPEC).
- **D-12:** Nav always visible; unconfigured page shows a "Configure AI" CTA (reusing `GET /api/v1/ai/status`).

**Answer behavior & grounding**
- **D-13:** Narrate executed results only (cite-or-refuse). The LLM never computes numbers itself or adds facts not in the result set.
- **D-14:** Refuse + guide on out-of-scope/unmappable questions. Never fabricates a query or answer.
- **D-15:** Results first, narrative streams. Show interpretation + result table as soon as the query executes, then stream the narrative via the reused buffer-then-validate SSE pattern.
- **D-16:** Extend the CI eval + red-team gate with NLQ cases (golden-set filter correctness + promptfoo-style red-team: injection via question text, cross-tenant reach, hallucinated field/enum). Eval dimensions are eval-planner's detail.

**Loop-closing, RBAC, caching, history**
- **D-17:** Read-only "Open these in `<list>`" deep-link using the SAME translated filter via `useUrlState`/ChipBar params. No new mutation surface. (Depends on D-03's predicates being URL-expressible.)
- **D-18:** RBAC — analyst+ to ask (`require_analyst`), viewer+ for cached/status reads (`require_viewer`). Reuse the fail-closed per-tenant budget breaker + the `ai:inflight:{tenant_id}` concurrency lock. — Reversibility: reversible.
- **D-19:** Cache the translation, run the query live. Cache only question→filter (tenant-scoped, keyed on normalized question + model + `prompt_version`). Always execute the query fresh. Do NOT cache full answers/result sets. — Reversibility: reversible.
- **D-20:** Stateless v1 — no persisted question history.

### Claude's Discretion
- Exact route naming/layout for the "Ask" page (D-09) and how the interpretation summary + streaming narrative are laid out relative to the result table.
- The top-N cap size and result ranking passed to the model (D-07).
- Which specific additive filter predicates to add and to which filter object (D-03) — bounded by the representative query set research surfaces (see D-03 Predicate Inventory below).
- Exact starter-question copy and count (D-11), per copy-voice.md.
- Whether the ask path reuses the existing `_run_explain_stream` engine parameterized for the new prompt/response model, or a sibling stream function — as long as the buffer-then-validate + audit discipline holds (D-13/D-15). **Research recommendation: sibling function — see Architecture Patterns Pattern 1.**
- The precise NLQ eval/red-team case set (D-16) — eval-planner's call.

### Deferred Ideas (OUT OF SCOPE)
- Multi-turn/conversational refinement ("now just the internet-facing ones") — D-10 ships single-shot.
- Answering over SLA/exception/campaign/coverage/compliance/analytics — D-05 is core-three-only.
- Group-by/aggregation result shapes ("count by severity/status/owner") — D-06 is filtered-lists-plus-count.
- Persisted/saved question history — D-20 is stateless v1.
- Bulk actions on results (bulk-create tickets, export) — D-17 stays read-only.
- NL mode inside Cmd+K global search — D-09 chose a dedicated page.

None of the above blocks Phase 44.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NLQ-01 | Plain-English questions over the tenant's own vuln/asset/ticket data return grounded, tenant-scoped answers with the underlying result set shown | D-03 Predicate Inventory (below) proves most predicates already exist; Pattern 1 (two-call orchestration) + existing `PaginatedResponse`/`PaginationParams` give exact-count/top-N "for free"; `AiExplanationCitations` reuse gives grounded-citation rendering if the narrate schema mirrors `ExplainResponseBase` |
| NLQ-02 | Queries constrained to a safe schema (no free-form SQL, no injection, no cross-tenant reach) | D-01 tool-catalog-via-structured-output (not native tool-calling, see Pitfall 2); `extra="forbid"` + flat non-union filter schema (Pitfall 2); tenant_id structurally absent from the model's output schema and always session-supplied (Security Domain); `<user_question>` tag-isolation mirroring the proven `<scanner_data>` pattern; two CI-blocking gates identified and extension path given (Validation Architecture) |
| NLQ-03 | Inert until the tenant configures their own Anthropic key (BYOK), reusing the v3.0 scaffold + guardrails | `get_tenant_anthropic_key()` reused verbatim (zero changes); `GET /api/v1/ai/status` reused verbatim for the nav-always-visible/Configure-AI-CTA pattern (D-12); the new orchestrator's first precondition check is byte-identical to `_run_explain_stream`'s `if api_key is None: yield {"type":"no_key"}` |
</phase_requirements>

## D-03 Predicate Inventory (the highest-value finding)

Representative query set: the north-star ("which internet-facing hosts have an unremediated KEV older than 30 days?") plus the 4 UI-SPEC starter questions.

**Key architectural resolution:** the north-star question's surface language ("hosts") suggested an asset-primary result to me at first read, but D-02's own framing resolves it correctly as **vulnerability-primary** — `VulnerabilitySummary` already carries `asset_hostname` on every row (populated via `list_vulnerabilities`'s existing `.outerjoin(Asset, ...)`), so a vuln-primary result table with an asset-exposure predicate satisfies the question without ever needing a harder asset-primary "assets that have a matching vulnerability" EXISTS-subquery. This keeps every north-star predicate on ONE filter object (`VulnerabilityFilter`), consistent with D-02's "no model-side multi-tool join" constraint.

| Predicate needed | Already expressible? | Evidence | Additive field needed |
|---|---|---|---|
| KEV = true | **YES** | `VulnerabilityFilter.cisa_kev: bool \| None` [VERIFIED: `backend/app/vulnerabilities/schemas.py:143`] | none |
| Unremediated (status) | **YES** | `VulnerabilityFilter.status: list[str] \| None`, values `OPEN\|IN_PROGRESS\|REMEDIATED\|SUPPRESSED\|FALSE_POSITIVE` [VERIFIED: `models.py:24-29` `VulnStatus` enum]; "unremediated" = `status=["OPEN","IN_PROGRESS"]` | none |
| Older than N days | **YES** | `VulnerabilityFilter.age_days_min: int \| None` → `_apply_filters` does `Vulnerability.first_detected_at <= now - age_days_min` [VERIFIED: `service.py:106-108`] | none |
| Active exploit (starter Q4) | **YES** | `VulnerabilityFilter.exploit_available: bool \| None` [VERIFIED: `schemas.py:142`] | none |
| Severity = Critical (starter Q2) | **YES** | `VulnerabilityFilter.severity: list[str] \| None` [VERIFIED: `schemas.py:134`] | none |
| Internet-facing asset (north-star, starter Q4) | **NO** | `Asset.internet_facing: bool` exists on the model [VERIFIED: `assets/models.py:118`] but `VulnerabilityFilter` has no asset-derived predicate, and `AssetFilter` also has no `internet_facing` field [VERIFIED: `assets/schemas.py:68-76`] | **Add `asset_internet_facing: bool \| None` to `VulnerabilityFilter`**, applied in `_apply_filters` via a join to `Asset` (see Pitfall 1 for a join-collision landmine to verify). Add `internet_facing: bool \| None` to `AssetFilter` too (trivial — native column, no join — for future asset-primary symmetry) |
| Breaching SLA (starter Q2) | **NO** | `VulnerabilityFilter` has no SLA-state field at all. The live `sla_state` (on_track/approaching/breached) shown in list responses is a **Python-side computation** (`resolve_state_for_vuln`), not a queryable column [VERIFIED: `sla_tier_service.py:144-183`]. BUT a stored `Vulnerability.sla_breached: bool` column exists and is kept fresh by `run_sla_tier_pass`, explicitly documented as "the sla_breached DERIVED MIRROR" for exactly this kind of read [VERIFIED: `sla_tier_service.py:194,230-233`], refreshed every scheduler tick (60s interval [VERIFIED: `connectors/scheduler.py:422`]) | **Add `sla_breached: bool \| None` to `VulnerabilityFilter`**, mapped directly to the stored column. Staleness window ≤60s — a non-issue for this use case, and consistent with Phase 40's alerting already trusting this same column |
| "Open tickets for asset X" (starter Q3) | **PARTIALLY** | `list_tickets` already accepts `asset_id: str \| None` [VERIFIED: `ticketing/service.py:716`] and a status filter, but the question names a **hostname** ("prod-db-01"), not a UUID, and `list_tickets` has no hostname parameter | **No backend filter change** — needs a translation-layer hostname→asset_id resolution step (see Architecture Patterns Pattern 3); not a new predicate on `list_tickets` itself |

**`list_tickets` has no `TicketFilter` Pydantic object at all** — it takes loose scalar kwargs (`provider`, `status`, `asset_id`, `severity`, `sla`, `search`, `source`) with comma-separated strings for multi-value params [VERIFIED: `ticketing/service.py:709-721`]. Its own docstring claims `severity`/`sla` are "post-aggregate filters" but the actual code applies them as SQL `WHERE` (severity, via an `EXISTS`-style vulnerability-id subquery) and SQL `HAVING` (sla, on `MIN(Ticket.sla_due_at)`) [VERIFIED: `ticketing/service.py:774-861`] — **the docstring is stale; the real implementation is already SQL-native and deterministic-count-safe.** `sla` accepts `overdue|soon|ok` — a different, coarser vocabulary than vulnerabilities' `on_track|approaching|breached`. **Recommendation: do not refactor `list_tickets`.** Write a small, NLQ-only `TicketQueryFilter` Pydantic model (`extra="forbid"`) that the model emits, and have the translation layer map its fields onto `list_tickets`'s existing kwargs. This is exactly the "tool catalog" layer D-01 already calls for, so it's in scope regardless of `list_tickets`'s messiness — zero changes to the ticketing service required.

**D-17 URL-param coupling is broader than CONTEXT's note implies.** `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` only wires `severity`, `source`, `status`, `group`, `sort`, `order` into `useUrlState`/`useUrlStateList` [VERIFIED: grep for these hook calls, zero matches for `kev`/`exploit_available`/`age_days` in that file]. **Even the already-existing `cisa_kev`/`exploit_available`/`age_days_min` backend filter fields have no URL-param path into the list page today** — this is a pre-existing gap, not something Phase 44 introduced. D-17 therefore needs new URL-param wiring for up to 6 fields (kev, exploit_available, age_days_min, sla_breached, internet_facing, plus whatever ticket params are needed), not just the 1-2 genuinely-new ones. Still low-risk/mechanical (the `useUrlState`/`useUrlStateList` pattern with an allowed-values clamp is fully proven — see `use-url-state-list.ts`), but the planner should scope tasks for the full list, not just the new fields.

## Standard Stack

No new libraries. Every dependency this phase needs is already installed and pinned.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` (Python SDK) | 0.122.0 installed [VERIFIED: `python -c "import anthropic; print(anthropic.__version__)"`], pinned `>=0.120.0` in `pyproject.toml` | Structured-output model calls | Already the proven v3.0 client; a second AI client library would violate the explicit reuse mandate |
| `pydantic` | 2.13.4 installed [VERIFIED], pinned `>=2.9` | Filter/response schema validation, `extra="forbid"` | Same reasoning — every existing AI schema in this codebase is Pydantic v2 |
| `deepeval` | 4.1.5 installed, pinned exactly (`==4.1.5`) [VERIFIED: `pyproject.toml:41`] | Golden-set structural eval harness | Pinned deliberately for deterministic CI behavior (see comment in pyproject.toml) — do not bump for this phase |
| `redis` (via `redis.asyncio`) | already a dependency (used throughout `app/ai/cache.py`) | Translation cache + inflight lock | Reused verbatim, zero new client code |

### Supporting
None new. `structlog`, `sqlalchemy`, `fastapi` are already project-wide dependencies with no NLQ-specific version requirement.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Anthropic structured outputs (`output_config`, what `explain.py` already uses) | Anthropic's native tool-calling (`tools=[...]`, `tool_choice`) | D-01's product language ("tool-call the LLM") literally suggests this, but it introduces an UNTESTED response shape (`stop_reason=="tool_use"`, `tool_use`/`tool_result` content blocks) that `_run_explain_stream`'s validate/retry loop was never built for. Structured outputs achieve the identical product outcome (model picks an entity + emits a schema-validated filter) with zero new SDK surface. **Recommend structured outputs — see Pitfall 2.** |
| A flat, non-union filter response schema + Python post-validation for "exactly one filter set" | Pydantic discriminated union (`Field(discriminator=...)`) for `entity`→filter-shape | Pydantic's discriminated-union JSON Schema typically emits `oneOf`, which Anthropic's structured-output docs do not list as supported (only `anyOf`/`allOf` are) [CITED: platform.claude.com/docs/en/build-with-claude/structured-outputs]. Flat schema + an explicit re-check function (mirroring the ALREADY-existing `recheck_business_rules()` pattern) avoids the unsupported keyword entirely. See Pitfall 2. |
| Extending the existing `test_golden_evals.py`/`test_ai_injection_redteam.py` files | A brand-new, NLQ-only eval/red-team pipeline | The existing files were explicitly designed to be extended per-capability (`_load_goldens()` auto-discovers new `goldens/<capability>/` directories; `CAPABILITY_CASES` is a plain list new entries append to) — inventing a parallel pipeline would fork the "evals are the arbiter" discipline D-16 exists to preserve. |

**Installation:** none required.

**Version verification:** confirmed live against the installed backend `.venv` this session (see Core table above) — no `npm view`/`pip index` lookup needed since these are already-running, already-pinned dependencies, not new additions.

## Architecture Patterns

### System Architecture Diagram

```
Analyst types question ──► Frontend "Ask" page (/dashboard/ask)
                              │
                              │ POST /api/v1/ai/query  {question}
                              ▼
                    ┌─────────────────────────────────────────┐
                    │  New orchestrator: query_assistant.py    │
                    │  _run_query_stream(db, tenant_id, ...)   │
                    └─────────────────────────────────────────┘
                              │
             ┌────────────────┼─────────────────────────────────┐
             │ (ONE shared precondition envelope, mirrors        │
             │  _run_explain_stream's first 3 checks exactly)    │
             ▼                                                   │
     get_tenant_anthropic_key() ──None──► SSE {"type":"no_key"}  │  (NLQ-03)
             │ (key present)                                     │
             ▼                                                   │
     check_tenant_budget() ──fail──► audit "budget_exceeded" ──► SSE error
             │ (ok)                                               │
             ▼                                                   │
     acquire_inflight(tenant) ──busy──► SSE {"error","busy"}     │  (D-18)
             │ (acquired)                                         │
             ▼
   ┌─────────────────────────────────────────────────┐
   │ CALL 1: TRANSLATE (structured output, no stream  │
   │ visible to client)                               │
   │  build_query_translate_prompt(question) ────────►│  <user_question> tag
   │  client.messages.stream(output_config=filter     │  isolation, mirrors
   │    schema) → validate (extra=forbid + "exactly   │  <scanner_data>
   │    one filter matches entity" recheck) → retry    │
   │    once on failure (mirrors CORRECTIVE_TURN)      │
   └─────────────────────────────────────────────────┘
             │ schema-valid filter, OR terminal refuse (D-14)
             ▼
   Hostname→asset_id resolution (if filter references a hostname; deterministic,
   no model call — Pattern 3)
             │
             ▼
   Execute list_vulnerabilities / list_assets / list_tickets
   (tenant_id from AUTHENTICATED SESSION, never from the model's output —
   the filter schema structurally has no tenant_id field)
             │
             ▼
   SSE {"type":"interpreted", filter, entity}  ──────────────► Frontend renders
   SSE {"type":"results", rows: top_N, total: M}  ───────────► interpretation +
             │                                                  result table
             ▼                                                  IMMEDIATELY (D-15)
   ┌─────────────────────────────────────────────────┐
   │ CALL 2: NARRATE (same structured-output          │
   │ mechanism, response_model = NlqAnswerResponse,   │
   │ zero new fields beyond ExplainResponseBase)      │
   │  grounding record = {question, filter, top_N,    │
   │    total} — narrate ONLY these, never compute     │
   │    new numbers (D-13)                             │
   └─────────────────────────────────────────────────┘
             │ validated narrative
             ▼
   cache SET (translation only — D-19) + audit BOTH calls (ai.query.*)
             ▼
   SSE {"type":"summary_delta", text}* → SSE {"type":"done", payload}
             │
             ▼
   release_inflight(tenant)  [finally, mirrors _run_explain_stream exactly]
             │
             ▼
   Frontend streams narrative prose (reusing AiExplanationCitations IF the
   narrate schema mirrors ExplainResponseBase), offers "Open in <List>"
   deep-link that builds a URL from the SAME interpreted filter (D-17)
```

### Recommended Project Structure
```
backend/app/ai/
├── explain.py                 # UNCHANGED — existing single-record engine
├── prompt_builder.py          # ADD: build_query_translate_prompt(),
│                               #      build_query_narrate_prompt(),
│                               #      query_translate_prompt_version(),
│                               #      query_narrate_prompt_version()
│                               #      (mirrors the 5 existing capabilities'
│                               #      pattern in the SAME file)
├── schemas.py                  # ADD: NlqFilterResponse (flat, non-union —
│                               #      see Pitfall 2), NlqAnswerResponse
│                               #      (ExplainResponseBase subclass, zero
│                               #      new fields)
├── query_assistant.py          # NEW: _run_query_stream() orchestrator —
│                               #      imports (does not modify) explain.py's
│                               #      _default_client_factory, cache.py,
│                               #      budget.py, audit.py, tenant_keys.py
├── cache.py, budget.py,        # UNCHANGED
│   audit.py, tenant_keys.py,
│   safety.py

backend/app/api/v1/ai/
├── query.py                    # NEW: POST /query (SSE, require_analyst),
│                               #      GET /query/cache-check or similar
│                               #      (require_viewer) — mirrors
│                               #      explain_vuln.py's POST+GET split
└── __init__.py                 # ADD: ai_router.include_router(query.router)

backend/app/vulnerabilities/schemas.py   # ADD: asset_internet_facing,
                                          #      sla_breached to VulnerabilityFilter
backend/app/vulnerabilities/service.py   # ADD: 2 predicates in _apply_filters
backend/app/assets/schemas.py            # ADD: internet_facing to AssetFilter (symmetry)
backend/app/ticketing/schemas.py         # ADD: TicketQueryFilter (new, NLQ-only,
                                          #      translation-input wrapper — does
                                          #      NOT touch list_tickets's own signature)

frontend/src/lib/ai/
├── use-explain-stream.ts       # UNCHANGED (or: extract shared SSE-frame-
│                               #  parsing loop into a small internal helper
│                               #  both hooks call — optional refactor)
└── use-query-stream.ts         # NEW: POSTs {question} as a JSON body (the
                                #      existing hook has no body-sending
                                #      capability — see Pitfall 7), handles
                                #      new SSE kinds: interpreted, results

frontend/src/components/ai/
├── ai-explanation-section.tsx  # ADD: `export` on DegradedCard (currently
│                               #      module-private — see Pitfall 8)
└── ask/                        # NEW: query-box.tsx, interpreted-filter.tsx,
                                #      result-table.tsx (thin wrapper reusing
                                #      vuln/asset/ticket row primitives),
                                #      starter-questions.tsx

frontend/src/app/(authed)/dashboard/ask/page.tsx   # NEW — mirrors
    coverage/analytics/compliance page.tsx precedent exactly (ErrorBoundary >
    Suspense > PageInner, useDocumentTitle, useUrlState if any page-level state)

frontend/src/components/shell/nav-items.ts   # ADD one WORKFLOW_ITEMS entry,
    no chip (not one of the 3 chip-carrying destinations)
```

### Pattern 1: Two-call orchestration, not a parameterized `_run_explain_stream`
**What:** `_run_explain_stream()` is fundamentally shaped for "fetch one record → explain it" (single `build_prompt(record)` call, one narrative response). NLQ needs "map a question → filter → execute a query → narrate the results" — a structurally different, two-model-call flow with a deterministic DB step in between. Parameterizing `_run_explain_stream` for this would require threading an unrelated DB-query step through the middle of a function whose entire contract is `build_prompt(record) → validate → cache → audit → stream`.
**When to use:** Any future AI capability that needs to act on a QUESTION or a SET of records rather than a single fetched-by-ID record.
**Recommendation:** Write `query_assistant.py::_run_query_stream()` as a new function that:
1. Runs the SAME precondition sequence as `_run_explain_stream` (key check → budget check → inflight acquire), by direct import — do not duplicate this logic.
2. Calls a small internal helper (`_call_structured()`) TWICE — once per model call — that itself mirrors `_run_explain_stream`'s inner `for attempt_index in range(2)` retry loop (this loop, not the whole function, is the truly reusable unit). Extracting it as a shared private helper both `explain.py` and `query_assistant.py` import is a clean, additive, zero-regression-risk refactor if the planner wants it; simply duplicating ~40 lines is also acceptable given the loop is small and stable.
3. Executes the deterministic query between the two calls, using the SAME `tenant_id` the route already authenticated — never anything from the model's output.
4. Emits the two NEW SSE event kinds (`interpreted`, `results`) before the narrate call even starts (satisfies D-15).
5. Runs `acquire_inflight`/`release_inflight` ONCE for the whole two-call flow (not once per call) — two independent acquisitions risk the narrate call self-blocking behind its own just-released-but-recently-contended lock, or (worse) a different request sneaking in between the two calls for the same tenant.
6. Checks budget once before translate; given `MAX_TOKENS=1024` per call already bounds worst-case spend per call, re-checking before narrate is optional hardening, not required correctness.

**Example (translate call sketch):**
```python
# Source: mirrors app/ai/explain.py's proven pattern, generalized
async def _call_structured(
    client: AsyncAnthropic,
    *,
    model: str,
    system_prompt: str,
    user_blocks: list[dict[str, str]],
    response_model: type[BaseModel],
    max_attempts: int = 2,
) -> tuple[BaseModel, Any]:
    """Shared single-call-with-one-corrective-retry loop — extract this out
    of _run_explain_stream's existing for-loop body (lines ~343-428) rather
    than reimplementing it. Returns (validated_response, raw_usage)."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_blocks}]
    for attempt in range(max_attempts):
        async with client.messages.stream(
            model=model, max_tokens=MAX_TOKENS, temperature=0,
            system=system_prompt, messages=messages,
            output_config=_build_output_config(response_model, model),
        ) as stream:
            raw = await stream.get_final_message()
        text = "".join(getattr(b, "text", "") for b in raw.content if getattr(b, "type", None) == "text")
        try:
            candidate = response_model.model_validate_json(text)
            return candidate, raw.usage
        except ValidationError:
            if attempt == max_attempts - 1:
                raise
            messages = _append_corrective_turn(messages, text)
    raise AssertionError("unreachable")
```

### Pattern 2: Flat, non-union filter schema — avoid `oneOf`
**What:** The natural Pydantic modeling for "the model picks ONE of three entities and emits that entity's filter shape" is a discriminated union (`Field(discriminator="entity")`). Anthropic's structured-outputs documentation lists `anyOf`/`allOf` (with limits) as supported but does **not** list `oneOf` [CITED: platform.claude.com/docs/en/build-with-claude/structured-outputs, fetched 2026-08-24] — and Pydantic's discriminated-union feature commonly emits `oneOf`. This is a real, checkable risk to a schema design decision, not a stylistic preference.
**When to use:** Any Anthropic structured-output schema that needs "exactly one of N shapes."
**Recommendation:** One flat response model with `entity: Literal[...]` plus three independently-optional, non-discriminated filter fields, and a NEW business-rule recheck function (mirroring the exact pattern `recheck_business_rules()` already established for constraints Anthropic's schema translator strips) enforcing "exactly one of the three is non-null, and it matches `entity`."
```python
# Source: schemas.py — new addition, mirrors ExplainResponseBase's
# "Anthropic strips constraints, recheck explicitly" precedent (Pitfall 4)
class VulnFilterInput(BaseModel):
    model_config = {"extra": "forbid"}
    severity: list[str] | None = None
    cisa_kev: bool | None = None
    exploit_available: bool | None = None
    sla_breached: bool | None = None
    asset_internet_facing: bool | None = None
    age_days_min: int | None = None
    status: list[str] | None = None
    asset_hostname: str | None = None  # resolved server-side, never a UUID

class AssetFilterInput(BaseModel):
    model_config = {"extra": "forbid"}
    internet_facing: bool | None = None
    device_category: str | None = None

class TicketFilterInput(BaseModel):
    model_config = {"extra": "forbid"}
    status: str | None = None
    asset_hostname: str | None = None

class NlqFilterResponse(BaseModel):
    model_config = {"extra": "forbid"}
    entity: Literal["vulnerabilities", "assets", "tickets"]
    vulnerability_filter: VulnFilterInput | None = None
    asset_filter: AssetFilterInput | None = None
    ticket_filter: TicketFilterInput | None = None
    groundable: bool  # mirrors `grounded` — false + no filter = D-14 refuse

def recheck_nlq_filter_exclusivity(resp: NlqFilterResponse) -> None:
    filters = {"vulnerabilities": resp.vulnerability_filter,
               "assets": resp.asset_filter, "tickets": resp.ticket_filter}
    matching = filters.pop(resp.entity)
    if resp.groundable and matching is None:
        raise BusinessRuleError(f"entity={resp.entity} but its filter is null")
    if any(f is not None for f in filters.values()):
        raise BusinessRuleError("more than one entity's filter is populated")
```
**Note [ASSUMED — verify empirically before locking]:** whether Pydantic v2's plain `Union` (no discriminator) emits `anyOf` (supported) is training-knowledge, not independently verified this session. Before finalizing, run `NlqFilterResponse.model_json_schema()` and confirm no `oneOf` key appears anywhere in the output — a 2-minute check, cheap insurance against a schema Anthropic's API may silently coerce or reject.

### Pattern 3: Hostname resolution is a deterministic backend step, never model-side
**What:** "Open tickets for asset prod-db-01" requires resolving a hostname string to an internal `asset_id` UUID. The model cannot know this UUID (it's tenant data outside training), and D-02 forbids model-side multi-tool composition (so the model can't "look up the asset, then list tickets" itself).
**When to use:** Any question that names an asset/host by hostname.
**Example:**
```python
# Deterministic, tenant-scoped, runs AFTER translation validates, BEFORE
# executing the real query. Reuses AssetFilter's existing hostname ILIKE.
async def _resolve_hostname(db, tenant_id, hostname: str) -> uuid.UUID | None:
    result = await list_assets(db, tenant_id, AssetFilter(hostname=hostname),
                                PaginationParams(page=1, page_size=1))
    return result.items[0].id if result.items else None
```
If unresolved, treat as a **zero-results** answer (D-06's "every question resolves to a filtered list" framing), not a D-14 refuse — the question was well-formed and safe-schema-compliant; it simply matched nothing. Flagged as an Open Question below for eval-planner confirmation.

### Anti-Patterns to Avoid
- **Native Anthropic tool-calling for D-01:** introduces an untested response shape this codebase's validate/retry/audit discipline was never built for. Use structured outputs (Pattern 2) instead — same product outcome, zero new SDK surface.
- **Reusing `AiExplanationSection`/`useExplainStream` unchanged:** both assume a stable `resourceId` and a click-to-trigger UX with a pre-existing cache-check GET. NLQ has neither (see Pitfall 7). Write small new siblings that reuse the LOW-LEVEL pieces (SSE frame parsing, `AiExplanationCitations`, `AnalyzingIndicator`, `DegradedCard` once exported).
- **Refactoring `list_tickets` into a clean `TicketFilter`:** out of scope, higher-risk than needed. The translation-input-wrapper approach (Pattern in D-03 table) gets the same safety guarantee with zero changes to a working, tested function.
- **Replicating live `resolve_state_for_vuln` SLA logic in SQL:** the stored `sla_breached` mirror column already exists for exactly this read pattern (Phase 40 alerting already trusts it) — don't build a second SLA-computation path.
- **Caching narrated answers or result sets:** D-19 explicitly forbids this (staleness would break the grounding guarantee) — cache the translation only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fresh-per-request Anthropic client construction | A new client wrapper/singleton | `_default_client_factory` pattern (`AsyncAnthropic(api_key=..., max_retries=2)`, constructed fresh per call) | Cross-tenant key-leak defense (T-24-19) is already proven here; a singleton or cached client would reintroduce that exact risk |
| Prompt-injection isolation | A new sanitization/escaping layer for question text | The `<tag>`-wrapped, `json.dumps`'d untrusted-content-as-data pattern (`<scanner_data>` → new `<user_question>`) | Already red-teamed with 17 adversarial payloads × 5 capabilities; a new isolation mechanism would need its own red-team proof from scratch |
| Cost/budget enforcement | A new spend-tracking table or counter | `budget.py`'s `check_tenant_budget()` (SUMs existing `ai.*` audit rows — no new source of truth) | Fail-closed, already tested, already wired to admin notification |
| Exact result count + pagination | A new count query / manual `LIMIT`/`OFFSET` math | `list_vulnerabilities`/`list_assets` + `PaginationParams`/`PaginatedResponse.create()` | Already computes an exact, deterministic total for every existing list endpoint — D-07 requires nothing new here beyond choosing a `page_size` |
| Two-tier citation rendering | New inline-highlight/tooltip logic | `AiExplanationCitations` (IF `NlqAnswerResponse` mirrors `ExplainResponseBase`'s shape exactly) | Already handles overlapping citation ranges, animate-reveal, tooltip source labeling |
| Per-tenant request concurrency limiting | A new mutex/queue | `cache.py`'s `acquire_inflight`/`release_inflight` (`SETNX`-with-TTL on `ai:inflight:{tenant_id}`) | Already proven, already the exact key namespace D-18 names |
| RBAC gating | New role-check decorators | `require_analyst`/`require_viewer` from `app.auth.rbac` | Already the entire AI router's convention (every `explain_*.py` route uses this exact split) |

**Key insight:** every "Don't Hand-Roll" item above is not a generic industry best-practice reminder — each one is a SHIPPED, TESTED module in this exact codebase whose signature was verified this session. The risk in this phase is not "someone invents a worse cache/budget/audit mechanism" (unlikely given how explicit the reuse mandate is) — it's "someone reimplements a *slightly different* prompt-isolation or citation-rendering pattern for NLQ specifically," which would fragment the "one AI stack" property NLQ-03 depends on.

## Common Pitfalls

### Pitfall 1: Double-joining `Asset` when adding the `asset_internet_facing` predicate
**What goes wrong:** `list_vulnerabilities`'s data query already does `.outerjoin(Asset, Vulnerability.asset_id == Asset.id)` for the hostname column [VERIFIED: `service.py:135`], AFTER `_apply_filters()` already ran. If `_apply_filters` (used by both the count query and the data query) ALSO joins `Asset` when `asset_internet_facing` is set, the SAME query may end up joining `Asset` twice.
**Why it happens:** `_apply_filters` and `list_vulnerabilities` currently assume Asset joins are the caller's (list_vulnerabilities's) exclusive responsibility; adding a filter-driven join inside `_apply_filters` breaks that assumption for the count-query path specifically (which never joins Asset today).
**How to avoid:** Verify empirically (a quick unit test asserting the generated SQL / running the query against a test DB) whether SQLAlchemy 2.0's `select(Vulnerability).join(Asset, cond)` deduplicates when the same target+onclause is joined twice, or raises. If it errors, have `_apply_filters` own the Asset join unconditionally (moving `list_vulnerabilities`'s existing `.outerjoin(Asset,...).add_columns(...)` into `_apply_filters` itself) rather than filtering and joining in two places.
**Warning signs:** `sqlalchemy.exc.InvalidRequestError` mentioning the `assets` table already being present in the FROM list, surfacing only when `asset_internet_facing` is set (the existing test suite won't catch this — it never sets this new field).

### Pitfall 2: `oneOf` in the filter response schema
**What goes wrong:** A naive, idiomatic Pydantic discriminated union for "the model picks ONE of three filter shapes" emits `oneOf` in its JSON Schema. Anthropic's structured-outputs docs list `anyOf`/`allOf` as supported but do not mention `oneOf` [CITED: platform.claude.com/docs/en/build-with-claude/structured-outputs].
**Why it happens:** Discriminated unions are the "correct" Pydantic pattern for this shape in every other context; nothing about writing one here looks wrong in review.
**How to avoid:** Use Pattern 2's flat schema (three independently-optional fields, no union) + an explicit Python re-check (mirrors the ALREADY-precedented `recheck_business_rules` discipline for constraints the API strips or mishandles).
**Warning signs:** A live smoke test (once `DEV_ANTHROPIC_API_KEY` exists) returning a 400 on the `output_config`, or the model silently ignoring the union constraint and returning multiple filters populated.

### Pitfall 3: `audit_log_ai_call`'s hardcoded `ai.explain.` action prefix
**What goes wrong:** `audit_log_ai_call()` constructs `action=f"ai.explain.{resource_type}"` [VERIFIED: `audit.py:61`] — the string `"explain"` is a literal, not a parameter. Calling this function as-is from the new NLQ orchestrator would silently mislabel every NLQ audit row as an "explain" action, breaking CONTEXT's explicit instruction to add an `ai.query.*` vocabulary and corrupting any usage/cost rollup (Phase 28's `usage.py`) that groups by action prefix.
**Why it happens:** `audit_log_ai_call` was written when "explain" was the only capability family; nothing forced generalizing it until now.
**How to avoid:** Add one optional, backward-compatible parameter: `action_prefix: str = "explain"`. Every existing call site is unaffected (default preserves current behavior byte-for-byte); the new orchestrator passes `action_prefix="query"`.
**Warning signs:** Grep the `audit_logs` table for `action LIKE 'ai.query%'` after implementation returning zero rows despite NLQ calls having run.

### Pitfall 4: `list_tickets`'s stale docstring vs. its actual (safer) implementation
**What goes wrong:** Trusting the function's own docstring ("severity and sla are applied as a post-aggregate filter on the built items") would lead a planner to (incorrectly) conclude ticket queries with severity/SLA predicates can't get an exact deterministic count cheaply, and to over-engineer a Python-side count workaround.
**Why it happens:** The docstring predates a later refactor that moved these filters into SQL `WHERE`/`HAVING` without updating the comment.
**How to avoid:** Trust the code, not the docstring, for `severity`/`sla` [VERIFIED: `service.py:774-861` — both are SQL-level and the count query re-applies the identical `HAVING`]. No special-case handling needed for D-07's exact-count requirement on tickets.
**Warning signs:** none at runtime — this is purely a planning-time trap.

### Pitfall 5: The per-tenant inflight lock deadlocking (or false-"busy"-ing) across the two model calls
**What goes wrong:** If translate and narrate each independently `acquire_inflight`/`release_inflight`, a narrow race window between the two calls lets a concurrent second question from the SAME tenant acquire the lock, causing the FIRST question's own narrate call to spuriously report "busy" against itself (worse: a badly-sequenced acquire/release could self-deadlock if release doesn't happen before the second acquire attempt).
**Why it happens:** `_run_explain_stream`'s single-call shape never had to reason about this; NLQ's two-call shape is new.
**How to avoid:** Acquire the inflight lock ONCE for the whole two-call flow (translate + query execution + narrate), release once in a `finally`, exactly mirroring `_run_explain_stream`'s existing `try/finally` shape but wrapping more work inside it.
**Warning signs:** Ask page occasionally shows "AI busy" on a fresh single question with no concurrent activity.

### Pitfall 6: SLA-breach filter staleness is bounded and acceptable — don't over-engineer freshness
**What goes wrong:** A planner unfamiliar with `run_sla_tier_pass`'s scheduler cadence might assume filtering on the stored `sla_breached` column requires a live recompute to stay "grounded" (D-13), and build unnecessary Python-side recomputation.
**Why it happens:** D-13's "narrate results only" principle sounds like it demands perfect real-time accuracy.
**How to avoid:** The scheduler tick interval is 60 seconds [VERIFIED: `connectors/scheduler.py:422`, `asyncio.sleep(60)`], and `run_sla_tier_pass` is documented as the authoritative "derived mirror" for exactly this read pattern. A sub-minute staleness window on an SLA-breach filter is a total non-issue for an analyst's ad-hoc question, and is the SAME tradeoff Phase 40's alerting already accepts.
**Warning signs:** none expected; flagged here purely to prevent scope creep.

### Pitfall 7: `useExplainStream` cannot send a request body — it does not fit NLQ's shape
**What goes wrong:** CONTEXT.md's canonical_refs describe `use-explain-stream.ts` as reusable "so a new NLQ stream reuses it," but the hook's `fetch()` call has **no `body` parameter at all** [VERIFIED: `use-explain-stream.ts:68-73` — `fetch(url, {method: 'POST', headers: {...}})`, no body] and builds its URL by interpolating a `resourceId` path segment. NLQ has no resourceId (a question isn't a resource) and needs to POST a JSON body (`{question}`).
**Why it happens:** Every existing AI capability (vuln/host/remediation/prioritization) genuinely is "fetch one record by ID, explain it" — the hook was never designed for a free-text-input flow.
**How to avoid:** Write a new `use-query-stream.ts` hook. It can and should reuse the SSE-frame-parsing loop (the genuinely valuable, nontrivial 50 lines) — either by copy (small, stable, low risk of drift) or by extracting a shared internal helper both hooks call.
**Warning signs:** none at build time (TypeScript won't catch "this hook doesn't send what NLQ needs" since it would just always send an empty body) — this must be caught in code review/planning, not by the type system.

### Pitfall 8: `DegradedCard` is not exported
**What goes wrong:** UI-SPEC repeatedly describes the Ask page reusing `DegradedCard variant="neutral"/"amber"/"danger"` "verbatim" for the Configure-AI, refusal, budget-exceeded, and safety-refusal states. But `DegradedCard` is a module-private function inside `ai-explanation-section.tsx` [VERIFIED: no `export` keyword at its declaration, line 47] — it cannot be imported from a new `ask/` component today.
**Why it happens:** It was never needed outside that one file until now.
**How to avoid:** Add `export` to the existing declaration — a one-line, zero-behavior-change diff.
**Warning signs:** A TypeScript import error the moment a new Ask component tries `import { DegradedCard } from '@/components/ai/ai-explanation-section'`.

## Code Examples

### New prompt-builder function (mirrors the 5 existing capabilities exactly)
```python
# Source: pattern verified against build_explain_vuln_prompt,
# backend/app/ai/prompt_builder.py:294-315
def build_query_translate_prompt(question: str) -> tuple[str, list[dict[str, str]]]:
    """<user_question> mirrors <scanner_data>'s isolation contract exactly —
    the analyst's own text is still treated as untrusted-content-as-data,
    never concatenated into the system prompt."""
    user_block_text = f'<user_question>{json.dumps({"question": question})}</user_question>'
    return SYSTEM_PROMPT_QUERY_TRANSLATE, [{"type": "text", "text": user_block_text}]

def query_translate_prompt_version() -> str:
    return prompt_version(SYSTEM_PROMPT_QUERY_TRANSLATE, FEW_SHOT_QUERY_TRANSLATE, NlqFilterResponse)
```

### New SSE event kinds (frontend type additions)
```typescript
// Source: extends the existing RawSseEvent union in use-explain-stream.ts's
// pattern — kept in a NEW sibling file (use-query-stream.ts), not merged
// into the shared union, so existing explain views' exhaustive branches
// are untouched.
type InterpretedEvent = { type: 'interpreted'; entity: 'vulnerabilities' | 'assets' | 'tickets'; filter: Record<string, unknown> };
type ResultsEvent = { type: 'results'; rows: unknown[]; total: number };
```

### `audit_log_ai_call`'s additive parameter
```python
# Source: backend/app/ai/audit.py:26 — additive, backward-compatible
async def audit_log_ai_call(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_email: str, model: str,
    usage: Any, resource_type: str, resource_id: str, status: str,
    cost_estimate_usd: float | None = None,
    action_prefix: str = "explain",  # NEW — every existing call site unaffected
) -> None:
    log = AuditLog(
        tenant_id=tenant_id, user_id=None, user_email=user_email,
        action=f"ai.{action_prefix}.{resource_type}",  # was: f"ai.explain.{resource_type}"
        ...
    )
```

## State of the Art

| Old Approach (Phases 24-27) | Current Approach (Phase 44) | When Changed | Impact |
|--------------------------|------------------------------|---------------|--------|
| AI explains ONE record fetched by a stable ID | AI translates a free-text QUESTION into a filter, then narrates a SET of records | This phase | First "search"-shaped AI feature in the codebase, not "explain"-shaped — needs a new orchestration layer, not a parameterization |
| Vulnerabilities list page URL state covers `severity`/`source`/`status`/`group`/`sort`/`order` only | D-17 needs `cisa_kev`/`exploit_available`/`age_days_min`/`sla_breached`/`internet_facing` also URL-expressible | This phase (if D-17 is fully honored) | The deep-link task is larger than a 1-2 field patch — scope 5-6 URL params, not 1-2 |
| `list_tickets` filters via loose kwargs | No change recommended — a thin translation-only wrapper schema sits ABOVE it | This phase | Keeps a known-messy-but-working function untouched while still giving NLQ a clean, `extra="forbid"` tool schema |

**Deprecated/outdated:** nothing in this phase deprecates prior work — it is purely additive on top of the v3.0/v4.0/v5.0 scaffolds.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pydantic v2's plain (non-discriminated) `Union` type annotation emits `anyOf` (not `oneOf`) in `model_json_schema()` output | Architecture Patterns, Pattern 2 | If wrong, the recommended flat-schema-with-a-plain-Union sub-shape could still emit an unsupported keyword; mitigated by the recommendation itself avoiding any `Union` at all (three independently-optional fields, no union type) — so this assumption is actually load-bearing only for the "why avoid discriminated unions" reasoning, not the recommended implementation. Low risk. |
| A2 | SQLAlchemy 2.0's `select(Vulnerability).join(Asset, cond)` either dedupes or errors (not silently produces a broken/duplicate JOIN) when the same target+onclause is added twice via `_apply_filters` + `list_vulnerabilities`'s existing outerjoin | Pitfall 1 | If it silently produces a malformed query instead of erroring, this could ship a subtly wrong result set rather than fail loudly. Mitigation already given: verify empirically with a test before relying on double-join safety either way; the safer recommendation (have `_apply_filters` own the join unconditionally) sidesteps the question entirely. |
| A3 | An unresolvable "asset X" hostname should render as a zero-results answer, not a D-14 refusal | Architecture Patterns, Pattern 3 | If eval-planner/UX disagrees, the refusal-vs-zero-results branch logic and its copy (UI-SPEC already has copy for both states) would need to swap which condition triggers which state — a small, contained change, not a re-architecture. |
| A4 | Checking the tenant's budget once (before translate) rather than before each of the two calls is an acceptable simplification | Pattern 1 | If a tenant's budget is exhausted exactly between the two calls, the narrate call could push spend slightly over cap before the NEXT question is blocked. Bounded by `MAX_TOKENS=1024` per call — worst-case overshoot is one call's cost, not unbounded. Planner discretion either way. |

**If this table is empty:** N/A — see rows above. Everything else in this document is either directly verified by reading the real source this session (tagged VERIFIED) or cross-checked against official Anthropic documentation (tagged CITED).

## Open Questions

1. **Does Pydantic's `model_json_schema()` for the recommended flat `NlqFilterResponse` (Pattern 2) produce zero `oneOf`/recursive-schema keywords?**
   - What we know: the three filter fields are independently-optional (no `Union` type), which should avoid `oneOf` by construction.
   - What's unclear: whether `$ref`/`$defs` generated for the nested `VulnFilterInput`/`AssetFilterInput`/`TicketFilterInput` sub-models trip the "no recursive schemas" / "no external `$ref`" limitation also documented at platform.claude.com/docs.
   - Recommendation: a 5-minute check (`NlqFilterResponse.model_json_schema()`, grep the output for `oneOf`/external `$ref`) before finalizing the schema in a plan — cheap, deterministic, no live API key needed.

2. **Should "Open tickets for asset X" with an unresolvable hostname be a zero-results state or a D-14 refusal?**
   - What we know: D-06 frames every question as "resolves to a filtered list"; D-14 is specifically for schema-mapping failures (can't map to ANY valid filter), not "valid filter, zero matches."
   - What's unclear: whether the eval-planner wants a red-team case distinguishing "wrong hostname" from "well-formed but empty" for UX-honesty reasons.
   - Recommendation: treat as zero-results (Pattern 3) unless eval-planner's D-16 case design says otherwise.

3. **Exact top-N cap value (D-07 discretion).**
   - What we know: UI-SPEC's own copy example is `"10 of 47 total"`; `PaginationParams.page_size` already supports 1-200.
   - What's unclear: whether 10 is enough for the north-star query's typical result size, or whether a slightly larger cap (e.g. 20) better serves the narrate call's grounding richness without meaningfully increasing cost (MAX_TOKENS=1024 already bounds narrate regardless of row count fed in, up to a point).
   - Recommendation: start with 10 (matches UI-SPEC's copy precedent exactly), revisit only if eval feedback shows the narrate call under-cites.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `anthropic` Python SDK | Both model calls | ✓ | 0.122.0 | — |
| `pydantic` | Filter/response schema validation | ✓ | 2.13.4 | — |
| `deepeval` | Golden-set CI gate | ✓ | 4.1.5 (pinned exact) | — |
| Redis | Translation cache + inflight lock | ✓ (already required by every other AI feature; used in local dev + CI service container) | — | — |
| PostgreSQL | Tenant/filter/audit reads+writes | ✓ (already required) | — | — |
| `DEV_ANTHROPIC_API_KEY` (GitHub secret) | Live/opt-in promptfoo red-team tier + a real (non-hand-authored) golden capture | ✗ [VERIFIED: STATE.md deferred-items log — "GETVUL_DEV_ANTHROPIC_KEY absent," formal override accepted at Phase 28] | — | Hand-author NLQ golden fixtures the same way Phase 28 did (`capture_ai_goldens.py` documents the fallback); the keyless CI-blocking gates (`ai-evals`, `ai-redteam-injection`) are unaffected and remain fully exercisable without this key |

**Missing dependencies with no fallback:** none — the one missing item (`DEV_ANTHROPIC_API_KEY`) has an already-precedented fallback (hand-authored goldens) that Phase 28 already used and documented.

**Missing dependencies with fallback:** `DEV_ANTHROPIC_API_KEY` (see above) — this is a pre-existing, already-formally-accepted gap from Phase 28, not a new blocker Phase 44 introduces.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (backend) | pytest (existing `backend/tests/`) + DeepEval 4.1.5 (`deepeval test run`) |
| Framework (frontend) | Vitest/Testing Library (existing `*.test.tsx` co-location convention) |
| Config file | `backend/pyproject.toml` (pytest), `.github/workflows/ci.yml` (job wiring), `.github/branch-protection.json` (required-check names) |
| Quick run command | `pytest tests/test_ai_query_stream.py tests/test_ai_prompt_builder_query.py -v` |
| Full suite command | `pytest -v --cov=app --cov-report=xml` (backend "Backend" job) + `deepeval test run tests/evals/test_golden_evals.py tests/evals/test_nlq_golden_evals.py` + `pytest tests/test_ai_injection_redteam.py tests/test_ai_budget_coverage.py -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NLQ-01 | Question → filter → correct rows returned, exact count matches | integration | `pytest tests/test_ai_query_stream.py -k test_query_returns_grounded_result_set -x` | ❌ Wave 0 |
| NLQ-01 | Translate produces the EXPECTED filter for each representative question | eval | `deepeval test run tests/evals/test_nlq_golden_evals.py -k translate` | ❌ Wave 0 |
| NLQ-01 | Narrate output passes the 5 EXISTING structural metrics (reused verbatim since `NlqAnswerResponse` mirrors `ExplainResponseBase`) | eval | `deepeval test run tests/evals/test_nlq_golden_evals.py -k narrate` | ❌ Wave 0 |
| NLQ-01 | Results-first-then-stream ordering (D-15) — interpreted+results SSE events arrive before any summary_delta | integration | `pytest tests/test_ai_query_stream.py -k test_results_before_narrative -x` | ❌ Wave 0 |
| NLQ-01 | "Open in `<list>`" deep-link produces a URL the target list page actually filters on (D-17) | frontend e2e/component | `vitest run ask-page.test.tsx -t "deep link"` | ❌ Wave 0 |
| NLQ-02 | Filter schema rejects a hallucinated field (`extra="forbid"`) | unit, keyless | `pytest tests/test_ai_schemas.py -k test_nlq_filter_rejects_unknown_field -x` | ❌ Wave 0 |
| NLQ-02 | Filter schema rejects "more than one entity's filter populated" | unit, keyless | `pytest tests/test_ai_schemas.py -k test_nlq_exclusivity_recheck -x` | ❌ Wave 0 |
| NLQ-02 | Question text stays isolated to `<user_question>`, never appears in system prompt (add as 6th capability to the EXISTING consolidated suite) | red-team, keyless, CI-blocking | `pytest tests/test_ai_injection_redteam.py -k query_translate -x` | ❌ Wave 0 (extends existing file) |
| NLQ-02 | Execution always uses session `tenant_id`, never anything from model output | unit, keyless | `pytest tests/test_ai_query_stream.py -k test_tenant_id_never_from_model -x` | ❌ Wave 0 |
| NLQ-02 | Live adversarial red-team (real question-phrasing injection attempts, LLM-graded) | red-team, live, non-blocking, key-gated | `npx promptfoo@0.121.20 redteam run -c redteam/promptfooconfig.yaml` (extend existing config with NLQ scenarios) | Config exists; NLQ scenarios ❌ Wave 0. **Currently inert (no DEV_ANTHROPIC_API_KEY) — same accepted gap as Phase 28.** |
| NLQ-03 | `POST /api/v1/ai/query` returns `{"type":"no_key"}` when unconfigured (never a 500, never a generic error) | unit, keyless | `pytest tests/test_ai_query_stream.py -k test_no_key_precondition -x` | ❌ Wave 0 |
| NLQ-03 | `/dashboard/ask` renders "Configure AI" card when `useAiStatus()` returns `configured:false` | frontend component | `vitest run ask-page.test.tsx -t "configure AI"` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_ai_query_stream.py tests/test_ai_prompt_builder_query.py tests/test_ai_schemas.py -v` (fast, keyless, DB+Redis via existing CI service containers)
- **Per wave merge:** `deepeval test run tests/evals/test_nlq_golden_evals.py` + `pytest tests/test_ai_injection_redteam.py -v` + frontend `vitest run`
- **Phase gate:** Full suite green (both existing `ai-evals`/`ai-redteam-injection` CI jobs, extended, still green) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_ai_query_stream.py` — covers NLQ-01/NLQ-02/NLQ-03 orchestration-level behavior; needs the SAME `anthropic_client_factory` test seam already proven in `test_ai_explain_stream.py`
- [ ] `backend/tests/test_ai_prompt_builder_query.py` — covers the new prompt-builder functions' isolation contract at the unit level
- [ ] `backend/tests/evals/goldens/nlq_translate/*.json` + `backend/tests/evals/goldens/nlq_narrate/*.json` — new golden fixture directories (auto-discovered by the existing `_load_goldens()` once populated)
- [ ] `backend/tests/evals/test_nlq_golden_evals.py` — new eval test file; reuses the 5 existing metrics for `nlq_narrate` fixtures verbatim, needs ONE new metric (`FilterCorrectnessMetric` or similar) for `nlq_translate` fixtures since the existing 5 metrics all assume an `ExplainResponseBase`-shaped `model_response`
- [ ] Extend `backend/tests/test_ai_injection_redteam.py`'s existing `CAPABILITY_CASES` list with a 6th entry (`build_query_translate_prompt`, poisoned field `"question"`, a one-line `_query_record` factory) — gains all 17 existing adversarial payloads automatically, no new payload authoring needed
- [ ] Extend `.github/workflows/ci.yml`'s `ai-evals` step to also run `tests/evals/test_nlq_golden_evals.py`, and `ai-redteam-injection`'s step already picks up the extended `test_ai_injection_redteam.py` automatically (same file, same `pytest` invocation)
- [ ] Frontend `frontend/src/app/(authed)/dashboard/ask/page.test.tsx` — mirrors `campaigns/page.test.tsx`'s co-located convention

*(No framework install needed — pytest/DeepEval/Vitest are all already configured and running in CI.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (new surface) | Existing session/JWT auth unchanged — `CurrentUser` dependency already gates every AI route |
| V3 Session Management | no (new surface) | Unchanged |
| V4 Access Control | yes | `require_analyst` (POST /query — spends the tenant's key) / `require_viewer` (any cached/status GET) — mirrors every existing `explain_*.py` route split verbatim (D-18) |
| V5 Input Validation | yes | Question length cap (UI-SPEC backstop, ~500 chars) enforced at the API boundary via `Field(max_length=...)` on the request body schema (this ONE constraint, unlike citation/summary length, is NOT stripped by Anthropic since it's validated on the REQUEST body by FastAPI/Pydantic before the model is ever called — not part of the model's own output schema); `extra="forbid"` on every filter/response schema |
| V6 Cryptography | no new work | BYOK key already encrypted via the existing Fernet-based `encryption.py`/`tenant_keys.py` path — zero new crypto surface |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via question text (model steered to reveal system prompt, ignore grounding, or emit a filter it shouldn't) | Tampering / Elevation of Privilege | `<user_question>` tag-isolation (Pattern in Architecture), mirrors the proven `<scanner_data>` contract; leak-marker check (`_contains_leak_marker`-style) reusable verbatim against the translate/narrate outputs |
| Cross-tenant data reach via a manipulated filter | Information Disclosure | Structural: the filter schema has NO `tenant_id` field to begin with (mirrors `AllowlistedFinding`'s exclusion-by-omission); execution always uses the AUTHENTICATED session's `tenant_id`, never anything from model output — this is not a runtime check to bypass, it's an absent code path |
| Hallucinated field/enum in the emitted filter | Tampering | `extra="forbid"` (schema-level rejection) + `recheck_nlq_filter_exclusivity`-style business-rule recheck (Anthropic's schema translator strips some constraints server-side — never assume the API alone enforces them, per the ALREADY-documented Pitfall 4 in `schemas.py`) |
| Free-form SQL / query-grammar injection | Tampering | Structurally impossible by design — the model never emits SQL or a query string, only a Pydantic-validated filter OBJECT executed via the existing parameterized-ORM `list_*` functions (D-01) |
| Resource exhaustion via an oversized question or an unbounded top-N | Denial of Service | Question length cap (V5 above); `MAX_TOKENS=1024` per call already bounds worst-case model cost; top-N cap (D-07, recommend 10) bounds the narrate call's context size regardless of how many rows actually match |
| Cost-blowup from an uncapped or repeated question | Denial of Service (financial) | `check_tenant_budget()` fail-closed reused verbatim; `acquire_inflight` prevents concurrent-request stampede; D-19's translation-only cache reduces repeat-question cost |

## Sources

### Primary (HIGH confidence — directly read/verified this session)
- `backend/app/ai/explain.py`, `prompt_builder.py`, `schemas.py`, `cache.py`, `budget.py`, `audit.py`, `safety.py`, `tenant_keys.py` — full read, every canonical_ref line number confirmed exact
- `backend/app/vulnerabilities/service.py`, `schemas.py`, `models.py`, `sla_tier_service.py` — full/targeted read for D-03 predicate inventory
- `backend/app/assets/service.py`, `schemas.py`, `models.py` — full read
- `backend/app/ticketing/service.py`, `models.py` — targeted read of `list_tickets` and `Ticket` model
- `backend/app/connectors/scheduler.py` (SLA tick interval), `schemas.py`/`tester.py` (ANTHROPIC connector)
- `backend/app/api/v1/ai/__init__.py`, `status.py`, `explain_vuln.py` (router pattern)
- `backend/tests/evals/test_golden_evals.py`, `metrics.py`, `goldens/vuln/grounded.json` — full read
- `backend/tests/test_ai_injection_redteam.py` — full read (the red-team suite CONTEXT.md refers to as "promptfoo")
- `.github/workflows/ci.yml` (jobs 160-296), `.github/branch-protection.json` — confirmed required-check names exactly
- `frontend/src/lib/ai/use-explain-stream.ts`, `use-ai-status.ts`, `components/ai/ai-explanation-section.tsx`, `ai-explanation-citations.tsx` — full read
- `frontend/src/hooks/use-url-state.ts`, `use-url-state-list.ts`, `components/shell/nav-items.ts` — full read
- `frontend/src/app/(authed)/dashboard/compliance/page.tsx`, `vulnerabilities/page.tsx` — targeted read for new-page precedent + URL-param gap
- `backend/.venv` live inspection — `anthropic==0.122.0`, `pydantic==2.13.4` confirmed installed
- `.planning/phases/44-natural-language-query-assistant/44-CONTEXT.md`, `44-UI-SPEC.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`

### Secondary (MEDIUM-HIGH confidence — official docs, cross-checked against codebase behavior)
- [Structured outputs - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — fetched 2026-08-24; confirmed `anyOf`/`allOf` (with limits) supported, `oneOf` not listed, no `minimum`/`maximum`/`minLength`/`maxLength`, `additionalProperties: false` required, `minItems` only 0/1 (this LAST point independently corroborates `schemas.py`'s own already-documented Pitfall 4 about citation `min_length=1`)

### Tertiary (LOW confidence — flagged for validation)
- Initial WebSearch summary claiming "schema recursion doesn't handle oneOf/anyOf/allOf" — superseded by the direct docs fetch above, which clarifies `anyOf`/`allOf` ARE supported (the recursion caveat is narrower than the search snippet implied). Not relied upon in this document except as the reason a direct docs fetch was performed.

## Metadata

**Confidence breakdown:**
- Standard stack / reuse inventory: HIGH — every file, function, and line number verified by direct reading this session
- D-03 predicate inventory: HIGH — every existing/missing field confirmed by reading the actual filter classes and `_apply_filters` bodies
- CI/eval gate structure: HIGH — confirmed via `ci.yml` and `branch-protection.json` directly, corrected a mismatch between CONTEXT.md's "promptfoo" framing and the actual keyless pytest/DeepEval implementation
- Two-call orchestration architecture: MEDIUM-HIGH — sound extrapolation from proven, read patterns, but the exact orchestration has not been built or spiked
- Anthropic structured-output schema limits (oneOf/anyOf): MEDIUM-HIGH — CITED against official docs fetched this session, but not independently spiked against a live key (none available — see Environment Availability)
- Frontend reuse-seam gaps (useExplainStream body, AiExplanationSection fit, DegradedCard export): HIGH — directly verified by reading the actual component/hook source

**Research date:** 2026-08-24
**Valid until:** 30 days for the internal-codebase findings (stable unless another phase touches these same files first — check `git log` on `app/ai/`, `vulnerabilities/service.py`, `ticketing/service.py` before planning if significant time has passed); 7 days for the Anthropic structured-output schema-limits claim (fast-moving API surface, explicitly flagged beta-adjacent in the fetched docs)
