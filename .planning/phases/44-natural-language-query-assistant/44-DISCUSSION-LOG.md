# Phase 44: Natural-Language Query Assistant - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-24
**Phase:** 44-natural-language-query-assistant
**Areas discussed:** Translation & safe-schema, Query surface & result types, Entry point & interaction, Answer behavior & grounding, Caching & freshness, Closing the loop (result actions), Who can ask (RBAC & spend), Question history

---

## Translation & safe-schema

| Option | Description | Selected |
|--------|-------------|----------|
| Tool-call existing filters | LLM emits a schema-validated filter object into the shipped read services | ✓ |
| Canned intent catalog | Classify into N predefined templates + slot-fill | |
| Constrained query DSL | Emit a custom grammar → compile to SQLAlchemy | |

**User's choice:** Tool-call existing filters (D-01)
**Notes:** Smallest new surface, reuses v3.0 tenant-scoping + Pydantic validation.

| Option | Description | Selected |
|--------|-------------|----------|
| One primary entity + joins | One result entity per question; filter carries supported cross-object predicates | ✓ |
| Model chains multiple tools | LLM composes several tool calls itself | |
| You decide | Research-gated | |

**User's choice:** One primary entity + joins (D-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend filters additively | Add missing predicates to existing filter objects (benefits NLQ + list UI) | ✓ |
| Refuse honestly, ship as-is | Scope to current filters; refuse unsupported | |
| You decide (research-gated) | Extend only where the gap is material | |

**User's choice:** Extend filters additively (D-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Always show interpretation | Human-readable summary of applied filter alongside the answer | ✓ |
| Expandable / on demand | Behind a "how I read this" expander | |
| Don't show | Answer + results only | |

**User's choice:** Always show interpretation (D-04)

---

## Query surface & result types

| Option | Description | Selected |
|--------|-------------|----------|
| Core three only | Vuln / asset / ticket | ✓ |
| Core + SLA/exception | + operational SLA + exception records | |
| All available services | + campaign/coverage/compliance/analytics | |

**User's choice:** Core three only (D-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Filtered lists (+ count) | Every question → filtered list; "how many" = list size | ✓ |
| Lists + group-by aggregations | Also count-by breakdowns via facet/stats services | |
| You decide | Planner picks | |

**User's choice:** Filtered lists (+ count) (D-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Exact count + top-N to model | Deterministic total; bounded top-N narrated | ✓ |
| Reuse list pagination as-is | Narrate one page | |
| You decide | Planner sets cap | |

**User's choice:** Exact count + top-N to model (D-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing list rows | Sunset-design row primitives, rows link to drill/detail | ✓ |
| Compact bespoke result table | Lightweight generic table | |
| You decide | Per entity | |

**User's choice:** Reuse existing list rows (D-08)

---

## Entry point & interaction

| Option | Description | Selected |
|--------|-------------|----------|
| New "Ask" nav page | Dedicated top-level page | ✓ |
| NL mode in Cmd+K search | Extend global search | |
| Both: page + Cmd+K entry | Full page + palette deep-link | |

**User's choice:** New "Ask" nav page (D-09)

| Option | Description | Selected |
|--------|-------------|----------|
| Single-shot per question | Independent asks, no conversation state | ✓ |
| Multi-turn refine | Carry context for follow-ups | |
| You decide | Low-risk default | |

**User's choice:** Single-shot per question (D-10)

| Option | Description | Selected |
|--------|-------------|----------|
| Curated example questions | Clickable starters reflecting the supported surface | ✓ |
| Placeholder hint only | Single placeholder line | |
| You decide | Per state-patterns | |

**User's choice:** Curated example questions (D-11)

| Option | Description | Selected |
|--------|-------------|----------|
| Nav visible, page shows configure-CTA | Always-visible entry; inert page links to wizard | ✓ |
| Hide nav until configured | Entry appears only once keyed | |
| You decide | Mirror existing inert state | |

**User's choice:** Nav visible, page shows configure-CTA (D-12)

---

## Answer behavior & grounding

| Option | Description | Selected |
|--------|-------------|----------|
| Narrate executed results only | Model narrates returned rows + exact count; no invented facts | ✓ |
| Model reasons over data | Freer analysis | |
| You decide | Within grounded discipline | |

**User's choice:** Narrate executed results only (D-13)

| Option | Description | Selected |
|--------|-------------|----------|
| Refuse + guide to supported | Decline + point to answerable questions | ✓ |
| Best-effort, never refuse | Always answer closest interpretation | |
| You decide | Within cite-or-refuse | |

**User's choice:** Refuse + guide to supported (D-14)

| Option | Description | Selected |
|--------|-------------|----------|
| Results first, narrative streams | Table on query execute; prose streams after via SSE | ✓ |
| Single buffered response | Everything at once | |
| You decide | Reuse SSE if streaming | |

**User's choice:** Results first, narrative streams (D-15)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend gate with NLQ cases | Add NLQ golden-set + injection/cross-tenant red-team to CI | ✓ |
| Reuse guardrails, no new evals | Rely on shipped guardrails only | |
| You decide | Eval-planner scopes | |

**User's choice:** Extend gate with NLQ cases (D-16)

---

## Caching & freshness

| Option | Description | Selected |
|--------|-------------|----------|
| Cache translation, run query live | Cache question→filter; always execute fresh | ✓ |
| No caching | Re-run translation + query each time | |
| Cache full answers (TTL) | Cache whole answer+result | |

**User's choice:** Cache translation, run query live (D-19)

---

## Closing the loop (result actions)

| Option | Description | Selected |
|--------|-------------|----------|
| Deep-link to filtered list | "Open these N in <list>" applies the translated filter to the real list view | ✓ |
| Read-only v1 | Per-row links only | |
| You decide | If filter maps to URL params | |

**User's choice:** Deep-link to filtered list (D-17)

---

## Who can ask (RBAC & spend)

| Option | Description | Selected |
|--------|-------------|----------|
| Analyst+ to ask, viewer+ cached | Mirror v3.0 route guards | ✓ |
| Viewer+ can ask | Any read role can spend the key | |
| You decide | Reuse guards + breaker | |

**User's choice:** Analyst+ to ask, viewer+ cached (D-18)

---

## Question history

| Option | Description | Selected |
|--------|-------------|----------|
| Stateless v1 (no history) | No persisted history | ✓ |
| Recent questions (client-only) | localStorage recents | |
| Persisted saved questions | Backend store + CRUD | |

**User's choice:** Stateless v1 (no history) (D-20)

---

## Claude's Discretion

- "Ask" page route naming/layout + interpretation/streaming layout (D-09).
- Top-N cap size + result ranking to the model (D-07).
- Which additive filter predicates and to which filter object (D-03).
- Starter-question copy + count (D-11).
- Reuse `_run_explain_stream` parameterized vs a sibling stream function (D-13/D-15).
- Precise NLQ eval/red-team case set (D-16).

## Deferred Ideas

- Multi-turn / conversational refinement (D-10 ships single-shot).
- Answering over SLA / exception / campaign / coverage / compliance / analytics (D-05 core-three-only).
- Group-by / aggregation result shapes (D-06 lists+count only).
- Persisted / saved question history (D-20 stateless).
- Bulk actions on results (D-17 read-only deep-link only).
- NL mode inside Cmd+K global search (D-09 chose a dedicated page).
