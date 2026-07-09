# Phase 7: Health and Observability - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Split the backend's **liveness** (`GET /health`, no dependencies, always 200 if the process is alive) from **readiness** (`GET /ready`, checks Postgres `SELECT 1` + Redis `PING` with bounded ≤500ms timeouts, 503 on any failure), wire the readiness signal into the infrastructure (docker-compose healthcheck + passive nginx upstream + docs), and make production logs machine-parseable JSON via a real `structlog` configuration (which does not exist today). Document the operator response for each dependency-down failure mode.

**In scope:** `/health` reaffirm, new `/ready`, nginx/compose wiring, structlog JSON config, request-id correlation, failure-mode runbook.
**Not in scope:** building alerting infrastructure, scheduler health surfacing, unifying the audit/CEF pipeline, multi-replica load balancing (single-VM stays the topology).
</domain>

<decisions>
## Implementation Decisions

### Liveness `/health` (PROD-07-01)
- **D-01:** `/health` stays a no-dependency liveness probe, always 200 if the process is alive.
- **D-02:** Response body kept **verbatim** — `{"status": "ok", "service": "getvul-api"}`. The compose healthcheck and any external monitors already parse it; no gratuitous contract change. (Current impl: [backend/app/main.py:270-272](backend/app/main.py#L270-L272).)

### Readiness `/ready` (PROD-07-02)
- **D-03:** New `GET /ready` checks Postgres `SELECT 1` + Redis `PING`.
- **D-04:** **Hard-fail policy** — Postgres OR Redis down ⇒ 503. Both must be healthy for 200. Matches SC#2/SC#5 literally; the loud signal tells the operator Redis needs attention even though the rate limiter fails-open and most traffic would still flow. (Accepted tradeoff: on single-VM a 503 de-registers the only node — see Deferred/Specifics for the fail-open nuance.)
- **D-05:** **Per-dependency detail body**, same shape on 200 and 503 — status + per-check `ok`/`latency_ms`/`error`. Example 200: `{"status":"ready","checks":{"postgres":{"ok":true,"latency_ms":4},"redis":{"ok":true,"latency_ms":1}}}`. Example 503: `{"status":"not_ready","checks":{"postgres":{"ok":true,"latency_ms":5},"redis":{"ok":false,"error":"timeout"}}}`.
- **D-06:** **Per-check timeout via `asyncio.wait_for(coro, timeout=0.5)`** — uniform 500ms bound regardless of driver socket settings. On timeout the dep is `ok:false, error:"timeout"` and overall response is 503. (Note: `app.state.redis` has `socket_timeout=2.0` which is too loose for the probe — the wait_for wrapper enforces the tighter bound.)
- **D-07:** DB probe runs through the **shared app connection pool** (`async_session_factory` / get_db path), NOT a dedicated probe connection. If the pool is exhausted, `/ready` correctly reports not-ready — it reflects real serving capacity. A dedicated connection would mask exactly the pool-saturation failure we want caught.
- **D-08:** `/ready` is **DB + Redis only**. Scheduler-liveness is explicitly out of scope (see Deferred).

### Infrastructure wiring (PROD-07-03)
- **D-09:** **Full wiring** (open-source nginx has no active upstream health probing — that's nginx Plus; single-VM/single-backend topology):
  1. Flip the **docker-compose backend healthcheck** from `/health` to `/ready` (both `docker-compose.yml` and `docker-compose.ci.yml`). The compose healthcheck is the de-facto readiness monitor here; `depends_on: condition: service_healthy` + restart policy react to it.
  2. Add an `upstream backend { server backend:8000 max_fails=3 fail_timeout=30s; }` block in [nginx/nginx.conf](nginx/nginx.conf) and route the proxied locations through it — **passive** ejection on real 5xx/timeouts (open-source-nginx-native).
  3. Add a docs section explaining that **active** `/ready` probing requires nginx Plus or an external monitor, and that the compose healthcheck fills that role in this deployment.
- **D-10:** Expose `/ready` through nginx **like `/health` is today** (both public locations). No sensitive data in the per-dep body (only ok/latency/error-class), so external HTTPS uptime monitors can reach it.

### Structured logging (PROD-07-04)
- **D-11:** **Unified JSON stream** — route app structlog AND stdlib logging (uvicorn app/error/access) through one processor chain (`structlog.stdlib.ProcessorFormatter`) so production stdout is ONE consistent JSON stream, no mixed plaintext/JSON. Env-gated: JSON renderer when `ENVIRONMENT=production`, `ConsoleRenderer` (color) in dev.
- **D-12:** New `configure_logging()` lives in a **new `backend/app/logging.py` module**, called during app startup (lifespan/create_app). (Exact call-site is Claude's discretion.)
- **D-13:** **request_id correlation** — a lightweight middleware generates/propagates a `request_id`, binds it via `structlog` contextvars so every log line during the request carries it, and echoes it back as an `X-Request-ID` response header.
- **D-14:** **Inbound `X-Request-ID` honored but sanitized** — reuse the client/proxy-supplied value if valid (len ≤128, charset `[A-Za-z0-9._-]`), else mint a UUID4. Structured JSON escaping keeps injection risk low; the length/charset cap is defense-in-depth.
- **D-15:** **Standard structlog default field keys** — `timestamp` (ISO-8601 UTC via `TimeStamper`), `level`, `logger`, `event`. No ECS/`@timestamp` remap — no aggregator chosen yet; remap-in-aggregator is trivial later.
- **D-16:** **Production min level = INFO** (DEBUG suppressed); dev = DEBUG. Via `structlog.make_filtering_bound_logger`. Access-log probe suppression (D-19) handles the highest-volume noise.
- **D-17:** **Redaction processor** in the chain — scrub known-sensitive keys (`authorization`, `cookie`, `password`, `token`, `secret`, `credentials`, `api_key`) to `[REDACTED]` before rendering. Extends Phase 5's "never log key material" principle to operational logs.
- **D-18:** The existing **audit CEF-over-syslog pipeline stays fully separate** and untouched ([backend/app/audit.py](backend/app/audit.py) `configure_syslog`, loaded per-tenant in lifespan). Phase 7 configures operational logging only; it does NOT route audit events through structlog or vice-versa. Two independent channels.
- **D-19:** **Suppress `/health` + `/ready` access logs** (stdlib logging filter on `uvicorn.access`) so ~5s-interval probes don't flood the JSON stream. A failed `/ready` still emits its own explicit `logger.error`/`readiness_check_failed` line, so failures stay visible.

### Failure-mode alerting (PROD-07 SC#5)
- **D-20:** **No new alerting infrastructure.** "Alert" for this phase = (a) `/ready` emits a loud structured log line (`logger.error`/`critical` naming the failed dep) on each failed check, and (b) a **"Failure Modes & Operator Response"** docs section (in `docs/16-security.md` or an ops doc) mapping symptom → `/ready` state → log event → operator action, plus a note to wire the compose healthcheck / external uptime monitor to page on repeated 503. The log line + `/ready` ARE the alert surface.

### Test contract (SC#1/2/4)
- **D-21:** **Full test matrix** required by the planner:
  - `/health` always 200, no deps
  - `/ready` 200 when both up (asserts per-dep body + `latency_ms` fields)
  - `/ready` 503 when Postgres down (mocked)
  - `/ready` 503 when Redis down (mocked)
  - `/ready` timeout path — slow dep ⇒ `ok:false`, overall 503
  - logging: JSON renderer selected under `ENVIRONMENT=production`, `ConsoleRenderer` in dev

### Claude's Discretion
- Exact `configure_logging()` call-site (lifespan vs module import vs create_app).
- Processor ordering within the structlog chain (subject to redaction running before render).
- Helper/function names, precise nginx location block phrasing, docs file placement (security.md vs a new ops doc).
- Whether the request_id middleware is a new class or folded into an existing middleware.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements / roadmap
- `.planning/REQUIREMENTS.md` §"Health and Observability (PROD-07)" — PROD-07-01..04 acceptance criteria.
- `.planning/ROADMAP.md` §"Phase 7: Health and Observability" — Goal + 5 Success Criteria (SC#1–5).

### Code to modify / extend
- `backend/app/main.py` — existing `/health` handler ([:270-272](backend/app/main.py#L270-L272)); lifespan Redis setup on `app.state.redis` ([:99-104](backend/app/main.py#L99-L104)); existing middleware stack (`SecurityHeadersMiddleware`, `TenantRateLimitMiddleware`) as the pattern for the new request_id middleware; `logger = structlog.get_logger()` at [:34](backend/app/main.py#L34).
- `backend/app/redis_client.py` — `get_redis(request)` dependency; Redis lives on `app.state.redis`.
- `backend/app/db/session.py` — `get_db` / `async_session_factory` for the DB probe.
- `backend/app/config.py` — `settings.environment` / `settings.debug` env-gating pattern ([:10-11](backend/app/config.py#L10-L11)).
- `backend/app/audit.py` — existing CEF/syslog pipeline (`configure_syslog`); MUST stay independent (D-18).
- `nginx/nginx.conf` — proxy locations (`/api/`, `/auth/`, `/health`, `/docs`, `/dev/`); no `upstream` block today; two server blocks (HTTP + HTTPS).
- `docker-compose.yml` + `docker-compose.ci.yml` — backend `healthcheck` currently hits `/health`; Postgres/Redis have `service_healthy` gates.

### Prior-phase context that constrains this phase
- Phase 1 fail-mode contract: rate limiter **fails OPEN**, OIDC state **fails CLOSED** on Redis loss (informs D-04's accepted tradeoff).
- Phase 5 principle: "never log key material" (extended by D-17 redaction).

### Docs to update
- `docs/16-security.md` — likely home for the Failure Modes & Operator Response runbook (D-20); confirm during planning.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app.state.redis`** (redis.asyncio client, `socket_timeout=2.0`) + `get_redis` dependency — reuse for the `/ready` Redis PING (wrap in `asyncio.wait_for(0.5)` per D-06).
- **`async_session_factory` / `get_db`** — reuse for the `/ready` DB `SELECT 1` through the shared pool (D-07).
- **`SecurityHeadersMiddleware` / `TenantRateLimitMiddleware`** (`BaseHTTPMiddleware` subclasses in main.py) — the established middleware pattern for the new request_id middleware (D-13).
- **`settings.environment` / `settings.debug`** — the env-gating pattern already used by `_check_secrets_at_startup` and the docs-route CSP carve-out; reuse for renderer + level selection (D-11, D-16).
- **structlog is already a dependency** and `structlog.get_logger()` is already called — but there is **NO `structlog.configure()` anywhere**, so logging currently runs on library defaults. This phase establishes the real config.

### Established Patterns
- Loud startup issues logged via `logger.critical(...)` with structured kwargs, hard-fail in prod (`_check_secrets_at_startup`) — mirror for readiness-failure logging (D-20).
- Snake_case structured event names (`redis_unavailable`, `startup_secret_check_failed`) — keep the convention (`readiness_check_failed`).
- `create_app()` factory returns independent apps; tests spin up isolated instances (PROD-01-03) — the test matrix (D-21) uses this.

### Integration Points
- New `/ready` route registered alongside `/health` in `create_app()`.
- New request_id middleware added to the `add_middleware` stack in `create_app()`.
- `configure_logging()` invoked at startup (before/at lifespan).
- nginx `upstream backend` block + `/ready` location.
- compose `healthcheck.test` string flipped to `/ready` in both compose files.
</code_context>

<specifics>
## Specific Ideas

- **Accepted tradeoff on D-04 (hard-fail Redis):** the user explicitly chose spec-literal hard-fail over a "Redis soft/degraded" 200-with-`degraded:true` body, even though the rate limiter fails-open means the app can serve most traffic without Redis. Rationale: keep the `/ready` contract honest and the operator signal loud. On single-VM this means a Redis outage marks the only node not-ready — the operator response (D-20 runbook) covers this.
- **nginx reality check:** open-source nginx cannot actively probe `/ready`. D-09's compose-healthcheck + passive-upstream + docs combo is the honest single-VM implementation of "nginx upstream health uses /ready" (SC#3), not a pretend active health check.
- **Probe body carries no secrets** — only `ok`/`latency_ms`/`error`-class — which is why `/ready` can be public (D-10).
</specifics>

<deferred>
## Deferred Ideas

- **Scheduler health surface** — asserting the in-process background scheduler ([backend/app/connectors/scheduler.py](backend/app/connectors/scheduler.py)) is alive is a distinct concern (work-not-getting-done vs request-serving readiness). Kept out of `/ready` (D-08). Candidate for a future observability slice / v1.1.
- **Real alerting infrastructure** — email/PagerDuty/Prometheus on repeated readiness failures. Out of scope; D-20 ships a log line + runbook instead. Candidate for a future phase.
- **Log aggregator integration + ECS field mapping** — no aggregator chosen; D-15 uses structlog defaults. Remap when/if an aggregator (ELK/Loki/Datadog) is adopted.
- **Multi-replica load balancing** — single-VM stays the topology (per PROJECT.md Out of Scope); the passive upstream block is single-backend today but is forward-compatible.

None of the above were scope creep during discussion — they were deliberately bounded out.
</deferred>

---

*Phase: 07-health-and-observability*
*Context gathered: 2026-07-09*
