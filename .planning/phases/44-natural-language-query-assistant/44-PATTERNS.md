# Phase 44: Natural-Language Query Assistant - Pattern Map

**Mapped:** 2026-08-24
**Files analyzed:** 15 (10 backend, 5 frontend) + 3 URL-param wiring touch points
**Analogs found:** 15 / 15

This phase is reuse-heavy on the shipped v3.0 `backend/app/ai/` scaffold. Every analog below was read directly this session (not inferred from RESEARCH.md's summaries) — line numbers are exact as of 2026-08-24.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/ai/query_assistant.py` (NEW) | service (orchestrator) | request-response (two model calls + one DB query, SSE) | `backend/app/ai/explain.py::_run_explain_stream` | role-match (structurally different — single-call vs two-call — see watch-out) |
| `backend/app/ai/prompt_builder.py` (MODIFIED — add 4 functions) | utility (prompt builder) | transform | `build_explain_prioritization_prompt` + `prioritization_prompt_version` (same file, lines 1214-1241) | exact |
| `backend/app/ai/schemas.py` (MODIFIED — add `NlqFilterResponse`, 3 filter-input models, `NlqAnswerResponse`, `recheck_nlq_filter_exclusivity`) | model (Pydantic schema) | transform / validation | `ExplainResponseBase` + `recheck_business_rules` (same file, lines 44-67, 129-161) | exact |
| `backend/app/api/v1/ai/query.py` (NEW) | route | request-response, streaming (SSE) | `backend/app/api/v1/ai/explain_vuln.py` | exact |
| `backend/app/ai/audit.py` (MODIFIED — add `action_prefix` param) | utility (audit writer) | event-driven (write-only) | itself, additive param | exact (self-analog) |
| `backend/app/vulnerabilities/schemas.py` (MODIFIED — add `asset_internet_facing`, `sla_breached` to `VulnerabilityFilter`) | model | CRUD (filter object) | itself, existing fields on same class (lines 127-176) | exact |
| `backend/app/vulnerabilities/service.py` (MODIFIED — add 2 predicates to `_apply_filters`) | service | CRUD | itself, existing `_apply_filters` clauses (lines 44-113) | exact |
| `backend/app/assets/schemas.py` (MODIFIED — add `internet_facing` to `AssetFilter`) | model | CRUD | itself (lines 68-76) | exact |
| `backend/app/ticketing/schemas.py` (NEW class `TicketQueryFilter`) | model (NLQ-only translation wrapper) | transform | `VulnFilterInput`/`AssetFilterInput` (new, same-phase sibling in `ai/schemas.py`) + existing `TicketRuleConditions` (ticketing/schemas.py:138) for file placement convention | role-match |
| `backend/app/api/v1/ai/__init__.py` (MODIFIED — register `query.router`) | route (mount) | — | itself, existing `include_router` calls (lines 52-59) | exact |
| `frontend/src/lib/ai/use-query-stream.ts` (NEW) | hook | streaming (SSE) | `frontend/src/lib/ai/use-explain-stream.ts` | role-match (body-less GET-by-ID hook vs body-carrying POST hook — see watch-out) |
| `frontend/src/components/ai/ask/query-box.tsx` (NEW) | component | request-response (local input state) | `EmptyState`/`CommentInput`-style bounded text input (no single exact analog — see below) | partial |
| `frontend/src/components/ai/ask/starter-questions.tsx` (NEW) | component | — (static + click-to-fill) | `EmptyState.Suggestion` pattern (state-patterns.md, consumed elsewhere) | role-match |
| `frontend/src/components/ai/ask/interpreted-filter.tsx` (NEW) + refusal/degraded cards | component | request-response | `DegradedCard` in `ai-explanation-section.tsx` (lines 30-86) | role-match |
| `frontend/src/components/ai/ask/result-table.tsx` (NEW) | component | CRUD (read, render) | vuln/asset/ticket list-row primitives (`frontend/src/components/vulnerabilities/`, `assets/`, `tickets/`) | role-match (thin wrapper, not a new table) |
| `frontend/src/app/(authed)/dashboard/ask/page.tsx` (NEW) | route/page | request-response | `frontend/src/app/(authed)/dashboard/compliance/page.tsx` | exact |
| `frontend/src/components/shell/nav-items.ts` (MODIFIED — add 1 `WORKFLOW_ITEMS` entry) | config | — | itself, existing entries (lines 56-63) | exact |
| `frontend/src/components/ai/ai-explanation-section.tsx` (MODIFIED — export `DegradedCard`) | component | — | itself, `AnalyzingIndicator`'s existing `export` (line 108) | exact |
| Vuln/Asset/Ticket list `page.tsx` files (MODIFIED — D-17 URL-param wiring, up to 6 new params) | route (URL state) | request-response | `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` (lines 26-77) | role-match (existing hooks are string-enum-only — see watch-out) |

---

## Pattern Assignments

### `backend/app/ai/query_assistant.py` (NEW — service/orchestrator)

**Analog:** `backend/app/ai/explain.py` (import from, do not modify)

**Watch out (RESEARCH):** `_run_explain_stream()` is single-call-shaped (`build_prompt(record) → validate → cache → audit → stream`). NLQ is two-call (translate → execute DB query → narrate). Do **not** parameterize `_run_explain_stream` for this — write a new sibling that reuses its *constituent pieces* by direct import, not the whole function.

**Precondition envelope to copy verbatim** (`explain.py:297-330`):
```python
model, monthly_cap_usd = await get_model_and_budget(db, tenant_id)

api_key = await get_tenant_anthropic_key(db, tenant_id)
if api_key is None:
    yield _sse_event({"type": "no_key"})
    return

if not await check_tenant_budget(db, tenant_id, monthly_cap_usd):
    await notify_admins_budget_exceeded(db, tenant_id)
    await _audit(db, ..., status="budget_exceeded", cost_estimate_usd=0.0)
    yield _sse_event({"type": "error", "kind": "budget_exceeded"})
    return

if not await acquire_inflight(redis_client, tenant_id):
    yield _sse_event({"type": "error", "kind": "busy"})
    return
```
Run this **once** for the whole two-call flow (Pitfall 5: two independent acquire/release calls around translate+narrate can self-block or race). `release_inflight` goes in one shared `finally` (mirrors `explain.py:517-518`).

**Single-call-with-retry loop to extract or duplicate** (`explain.py:343-489`, the `for attempt_index in range(2)` block) — this is the actually-reusable unit (RESEARCH Pattern 1's `_call_structured()` sketch). Duplicating ~40 lines is acceptable per RESEARCH; extracting a shared private helper both `explain.py` and `query_assistant.py` import is the cleaner option if the planner has budget for it.

**Client factory / fresh-per-request discipline** (`explain.py:115-121`):
```python
def _default_client_factory(api_key: str) -> AsyncAnthropic:
    return AsyncAnthropic(api_key=api_key, max_retries=2)
```
Import and reuse this exact function — never a module-level singleton (T-24-19 cross-tenant leak defense).

**Two new SSE event kinds** (`interpreted`, `results`) must be emitted **before** the narrate call starts (D-15) — see `_sse_event()` helper (`explain.py:124-125`), reuse verbatim.

**Constants to import, not redefine:** `MAX_TOKENS = 1024` (`explain.py:80`), `DEFAULT_MODEL` (`explain.py:76`), `_build_output_config` (`explain.py:138-144`).

---

### `backend/app/ai/prompt_builder.py` (MODIFIED — add `build_query_translate_prompt`, `build_query_narrate_prompt`, `query_translate_prompt_version`, `query_narrate_prompt_version`)

**Analog:** `build_explain_prioritization_prompt` + `prioritization_prompt_version` in the SAME file (lines 1214-1241) — the most recently added capability, proving the exact per-capability pattern to repeat a 6th time.

**Pattern to copy** (structure, not literal content):
```python
def build_explain_prioritization_prompt(record: Any) -> tuple[str, list[dict[str, str]]]:
    prioritization = _to_allowlisted_prioritization(record)
    scanner_data = json.dumps(prioritization.model_dump())
    user_block_text = f'<scanner_data source="prioritization">{scanner_data}</scanner_data>'
    return SYSTEM_PROMPT_PRIORITIZATION, [{"type": "text", "text": user_block_text}]

def prioritization_prompt_version() -> str:
    return prompt_version(SYSTEM_PROMPT_PRIORITIZATION, FEW_SHOT_PRIORITIZATION, ExplainPrioritizationResponse)
```

**Watch out:** the NLQ translate prompt wraps the analyst's own question text, not scanner data — use a NEW tag `<user_question>` (not `<scanner_data>`) per RESEARCH's Code Examples section, but apply the exact same isolation contract (`<untrusted_content_policy>` block, verbatim from `SYSTEM_PROMPT_PRIORITIZATION`'s header, lines 1190-1197):
```python
def build_query_translate_prompt(question: str) -> tuple[str, list[dict[str, str]]]:
    user_block_text = f'<user_question>{json.dumps({"question": question})}</user_question>'
    return SYSTEM_PROMPT_QUERY_TRANSLATE, [{"type": "text", "text": user_block_text}]
```
`prompt_version()` itself (lines 318-345) is already generalized to accept `response_model` — call it with `NlqFilterResponse`/`NlqAnswerResponse`, don't re-derive the hashing.

Every existing system prompt in this file follows the SAME 3-part shape: `<untrusted_content_policy>` block → task instructions → `{_render_few_shot(...)}`. Reuse `_render_few_shot()` (lines 265-272) verbatim for the two new few-shot tuples.

---

### `backend/app/ai/schemas.py` (MODIFIED — add `NlqFilterResponse`, `VulnFilterInput`, `AssetFilterInput`, `TicketFilterInput`, `NlqAnswerResponse`, `recheck_nlq_filter_exclusivity`)

**Analog:** `ExplainResponseBase` + `recheck_business_rules` (same file, lines 44-67, 129-161); `AllowlistedFinding` in `prompt_builder.py` (lines 84-107) for the `extra="forbid"` field-by-field discipline.

**`NlqAnswerResponse`** — zero new fields beyond `ExplainResponseBase`:
```python
class NlqAnswerResponse(ExplainResponseBase):
    """No additional fields — narrative lives in summary/business_risk,
    exactly as every other ExplainResponseBase subclass in this file."""
```

**`NlqFilterResponse` — flat, non-union schema (RESEARCH Pattern 2, avoid `oneOf`):**
```python
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

class NlqFilterResponse(BaseModel):
    model_config = {"extra": "forbid"}
    entity: Literal["vulnerabilities", "assets", "tickets"]
    vulnerability_filter: VulnFilterInput | None = None
    asset_filter: AssetFilterInput | None = None
    ticket_filter: TicketFilterInput | None = None
    groundable: bool
```

**Watch out (Pitfall 2):** do NOT use a Pydantic discriminated union (`Field(discriminator="entity")`) — it emits `oneOf` in JSON Schema, which Anthropic's structured-outputs docs do not list as supported (only `anyOf`/`allOf`). Use three independently-optional fields (as above) + an explicit Python recheck, mirroring `recheck_business_rules`'s exact "Anthropic strips constraints, recheck explicitly" precedent:
```python
def recheck_nlq_filter_exclusivity(resp: NlqFilterResponse) -> None:
    filters = {"vulnerabilities": resp.vulnerability_filter,
               "assets": resp.asset_filter, "tickets": resp.ticket_filter}
    matching = filters.pop(resp.entity)
    if resp.groundable and matching is None:
        raise BusinessRuleError(f"entity={resp.entity} but its filter is null")
    if any(f is not None for f in filters.values()):
        raise BusinessRuleError("more than one entity's filter is populated")
```
**Before locking the schema:** run `NlqFilterResponse.model_json_schema()` and grep for `oneOf` (RESEARCH Open Question 1) — a 5-minute check, no live key needed.

`BusinessRuleError` (line 121) is already generic — reuse it, don't create a new exception type.

---

### `backend/app/api/v1/ai/query.py` (NEW)

**Analog:** `backend/app/api/v1/ai/explain_vuln.py` (full file, 104 lines) — copy the POST/GET split verbatim, substituting the grounding-record resolution step.

```python
@router.post("/query")
async def query(
    body: QueryRequest,  # {question: str, max_length=500 per V5}
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> StreamingResponse:
    return StreamingResponse(
        _run_query_stream(
            db, tenant_id=user.tenant_id, user_email=user.email,
            question=body.question, redis_client=redis_client,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```
`require_analyst` on POST (spends the tenant's key), `require_viewer` on any cached/status GET — mirrors `explain_vuln.py`'s exact RBAC split (D-18). Register in `backend/app/api/v1/ai/__init__.py` alongside the existing `ai_router.include_router(...)` calls (lines 52-59) — add `ai_router.include_router(query.router)`.

**Watch out:** unlike `explain_vuln.py`, there's no `finding_id` path param to resolve a tenant-scoped record from — the "record" here is the question text itself plus (after call 1) the executed query results. `QueryRequest.question` needs `Field(..., max_length=500)` (V5 input validation, enforced by FastAPI/Pydantic on the REQUEST body — not stripped by Anthropic since it never reaches the model's own output schema).

---

### `backend/app/ai/audit.py` (MODIFIED — additive `action_prefix` param)

**Analog:** itself — Pitfall 3 flags the hardcoded `f"ai.explain.{resource_type}"` (line 61).

```python
async def audit_log_ai_call(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_email: str, model: str,
    usage: Any, resource_type: str, resource_id: str, status: str,
    cost_estimate_usd: float | None = None,
    action_prefix: str = "explain",  # NEW — every existing call site unaffected
) -> None:
    log = AuditLog(
        ...,
        action=f"ai.{action_prefix}.{resource_type}",  # was: f"ai.explain.{resource_type}"
        ...
    )
```
`query_assistant.py` calls this with `action_prefix="query"` for both the translate and narrate audit rows, giving `ai.query.vulnerabilities` / etc. This is a one-line, backward-compatible change — no other call site needs updating.

---

### `backend/app/vulnerabilities/schemas.py` (MODIFIED — `VulnerabilityFilter` additive fields)

**Analog:** itself, existing fields on the same class (lines 127-176).

```python
class VulnerabilityFilter(BaseModel):
    ...
    exploit_available: bool | None = None       # already exists (line 142)
    cisa_kev: bool | None = None                 # already exists (line 143)
    age_days_min: int | None = Field(None, ge=0)  # already exists (line 146)
    # NEW additive fields (D-03):
    asset_internet_facing: bool | None = None
    sla_breached: bool | None = None
```
Confirmed already-existing (no change needed): `severity`, `status`, `cisa_kev`, `exploit_available`, `age_days_min`. Only `asset_internet_facing` and `sla_breached` are genuinely new.

---

### `backend/app/vulnerabilities/service.py` (MODIFIED — 2 predicates in `_apply_filters`)

**Analog:** itself, existing clause style (lines 44-113) — e.g. `if filters.cisa_kev is not None: query = query.where(Vulnerability.cisa_kev == filters.cisa_kev)` (line 94-95).

```python
if filters.sla_breached is not None:
    query = query.where(Vulnerability.sla_breached == filters.sla_breached)
if filters.asset_internet_facing is not None:
    query = query.join(Asset, Vulnerability.asset_id == Asset.id).where(
        Asset.internet_facing == filters.asset_internet_facing
    )
```
**Watch out (Pitfall 1 — double-join hazard):** `list_vulnerabilities` (same file, lines 133-137) ALREADY does its own `.outerjoin(Asset, Vulnerability.asset_id == Asset.id)` for the `asset_hostname` column, AFTER `_apply_filters` runs. If `_apply_filters` also joins `Asset` when `asset_internet_facing` is set, the SAME query may join `Asset` twice (the count-query path never joins `Asset` today at all, so this is a NEW code path for it specifically). Verify empirically (SQLAlchemy 2.0 join-dedup behavior) before shipping; the safer fallback per RESEARCH is to have `_apply_filters` own the `Asset` join unconditionally, moving `list_vulnerabilities`'s own outerjoin into `_apply_filters`.

`Vulnerability.sla_breached` is a stored "derived mirror" column, refreshed every 60s by `run_sla_tier_pass` (`sla_tier_service.py`) — do not recompute it live; a sub-minute staleness window is accepted (Pitfall 6).

---

### `backend/app/assets/schemas.py` (MODIFIED — `AssetFilter.internet_facing`)

**Analog:** itself (lines 68-76).
```python
class AssetFilter(BaseModel):
    ...
    internet_facing: bool | None = None  # NEW — trivial, native column, no join
```
`backend/app/assets/service.py::_apply_filters` (lines 16-41) gets one matching clause:
```python
if filters.internet_facing is not None:
    query = query.where(Asset.internet_facing == filters.internet_facing)
```
No join needed here (unlike the vuln-side predicate) — `internet_facing` is a native `Asset` column.

---

### `backend/app/ticketing/schemas.py` (NEW class `TicketQueryFilter`)

**Analog:** `VulnFilterInput`/`AssetFilterInput` (new siblings in `ai/schemas.py`, same `extra="forbid"` shape) for the schema pattern; `TicketRuleConditions` (`ticketing/schemas.py:138`) for file-placement convention (a Pydantic filter-shaped model already lives in this file).

```python
class TicketQueryFilter(BaseModel):
    """NLQ-only translation-input wrapper. Maps onto list_tickets's existing
    loose kwargs (provider/status/asset_id/severity/sla/search/source) —
    does NOT change list_tickets's own signature."""
    model_config = {"extra": "forbid"}
    status: str | None = None
    asset_hostname: str | None = None  # resolved server-side via _resolve_hostname, never a UUID
```

**Watch out (RESEARCH — do not refactor `list_tickets`):** `list_tickets` (`backend/app/ticketing/service.py:709-861`) takes loose scalar kwargs, not a `TicketFilter` Pydantic object — there is no existing filter class to extend additively the way `VulnerabilityFilter`/`AssetFilter` work. Its docstring ("severity/sla are post-aggregate filters") is STALE — the real implementation is SQL `WHERE`/`HAVING` already (lines 774-861), so exact-count is not actually a problem here (Pitfall 4) — but do not use the docstring as a design input. Write `TicketQueryFilter` as a translation-layer-only schema; the orchestrator maps its fields onto `list_tickets`'s existing kwargs, e.g. `list_tickets(db, tenant_id, status=filter.status, asset_id=resolved_uuid)`.

"Open tickets for asset X" needs a deterministic hostname→UUID resolution step BEFORE calling `list_tickets` — never let the model emit a UUID:
```python
async def _resolve_hostname(db, tenant_id, hostname: str) -> uuid.UUID | None:
    result = await list_assets(db, tenant_id, AssetFilter(hostname=hostname),
                                PaginationParams(page=1, page_size=1))
    return result.items[0].id if result.items else None
```
Unresolved hostname → treat as a zero-results answer (not a D-14 refusal) per RESEARCH Pattern 3 / Open Question 2, unless eval-planner overrides.

---

### `frontend/src/lib/ai/use-query-stream.ts` (NEW)

**Analog:** `frontend/src/lib/ai/use-explain-stream.ts` (full file, 142 lines) — reuse the SSE-frame-parsing loop (lines 88-138) essentially verbatim.

**Watch out (Pitfall 7 — do NOT reuse `useExplainStream` unchanged):** its `fetch()` call has NO `body` parameter (`use-explain-stream.ts:70-73`) and builds its URL by interpolating a `resourceId` path segment — NLQ has no `resourceId` and must `POST` a JSON `{question}` body. Copy the frame-parsing loop, change the fetch call:

```typescript
// Analog: use-explain-stream.ts:70-73 (has no body param at all)
res = await fetch(`${API_URL}/api/v1/ai/query`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ question }),
});
```
New SSE event types, additive to the `RawSseEvent` union pattern (`use-explain-stream.ts:41-49`), kept in the NEW sibling file so existing explain views' exhaustive branches are untouched:
```typescript
type InterpretedEvent = { type: 'interpreted'; entity: 'vulnerabilities' | 'assets' | 'tickets'; filter: Record<string, unknown> };
type ResultsEvent = { type: 'results'; rows: unknown[]; total: number };
```
The `ExplainStreamState`-shaped state machine (idle/analyzing/done/error) is directly reusable in structure — add `interpreted`/`results` as intermediate phases before `done`, since D-15 requires showing them before the narrative streams.

---

### `frontend/src/components/ai/ask/*.tsx` (NEW — query-box, interpreted-filter, result-table, starter-questions)

**`interpreted-filter.tsx` / refusal / budget / configure-AI cards — Analog:** `DegradedCard` in `ai-explanation-section.tsx` (lines 30-86, full component).
```typescript
// Reuse variant/heading/body/action props verbatim:
<DegradedCard variant="neutral" heading="Can't answer that one" body="..." />
<DegradedCard variant="amber" heading="This tenant's monthly AI budget is used up" body="..." />
<DegradedCard variant="danger" heading="..." body="..." />  // safety-refusal only
```
**Watch out (Pitfall 8):** `DegradedCard` is currently module-private (no `export` at its declaration, `ai-explanation-section.tsx:47`) — it cannot be imported from a new `ask/` component today. Add `export function DegradedCard(...)` — a one-line, zero-behavior-change diff. `AnalyzingIndicator` (line 108) is ALREADY exported — reuse directly for the "Interpreting your question…" state (D-15).

**`starter-questions.tsx` — Analog:** `EmptyState.Suggestion` pattern (consumed project-wide per state-patterns.md) — same violet-soft chip chrome UI-SPEC calls for ("Starter-question chip active/hover state ... same token pair as `EmptyState.Suggestion`, reused verbatim").

**`result-table.tsx` — Analog:** the existing vuln/asset/ticket list-row primitives in `frontend/src/components/vulnerabilities/`, `assets/`, `tickets/` (e.g. `VulnTable` imported in `vulnerabilities/page.tsx:10`). This must be a thin wrapper that picks the right row component based on `entity`, NOT a new table (D-08, sketch-findings explicitly warns against a second table pattern).

**`query-box.tsx` — no exact analog** (first free-text-question input in the codebase). Nearest precedent for a bounded-length text input with a live char-count warning is `CommentInput` (per UI-SPEC's own backstop note) — follow its char-cap/counter convention, not a from-scratch design.

**Narrative/citation rendering:** `AiExplanationCitations` (`ai-explanation-citations.tsx`, full read) is reusable **only if** `NlqAnswerResponse`'s shape mirrors `ExplainResponseBase` exactly (it does, per the schema pattern above) — but it currently imports its `Citation`/`ExplainVulnResponse` types from `use-explain-stream.ts` (line 5). The new `ask/` narrative view either imports those same types (they're structurally identical to `NlqAnswerResponse`) or the component needs a small type-import adjustment — flag this as a one-line wiring detail, not a rewrite.

---

### `frontend/src/app/(authed)/dashboard/ask/page.tsx` (NEW)

**Analog:** `frontend/src/app/(authed)/dashboard/compliance/page.tsx` (full file, 275 lines) — copy the composition shape verbatim:
```
ErrorBoundary(pageErrorFallback) > Suspense(PAGE_FALLBACK) > AskPageInner
```
Reuse directly:
- `useDocumentTitle(PAGE_TITLE)` (compliance/page.tsx:143)
- sr-only `<h1>` heading pattern (compliance/page.tsx:193, matches UI-SPEC's Typography row for the Ask page's own sr-only h1)
- `pageErrorFallback` + `PartialFailureBanner` shape (compliance/page.tsx:64-74)
- Skeleton pattern via `SKELETON_BAR`/`SKELETON_PILL` shimmer classes (compliance/page.tsx:79-80) if a loading skeleton is needed (UI-SPEC's D-15 loading state is lighter-weight — an `AnalyzingIndicator`, not a full skeleton — so this may not be needed at page level, only within the result region)
- `EmptyState` / `EmptyState.Title` / `EmptyState.Body` / `EmptyState.Actions` composition (compliance/page.tsx:213-224) for the D-11 first-run empty state

**Watch out:** unlike Coverage/Analytics/Compliance (which fetch on page load), the Ask page's data flow is submit-triggered (SSE stream after a POST), so the `useQuery`-per-page-load pattern those pages use for `complianceQ`/`coverageSummaryQ` does NOT apply here — the `useAiStatus()` check (D-12 gate) is the only page-load query; everything else is driven by `use-query-stream.ts`'s local state.

---

### `frontend/src/components/shell/nav-items.ts` (MODIFIED)

**Analog:** itself — existing `WORKFLOW_ITEMS` entries (lines 56-63), specifically the most recent 3 (Coverage/Analytics/Compliance, Phases 41-43), each with an explanatory comment and no `chip`.

```typescript
// Phase 44 (44-01, NLQ-01..03) — natural-language query assistant.
// No chip per D-N-01 (not one of the three chip-carrying destinations).
{ label: 'Ask', href: '/dashboard/ask', icon: Sparkles },
```
Import `Sparkles` from `lucide-react` (already imported project-wide, e.g. `ai-explanation-section.tsx:4`) — matches UI-SPEC's "icon family" note (Sparkles is the established AI-feature icon).

---

### `frontend/src/components/ai/ai-explanation-section.tsx` (MODIFIED — export `DegradedCard`)

**Analog:** itself — `AnalyzingIndicator`'s existing `export` (line 108), which already went through exactly this "make a module-private component importable elsewhere" change (Phase 27, per its own comment).
```typescript
// was: function DegradedCard(...)
export function DegradedCard({ variant, heading, body, action, icon = 'sparkles' }: DegradedCardProps) {
```
Zero behavior change — the existing internal call sites in this file are unaffected.

---

### Vuln/Asset/Ticket list `page.tsx` (MODIFIED — D-17 URL-param wiring)

**Analog:** `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` (lines 24-77) — the `useUrlState`/`useUrlStateList` wiring pattern for `severity`/`source`/`status`/`group`/`sort`/`order`.

```typescript
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'] as const;
const [severity, setSeverity, toggleSeverity] = useUrlStateList<Severity>('severity', SEVERITIES, []);
```

**Watch out (RESEARCH — this is a bigger task than it looks):** `useUrlState`/`useUrlStateList` (`frontend/src/hooks/use-url-state.ts`, `use-url-state-list.ts`, both read in full) are **string-enum-clamped only** — `allowed: readonly T[]` with an `includes()` XSS-safety check. They do not natively support:
- booleans (`cisa_kev`, `exploit_available`, `sla_breached`, `internet_facing`) — need `'true'|'false'` string-enum mapping, or a small boolean-flavored wrapper
- numeric ranges (`age_days_min`) — needs a numeric-parse-with-bounds variant, not a plain enum clamp

Even the currently-existing `cisa_kev`/`exploit_available`/`age_days_min` backend filter fields have **zero** URL-param wiring today (confirmed via grep — zero matches for these names in `vulnerabilities/page.tsx`) — this is a **pre-existing gap**, not something Phase 44 introduces. D-17 needs new URL-param plumbing for up to 6 fields total (kev, exploit_available, age_days_min, sla_breached, internet_facing, plus ticket params), not just the 1-2 genuinely-new filter fields. Scope planner tasks accordingly — mechanical but broader than it first appears.

---

## Shared Patterns

### BYOK-inert precondition gate (D-12/NLQ-03)
**Source:** `backend/app/ai/tenant_keys.py::get_tenant_anthropic_key` (returns `None`, never raises) + `backend/app/ai/explain.py:299-306`
**Apply to:** `query_assistant.py`'s orchestrator (backend) and `ask/page.tsx` (frontend, via `useAiStatus()`, byte-identical to how `ai-explanation-section.tsx:163,300-313` already gates its trigger button).

### Fail-closed budget + inflight concurrency (D-18)
**Source:** `backend/app/ai/budget.py::check_tenant_budget` + `backend/app/ai/cache.py::acquire_inflight`/`release_inflight`
**Apply to:** `query_assistant.py` — acquire the inflight lock ONCE for the whole two-call flow (Pitfall 5), not once per call.

### Two-tier citation + `extra="forbid"` schema-validation gate (D-01/D-13)
**Source:** `backend/app/ai/schemas.py::recheck_business_rules` + `backend/app/ai/prompt_builder.py::AllowlistedFinding`
**Apply to:** every new NLQ schema (`NlqFilterResponse`, `NlqAnswerResponse`, `TicketQueryFilter`) — `extra="forbid"` + a business-rule recheck function, never trust the Anthropic-enforced JSON Schema alone.

### `ai.*` audit trail, one row per attempt (D-16/NLQ-02 provability)
**Source:** `backend/app/ai/audit.py::audit_log_ai_call` (+ the new `action_prefix` param)
**Apply to:** both the translate call and the narrate call in `query_assistant.py`, each getting its own audit row with `action_prefix="query"`.

### New top-level nav page shell (D-09)
**Source:** `frontend/src/app/(authed)/dashboard/compliance/page.tsx` (ErrorBoundary > Suspense > PageInner, `useDocumentTitle`, sr-only h1)
**Apply to:** `frontend/src/app/(authed)/dashboard/ask/page.tsx`

### `DegradedCard`/`AnalyzingIndicator` state-card family (D-11/D-12/D-14/E7/E8)
**Source:** `frontend/src/components/ai/ai-explanation-section.tsx`
**Apply to:** every non-happy-path state on the Ask page (configure-AI, refusal, budget-exceeded, safety-refusal, transient-error).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `frontend/src/components/ai/ask/query-box.tsx` | component | request-response | First free-text-question submit input in the codebase — nearest precedent is `CommentInput`'s char-cap/counter convention (UI-SPEC backstop), not a full analog. Planner should treat the 500-char cap + counter as the concrete pattern to copy from `CommentInput`, and everything else (submit button, disabled-while-in-flight state) as novel-but-simple composition of existing button/input chrome tokens (`foundation.md`). |
| `backend/app/ai/query_assistant.py`'s two-call orchestration shape | service | request-response | No existing file in this codebase runs two independent structured-output model calls with a deterministic DB step between them — genuinely new orchestration, built from the constituent pieces of `explain.py` per RESEARCH Pattern 1, not copied from a single existing analog file. |

---

## Metadata

**Analog search scope:** `backend/app/ai/`, `backend/app/api/v1/ai/`, `backend/app/vulnerabilities/`, `backend/app/assets/`, `backend/app/ticketing/`, `frontend/src/lib/ai/`, `frontend/src/components/ai/`, `frontend/src/app/(authed)/dashboard/{compliance,vulnerabilities}/`, `frontend/src/hooks/`, `frontend/src/components/shell/`
**Files read in full or targeted this session:** `explain.py`, `prompt_builder.py`, `schemas.py`, `audit.py`, `cache.py`, `budget.py` (partial), `status.py`, `explain_vuln.py`, `api/v1/ai/__init__.py`, `vulnerabilities/service.py` (targeted), `vulnerabilities/schemas.py` (targeted), `assets/service.py` (targeted), `assets/schemas.py` (targeted), `ticketing/service.py` (targeted, `list_tickets`), `use-explain-stream.ts`, `use-ai-status.ts`, `nav-items.ts`, `ai-explanation-section.tsx`, `ai-explanation-citations.tsx` (partial), `use-url-state.ts`, `use-url-state-list.ts`, `compliance/page.tsx`, `vulnerabilities/page.tsx` (partial)
**Pattern extraction date:** 2026-08-24
