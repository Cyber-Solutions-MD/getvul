# Phase 26: Prioritization Narrative - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

An analyst sees a **"what to fix first and why" narrative** for a finding — built from **exploit / KEV / owner / SLA factors fed to the model as structured facts** (never raw free reasoning) — that **explains and augments, but never replaces or out-ranks**, the deterministic risk score (ASSET-02). Narratives are **pre-generated in bulk on a schedule via the Anthropic Message Batches API**, dispatched from the connector scheduler via `asyncio.create_task` (never inline, never stalling a sync tick), using only each tenant's own configured key.

Requirements: **AIP-01** (augment-never-replace narrative from exploit/KEV/owner/SLA factors), **AIP-02** (bulk generation via the scheduler + Message Batches API, tenant's key). Both fixed by ROADMAP.md.

This is the **first batch/scheduler AI path** — a genuine departure from Phases 24/25's request-path SSE. It reuses Phase 24's scaffold (BYOK key, tenant cache, fail-closed budget, audit, RBAC, schema-validation + prompt-injection-as-data contract, grounding allowlist discipline) and Phase 25's grounding-record + schema-variant + prompt-builder pattern; it ADDS a batch submission/retrieval flow and a scheduled pre-warm job. Pitfall #7 (over-trusting AI over the deterministic score) is owned here and enforced as an output-schema + UI constraint, not just intent.
</domain>

<decisions>
## Implementation Decisions

### Batch generation strategy (AIP-02)
- **D-01:** Batch scope = each tenant's **top-N OPEN findings ranked by the existing deterministic ASSET-02 score** (the findings an analyst actually triages first), regenerated **nightly**. Freshness via a **factor-hash** cache-key component: a narrative regenerates only when its exploit/KEV/owner/SLA facts change (mirrors Phase 24 D-18's hash-scoped invalidation). Bounds cost + keeps the highest-value findings fresh; N and exact schedule time are plan-time details. — **Reversibility:** costly — the batch scope + schedule contract is a scheduled path Phase 28's cost/observability gate builds on.
- **D-05:** The nightly batch is dispatched from the connector scheduler (`backend/app/connectors/scheduler.py`) via `asyncio.create_task`, **never inline in a sync tick** (AIP-02 hard constraint — must not stall a connector-sync). It submits ONE Message Batches request per tenant covering the top-N set. Retrieval of async batch results (poll vs webhook, back-off, partial-result handling) is a researcher/planner decision. — **Reversibility:** costly — first use of the scheduler's batch pre-warm path.
- **D-06:** The batch result writes each narrative into the **SAME tenant cache the drill panel reads** (keyed `(finding, factor-hash, model, prompt-version)`), so a batch-warmed narrative is a plain cache hit for the analyst. Each batch item is audited (Phase 24 D-27 / AI-06 audit shape) with distinct status.
- **D-07:** **Fail-closed budget applies to the batch.** Pre-estimate the batch's token cost and refuse submission if it would breach the tenant's monthly cap (reuse Phase 24 D-06's guard); a skipped batch is logged + admin-alerted (D-08 lineage), never a silent partial. — **Reversibility:** reversible.

### Async-batch cache-miss UX (AIP-01/AIP-02 seam)
- **D-02:** **Cache hit → show it. Miss → on-demand single-request fallback.** An Analyst+ can trigger an **on-demand single-request generation** for an ungenerated finding, reusing Phase 24's request-path `_run_explain_stream()` engine with a new `resourceType` (instant, spends a little). A finding queued for the next batch but not yet ready shows a neutral **"Prioritization narrative is being prepared"** state. Viewers stay cached-only (D-17). Best analyst experience without waiting up to 24h. — **Reversibility:** reversible.

### Augment-never-replace surface + enforcement (Pitfall #7 / SC2)
- **D-03:** The narrative surfaces in a **new dedicated "Prioritization" drill-panel section** (like the Phase 25 remediation-guidance section), **explanatory prose only**, reusing Phase 24's AI section chrome + citation component. The response **schema carries NO numeric rank/priority field**, and **NO list column or sort control is added** — the deterministic ASSET-02 score stays the ONE sortable/authoritative number in every list and view. Enforced in the output schema AND the UI, not just design intent. — **Reversibility:** costly — the "no AI rank" schema/UI contract is the literal Pitfall-#7 mitigation Phase 28 audits.

### Grounding factors + owner-PII (AIP-01 / SC1)
- **D-04:** The narrative is grounded in these **structured facts** (fed as data, never free reasoning), all already on the models: `cvss_v3_score`, `epss_score`, `exploit_available`, `cisa_kev`, `exploit_status_name`, `severity`, `sla_due_at`, `sla_breached`. **Owner is expressed as the non-PII `Asset.department`** (e.g. "owned by Finance") — **NEVER `assigned_user` / directory identity / email** — honoring Phase 24 D-15's owner-PII exclusion, allowlist-enforced at the query + prompt-builder layers. — **Reversibility:** costly — the factor allowlist is a grounding contract.
- **D-08:** The narrative must **explain the score's drivers, not invent a competing verdict** — e.g. "ranked high because it's KEV-listed, has a public exploit, and its SLA is breached" — referencing the same signals the deterministic score already uses (AIP-01 "augment and explain"). It does not assert its own priority number.

### Reuse (defaults, not re-litigated)
- **D-09:** Reuse Phase 24/25 wholesale: `_run_explain_stream()` for the on-demand path, the grounding-assembler + schema-variant + prompt-builder quadruplet pattern, cache/budget/audit/RBAC, the frontend AI section + citation component, `prompt_version` auto-hash (D-20). Phase 26 adds only: a prioritization grounding query, a `ExplainPrioritization…`-style schema (no rank field), a prompt builder, the batch submit/retrieve flow, and the scheduled pre-warm job. English-only (D-28) carried forward.

### Claude's Discretion
- Exact N for top-N and the nightly schedule time (D-01).
- Batch result retrieval mechanism — poll vs webhook, back-off, partial/failed-item handling (D-05) — researcher recommends.
- Exact factor-hash field set (D-01) and drill-panel placement/ordering (UI-SPEC).
- Whether the on-demand fallback and batch share one prompt/schema or need slight variants (default: share).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 26: Prioritization Narrative" — goal, 3 success criteria, Pitfall #7 ownership.
- `.planning/REQUIREMENTS.md` — AIP-01, AIP-02 (lines ~39–42, traceability ~93–94).

### Inherited scaffold (MUST read)
- `.planning/phases/24-ai-foundation-explain-this-vuln/24-CONTEXT.md` — D-06 (budget), D-08 (admin alert), D-15 (owner-PII exclusion), D-17 (RBAC), D-18/D-20 (cache + prompt-version hash), D-24 (grounded-false), D-25 (busy), D-27 (audit).
- `.planning/phases/25-asset-aware-remediation-guidance/25-SUMMARY files + 25-PATTERNS.md` — the grounding-assembler + schema-variant + prompt-builder + new-drill-section pattern to mirror.
- `.planning/phases/24-ai-foundation-explain-this-vuln/*-AI-SPEC.md` (if present) — the milestone AI design/eval contract.

### Message Batches API (NEW integration — research territory)
- The Anthropic Message Batches API (async bulk, ~50% cost, up to 24h turnaround) — the AIP-02 generator. Use the `claude-api` skill / official Anthropic docs to pin the current batch submit/retrieve API shape at research time.

### Code the phase touches / grounds in
- `backend/app/connectors/scheduler.py` — the asyncio task-based scheduler the nightly batch pre-warm plugs into (`_run_single_sync`/`_running_syncs` pattern; `asyncio.create_task`).
- `backend/app/vulnerabilities/models.py` — factor fields (`cvss_v3_score`, `epss_score`, `exploit_available`, `cisa_kev`, `exploit_status_name`, `sla_due_at`, `sla_breached`) + wherever the deterministic ASSET-02 score/ordering is computed (`backend/app/vulnerabilities/service.py`).
- `backend/app/assets/models.py` — `department` (the allowed owner factor) vs `assigned_user` (excluded PII).
- `backend/app/ai/` (grounding.py, schemas.py, prompt_builder.py, explain.py, cache.py, budget.py, audit.py, api/v1/ai/) — reuse + extend.
- `frontend/src/components/ai/` + drill panel — the reused AI section; a new "Prioritization" section with NO sort control.
- `.claude/skills/sketch-findings-getvul/` — MANDATORY before UI (states, copy-voice, tokens; reuse Phase 24 section + citations).

### Phase boundary (do NOT build)
- Phase 27 (AID-01) — ticket auto-drafting. Phase 28 — eval/cost/observability dashboards. This phase captures audit rows + enforces the budget guard but builds no dashboard.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/connectors/scheduler.py` — asyncio-task scheduler; the batch pre-warm is a new task dispatched here (never inline in a sync tick).
- `backend/app/ai/explain.py::_run_explain_stream()` — the on-demand (cache-miss) request path, reused with a new resourceType.
- Phase 24/25 grounding + schema-variant + prompt-builder + AI-section + citation components — mirrored for the prioritization view.
- Factor fields already present on `Vulnerability` (cvss/epss/exploit/kev/exploit-status/sla) + `Asset.department` — no new columns needed for grounding.

### Established Patterns
- Per-view quadruplet (allowlist → schema → prompt builder → thin path) from Phase 25.
- Tenant cache keyed `(resource, factor-hash, model, prompt-version)`; batch and on-demand write the same cache (D-06).
- Fail-closed budget guard (D-06) — extended to pre-estimate a batch before submission (D-07).
- Owner-PII exclusion via query + prompt-builder allowlist (D-15) — department-only.

### Integration Points
- Scheduler → batch submit (asyncio.create_task) → Message Batches API → retrieve → write tenant cache → drill panel reads as a cache hit.
- New "Prioritization" drill section reads the cache; on miss offers on-demand generation (Analyst+) or a "being prepared" state.
</code_context>

<specifics>
## Specific Ideas

- The deterministic ASSET-02 score is sacrosanct: it remains the single sortable number; the AI narrative never introduces a competing rank (no rank field in schema, no sort control in UI).
- Narrative explains the score's real drivers (KEV/exploit/SLA/severity/department) rather than asserting an independent verdict.
- Bulk-first economics: nightly batch via Message Batches API (~50% cost) is the primary generator; on-demand single-request is the cache-miss fallback.
- Fail-closed everywhere: budget pre-estimate before batch submit; owner referenced only by department; grounded-false honest refusal inherited.
</specifics>

<deferred>
## Deferred Ideas

- **Ticket auto-drafting** (title/description/remediation/asset-context, provider field mapping) → Phase 27 (AID-01).
- **AI usage/cost dashboard, per-tenant cost circuit breaker sophistication, eval harness (DeepEval/promptfoo)** → Phase 28. This phase writes audit rows + enforces the simple fail-closed budget guard, but builds no dashboard.
- **An independently-sortable AI priority rank** — explicitly OUT (violates AIP-01/SC2/Pitfall #7); never build.
- Non-English narratives → out of milestone scope (D-28 carried forward).

None of the above are built in Phase 26.
</deferred>

---

*Phase: 26-prioritization-narrative*
*Context gathered: 2026-07-30*
