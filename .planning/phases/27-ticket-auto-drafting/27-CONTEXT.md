# Phase 27: Ticket Auto-Drafting - Context

**Gathered:** 2026-08-01
**Status:** Ready for planning

<domain>
## Phase Boundary

An analyst opening the Jira/Asana ticket-create flow for a vulnerability gets an **AI-drafted title + description + remediation + asset-context pre-filled** into the existing create form, **edits every field**, and a **human click always creates** the ticket — the draft NEVER auto-submits.

Requirement: **AID-01** (single). Depends on Phase 24 (explain) + Phase 25 (remediation guidance + the `TicketCreateRequest.description` pre-fill seam) — this phase is a **pure CONSUMER of already-generated AI outputs**: no new AI grounding/schema/engine, no new backend risk surface, **no `Ticket` DB model change**. The one small backend change is a `title` override on the request schema (mirroring Phase 25's `description`).

Reuses wholesale: BYOK/RBAC (D-17), no-key state (D-23), the existing drill-panel ticket-create dialog + Phase 25's description textarea + `TicketCreateRequest.description`/`create_tickets()` WYSIWYG override, owner-as-department PII discipline (D-15), English-only (D-28). It ADDS only: a client-side draft-composer, a `title` request-override field + auto-build fallback, and the auto-populate-on-open UX.
</domain>

<decisions>
## Implementation Decisions

### Draft source (the core architectural decision)
- **D-01:** The draft is **composed CLIENT-SIDE from already-cached AI outputs** — no new AI call, no new backend risk surface (the roadmap's "pure consumer"). Sources: Phase 24 explain summary → the description body; Phase 25 remediation guidance → the remediation section; the drill panel's own asset facts → the asset-context section; Phase 26 prioritization narrative optionally included. The **TITLE is derived DETERMINISTICALLY** (e.g. `{cve_id}: {affected_product}` / the existing server title convention) — NOT a new AI call. — **Reversibility:** reversible (client-side composition; no new persisted contract).
- **D-06:** Asset-context and any AI-composed text follow the **owner-as-department** discipline (D-15) — the AI-sourced portions never carry owner PII (email/name); the analyst edits freely (it's their own tenant data going to their own ticketing system, gated by their explicit Create click).

### Trigger + freshness
- **D-02:** **Auto-populate on opening the create flow** from whatever cached AI outputs exist (free — no spend; SC1 literal). A missing piece (e.g. explain not generated yet) leaves that section blank with a **subordinate "Draft with AI" action** (Analyst+, D-17) that generates it on demand via the existing per-resource endpoints. No spend on findings the analyst just glances at (respects D-09's budget discipline). — **Reversibility:** reversible.

### Field mapping + editability (SC2)
- **D-03:** **An editable TITLE field + one composed, editable description body.** Backend gains a `title: str | None` override on `TicketCreateRequest` (mirroring Phase 25's `description` exactly: `max_length`, `extra="forbid"` mass-assignment defense, whitespace→None, and `create_tickets()` honors it, falling back to the existing server auto-build when absent). The existing description textarea is pre-filled with a **composed body** (description + remediation + asset-context as clearly-labeled sections; prioritization optional). The whole body + title are freely editable → satisfies SC2 "edit every drafted field." Maps to Jira/Asana's real summary+description shape (no forced 4-field UI). — **Reversibility:** costly — the `title` request field + `create_tickets()` branch is a new (small) request contract, mirroring D-08/25-06.

### Graceful degradation + never-auto-submit (SC3)
- **D-04:** The create flow **ALWAYS works and is NEVER blocked by missing AI**: pre-fill whichever sections have cached outputs, leave the rest blank/manual (deterministic title fallback); **no key configured → the existing fully-manual flow, unchanged** (D-23). **Nothing is ever auto-submitted** — the existing human **Create** click is the ONLY submit path (SC3); AI pre-fill is a convenience layer, never a dependency or a gate. Do NOT gate the Create button on a complete draft. — **Reversibility:** reversible.

### Scope
- **D-05:** The ONLY backend change is the `title` request-override + its `create_tickets()` fallback branch (D-03). No new AI endpoint, no new grounding/schema/prompt, no `Ticket` DB model change, no new migration for a draft (drafts are ephemeral client state until the analyst clicks Create). The mobile ticket-create path (`drill-panel-mobile.tsx renderConfirm`) must be threaded the same as desktop (the Phase 25 divergence lesson).

### Claude's Discretion
- Exact deterministic title format (D-01) and the composed-body section labels/order (D-03).
- Whether the Phase 26 prioritization narrative is included in the body by default (D-01) — lean: include when cached.
- Placement of the "Draft with AI" gap-fill affordance (D-02) — a UI-SPEC decision.
- Whether title pre-fill needs a `title` field at all vs. reusing the existing summary field path — plan-time confirm against `create_tickets()`.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 27: Ticket Auto-Drafting" — goal, 3 success criteria, "pure consumer / no Ticket model changes".
- `.planning/REQUIREMENTS.md` — AID-01 (lines ~46, traceability ~95).

### Inherited seams this phase consumes/extends (MUST read)
- `.planning/phases/25-asset-aware-remediation-guidance/25-06-SUMMARY.md` + `25-07-SUMMARY.md` — the `TicketCreateRequest.description` override + `create_tickets()` WYSIWYG fallback + desktop/mobile dialog threading (the EXACT pattern the `title` override + composed pre-fill mirror).
- `.planning/phases/24-ai-foundation-explain-this-vuln/24-CONTEXT.md` — D-17 RBAC, D-23 no-key, D-09 auto-render-if-cached-else-button, D-15 owner-PII exclusion.
- `.planning/phases/26-prioritization-narrative/26-*` — the prioritization narrative optionally composed into the body.

### Code the phase touches / reads
- `backend/app/ticketing/schemas.py` — `TicketCreateRequest` (add `title` override, mirror `description`).
- `backend/app/ticketing/service.py` — `create_tickets()` (honor `title`, fallback to the existing auto-build; the server title convention informs D-01's deterministic title).
- `frontend/src/components/vulnerabilities/` — the drill-panel ticket-create dialog (`drill-content.tsx` ConfirmModal + `drill-panel-mobile.tsx` renderConfirm — DIVERGENT paths, thread both), `ticket-provider-picker.tsx`.
- `frontend/src/lib/mutations/use-create-ticket.ts` — the create mutation body (add `title`).
- The GET cache-check endpoints the composer reads: `use-explain-cache.ts` (resourceType `vuln`/`remediation-guidance`/`prioritization`) — cached outputs to compose from.
- `.claude/skills/sketch-findings-getvul/` — MANDATORY before UI (states, copy-voice, tokens; reuse existing dialog chrome).

### Phase boundary (do NOT build)
- Phase 28 — eval/cost/observability dashboards + red-team CI + cost circuit breaker. This phase adds no new AI call to eval and no dashboard.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 25's `TicketCreateRequest.description` override + `create_tickets()` WYSIWYG fallback + desktop/mobile dialog threading — the `title` override + composed pre-fill mirror it exactly.
- The GET cache-check endpoints (explain / remediation-guidance / prioritization) + `use-explain-cache.ts` — the frontend composer reads cached outputs client-side.
- The drill panel's own asset facts (owner department, host, product) — the asset-context source, already loaded.

### Established Patterns
- Request-schema override + server fallback (Phase 25 `description`) — the `title` override follows it (extra=forbid mass-assignment defense, whitespace→None).
- Divergent desktop `ConfirmModal` vs mobile `renderConfirm` — must thread the new title field + pre-fill through BOTH (Phase 25 lesson).
- AI-as-convenience-never-dependency + human-click-to-create (D-09, D-23, existing create gate).

### Integration Points
- On dialog open: compose title (deterministic) + body (cached explain/remediation/asset-context/prioritization) → pre-fill the title field + description textarea → analyst edits → existing Create click → `create_tickets()` honors title+description, else auto-builds.
</code_context>

<specifics>
## Specific Ideas

- Pure consumer: reuse cached AI outputs; add NO new AI call. Title is deterministic, not AI-generated.
- The create flow is sacrosanct: never blocked by missing AI, never auto-submits; the human Create click is the only submit path.
- Edit-everything: title field + one composed, fully-editable description body (Jira/Asana summary+description shape).
- Convenience layer: pre-fill what's cached, offer on-demand "Draft with AI" for gaps (Analyst+), degrade to the existing manual flow with no key.
</specifics>

<deferred>
## Deferred Ideas

- **A dedicated 'draft this ticket' AI call / AI-generated title** — explicitly OUT (chose compose-from-cache + deterministic title; a new call would add backend risk surface the roadmap forbids).
- **Auto-generating missing explain/remediation on dialog open** — OUT (spends budget on every open; use the on-demand "Draft with AI" gap-fill instead, D-02/D-09).
- **Eval/cost/observability, red-team CI, cost circuit breaker** → Phase 28.
- **Ticket DB model changes / new draft-persistence table** — OUT (drafts are ephemeral client state until Create).
- Non-English drafts → out of milestone scope (D-28).

None of the above are built in Phase 27.
</deferred>

---

*Phase: 27-ticket-auto-drafting*
*Context gathered: 2026-08-01*
