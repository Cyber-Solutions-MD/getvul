# Phase 24: AI Foundation + "Explain This Vuln" - Research

**Researched:** 2026-07-28
**Domain:** Anthropic SDK integration (streaming + structured outputs) grounded in an existing FastAPI/Postgres/Redis/Next.js codebase — BYOK per-tenant AI foundation
**Confidence:** HIGH (codebase-grounded findings verified by direct file inspection; SDK/model claims verified against live platform.claude.com docs and package registries, July 2026)

> **Scope note:** `24-AI-SPEC.md` already locks the technical HOW (framework, model config, streaming pattern, prompt-builder contract, schema, cache design, audit design, eval strategy) to an excellent standard. This document does **not** repeat that content. It (1) verifies AI-SPEC's most load-bearing claims against live sources now that they're checkable, (2) grounds every abstract AI-SPEC pattern in this specific codebase's actual files/functions/conventions, and (3) surfaces concrete gaps AI-SPEC could not have seen (it predates `24-CONTEXT.md`'s D-15 three-view widening) or could not verify (anything gated behind a real Anthropic API key). Read AI-SPEC and UI-SPEC first; this document assumes both.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**AI configuration (AI-01)**
- D-01: Admin configures API key + model dropdown (`claude-sonnet-5` / `claude-opus-5` / `claude-haiku-4-5`). `effort` fixed at `low` (AI-SPEC §4). Default model = `claude-sonnet-5`.
- D-02: Model choice is tenant-wide (one model per tenant). Cache key already includes `model`. Reversible.
- D-03: AI configuration lives as a new `ConnectorConfig` connector-type card on `/connectors`, reusing the Phase 19 add-connector wizard (provider → credentials → test → confirm). AI is a new encrypted `connector_type`. Costly reversibility — new contract Phases 25-28 build on.
- D-04: Key is tested before save — a cheap validation call authenticates the key; persist only on success (wizard's step-3 test gate).
- D-05: Model dropdown carries short cost/quality guidance copy per option (no naked controls).

**Cost / budget (partial pull-forward of AIE-03)**
- D-06: Simple per-tenant monthly spend cap ships this phase — budget field + fail-closed pre-call check + typed "AI budget exceeded" state. Full circuit-breaker + admin dashboard stays Phase 28. Costly reversibility.
- D-07: Per-call hard `max_tokens=1024` ceiling ships regardless, independent of the configurable monthly cap.
- D-08: On budget breach: analyst sees typed panel state; admins alerted via existing NOTIF-01 in-app + SMTP.

**Explain trigger + panel UX (AI-03, AI-04)**
- D-09: Auto-render if cached, else button. Cheap cache-lookup (no model call) on drill-panel open.
- D-10: No manual "regenerate" affordance. Cache key `(finding, record hash, model, prompt version)` auto-invalidates on meaningful change.
- D-11: Trigger + output live in a dedicated "AI Explanation" section in the drill panel's main column. Placement locked by UI-SPEC (between Description and Remediation).
- D-12: Perceived streaming = "Analyzing…" then replay. Buffer-then-validate-then-replay (AI-SPEC §4). Raw provider tokens never proxied to the browser.

**Two-tier citation (AI-04)**
- D-13: Inline per-claim tagging — `scanner_verbatim` visually marked in place vs. `ai_interpreted` as normal prose + small source tag. Reuse sunset design system chip/badge primitives (UI-SPEC locks exact visual).
- D-14: `source_field` surfaced on hover/expand — tier always visible, field reveals on demand.

**Explain affordance scope — all three views, sequenced (AI-04)**
- D-15: Explain ships on all three drill views — per-vuln (CVE-on-host), per-host, per-remediation — but sequenced internally: build/validate the per-vuln CVE-on-host path end-to-end first (grounding record, `ExplainVulnResponse` schema, eval golden-set), then extend the prompt-builder to host + remediation record shapes within the phase. Costly reversibility.
  - ⚠️ Scope note (verbatim from CONTEXT.md): this is a real widening vs. the AI-SPEC's single-record "minimum blast radius" design (`get_correlated_finding` targets one CVE-on-host record only). Per-host is an aggregate of many findings — a genuinely different grounding/faithfulness problem. The per-vuln-first sequencing is the risk mitigation; do not let host/remediation grounding block the per-vuln foundation from being proven first.
- D-16: Aggregate explanation shape = "posture summary." Per-host = the asset's overall risk posture grounded in aggregated findings (which findings dominate, internet-facing exposure, KEV-listed count, worst CVSS) — not a concatenation of per-CVE blurbs. Per-remediation = what applying this one fix accomplishes across the affected assets + its priority. Each aggregate view gets its own grounding shape + schema variant. Costly reversibility.

**RBAC (RBAC-01)**
- D-17: Explain is invokable by Analyst and above. Viewers see a cached explanation but cannot trigger a new call.

**Caching (AI-05)**
- D-18: Cache-hash covers the allowlisted grounding fields only — an unrelated edit (e.g. owner reassignment) does not force a re-spend.
- D-19: Cache entries carry a TTL (~30 days, exact window at plan time) on top of the `(finding, record-hash, model, prompt-version)` keying.

**Prompt-version convention (reused by Phases 25-27)**
- D-20: `prompt_version` is an auto-hash of `SYSTEM_PROMPT` + few-shot + schema — self-invalidating, zero manual bump. Deviation noted: AI-SPEC §4b suggested a manual versioned constant; auto-hash supersedes it and is the house convention Phases 25-27 inherit.

**Feedback capture (flywheel signal)**
- D-21: Ship thumbs (up/down) + optional freeform correction note now — stored in a new dedicated `ai_feedback` table (finding, tenant, verdict, note, provenance), capture-only this phase — no UI surfacing until Phase 28. One-way reversibility — new table is a migration; shape changes need backfill.
- D-22: Feedback is per-user and editable — one thumbs+note row per (finding-explanation, user); an analyst can change their own verdict.

**Degraded / edge states**
- D-23: No key configured → honest "AI isn't set up yet" state, never an error. Role-gated CTA copy.
- D-24: `grounded=false` → distinct, honest "not enough finding data" card — a feature, not an error.
- D-25: Anthropic 429/rate limits → SDK built-in retry/backoff honors `Retry-After`; persistent failure → typed "AI busy" state; light per-tenant in-flight concurrency guard.
- D-26: The one-time corrective retry (validation-fail / `grounded=false`) is invisible to the analyst — both attempts audit-logged with distinct status.

**Audit visibility (AI-06)**
- D-27: AI calls write into the existing AUDIT-01 audit log, surface in the existing `audit-log-pane` this phase. Dedicated usage/cost dashboard stays Phase 28.

**Localization**
- D-28: English-only this phase.

### Claude's Discretion
D-15/D-16 leave the exact aggregate (host/remediation) schema-variant field lists and grounding-record assembly to the researcher/planner; D-11/D-13 leave exact panel layout, ordering, and citation pixel-styling to the UI-SPEC (already resolved — see `24-UI-SPEC.md`); D-19's exact TTL window and D-25's concurrency-cap value are plan-time details.

### Deferred Ideas (OUT OF SCOPE)
- Full per-tenant cost circuit breaker + admin usage/cost dashboard — Phase 28 (AIE-03/04). This phase ships only a simple monthly cap + fail-closed check (D-06).
- AI explanation quoted/pre-filled into Jira/Asana ticket drafts — Phase 27. Explanation stays in the drill panel this phase; no copy-to-ticket path.
- Golden-set promotion of thumbs-down/correction cases + calibrated LLM-judge dashboards — Phase 28. This phase captures the `ai_feedback` signal only.
- Effort-dial exposure / model-choice expansion beyond the dropdown — revisit if evals justify (Phase 28+). Effort stays fixed `low`.
- Explanation localization — out of scope; English-only this phase.
- Semantic/embedding caching, RAG — milestone out-of-scope; exact-match tenant-scoped cache only.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AI-01 | Tenant admin configures own Anthropic API key + model prefs, Fernet-encrypted, inert until keyed, no shared/fallback key | §"ConnectorConfig Reuse" resolves this as a **zero-migration** addition to the existing `connector_configs` table/wizard/CRUD stack. §"Key Test-Before-Save" gives the concrete free validation call. |
| AI-02 | Untrusted scanner text delivered as data never instructions; all output schema-validated before UI | AI-SPEC §4b already locks the pattern. This doc adds the concrete allowlist field lists (`VulnerabilityDetail`, `AssetDetail`) including which fields to **exclude** for PII (Critical Failure Mode #3, concretely identified in `AssetDetail.directory_user`). |
| AI-03 | AI responses stream token-by-token into drill panel via `fetch()`+`ReadableStream`, scoped nginx location, `proxy_buffering off` | §"nginx Location Block" gives the exact diff. §"Frontend SSE Consumption" gives the concrete hook design — grounded in why this codebase's Bearer-token auth structurally requires `fetch()` over `EventSource`. §"No Existing True-SSE Precedent" flags this as the phase's highest implementation-risk item. |
| AI-04 | "Explain this vuln" plain-English + business-risk summary, grounded, two-tier citation | AI-SPEC §5 (eval dimensions) + UI-SPEC (citation rendering contract) already cover this fully. This doc adds the reconciliation of **D-15's 3-view widening** against AI-SPEC's original single-record file layout (§"Reconciling D-15 Three-View Widening"). |
| AI-05 | AI outputs cached in Redis tenant-scoped, content-hash keyed, no cross-tenant serving | §"Redis Cache Key Convention" grounds the key format in the one existing Redis convention (`oidc:state:{state}`) and confirms `flushed_redis`/`tenant_a`/`tenant_b` fixtures already exist for the isolation test. |
| AI-06 | Every AI call audit-logged (model/tokens/cost/provenance), incl. scheduler-originated, avoiding the `audit()` nil-tenant path | §"Scheduler Audit Pattern" gives the exact resolution — mirrors the `system:cli` precedent in `encryption.py::rotate_credentials()`, with a concrete existing test (`test_encryption_rotation.py::test_audit_event`) to model new tests on. |
</phase_requirements>

---

## Summary

`24-AI-SPEC.md` already did the hard, generic Anthropic-SDK research to an unusually high standard — model config, streaming pattern, prompt-injection contract, schema validation, eval strategy are all locked and don't need to be redone. This research instead did two things: **verified** AI-SPEC's most consequential claims against live sources now that they're checkable (they held up, with one real gap found — see below), and **grounded** every abstract pattern in this specific codebase by reading the actual files that Phase 24 will touch or extend.

The single biggest finding is good news: **this phase requires far less new database schema than AI-SPEC's abstract description implies.** `ConnectorConfig.connector_type` is a plain `String(30)` column (not a Postgres enum) validated only by a Python dict (`CONNECTOR_TYPES`) — adding an `"ANTHROPIC"` connector type is a **pure application-layer change, zero Alembic migration**, and it automatically inherits the existing key-rotation (`rotate_credentials()`), CRUD, and test-before-save infrastructure verbatim. This also resolves the STATE.md-flagged concern about generalizing `rotate_credentials()` to sweep a new `AiConfig` table — there is no new table; it's a new row in the table `rotate_credentials()` already sweeps. Similarly, the model preference and monthly budget cap (D-01, D-06) fit inside the existing `ConnectorConfig.config` JSONB column with no schema change, and monthly spend tracking (D-06) is best derived by `SUM`-aggregating the existing `audit_logs` table rather than hand-rolling a new counter — the only genuinely new tables are `ai_feedback` (D-21) and a supporting composite index on `audit_logs(tenant_id, created_at)`.

The second-biggest finding is a real, concrete pitfall AI-SPEC's generic SDK research could not have caught: **Anthropic's live `effort` parameter documentation (fetched July 2026) does not list `claude-haiku-4-5` among effort-supporting models**, while D-01 explicitly offers Haiku as a tenant-selectable option and AI-SPEC §4 hardcodes `effort: "low"` for every model. This needs a live smoke-test before shipping the Haiku path (see Common Pitfalls).

The third finding is architectural: this codebase's **Bearer-token-in-`localStorage`** auth model is *why* AI-03 mandates `fetch()`+`ReadableStream` over native `EventSource` (which cannot carry custom headers) — a concrete grounding for a decision AI-SPEC stated but didn't derive. The existing generic `api()` fetch helper cannot be reused for the streaming endpoint (it always calls `.json()`); a new, small, purpose-built hook is needed, and this document sketches it.

Finally, this phase's technical HOW (Anthropic SDK version, model IDs, `output_config.format`/`effort` structured-outputs API) was independently re-verified against live `platform.claude.com` docs and package registries as of 2026-07-28 — everything AI-SPEC claimed checks out, now at HIGH confidence rather than "as researched by an agent that can't re-verify."

**Primary recommendation:** Build Phase 24 as a pure additive layer over the existing `ConnectorConfig`/wizard/audit/Redis/RBAC infrastructure — resist the temptation to introduce new tables or new auth dependencies where the existing ones (`require_analyst`, `get_redis`, `audit_log` shape, `AddConnectorWizard`) already fit. Spend the phase's real engineering novelty budget on the two things that are genuinely new to this codebase: true incremental SSE through nginx, and the frontend's manual stream-parsing hook.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| BYOK key configuration + storage | API / Backend (`ConnectorConfig`, Fernet) | Frontend Server (wizard form) | Encryption + persistence is a backend contract; the wizard is a thin, already-generic UI over it |
| Key test-before-save | API / Backend (`tester.py` + Anthropic `count_tokens`) | — | Cheap validation call must happen server-side (key material never reaches the browser) |
| Explain trigger + cache-check | Browser / Client (button/auto-render state) | API / Backend (cheap cache-lookup endpoint) | UI decides what to render; a fast backend GET tells it cache-hit vs. miss |
| Model→backend token consumption | API / Backend (`explain_vuln_stream`, buffer-then-validate) | — | The untrusted Anthropic stream must never leave backend process memory unvalidated |
| Backend→browser replay stream | API / Backend (SSE emitter) | Browser / Client (`fetch`+`ReadableStream` consumer) | Two independent streams joined by the validation gate — genuinely split ownership |
| Schema validation gate | API / Backend (Pydantic) | — | AI-02's non-negotiable backstop; must run before any byte reaches the client |
| Two-tier citation rendering | Browser / Client (inline span/tooltip) | — | Pure presentation over an already-validated JSON payload |
| Prompt construction (untrusted-as-data) | API / Backend (`prompt_builder.py`) | — | The allowlist boundary is a backend-only concern; scanner text never touches the frontend AI path |
| Cross-tenant cache isolation | Database / Storage (Redis key namespacing) | API / Backend (key construction logic) | Redis enforces the boundary at rest; backend code must construct keys correctly |
| Audit logging | API / Backend (`AuditLog` write) | Database / Storage (`audit_logs` table) | Existing AUDIT-01 infra; AI calls are just new `action` values |
| Cost / budget enforcement | API / Backend (pre-call guard, `SUM` over audit_logs) | Database / Storage (`config` JSONB + `audit_logs`) | Fail-closed check must run before any Anthropic call is dispatched |
| Admin notification on budget breach | API / Backend (NOTIF-01 `create_notification`) | — | Reuses existing notification/email infra unmodified |
| RBAC gating | API / Backend (`require_analyst`/`require_viewer` deps) | — | Enforced at the FastAPI dependency layer, same as every other route |
| nginx SSE passthrough | API / Backend (network boundary) | — | Not a distinct tier in this stack, but a required unbuffered pass-through the backend's stream must cross unmodified |
| Feedback capture (thumbs/note) | Browser / Client (UI control) | API / Backend (`ai_feedback` upsert) | Low-stakes, non-billed action; simple round-trip |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` (Python) | `>=0.120.0` — **0.120.0 confirmed current, released 2026-07-24** `[VERIFIED: pypi.org/pypi/anthropic/json, checked 2026-07-28]` | Direct Anthropic SDK, no orchestration framework (AI-SPEC §2) | Single grounded call; framework abstraction buys nothing and hides the prompt boundary the injection defense depends on |
| `pydantic` | `>=2.9` already in `backend/pyproject.toml`; `2.13.4` is current on PyPI `[VERIFIED: pypi registry]` | Schema-validation gate (`ExplainVulnResponse` etc.) | Already the project's validation library everywhere; no new dependency |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `anthropic[aiohttp]` | same pin as core | Faster async I/O backend under concurrent analyst load | Optional — AI-SPEC flags this as worth adding once under real traffic; not required for Phase 24's initial ship |
| `deepeval` | `>=4.1.4` current on PyPI `[VERIFIED: pypi registry]` | Golden-set grounding/citation eval harness | **Phase 28 (AIE-01), not Phase 24** — see "Scoping DeepEval/promptfoo" below. Do not add to Phase 24's dependency list. |
| `promptfoo` (npm, global CLI) | `>=0.121.19` current on npm `[VERIFIED: registry.npmjs.org]` | Prompt-injection red-team CI job | **Phase 28 (AIE-02), not Phase 24** — same scoping note |

### Alternatives Considered

Already fully covered by AI-SPEC §2 ("Alternatives Considered" table: Anthropic SDK + Instructor, Claude Agent SDK, LangChain/LangGraph, all ruled out with rationale). No new alternatives surfaced by this research.

**Installation (Phase 24's actual new backend dependency):**
```bash
# Add to backend/pyproject.toml [project.dependencies] — the Docker build
# already runs `pip install -e ".[dev]"` (backend/Dockerfile), so this is
# the only change needed; no separate requirements.txt to sync.
"anthropic>=0.120.0",
```

No new frontend npm dependency is required — `fetch()` + `ReadableStream` are browser/Node built-ins, and the project already has React 19 + TanStack Query 5.100 for the surrounding state (see "Frontend SSE Consumption").

### Scoping DeepEval / promptfoo Out of Phase 24

`REQUIREMENTS.md`'s traceability table assigns **AIE-01 (DeepEval CI harness)** and **AIE-02 (promptfoo red-team CI job)** to **Phase 28**, not Phase 24. AI-SPEC §5 describes the full eval strategy (dimensions D1-D11, tooling, reference dataset) because that's the system-wide design contract — but "designed" is not "installed this phase." Phase 24 should:

- Write the **deterministic pytest-level checks** for dimensions D1, D3, D4, D9 (partial), D10, D11 — these are plain `pytest` assertions (schema validation, provenance substring-check, PII-field-allowlist, cross-tenant isolation) that need **no new tooling**, just the existing `pytest`/`pytest-asyncio` already in `backend/pyproject.toml`.
- **Not** install `deepeval` or `promptfoo` as part of this phase's CI gate — that installation, the golden-set construction, and the CI job wiring are Phase 28's explicit deliverable (AIE-01/02). Phase 24's pytest tests and fixture conventions become the foundation Phase 28 builds the full harness on top of.

This distinction matters for scope control: conflating "the eval strategy is designed in AI-SPEC §5" with "Phase 24 must stand up DeepEval CI" would silently pull Phase 28 scope forward.

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Browser (Next.js drill panel)                                               │
│                                                                               │
│  1. Drill panel opens                                                       │
│       │                                                                     │
│       ▼                                                                     │
│  2. GET /api/v1/ai/explain-{vuln|host|remediation}/{id}   (cheap, TanStack   │
│       │  query — no model call, checks Redis cache only)  useQuery)         │
│       ▼                                                                     │
│  ┌─── cache HIT ──────────────┐   ┌─── cache MISS ─────────────────────┐    │
│  │ render validated summary   │   │ show "Explain this vuln" button    │    │
│  │ + citations immediately    │   │ (role-gated: Viewer sees muted     │    │
│  └─────────────────────────────┘   │  text instead, D-17)               │    │
│                                     └──────────────┬──────────────────┘    │
│                                                     │ click                 │
│                                                     ▼                       │
│  3. POST /api/v1/ai/explain-{view}/{id}  (custom fetch()+ReadableStream    │
│       hook — NOT the generic api() helper, NOT EventSource — Bearer token   │
│       must ride the Authorization header)                                  │
│       │                                                                     │
└───────┼───────────────────────────────────────────────────────────────────┘
        │  nginx: location /api/v1/ai/ { proxy_buffering off; ... }
        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ FastAPI backend                                                            │
│                                                                             │
│  4. require_analyst dependency (RBAC gate, D-17)                          │
│  5. check_tenant_budget(tenant_id)  — fail-closed pre-call guard (D-06)    │
│       │  SUM(audit_logs.details->cost_estimate) this month vs. config cap  │
│       ▼ (pass)                                                             │
│  6. get_correlated_finding / get_asset_posture / get_remediation_group     │
│       │  (existing SQL joins — no RAG)                                    │
│       ▼                                                                   │
│  7. prompt_builder.build_explain_{view}_prompt(record)                    │
│       │  allowlist ONLY — strips PII (e.g. AssetDetail.directory_user)    │
│       │  JSON-encodes scanner data into a tagged <scanner_data> user block │
│       ▼                                                                   │
│  8. get_tenant_anthropic_key(tenant_id)  — Fernet-decrypt from             │
│       │  connector_configs row where connector_type='ANTHROPIC'           │
│       ▼                                                                   │
│  9. AsyncAnthropic(api_key=..., http_client=...).messages.stream(...)     │
│       │  buffer INSIDE backend — never proxied raw                        │
│       ▼                                                                   │
│ 10. await stream.get_final_message()                                     │
│       │                                                                   │
│       ▼                                                                   │
│ 11. ExplainResponse.model_validate_json(...)  ◄── THE GATE                │
│       │                                                                   │
│  ┌────┴────┐                                                              │
│  │ pass    │──► 12a. audit_log_ai_call(status="ok") + write Redis cache   │
│  │         │         (tenant_id, resource_type, resource_id, record_hash, │
│  │         │          model, prompt_version) → then replay via SSE       │
│  │ fail /  │──► 12b. retry ONCE with corrective turn (D-26, invisible)    │
│  │grounded=│         → still fails → audit_log_ai_call(status=...)       │
│  │ false   │         → typed error event, no partial text ever streamed  │
│  └─────────┘                                                              │
└───────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

Extends AI-SPEC §3's structure to honor D-15's three-view widening (AI-SPEC's original layout assumed one record type; see "Reconciling D-15" below for why this changed):

```
backend/
└── app/
    ├── ai/
    │   ├── tenant_keys.py       # get_tenant_anthropic_key() — Fernet decrypt via ConnectorConfig
    │   ├── budget.py            # check_tenant_budget() — SUM-over-audit_logs guard (D-06)
    │   ├── schemas.py           # ExplainResponseBase + ExplainVulnResponse/ExplainHostResponse/
    │   │                        # ExplainRemediationResponse (D-16 variants share a base)
    │   ├── prompt_builder.py    # build_explain_vuln_prompt / _host_prompt / _remediation_prompt
    │   │                        # — each with ITS OWN field allowlist (host view has PII risk
    │   │                        # the vuln view doesn't — see "PII Allowlist" below)
    │   ├── explain.py           # _run_explain_stream() shared buffer-validate-retry-audit core,
    │   │                        # called by 3 thin per-view wrappers (avoids triplicating control flow)
    │   ├── audit.py             # audit_log_ai_call(tenant_id, user_email, ...) — see "Scheduler
    │   │                        # Audit Pattern": takes tenant_id + user_email directly, NOT a
    │   │                        # CurrentUser, so "system:scheduler" and analyst calls are symmetric
    │   └── cache.py             # tenant-scoped, content-hash-keyed Redis cache via get_redis()
    └── api/v1/ai/
        ├── explain_vuln.py       # POST/GET /api/v1/ai/explain-vuln/{finding_id}
        ├── explain_host.py       # POST/GET /api/v1/ai/explain-host/{asset_id}
        ├── explain_remediation.py# POST/GET /api/v1/ai/explain-remediation/{id}
        └── feedback.py           # POST /api/v1/ai/feedback/{resource_type}/{resource_id}

frontend/src/
├── lib/ai/
│   └── use-explain-stream.ts    # NEW — the only genuinely new frontend hook shape (see below)
├── lib/queries/
│   └── use-explain-cache.ts     # cheap cache-check — ordinary useQuery, fits existing convention
└── components/vulnerabilities/
    └── drill-content.tsx        # add "AI Explanation" <section> per UI-SPEC placement (D-11)
```

### Pattern 1: ConnectorConfig Reuse (Resolves the "New AiConfig Table" Concern)

**What:** AI-01's per-tenant key + model + budget config is stored as an ordinary `ConnectorConfig` row with `connector_type="ANTHROPIC"` — **not** a new table.

**Why this is safe (verified by direct inspection, `[VERIFIED: backend/app/ticketing/models.py]`):**
- `ConnectorConfig.connector_type` is `Mapped[str] = mapped_column(String(30), nullable=False)` — a plain varchar, not a Postgres native enum. There is a stale `ConnectorType(str, enum.Enum)` in the same file with only 4 members (`CROWDSTRIKE`, `NESSUS`, `DEFENDER`, `WIZ`) — it is **not** the actual validation source of truth (confirmed: `ConnectorCreate.connector_type: str` in `connectors/schemas.py` has no `Literal`/enum constraint; the real gate is the `CONNECTOR_TYPES: dict[str, ConnectorTypeInfo]` dict, which already has 15 entries including types that enum never learned about, e.g. `GOOGLE_WORKSPACE`, `HUMAANS`). Adding `"ANTHROPIC"` is a **pure dict-entry + tester-function addition — zero Alembic migration.**
- `ConnectorConfig.config: Mapped[dict | None] = mapped_column(JSONB, default=dict)` already exists and is unstructured — `config={"model": "claude-sonnet-5", "monthly_budget_usd": 50}` fits with no schema change.
- `credentials_secret_arn` already stores a `json.dumps({field: encrypt_value(v)})` map (see `connectors/service.py::create_connector`) — `{"api_key": encrypt_value("sk-ant-...")}` is a drop-in fit.
- **This directly resolves the STATE.md-flagged concern**: *"Phase 24 needs a dedicated research/design pass on generalizing `rotate_credentials()` to sweep the new `AiConfig` table (currently hardcodes `ConnectorConfig`)."* There is no new `AiConfig` table under this design — `rotate_credentials()` (`backend/app/encryption.py`) already does `select(ConnectorConfig).where(ConnectorConfig.credentials_secret_arn.isnot(None))` with no `connector_type` filter, so the AI key is swept by the **existing, unmodified** rotation code path the moment it's saved as a `ConnectorConfig` row. **No code change to `encryption.py` is needed for this phase.**

**Concretely reused, verbatim, with no changes needed:**
| Existing function/component | File | Reused for |
|---|---|---|
| `create_connector`, `update_connector`, `list_connectors`, `delete_connector` | `backend/app/connectors/service.py` | AI key CRUD |
| `POST /api/v1/connectors`, `PATCH /{id}`, `GET`, `DELETE /{id}` | `backend/app/connectors/router.py` | AI key CRUD endpoints |
| `POST /api/v1/connectors/test` + `test_connector()` dispatcher | `backend/app/connectors/tester.py` | D-04's test-before-save (add one `test_anthropic()` function + one `TESTERS` dict entry) |
| `<AddConnectorWizard connectorType="ANTHROPIC" providerName="Anthropic" .../>` | `frontend/src/components/connectors/wizard/add-connector-wizard.tsx` | D-03's entire config UI — the component already derives `fields`/`permissions` from `useConnectorTypes()` and is generic over `connectorType`; **no new wizard code**, only a new `CONNECTOR_TYPES["ANTHROPIC"]` entry with `fields=[{name:"api_key", type:"password", required:true}]` plus a model-dropdown field |
| `useConnectorsList`, `useCreateConnector`, `useTestConnector` | `frontend/src/lib/queries/use-connectors-admin.ts` | Already generic over `connector_type` string — zero changes |

### Pattern 2: RBAC Dependency — Correcting AI-SPEC's Illustrative Code

**What:** AI-SPEC's Section 3 example route uses `tenant=Depends(current_tenant)`. **This dependency does not exist in the codebase** `[VERIFIED: grep across backend/app/auth/ and backend/app/tenants/router.py found no `current_tenant` definition]`. It was illustrative shorthand in AI-SPEC, not a literal reference to this codebase.

**The actual, real pattern** (used by every existing route, e.g. `backend/app/connectors/router.py`):
```python
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession  # Annotated[AsyncSession, Depends(get_db)]

@router.post("/explain-vuln/{finding_id}")
async def explain_vuln(
    finding_id: str,
    db: DBSession,
    user: CurrentUser = Depends(require_analyst),   # D-17: Analyst+ can trigger
):
    # user.tenant_id, user.email, user.id, user.role are all directly available —
    # no separate "tenant" lookup needed.
    ...

@router.get("/explain-vuln/{finding_id}")
async def get_cached_explanation(
    finding_id: str,
    db: DBSession,
    user: CurrentUser = Depends(require_viewer),   # D-17: Viewer can READ cached only
):
    ...
```
`CurrentUser` (`backend/app/auth/schemas.py`) is `{id, tenant_id, email, role, must_change_password}` — this **is** the correlate of AI-SPEC's imagined `tenant` object; `require_analyst`/`require_viewer` (`backend/app/auth/rbac.py`) are `RequireRole` instances already implementing the exact Owner(40) > Admin(30) > Analyst(20) > Viewer(10) hierarchy D-17 needs, with zero new code.

### Pattern 3: Key Test-Before-Save — the Free Validation Call

**What:** D-04 needs "a cheap validation call" for the wizard's test step. Anthropic's `count_tokens` endpoint is documented as genuinely free (no inference billed) and validates the key/model exactly like `messages.create` would `[CITED: platform.claude.com/docs/en/build-with-claude/token-counting, cross-verified via WebSearch summary of the same page, 2026-07-28]`.

```python
# backend/app/connectors/tester.py — new function, same shape as every
# existing tester (test_okta, test_jira, etc.)
async def test_anthropic(credentials: dict, config: dict) -> ConnectorTestResult:
    """Validate an Anthropic API key with a free count_tokens call — no
    inference is billed, unlike a real messages.create() call."""
    api_key = credentials.get("api_key", "")
    model = config.get("model", "claude-sonnet-5")
    if not api_key:
        return ConnectorTestResult(success=False, message="API key is required")
    try:
        from anthropic import AsyncAnthropic, AuthenticationError
        client = AsyncAnthropic(api_key=api_key)
        try:
            result = await client.messages.count_tokens(
                model=model,
                messages=[{"role": "user", "content": "test"}],
            )
            return ConnectorTestResult(
                success=True,
                message=f"Key validated for {model}",
                details={"input_tokens": result.input_tokens},
            )
        except AuthenticationError:
            return ConnectorTestResult(success=False, message="Invalid API key")
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")

# TESTERS dict addition:
TESTERS["ANTHROPIC"] = test_anthropic
```

**Open verification item (cannot be confirmed without a live key in this research session):** confirm `count_tokens` is scoped identically to `messages.create` for a restricted/scoped API key — in the unlikely event a tenant issues a narrowly-scoped key valid for counting but not generation, the test-before-save gate would false-positive. Flag as a defensive note, not a blocker (see Open Questions).

### Pattern 4: Redis Cache Key Convention

**What:** the only existing Redis read/write in this codebase today is the OIDC CSRF-state nonce (`backend/app/auth/router.py`): `redis_client.set(f"oidc:state:{state}", provider, ex=600, nx=True)` `[VERIFIED: grep]`. This confirms the project's one Redis-key convention — colon-delimited, category-prefixed — and confirms Phase 24's explanation cache is genuinely the **first real content cache** built on Redis in this codebase (everything before it is ephemeral auth/session state).

**Recommended key format**, extending AI-SPEC's `(tenant_id, correlation_record_hash, model, prompt_version)` with an explicit `resource_type` (needed once D-15 adds 3 view types, so a vuln ID and a remediation-group ID can never theoretically collide in the same namespace):

```
ai:explain:{tenant_id}:{resource_type}:{resource_id}:{record_hash}:{model}:{prompt_version}
```

**Access pattern:** via the existing `get_redis(request: Request) -> redis.Redis` dependency (`backend/app/redis_client.py`) — do not construct a separate Redis connection in `cache.py`; reuse the connection built once in `app.main.lifespan` and stored on `app.state.redis`.

### Pattern 5: Scheduler Audit Pattern — Resolving the `system:scheduler` Question

**What:** STATE.md flags: *"Phase 26 needs to confirm the scheduler's `user=None`/`system:scheduler` direct-`AuditLog`-construction precedent is the right long-term fix vs. a scheduler-wide `audit()` signature change."* This phase should settle that precedent now since AI-06 explicitly requires it here first.

**The trap** (`[VERIFIED: backend/app/audit.py]`): the shared `audit(db, user: CurrentUser | None, ...)` helper does `tenant_id=user.tenant_id if user else uuid.UUID(int=0)` — passing `user=None` for a scheduler call would silently stamp the **nil UUID** as tenant, which is exactly the "nil-tenant path" AI-06's requirement text warns against, and would make a tenant-billed AI call's audit row untraceable to its tenant.

**The existing, already-battle-tested fix** is `encryption.py::rotate_credentials()`'s pattern: bypass the `audit()` helper entirely and construct `AuditLog(...)` directly with an explicit `tenant_id` (never derived from a possibly-`None` user) and `user_email="system:cli"` as a plain string sentinel. This exact pattern is tested today: `backend/tests/test_encryption_rotation.py::test_audit_event` asserts `row.user_email == "system:cli"`.

**Recommendation — `audit_log_ai_call()` should take `tenant_id` and `user_email` as required, independent parameters (not a `CurrentUser | None`):**
```python
# backend/app/ai/audit.py
async def audit_log_ai_call(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,      # ALWAYS explicit — never derived from a nullable user
    user_email: str,           # analyst's email OR "system:scheduler" — symmetric, no branching
    model: str,
    usage: Any,                # Anthropic Usage object — input/output/cache tokens
    resource_type: str,
    resource_id: str,
    status: str,                # "ok" | "validation_failed" | "grounded_retry" | "budget_exceeded"
    cost_estimate_usd: float | None = None,
) -> None:
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=None,           # scheduler calls have no user row; interactive calls could add user.id
        user_email=user_email,
        action=f"ai.explain.{resource_type}",
        resource_type=resource_type,
        resource_id=resource_id,
        details={
            "model": model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_estimate_usd": cost_estimate_usd,
            "status": status,
        },
        created_at=datetime.now(UTC),
    )
    db.add(log)
```
This makes an interactive analyst call (`user_email=user.email`) and Phase 26's future scheduler-originated batch call (`user_email="system:scheduler"`) **the same function call shape** — no special-casing, no risk of ever hitting the nil-tenant branch, because `tenant_id` is a required parameter regardless of caller identity. **Test this the same way `test_encryption_rotation.py::test_audit_event` tests the `system:cli` case** — assert `row.user_email == "system:scheduler"` for a directly-invoked scheduler-shaped call, and `row.user_email == user.email` for an interactive one.

### Pattern 6: Frontend SSE Consumption — Why `fetch()` not `EventSource`, Concretely

**Grounding for AI-03's own stated choice:** this codebase's auth (`frontend/src/lib/api.ts`) stores the JWT in `localStorage` and sends it as `Authorization: Bearer <token>` on every request. Native browser `EventSource` **cannot set custom request headers** — it can only be pointed at a URL with credentials via cookies. Since this app has no cookie-based session, `EventSource` is structurally incompatible with its auth model; `fetch()` + manual `ReadableStream` reading is the only way to stream while still authenticating. This is a concrete, codebase-specific reason for a decision AI-SPEC only asserted.

**The existing generic `api()` helper (`frontend/src/lib/api.ts`) cannot be reused** — it unconditionally does `return res.json()`. A new, small, dedicated function/hook is needed:

```typescript
// frontend/src/lib/ai/use-explain-stream.ts — NEW, no existing precedent to reuse.
// Not modeled as useQuery/useMutation — neither fits a long-lived multi-event
// stream cleanly; a small dedicated hook with local state is the right shape,
// consistent with this codebase's existing "one hook, one concern" convention.

type ExplainStreamState =
  | { phase: 'idle' }
  | { phase: 'analyzing' }
  | { phase: 'done'; data: ExplainVulnResponse }
  | { phase: 'error'; kind: 'busy' | 'grounded_false' | 'budget_exceeded' | 'unknown' };

export function useExplainStream(resourceType: string, resourceId: string) {
  const [state, setState] = useState<ExplainStreamState>({ phase: 'idle' });

  const start = useCallback(async () => {
    setState({ phase: 'analyzing' });
    const token = localStorage.getItem('getvul_token') || 'dev-token';
    const res = await fetch(`${API_URL}/api/v1/ai/explain-${resourceType}/${resourceId}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok || !res.body) {
      setState({ phase: 'error', kind: 'unknown' });
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() ?? '';           // last (possibly partial) frame stays buffered
      for (const frame of frames) {
        const line = frame.split('\n').find((l) => l.startsWith('data: '));
        if (!line) continue;
        const evt = JSON.parse(line.slice(6));
        if (evt.type === 'done') setState({ phase: 'done', data: evt });
        else if (evt.type === 'error') setState({ phase: 'error', kind: evt.kind });
        // 'summary_delta' events (D-12's post-validation replay) can drive a
        // token-by-token text reveal here if the replay is chunked; prefers-
        // reduced-motion path (UI-SPEC) renders 'done' directly instead.
      }
    }
  }, [resourceType, resourceId]);

  return { state, start };
}
```

The **cache-check** (D-09's "auto-render if cached, else button") is a separate, ordinary `useQuery` — it fits the existing convention perfectly since it's a single fast GET, not a stream:
```typescript
// frontend/src/lib/queries/use-explain-cache.ts
export function useExplainCache(resourceType: string, resourceId: string) {
  return useQuery({
    queryKey: ['ai', 'explain', resourceType, resourceId],
    queryFn: ({ signal }) =>
      api<{ cached: false } | ({ cached: true } & ExplainVulnResponse)>(
        `/api/v1/ai/explain-${resourceType}/${resourceId}`, { signal }
      ),
    staleTime: 30_000,
    retry: 1,
  });
}
```

### Pattern 7: nginx Location Block

**Current state** (`[VERIFIED: nginx/nginx.conf]`): no `/api/v1/ai/` location exists; only a broad `location /api/ { proxy_pass http://backend/api/; limit_req zone=api burst=50 nodelay; ... }` in both the HTTP and HTTPS `server` blocks. `StreamingResponse` is already used elsewhere in the backend (`backend/app/main.py`, for PDF/CSV export) but **only as `StreamingResponse(iter([bytes]))`** — a one-shot buffered body, not a true incrementally-yielded generator. **True multi-chunk `text/event-stream` streaming is genuinely new to this codebase's backend.**

**Recommended addition** (nginx uses longest-prefix matching for plain `location` blocks, so a more specific `/api/v1/ai/` block correctly takes precedence over the existing `/api/` block regardless of file order — but place it adjacent for readability). Add to **both** the HTTP and HTTPS `server` blocks in `nginx/nginx.conf`:

```nginx
location /api/v1/ai/ {
    limit_req zone=api burst=50 nodelay;   # keep existing rate-limit zone
    proxy_pass http://backend/api/v1/ai/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;   # or "https" in the HTTPS block, matching existing convention
    proxy_buffering off;        # AI-03 — do not buffer the SSE body
    proxy_cache off;
    chunked_transfer_encoding on;
    proxy_read_timeout 90s;     # default 60s risks killing a slow buffer-then-validate call mid-stream
}
```
`docker-compose.yml` mounts `nginx.conf` read-only directly (`./nginx/nginx.conf:/etc/nginx/nginx.conf:ro`) — an nginx container restart (not rebuild) picks up this change.

**D-25's "light per-tenant in-flight concurrency guard" is an application-layer control, not an nginx one** — nginx's `limit_req` throttles request *rate*, not concurrent long-lived connections from one client; a queue-clicking analyst holding multiple simultaneous streams open is not prevented by `limit_req` alone, confirming D-25's app-layer guard is genuinely necessary (e.g. a Redis `SETNX` in-flight lock keyed `ai:inflight:{tenant_id}`, TTL'd to the request timeout, checked before dispatching each Anthropic call).

### Pattern 8: PII Allowlist — Concrete Field Lists Per View

AI-SPEC's Critical Failure Mode #3 ("prompt-builder lacks a strict field allowlist") is abstract; here are the actual field lists from this codebase's own response shapes.

**Per-vuln grounding record** — from `VulnerabilityDetail` (`frontend/src/lib/queries/use-vulnerability-detail.ts`, backing `GET /api/v1/vulnerabilities/{id}`) `[VERIFIED]` — **safe to allowlist in full, no PII present:**
```
cve_id, vulnerability_name, cvss_v3_score, cvss_v3_vector, severity, cisa_kev,
exploit_available, asset_hostname, source, affected_product, affected_version,
fixed_version, remediation_info, status, first_detected_at, last_seen_at
```
(`asset_id`, a UUID, should stay out of the prompt text itself — it's an internal identifier, not grounding content, and citing it would only invite the model to echo an opaque ID; keep it as external provenance metadata on the `Citation.source_field`, not prompt content.)

**Per-host grounding record** — from `AssetDetail` (`frontend/src/lib/queries/use-asset-detail.ts`, backing `GET /api/v1/assets/{id}`) `[VERIFIED]` — **contains real PII that must be excluded:**
```
directory_user: { email, display_name, department, job_title, avatar_url, groups, ... }  ← PII, EXCLUDE
assigned_user   ← owner name, PII-adjacent, EXCLUDE
managed_by      ← likely a person/team name, EXCLUDE unless confirmed non-PII
building        ← physical location, not grounding-relevant, EXCLUDE for minimality
serial_number   ← internal asset identifier, low grounding value, EXCLUDE for minimality
```
Safe to allowlist: `hostname, os_name, os_version, device_category, risk_score, vuln_counts (total/critical/high/medium/low/exploitable/kev/sla_breach), tags, sla_breach, last_checkin_at`. This is a **concrete, evidence-based finding AI-SPEC could not have produced** — it required reading the actual `AssetDetail` response shape, which bundles owner PII directly alongside grounding-relevant fields in one endpoint response. The per-host `prompt_builder` function must filter this at the object-construction boundary, not rely on "don't mention PII" prompt instructions (AI-SPEC's own §4b pitfall #5: never trust an instruction to suppress data that's structurally present in the input).

**Per-remediation grounding record — genuinely unresolved, flagged for plan-time design (see Open Questions and Assumptions Log).** The existing codebase concept closest to "remediation" is a `Ticket` row (`backend/app/ticketing/models.py`), which is **one ticket ↔ one `vulnerability_id`** (a single FK, not a list) scoped to one asset — this does not cleanly match D-16's framing of "what applying this one fix accomplishes across the affected assets," which implies grouping by CVE/fix **across multiple assets**, a query shape that doesn't exist today. Two candidate designs are presented in Open Questions; do not resolve this before the per-vuln path ships, per D-15's own explicit sequencing guidance.

### Reconciling D-15's Three-View Widening Against AI-SPEC's Original Layout

AI-SPEC §3's "Recommended Project Structure" lists a single `explain_vuln.py` — reasonable, since AI-SPEC was written to lock the single-record "minimum blast radius" design. `24-CONTEXT.md` (written after AI-SPEC, in the same phase's document sequence) explicitly and self-consciously widens this to three views (D-15), calling it out as "a real widening vs. the AI-SPEC's ... design." This is not a contradiction to resolve by picking one document over the other — it's a sequencing artifact: **AI-SPEC's core pattern (buffer-then-validate-then-replay, schema gate, allowlist prompt-builder, cache key shape, audit shape) is exactly right and should NOT be re-derived per view; only the grounding-record assembly and the Pydantic response schema vary per view.** The "Recommended Project Structure" in this document's Architecture Patterns section above reflects the reconciled layout: one shared `_run_explain_stream()` core (the part AI-SPEC locked), three thin per-view wrapper functions and three schema variants sharing a common base (the part D-15 legitimately widens).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-tenant encrypted credential storage | A new `AiConfig` table/model | Existing `ConnectorConfig` row with `connector_type="ANTHROPIC"` | Zero migration, inherits key rotation, CRUD, and RBAC-gating for free (see Pattern 1) |
| Add-connector UI flow (provider → credentials → test → confirm) | A new wizard/dialog for AI setup | `AddConnectorWizard` (`frontend/src/components/connectors/wizard/`) | Already generic over `connectorType`/`providerName`; Phase 19 built this exactly for this kind of reuse |
| API key validation | A custom "ping" endpoint call or a real (billed) `messages.create` | `client.messages.count_tokens()` | Documented as free — validates auth without spending on inference (Pattern 3) |
| Monthly spend tracking | A new counter table/column incremented per call | `SUM` aggregate query over existing `audit_logs.details->cost_estimate_usd` for the tenant, current month | Audit log is already the source of truth for cost/tokens (AI-06); avoids a second write path that could drift from the audit trail. Add one composite index (`audit_logs(tenant_id, created_at)`) for query performance — the only schema change this needs. |
| Admin alerting on budget breach | A new email-sending code path | `app.notifications.service.create_notification(..., send_email_flag=True)` (NOTIF-01), mirroring the existing pattern in `app/notifications/alerts.py`'s `_check_sla_breaches`/`_check_new_critical_vulns` | Identical shape already exists for "notify admins about something bad" — the only new code is *which* condition triggers it |
| Redis connection management in the new cache module | A new Redis client instantiation in `app/ai/cache.py` | `app.redis_client.get_redis(request)` dependency, reading `request.app.state.redis` | One pooled connection built once at app startup; avoids connection sprawl |
| HTTP mocking for Anthropic SDK tests | A new mocking library (`respx`, `pytest-httpx`) | `httpx.MockTransport` passed via `AsyncAnthropic(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))` | The SDK is httpx-based and accepts an `http_client` override `[VERIFIED via WebSearch of anthropic-sdk-python source/DeepWiki, 2026-07-28]`; this codebase already uses bare `httpx.MockTransport` everywhere (`test_okta_sync.py`, etc.) — no new test dependency needed |
| RBAC gating for the Explain endpoints | A new permission-check decorator | `Depends(require_analyst)` / `Depends(require_viewer)` (`app/auth/rbac.py`) | Exact Owner>Admin>Analyst>Viewer hierarchy D-17 needs already exists |
| Scheduler-originated audit attribution | A special-cased "system user" row in the `users` table, or a nullable-user branch in the shared `audit()` helper | Direct `AuditLog(...)` construction with explicit `tenant_id` + `user_email="system:scheduler"` string sentinel, mirroring `rotate_credentials()`'s proven `"system:cli"` pattern | Avoids the `audit()` helper's nil-tenant fallback entirely; already tested (`test_encryption_rotation.py::test_audit_event`) |

**Key insight:** almost everything Phase 24 needs at the *plumbing* layer (encrypted config, wizard UI, RBAC, audit, Redis access, admin alerting, HTTP test mocking) already exists in this codebase in a form generic enough to reuse without modification. The genuinely novel engineering is narrowly scoped to: the Anthropic SDK integration itself, true incremental SSE through nginx, and the frontend's manual stream-parsing hook. Recognizing this narrows where the phase's actual risk and effort should concentrate.

---

## Common Pitfalls

### Pitfall 1: `effort: "low"` May Not Be Supported on `claude-haiku-4-5`
**What goes wrong:** D-01 lets a tenant admin select Haiku as a model; AI-SPEC §4 hardcodes `output_config={"effort": "low", ...}` for every model choice. Anthropic's live `effort` parameter documentation (fetched 2026-07-28) lists supported models as *"Claude Fable 5, Claude Mythos 5, Claude Opus 5, Claude Opus 4.8, Claude Mythos Preview, Claude Opus 4.7, Claude Opus 4.6, Claude Sonnet 5, Claude Sonnet 4.6, and Claude Opus 4.5"* `[CITED: platform.claude.com/docs/en/build-with-claude/effort]` — **`claude-haiku-4-5` is not in this list.**
**Why it happens:** the effort parameter rolled out model-by-model; Haiku's smaller reasoning budget may make it a non-target for this particular lever, or support may simply be undocumented-but-present. This research could not determine which, without a live API key to smoke-test against.
**How to avoid:** before shipping the Haiku option, make one live test call with `model="claude-haiku-4-5"` + `output_config={"effort": "low"}` against a real (even a personal/dev) Anthropic key and confirm it succeeds. If it 400s, either omit the `effort` key conditionally when `model == "claude-haiku-4-5"`, or exclude Haiku from D-01's dropdown until confirmed.
**Warning signs:** a `400` from the Anthropic API specifically on Haiku-model calls in staging/production that doesn't reproduce on Sonnet/Opus.

### Pitfall 2: No True Incremental SSE Precedent in This Backend
**What goes wrong:** `StreamingResponse` already appears in `backend/app/main.py`, which could mislead someone into assuming "we already do SSE here" — but every existing usage is `StreamingResponse(iter([bytes]))`, a **one-shot buffered response** (used for PDF/CSV export), not a generator that yields multiple chunks across real wall-clock time while a client is actively reading. Multi-yield, long-lived `text/event-stream` responses are genuinely new; nginx buffering, uvicorn worker behavior under a held-open connection, and browser-side partial-chunk framing are all unproven in this specific deployment.
**Why it happens:** the existing `StreamingResponse` calls look identical at the type-signature level to what AI-03 needs, but behave completely differently at the semantics level (batch-write-then-close vs. genuinely incremental).
**How to avoid:** treat this as its own small, isolated spike task before building the full buffer-then-validate-then-replay logic on top — prove a minimal `text/event-stream` endpoint that yields 3-4 chunks with artificial delays reaches the browser incrementally (not all-at-once after the last chunk) through the full nginx → Docker → browser path, in both dev and a prod-build-like environment. This mirrors the project's own "Playwright + prod build + kill next-server children" quality-gate discipline already used for other integration-risk features (per project memory).
**Warning signs:** the "Analyzing…" state appears to hang for the full model-latency duration and then the ENTIRE explanation appears at once (indicating nginx or a proxy layer buffered the whole response despite `proxy_buffering off`) — the classic SSE-buffering symptom.

### Pitfall 3: The Generic `api()` Fetch Helper Silently Breaks the Streaming Endpoint
**What goes wrong:** `frontend/src/lib/api.ts`'s `api<T>()` helper unconditionally calls `res.json()` at the end. If a developer reflexively reuses it for the AI explain endpoint (as they would for every other endpoint in this codebase), it will either hang waiting for the stream to fully close before parsing, or throw a JSON-parse error on the first SSE frame.
**Why it happens:** `api()` is the established, load-bearing convention for every other endpoint in this app — the instinct to reuse it is exactly right everywhere else.
**How to avoid:** a dedicated hook (Pattern 6 above) that manually reads `res.body.getReader()`. Do not attempt to retrofit `api()` with a streaming mode; keep the streaming path clearly separate so future maintainers don't assume the general helper handles it.
**Warning signs:** the Explain button appears to do nothing until the full model response completes, then errors with a JSON parse exception.

### Pitfall 4: `audit()` Helper's Nil-Tenant Fallback
**What goes wrong:** calling the shared `audit(db, user=None, ...)` helper for a scheduler-originated or otherwise userless AI call silently stamps `tenant_id=uuid.UUID(int=0)` — a real, insertable UUID that looks like a legitimate row until someone tries to query "all AI audit rows for tenant X" and the scheduler-originated ones are invisible (or worse, all bucketed together under the nil tenant across every tenant).
**Why it happens:** `audit()`'s signature accepts `user: CurrentUser | None` and was designed around always having a real interactive user; it was never meant to be the audit path for background/system actions with an implicit but real tenant.
**How to avoid:** never call the shared `audit()` helper for AI calls. Use a dedicated `audit_log_ai_call()` (Pattern 5) that requires `tenant_id` as an explicit, non-optional parameter, mirroring `rotate_credentials()`'s direct `AuditLog(...)` construction.
**Warning signs:** a query for a tenant's AI audit history returns fewer rows than the tenant's Redis cache/spend data implies should exist.

### Pitfall 5: `AssetDetail`'s Bundled PII
**What goes wrong:** the existing `GET /api/v1/assets/{id}` endpoint (which the per-host prompt-builder will naturally want to call, since it's the existing grounding source) returns `directory_user: {email, display_name, department, job_title, ...}` directly inline. A prompt-builder written by copying the per-vuln allowlist pattern without re-auditing field-by-field for the host shape could accidentally allowlist the whole object or a careless subset that still leaks PII.
**Why it happens:** the endpoint's job (serve a UI detail page) legitimately needs owner PII for display; the AI prompt-builder's job (ground a business-risk explanation) does not, but both consume the same response shape.
**How to avoid:** the per-host `prompt_builder` function must construct its own narrow, explicitly-named allowlist object (see Pattern 8) — never pass the raw `AssetDetail`-shaped dict/row through even partially.
**Warning signs:** a code reviewer for the host-explain prompt-builder does NOT see an explicit line excluding `directory_user`/`assigned_user`/`managed_by`.

### Pitfall 6: Assuming the Stale `ConnectorType` Enum Needs Updating
**What goes wrong:** a developer sees `class ConnectorType(str, enum.Enum)` in `ticketing/models.py` and assumes it must have `ANTHROPIC` added to it, potentially triggering unnecessary "is this a Postgres enum, do I need `ALTER TYPE`" concern.
**Why it happens:** the enum's name and location (right above the `ConnectorConfig` model it seems to describe) strongly suggests it's load-bearing.
**How to avoid:** confirmed by direct inspection this enum is **not used as a Postgres column type** (the column is `String(30)`) and is not referenced by the connector CRUD/test dispatch code path — `CONNECTOR_TYPES` (a dict in `connectors/schemas.py`) is the real source of truth. No enum update is required; if updating it anyway for documentation/consistency, it's a pure Python change with no migration.
**Warning signs:** a plan task titled "add ANTHROPIC to the connector_type Postgres enum" or "write an `ALTER TYPE` migration" — this indicates the misunderstanding; there is no such migration to write.

---

## Code Examples

### Testing the Anthropic Client with the Existing `httpx.MockTransport` Convention

```python
# backend/tests/test_ai_explain.py — mirrors the existing style of
# backend/tests/test_okta_sync.py's httpx.MockTransport usage.
import httpx
import pytest
from anthropic import AsyncAnthropic

SSE_BODY = (
    b'event: message_start\n'
    b'data: {"type":"message_start","message":{"id":"msg_1","type":"message","role":"assistant","content":[],'
    b'"model":"claude-sonnet-5","usage":{"input_tokens":50,"output_tokens":0}}}\n\n'
    b'event: content_block_start\n'
    b'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n'
    b'event: content_block_delta\n'
    b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta",'
    b'"text":"{\\"summary\\":\\"...\\",\\"business_risk\\":\\"...\\",\\"citations\\":[],\\"grounded\\":true}"}}\n\n'
    b'event: content_block_stop\n'
    b'data: {"type":"content_block_stop","index":0}\n\n'
    b'event: message_delta\n'
    b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":40}}\n\n'
    b'event: message_stop\n'
    b'data: {"type":"message_stop"}\n\n'
)

@pytest.mark.asyncio
async def test_explain_vuln_stream_validates_and_audits(db_session, tenant_a):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=SSE_BODY, headers={"content-type": "text/event-stream"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncAnthropic(api_key="test-key", http_client=mock_client)
    # ... pass `client` into explain_vuln_stream() via dependency injection or
    # monkeypatch — assert the yielded SSE frames only appear AFTER the
    # buffered message validates, and that an AuditLog row lands with
    # status="ok" and the correct tenant_id.
```

For pure schema/property tests that don't need a real SSE wire-format fixture, mock at the SDK boundary instead (faster, simpler — reserve the MockTransport fixture above for one true wire-format integration test):
```python
from unittest.mock import AsyncMock, patch

@patch("app.ai.explain.AsyncAnthropic")
async def test_grounded_false_triggers_invisible_retry(mock_anthropic_cls, ...):
    ...
```

### `check_tenant_budget()` — Deriving Spend from the Audit Log

```python
# backend/app/ai/budget.py
from sqlalchemy import func, select
from app.audit import AuditLog

async def check_tenant_budget(db: AsyncSession, tenant_id: uuid.UUID, monthly_cap_usd: float) -> bool:
    """Fail-closed pre-call guard (D-06). Returns True if under budget."""
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = (
        await db.execute(
            select(func.sum(AuditLog.details["cost_estimate_usd"].as_float()))
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.action.like("ai.%"),
                AuditLog.created_at >= month_start,
            )
        )
    ).scalar_one_or_none() or 0.0
    return spent < monthly_cap_usd
```
Add a supporting migration: `CREATE INDEX ix_audit_logs_tenant_created ON audit_logs (tenant_id, created_at);` — the only new index this phase needs for budget tracking.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `output_format` param + `structured-outputs-2025-11-13` beta header | `output_config.format` (GA, no beta header) | Documented as a completed transition as of the 2026-07-28 doc fetch; old form "continues working for a transition period" | AI-SPEC already correctly uses the GA form — no action needed, just confirms currency |
| Manually retrying/prompting for JSON-shaped output via `tool_choice` forcing | Native `output_config.format: {"type": "json_schema", ...}` structured outputs | GA on Claude 4.5+ models | AI-SPEC already made this call correctly (§4 "Tool Use" section explicitly notes this supersedes the old tool-forcing hack) |
| Fixed high-effort-only reasoning | Tunable `effort` dial (`low`→`xhigh`→`max`) on Claude 4.5+/4.6+ models, GA | Current as of July 2026 | Confirmed real and combinable with `output_config.format` in the same request object — but **not confirmed present on `claude-haiku-4-5`** (see Pitfall 1) |

**Deprecated/outdated:** nothing in this phase's design is using a deprecated pattern — both this research's live-doc fetches and AI-SPEC's own citations agree the design targets current, GA, non-beta surfaces.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Per-remediation grounding groups by CVE/fix **across multiple assets** (a new aggregate query) rather than reusing the existing per-asset `Ticket` row | Pattern 8 / Open Questions | If the planner instead builds around the existing `Ticket` shape without confirming against D-16's "across the affected assets" framing, the shipped feature may not match the product intent; conversely, over-building a new cross-asset aggregation query when a simpler per-ticket view was intended wastes effort. Explicitly flagged as unresolved, matching CONTEXT.md's own "Claude's Discretion" note. |
| A2 | `count_tokens()` validates a key with equivalent auth scope to `messages.create()` for every realistic tenant key configuration | Pattern 3 | If a tenant issues a narrowly-scoped key (e.g., counting-only) that passes the test-before-save gate but then fails on the real explain call, an admin would see a false "key validated" success followed by a confusing runtime failure. Low likelihood (Anthropic API keys are not typically scoped this granularly today) but not verified with a live key in this session. |
| A3 | `ai_feedback` should include a `prompt_version` column tying a feedback row to the specific explanation version it rates | Pattern (schema sketch, "Don't Hand-Roll"/D-21 area) | Not explicitly required by CONTEXT.md D-21/D-22. If omitted, Phase 28's flywheel work loses the ability to distinguish "this thumbs-down was about an old prompt version already superseded" from a live quality signal — low risk either way, flagged as a recommendation not a requirement. |
| A4 | Feedback submission (`POST /api/v1/ai/feedback/...`) should be gated at `require_viewer` (any authenticated role) rather than `require_analyst` | Pattern 6 / endpoint list | CONTEXT.md D-17 only explicitly gates the paid Explain *trigger*, not feedback capture (which is free/non-billed). If the intent was actually to restrict feedback to Analyst+, a Viewer-accessible feedback endpoint would be a minor scope deviation — low stakes since feedback is capture-only with no UI surfacing this phase (D-21). |
| A5 | The `ai:explain:{tenant_id}:{resource_type}:{resource_id}:{record_hash}:{model}:{prompt_version}` Redis key format (adding `resource_type` to AI-SPEC's original 4-part key) is the right extension for D-15's 3-view widening | Pattern 4 | If the planner instead keeps AI-SPEC's original 4-part key and relies on `resource_id` alone being globally unique across vulnerabilities/assets/remediation-groups (plausible if all three are UUIDs from disjoint tables, which they are), the extra `resource_type` segment is redundant-but-harmless insurance, not a correctness requirement. |

---

## Open Questions

1. **Does `effort: "low"` work on `claude-haiku-4-5`?**
   - What we know: official Anthropic docs (fetched live, 2026-07-28) list effort-supporting models and do not include Haiku 4.5.
   - What's unclear: whether this means "unsupported (will error)" or "just not the primary documented use case (may silently work or silently no-op)." No live API key was available in this research session to test directly.
   - Recommendation: run one live smoke-test call against a real Anthropic key with `model="claude-haiku-4-5"` + `output_config={"effort":"low", "format": {...}}` before finalizing the Haiku option in D-01's dropdown. If it errors, branch the request builder to omit `effort` for Haiku specifically.
   - **[PLANNING RESOLVED]** Plan 24-01 Task 1 runs this exact live smoke-test and records the result; Plan 24-04 Task 1's request builder honors the finding (omit `effort` for Haiku if it 400s).

2. **What is the correct grounding shape for "per-remediation" (D-16)?**
   - What we know: the existing "remediation" concept in this codebase (`/assets/[id]` remediation timeline, `RemediationTicket`) is a per-asset `Ticket` row with a single `vulnerability_id` FK — not a multi-asset aggregate.
   - What's unclear: D-16 explicitly frames per-remediation as "what applying this one fix accomplishes **across the affected assets**" — implying a cross-asset grouping (e.g., by CVE ID) that has no existing query today.
   - Recommendation: two candidate designs, either viable — (a) group by CVE ID across all of a tenant's affected assets (new aggregate query, more faithful to D-16's literal framing, more implementation cost); (b) ground on the existing per-asset `Ticket`/`RemediationTicket` shape and interpret "across the affected assets" more loosely as "this fix as scoped to the ticket's actual blast radius" (reuses existing data, less faithful to a literal multi-asset reading). Per D-15's explicit sequencing guidance, resolve this only after the per-vuln path ships — don't let it block Wave 0.
   - **[PLANNING RESOLVED]** Plan 24-06 Task 2 is a `checkpoint:decision` presenting exactly these two options (cross-asset-cve vs per-ticket-blast-radius) after the tracer ships; Plan 24-08 implements the recorded choice.

3. **Should the AI connector's model dropdown and monthly budget cap live inside `ConnectorConfig.config` JSONB, or does the planner prefer a typed sub-schema for stronger validation?**
   - What we know: the JSONB column already exists and needs no migration; other connectors already store loosely-typed config there (e.g., `base_url`, `verify_tls`).
   - What's unclear: whether the team wants a stricter Pydantic sub-model validating `config` shape specifically for the AI connector type (other connector types don't do this today — `config: dict[str, Any]` is uniformly loose).
   - Recommendation: match the existing convention (loose JSONB, validated ad hoc by the specific tester/service function that reads it) rather than introducing a new validation pattern only for this one connector type — consistency with 15 existing connector types outweighs marginal type-safety gain here.
   - **[PLANNING RESOLVED]** Adopted the loose-JSONB convention: model + monthly_budget_usd live in `ConnectorConfig.config` (Plan 24-01 fields; Plan 24-03 reads them), no typed sub-schema.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build/test | ✓ | v26.5.0 | — |
| Python 3.12 (via pyenv) | Backend | ✓ | 3.12.7 (project-pinned; local shell default resolved 3.14.6 but `backend/pyproject.toml` requires `>=3.12` and Docker image pins `python:3.12-slim`) | Use the Docker image or a pyenv-selected 3.12.x for parity with CI |
| Docker | Local full-stack run (Postgres/Redis/nginx) | ✓ | 29.6.2 (client) | — |
| Postgres (containerized) | All persistence | Not running at research time (`docker compose ps` empty) | — | `docker compose up -d` brings it up; not a blocker, just not live during this research session |
| Redis (containerized) | Cache, session/OIDC state, new AI explanation cache | Not running at research time | image pin: `redis:7-alpine` (both `docker-compose.yml` and `docker-compose.ci.yml`) | Same — `docker compose up -d` |
| `anthropic` (PyPI) | AI-01 through AI-06 | ✗ (not yet a dependency) | Latest: `0.120.0`, released 2026-07-24 `[VERIFIED: pypi registry]` | Add to `backend/pyproject.toml`; no fallback needed, this is the phase's core new dependency |
| Outbound HTTPS to `api.anthropic.com` | All live Anthropic calls | ✓ — confirmed reachable (`curl` returned `401` — DNS/TLS/HTTP all functioning, just no key in this sandbox) `[VERIFIED: curl from this environment, 2026-07-28]` | — | — |
| `deepeval` / `promptfoo` | AIE-01/AIE-02 (Phase 28, not this phase) | ✗ | `deepeval 4.1.4`, `promptfoo 0.121.19` current `[VERIFIED: registries]` | Not needed this phase — see "Scoping DeepEval/promptfoo Out of Phase 24" |

**Missing dependencies with no fallback:** none — `anthropic` is a standard `pip install`/Docker-rebuild addition with no blocking constraint found.

**Missing dependencies with fallback:** Postgres/Redis containers simply need `docker compose up -d` before implementation/testing begins; this is normal pre-work, not a phase risk.

---

## Validation Architecture

Backend test framework: **pytest** (`pytest>=8.3`, `pytest-asyncio>=0.24`, `asyncio_mode=auto`, `testpaths=["tests"]` — `backend/pyproject.toml`). Frontend: **Vitest** (`^4.1.6`) for unit/component tests, **Playwright** (`^1.61.1`) for e2e.

**Known backend test-env requirement** (from prior-session project memory — apply to every new AI test file): set `ENCRYPTION_KEY` and `JWT_SECRET_KEY` env vars before running, and run new test files individually rather than the whole `tests/` directory in one invocation, since a known pre-existing harness quirk produces false failures when the full directory is collected together.

**Existing fixtures directly reusable for every AI-01..AI-06 test** (`[VERIFIED: backend/tests/conftest.py]`) — this is a significant de-risking finding: almost no new test plumbing is needed.

| Fixture | Use for |
|---|---|
| `tenant_a`, `tenant_b` | AI-05's cross-tenant cache-isolation test — two real, distinct tenants already provisioned |
| `analyst_user`, `viewer_user`, `admin_user` (all in `tenant_a`) | D-17's RBAC gate tests (Analyst can trigger, Viewer cannot) |
| `analyst_user_b` (in `tenant_b`) | The cross-tenant test's second identity |
| `flushed_redis` | AI-05's cache tests — Redis is flushed between tests, a real integration test (not mocked) is the existing convention |
| `client`, `client_factory` | Authenticated `AsyncClient` fixtures already wired to a specific user/tenant — reuse directly for the new `/api/v1/ai/*` routes |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AI-01 | AI key saves as encrypted `ConnectorConfig` row, connector inert until keyed | integration | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest tests/test_ai_connector.py -x -q` | ❌ Wave 0 |
| AI-01 | Test-before-save (`test_anthropic`) succeeds/fails correctly against a mocked key | unit | `pytest tests/test_connectors/test_ai_tester.py -x -q` | ❌ Wave 0 |
| AI-01 | AI connector card renders + wizard completes for `connectorType="ANTHROPIC"` | component | `npm test -- add-connector-wizard` (extend existing `add-connector-wizard.test.tsx` with a data-driven ANTHROPIC case) | ✅ existing file, extend |
| AI-02 | `build_explain_vuln_prompt()` never includes a non-allowlisted field, for any DB row shape | unit (property-style) | `pytest tests/test_ai_prompt_builder.py -x -q` | ❌ Wave 0 |
| AI-02 | `ExplainVulnResponse.model_validate_json()` rejects malformed/missing-citation/bad-enum JSON | unit | `pytest tests/test_ai_schemas.py -x -q` | ❌ Wave 0 |
| AI-02 | Prompt-injection structural defense: adversarial text embedded in a scanner field never reaches `system`, always lands inside the tagged `<scanner_data>` user block | unit | `pytest tests/test_ai_prompt_builder.py::test_injection_isolation -x -q` | ❌ Wave 0 (full promptfoo red-team suite is Phase 28/AIE-02, not this phase) |
| AI-03 | SSE endpoint returns `text/event-stream`, correct headers, correct frame sequence against a mocked Anthropic stream | integration | `pytest tests/test_ai_explain_stream.py -x -q` | ❌ Wave 0 |
| AI-03 | nginx does not buffer the response (first byte arrives before stream completes) | manual / smoke (justified manual-only — see below) | manual `curl -N` against the running Docker Compose stack, or a timing-based Playwright assertion | ❌ Wave 0 (manual verification step) |
| AI-04 | Two-tier citation rendering: `scanner_verbatim` gets tinted span, `ai_interpreted` gets superscript tag | component | `npm test -- ai-explanation-citations` | ❌ Wave 0 |
| AI-04 | Grounding/citation/calibration dimensions (D2-D8 from AI-SPEC §5) | DeepEval golden-set | **Phase 28 (AIE-01)** — Phase 24 does not install/run DeepEval; it produces the schema/fixtures Phase 28 consumes | N/A this phase |
| AI-05 | Same finding + same record hash + different tenant → no cross-tenant cache read | integration (real Redis via `flushed_redis`) | `pytest tests/test_ai_cache_isolation.py -x -q` | ❌ Wave 0 |
| AI-06 | `audit_log_ai_call()` writes correct row for an interactive analyst call | unit | `pytest tests/test_ai_audit.py::test_interactive_audit -x -q` | ❌ Wave 0 |
| AI-06 | `audit_log_ai_call()` writes correct row with `user_email="system:scheduler"` for a system-originated call, avoiding the nil-tenant path | unit | `pytest tests/test_ai_audit.py::test_scheduler_audit -x -q` (model directly on `test_encryption_rotation.py::test_audit_event`'s existing shape) | ❌ Wave 0 |
| D-06 | Fail-closed budget check blocks a call when monthly spend (summed from `audit_logs`) exceeds `config.monthly_budget_usd` | unit | `pytest tests/test_ai_budget.py -x -q` | ❌ Wave 0 |
| D-08 | Budget breach triggers an admin notification via existing NOTIF-01 path | integration | `pytest tests/test_ai_budget.py::test_admin_notified_on_breach -x -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the single new/changed test file, run individually (per the known harness quirk) — e.g. `pytest tests/test_ai_schemas.py -x -q`
- **Per wave merge:** full new `tests/test_ai_*.py` set together, plus a targeted rerun of `test_encryption_rotation.py` (since Pattern 5's audit change touches shared conventions) and `test_connectors/` (since Pattern 1 extends shared connector infra)
- **Phase gate:** full backend `pytest` suite (per-file if the directory-collection quirk still reproduces) + full frontend `npm test` + the manual SSE-buffering smoke check, green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_ai_connector.py` — AI-01 connector CRUD + inert-until-keyed state
- [ ] `backend/tests/test_connectors/test_ai_tester.py` — `test_anthropic()` success/failure via `httpx.MockTransport`
- [ ] `backend/tests/test_ai_prompt_builder.py` — allowlist enforcement + injection-isolation structural test (AI-02)
- [ ] `backend/tests/test_ai_schemas.py` — Pydantic schema-validation gate (AI-02)
- [ ] `backend/tests/test_ai_explain_stream.py` — SSE framing + buffer-then-validate-then-replay, mocked Anthropic client (AI-03)
- [ ] `backend/tests/test_ai_cache_isolation.py` — cross-tenant Redis isolation, real `flushed_redis` (AI-05)
- [ ] `backend/tests/test_ai_audit.py` — interactive + `system:scheduler` audit row shapes (AI-06)
- [ ] `backend/tests/test_ai_budget.py` — fail-closed budget guard + admin notification (D-06/D-08)
- [ ] `frontend/src/lib/ai/use-explain-stream.test.ts` — SSE-parsing hook state machine (idle → analyzing → done/error)
- [ ] Extend `frontend/src/components/connectors/wizard/add-connector-wizard.test.tsx` with an `ANTHROPIC` connector-type case
- [ ] Framework install: none — `pytest`/`pytest-asyncio`/`vitest`/`@playwright/test` are all already present; only the `anthropic` production dependency needs adding

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No (unchanged) | Existing JWT bearer auth reused as-is |
| V3 Session Management | No (unchanged) | — |
| V4 Access Control | Yes | `Depends(require_analyst)` / `Depends(require_viewer)` (`app/auth/rbac.py`) — D-17's role gate on every new route |
| V5 Input Validation | Yes | Pydantic (`ExplainVulnResponse` + variants) validates **model output**, not just request input — an unusual but correct application of V5 to an LLM boundary; prompt-builder field allowlist validates what enters the model |
| V6 Cryptography | Yes | Existing Fernet (`app/encryption.py`) — reused verbatim, never hand-rolled, for the BYOK key at rest |
| V7 Error Handling & Logging | Yes | Every AI call (success or failure) writes an audit row unconditionally (AI-06) — matches this project's existing AUDIT-01 fail-closed convention (`app/audit.py`'s own docstring: "a mutation does not succeed without its audit row landing") |
| V13 API and Web Service | Yes | The new SSE endpoint is a genuinely new API surface shape (long-lived streaming response) — ensure standard rate-limiting (`limit_req`) still applies, plus the new app-layer in-flight concurrency guard (D-25) |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Prompt injection via scanner-sourced text (CVE description, hostname, finding title) | Tampering / Elevation of Privilege | Untrusted-content-as-data contract — JSON-encoded, tagged `<scanner_data>` block, never in `system`, backstopped by the schema-validation gate (AI-SPEC §4b, already locked) |
| Cross-tenant cache/audit bleed | Information Disclosure | Redis key always includes `tenant_id` as the first segment; `audit_log_ai_call()` always takes an explicit `tenant_id`, never derived from a nullable/ambiguous source (Pattern 5) |
| PII leakage into the model prompt or output | Information Disclosure | Per-view field allowlist enforced at object-construction time in `prompt_builder.py`, not by prompt instruction alone (Pattern 8; concrete `AssetDetail.directory_user` exclusion) |
| Unvalidated/partial LLM output reaching the UI | Tampering | Buffer-then-validate-then-replay — the Anthropic stream is fully consumed and Pydantic-validated server-side before any byte is emitted to the browser (AI-SPEC §4, already locked) |
| Fernet key material exposure in logs/audit | Information Disclosure | Existing convention already redacts key material from CLI/audit output (`encryption.py::_print_rotation_failure` prints no key values) — apply the same discipline to any new AI-key-related logging |
| Budget/DoS via a queue-clicking analyst holding many concurrent streams | Denial of Service (cost) | App-layer in-flight concurrency guard (D-25) + fail-closed monthly budget check (D-06) — nginx `limit_req` alone is insufficient (Pattern 7) |

---

## Sources

### Primary (HIGH confidence)
- `platform.claude.com/docs/en/build-with-claude/structured-outputs` — fetched live 2026-07-28; confirmed `output_config.format` GA syntax, constraint-stripping behavior, no-beta-header status
- `platform.claude.com/docs/en/build-with-claude/effort` — fetched live 2026-07-28; confirmed `output_config.effort` GA syntax, per-model support table (Haiku 4.5 notably absent — Pitfall 1)
- `platform.claude.com/docs/en/docs/build-with-claude/streaming` — fetched live 2026-07-28; confirmed `client.messages.stream()` context-manager shape, `get_final_message()`, SSE event-type sequence (`message_start`/`content_block_start`/`content_block_delta`/`content_block_stop`/`message_delta`/`message_stop`)
- `pypi.org/pypi/anthropic/json` — confirmed `anthropic` 0.120.0, released 2026-07-24
- `pypi.org/pypi/{pydantic,deepeval}/json`, `registry.npmjs.org/promptfoo/latest` — confirmed current versions
- Direct file reads: `backend/app/encryption.py`, `backend/app/audit.py`, `backend/app/ticketing/models.py`, `backend/app/connectors/{schemas,service,tester,router}.py`, `backend/app/auth/{rbac,dependencies,schemas}.py`, `backend/app/redis_client.py`, `backend/app/config.py`, `backend/app/notifications/{service,alerts}.py`, `backend/tests/conftest.py`, `backend/tests/test_encryption_rotation.py`, `backend/tests/test_okta_sync.py`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries/{keys,use-connectors-admin,use-vulnerability-detail,use-asset-detail,use-asset-remediations}.ts`, `frontend/src/components/connectors/wizard/add-connector-wizard.tsx`, `frontend/src/components/vulnerabilities/drill-content.tsx`, `nginx/nginx.conf`, `docker-compose.yml`, `backend/Dockerfile`, `backend/pyproject.toml`, `frontend/package.json`

### Secondary (MEDIUM confidence)
- WebSearch summary confirming `AsyncAnthropic(http_client=...)` override support (cross-referenced against `anthropic-sdk-python` GitHub source + DeepWiki, not fetched directly)
- WebSearch summary confirming `claude-sonnet-5`/`claude-opus-5`/`claude-haiku-4-5` as current GA model IDs, cross-verified against anthropic.com/news announcement pages
- WebSearch summary on `count_tokens()` being a free, non-billed endpoint suitable for key validation

### Tertiary (LOW confidence)
- None retained — every WebSearch finding used in this document was either directly fetched from an official doc page or cross-verified against a second independent source before being stated as fact.

---

## Metadata

**Confidence breakdown:**
- Standard stack (SDK version, model IDs, structured-outputs/effort API shape): HIGH — independently re-verified against live official docs and package registries on the research date, not solely inherited from AI-SPEC
- Architecture (ConnectorConfig reuse, RBAC pattern, audit pattern, Redis pattern, nginx pattern, frontend SSE pattern): HIGH — every claim traced to a specific file read in this session
- Pitfalls: HIGH for the codebase-grounded ones (stale enum, nil-tenant audit trap, `api()` helper mismatch, PII bundling); MEDIUM for the `effort`-on-Haiku pitfall (documented absence is strong but not a live-tested confirmation of failure)
- Per-remediation grounding shape (D-16): LOW / explicitly unresolved — flagged as an open question and assumption, consistent with CONTEXT.md's own designation of this as discretionary

**Research date:** 2026-07-28
**Valid until:** ~14 days for the Anthropic-API-specific claims (model IDs, `effort` support table, pricing) — this is a fast-moving surface with introductory pricing already noted to expire 2026-08-31 per AI-SPEC; ~30 days for the codebase-grounded architecture findings (stable unless the referenced files change first)
