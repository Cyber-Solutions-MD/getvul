# Phase 26: Prioritization Narrative - Research

**Researched:** 2026-07-30
**Domain:** Anthropic Message Batches API (async bulk LLM generation) integrated into an existing `asyncio`-task connector scheduler; a 5th per-view AI grounding/prompt/schema quadruplet; deterministic-score-augment-never-replace enforcement. Extends Phase 24/25's request-path AI scaffold with a genuinely new batch/scheduler dispatch path.
**Confidence:** HIGH (Message Batches API shape verified directly against the installed SDK + official docs; every backend integration seam verified by direct codebase read; the one real ambiguity — what "ASSET-02 score" means for a per-finding sort — is a codebase fact, not a guess, and is flagged for plan-time confirmation)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Batch generation strategy (AIP-02)
- **D-01:** Batch scope = each tenant's **top-N OPEN findings ranked by the existing deterministic ASSET-02 score** (the findings an analyst actually triages first), regenerated **nightly**. Freshness via a **factor-hash** cache-key component: a narrative regenerates only when its exploit/KEV/owner/SLA facts change (mirrors Phase 24 D-18's hash-scoped invalidation). Bounds cost + keeps the highest-value findings fresh; N and exact schedule time are plan-time details. — **Reversibility:** costly — the batch scope + schedule contract is a scheduled path Phase 28's cost/observability gate builds on.
- **D-05:** The nightly batch is dispatched from the connector scheduler (`backend/app/connectors/scheduler.py`) via `asyncio.create_task`, **never inline in a sync tick** (AIP-02 hard constraint — must not stall a connector-sync). It submits ONE Message Batches request per tenant covering the top-N set. Retrieval of async batch results (poll vs webhook, back-off, partial-result handling) is a researcher/planner decision. — **Reversibility:** costly — first use of the scheduler's batch pre-warm path.
- **D-06:** The batch result writes each narrative into the **SAME tenant cache the drill panel reads** (keyed `(finding, factor-hash, model, prompt-version)`), so a batch-warmed narrative is a plain cache hit for the analyst. Each batch item is audited (Phase 24 D-27 / AI-06 audit shape) with distinct status.
- **D-07:** **Fail-closed budget applies to the batch.** Pre-estimate the batch's token cost and refuse submission if it would breach the tenant's monthly cap (reuse Phase 24 D-06's guard); a skipped batch is logged + admin-alerted (D-08 lineage), never a silent partial. — **Reversibility:** reversible.

#### Async-batch cache-miss UX (AIP-01/AIP-02 seam)
- **D-02:** **Cache hit → show it. Miss → on-demand single-request fallback.** An Analyst+ can trigger an **on-demand single-request generation** for an ungenerated finding, reusing Phase 24's request-path `_run_explain_stream()` engine with a new `resourceType` (instant, spends a little). A finding queued for the next batch but not yet ready shows a neutral **"Prioritization narrative is being prepared"** state. Viewers stay cached-only (D-17). Best analyst experience without waiting up to 24h. — **Reversibility:** reversible.

#### Augment-never-replace surface + enforcement (Pitfall #7 / SC2)
- **D-03:** The narrative surfaces in a **new dedicated "Prioritization" drill-panel section** (like the Phase 25 remediation-guidance section), **explanatory prose only**, reusing Phase 24's AI section chrome + citation component. The response **schema carries NO numeric rank/priority field**, and **NO list column or sort control is added** — the deterministic ASSET-02 score stays the ONE sortable/authoritative number in every list and view. Enforced in the output schema AND the UI, not just design intent. — **Reversibility:** costly — the "no AI rank" schema/UI contract is the literal Pitfall-#7 mitigation Phase 28 audits.

#### Grounding factors + owner-PII (AIP-01 / SC1)
- **D-04:** The narrative is grounded in these **structured facts** (fed as data, never free reasoning), all already on the models: `cvss_v3_score`, `epss_score`, `exploit_available`, `cisa_kev`, `exploit_status_name`, `severity`, `sla_due_at`, `sla_breached`. **Owner is expressed as the non-PII `Asset.department`** (e.g. "owned by Finance") — **NEVER `assigned_user` / directory identity / email** — honoring Phase 24 D-15's owner-PII exclusion, allowlist-enforced at the query + prompt-builder layers. — **Reversibility:** costly — the factor allowlist is a grounding contract.
- **D-08:** The narrative must **explain the score's drivers, not invent a competing verdict** — e.g. "ranked high because it's KEV-listed, has a public exploit, and its SLA is breached" — referencing the same signals the deterministic score already uses (AIP-01 "augment and explain"). It does not assert its own priority number.

#### Reuse (defaults, not re-litigated)
- **D-09:** Reuse Phase 24/25 wholesale: `_run_explain_stream()` for the on-demand path, the grounding-assembler + schema-variant + prompt-builder quadruplet pattern, cache/budget/audit/RBAC, the frontend AI section + citation component, `prompt_version` auto-hash (D-20). Phase 26 adds only: a prioritization grounding query, a `ExplainPrioritization…`-style schema (no rank field), a prompt builder, the batch submit/retrieve flow, and the scheduled pre-warm job. English-only (D-28) carried forward.

### Claude's Discretion
- Exact N for top-N and the nightly schedule time (D-01).
- Batch result retrieval mechanism — poll vs webhook, back-off, partial/failed-item handling (D-05) — researcher recommends.
- Exact factor-hash field set (D-01) and drill-panel placement/ordering (UI-SPEC).
- Whether the on-demand fallback and batch share one prompt/schema or need slight variants (default: share).

### Deferred Ideas (OUT OF SCOPE)
- **Ticket auto-drafting** (title/description/remediation/asset-context, provider field mapping) → Phase 27 (AID-01).
- **AI usage/cost dashboard, per-tenant cost circuit breaker sophistication, eval harness (DeepEval/promptfoo)** → Phase 28. This phase writes audit rows + enforces the simple fail-closed budget guard, but builds no dashboard.
- **An independently-sortable AI priority rank** — explicitly OUT (violates AIP-01/SC2/Pitfall #7); never build.
- Non-English narratives → out of milestone scope (D-28 carried forward).

None of the above are built in Phase 26.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AIP-01 | An analyst can see a "what to fix first and why" narrative that **augments and explains — never replaces** — the deterministic risk score, using exploit/KEV/owner/SLA factors | Pattern 7 (the 5th grounding/schema/prompt-builder quadruplet — a zero-rank-field schema IS the D-03 enforcement mechanism), Pattern 3 (D-01 top-N batch scope + the "OPEN" status semantics), Don't Hand-Roll table (no second AI-priority number, ever), Security Domain (the No-Rank threat pattern + its checkable mitigation) |
| AIP-02 | Prioritization/triage suggestions are generated **in bulk via the scheduler using the Message Batches API** (cost-efficient), respecting the tenant's key | Pattern 1 (Message Batches API call/poll/retrieve shape, verified against the installed SDK + official docs), Pattern 2 (the exact scheduler hook — which existing idiom to copy and which NOT to), Pattern 4 (the durable `AiBatchJob` registry, required because in-memory tracking is provably unsafe across a 24h window), Pattern 6 (budget pre-estimate + the batch discount math), Pattern 8 (single-pass batch-result validation, distinct from the interactive retry engine) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

| Directive | Applies to Phase 26 |
|-----------|---------------------|
| Read `sketch-findings-getvul` skill before any frontend work | Already satisfied — `26-UI-SPEC.md` (approved) fully encodes the relevant `state-patterns.md`/`copy-voice.md` guidance for the one new "queued" state and the No-Rank contract. This research does not re-derive UI decisions; the UI-SPEC is authoritative for all copy/visual choices, per this phase's own "reuse unchanged, do not redesign" directive. |
| Don't substitute fonts (Inter + JetBrains Mono locked) | No new typography introduced — 26-UI-SPEC.md confirms an identical scale to Phase 24/25, no new size/weight, and explicitly states JetBrains Mono is NOT used in the new copy. |
| Don't pick hex colors freehand | The one new visual element (the "queued" pending card) reuses the EXISTING `--color-violet`/`--color-surface-2` neutral family verbatim (UI-SPEC: "SAME color family as insufficient-evidence, deliberately not a new hue") — no new hex value anywhere in this phase. |
| Don't ship a screen without empty/loading/error states | 26-UI-SPEC.md's state-coverage table explicitly covers empty/loading/error/**pending (NEW)**/populated/no-rank/overflow/long-text for the new section — this research's Validation Architecture section maps each backend-observable state to a concrete test. |
| Don't use Tailwind admin-template patterns | Not applicable — this phase adds zero new visual chrome; it reuses the existing `AiExplanationSection`/`DegradedCard` components verbatim with one additive icon prop (Code Examples section). |
| Don't compose generic SaaS copy | Not applicable to this research — 26-UI-SPEC.md's Copywriting Contract already locks every string this phase introduces (e.g. "Prioritization narrative is being prepared"); no new copy is authored here. |
| Backend: FastAPI + Postgres + Redis | No new infrastructure — the new `AiBatchJob` table uses the existing Postgres instance; the batch result cache uses the existing Redis instance; no new datastore, queue, or service is introduced (see Don't Hand-Roll). |
| Frontend: Next.js 15 App Router + React 19 + TS 5.5 + Tailwind 3.4 | No framework change; no new package (the one new `lucide-react` icon import, `Clock`, is already a dependency per 26-UI-SPEC.md's Registry Safety table). |

## Summary

Phase 26's genuinely new territory is narrow but load-bearing: submit one Anthropic Message Batch per tenant per night from the connector scheduler, track it across a window that can legitimately last up to 24 hours, and write validated results into the same Redis cache the interactive "Explain the priority" fallback and the drill panel both read. The Message Batches API itself is fully verified against the installed `anthropic==0.120.2` SDK (`client.messages.batches.create/retrieve/results/cancel/list`) and the current official guide: submit a list of `{custom_id, params}` requests (same shape as `client.messages.create()`, non-streaming, `output_config` supported so the existing structured-output contract carries over unchanged), poll `retrieve()` (idempotent) until `processing_status == "ended"` — **there is no webhook; polling is the only retrieval mechanism the API offers** — then stream `.jsonl` results via `results()`, matching each line back to its request by `custom_id` (order is never guaranteed). Pricing is a flat 50% discount on every model, on both input and output tokens; results are retained 29 days; a batch is capped at 100,000 requests or 256MB (whichever first) with per-tenant-key rate limits (100,000 requests per batch on Start/Build tier, up to 500,000 requests queued at once on Scale) — none of which GetVul will approach at a "top-N findings per tenant" scale.

Two facts surfaced by direct codebase reads reshape the plan more than the API research does. First, **"the deterministic ASSET-02 score" is a per-ASSET aggregate (`Asset.risk_score`, computed by `backend/app/assets/risk_score.py`), not a per-finding column** — `Vulnerability` has no `risk_score` field at all. D-01's "top-N OPEN findings ranked by the existing deterministic ASSET-02 score" therefore needs a concrete, plan-time-confirmed interpretation (this research recommends joining to `Asset.risk_score` with a per-finding KEV/CVSS/SLA tiebreak, not a pure per-finding reinterpretation) — see Pattern 3 and Assumption A1. Second, **the scheduler's existing in-memory task registry (`_running_syncs: dict[str, asyncio.Task]`) is the wrong precedent to copy for tracking a submitted batch** — connector syncs finish in seconds/minutes within one process lifetime; a Message Batch can legitimately still be `in_progress` 24 hours later, past any deploy/restart. Submitted batches MUST be persisted to Postgres (a new `AiBatchJob` row), not tracked only in a module-level dict, or a restart silently orphans in-flight spend with no way to retrieve results. A third, subtler correctness risk: batch-derived cost must be recorded at **half** the standard per-token rate (`_estimate_cost_usd()` as it exists today computes the *interactive* rate) — forgetting the batch discount when writing `cost_estimate_usd` into the audit row would make `check_tenant_budget()`'s month-to-date SUM systematically over-count real spend by 2x.

**Primary recommendation:** Add one new grounding/schema/prompt-builder quadruplet member (`prioritization`, mirroring the `remediation-guidance` quadruplet added in Phase 25 almost line-for-line), one new small module (`backend/app/ai/batch.py`) holding the batch-cost-estimate/submit/poll/validate functions, one new Postgres table (`AiBatchJob`) as the durable submitted-batch registry, and two new `try/except` blocks inside the scheduler's existing `_scheduler_loop()` — a nightly (24h-gated, mirroring the existing `_last_ticket_sync` timing idiom) submission block and an every-tick polling block — **both wrapped in `asyncio.create_task`**, unlike the two *existing* "nightly" blocks in that same loop (ticket status sync, snapshot capture), which run inline today and are the wrong precedent to copy for this phase's explicit hard constraint.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Top-N batch-scope selection (D-01 query) | API / Backend | Database / Storage | New SQLAlchemy query joining `Vulnerability`+`Asset`, ordered by risk factors — pure DB read |
| Per-finding prioritization grounding record (allowlisted) | API / Backend | — | New `get_prioritization_context()` in `grounding.py`, mirrors existing quadruplet members exactly |
| Batch cost pre-estimate (D-07) | API / Backend | — | `count_tokens()` SDK call (free, separate rate-limit bucket) + existing pricing table, no new infra |
| Batch submission (Message Batches API) | API / Backend | — | `asyncio.create_task`-dispatched from the scheduler; a real outbound network call to Anthropic |
| Submitted-batch durability across the 24h window | API / Backend | Database / Storage | MUST be a Postgres row, not an in-memory dict — survives process restarts |
| Batch polling + result retrieval | API / Backend | — | `asyncio.create_task`-dispatched, runs on the scheduler's existing 60s tick |
| Batch result validation (schema + business-rules + grounded check) | API / Backend | — | A new, simpler single-pass validator — NOT `_run_explain_stream()`'s retry-loop shape, which assumes a live, retryable conversation |
| Shared tenant cache write (batch AND on-demand) | API / Backend | Database / Storage (Redis) | Same `build_cache_key()`/`set_cached()` Phase 24 already built — zero changes needed |
| Fail-closed budget guard (interactive AND batch) | API / Backend | Database / Storage (Postgres audit) | Same `AuditLog`-derived SUM query Phase 24 built, extended with a batch-aware pre-check |
| Admin alert on skipped batch (D-07/D-08) | API / Backend | Database / Storage (notifications) | Reuses `notify_admins_budget_exceeded()` verbatim — zero new code |
| On-demand single-request fallback (D-02) | API / Backend | — | `_run_explain_stream()` reused unchanged with `resource_type="prioritization"` |
| "Queued, not ready yet" signal | API / Backend | — | New boolean on the existing GET cache-check response, derived from the `AiBatchJob` registry |
| Prioritization narrative rendering + no-rank enforcement | Browser / Client | — | New branch in the existing shared `AiExplanationSection`; UI-SPEC already locks this contract |

## Standard Stack

### Core

No new external library. Phase 26 uses functionality **already present** in the installed `anthropic` SDK that Phases 24/25 have not yet exercised (the Batches resource + the token-counting resource), plus GetVul's own existing Postgres/Redis/SQLAlchemy stack.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | `0.120.2` (already installed, unchanged) | `client.messages.batches.{create,retrieve,results,cancel}` + `client.messages.count_tokens()` | [VERIFIED: `backend/.venv` introspection, this session — `hasattr(client.messages, 'batches')` is `True`; exact method signatures extracted via `inspect.signature()`, matching the official docs verbatim] |
| pydantic | already installed (v2) | New `ExplainPrioritizationResponse` schema | [VERIFIED: codebase] Same pattern as every existing `Explain*Response` variant |
| SQLAlchemy / Alembic | already installed | New `AiBatchJob` model + migration `033_...py` | [VERIFIED: codebase] Same pattern as `AiFeedback`/migration `032_add_ai_feedback.py` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| n/a — `client.messages.count_tokens()` | part of `anthropic` SDK, already installed | Free, exact pre-submission input-token estimate for the D-07 budget guard | [CITED: platform.claude.com/docs/en/build-with-claude/token-counting, fetched this session] "Token counting is free to use... You are not billed for system-added tokens." Has its own separate RPM bucket (2,000/4,000/8,000 per tier), independent of the Messages API's rate limits — calling it before every nightly batch never competes with interactive request budget. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `count_tokens()` for the pre-submission budget estimate | A char-count heuristic (`len(text) / 4`) | Free and zero-network, but imprecise (±20-30%+ depending on content, and Claude 4.7+/Fable/Mythos tokenizers produce ~30% more tokens than earlier models for the same text per the official docs) — a heuristic under-estimate could let a batch through that actually breaches the cap. `count_tokens()` costs nothing and one extra round-trip per nightly run per tenant is negligible; there is no real reason to accept the imprecision. |
| A new `AiBatchJob` Postgres table (durable registry) | Tracking submitted batch IDs only in the existing in-memory `_running_syncs`-style dict | An in-memory-only registry is provably wrong here: connector syncs (`_running_syncs`'s actual use today) finish within one process's lifetime; a Message Batch can still be `in_progress` up to 24h later, spanning restarts/deploys. Losing the `message_batch_id` orphans real spend with no way to ever retrieve results — this is not a style preference, it is a correctness requirement given the API's own stated processing window. |
| Polling on the scheduler's existing 60s tick | A dedicated poller process / Celery-beat-style scheduled task / webhook receiver | Anthropic's Message Batches API has **no webhook mechanism** at all (confirmed absent from the fetched official guide — the guide's own canonical example is a `while True: retrieve(); sleep(60)` loop). A separate process is real infra GetVul doesn't have today (no task queue exists in this codebase — the "scheduler" IS an in-process `asyncio` loop). Reusing the existing 60s tick costs zero new infrastructure and happens to match Anthropic's own reference polling interval exactly. |

**Installation:** None required — every capability used is already present in `backend/pyproject.toml`'s pinned `anthropic>=0.120.0`.

**Version verification:** [VERIFIED, this session] `backend/.venv/bin/python -c "import anthropic; print(anthropic.__version__)"` → `0.120.2`. `pip show`/`pyproject.toml` both agree. No bump needed — the Batches resource and `count_tokens()` are both already present on this exact installed version; nothing about Phase 26 requires touching `pyproject.toml`.

## Architecture Patterns

### System Architecture Diagram

```
[Scheduler _scheduler_loop(), every 60s tick]
        |
        +-- (existing) connector-sync dispatch loop -- UNCHANGED, runs first
        |
        +-- NEW block A: "has 24h elapsed since last AI batch submission?"
        |     (mirrors the EXISTING _last_ticket_sync 24h-gate idiom)
        |     |
        |     +-- asyncio.create_task(run_batch_prewarm(db))   <-- non-blocking
        |             |
        |             v
        |     [batch.py: run_batch_prewarm(db)]
        |             |
        |             1. SELECT active tenants  (mirrors SLA-check block's tenant loop)
        |             2. for each: get_tenant_anthropic_key() -- skip silently if None (D-23 parity)
        |             3. get_top_findings_for_ai_batch(db, tenant_id, N)   -- D-01 query
        |             4. for each finding: get_prioritization_context() + record_hash()
        |             5. SKIP findings whose (hash,model,prompt_version) cache key is
        |                already a hit -- D-01 "regenerates only when facts change"
        |             6. build_explain_prioritization_prompt() per remaining finding
        |             7. count_tokens() per request --> sum --> x0.5 (batch discount)
        |             8. check_tenant_budget_for_batch(...)
        |             |
        |             +-- OVER cap --> notify_admins_budget_exceeded() + audit
        |             |               "batch_skipped_budget_exceeded" --> STOP, no submit
        |             |
        |             +-- OK -----> client.messages.batches.create(requests=[...])
        |                             |
        |                             v
        |                       INSERT AiBatchJob(tenant_id, anthropic_batch_id,
        |                             status="in_progress", custom_id_map={finding_id: hash})
        |
        +-- NEW block B: "poll every tick" (ALSO asyncio.create_task-wrapped)
              |
              v
        [batch.py: poll_pending_batches(db)]
              |
              1. SELECT AiBatchJob WHERE status='in_progress'
              2. for each: client.messages.batches.retrieve(anthropic_batch_id)  -- idempotent
              |
              +-- processing_status != "ended" --> no-op, try again next tick
              |
              +-- processing_status == "ended" -->
                      client.messages.batches.results(anthropic_batch_id)  -- streams .jsonl
                      for each MessageBatchIndividualResponse (match by custom_id):
                        - succeeded --> validate_and_cache_batch_result()
                              (schema validate -> business-rule recheck -> grounded check
                               -> leak-marker check -> set_cached() + audit "ok",
                               cost x0.5 discount applied)
                        - errored/canceled/expired --> audit distinct status, NO cache write
                      UPDATE AiBatchJob SET status='completed'

[Analyst opens drill panel]
        |
        v
[Frontend] AiExplanationSection(resourceType='prioritization')
        |  GET /api/v1/ai/explain-prioritization/{finding_id}   (cache-check, no model call)
        v
[Backend GET route]
        cache HIT  --------------------------------------> render cited narrative (D-08 prose)
        cache MISS, finding_id in an in-flight AiBatchJob.custom_id_map --> {queued: true}
        cache MISS, not queued -----------------------------------------> {queued: false}
        |
        v (queued=true, Analyst+)         (queued=false, Analyst+)
   "being prepared" card,          "Explain the priority" button
   subordinate "Generate it now" -------> POST /explain-prioritization/{finding_id}
        link  ---------------------------> _run_explain_stream(..., resource_type="prioritization")
                                              (D-02 on-demand fallback, UNCHANGED engine)
```

### Recommended Project Structure

```
backend/app/ai/
├── grounding.py            # + get_prioritization_context() -- 5th quadruplet member
├── schemas.py                # + ExplainPrioritizationResponse(ExplainResponseBase): pass
├── prompt_builder.py          # + PRIORITIZATION_ALLOWLIST + AllowlistedPrioritization +
│                                  build_explain_prioritization_prompt() + prioritization_prompt_version()
├── budget.py                   # + reusable month-to-date-spend helper + check_tenant_budget_for_batch()
├── models.py                     # + AiBatchJob (new table, alongside existing AiFeedback)
├── batch.py                       # NEW module: estimate_batch_cost_usd(), run_batch_prewarm(),
│                                     poll_pending_batches(), validate_and_cache_batch_result()
└── api/v1/ai/
    └── explain_prioritization.py    # NEW thin route: POST (on-demand fallback) + GET (cache-check + queued flag)

backend/app/vulnerabilities/
└── service.py                # + get_top_findings_for_ai_batch() -- D-01 top-N query (list/sort concern,
                                 not a grounding concern -- lives alongside list_vulnerabilities()'s own
                                 sort logic, not in ai/grounding.py)

backend/app/connectors/
└── scheduler.py               # + 2 new try/except blocks inside _scheduler_loop(): nightly submit
                                  (24h-gated) + every-tick poll -- BOTH asyncio.create_task-wrapped

backend/alembic/versions/
└── 033_add_ai_batch_job.py    # NEW migration

frontend/src/components/ai/
└── ai-explanation-section.tsx  # + isPrioritization discriminator (mirrors isRemediationGuidance) +
                                   a 'queued' branch (Clock icon, same neutral/violet DegradedCard variant)

frontend/src/lib/queries/
└── use-explain-cache.ts        # + optional queued?: boolean (mirrors the Phase 25 groundable precedent)

frontend/src/components/vulnerabilities/
└── drill-content.tsx           # + new <section aria-labelledby="drill-prioritization-h"> between the
                                   EXISTING drill-ai-h section and drill-remed-h section (UI-SPEC-locked order)
```

---

### Pattern 1: The Message Batches API call shape — verified against the installed SDK, not training data

**What:** The exact submit/poll/retrieve/cancel call signatures.

**Evidence [VERIFIED: installed `anthropic==0.120.2`, introspected this session + CITED: platform.claude.com/docs/en/build-with-claude/batch-processing, fetched this session]:**

```python
# Submit -- backend/app/ai/batch.py
from anthropic.types.messages.batch_create_params import Request
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming

batch = await client.messages.batches.create(
    requests=[
        Request(
            custom_id=str(finding_id),          # ^[a-zA-Z0-9_-]{1,64}$ -- a bare UUID is safe (36 chars, hyphens allowed)
            params=MessageCreateParamsNonStreaming(
                model=model,
                max_tokens=MAX_TOKENS,            # reuse explain.py's existing constant (1024)
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_blocks}],
                output_config=output_config,       # SAME _build_output_config() explain.py already builds
            ),
        )
        for finding_id, (system_prompt, user_blocks, output_config) in per_finding_prompts.items()
    ],
)
# batch.id, batch.processing_status ("in_progress"), batch.expires_at (created_at + 24h exactly),
# batch.request_counts (all fields 0 except .processing until the WHOLE batch ends)

# Poll -- idempotent, safe to call every scheduler tick
refreshed = await client.messages.batches.retrieve(batch.id)
if refreshed.processing_status == "ended":
    async for line in await client.messages.batches.results(batch.id):
        # line: MessageBatchIndividualResponse(custom_id=..., result=<discriminated union>)
        match line.result.type:
            case "succeeded":
                message = line.result.message   # a normal anthropic Message object
            case "errored":
                error = line.result.error        # ErrorResponse
            case "canceled" | "expired":
                pass  # no payload
```

Confirmed method surface on `AsyncBatches` (via `inspect.signature`): `create`, `retrieve`, `list`, `delete`, `cancel`, `results` — matches the official docs one-for-one. `MessageCreateParamsNonStreaming` (the batch item's `params` type) includes `output_config` as a first-class field — **the exact structured-output mechanism `_build_output_config()` already builds for the interactive path carries over into a batch request unchanged.** This is the single most important compatibility fact: Phase 26 does not need a different response-shaping mechanism for batch vs. interactive.

**Status lifecycle [CITED, HIGH confidence]:** `processing_status: "in_progress" | "canceling" | "ended"`. `request_counts` (`canceled`/`errored`/`expired`/`processing`/`succeeded`) are **all zero except `processing` until the ENTIRE batch ends** — confirmed both in the SDK's own type docstrings and the official guide. **This means results are batch-atomic in availability**: even though Anthropic processes each request independently server-side, GetVul cannot observe "3 of 50 done" partway through — the UI's "being prepared" state is correct to treat the whole tenant's batch as one on/off signal, never a progress bar.

**No webhook exists.** The entire official guide's retrieval story is polling `retrieve()` in a loop; no callback/webhook registration is described anywhere. This settles CONTEXT.md's "poll vs webhook" discretion point as not actually a choice — poll is the only option the API offers.

**Limits [CITED]:** 100,000 requests OR 256MB per batch, whichever first; `custom_id` must match `^[a-zA-Z0-9_-]{1,64}$`; `max_tokens` must be ≥1 (batch does not support the `max_tokens: 0` cache-prewarm trick); `stream`/`speed`/`store`/`previous_thread_event_id`/`cache_hint`/`context_hint` are rejected inside a batch request (none of these are used by GetVul's existing prompt-builder output, so no conflict). Rate limits are a SEPARATE bucket from the Messages API (its own RPM + "batch requests in processing queue" ceiling per usage tier, e.g. Build tier: 2,000 RPM / 300,000 queued / 100,000 per batch) — batch usage never competes with interactive request budget.

**Pricing [CITED]:** Flat 50% discount vs. standard price, on every model, both input and output tokens uniformly. Results retained 29 days from `created_at` (not `ended_at`); a batch can be deleted any time after it ends via `DELETE`, or canceled (which then still ends with partial results for whatever finished before cancellation).

---

### Pattern 2: Scheduler hook — mirror `trigger_background_sync()`'s dispatch shape, NOT the existing "nightly" blocks' inline-await shape

**What:** Exactly where and how the nightly batch submission plugs into `backend/app/connectors/scheduler.py`.

**Evidence [VERIFIED: direct read, `backend/app/connectors/scheduler.py`]:** The file already contains TWO structurally different "run periodically" idioms that look superficially similar but are not equally safe to copy:

1. **The non-blocking idiom (the one to copy):** `trigger_background_sync()` (lines 53-62) does `task = asyncio.create_task(_run_single_sync(connector_id, tenant_id)); _running_syncs[connector_id] = task` — fire-and-forget, tracked in a dict, the loop itself never `await`s the task directly.
2. **The inline-await idiom (the one NOT to copy, despite looking like a "nightly" precedent):** the daily ticket-status-sync block (lines 152-165) and the daily-snapshot-capture block (lines 167-177) both gate on a single global `_last_ticket_sync: datetime | None` checked via `(now - _last_ticket_sync).total_seconds() >= 86400`, but then `await run_daily_ticket_sync(db)` / `await capture_all_snapshots(db)` **directly inside the loop body** — genuinely blocking the tick until they finish.

D-05 is an explicit hard constraint ("dispatched... via `asyncio.create_task`, never inline in a sync tick") — idiom 2 is the WRONG one to imitate even though it is the more superficially similar "runs once every 24h" pattern already in this exact file. The correct synthesis is: **reuse idiom 2's timing gate** (a global `_last_ai_batch_prewarm: datetime | None`, checked the same way) **combined with idiom 1's dispatch mechanism** (`asyncio.create_task`, not a direct `await`).

**Recommendation — two new blocks inside `_scheduler_loop()`, each its own `try/except` (matching the file's existing one-block-per-concern convention: SLA check, ticket rules, reports, daily ticket sync, snapshot capture, alert checks are already seven such blocks):**

```python
# NEW block A -- nightly submission (24h-gated like _last_ticket_sync, but
# asyncio.create_task-dispatched like trigger_background_sync -- NOT
# awaited inline, unlike this file's OTHER two 24h-gated blocks).
global _last_ai_batch_prewarm
try:
    now = datetime.now(UTC)
    if _last_ai_batch_prewarm is None or (now - _last_ai_batch_prewarm).total_seconds() >= 86400:
        from app.ai.batch import run_batch_prewarm
        asyncio.create_task(run_batch_prewarm())   # fire-and-forget; opens its OWN db session
        _last_ai_batch_prewarm = now
except Exception as e:
    logger.error("ai_batch_prewarm_dispatch_error", error=str(e))

# NEW block B -- poll every tick (ALSO create_task-wrapped: retrieve() is
# cheap, but N tenants x however many ticks a 24h window spans is real
# cumulative latency if run inline; extend D-05's "never stall a tick"
# discipline uniformly rather than only where literally mandated).
try:
    from app.ai.batch import poll_pending_batches
    asyncio.create_task(poll_pending_batches())
except Exception as e:
    logger.error("ai_batch_poll_dispatch_error", error=str(e))
```

`run_batch_prewarm()`/`poll_pending_batches()` should each open their own `async with async_session_factory() as db:` internally (mirroring `_run_single_sync()`'s own pattern, lines 27-28) since they're now detached from the loop's own `db` variable once wrapped in `create_task`.

**How the app learns a batch finished:** there is no push notification — `poll_pending_batches()` is the only mechanism, running on the existing 60-second cadence. Since `expires_at` is always `created_at + 24h` and most batches finish "in under 1 hour" per the official guide, in practice a submitted-tonight batch is very likely to show `ended` within the first few ticks after submission, not anywhere near the 24h ceiling — but the design must not assume this; a stalled/slow batch just keeps polling harmlessly until it ends or expires.

---

### Pattern 3: The D-01 top-N query — "ASSET-02 score" is per-asset; findings need a concrete tiebreak

**What:** The concrete query for "each tenant's top-N OPEN findings ranked by the existing deterministic ASSET-02 score."

**Evidence [VERIFIED: direct read, `backend/app/assets/risk_score.py` + `backend/app/vulnerabilities/models.py` + `backend/app/vulnerabilities/service.py`]:**

`Asset.risk_score` (0-100, `backend/app/assets/models.py`) is computed by `compute_risk_scores()` in `backend/app/assets/risk_score.py`: a piecewise curve over the SUM of `severity_weight × exploit_multiplier(2x) × kev_multiplier(3x)` across every OPEN/IN_PROGRESS vulnerability on that asset. **`Vulnerability` has no `risk_score` column at all** — confirmed by grepping the full model definition (only `cvss_v3_score`, `severity`, `epss_score`, `exploit_available`, `cisa_kev`, `exploit_status_id/name`, `sla_due_at`, `sla_breached` exist as scoring-relevant fields). "ASSET-02" is a per-ASSET aggregate; there is no existing per-finding equivalent number to sort by directly.

Separately, `vulnerabilities/service.py::list_vulnerabilities()` already has a `sort="triage"` option (D-T-01, Phase 11): `KEV desc → CVSS desc → SLA-due asc` at the *finding* level — this is the analyst-facing "what to triage first" ordering today, and is textually very close to D-01's own parenthetical ("the findings an analyst actually triages first"), but it is a DIFFERENT number from `Asset.risk_score` and CONTEXT.md names the latter specifically.

**Recommendation (flagged for plan-time confirmation, see Assumption A1):** honor D-01's literal naming (rank by the asset's `risk_score`, since that IS "the ASSET-02 score") as the PRIMARY sort key, with the existing `sort=triage` factors as a per-finding tiebreak — this avoids a pure `Asset.risk_score`-only sort silently returning dozens of findings from one already-well-understood high-risk asset before ever reaching a CRITICAL/KEV finding on a slightly-lower-risk-score asset:

```python
# backend/app/vulnerabilities/service.py
async def get_top_findings_for_ai_batch(
    db: AsyncSession, tenant_id: uuid.UUID, limit: int,
) -> list[uuid.UUID]:
    """D-01 batch-scope query. 'OPEN' is interpreted as status IN
    ('OPEN','IN_PROGRESS') -- matching ASSET-02's OWN scoring input
    (risk_score.py) and get_asset_posture()'s vuln_counts precedent, not
    literally status == 'OPEN' only (which would exclude findings still
    counted in the very risk_score.py sum this batch is scoped by)."""
    result = await db.execute(
        select(Vulnerability.id)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .order_by(
            nulls_last(desc(Asset.risk_score)),               # primary: the literal ASSET-02 number
            desc(Vulnerability.cisa_kev),                       # tiebreak, mirrors sort=triage
            nulls_last(desc(Vulnerability.cvss_v3_score)),
            nulls_last(asc(Vulnerability.sla_due_at)),
        )
        .limit(limit)
    )
    return [row[0] for row in result.all()]
```

An asset-less finding (`asset_id IS NULL`, e.g. a scanner correlation gap) gets `Asset.risk_score` = NULL → `nulls_last` sorts it after every scored finding, never crowding out real triage priority — consistent with how every other NULL-tolerant sort in this file already behaves.

---

### Pattern 4: Durable batch registry — a new Postgres table, not the in-memory `_running_syncs` shape

**What:** How to track a submitted batch across the up-to-24h window, and how the app learns which cached result belongs to which finding.

**Evidence [VERIFIED: direct read, `backend/app/ai/models.py` (existing `AiFeedback`) + `backend/alembic/versions/032_add_ai_feedback.py`]:** GetVul already has exactly one prior "new AI-domain table" precedent to mirror: `AiFeedback` — a small model in `app/ai/models.py`, its own numbered migration, `tenant_id` as an explicit indexed column (not resolved via a join), `TimestampMixin`/`UUIDPrimaryKeyMixin` reused. `AiBatchJob` should follow the identical shape:

```python
# backend/app/ai/models.py -- alongside AiFeedback
class AiBatchJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """D-05/D-06: the durable registry for a submitted Message Batch. An
    in-memory dict (like scheduler.py's _running_syncs) is NOT sufficient --
    a batch can legitimately still be in_progress up to 24h later, spanning
    a backend restart; losing this row orphans real spend with no way to
    ever retrieve results (Pitfall 2)."""
    __tablename__ = "ai_batch_jobs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anthropic_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")  # in_progress|completed
    model: Mapped[str] = mapped_column(String(50), nullable=False)         # resolved at submit time -- frozen
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)  # ditto
    # custom_id -> factor_hash, so the poller can rebuild the SAME cache key
    # build_cache_key() would compute -- avoids a second child table for a
    # single-purpose per-item lookup (mirrors AuditLog.details' free-form
    # JSONB precedent rather than a new relational table).
    custom_id_hash_map: Mapped[dict] = mapped_column(JSONB, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Reusing `model`+`prompt_version` frozen at submission time (rather than recomputing at poll time) matters: if a tenant changes their configured model between submission and completion, the poller must still build the cache key the SUBMITTED requests actually used, or a completed narrative would be written under a cache key the drill panel's GET route (which resolves the tenant's CURRENT model) would never look up — a silent, permanent cache miss.

**The GET cache-check's new `queued` signal** is then a cheap, indexed lookup: `SELECT 1 FROM ai_batch_jobs WHERE tenant_id = :t AND status = 'in_progress' AND custom_id_hash_map ? :finding_id` (JSONB containment) — no live re-run of the D-01 top-N query needed. This deliberately does NOT also try to answer "will this finding be in TONIGHT's not-yet-submitted batch" (the UI-SPEC's "or upcoming" phrasing) — recommended as out of scope for this signal (see Assumption A4): a finding that hasn't been submitted yet shows the ordinary "Explain the priority" trigger, which is arguably the better analyst experience anyway (an immediate option, not a passive wait for something that hasn't started).

---

### Pattern 5: Shared-cache write from a scheduler context — `cache.py`/`budget.py` already take `tenant_id` explicitly, zero changes needed

**What:** Confirming the interactive-path cache/budget modules are reusable from a non-request context.

**Evidence [VERIFIED: direct read, `backend/app/ai/cache.py` + `budget.py`]:** `build_cache_key(tenant_id, resource_type, resource_id, record_hash_value, model, prompt_version)`, `record_hash(allowlisted_fields)`, `set_cached(redis_client, key, payload)`, and `check_tenant_budget(db, tenant_id, monthly_cap_usd)` are all **pure functions parameterized by an explicit `tenant_id`/`db`/`redis_client`** — none of them read from a FastAPI request, a dependency-injected `CurrentUser`, or any other request-scoped object. `audit_log_ai_call()`'s own docstring already anticipates this exact use case: *"`user_email` is either the analyst's email (interactive call) or the literal string `"system:scheduler"` (scheduler-originated call) — symmetric, no nil-tenant branch for either path."* This is not a hypothetical precedent — `backend/tests/test_ai_audit.py::test_scheduler_audit` (already passing today) asserts exactly `user_email == "system:scheduler"` and `tenant_id == tenant_a.id` (never the nil-tenant `uuid.UUID(int=0)` fallback `app.audit.audit()`'s generic helper would use). Phase 26's batch code should call `audit_log_ai_call()` directly with `user_email="system:scheduler"` — the identical string the test already locks in — for every batch-item outcome.

`_run_single_sync()`'s own pattern (open a fresh `async with async_session_factory() as db:` per background task, never reuse a request's session) is the correct template for `run_batch_prewarm()`/`poll_pending_batches()` to open their own DB sessions, needed anyway once the scheduler loop's calls are wrapped in `asyncio.create_task` and detached from the loop's own `db` variable.

**The one thing that IS new:** a Redis client. `scheduler.py` currently has no Redis dependency at all (it uses `get_redis(request)`'s FastAPI dependency only inside route handlers). Batch code needs to construct/obtain a Redis client outside a request context — recommend importing whatever the app's Redis client factory is at module scope (mirroring how `async_session_factory()` is a plain importable callable, not a FastAPI dependency) — confirm the exact factory function in `app/redis_client.py` at plan time (this file was not read this session; flagged as a plan-time verification item, not a blocker).

---

### Pattern 6: Budget pre-estimate for a batch — extract a reusable spend-sum helper, apply the batch discount

**What:** How to pre-estimate a batch's cost and reuse `check_tenant_budget()`'s fail-closed contract.

**Evidence [VERIFIED: direct read, `backend/app/ai/budget.py` + `explain.py`]:** `check_tenant_budget()` today only answers "is month-to-date spend already ≥ cap?" — a binary gate checked BEFORE a single interactive call (which is bounded by `MAX_TOKENS=1024` regardless of answer). It has no notion of "would adding X more dollars breach the cap?" Its SUM query (`AuditLog.details["cost_estimate_usd"].as_float()` where `action.like("ai.%")` and `created_at >= month_start`) is exactly the number a batch pre-check needs to add its own estimate to.

**Recommendation:**

```python
# backend/app/ai/budget.py -- extract the existing SUM query, add one new function
async def get_month_to_date_spend(db: AsyncSession, tenant_id: uuid.UUID) -> float:
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = (await db.execute(
        select(func.sum(AuditLog.details["cost_estimate_usd"].as_float())).where(
            AuditLog.tenant_id == tenant_id, AuditLog.action.like("ai.%"), AuditLog.created_at >= month_start,
        )
    )).scalar_one_or_none() or 0.0
    return spent

async def check_tenant_budget(db, tenant_id, monthly_cap_usd) -> bool:
    if monthly_cap_usd is None:
        return True
    return await get_month_to_date_spend(db, tenant_id) < monthly_cap_usd

async def would_exceed_budget_for_batch(
    db: AsyncSession, tenant_id: uuid.UUID, monthly_cap_usd: float | None, estimated_batch_cost_usd: float,
) -> bool:
    """D-07: fail-closed BEFORE submission. True means SKIP the batch."""
    if monthly_cap_usd is None:
        return False
    spent = await get_month_to_date_spend(db, tenant_id)
    return (spent + estimated_batch_cost_usd) >= monthly_cap_usd
```

```python
# backend/app/ai/batch.py -- the pre-estimate itself
async def estimate_batch_cost_usd(client: AsyncAnthropic, model: str, requests: list[dict]) -> float:
    input_rate, output_rate = _PRICING_PER_MTOK_USD.get(model, _DEFAULT_PRICING_PER_MTOK_USD)  # reuse explain.py's table
    total_input_tokens = 0
    for req in requests:
        counted = await client.messages.count_tokens(
            model=model, system=req["params"]["system"], messages=req["params"]["messages"],
        )
        total_input_tokens += counted.input_tokens
    worst_case_output_tokens = len(requests) * MAX_TOKENS  # reuse explain.py's constant
    input_cost = (total_input_tokens / 1_000_000) * input_rate
    output_cost = (worst_case_output_tokens / 1_000_000) * output_rate
    return round((input_cost + output_cost) * 0.5, 6)   # <-- the 50% BATCH discount, must not be forgotten
```

**The same 0.5 discount must be applied again when recording ACTUAL cost after a batch result comes back** — `_estimate_cost_usd(model, usage)` in `explain.py` computes the *interactive* (non-discounted) rate; a batch-result validator must call it and then halve the result (or a new `_estimate_batch_cost_usd()` twin) before writing `cost_estimate_usd` into the audit row. See Pitfall 4 — this is easy to get wrong silently, and the direction of the bug (over-counting, not under-counting) means it fails safe but still corrupts every cost figure a tenant admin would eventually see in Phase 28's dashboard.

On a skip: `notify_admins_budget_exceeded(db, tenant_id)` (reused verbatim, zero changes — it's already parameterized by `tenant_id` alone) + one `audit_log_ai_call(..., resource_type="prioritization", resource_id="batch", status="batch_skipped_budget_exceeded", cost_estimate_usd=0.0)` — never a partial submission (D-07's explicit "never a silent partial").

---

### Pattern 7: On-demand fallback + quadruplet reuse — the exact new symbols, mirroring Phase 25's `remediation-guidance` addition almost verbatim

**What:** The precise new grounding/schema/prompt-builder/route symbols, confirmed against the LIVE (already-shipped) Phase 25 code, not just its own research doc.

**Evidence [VERIFIED: direct read, `backend/app/ai/{grounding,schemas,prompt_builder}.py` + `backend/app/api/v1/ai/explain_remediation_guidance.py`, the actual committed files]:** Phase 25's quadruplet is real, shipped code today — `REMEDIATION_GUIDANCE_ALLOWLIST` (12 fields), `AllowlistedRemediationGuidance` (`model_config = {"extra": "forbid"}`, every field `| None = None`), `_to_allowlisted_remediation_guidance()` (field-by-field via the shared `_get_field()` helper, never a dict-spread passthrough), `SYSTEM_PROMPT_REMEDIATION_GUIDANCE` + `FEW_SHOT_REMEDIATION_GUIDANCE` (two exemplars, second demonstrates `grounded: false`), `build_explain_remediation_guidance_prompt()`, `remediation_guidance_prompt_version()` (calls the SAME generalized `prompt_version(system_prompt, few_shot, response_model)` every view already shares). The route file (`explain_remediation_guidance.py`, 184 lines, read in full this session) is a template: resolve grounding record (404 if `None`) → `StreamingResponse(_run_explain_stream(..., resource_type=..., build_prompt=..., response_model=..., allowed_source_fields=..., get_prompt_version=...))` for POST, and a matching GET that recomputes the same cache key via `_allowlisted_hash_fields()` (re-reading the prompt's own `<scanner_data>` block, never a second allowlist).

**Recommendation — the 5th quadruplet member, `prioritization`:**

| Seam | New symbol | Field set |
|------|-----------|-----------|
| Grounding (`grounding.py`) | `get_prioritization_context(db, tenant_id, finding_id) -> dict \| None` | `Vulnerability.{cve_id, cvss_v3_score, epss_score, exploit_available, cisa_kev, exploit_status_name, severity, sla_due_at, sla_breached}` + `Asset.department` (outer-joined) — exactly D-04's factor list plus `cve_id` (precedented in every other finding-level allowlist, needed so the narrative can name which CVE it's discussing) |
| Allowlist + prompt builder (`prompt_builder.py`) | `PRIORITIZATION_ALLOWLIST`, `AllowlistedPrioritization`, `_to_allowlisted_prioritization()`, `SYSTEM_PROMPT_PRIORITIZATION`, `FEW_SHOT_PRIORITIZATION`, `build_explain_prioritization_prompt()`, `prioritization_prompt_version()` | 10 fields (9 from D-04 + `cve_id`) — flat, scalar, no nested list (matches `AllowlistedHostPosture`'s shape, not `AllowlistedRemediationGroup`'s) |
| Schema (`schemas.py`) | `class ExplainPrioritizationResponse(ExplainResponseBase): pass` | **Zero new fields — this IS the D-03 "no rank field" enforcement.** `ExplainResponseBase` has no numeric field of any kind (`summary`/`business_risk`/`citations`/`grounded` only); there is structurally nowhere for a rank/priority number to live even if a future edit tried to add one without touching this base class. |
| Route (`api/v1/ai/`) | `explain_prioritization.py`, `POST/GET /explain-prioritization/{finding_id}` | UUID-keyed, mirrors `explain_host.py`/`explain_remediation_guidance.py`'s single-record 404 shape |
| Frontend resourceType | `'prioritization'` | Reuses `AiExplanationSection` unchanged except one new `isPrioritization` discriminator branch (mirrors `isRemediationGuidance` exactly, `ai-explanation-section.tsx` lines 164-184) |

**Owner-PII exclusion (D-04/D-15) [VERIFIED: `backend/app/assets/models.py`]:** `Asset.department: Mapped[str | None] = mapped_column(String(200))` exists and is safe (a business-unit label, not personal data). `Asset.assigned_user`, `directory_user`, `managed_by`, `building`, `serial_number` all exist on the SAME model and must never be selected by `get_prioritization_context()`'s query at all — mirroring every prior grounding function's "never even fetched" discipline (not just a prompt-layer filter). No new PII-risk surface exists here beyond what Phase 24/25 already vetted.

**Share one prompt/schema between batch and on-demand (CONTEXT's default, confirmed viable):** the batch submission code calls the exact SAME `build_explain_prioritization_prompt(record)` the interactive route calls — the only difference is where the result goes (`client.messages.batches.create(requests=[{"custom_id": ..., "params": {...}}])` vs. `client.messages.stream(...)`). No variant is needed.

**Why the on-demand fallback does NOT need a `dangerous_pattern_check`:** Phase 25's D-04 denylist gate exists because remediation guidance can contain actionable commands. A prioritization narrative is pure explanatory prose about WHY a score is what it is (D-08: "explain the score's drivers, not invent a competing verdict") — there is no destructive-command risk class here (the UI-SPEC's own Color table confirms: `--color-danger` has zero reserved usage in this phase). The on-demand route should call `_run_explain_stream()` exactly as `explain_vuln.py`/`explain_host.py` do today (no `dangerous_pattern_check` kwarg — `None` default, a no-op), not as `explain_remediation_guidance.py` does.

---

### Pattern 8: Batch result validation — a new single-pass validator, not `_run_explain_stream()`'s retry loop

**What:** Why the batch poller cannot literally call the interactive engine on each result.

**Evidence [VERIFIED: direct read, `backend/app/ai/explain.py`, whole function]:** `_run_explain_stream()`'s 2-attempt retry loop (D-26) exists because an interactive call is a live, synchronous conversation — on a validation failure or self-reported `grounded=false`, it appends a corrective turn and calls the model again, in the SAME request. A completed batch result is not a live conversation: there is no cheap way to "retry" one item without submitting an entirely new (paid) batch request, and D-02's own fallback design already covers the failure case for free — a batch item that comes back ungrounded/invalid simply never gets cached, so the next drill-panel open sees an ordinary cache miss and offers either "wait for tomorrow's batch" (if nothing changed) or the on-demand single-request fallback (which DOES get the full corrective-retry treatment via `_run_explain_stream()`).

**Recommendation — one new function, single pass, no retry:**

```python
# backend/app/ai/batch.py
async def validate_and_cache_batch_result(
    db: AsyncSession, redis_client: redis.Redis, *,
    tenant_id: uuid.UUID, finding_id: str, raw_text: str, model: str, usage: Any,
    cache_key: str,
) -> str:
    """Single-pass equivalent of _run_explain_stream()'s validation gate,
    minus the retry loop (no live conversation to retry within). Returns
    the audit status string written."""
    try:
        candidate = ExplainPrioritizationResponse.model_validate_json(raw_text)
        recheck_business_rules(candidate, allowed_source_fields=PRIORITIZATION_ALLOWLIST)
    except (ValidationError, BusinessRuleError):
        status = "validation_failed"
    else:
        if not candidate.grounded:
            status = "validation_failed"
        elif _contains_leak_marker(candidate, SYSTEM_PROMPT_PRIORITIZATION):  # reuse, cross-module import like Phase 25 does
            status = "injection_flagged"
        else:
            payload = candidate.model_dump(mode="json")
            await set_cached(redis_client, cache_key, payload)
            status = "ok"

    cost = _estimate_cost_usd(model, usage) * 0.5 if status == "ok" else 0.0  # the batch discount, Pattern 6
    await audit_log_ai_call(
        db, tenant_id=tenant_id, user_email="system:scheduler", model=model, usage=usage,
        resource_type="prioritization", resource_id=finding_id, status=status, cost_estimate_usd=cost,
    )
    return status
```

`errored`/`canceled`/`expired` results (per Pattern 1's four result types) never reach this function at all — the poller audits those directly with their own distinct status (`"batch_errored"`/`"batch_canceled"`/`"batch_expired"`) and `cost_estimate_usd=0.0` (per the official docs: none of these three are billed), never calling the model-response validator on a payload that doesn't exist.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Batch completion notification | A webhook receiver endpoint, or a message queue subscriber | Polling `retrieve()` on the scheduler's existing 60s tick | The Message Batches API has no webhook mechanism at all — confirmed absent from the official guide, whose own reference implementation is a polling loop. Building a receiver for a callback that will never arrive is pure waste. |
| Batch-completion progress tracking | A "N of M items done" progress indicator | A single on/off `processing_status` check | `request_counts` are provably all-zero-except-processing until the entire batch ends (SDK type docstrings + official guide agree) — there is no partial-progress signal to build a progress bar from. |
| Pre-submission cost estimation | A char-count/word-count token heuristic | `client.messages.count_tokens()` | Free, exact (per Anthropic's own tokenizer, not an approximation), and on a separate rate-limit bucket from the Messages API — there is no cost or contention reason to avoid it. |
| Batch-item retry-on-failure | Re-implementing `_run_explain_stream()`'s 2-attempt corrective-turn loop for batch results | Leave it uncached; let the next night's batch (if facts changed) or the analyst's on-demand fallback retry with the FULL interactive engine | A batch result is not a live conversation — there is no cheap corrective turn to append. D-02's fallback already exists specifically to cover this case. |
| Submitted-batch tracking | An in-memory dict (mirroring `_running_syncs`) | A new Postgres table (`AiBatchJob`) | Connector syncs finish within one process lifetime; a Message Batch can span a restart. This is the single highest-consequence "don't hand-roll" in this phase — an in-memory shortcut here silently orphans real spend. |
| A second, independent AI-priority number | Any schema field, UI badge, or sort control carrying a numeric verdict | `ExplainResponseBase`'s existing `summary`/`business_risk`/`citations`/`grounded` shape (zero new fields) | This is the literal Pitfall #7 mitigation — the schema structurally has nowhere to put a number, and the UI-SPEC's No-Rank Contract makes the same guarantee for every list/table surface. |

**Key insight:** every genuinely new piece of infrastructure this phase needs (a durable batch registry, a cost pre-estimate, a single-pass result validator) is a SMALL, additive extension of something Phase 24 already built (the audit table, the pricing table, the schema-validation gate) — the only wholly new external integration is the Batches API resource itself, and that resource's own documented contract (poll, atomic-per-batch results, `custom_id` matching) already tells you exactly what shape the surrounding code needs to take. There is very little room here for over-engineering a bespoke job-queue system GetVul does not otherwise have.

## Common Pitfalls

### Pitfall 1: Treating "ASSET-02 score" as if it were a per-finding column
**What goes wrong:** A plan/implementation assumes `Vulnerability.risk_score` exists, or silently substitutes `sort=triage`'s finding-level factors without realizing D-01 named a DIFFERENT (asset-level) number.
**Why it happens:** ASSET-02 is referenced constantly throughout `.planning/` as "the deterministic risk score" in prose that reads as if it's a single per-item number, and CONTEXT.md's own phrasing ("ranked by the existing deterministic ASSET-02 score") doesn't flag the asset/finding distinction.
**How to avoid:** Confirm at plan time which interpretation ships (Pattern 3's join-with-tiebreak recommendation, or a pure `sort=triage` finding-level reinterpretation) — this is Assumption A1, not a settled fact.
**Warning signs:** A migration or query that assumes `Vulnerability.risk_score` exists; a batch that returns 50 findings all belonging to one asset.

### Pitfall 2: Tracking a submitted batch only in memory
**What goes wrong:** A backend restart (deploy, crash, `docker compose restart`) mid-batch loses the `message_batch_id` forever — the batch keeps processing at Anthropic (already paid for), but GetVul has no record to poll or retrieve results from. The spend is real; the narrative is never written anywhere.
**Why it happens:** `scheduler.py`'s existing `_running_syncs: dict[str, asyncio.Task]` is the most visually similar in-repo precedent, and connector syncs genuinely don't need durability (they finish in seconds).
**How to avoid:** Persist every submitted batch to the new `AiBatchJob` Postgres row BEFORE returning from the submission function — the `INSERT` must happen synchronously as part of the same task that called `create()`, not queued for "later."
**Warning signs:** A code review that finds `anthropic_batch_id` only assigned to a local variable or a module-level dict, never `db.add()`'d.

### Pitfall 3: Forgetting BOTH scheduler blocks need `asyncio.create_task`, not just submission
**What goes wrong:** Someone correctly wraps the nightly submission in `create_task` (satisfying D-05's literal wording) but leaves the polling step as a direct `await` inside the loop (mirroring the file's OWN existing ticket-sync/snapshot-capture inline pattern) — reintroducing the exact tick-stall risk D-05 exists to prevent, just on the polling side instead of the submission side.
**Why it happens:** D-05's text explicitly says "dispatched... via `asyncio.create_task`" in the context of submission; polling isn't named, and the file's two existing "nightly" blocks are inline-awaited, making that feel like the house style.
**How to avoid:** Wrap BOTH new blocks in `asyncio.create_task` (Pattern 2) — extend the constraint's rationale (never stall the tick) to every new addition uniformly, not just the one sentence literally names.
**Warning signs:** `await poll_pending_batches(db)` (no `create_task`) inside `_scheduler_loop()`.

### Pitfall 4: Forgetting the batch 50% discount when recording cost
**What goes wrong:** `_estimate_cost_usd(model, usage)` (interactive-rate table) gets called directly on a batch result's `usage` and written into `cost_estimate_usd` without halving it — `check_tenant_budget()`'s month-to-date SUM now over-counts every batch-derived dollar by 2x, causing a tenant to trip their fail-closed cap roughly twice as early as their real Anthropic invoice would justify, and corrupting whatever cost figure Phase 28's eventual dashboard shows.
**Why it happens:** `_estimate_cost_usd()` is an existing, already-correct-for-interactive-calls function that's easy to reach for without re-reading its own pricing table's docstring (which says nothing about batch pricing, because Phase 24 never needed to know).
**How to avoid:** Apply `× 0.5` at every batch-result cost-recording call site (Pattern 6/8) — recommend a single, obviously-named helper (`_estimate_cost_usd(model, usage) * 0.5` inline, or a twin `_estimate_batch_cost_usd()`) rather than relying on every call site to remember the multiplier.
**Warning signs:** A tenant's audit-log cost total for a month with heavy batch usage looks exactly 2x what their actual Anthropic invoice shows.

### Pitfall 5: Re-submitting a finding whose narrative is already fresh
**What goes wrong:** Every night's batch includes ALL top-N findings unconditionally, re-paying for a narrative whose underlying facts (CVSS/EPSS/exploit/KEV/SLA/department) haven't changed since last night — directly contradicting D-01's "regenerates only when its exploit/KEV/owner/SLA facts change" freshness contract, and multiplying cost for no benefit (the cache would just be overwritten with an identical value).
**Why it happens:** It's the simplest version to build — "just batch the top N every night" — and the cache-skip step is an easy-to-omit optimization rather than a obviously-required correctness step.
**How to avoid:** Before building the batch's `requests` list, compute each candidate finding's `record_hash()` and do a cheap `get_cached()` lookup per finding; only include actual cache MISSES in the submitted batch (Pattern "System Architecture Diagram," step 5).
**Warning signs:** A tenant's batch size stays constant at exactly N every single night regardless of how many findings actually changed.

### Pitfall 6: Assuming `results()` can be called any time after `create()`
**What goes wrong:** Calling `client.messages.batches.results(batch_id)` before `processing_status == "ended"` — the SDK's own `results()` implementation calls `retrieve()` internally and raises `AnthropicError` if `results_url` is still `None`, so this fails loudly rather than silently, but only if the poller actually reaches that code path; a naive implementation might call `results()` unconditionally on every tick.
**How to avoid:** Always check `refreshed.processing_status == "ended"` before calling `results()` — never call it speculatively (Pattern 1's poll snippet already gates this correctly).
**Warning signs:** An `AnthropicError` exception in the scheduler's logs referencing "Has it finished processing?"

## Code Examples

See Patterns 1-8 above for fully-worked, ready-to-adapt code (batch submit/poll shape, the D-01 top-N query, the `AiBatchJob` model, the budget pre-estimate + discount math, the single-pass batch-result validator). All are original recommendations synthesized from the installed SDK's verified surface + the official docs' verified contract + direct reads of GetVul's own existing modules — tagged inline as `[VERIFIED: ...]` or `[CITED: ...]` per claim, per this document's provenance discipline.

### Frontend: the one new state branch (mirrors the Phase 25 `isRemediationGuidance` pattern exactly)

```typescript
// frontend/src/components/ai/ai-explanation-section.tsx
// (VERIFIED: current file, this session — the exact insertion points)
const isPrioritization = resourceType === 'prioritization';
// ...heading/triggerLabel/viewerEmptyText/insufficientEvidenceCopy each get
// a 3rd branch alongside the existing isRemediationGuidance ? ... : ... ternaries.

// DegradedCardProps needs one additive field so the SAME neutral/violet
// variant can render a Clock icon instead of Sparkles (UI-SPEC: same color
// family, deliberately not a new hue) -- e.g.:
type DegradedCardProps = {
  variant: 'neutral' | 'amber' | 'danger';
  icon?: 'sparkles' | 'clock';   // NEW, defaults to 'sparkles' (every existing call site unaffected)
  heading: string;
  body: string;
  action?: { label: string; onClick?: () => void; href?: string };
};

// New branch, inserted BEFORE the isAnalystOrAbove trigger-button branch --
// same placement discipline as Phase 25's groundable===false branch, so the
// "queued" card is structurally guaranteed rather than a copy choice:
} else if (cacheQuery.data?.cached === false && cacheQuery.data?.queued === true) {
  body = isAnalystOrAbove ? (
    <DegradedCard
      variant="neutral" icon="clock"
      heading="Prioritization narrative is being prepared"
      body="This finding is in the next scheduled batch — narratives typically land within 24h."
      action={{ label: 'Generate it now', onClick: () => void start() }}
    />
  ) : (
    <DegradedCard variant="neutral" icon="clock" heading="Prioritization narrative is being prepared"
      body="This finding is in the next scheduled batch — narratives typically land within 24h." />
    // Viewer: identical card, no action (D-17)
  );
}
```

## State of the Art

| Old Approach (Phase 24/25) | New Approach (Phase 26) | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Interactive SSE streaming, one finding per request, buffer-then-validate-then-replay | Bulk async submission, N findings per single API call, poll-then-validate-then-cache (no streaming, no replay) | This phase | First genuinely async, multi-request AI dispatch path in GetVul; the interactive engine (`_run_explain_stream()`) is reused ONLY for the cache-miss fallback, never for the primary bulk path |
| `_running_syncs` in-memory task tracking (sufficient for seconds-to-minutes connector syncs) | A durable Postgres registry (`AiBatchJob`) for a job that can span up to 24h and a process restart | This phase | First AI-domain job that outlives a single process lifetime |
| Cost recorded at the standard per-token rate | Cost recorded at the standard rate × 0.5 for anything batch-derived | This phase | A new, easy-to-miss arithmetic step every batch-result-writing call site must apply |

**Deprecated/outdated:** Nothing from Phase 24/25 is deprecated — every module Phase 26 touches (`cache.py`, `budget.py`, `audit.py`, `explain.py`'s `_run_explain_stream()`, the whole prompt-builder quadruplet pattern) is reused unchanged or extended additively, per D-09.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | D-01's "top-N findings ranked by the ASSET-02 score" should be implemented as `Asset.risk_score DESC` (primary) with a per-finding KEV/CVSS/SLA tiebreak (Pattern 3) — rather than a pure per-finding reinterpretation using the existing `sort=triage` factors alone, with no reference to `Asset.risk_score` at all | Pattern 3 | If the intended meaning was actually "the same ordering `sort=triage` already gives analysts" (ignoring `Asset.risk_score` entirely), the recommended query would still be defensible but not identical — and the recommended query's real risk (many findings from one asset crowding the batch) would need an explicit per-asset cap the alternative interpretation wouldn't need. Low implementation cost to switch either way if flagged before coding; CONTEXT.md explicitly defers exact mechanics as a researcher/planner decision, but the underlying ASSET-02-is-per-asset FACT itself is not in question — only which query best honors the intent. |
| A2 | `department` (bare column name) is the right allowlist field name for the owner factor, mirroring `os_name`/`os_version`'s bare-column convention in `REMEDIATION_GUIDANCE_ALLOWLIST` rather than the `asset_hostname`-style prefixed convention also present in that same allowlist | Pattern 7 | Purely cosmetic if wrong — a naming-convention nit with zero behavioral impact, easy to rename before merge. |
| A3 | The GET route's `queued` signal should answer ONLY "is this finding part of a currently-in-flight (already-submitted) batch," and deliberately should NOT also attempt to answer "will this finding be included in tonight's not-yet-submitted batch" (Pattern 4) | Pattern 4 / UI-SPEC's "currently-in-flight or upcoming" phrasing | If the UI-SPEC's "or upcoming" clause was meant literally, a not-yet-submitted-but-will-be-tonight finding would show the ordinary "Explain the priority" button instead of the "being prepared" card — arguably a BETTER analyst experience (an immediate option vs. a passive wait), but a literal reading of the UI-SPEC text would disagree. Low-cost to add a live top-N re-check later if the planner wants the stricter reading. |
| A4 | `cve_id` should be added to `PRIORITIZATION_ALLOWLIST` even though it is not literally in D-04's 8-field factor list, mirroring the precedent that every other finding-level allowlist (`VULN_ALLOWLIST`, `REMEDIATION_GUIDANCE_ALLOWLIST`) includes it so citations can name which CVE is being discussed | Pattern 7 | If D-04's factor list is meant to be exhaustive and closed, this is a one-field scope creep beyond the locked grounding contract (D-04 is explicitly flagged "costly to reverse" in CONTEXT.md). Trivial to remove at plan/review time if the planner wants D-04 read as a hard, closed set. |
| A5 | A default N (e.g. 50) per tenant per night is a reasonable starting point (well under every API size/count limit, large enough to cover a typical tenant's active triage queue) — CONTEXT.md explicitly leaves the exact value to plan time | Pattern 3 / Standard Stack | No correctness risk — purely a cost/coverage tuning knob the planner or a config value can adjust freely; flagged only so the plan doesn't need to re-derive "is 50 sane" from scratch. |

## Open Questions (RESOLVED)

1. **Exact Redis client access pattern from a non-request scheduler context**
   - **RESOLVED:** Closed by Plan 07's `get_redis_client()` factory (`backend/app/redis_client.py`) — a plain, non-request `redis.Redis` builder that both `main.py`'s lifespan and `batch.py` call (single construction site); `batch.py`'s `run_batch_prewarm()`/`poll_pending_batches()` obtain their Redis client from it.
   - What we know: `cache.py`'s functions all take an already-built `redis.Redis` client as a plain parameter (never construct their own) — this is Pattern 5's confirmed reusability. `scheduler.py` currently has zero Redis usage anywhere in the file.
   - What's unclear: the exact importable factory function/module (`app/redis_client.py` was not read this session) that constructs a `redis.Redis` instance outside of FastAPI's `get_redis(request)` dependency-injection path.
   - Recommendation: read `app/redis_client.py` at plan time (one file, low risk) to confirm whether a plain `get_redis_client()`-style callable already exists (mirroring `async_session_factory()`'s pattern) or needs a two-line addition.

2. **Whether a per-asset cap (e.g. "at most K findings from any single asset") is needed inside the D-01 top-N query**
   - **RESOLVED:** Plan 07 ships without a per-asset cap, per this section's recommendation — `get_top_findings_for_ai_batch()` has no cap in the first cut; revisit as a fast follow-up only if Phase 28 observability shows crowding materializes.
   - What we know: Pattern 3's recommended query has no such cap; Pattern 1 (Pitfall) flags the crowding risk explicitly.
   - What's unclear: whether N (Assumption A5, likely ~50) is small enough in practice that this risk rarely materializes, or whether a real GetVul tenant's data would trigger it regularly.
   - Recommendation: ship without a cap for the tracer/first plan (simpler, and Phase 28's eventual observability work would surface the problem empirically if it's real); treat as a fast, cheap follow-up if evidence shows it matters.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `anthropic` Python SDK (Batches resource + `count_tokens`) | Batch submit/poll/retrieve, budget pre-estimate | ✓ [VERIFIED, this session] | `0.120.2`, both resources confirmed present via introspection | — |
| Postgres (`getvul-postgres-1`) | New `AiBatchJob` table, all audit/budget queries | ✓ [VERIFIED, this session — `docker ps`] | healthy, up 28h | — |
| Redis (`getvul-redis-1`) | Shared tenant cache the batch poller writes into | ✓ [VERIFIED, this session] | healthy, up 28h | — |
| Backend/Frontend containers | Local dev loop | ✓ [VERIFIED, this session] | both healthy/up | — |
| Live Anthropic API key (`GETVUL_DEV_ANTHROPIC_KEY` or similar) | End-to-end live smoke test of a real batch submit/poll/retrieve cycle | ✗ [VERIFIED, this session — no `ANTHROPIC*` env var set] | — | Same accepted gap Phase 24/25 already carry: unit/integration tests inject a fake Anthropic client via the existing `anthropic_client_factory`-style test seam; a real end-to-end batch (which additionally requires waiting for actual async processing, not just mocking a synchronous response) remains a tracked, accepted gap, not a plan blocker. |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** Live Anthropic key — mitigated by dependency-injecting a fake `AsyncAnthropic`-shaped client into the batch submission/poll functions (mirroring `_run_explain_stream()`'s existing `anthropic_client_factory` test seam) — this is inherited risk, not new.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3 + pytest-asyncio (`asyncio_mode = "auto"`, session-scoped event loop, `backend/pyproject.toml`) for backend; Vitest for frontend (`frontend/package.json`'s `"test": "vitest"`) |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` (unchanged); frontend Vitest config (unchanged) |
| Quick run command | `pytest backend/tests/test_ai_batch.py -q` (per-file; project memory: set `ENCRYPTION_KEY`/`JWT_SECRET_KEY` env vars, never run the whole `tests/` dir for a quick loop) |
| Full suite command | `pytest backend/tests/ -q` + `npm run test` (from `frontend/`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AIP-02 | `get_top_findings_for_ai_batch()` orders by `Asset.risk_score` then KEV/CVSS/SLA tiebreak, respects `limit`, excludes REMEDIATED/SUPPRESSED/FALSE_POSITIVE | unit | `pytest backend/tests/test_vulnerabilities_service.py -k top_findings_for_ai_batch -x` | ❌ Wave 0 (extends existing file — verify exact filename at plan time; no `test_vulnerabilities_service.py` was confirmed to exist this session) |
| AIP-01 | `PRIORITIZATION_ALLOWLIST` excludes `assigned_user`/`directory_user`/`managed_by`/`building`/`serial_number` (dict + attribute-object input) | unit | `pytest backend/tests/test_ai_prompt_builder_prioritization.py -k pii -x` | ❌ Wave 0 (new file, mirrors `test_ai_prompt_builder_remediation_guidance.py`) |
| AIP-01 | `ExplainPrioritizationResponse` has exactly the 4 base fields, zero rank/priority field (schema-level No-Rank enforcement) | unit | `pytest backend/tests/test_ai_schemas.py -k prioritization_no_rank_field -x` | ❌ Wave 0 (extends existing file) |
| AIP-02 | Batch submission skips a finding whose cache entry is already fresh (Pitfall 5's freshness check) | unit | `pytest backend/tests/test_ai_batch.py -k skips_cached -x` | ❌ Wave 0 (new file) |
| AIP-02 | Budget pre-estimate refuses submission when projected cost would breach the cap; writes `batch_skipped_budget_exceeded` audit + admin notification, never partial | integration | `pytest backend/tests/test_ai_batch.py -k budget_skip -x` | ❌ Wave 0 (new file) |
| AIP-02 | Batch cost recorded at half the standard rate (Pitfall 4's discount check) | unit | `pytest backend/tests/test_ai_batch.py -k discount -x` | ❌ Wave 0 (new file) |
| AIP-02 | Submitted batch persists to `AiBatchJob` (Postgres), survives being re-queried in a fresh DB session (Pitfall 2's durability check) | integration | `pytest backend/tests/test_ai_batch.py -k durable_registry -x` | ❌ Wave 0 (new file) |
| AIP-02 | Poller: `succeeded` results get cached + audited `"ok"`; `errored`/`canceled`/`expired` never reach the cache, get their own distinct audit status | integration | `pytest backend/tests/test_ai_batch.py -k poll_result_types -x` | ❌ Wave 0 (new file) |
| AIP-02 | Scheduler submission AND polling are both dispatched via `asyncio.create_task` (Pitfall 3's regression guard — assert the loop's own tick returns before the task completes) | integration | `pytest backend/tests/test_scheduler_ai_batch.py -k non_blocking -x` | ❌ Wave 0 (new file — first-ever direct test of `scheduler.py`; mirrors `test_connector_health.py`'s `from app.connectors import scheduler as scheduler_module; await scheduler_module.<fn>(...)` direct-await pattern) |
| AIP-01 | No-rank UI contract: repo-wide grep for `priority`/`rank`/`ai_score` touching any table/sort/column definition returns zero NEW matches | static/CI | `grep -rn "priority\|rank\|ai_score" frontend/src/components/**/*.tsx frontend/src/lib/queries/**/*.ts` (baseline confirmed clean this session — zero matches outside the unrelated `watcher-stack.tsx` role-priority comment) | ❌ Wave 0 (recommend wiring as a small Vitest test using Node's `fs`, or a documented manual pre-merge check — CONTEXT/UI-SPEC don't mandate the mechanism) |
| AIP-01 | On-demand fallback (`_run_explain_stream(resource_type="prioritization")`) round-trips through the shared engine unchanged (RBAC, cache, budget, audit) | integration | `pytest backend/tests/test_ai_explain_prioritization.py -x` | ❌ Wave 0 (new file, mirrors `test_ai_explain_remediation_guidance.py`'s RBAC-matrix/cache-check/cross-tenant-404 structure) |

### Sampling Rate
- **Per task commit:** the new file's own quick-run command (per-file, per project memory's env-var gotcha).
- **Per wave merge:** `pytest backend/tests/test_ai_*.py backend/tests/test_scheduler_ai_batch.py -q` + `npm run test` for touched frontend files.
- **Phase gate:** Full backend + frontend suite green before `/gsd-verify-work 26`.

### Wave 0 Gaps
- [ ] `backend/tests/test_ai_batch.py` — covers batch cost estimate/discount, cache-skip-if-fresh, budget pre-check + skip, durable registry write, poll result-type branching (Patterns 4/6/8, Pitfalls 4/5)
- [ ] `backend/tests/test_scheduler_ai_batch.py` — first-ever direct scheduler test; covers the 24h submission gate + non-blocking `asyncio.create_task` dispatch for BOTH new blocks (Pattern 2, Pitfall 3)
- [ ] `backend/tests/test_ai_prompt_builder_prioritization.py` — the 5th quadruplet's allowlist/PII exclusion (mirrors `test_ai_prompt_builder_remediation_guidance.py`)
- [ ] `backend/tests/test_ai_explain_prioritization.py` — the on-demand route's RBAC/cache/cross-tenant-404 matrix (mirrors `test_ai_explain_remediation_guidance.py`)
- [ ] `backend/alembic/versions/033_add_ai_batch_job.py` — migration for the new table (mirrors `032_add_ai_feedback.py`)
- [ ] Confirm at plan time: does `test_vulnerabilities_service.py` already exist for `get_top_findings_for_ai_batch()`'s home test file, or does the closest existing test file for `vulnerabilities/service.py` have a different name? (not confirmed this session — flagged, not asserted)
- [ ] No new fixtures/conftest needed for the AI side — `tenant_a`/`tenant_b`/`db_session` fixtures already exist and are reused verbatim across every `test_ai_*.py` file.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Unchanged — reuses existing JWT/session auth |
| V3 Session Management | No | Unchanged |
| V4 Access Control | Yes | `require_analyst`/`require_viewer` reused verbatim on the new route (D-17); the scheduler's batch submission/poll paths run with NO user context at all (system-originated, `user_email="system:scheduler"`), so there is no analyst-facing authorization surface to get wrong there — only tenant-scoping (below) |
| V5 Input Validation | Yes | The same Pydantic schema-validation + `recheck_business_rules()` gate every existing view uses; the new `AiBatchJob.custom_id_hash_map` JSONB column needs no additional validation (values are internally-generated hashes, never user input) |
| V6 Cryptography | No | No new cryptographic material; BYOK key resolution is 100% reused (`get_tenant_anthropic_key()`), unchanged |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant batch/cache leak (a batch item's result written under the wrong tenant's cache key) | Information Disclosure | `AiBatchJob.tenant_id` is set once at submission and never re-derived from the result payload itself; the poller looks up `custom_id_hash_map` and `tenant_id` from the SAME `AiBatchJob` row, so a result can never be attributed to a different tenant than the one whose batch it came from (one batch = one tenant, per D-05) |
| Budget-guard bypass via cost under-counting (Pitfall 4, inverted) | Tampering (of the tenant's own accounted spend, not an attacker) | Applying the batch discount CONSISTENTLY (not just "sometimes") keeps `check_tenant_budget()`'s SUM accurate in both directions — this phase's own Pitfall 4 is about over-counting (fails safe), but an under-counted figure would fail UNSAFE (a tenant spends more than their cap without the guard noticing) — either direction is worth a direct unit test, not just the over-counting case |
| Owner-PII leakage into the prioritization prompt | Information Disclosure | `get_prioritization_context()`'s SELECT structurally excludes `assigned_user`/`directory_user`/`managed_by`/`building`/`serial_number` — never even fetched, mirroring every prior grounding function's defense-in-depth discipline |
| A second, independently-sortable AI rank re-introducing Pitfall #7 | (Product-integrity, not a STRIDE category — the milestone's own named anti-feature) | Schema has zero numeric fields (structural impossibility); UI-SPEC's No-Rank Contract + the repo-wide grep check (Validation Architecture) are the checkable enforcement mechanisms |

## Sources

### Primary (HIGH confidence)
- `backend/.venv/lib/python3.12/site-packages/anthropic/` — direct introspection + source read of `resources/messages/batches.py`, `types/messages/{message_batch,message_batch_request_counts,message_batch_individual_response,message_batch_result,message_batch_succeeded_result,message_batch_errored_result,message_batch_canceled_result,message_batch_expired_result,batch_create_params}.py`, `types/message_create_params.py` — the entire Batches API call-shape analysis (Pattern 1), verified against the EXACT installed version (`0.120.2`), not training data
- [Batch processing — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing) — fetched in full this session; limits, pricing, lifecycle, `custom_id` regex, result types, cancellation, no-webhook confirmation (Pattern 1)
- [Rate limits — Claude Platform Docs](https://platform.claude.com/docs/en/api/rate-limits) — fetched in full this session; Message Batches API's own separate rate-limit bucket (Standard Stack, Pattern 1)
- [Token counting — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/token-counting) — fetched in full this session; free-to-use confirmation, separate rate-limit bucket, exact Python SDK signature (Pattern 6)
- `backend/app/ai/{explain,grounding,cache,budget,audit,schemas,prompt_builder,models}.py`, `backend/app/api/v1/ai/{explain_vuln,explain_remediation_guidance,__init__,status}.py` — direct reads, every reuse-mechanics/extension-point claim (Patterns 2, 5, 6, 7, 8)
- `backend/app/connectors/scheduler.py` — direct read, whole file, the non-blocking-vs-inline idiom distinction (Pattern 2, Pitfall 3)
- `backend/app/vulnerabilities/{models,service}.py`, `backend/app/assets/{models,risk_score}.py` — direct reads, the ASSET-02-is-per-asset finding (Pattern 3, Assumption A1)
- `backend/tests/test_ai_audit.py::test_scheduler_audit`, `backend/tests/test_connector_health.py` — direct reads, the already-passing `"system:scheduler"` precedent and the scheduler-test-writing pattern (Pattern 5, Validation Architecture)
- `backend/alembic/versions/032_add_ai_feedback.py` — direct read, the migration-authoring convention for a new AI-domain table (Pattern 4)
- `frontend/src/components/ai/ai-explanation-section.tsx`, `frontend/src/lib/{ai/use-explain-stream,queries/use-explain-cache}.ts`, `frontend/src/components/vulnerabilities/drill-content.tsx` — direct reads, the exact frontend insertion points (Code Examples, Recommended Project Structure)
- `.planning/phases/26-prioritization-narrative/{26-CONTEXT.md, 26-UI-SPEC.md}` — the locked decisions and approved UI contract this research is scoped against
- `docker ps`, `env` (this session) — Environment Availability verification

### Secondary (MEDIUM confidence)
- None — every claim in this document is either a direct SDK/codebase read, a directly-fetched official doc, or clearly flagged as an Assumption pending plan-time confirmation.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Message Batches API mechanics: HIGH — verified against the exact installed SDK version via introspection AND the current official guide/rate-limits/token-counting docs, fetched live this session
- Scheduler integration seam: HIGH — every claim (idiom distinction, durability requirement, non-blocking requirement) derived from a direct read of the entire `scheduler.py` file plus the already-shipped `_running_syncs`/`trigger_background_sync` precedent
- ASSET-02 per-asset finding: HIGH as a codebase FACT (confirmed by direct model/service reads); MEDIUM on which query is the "right" interpretation of D-01's intent (flagged as Assumption A1, explicitly deferred by CONTEXT.md to plan time)
- Quadruplet reuse pattern: HIGH — verified against the LIVE, already-shipped Phase 25 files, not just that phase's own research/planning docs
- Pitfalls: HIGH — six concrete, codebase-and-API-specific pitfalls, each with a verifiable warning sign

**Research date:** 2026-07-30
**Valid until:** ~30 days for the codebase-integration findings (stable domain, no fast-moving dependency); the Anthropic API-shape findings should be re-verified if Phase 26 execution is delayed more than ~60 days, since Anthropic's own docs show active model-lineup and pricing changes on a similar cadence (e.g., the Sonnet 5 introductory-pricing cutover on 2026-08-31 is already inside this phase's likely execution window and affects `_PRICING_PER_MTOK_USD`'s existing values, not just anything new this phase adds).
