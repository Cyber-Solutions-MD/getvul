# Phase 24: AI Foundation + "Explain This Vuln" - Context

**Gathered:** 2026-07-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn AI on (BYOK) and ship the first grounded AI capability at minimum blast radius — the foundation Phases 25–28 reuse.

- A **tenant admin** configures their **own** Anthropic API key + model preference (encrypted via the existing Fernet/`ConnectorConfig` pattern); no shared/fallback key exists; every AI feature stays in a graceful "configure AI" state until the key is set (AI-01).
- An **analyst** gets an **"Explain this vuln"** streamed, plain-English + business-risk explanation in the drill panel, grounded in the correlated record with **two-tier citation** (verbatim scanner text vs. AI-interpreted framing) (AI-03, AI-04).
- Untrusted scanner text is delivered to the model **as data only**, never as instructions; **every** model response is schema-validated before a token reaches the UI (AI-02).
- Every AI call (incl. scheduler-originated) is **audit-logged** (model/tokens/cost/provenance); AI output cached **tenant-scoped only**, never cross-served (AI-05, AI-06).

**The entire technical HOW is already locked by `24-AI-SPEC.md`** (framework, model, streaming pattern, prompt-builder, schema, cache, audit, eval). This discussion captured only the **product/UX/scope decisions** that spec left open.

**Out of scope (deferred):** full per-tenant cost circuit breaker + admin usage/cost dashboard (Phase 28), explanation → ticket pre-fill (Phase 27), golden-set promotion + calibrated LLM-judge dashboards (Phase 28), RAG / semantic caching / embeddings (milestone out-of-scope). No new capability beyond "configure AI + explain a vuln."

</domain>

<decisions>
## Implementation Decisions

### AI configuration (AI-01)
- **D-01:** The admin configures an **API key + model dropdown** (`claude-sonnet-5` / `claude-opus-5` / `claude-haiku-4-5`). `effort` stays fixed at `low` (AI-SPEC §4). Default model = **`claude-sonnet-5`**.
- **D-02:** Model choice is **tenant-wide** (one model per tenant), not per-user/per-finding. The cache key already includes `model` (AI-SPEC), so no extra keying logic. — **Reversibility:** reversible.
- **D-03:** AI configuration lives as a **new `ConnectorConfig` connector-type card on `/connectors`**, reusing the **Phase 19 add-connector wizard** (provider → credentials → test → confirm). AI is a new encrypted `connector_type`; "AI features are the only consumers of that key" (REQUIREMENTS) holds because it's just another encrypted `ConnectorConfig` row. — **Reversibility:** costly — a new `connector_type` + config shape is a migration/contract other phases (25–28) build on.
- **D-04:** Key is **tested before save** — a cheap validation call authenticates the key; persist only on success. This is exactly the wizard's step-3 test gate. The admin who sets the key gets immediate feedback; no silent bad-key state that surfaces to an analyst mid-triage.
- **D-05:** The model dropdown carries **short cost/quality guidance copy** per option ("Sonnet 5 — recommended balance", "Opus 5 — higher cost", "Haiku — cheapest, lower grounding fidelity") because cost lands on the tenant's own BYOK account. Follows copy-voice "no naked controls."

### Cost / budget (partial pull-forward of AIE-03)
- **D-06:** A **simple per-tenant monthly spend cap** ships this phase: a budget field + a **fail-closed pre-call check** + a typed **"AI budget exceeded"** state. The full circuit-breaker sophistication + admin usage/cost dashboard stays **Phase 28 (AIE-03/04)**. This is a deliberate, fenced pull-forward. — **Reversibility:** costly — a budget field + monthly-spend accounting is a schema/contract Phase 28 extends.
- **D-07:** The per-call hard `max_tokens=1024` ceiling ships regardless (AI-SPEC §4) — independent of the configurable monthly cap.
- **D-08:** On budget breach: analyst sees the typed "AI budget exceeded" panel state; **admins are alerted via the existing NOTIF-01** in-app + SMTP system so the person who can raise the cap actually finds out.

### Explain trigger + panel UX (AI-03, AI-04)
- **D-09:** **Auto-render if cached, else button.** On drill-panel open, a **cheap cache-lookup** (no model call) renders the explanation instantly on a hit; on a miss the analyst sees an **"Explain this vuln"** button. No spend on findings an analyst just glances at (protects D-06's cap); re-opens of the same finding are cache hits.
- **D-10:** **No manual "regenerate"** affordance. The cache key `(finding, record hash, model, prompt version)` auto-invalidates on any meaningful change, so a fresh explanation always follows fresh inputs; a manual regenerate would only spend budget on near-identical `temperature=0` output.
- **D-11:** The trigger + output live in a **dedicated "AI Explanation" section** in the drill panel's main column. Exact vertical order/placement is a UI-SPEC decision.
- **D-12:** **Perceived streaming = "Analyzing…" then replay.** Because the architecture is buffer-then-validate-then-replay (AI-SPEC §4), the analyst sees a distinct **"Analyzing this finding…"** progress state during real model latency (server buffers + validates), then the **validated** summary **replays token-by-token** — that replay is where AI-03's "streams token-by-token into the panel" is actually satisfied. Raw provider tokens are never proxied to the browser.

### Two-tier citation (AI-04)
- **D-13:** **Inline per-claim tagging** — `scanner_verbatim` claims are visually marked in place (e.g. quoted/tinted) vs. `ai_interpreted` framing as normal prose, with a small source tag. Reuse the sunset design system's existing chip/badge primitives; exact visual locked at UI-SPEC. Goal: an analyst tells scanner fact from Claude's inference **at a glance** (AI-SPEC §1b rubric).
- **D-14:** `source_field` is surfaced **on hover / expand** — the tier is always visible; the specific grounding field (e.g. `cve_description`, `cvss_vector`) reveals on demand. Keeps a queue-of-hundreds triage flow uncluttered while preserving the field-level audit trail.

### Explain affordance scope — all three views, sequenced (AI-04)
- **D-15:** Explain ships on **all three drill views** — per-vuln (CVE-on-host), **per-host**, and **per-remediation** — but **sequenced internally**: the planner builds and validates the **per-vuln CVE-on-host path end-to-end first** (grounding record, `ExplainVulnResponse` schema, eval golden-set), **then** extends the prompt-builder to the host + remediation record shapes within the phase. — **Reversibility:** costly.
  - ⚠️ **Scope note for planner/researcher:** this is a real widening vs. the AI-SPEC's single-record "minimum blast radius" design (`get_correlated_finding` targets one CVE-on-host record only). Per-host is an **aggregate of many findings** — a genuinely different grounding/faithfulness problem. The per-vuln-first sequencing is the risk mitigation; do not let host/remediation grounding block the per-vuln foundation from being proven first.
- **D-16:** **Aggregate explanation shape = "posture summary."** Per-host = the asset's **overall risk posture** grounded in its aggregated findings (which findings dominate, internet-facing exposure, KEV-listed count, worst CVSS) — **not** a concatenation of per-CVE blurbs. Per-remediation = **what applying this one fix accomplishes** across the affected assets + its priority. Each aggregate view gets its **own grounding shape + schema variant**. — **Reversibility:** costly — each is a schema/prompt contract.

### RBAC (RBAC-01)
- **D-17:** Explain is invokable by **Analyst and above** (Analyst / Admin / Owner). **Viewers** (read-only) see a **cached** explanation but cannot trigger a new call (every uncached call spends the tenant's money) — matches the Owner>Admin>Analyst>Viewer hierarchy and the "Viewer takes no costly actions" principle.

### Caching (AI-05)
- **D-18:** **Cache-hash covers the allowlisted grounding fields only** — an unrelated edit (e.g. owner reassignment) does **not** force a re-spend; only a change to data that actually affects grounding yields a fresh explanation. This is what makes D-10 (no manual regenerate) correct.
- **D-19:** Cache entries carry a **TTL** (~30 days, exact window at plan time) **on top of** the `(finding, record-hash, model, prompt-version)` keying — bounds Redis growth and is a safety net against subtle staleness even when the hash looks unchanged.

### Prompt-version convention (reused by Phases 25–27)
- **D-20:** `prompt_version` (a cache-key component) is an **auto-hash of `SYSTEM_PROMPT` + few-shot + schema** — self-invalidating, zero manual bump, eliminates "forgot to bump the version" staleness bugs. The prompt change is still a reviewable diff; the version is computed from it. **Deviation noted:** AI-SPEC §4b suggested a manual versioned constant; auto-hash supersedes it and is the house convention Phases 25–27 inherit.

### Feedback capture (flywheel signal — AI-SPEC §6/§7)
- **D-21:** Ship **thumbs (up/down) + optional freeform correction note** on each explanation now — the highest-signal monitoring metric per AI-SPEC. Stored in a **new dedicated `ai_feedback` table** (finding, tenant, verdict, note, provenance), **capture-only** this phase — no UI surfacing until Phase 28's flywheel/dashboards. — **Reversibility:** one-way — a new table is a migration; changing its shape later requires another migration + backfill.
- **D-22:** Feedback is **per-user and editable** — one thumbs+note row per (finding-explanation, user); an analyst can change their own verdict.

### Degraded / edge states
- **D-23:** **No key configured** → an honest "AI isn't set up yet" state. Admins/owners get a CTA to the AI connector card; analysts get an "ask an admin to enable AI" nudge. Never an error (satisfies AI-01's graceful "configure AI" mandate + copy-voice).
- **D-24:** **`grounded=false`** → a **distinct, honest "not enough finding data to explain this reliably" card** naming what's missing — visually different from a system error. Reinforces the anti-fabrication value prop (the tool declined to guess).
- **D-25:** **Anthropic 429 / rate limits** (BYOK = tenant's own limits) → let the SDK's built-in retry/backoff honor `Retry-After`; on persistent failure surface a typed **"AI busy — try again in a moment"** state; add a **light per-tenant in-flight concurrency guard** so a queue-clicking analyst doesn't stampede the tenant's key.
- **D-26:** The one-time corrective **retry (on validation-fail / `grounded=false`) is invisible** to the analyst — just a slightly longer "Analyzing…" wait; both attempts are audit-logged with distinct status (AI-SPEC §4b).

### Audit visibility (AI-06)
- **D-27:** AI calls write into the **existing AUDIT-01 audit log** and surface in the existing `audit-log-pane` this phase. The dedicated AI **usage/cost dashboard** stays Phase 28.

### Localization
- **D-28:** The explanation is **English-only** this phase — keeps the eval golden-set and grounding rubric single-language (AI-SPEC §5). Locale-following is not in scope.

### Claude's Discretion
D-15/D-16 leave the exact aggregate (host/remediation) schema-variant field lists and grounding-record assembly to the researcher/planner; D-11/D-13 leave exact panel layout, ordering, and citation pixel-styling to the UI-SPEC (`/gsd-ui-phase`); D-19's exact TTL window and D-25's concurrency-cap value are plan-time details.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### AI design contract (READ FIRST — locks technical HOW)
- `.planning/phases/24-ai-foundation-explain-this-vuln/24-AI-SPEC.md` — the full AI design contract: framework (direct Anthropic SDK), model config (`claude-sonnet-5`/temp 0/effort low/max_tokens 1024), buffer-then-validate-then-replay streaming, allowlist prompt-builder + untrusted-content-as-data contract, `ExplainVulnResponse` schema, tenant-scoped content-hash cache, audit log, and the DeepEval/promptfoo/pytest eval strategy + guardrails + monitoring. This CONTEXT.md captures only the product/UX/scope decisions the AI-SPEC deliberately left open.

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — AI-01…AI-06 (this phase) + the BYOK foundational principle (client-provided-key only; no shared/fallback key; inert until configured).
- `.planning/ROADMAP.md` §"Phase 24" — goal, success criteria, pitfalls owned (#1 prompt injection, #3 PII leakage, #4 cross-tenant bleed, #6 non-determinism-in-CI, #9 drill-panel latency).

### Design system (UI work)
- `.claude/skills/sketch-findings-getvul/` — sunset palette, chip/badge primitives (D-13 citation tags), state patterns (loading/empty/error — D-23/D-24/D-25), copy-voice (D-05/D-23). Auto-load before any UI implementation per CLAUDE.md.

### Prior-phase reuse seams
- `.planning/phases/23-ingestion-reliability-precursor/23-CONTEXT.md` — provider-dispatch protocol (D-06) + drill-panel ticket-create affordance (D-14 there) that Phase 27 plugs into; the grounding-data reliability floor this phase depends on.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/encryption.py` + the `ConnectorConfig` / Fernet pattern — encrypted storage for the BYOK key (D-03). AI becomes a new `connector_type`.
- Phase 19 **add-connector wizard** (`/dashboard/connectors`, four-step provider→credentials→test→confirm, ResponsiveDialog/vaul) — reused verbatim for AI key config (D-03); its step-3 test **is** D-04's test-before-save.
- **DrillPanel** (`frontend/src/…/DrillPanel`, generalized with `idKey` in Phase 13) — host of the "AI Explanation" section (D-11) across vuln/host/remediation views (D-15).
- Settings panes (`frontend/src/components/settings/*-pane.tsx`) incl. `audit-log-pane.tsx` — surfaces AI audit rows (D-27); RBAC-gating precedent (D-17).
- **NOTIF-01** in-app + SMTP notification system — budget-breach admin alert (D-08).
- **AUDIT-01** audit log + `audit-log-pane` — AI-call audit rows (D-27, AI-06).
- `SyncStatusPill` / existing error-state visual language — degraded-state treatments (D-23/D-24/D-25).

### Established Patterns
- Per-tenant scoping by `tenant_id` from JWT (TENANT-01) — cache keying (D-18), config, and cross-tenant isolation (AI-05).
- RBAC per-route enforcement (RBAC-01) — Explain invocation gate (D-17).
- Redis for cache/session state (v1.0 Phase 1) — tenant-scoped explanation cache (D-18/D-19).
- TanStack Query data layer + `queryKeys` namespacing — the cache-lookup-on-open (D-09) and streamed-replay hooks.

### Integration Points
- New `backend/app/ai/` package (per AI-SPEC §3 structure: `tenant_keys.py`, `schemas.py`, `prompt_builder.py`, `explain_vuln.py`, `audit.py`, `cache.py`) + `app/api/v1/ai/` SSE router.
- New `ai_feedback` table (D-21) + alembic migration; AI `connector_type` + monthly-budget field migration (D-03/D-06).
- nginx: scoped `location /api/v1/ai/` with `proxy_buffering off` (AI-03 / AI-SPEC).

</code_context>

<specifics>
## Specific Ideas

- The replay UX (D-12) is the one non-obvious design the AI-SPEC locks for all four later AI phases: "stream to the UI" and "stream from the model" are two different streams joined by a validation gate.
- Citations should read as **one flowing explanation** an analyst can audit at a glance (D-13) — not a bureaucratic two-block split.
- `grounded=false` (D-24) is a **feature, not an error** — surfacing "the tool declined to guess" is a trust signal, per the AI-SPEC domain rubric.

</specifics>

<deferred>
## Deferred Ideas

- **Full per-tenant cost circuit breaker + admin usage/cost dashboard** — Phase 28 (AIE-03/04). This phase ships only a simple monthly cap + fail-closed check (D-06).
- **AI explanation quoted/pre-filled into Jira/Asana ticket drafts** — Phase 27 (Ticket Auto-Drafting). Explanation stays in the drill panel this phase (D-15); no copy-to-ticket path.
- **Golden-set promotion of thumbs-down/correction cases + calibrated LLM-judge dashboards** — Phase 28. This phase captures the `ai_feedback` signal only (D-21).
- **Effort-dial exposure / model-choice expansion beyond the dropdown** — revisit if evals justify (Phase 28+). Effort stays fixed `low` (D-01).
- **Explanation localization (locale-following)** — out of scope; English-only this phase (D-28).
- **Semantic/embedding caching, RAG** — milestone out-of-scope; exact-match tenant-scoped cache only.

</deferred>

---

*Phase: 24-ai-foundation-explain-this-vuln*
*Context gathered: 2026-07-28*
