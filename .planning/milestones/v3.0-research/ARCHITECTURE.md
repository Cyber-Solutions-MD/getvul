# Architecture Research: v3.0 AI-Assisted Triage — LLM Layer Integration

**Domain:** LLM assistance layer integration into an existing multi-tenant FastAPI + Next.js vulnerability-triage platform
**Researched:** 2026-07-25
**Confidence:** HIGH for integration points (read directly from `backend/app/**`, `frontend/src/**`, `nginx/nginx.conf`) · MEDIUM for Anthropic SDK streaming specifics (WebSearch-verified against current docs, not Context7-resolved)

This is an **integration** research file, not a from-scratch domain survey. GetVul's existing architecture (scheduler, `ConnectorConfig`/Fernet encryption, `audit()`, `DrillPanel`, tenant-scoped Postgres, Redis) is treated as fixed. Every recommendation below says explicitly what's **new** vs. what's **reused unmodified**.

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js 15 / React 19)                     │
│  ┌────────────────┐   ┌─────────────────────┐   ┌────────────────────────┐  │
│  │ DrillPanel      │   │ AI panel section     │   │ /settings → AI pane    │  │
│  │ (existing,      │──▶│ (NEW — additive to   │   │ (NEW — model picker,   │  │
│  │  drill-content) │   │  drill-content.tsx)   │   │  masked API key,       │  │
│  │                 │   │ useVulnAIExplain()   │   │  usage/budget)         │  │
│  └────────────────┘   │ fetch()+ReadableStream│   └────────────────────────┘  │
│                        └─────────┬────────────┘                              │
├──────────────────────────────────┼────────────────────────────────────────────┤
│                          nginx (reverse proxy)                                │
│  location /api/v1/ai/ { proxy_buffering off; gzip off; }  ← NEW, scoped block │
├───────────────────────────────────┼───────────────────────────────────────────┤
│                         FASTAPI (async request path)                         │
│  Existing routers (vuln/asset/tenant/connector/cspm/user/ticket/notif) …     │
│  ┌───────────────────────────────▼──────────────────────────────────────┐    │
│  │  app/ai/router.py  (NEW)  — /api/v1/ai/*                             │    │
│  │  Depends(get_current_user)  ← same RBAC/tenant dependency, unchanged │    │
│  └───────────────────────────────┬──────────────────────────────────────┘    │
│  ┌───────────────────────────────▼──────────────────────────────────────┐    │
│  │  app/ai/service.py (NEW) — orchestrates:                             │    │
│  │  grounding.py → cache.py → client.py → guardrails.py → costs.py      │    │
│  │                            → app/audit.py (existing, reused as-is)   │    │
│  └───────┬──────────────────┬───────────────┬──────────────┬────────────┘    │
├──────────┼──────────────────┼───────────────┼──────────────┼─────────────────┤
│  Vulnerability/Asset/        │        Redis (existing)      │  Anthropic API │
│  Misconfiguration/           │  ai:cache:{tenant}:{hash}    │  (external,     │
│  Correlation/SLA/Ticket      │  ai:usage:{tenant}:{yyyy-mm} │  AsyncAnthropic)│
│  tables (existing, read-only│  (reuses the Redis client    │                 │
│  grounding source)           │   already on app.state.redis)│                 │
├───────────────────────────────┼───────────────────────────────────────────────┤
│  Postgres (NEW tables)        │  connectors/scheduler.py (existing 60s loop)  │
│  ai_configs, ai_usage,        │  + NEW tick: batch triage pre-warm, budget    │
│  ai_eval_runs                 │    reconciliation — asyncio.create_task,      │
│  (audit_logs reused as-is)    │    same pattern as trigger_background_sync    │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | New / Modified / Reused |
|-----------|-----------------|--------------------------|
| `app/ai/router.py` | FastAPI endpoints: explain, remediate, triage (batch + single), ticket-draft | **New** |
| `app/ai/service.py` | Orchestrates grounding → cache → model call → guardrails → cost/audit for a single request | **New** |
| `app/ai/grounding.py` | Tenant-scoped SQL assembly of context from `Vulnerability`/`Asset`/`Misconfiguration`/`VulnerabilityCorrelation`/SLA fields | **New** |
| `app/ai/client.py` | `AsyncAnthropic` wrapper; resolves per-tenant model + decrypted API key; per-capability model routing (Haiku/Sonnet/Opus) | **New** |
| `app/ai/cache.py` | Redis get/set keyed by tenant + content hash | **New** |
| `app/ai/guardrails.py` | Prompt-injection defense (delimit untrusted scanner text), output validation ("no hallucinated remediation" — cross-check cited facts against grounding), PII scrub | **New** |
| `app/ai/costs.py` | Per-model token pricing table, cost computation, Redis budget pre-check + Postgres ledger write | **New** |
| `app/ai/models.py` | `AiConfig`, `AiUsage`, `AiEvalRun`/`AiEvalResult` SQLAlchemy models | **New** |
| `app/ai/prompts.py` | Versioned prompt templates per capability (explain/remediate/triage/draft) | **New** |
| `app/audit.py` | Records every AI call (prompt provenance, model, tokens, cost) via existing `audit()` / direct-`AuditLog` pattern | **Reused unmodified** |
| `app/encryption.py` | Encrypt/decrypt tenant Anthropic API keys with the same Fernet helpers connector credentials use | **Reused; `rotate_credentials()` extended to sweep `ai_configs` too** |
| `connectors/scheduler.py` | Gains one more tick (like the existing every-5-loop notification check) for AI batch pre-warm + monthly budget reconciliation | **Modified (additive)** |
| `ticketing/router.py` (`POST /tickets`) | Ticket creation | **Reused unmodified** — AI only pre-fills the create form; no new required fields |
| `DrillPanel` / `drill-content.tsx` | Vuln detail panel | **Modified (additive)** — new AI section, same idKey/renderContent generalization pattern Phase 13 established |
| `SettingsSidebarShell` (Phase 14 pattern) | RBAC-gated settings categories | **Modified (additive)** — new "AI Assistant" pane, reusing `SaveBar`/`useDirtyState`/sentinel-passthrough secret field pattern |
| nginx | Reverse proxy | **Modified** — new scoped `location /api/v1/ai/` block for streaming |

## Recommended Project Structure

```
backend/app/ai/                    # NEW top-level package, sibling to connectors/, vulnerabilities/, ticketing/
├── __init__.py
├── models.py         # AiConfig, AiUsage, AiEvalRun, AiEvalResult (Base + TimestampMixin + UUIDPrimaryKeyMixin, same as every other domain package)
├── schemas.py         # Pydantic request/response — ExplainRequest, TriageBatchResponse, TicketDraftResponse, AiConfigUpdate (mirrors connectors/schemas.py shape)
├── router.py          # /api/v1/ai/* — thin, Depends(get_current_user) + RBAC checks, delegates to service.py
├── service.py          # Orchestration per capability: explain_vulnerability(), remediation_for_asset(), triage_batch(), draft_ticket()
├── grounding.py       # build_context(db, tenant_id, vuln_id) -> GroundingContext (dataclass), tenant-scoped joins only
├── client.py          # get_client_for_tenant(tenant_id, capability) -> (AsyncAnthropic, model_name); decrypts stored key
├── cache.py           # content_hash(), get_cached(tenant_id, hash), set_cached(tenant_id, hash, payload, ttl)
├── guardrails.py       # sanitize_untrusted_text(), validate_no_hallucination(output, grounding), detect_injection_markers()
├── costs.py           # PRICING table per model, compute_cost(), check_budget(tenant_id), record_usage()
├── prompts.py          # PROMPT_VERSION constants + templates (used in the cache key so a prompt edit invalidates cache)
└── evals.py            # loads eval fixtures, runs them against a config, writes AiEvalRun/AiEvalResult

backend/app/ai_evals/                # NEW — eval fixtures, versioned in git (not runtime data)
├── explain_vuln.jsonl              # {input: {...grounding fixture...}, expected_facts: [...], forbidden_claims: [...]}
├── remediation.jsonl
└── triage_ranking.jsonl

frontend/src/components/vulnerabilities/
├── drill-content.tsx                # MODIFIED — new <AiExplainSection> mounted additively, same forwardRef/idOrCve contract
├── ai-explain-section.tsx           # NEW — streams via fetch()+ReadableStream, renders progressively
frontend/src/lib/queries/
├── use-ai-explain.ts                 # NEW — not a normal TanStack useQuery (streaming doesn't fit request/response caching); a small custom hook wrapping fetch + reader, writing chunks into local state, with the *final* assembled text written into the TanStack cache under a stable key so re-opening the same vuln within the session shows the last result instantly without re-streaming
```

### Structure Rationale

- **`app/ai/` as its own top-level package** — matches the existing convention where every domain (auth, assets, connectors, cspm, tenants, ticketing, users, vulnerabilities) is a sibling package under `backend/app/`, not a subpackage nested inside an existing one. This keeps the "AI is additive, never load-bearing for existing features" boundary crisp and matches how `notifications/` was added.
- **`app/ai_evals/` as fixture data, separate from `app/ai/`** — eval cases are test data, not application code; keeping them out of the importable package avoids them being packaged/deployed and makes git diffs on eval-case changes easy to review in PRs, the same way `docs/` and `BACKLOG.md` are reviewed today. `AiEvalRun`/`AiEvalResult` rows in Postgres are the *outcome* of running these fixtures against a given prompt/model version — the fixtures are the input, the DB is the historical ledger (so regressions across model/prompt versions are queryable, not just "green/red in CI").
- **No new microservice / no Celery / no vector DB** — Key Decisions already flags "in-process scheduler, no Celery" as a ⚠️ Revisit item for horizontal scale, but v3.0's Out-of-Scope inherits from PROJECT.md ("Per-tenant SaaS... single-VM... unsupported in practice"). Grounding is deterministic SQL joins over already-correlated tables, not semantic/vector retrieval — there's no unstructured corpus to index; the correlation service already did the hard work of joining CVE-on-host across sources. Introducing a vector DB or a separate worker service now would be premature complexity the constraints explicitly forbid ("no language migrations," single-VM Docker Compose).

## Architectural Patterns

### Pattern 1: Grounding Context Assembly (deterministic SQL join, not vector RAG)

**What:** For a given `vulnerability_id`, assemble a `GroundingContext` from `Vulnerability` (CVE/CVSS/EPSS/exploit/KEV/remediation_info fields already on the row), its `asset` relationship (hostname/OS/device_category/owner fields from MDM/HR enrichment), any `VulnerabilityCorrelation` rows for the same `(tenant_id, cve_id, asset_id)` (so the model sees "seen by CrowdStrike + Nessus" rather than one source's view), the asset's open `Misconfiguration` rows (CSPM context), and SLA fields (`sla_due_at`, `sla_breached`) already on the vuln row.

**When to use:** Every AI call. This is the single function every capability (`explain`, `remediate`, `triage`, `draft`) calls first, so grounding logic lives in exactly one place (`grounding.py`), never duplicated per-endpoint.

**Trade-offs:** Deterministic joins are cheap, auditable, and tenant-safe by construction (every query already carries `.where(Model.tenant_id == tenant_id)`, identical to every existing router in the codebase — no new isolation primitive needed). The trade-off is it can't answer questions outside what's in these tables (e.g. no live CVE-feed lookup) — which is fine, since "scanner-less CVE feeds" and "self-scanning" are already Out of Scope for the whole product.

**Example:**
```python
# app/ai/grounding.py
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class GroundingContext:
    cve_id: str | None
    vulnerability_name: str | None
    severity: str
    cvss_v3_score: float | None
    epss_score: float | None
    exploit_available: bool
    cisa_kev: bool
    remediation_info: str | None
    sources_seen: list[str]          # from VulnerabilityCorrelation, tenant-scoped
    asset_hostname: str | None
    asset_os: str | None
    device_category: str | None
    asset_owner: str | None          # MDM/HR-enriched assigned_user
    sla_due_at: str | None
    sla_breached: bool
    open_misconfigurations: list[dict]  # CSPM findings on the same asset, tenant-scoped

async def build_context(db: AsyncSession, tenant_id: uuid.UUID, vuln_id: uuid.UUID) -> GroundingContext:
    vuln = (await db.execute(
        select(Vulnerability)
        .options(selectinload(Vulnerability.asset))
        .where(Vulnerability.id == vuln_id, Vulnerability.tenant_id == tenant_id)  # tenant scope, same as every existing query
    )).scalar_one_or_none()
    if vuln is None:
        raise GroundingNotFound(vuln_id)
    # ... correlation + misconfiguration queries, each with the same .where(tenant_id == tenant_id) guard
    return GroundingContext(...)
```

### Pattern 2: Redis Content-Hash Cache (avoid re-billing identical vulns)

**What:** Before calling the model, compute `content_hash = sha256(capability + prompt_version + model + json.dumps(asdict(grounding_context), sort_keys=True))`. Check `ai:cache:{tenant_id}:{content_hash}` in Redis first; only call the model on a miss.

**When to use:** Every request. CVE descriptions and remediation text for a given CVE-on-host almost never change between scans, so this is a high-hit-rate cache — the same vuln re-opened by a second analyst, or the scheduler's nightly re-scan finding the same finding again, must not re-bill.

**Trade-offs:** Cache is **tenant-scoped**, not shared across tenants (see "Tenant Isolation" below) — simpler and safer, at the cost of not sharing the generic-CVE-text portion across tenants. This is the right trade for GetVul specifically: the deployment model is one VM per customer (Out of Scope: "Per-tenant SaaS... unsupported in practice"), so there is normally only one tenant's data on a given install anyway — cross-tenant cache sharing would add complexity for a benefit that mostly doesn't apply to the real deployment topology. TTL should be long (30–90 days) since the underlying facts are stable; invalidate by bumping `prompt_version` in `prompts.py` when a prompt changes, which naturally busts the hash.

**Example:**
```python
# app/ai/cache.py
def content_hash(capability: str, prompt_version: str, model: str, context: GroundingContext) -> str:
    payload = json.dumps({"c": capability, "v": prompt_version, "m": model, "ctx": asdict(context)}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

async def get_cached(redis_client, tenant_id: uuid.UUID, hash_: str) -> dict | None:
    raw = await redis_client.get(f"ai:cache:{tenant_id}:{hash_}")
    return json.loads(raw) if raw else None

async def set_cached(redis_client, tenant_id: uuid.UUID, hash_: str, payload: dict, ttl_seconds: int = 60 * 60 * 24 * 60) -> None:
    await redis_client.set(f"ai:cache:{tenant_id}:{hash_}", json.dumps(payload), ex=ttl_seconds)
```

### Pattern 3: Per-Tenant Encrypted Model Config (mirrors `ConnectorConfig`)

**What:** New `AiConfig` table, one row per tenant, storing `provider` (default `"anthropic"`), an **encrypted** API key using the exact same `encrypt_value`/`decrypt_value` Fernet helpers from `app/encryption.py` (no new crypto scheme), per-capability model overrides (`model_explain`, `model_remediate`, `model_triage`, `model_ticket_draft` — defaulting to Haiku/Sonnet/Sonnet/Sonnet per the milestone's stated cost tiers), and monthly budget fields.

**When to use:** Resolved once per request in `client.py`, with a global-env-var fallback (`settings.anthropic_api_key`) so a tenant that hasn't configured anything yet still gets a working default — matching the "any new env var needs a sensible default" constraint from `install.sh`'s operator UX contract.

**Trade-offs:** Storing the credential exactly like `ConnectorConfig.credentials_secret_arn` (a JSON-map string of encrypted fields) rather than inventing a new shape means `rotate_credentials()` in `encryption.py` can be **generalized to accept a table/model parameter** and sweep both `ConnectorConfig` and `AiConfig` in the same single-transaction abort-all-or-nothing rotation the CLI already performs — one documented key-rotation operation, not two. The trade-off is `rotate_credentials()` needs a small refactor (currently hardcodes `from app.ticketing.models import ConnectorConfig`); this refactor is worth flagging explicitly to whichever phase touches encryption, since Constraints says "no Fernet key rotation without a documented migration."

**Example:**
```python
# app/ai/models.py
class AiConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_configs"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_ai_config_tenant"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="anthropic")
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)   # same encrypt_value() shape as ConnectorConfig
    model_explain: Mapped[str] = mapped_column(String(50), default="claude-haiku-4-5")
    model_remediate: Mapped[str] = mapped_column(String(50), default="claude-sonnet-5")
    model_triage: Mapped[str] = mapped_column(String(50), default="claude-sonnet-5")
    model_ticket_draft: Mapped[str] = mapped_column(String(50), default="claude-sonnet-5")
    monthly_token_budget: Mapped[int | None] = mapped_column(Integer)
    monthly_cost_budget_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

### Pattern 4: SSE Streaming Through FastAPI + nginx

**What:** `AsyncAnthropic().messages.stream(...)` (the typed streaming helper, not raw `create(stream=True)`) is consumed inside an async generator that yields `f"data: {json.dumps({'delta': text})}\n\n"` per text delta, returned as `StreamingResponse(gen, media_type="text/event-stream")` — the codebase already uses `StreamingResponse` for CSV/PDF export, so this is a proven FastAPI pattern here, just incremental instead of single-shot.

**When to use:** The two user-facing, potentially-slow generative endpoints (`explain`, `remediate`/`draft` narrative text) where perceived latency matters in the `DrillPanel`. Batch triage-ranking (structured, short) can stay non-streamed JSON.

**Trade-offs:**
- **Auth:** the browser `EventSource` API cannot send a custom `Authorization` header, and this app's auth is Bearer-JWT, not cookies. Recommend the frontend consume the stream via `fetch(url, {headers: {Authorization}})` + `response.body.getReader()` with manual SSE-line parsing, **not** `EventSource** — this requires zero change to the existing auth model.
- **nginx buffering:** the current `/api/` location block has no `proxy_buffering` directive, meaning nginx fully buffers the upstream response before forwarding — this defeats streaming entirely if left as-is. A **new, scoped** `location /api/v1/ai/ { proxy_buffering off; proxy_cache off; gzip off; proxy_read_timeout 120s; ... }` block (copying the existing headers/rate-limit lines) is the safest change — it doesn't touch the timeout/buffering behavior of the already-verified `/api/` block used by every other endpoint.
- **Heartbeats:** long Opus reasoning calls can exceed typical idle-connection windows; emit a `: heartbeat\n\n` comment line every ~15s during generation to keep the connection alive through nginx and any browser idle timeouts.

### Pattern 5: Guardrail Wrapper (prompt-injection + hallucination defense)

**What:** Two-sided defense, since "scanner/vuln text is attacker-controllable" is called out as a first-class threat in the milestone context: (1) **input side** — every untrusted string pulled from `Vulnerability`/`Asset`/`Misconfiguration` fields (CVE descriptions, hostnames, finding titles, which ultimately come from scanner vendors and could theoretically be crafted) is wrapped in an explicit delimiter block in the prompt (e.g. `<untrusted_scanner_data>...</untrusted_scanner_data>`) with a system-prompt instruction to treat delimited content as data, never as instructions; (2) **output side** — before returning a remediation/ticket draft, `validate_no_hallucination()` checks that any concrete claim the model makes (fixed version, CVE ID, package name) actually appears in the `GroundingContext` it was given, rejecting/flagging outputs that introduce facts not present in the grounding (the "no hallucinated remediation" guardrail named explicitly in the milestone's target features).

**When to use:** Every call, no exceptions — this is the first-class guardrail the milestone explicitly requires before the eval/cost gate phase, and it belongs in `app/ai/`, not duplicated per capability.

**Trade-offs:** Output validation against grounding facts is necessarily heuristic (string/entity matching, not a full logical proof) — false positives (rejecting a correct-but-differently-worded claim) are the safe failure mode and should degrade to "show with a caveat banner" rather than a hard block, consistent with the product's existing pattern of never silently swallowing failures (`audit()`'s fail-closed philosophy, `PartialFailureBanner` primitive already built for connector partial failures).

### Pattern 6: Cost Ledger + Budget Enforcement (reuses the Redis sliding-window idiom, opposite fail-mode)

**What:** A Redis counter `ai:usage:{tenant_id}:{yyyy-mm}` tracks running cost for the month (INCRBYFLOAT cents or micro-dollars, TTL to end-of-month), checked **before** issuing a call and updated **after** a call completes with exact token counts from the response. Postgres `AiUsage` is the append-only system-of-record (one row per call: tenant, user, capability, model, prompt/completion tokens, cost_usd, cache_hit, resource ref) for reporting and audit cross-reference.

**When to use:** Every call, pre-check and post-record.

**Trade-offs — deliberately the opposite fail-mode of the existing rate limiter:** `TenantRateLimitMiddleware` fails **open** on Redis unavailability (an availability guardrail — better to let a request through than 500 the whole API). Budget enforcement should fail **closed** on Redis unavailability (a cost/compliance guardrail — better to block an AI call than risk an unbounded-cost incident while the safety rail is down), with a friendly, non-crashing "AI assistant is temporarily unavailable" state (per the state-patterns skill), not a raw 503. This asymmetry is intentional and should be called out in code comments the same way the rate limiter's fail-open choice is documented today.

### Pattern 7: Audit Logging via the Existing `audit()` Helper — No Schema Change

**What:** `AuditLog.details` is already an unconstrained `JSONB` column, so new action names (`ai.explain`, `ai.remediate`, `ai.triage_suggest`, `ai.ticket_draft`, `ai.batch_triage`) slot in with zero migration to `audit_logs` itself. `details` carries `{"model": ..., "prompt_tokens": ..., "completion_tokens": ..., "cost_usd": ..., "cache_hit": ..., "content_hash": ..., "resource_type": "vulnerability", "resource_id": "..."}`. **Do not store the raw prompt or full model output in the audit row** — store the content hash + resource reference (the full text is already reconstructable from `GroundingContext` + the cached response in Redis/`AiUsage`), keeping the audit table's existing size/PII profile intact.

**When to use:** Every AI call, user-initiated or scheduler-initiated.

**Trade-offs / a real gap found in the existing code:** `audit(db, user, ...)` takes `user: CurrentUser | None`, and when `user=None` it sets `tenant_id=uuid.UUID(int=0)` — a **nil sentinel**, not a real tenant. That's correct for truly system-wide events but **wrong** for a scheduler-originated per-tenant AI batch call, which must file under the real tenant. The codebase already solved this exact problem for the CLI key-rotation audit row: `encryption.py`'s `rotate_credentials()` bypasses the `audit()` helper and constructs `AuditLog` directly with `user_id=None, user_email="system:cli", tenant_id=<real tenant>`. The scheduler's AI batch job should follow the identical precedent — construct `AuditLog(tenant_id=<real tenant from the AiConfig row>, user_id=None, user_email="system:scheduler", action="ai.batch_triage", ...)` directly, not via `audit()`.

## Data Flow

### Request Flow — User-Initiated (Explain / Remediate / Ticket Draft)

```
DrillPanel opens (existing drill-content.tsx, additive AiExplainSection)
    ↓
fetch(`/api/v1/ai/vulnerabilities/{id}/explain`, {headers:{Authorization: Bearer <jwt>}})
    ↓ (nginx: location /api/v1/ai/ — proxy_buffering off, gzip off)
FastAPI app/ai/router.py
    ↓ Depends(get_current_user)   ← existing dependency, unchanged, gives tenant_id + role
    ↓ RBAC check (Viewer can read explanations; Analyst+ can trigger remediation/draft — per existing ROLE_HIERARCHY)
app/ai/service.py:explain_vulnerability(db, user, vuln_id)
    ↓
grounding.build_context(db, user.tenant_id, vuln_id)   ← tenant-scoped SELECT on Vulnerability/Asset/Correlation/Misconfiguration
    ↓
cache.content_hash(...) → cache.get_cached(redis, tenant_id, hash)
    ├─ HIT  → stream cached text back (single/few chunks) + audit(action=..., details={cache_hit: true, cost_usd: 0}) → db.commit()
    └─ MISS → costs.check_budget(tenant_id)  [fail-closed if over budget]
              → client.get_client_for_tenant(tenant_id, "explain")  [decrypt AiConfig.api_key_encrypted via encryption.py]
              → guardrails.sanitize_untrusted_text(grounding fields) → prompts.render("explain", context)
              → AsyncAnthropic.messages.stream(model=..., messages=[...])
                    ↓ async for event in stream:  yield f"data: {json.dumps({'delta': event.text})}\n\n"
              → on stream completion: guardrails.validate_no_hallucination(full_text, context)
              → cache.set_cached(redis, tenant_id, hash, full_text)
              → costs.record_usage(tenant_id, model, prompt_tokens, completion_tokens, cost_usd) → Redis INCR + AiUsage row
              → audit(db, user, "ai.explain", "vulnerability", vuln_id, {model, tokens, cost_usd, cache_hit: false, content_hash}) → db.commit()
    ↓
StreamingResponse → nginx (unbuffered) → browser ReadableStream reader → AiExplainSection renders progressively
```

### Data Flow — Scheduler-Initiated (Batch Triage Pre-Warm)

```
connectors/scheduler.py _scheduler_loop() — existing 60s loop, gains one more tick
    (mirrors the existing "every 5 loops" notification-alert cadence, e.g. every 60 loops = hourly, or once/24h like ticket sync)
    ↓
for each tenant with AiConfig.is_enabled and a triage-batch feature flag:
    asyncio.create_task(_run_ai_batch(tenant_id))   ← same fire-and-forget-with-tracking pattern as trigger_background_sync(),
                                                        tracked in its own _running_ai_batches dict to prevent overlap
    ↓ (inside the task, its own DB session — never share a session across the loop iteration, same as every other scheduler job)
service.triage_batch(db, tenant_id, top_n=50)
    → for each open vuln lacking a fresh cache entry: grounding.build_context() → cache-or-call, same as the request path
    → costs.check_budget(tenant_id) enforced per-item so one tenant's batch can't blow through budget mid-run
    → AuditLog constructed DIRECTLY (not via audit()) — user_id=None, user_email="system:scheduler",
      tenant_id=<real tenant>, action="ai.batch_triage" — same precedent as encryption.py's "system:cli" rotation audit row
    ↓
Result: on-demand /vulnerabilities list "what to fix first" suggestions are cache hits when the analyst next loads the page —
        the batch's job is to pre-warm cost-bearing calls at a predictable, budget-capped time, not to push data to the frontend directly.
```

### Key Data Flows

1. **Grounding never leaves tenant scope:** every SQL query in `grounding.py` carries the same `.where(Model.tenant_id == tenant_id)` predicate every existing router already uses — no new isolation primitive, no risk of cross-tenant grounding leakage, because it's the identical query-scoping discipline already enforced everywhere else in the codebase.
2. **Cache and audit both key off the same `content_hash` / `resource_id`,** so a support engineer debugging "why did the analyst see this remediation" can trace: `AuditLog.details.content_hash` → `AiUsage` row (exact cost/tokens) → Redis cache entry (if still live) → `GroundingContext` reconstructable from the resource_id at read time. Nothing about the AI layer is a black box relative to the rest of the audited system.
3. **The ticket-draft flow is purely additive to the existing create path:** `POST /api/v1/ai/tickets/draft` returns a suggested `{title, description, remediation}` payload that the frontend uses to **pre-fill** the existing ticket-creation form; the analyst still calls the unchanged `POST /api/v1/tickets` (or `/tickets/host`) to actually create it. No new required field, no schema change to `Ticket`.

## Scaling Considerations

GetVul's real scale axis isn't "users" — it's **tenants × vulns × model calls**, and the single-VM Docker Compose ceiling is already a documented constraint (PROJECT.md: "single-VM topology is the explicit deployment model").

| Scale | Architecture Adjustments |
|-------|---------------------------|
| Single tenant, low volume (v3.0 launch target) | In-process scheduler tick for batch pre-warm is sufficient; Redis cache + Postgres ledger on the existing Redis/Postgres containers, no new infra. |
| Single tenant, high vuln volume (10k+ open vulns) | Batch triage must cap `top_n` per run and spread across scheduler ticks rather than one giant burst (mirrors how `run_all_due_rules`/`check_sla_breaches` already iterate per-tenant per-loop rather than doing everything at once); cache hit rate becomes the dominant cost lever — prioritize a high cache TTL over the correctness of a marginally-fresher answer. |
| Several tenants on one VM (schema supports it even though SaaS is Out of Scope) | Per-tenant Redis key namespacing already prevents cross-tenant cache/budget bleed; the scheduler's per-tenant loop already iterates `Tenant.is_active` the same way SLA checks do — AI batch ticks should follow that exact existing iteration pattern, not invent a new one. |

### Scaling Priorities

1. **First bottleneck: Anthropic API rate limits / latency, not GetVul's own infra.** A slow Opus call blocking a scheduler tick would delay the *next* connector sync/SLA check/ticket-rule tick in the same 60s loop (everything in `_scheduler_loop()` currently runs sequentially in one loop body). AI batch work **must** be dispatched via `asyncio.create_task` (like `trigger_background_sync`), never awaited inline in the loop body, so a slow model call can't stall connector syncs or SLA breach detection.
2. **Second bottleneck: Redis cache/budget key contention at scheduler-batch time.** Since batch pre-warm iterates many vulns for a tenant in one task, budget-check-then-increment must be atomic (Redis `INCRBYFLOAT` / Lua script or pipeline, same MULTI/EXEC discipline the existing rate limiter already uses) to avoid two near-simultaneous calls (one user-initiated, one batch-initiated) both passing a stale budget check.

## Anti-Patterns

### Anti-Pattern 1: Calling the model inline inside `_scheduler_loop()`'s main `try` blocks

**What people do:** Add `await call_anthropic(...)` directly inside the existing loop body, next to the SLA-check/ticket-rule/report blocks.
**Why it's wrong:** Every other block in that loop is fast (DB queries, local computation); a multi-second-to-tens-of-seconds LLM call would delay every other tenant's connector sync, SLA check, and ticket rule for the remainder of that 60s tick — a correctness/availability regression to features that have nothing to do with AI.
**Instead:** Fire-and-track via `asyncio.create_task`, exactly like `trigger_background_sync()` already does for connector syncs.

### Anti-Pattern 2: A single global Redis cache key (no tenant scoping) "to maximize cache hits"

**What people do:** Key the cache purely by `content_hash` (CVE + prompt version) to share hits across all data on the box.
**Why it's wrong:** Even though the deployment model is one-VM-per-customer, the schema is genuinely multi-tenant and `tenant_id` scoping is a hard constraint ("Every domain table includes tenant_id... No new feature may bypass this" — Constraints). A cache is invisible state that can silently violate that discipline if it's the one place `tenant_id` isn't in the key. Grounding context also isn't CVE-text-only — it includes asset owner/hostname, which is tenant-private data by definition.
**Instead:** Always prefix cache and budget keys with `tenant_id`, matching every other Redis key in the codebase (`ratelimit:{tenant_key}`, the OIDC-state keys).

### Anti-Pattern 3: Storing the full prompt or raw model output in `AuditLog.details`

**What people do:** Log the entire prompt + completion into the JSONB `details` column "for completeness."
**Why it's wrong:** `audit_logs` is a compliance/forensic table forwarded to SIEM via syslog in CEF format; ballooning its row size with full LLM I/O (which can include PII pulled from HR/MDM enrichment in the grounding context) turns a lightweight audit trail into a second copy of sensitive data with a different retention/access model than the rest of the system, and the existing CEF `msg=` field is size-sensitive for syslog transport.
**Instead:** Log the content hash, model, token counts, and cost — the underlying data is already reconstructable from `GroundingContext` (tenant-scoped, RBAC-gated) plus the cache/ledger, so nothing is lost, and the audit row stays small and consistent with every other action already logged.

### Anti-Pattern 4: Treating scanner-sourced text as trusted instruction context

**What people do:** Interpolate `vulnerability_name`, `remediation_info`, or asset hostnames directly into the system/instruction portion of the prompt.
**Why it's wrong:** This data originates from scanner vendors and, transitively, from whatever a scanned host or cloud resource reports about itself — an attacker who controls a scanned asset's metadata (e.g. a hostname, a CSPM finding's user-supplied resource tag) could craft a prompt-injection payload. The milestone context calls this out explicitly as a first-class threat, not a hypothetical.
**Instead:** Always wrap untrusted grounding fields in an explicit data-delimiter block with an instruction that content inside it is data, never a command, and validate outputs against the guardrail's hallucination/injection checks before they reach the analyst or a ticket.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|----------------------|-------|
| Anthropic API (Claude Haiku 4.5 / Sonnet 5 / Opus 4.8) | `AsyncAnthropic` client, per-tenant API key decrypted from `AiConfig`, per-capability model selection | Use `client.messages.stream()` (typed streaming helper) rather than `create(stream=True)` (raw SSE bytes) — confirmed as the documented/recommended pattern for FastAPI + `StreamingResponse` integration. Global `settings.anthropic_api_key` env var is the fallback default (mirrors the `encryption_key`/`jwt_secret_key` placeholder-default pattern already in `config.py`), satisfying "any new env var needs a sensible default." |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|-----------------|-------|
| `app/ai/` ↔ `app/vulnerabilities/`, `app/assets/`, `app/cspm/` | Direct SQLAlchemy `select()` in `grounding.py`, read-only, tenant-scoped | No new service-to-service API; this is an in-process read, same as any other cross-package query in this monolith (e.g. `ticketing` already reads `Vulnerability` directly). |
| `app/ai/` ↔ `app/encryption.py` | Reuses `encrypt_value`/`decrypt_value` directly; `rotate_credentials()` extended to also sweep `AiConfig.api_key_encrypted` | Do not introduce a second encryption scheme — Constraints forbids "no Fernet key rotation without a documented migration," so a second scheme would need its own rotation story from scratch. |
| `app/ai/` ↔ `app/audit.py` | Calls existing `audit()` helper for user-initiated calls; direct `AuditLog(...)` construction (bypassing `audit()`) for scheduler-initiated calls, following the `encryption.py` "system:cli" precedent verbatim | No schema change to `AuditLog`/`audit_logs` table. |
| `app/ai/` ↔ `connectors/scheduler.py` | New tick added to `_scheduler_loop()`, dispatched via `asyncio.create_task` with its own tracking dict (`_running_ai_batches`), never awaited inline | Matches the existing `_running_syncs` / `trigger_background_sync` shape exactly. |
| `app/ai/` ↔ `app/ticketing/` | AI ticket-draft endpoint returns a suggestion payload the frontend uses to pre-fill the existing `POST /tickets` create flow; no direct call from `app/ai/` into ticket creation | Keeps "AI drafts, analyst ships" as a UI-layer decision, not a backend coupling — avoids AI ever creating a ticket unilaterally. |
| Frontend `AiExplainSection` ↔ backend `app/ai/router.py` | `fetch()` + `ReadableStream` reader (NOT `EventSource`), same Bearer-JWT header the rest of the app already sends | Preserves the existing auth model; avoids EventSource's incompatible header/cookie auth story. |
| nginx ↔ `app/ai/router.py` | New scoped `location /api/v1/ai/` block: `proxy_buffering off; proxy_cache off; gzip off; proxy_read_timeout 120s;` | Scoped so the rest of `/api/` keeps its current buffering/timeout behavior unchanged (no regression risk to already-verified endpoints). |
| `app/ai/evals.py` ↔ `app/ai_evals/*.jsonl` | Loads versioned fixture files from the repo, runs them against a given prompt/model config, writes results to `AiEvalRun`/`AiEvalResult` | Fixtures are git-reviewable data; results are a queryable historical ledger for regression detection across prompt/model changes. |

## Suggested Build Order

Respecting the milestone's own stated feature order (PROJECT.md "Target features") and the dependency chain uncovered above:

1. **Ingestion-reliability precursor (already first in the milestone plan) — no AI code.** Fix Wiz/Rapid7 wiring, add scanner HTTP-layer tests, wire Jira ticket-create + finish GitHub ticketing, surface per-connector sync health. This is a **hard prerequisite**, not just good practice: `grounding.py`'s entire value proposition is "grounded in the tenant's own correlated data" — if the correlation/ingestion layer is silently broken, every downstream AI feature grounds on incomplete or wrong data and nobody would know why the AI seems unreliable.
2. **AI foundation package + "Explain this vuln."** Build `app/ai/` skeleton (models, `AiConfig` + encryption reuse, `grounding.py`, `cache.py`, `client.py`, `guardrails.py`, `costs.py`, `audit` wiring, the scoped nginx block, the streaming frontend hook) against the single simplest capability (`explain`). Every later capability reuses this scaffold — this phase is where the **integration risk concentrates** (streaming through nginx, tenant-scoped caching, encrypted per-tenant config, guardrails) and should be validated end-to-end before any other capability is added.
3. **Asset-aware remediation guidance.** Reuses everything from step 2; adds `Misconfiguration`/asset fields to `grounding.py` and a second prompt template. Low incremental integration risk once step 2 is solid.
4. **Natural-language triage assistant (batch).** First feature that touches `connectors/scheduler.py` (the batch pre-warm tick) — sequence this after the request-path (steps 2–3) is proven, since the scheduler-originated audit/budget paths are subtly different (`user=None` handling) and easier to get right once the single-request path is a known-good reference.
5. **AI ticket auto-drafting.** Purely additive to the existing ticket-create UI; depends on steps 2–3's grounding/guardrail infrastructure but touches no new backend risk surface (no ticket-model changes).
6. **Eval + guardrail + cost/observability gate (milestone-closing).** By this point every capability exists and has been generating real `AiUsage`/`AuditLog` data; this phase adds the `app/ai_evals/` fixtures + `AiEvalRun`/`AiEvalResult` tables, hardens the guardrails against the accumulated real examples, and turns the cost ledger into enforced per-tenant budgets + an admin-visible usage pane. Doing this last (not first) means the eval fixtures can be seeded from real explain/remediate/triage/draft outputs already observed in steps 2–5, rather than purely synthetic cases.

This order also means the single riskiest architectural bet — streaming through nginx with tenant-scoped caching and per-tenant encrypted config — gets proven in phase 2 while the blast radius is one capability, not discovered while juggling four.

## Sources

- Direct codebase reads (HIGH confidence): `backend/app/connectors/scheduler.py`, `backend/app/encryption.py`, `backend/app/audit.py`, `backend/app/main.py`, `backend/app/ticketing/models.py` (`ConnectorConfig`), `backend/app/vulnerabilities/models.py`, `backend/app/assets/models.py`, `backend/app/db/base.py`, `backend/app/config.py`, `backend/app/auth/schemas.py` (`CurrentUser`), `backend/app/ticketing/router.py`, `nginx/nginx.conf`, `frontend/src/components/vulnerabilities/drill-content.tsx`, `.planning/PROJECT.md`.
- [Streaming messages - Claude API Docs](https://docs.anthropic.com/en/api/messages-streaming) — MEDIUM confidence, WebSearch-verified, not Context7-resolved: confirms `AsyncAnthropic` + `client.messages.stream()` (typed helper) vs. raw `create(stream=True)`, and the SSE event-accumulation model.
- [FastAPI + Claude API: Production Streaming API — SSE & Retry](https://jangwook.net/en/blog/en/fastapi-claude-api-streaming-production-guide-2026/) — MEDIUM confidence: confirms the `StreamingResponse` + `text/event-stream` + `data: ...\n\n` chunk pattern used above.
- [Python SDK - Claude Platform Docs](https://platform.claude.com/docs/en/api/sdks/python) — MEDIUM confidence: general SDK usage reference.

---
*Architecture research for: v3.0 AI-Assisted Triage — LLM layer integration into GetVul's existing multi-tenant FastAPI/Next.js platform*
*Researched: 2026-07-25*
