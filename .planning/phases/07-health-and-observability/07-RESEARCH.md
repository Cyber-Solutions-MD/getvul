# Phase 7: Health and Observability — Research

**Researched:** 2026-07-10
**Domain:** FastAPI health/readiness probes, structlog stdlib integration, nginx passive upstream, docker-compose healthcheck
**Confidence:** HIGH (all critical mechanics verified against official docs or live codebase)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Liveness `/health` (PROD-07-01)**
- D-01: `/health` stays a no-dependency liveness probe, always 200 if the process is alive.
- D-02: Response body kept verbatim: `{"status": "ok", "service": "getvul-api"}`. No contract change.

**Readiness `/ready` (PROD-07-02)**
- D-03: New `GET /ready` checks Postgres `SELECT 1` + Redis `PING`.
- D-04: Hard-fail policy — Postgres OR Redis down => 503. Both must be healthy for 200.
- D-05: Per-dependency detail body, same shape on 200 and 503. Example 200: `{"status":"ready","checks":{"postgres":{"ok":true,"latency_ms":4},"redis":{"ok":true,"latency_ms":1}}}`. Example 503: `{"status":"not_ready","checks":{"postgres":{"ok":true,"latency_ms":5},"redis":{"ok":false,"error":"timeout"}}}`.
- D-06: Per-check timeout via `asyncio.wait_for(coro, timeout=0.5)`. On timeout: `ok:false, error:"timeout"`, overall 503.
- D-07: DB probe runs through the shared app connection pool (`async_session_factory` / get_db path).
- D-08: `/ready` is DB + Redis only. Scheduler-liveness is out of scope.

**Infrastructure wiring (PROD-07-03)**
- D-09: Full wiring:
  1. Flip docker-compose backend healthcheck from `/health` to `/ready` (both `docker-compose.yml` and `docker-compose.ci.yml`).
  2. Add `upstream backend { server backend:8000 max_fails=3 fail_timeout=30s; }` in nginx.conf, route proxied locations through it.
  3. Add docs explaining active `/ready` probing requires nginx Plus or an external monitor; compose healthcheck fills that role here.
- D-10: Expose `/ready` through nginx like `/health` is today (public location).

**Structured logging (PROD-07-04)**
- D-11: Unified JSON stream — route app structlog AND stdlib logging (uvicorn app/error/access) through one processor chain (`structlog.stdlib.ProcessorFormatter`). Env-gated: JSON in production, ConsoleRenderer in dev.
- D-12: New `configure_logging()` lives in a new `backend/app/logging.py` module.
- D-13: Request_id correlation — lightweight middleware generates/propagates `request_id`, binds via structlog contextvars, echoes as `X-Request-ID` response header.
- D-14: Inbound `X-Request-ID` honored but sanitized — reuse if valid (len ≤128, charset `[A-Za-z0-9._-]`), else mint UUID4.
- D-15: Standard structlog default field keys: `timestamp` (ISO-8601 UTC), `level`, `logger`, `event`. No ECS remap.
- D-16: Production min level = INFO (DEBUG suppressed); dev = DEBUG. Via `structlog.make_filtering_bound_logger`.
- D-17: Redaction processor in the chain — scrub `authorization`, `cookie`, `password`, `token`, `secret`, `credentials`, `api_key` keys to `[REDACTED]` before rendering.
- D-18: Existing audit CEF-over-syslog pipeline stays fully separate and untouched.
- D-19: Suppress `/health` + `/ready` access logs via stdlib logging filter on `uvicorn.access`. A failed `/ready` still emits an explicit `logger.error` / `readiness_check_failed` line.

**Failure-mode alerting (PROD-07 SC#5)**
- D-20: No new alerting infrastructure. "Alert" = `/ready` emits a loud structured log line (`logger.error`/`critical`) on each failed check + a "Failure Modes & Operator Response" docs section.

**Test contract (SC#1/2/4)**
- D-21: Full test matrix: `/health` always 200; `/ready` 200 when both up; 503 when Postgres down; 503 when Redis down; timeout path; JSON renderer selected in production, ConsoleRenderer in dev.

### Claude's Discretion
- Exact `configure_logging()` call-site (lifespan vs module import vs create_app).
- Processor ordering within the structlog chain (subject to redaction running before render).
- Helper/function names, precise nginx location block phrasing, docs file placement.
- Whether the request_id middleware is a new class or folded into an existing middleware.

### Deferred Ideas (OUT OF SCOPE)
- Scheduler health surface
- Real alerting infrastructure (email/PagerDuty/Prometheus)
- Log aggregator integration + ECS field mapping
- Multi-replica load balancing
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-07-01 | `GET /health` is a liveness probe (no dependencies) | D-01/D-02 locked; existing handler at main.py:270-272; no changes needed beyond confirming response body is preserved |
| PROD-07-02 | `GET /ready` is a readiness probe checking Postgres + Redis with bounded timeout | asyncio.wait_for(coro, 0.5) pattern verified; JSONResponse return for 503 with custom body confirmed; async_session_factory SELECT 1 + redis.asyncio PING patterns documented |
| PROD-07-03 | Nginx upstream health check uses `/ready` | nginx passive upstream syntax verified from nginx.org; CRITICAL: single-server upstream ignores max_fails/fail_timeout — see Pitfall 3; compose healthcheck flip pattern confirmed |
| PROD-07-04 | structlog output is JSON in production, env-gated | ProcessorFormatter + foreign_pre_chain + wrap_for_formatter pattern verified from structlog docs; make_filtering_bound_logger confirmed; contextvars bind/clear pattern confirmed |
</phase_requirements>

---

## Summary

Phase 7 establishes three independent but related capabilities: a split health/readiness probe pair, nginx infrastructure wiring, and production-grade structured logging via structlog. All three are additive — no existing functionality is removed or broken.

The structlog configuration is the highest-complexity item. The `ProcessorFormatter` approach routes both structlog-native and stdlib loggers (uvicorn.access, uvicorn.error, uvicorn) through a single processor chain. The key insight is that `structlog.configure()` must end with `ProcessorFormatter.wrap_for_formatter`, and the stdlib `logging.StreamHandler` must use `ProcessorFormatter` as its formatter — this creates the unified stream. The `foreign_pre_chain` argument applies shared processors to stdlib-originated records before they reach the final renderer.

The readiness probe uses `asyncio.wait_for(coro, timeout=0.5)` to enforce a 500ms ceiling on both the Postgres and Redis checks, wrapping a `SELECT 1` via `async_session_factory` (shared pool, so pool exhaustion is detectable) and a `PING` via `app.state.redis`. The FastAPI idiom for a 503 with a custom body is to return a `JSONResponse(..., status_code=503)` directly from the route handler — **not** to raise `HTTPException`, which wraps the body in `{"detail": ...}`.

The nginx upstream block has an important real-world limitation: open-source nginx ignores `max_fails` and `fail_timeout` for a **single-server upstream group** (the `server backend:8000` is the only server). Passive ejection is silently disabled. The honest deliverable for D-09 is the compose healthcheck flip (the real readiness monitor for this topology) plus the upstream block as forward-compatible scaffolding, plus clear docs explaining what the block does and does not do.

**Primary recommendation:** Implement all three capabilities as three distinct waves: logging config (foundational), readiness probe, infrastructure wiring. The logging module must be initialized before any route handler runs to ensure request_id correlation covers the readiness probe itself.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `/health` liveness probe | API / Backend | — | Process-alive check; meaningless at any other tier |
| `/ready` readiness probe | API / Backend | — | Pool access + Redis client live on app state; only the backend can evaluate them |
| Structured logging | API / Backend | — | Logging is a backend concern; stdout consumed by Docker |
| Request-ID propagation | API / Backend | CDN / nginx | Backend generates/validates; nginx may pass `X-Request-ID` header forward |
| Nginx upstream passive ejection | CDN / nginx | — | nginx config change; backend just needs to return 5xx |
| Docker-compose healthcheck | CDN / Static (infra) | — | Compose YAML change; triggers `service_healthy` gating |
| Failure-mode runbook | Documentation | — | No code; docs update in `docs/16-security.md` or new ops doc |

---

## Standard Stack

### Core (all already in pyproject.toml)

| Library | Version (declared) | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| `structlog` | >=24.0 (declared), ≥21.1 for make_filtering_bound_logger | Structured logging + stdlib bridge | Official docs confirm ProcessorFormatter is the canonical stdlib integration pattern |
| `fastapi` | >=0.115 | Route definition, JSONResponse | JSONResponse with explicit status_code is the documented idiom for non-200 responses with custom body |
| `redis.asyncio` | via `redis>=5.2` | Redis PING probe | `app.state.redis` is already set up in lifespan; PING is a standard method |
| `sqlalchemy[asyncio]` | >=2.0 | Postgres SELECT 1 probe | `async_session_factory` is the shared pool; using it for probing is intentional per D-07 |
| `orjson` | >=3.10 (declared) | Fast JSON serialization for structlog | Already a dependency; `JSONRenderer(serializer=orjson.dumps)` is the performance-optimal pattern |

### No New Dependencies Required

All required libraries are already declared in `backend/pyproject.toml`. Phase 7 adds no new packages.

**Installation:** (no-op — all deps already present)

---

## Architecture Patterns

### System Architecture Diagram

```
Request enters nginx
       |
       v
nginx http block
  ├── upstream backend { server backend:8000 max_fails=3 fail_timeout=30s; }  ← new
  ├── location /health  → proxy_pass http://backend/health   (liveness, no auth)
  ├── location /ready   → proxy_pass http://backend/ready    ← new
  └── location /api/    → proxy_pass http://backend/api/     (unchanged)
       |
       v
FastAPI app (uvicorn)
  Middleware stack (in order, outermost first):
    1. CORSMiddleware
    2. SecurityHeadersMiddleware
    3. TenantRateLimitMiddleware
    4. RequestIdMiddleware              ← new
       - clear_contextvars()
       - validate/generate request_id
       - bind_contextvars(request_id=...)
       - set X-Request-ID response header
       |
       v
  Route handlers
  ├── GET /health  → { status: ok, service: getvul-api }    (no deps)
  └── GET /ready   → async probe:
        ├── asyncio.wait_for(db_select_1, 0.5)
        ├── asyncio.wait_for(redis_ping, 0.5)
        └── 200 if both ok; 503 otherwise
            + logger.error("readiness_check_failed") on failure

Logging pipeline (stdout):
  structlog loggers  →  ProcessorFormatter.wrap_for_formatter
                               │
  stdlib loggers     →  ProcessorFormatter.foreign_pre_chain
  (uvicorn.*)               │
                            ↓
                    shared_processors:
                      merge_contextvars  (injects request_id)
                      add_log_level
                      add_logger_name
                      TimeStamper(fmt="iso", utc=True)
                      StackInfoRenderer
                      format_exc_info
                      UnicodeDecoder
                      redact_sensitive_keys  ← custom, runs before renderer
                            │
                    ┌───────┴───────┐
                    │ ENVIRONMENT=  │
                    │ production    │ dev
                    ↓               ↓
              JSONRenderer     ConsoleRenderer
                            │
                            ↓
                    StreamHandler(stdout)

Docker Compose healthcheck:
  backend:
    healthcheck:
      test: urlopen('http://localhost:8000/ready')   ← was /health
      interval: 5s / timeout: 5s / retries: 20
```

### Recommended Project Structure

```
backend/app/
├── logging.py         # new — configure_logging(), redact_sensitive_keys processor
├── main.py            # add RequestIdMiddleware, call configure_logging(), add /ready route
├── db/
│   └── session.py     # unchanged — async_session_factory reused for probe
└── redis_client.py    # unchanged — app.state.redis reused for probe

nginx/
└── nginx.conf         # add upstream block + /ready location in both server blocks

docker-compose.yml     # flip backend healthcheck to /ready
docker-compose.ci.yml  # flip backend healthcheck to /ready

docs/
└── 16-security.md     # OR new docs/19-operations.md — failure modes runbook (D-20)
```

---

## Pattern 1: structlog `configure_logging()` — Full Unified Stream

**What:** A single `configure_logging()` function in `backend/app/logging.py` that configures both the structlog pipeline and the stdlib root logger to share one processor chain.

**When to use:** Called once at application startup, before any route handler runs. Best called at the top of the lifespan function (before `_check_secrets_at_startup`), or as a module-level call inside `create_app()`.

**Call-site recommendation (Claude's discretion area):** Call at the top of `lifespan()` in `main.py`, imported from `app.logging`. This guarantees it runs before the first uvicorn log event.

**Example (verified against structlog docs):**
```python
# backend/app/logging.py
# Source: https://github.com/hynek/structlog/blob/main/docs/standard-library.md
import logging
import sys
import structlog

from app.config import settings

SENSITIVE_KEYS = frozenset({
    "authorization", "cookie", "password", "token",
    "secret", "credentials", "api_key",
})


def redact_sensitive_keys(logger, method, event_dict):
    """Scrub known-sensitive keys from the event dict before rendering.

    Must run BEFORE the renderer (JSONRenderer / ConsoleRenderer).
    """
    for key in SENSITIVE_KEYS:
        if key in event_dict:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging() -> None:
    """Configure structlog + stdlib root logger for a unified output stream.

    - production (ENVIRONMENT=production): JSON via JSONRenderer + orjson
    - dev: human-readable via ConsoleRenderer
    - Min level: INFO in prod, DEBUG in dev
    - Both structlog and stdlib loggers (uvicorn.*) emit through the same chain
    """
    import orjson

    min_level = logging.DEBUG if settings.debug else logging.INFO

    shared_processors = [
        structlog.contextvars.merge_contextvars,      # injects request_id from contextvars
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        redact_sensitive_keys,                        # MUST run before renderer
    ]

    if settings.environment == "production":
        renderer = structlog.processors.JSONRenderer(serializer=orjson.dumps)
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # 1. Configure structlog — end with wrap_for_formatter so output is
    #    routed through the stdlib handler below.
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
        cache_logger_on_first_use=True,
    )

    # 2. ProcessorFormatter wraps the stdlib side.
    #    foreign_pre_chain applies shared_processors to records that
    #    originate from stdlib loggers (uvicorn.access, uvicorn.error, etc.).
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    # 3. One StreamHandler on the root logger — captures uvicorn.* + app logs.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = []          # remove any handler basicConfig added
    root_logger.addHandler(handler)
    root_logger.setLevel(min_level)

    # 4. Suppress /health + /ready from uvicorn.access (D-19).
    #    Failed /ready still emits its own logger.error — not suppressed.
    logging.getLogger("uvicorn.access").addFilter(_ProbePathFilter())


class _ProbePathFilter(logging.Filter):
    """Drop uvicorn.access records for /health and /ready probe paths."""
    _PROBE_PATHS = ("/health", "/ready")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(path in msg for path in self._PROBE_PATHS)
```

**Ordering constraint (verified):** `redact_sensitive_keys` must appear in `shared_processors` BEFORE the renderer. The `remove_processors_meta` processor must be the first processor in the `ProcessorFormatter.processors` list (removes internal `_record` and `_from_structlog` keys that structlog injects). [VERIFIED: docs.structlog.org]

---

## Pattern 2: `/ready` Readiness Probe — FastAPI JSONResponse 503

**What:** An async route handler that fires two probes concurrently, applies per-probe timeout, and returns a rich body on both 200 and 503.

**Key idiom:** Return `JSONResponse(content=..., status_code=503)` directly. Do NOT use `raise HTTPException(503, detail=...)` — that wraps the body in `{"detail": ...}` which is the wrong shape per D-05. [VERIFIED: FastAPI source exception_handlers.py]

```python
# In backend/app/main.py — inside create_app(), alongside /health
import asyncio
import time
from fastapi.responses import JSONResponse
from sqlalchemy import text

@app.get("/ready")
async def readiness_check(request: Request):
    """Readiness probe — checks Postgres SELECT 1 + Redis PING.

    Returns 200 when both healthy, 503 when either fails.
    Per-check timeout: 500ms via asyncio.wait_for.
    Uses the shared connection pool (D-07) — pool exhaustion => not-ready.
    """
    checks = {}
    overall_ok = True

    # --- Postgres probe ---
    t0 = time.monotonic()
    try:
        async with async_session_factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=0.5)
        checks["postgres"] = {"ok": True, "latency_ms": round((time.monotonic() - t0) * 1000)}
    except TimeoutError:
        checks["postgres"] = {"ok": False, "error": "timeout"}
        overall_ok = False
    except Exception as exc:
        checks["postgres"] = {"ok": False, "error": type(exc).__name__}
        overall_ok = False

    # --- Redis probe ---
    t0 = time.monotonic()
    try:
        await asyncio.wait_for(request.app.state.redis.ping(), timeout=0.5)
        checks["redis"] = {"ok": True, "latency_ms": round((time.monotonic() - t0) * 1000)}
    except TimeoutError:
        checks["redis"] = {"ok": False, "error": "timeout"}
        overall_ok = False
    except Exception as exc:
        checks["redis"] = {"ok": False, "error": type(exc).__name__}
        overall_ok = False

    status = "ready" if overall_ok else "not_ready"
    if not overall_ok:
        logger.error(
            "readiness_check_failed",
            postgres_ok=checks["postgres"]["ok"],
            redis_ok=checks["redis"]["ok"],
        )

    return JSONResponse(
        content={"status": status, "checks": checks},
        status_code=200 if overall_ok else 503,
    )
```

**asyncio.TimeoutError note:** In Python 3.12 (the project's target), `asyncio.wait_for` raises the builtin `TimeoutError` (which is the same as `asyncio.TimeoutError` — they are aliased). Catching `TimeoutError` is correct. [VERIFIED: Python 3.14 runtime test]

---

## Pattern 3: RequestIdMiddleware — contextvars Binding

**What:** A `BaseHTTPMiddleware` subclass (matching the established middleware pattern in `main.py`) that binds `request_id` to structlog's contextvars for the duration of each request.

```python
# backend/app/main.py — alongside SecurityHeadersMiddleware, TenantRateLimitMiddleware
import re
from structlog.contextvars import bind_contextvars, clear_contextvars

_REQUEST_ID_RE = re.compile(r'^[A-Za-z0-9._-]{1,128}$')

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate or validate X-Request-ID and bind to structlog contextvars."""

    async def dispatch(self, request: Request, call_next):
        clear_contextvars()                                 # clean slate per request
        inbound = request.headers.get("X-Request-ID", "")
        if inbound and _REQUEST_ID_RE.match(inbound):
            request_id = inbound                           # honor sanitized inbound
        else:
            request_id = str(uuid.uuid4())                 # mint fresh UUID4
        bind_contextvars(request_id=request_id)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

**Middleware stack position:** Add `app.add_middleware(RequestIdMiddleware)` AFTER `SecurityHeadersMiddleware` and `TenantRateLimitMiddleware` so request_id is available during rate-limit and security-header processing. In Starlette, `add_middleware` wraps in reverse order — the last-added middleware is outermost. To make RequestIdMiddleware outermost (runs first), it should be added last. [ASSUMED — Starlette middleware ordering behavior; verify against Starlette docs if ordering matters for test]

---

## Pattern 4: nginx Upstream Block + `/ready` Location

**What:** Add a named upstream group and route the existing proxy locations through it. Add `/ready` alongside `/health`.

```nginx
# nginx/nginx.conf — inside the http block, above the server blocks
upstream backend {
    server backend:8000 max_fails=3 fail_timeout=30s;
}
```

Then in both server blocks (HTTP and HTTPS), replace `proxy_pass http://backend:8000/...` with `proxy_pass http://backend/...` (using the upstream name), and add the `/ready` location:

```nginx
# In both server blocks (HTTP :80 and HTTPS :443)
location /ready {
    proxy_pass http://backend/ready;
}
location /health {
    proxy_pass http://backend/health;     # unchanged path, but now uses upstream
}
# Existing locations /api/, /auth/, /docs, /dev/ — change proxy_pass to use upstream name
```

**CRITICAL VERIFIED LIMITATION:** Open-source nginx ignores `max_fails` and `fail_timeout` when the upstream group has **only one server**. From nginx.org official docs:

> "If there is only a single server in a group, max_fails, fail_timeout and slow_start parameters are ignored, and such a server will never be considered unavailable."

This means in the single-VM topology, passive ejection is **silently disabled**. The upstream block is still worth adding (forward-compatible when a second backend server is added; provides an explicit named group), but the real readiness gate for this deployment is the docker-compose healthcheck + restart policy. The docs section (D-20) must make this explicit. [VERIFIED: nginx.org/en/docs/http/ngx_http_upstream_module.html]

**Active health check is nginx Plus only.** The `health_check` directive is not available in open-source nginx. [VERIFIED: nginx.org official docs]

---

## Pattern 5: Docker-Compose Healthcheck Flip

**In `docker-compose.yml`** — the `backend` service has no `healthcheck` section today (only postgres and redis do). Add:

```yaml
backend:
  # ... existing config ...
  healthcheck:
    test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready')"]
    interval: 5s
    timeout: 5s
    retries: 20
    start_period: 30s
```

**In `docker-compose.ci.yml`** — the `backend` service ALREADY has a healthcheck hitting `/health`. Change the URL from `/health` to `/ready`:

```yaml
# Before:
test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
# After:
test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready')"]
```

The CI compose also has `depends_on: backend: condition: service_healthy` on the frontend service — this will now wait for the backend to pass `/ready` (Postgres + Redis both up) before starting the frontend. This is correct for CI. [VERIFIED: docker-compose.ci.yml read directly]

**Important:** `docker-compose.yml` (dev) does not currently have a backend healthcheck — the `depends_on` on `frontend` only depends on `backend` with no condition. The nginx and frontend services also depend on `backend` with no condition. Adding the healthcheck to dev compose introduces the healthcheck but does not change any `depends_on` semantics unless those are also updated. The planner should decide whether to also add `condition: service_healthy` to the dev nginx/frontend depends_on — it would slow dev startup but improve correctness. [ASSUMED — check if this is desired vs. leaving dev depends_on unconditioned]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON log rendering | Custom JSON serializer | `structlog.processors.JSONRenderer(serializer=orjson.dumps)` | orjson is already a dep; handles datetime, UUID, bytes correctly |
| Stdlib log routing | Custom logging.Handler subclass | `structlog.stdlib.ProcessorFormatter` + `foreign_pre_chain` | Official structlog mechanism; handles `_record` metadata, thread safety |
| Sensitive field scrubbing | Regex on the final JSON string | Custom processor in the chain BEFORE renderer | Processor operates on the dict; no parsing overhead, no false positives |
| Request-ID generation | Custom PRNG or timestamp-based ID | `str(uuid.uuid4())` | UUID4 is collision-resistant, format universally understood |
| Probe timeout enforcement | `socket_timeout` configuration | `asyncio.wait_for(coro, 0.5)` | `socket_timeout=2.0` is already set on the Redis client (too loose); wait_for enforces the tighter bound regardless of driver settings |

**Key insight:** The structlog `ProcessorFormatter` + `foreign_pre_chain` combination is specifically designed for this "route everything through one chain" problem. Do not implement a custom `logging.Formatter` subclass or try to intercept uvicorn logs at a lower level.

---

## Common Pitfalls

### Pitfall 1: Using `HTTPException` for `/ready` 503 Body Shape

**What goes wrong:** `raise HTTPException(status_code=503, detail={"status":"not_ready",...})` wraps the body in `{"detail": {"status":"not_ready",...}}`. The response contract (D-05) expects the body at the top level, not nested under `"detail"`.
**Why it happens:** `HTTPException` is the natural FastAPI error idiom, but it always adds the `"detail"` wrapper via the default exception handler.
**How to avoid:** Return `JSONResponse(content={"status": "not_ready", "checks": {...}}, status_code=503)` directly from the route handler.
**Warning signs:** Test for `/ready` when Postgres is down returns 503 with `{"detail": {"status": "not_ready", ...}}` — extra nesting is the tell.

### Pitfall 2: Forgetting `remove_processors_meta` in ProcessorFormatter

**What goes wrong:** Log output contains `_record` (a `logging.LogRecord` object) and `_from_structlog` (a bool) as fields in the JSON output — noise/breakage in log consumers.
**Why it happens:** `ProcessorFormatter` injects these internal keys for processors to introspect; they must be stripped before the renderer.
**How to avoid:** Always include `structlog.stdlib.ProcessorFormatter.remove_processors_meta` as the FIRST processor in `ProcessorFormatter(processors=[...])`.
**Warning signs:** JSON log lines contain `"_record": "..."` or `"_from_structlog": true/false`.

### Pitfall 3: Assuming nginx Passive Ejection Works with a Single Backend

**What goes wrong:** Operator expects that when `/ready` starts returning 503, nginx will stop sending traffic to the backend. In a single-server upstream group, this does not happen — nginx ignores `max_fails` / `fail_timeout` for single-server groups.
**Why it happens:** The nginx docs mention this limitation only briefly; it is easy to miss.
**How to avoid:** The docs section (D-20) must state this explicitly. The compose healthcheck + container restart policy is the actual availability gate.
**Warning signs:** Backend is returning 503 from `/ready` but nginx is still proxying requests to it — this is expected behavior, not a bug.
**Source:** [VERIFIED: nginx.org/en/docs/http/ngx_http_upstream_module.html]

### Pitfall 4: `asyncio.wait_for` Cancels the Inner Task on Timeout

**What goes wrong:** When `asyncio.wait_for(session.execute(text("SELECT 1")), timeout=0.5)` times out, it cancels the inner coroutine. An in-flight SQLAlchemy session may be in an inconsistent state — trying to use the same session object after the timeout will raise `InvalidRequestError`.
**Why it happens:** `asyncio.wait_for` cancels the wrapped task; SQLAlchemy async sessions track internal state that may be corrupted by cancellation mid-operation.
**How to avoid:** The probe uses `async_session_factory()` as a context manager (opens a fresh session per probe call, closes it on exit), so the cancelled session is discarded rather than returned to the pool. This is the pattern from `get_db()` in `db/session.py`. Confirm the probe opens its own `async with async_session_factory() as session:` block.
**Warning signs:** `sqlalchemy.exc.InvalidRequestError: This session is in 'closed' state` appearing in readiness probe logs.

### Pitfall 5: `structlog.configure()` Called Multiple Times / After First Logger Use

**What goes wrong:** Calling `configure_logging()` after `structlog.get_logger()` has been called and `cache_logger_on_first_use=True` was set means the configuration change is silently ignored — existing bound loggers use the cached (old) configuration.
**Why it happens:** `cache_logger_on_first_use=True` freezes the config after the first bound logger is created. The module-level `logger = structlog.get_logger()` in `main.py` (line 34) runs at import time.
**How to avoid:** Call `configure_logging()` as early as possible — before `create_app()` runs any `get_logger()` calls, or before `lifespan` begins. The safest pattern: call it at the module level in `logging.py` itself (not in a function), or call it as the very first statement inside `lifespan()` before anything else.
**Warning signs:** Logs in production are still human-readable (ConsoleRenderer) instead of JSON — the renderer config was applied after caching.

### Pitfall 6: Redaction Processor Mutates the Original Event Dict

**What goes wrong:** The redaction processor modifies the event dict in place. If the dict is shared between the structlog and stdlib processing paths (it is not, normally), mutations could propagate unexpectedly.
**Why it happens:** structlog processors receive `event_dict` by reference. Mutating keys is the documented pattern — this is intentional.
**How to avoid:** The pattern `event_dict[key] = "[REDACTED]"` is correct and safe. Do NOT iterate `event_dict.items()` while mutating it — iterate over `list(event_dict.keys())` or the frozen `SENSITIVE_KEYS` set intersection with a copy.
**Warning signs:** `RuntimeError: dictionary changed size during iteration`.

### Pitfall 7: `_ProbePathFilter` Suppresses Failed `/ready` Log Lines

**What goes wrong:** The stdlib filter on `uvicorn.access` suppresses all records containing `/ready`. But the `logger.error("readiness_check_failed")` comes from the structlog logger in the route handler — it passes through structlog's processor chain, NOT uvicorn.access. These are different loggers.
**Why it happens:** Confusing the uvicorn access log (one record per HTTP request, emitted by uvicorn's access logger) with the application logger (emitted by `structlog.get_logger()` in the route handler).
**How to avoid:** The `_ProbePathFilter` on `uvicorn.access` only suppresses the access log line "GET /ready HTTP/1.1 503" — it does NOT suppress the `readiness_check_failed` event from the app logger. Both are correct behaviors.
**Warning signs:** Failed `/ready` calls produce zero log output — would indicate the filter was accidentally applied to the root logger or the app structlog logger.

---

## Runtime State Inventory

This is a greenfield additive phase (new routes, new module, config file changes). No rename/refactor involved. Section not applicable.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | asyncio.wait_for TimeoutError behavior | Assumed present (Docker image) | 3.12 per pyproject.toml | — |
| structlog >=24.0 | configure_logging(), ProcessorFormatter | Declared in pyproject.toml | >=24.0 | — |
| orjson >=3.10 | JSONRenderer serializer | Declared in pyproject.toml | >=3.10 | Fall back to stdlib json (slower) |
| Redis (running) | /ready probe, test suite | Running in Docker Compose | 7-alpine | Tests mock app.state.redis |
| Postgres (running) | /ready probe, test suite | Running in Docker Compose | 16-alpine | Tests mock async_session_factory |
| open-source nginx | Upstream passive health check | Running in Docker Compose | alpine | — |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.24+ |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"`, `testpaths = ["tests"]` |
| Quick run command | `cd backend && pytest tests/test_health_observability.py -x` |
| Full suite command | `cd backend && pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-07-01 | `GET /health` returns 200 with correct body regardless of DB/Redis state | unit (middleware-level, no deps) | `pytest tests/test_health_observability.py::test_health_always_200 -x` | Wave 0 |
| PROD-07-02 | `GET /ready` returns 200 with per-dep body when both DB and Redis are healthy | integration (single_app fixture) | `pytest tests/test_health_observability.py::test_ready_200_both_up -x` | Wave 0 |
| PROD-07-02 | `GET /ready` returns 503 when Postgres is down (mocked) | unit (monkeypatch session) | `pytest tests/test_health_observability.py::test_ready_503_postgres_down -x` | Wave 0 |
| PROD-07-02 | `GET /ready` returns 503 when Redis is down (mocked) | unit (monkeypatch app.state.redis) | `pytest tests/test_health_observability.py::test_ready_503_redis_down -x` | Wave 0 |
| PROD-07-02 | `/ready` timeout path — slow dep triggers `ok:false, error:"timeout"` | unit (asyncio.sleep mock) | `pytest tests/test_health_observability.py::test_ready_503_timeout_path -x` | Wave 0 |
| PROD-07-04 | JSON renderer selected when ENVIRONMENT=production | unit (monkeypatch settings) | `pytest tests/test_health_observability.py::test_logging_json_in_production -x` | Wave 0 |
| PROD-07-04 | ConsoleRenderer selected in dev | unit (monkeypatch settings) | `pytest tests/test_health_observability.py::test_logging_console_in_dev -x` | Wave 0 |
| D-13/D-14 | X-Request-ID echoed; inbound sanitized value honored; invalid replaced with UUID4 | unit (middleware dispatch) | `pytest tests/test_health_observability.py::test_request_id_middleware -x` | Wave 0 |
| D-17 | Redaction processor scrubs sensitive keys | unit (processor direct call) | `pytest tests/test_health_observability.py::test_redact_sensitive_keys -x` | Wave 0 |

### Mock Strategy (per D-21)

**Postgres down:** The `/ready` probe opens a fresh `async with async_session_factory() as session` — override this via `monkeypatch` on `app.db.session.async_session_factory` to raise `ConnectionRefusedError` or similar. Alternatively, use `AsyncMock` to replace the session's `execute` method. The `single_app` fixture (from conftest.py) yields `(client, app)` with lifespan running — after lifespan runs, monkeypatch `app.state.redis` or the session factory on the live `app` object.

**Redis down:** `monkeypatch.setattr(app.state.redis, "ping", boom_ping)` where `boom_ping` raises `RedisConnectionError`. This is the same pattern used in `test_rate_limit.py` for `pipeline`.

**Timeout path:** Replace the probe coroutine with one that does `await asyncio.sleep(10)` — `asyncio.wait_for` with `timeout=0.5` will raise `TimeoutError`.

**Renderer test:** `structlog.testing.capture_logs()` captures log output with processors bypassed. For renderer selection testing, monkeypatch `settings.environment` to `"production"` or `"development"` before calling `configure_logging()`, then assert the formatter class used on the root handler.

**Existing pattern in codebase:**
```python
# From test_rate_limit.py — established pattern for mocking app.state.redis after lifespan
client, app = single_app  # lifespan has run, app.state.redis is set
def boom_pipeline(*args, **kwargs):
    raise RedisConnectionError("simulated outage")
monkeypatch.setattr(app.state.redis, "pipeline", boom_pipeline)
```

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_health_observability.py -x`
- **Per wave merge:** `cd backend && pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_health_observability.py` — covers all PROD-07-01/02/04, D-13, D-14, D-17 test cases above
- [ ] `backend/app/logging.py` — the new module itself (needed before tests can import it)

*(No gaps in existing test infrastructure — conftest.py `single_app` fixture is sufficient for integration tests; `structlog.testing.capture_logs` is sufficient for unit-level log assertions)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | /health and /ready are public endpoints by design (D-10) |
| V3 Session Management | no | Probe endpoints carry no session |
| V4 Access Control | no | Probe body contains no sensitive data (ok/latency/error-class only) |
| V5 Input Validation | yes | X-Request-ID inbound validation: len ≤128, charset `[A-Za-z0-9._-]` (D-14) |
| V6 Cryptography | no | No crypto in this phase |
| V8 Data Protection | yes | Redaction processor (D-17) prevents key material in logs |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Log injection via unsanitized event keys | Tampering | structlog JSON rendering escapes values; redaction processor strips known-sensitive keys before render |
| X-Request-ID header injection | Tampering | Charset + length validation before accepting inbound header (D-14); structlog JSON encoding prevents further injection |
| Information disclosure via /ready body | Information Disclosure | Body contains only `ok`/`latency_ms`/`error`-class; no connection strings, credentials, or stack traces |
| Probe endpoint DoS | DoS | nginx rate limiting (`zone=api`) already applies; `/ready` runs fast (500ms max per dep) |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| structlog with no `configure()` call (library defaults) | Explicit `configure_logging()` with ProcessorFormatter | Phase 7 | Unifies uvicorn + app logs into one stream; enables JSON in prod |
| Single `/health` endpoint for both liveness and readiness | Split `/health` (liveness) + `/ready` (readiness) | Phase 7 | Allows load balancers / compose to distinguish starting-from-broken |
| nginx locations with inline `proxy_pass http://backend:8000/...` | Named `upstream backend {}` block + locations reference the upstream name | Phase 7 | Enables passive ejection (when >1 server added later); cleaner config |
| docker-compose healthcheck hits `/health` (CI only) | Healthcheck hits `/ready` (both CI and dev) | Phase 7 | Compose correctly waits for DB+Redis to be reachable before marking backend healthy |

**Deprecated/outdated:**
- `logging.basicConfig()` in `backend/app/enrich_assets.py`: this is a standalone script, not the app server — it is outside Phase 7 scope but may conflict if `enrich_assets` is ever run in the same process. Note for planner: do not touch this file.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Starlette `add_middleware()` wraps in reverse order (last-added = outermost); RequestIdMiddleware added last runs first | Pattern 3 | Middleware could run after rate limiter and security headers, meaning those handlers don't have request_id in context. Low risk — request_id is useful for readiness probe and API routes; ordering relative to security headers is not security-critical. |
| A2 | Dev `docker-compose.yml` does not need `condition: service_healthy` added to nginx/frontend depends_on — leaving it unconditioned is acceptable for dev | Pattern 5 | If Postgres/Redis start slowly in dev and the backend /ready check fails initially, nginx might start and briefly fail to proxy — but compose restart will recover it. Planner should confirm intent. |
| A3 | `configure_logging()` should be called before the first `structlog.get_logger()` call — placement at top of `lifespan()` is sufficient because the module-level `logger = structlog.get_logger()` at line 34 does not cache until first use IF `cache_logger_on_first_use` is set after the fact | Pattern 1 (Pitfall 5) | If the cache has already been set before `configure_logging()` runs, renderers in prod may default to the library's ConsoleRenderer. Mitigation: call `structlog.reset_defaults()` at the start of `configure_logging()`, or call `configure_logging()` at module-level in `logging.py` rather than in a function. The planner should pick the call-site carefully. |

---

## Open Questions

1. **configure_logging() call-site ordering vs module-level logger caching**
   - What we know: `main.py` line 34 creates `logger = structlog.get_logger()` at module import time. With `cache_logger_on_first_use=True`, calling `configure_logging()` inside `lifespan()` may happen after the logger is already cached.
   - What's unclear: Does `structlog.get_logger()` at module level actually trigger caching, or is caching deferred until the first `.info()`/`.debug()` call on the bound logger?
   - Recommendation: The planner should add a `structlog.reset_defaults()` call at the start of `configure_logging()` to guarantee a clean slate regardless of import order, or move the call to module-level in `logging.py`. Document the chosen approach clearly in the code.

2. **Dev compose nginx/frontend `depends_on` condition**
   - What we know: Currently no `condition: service_healthy` for the backend in dev compose. Adding a backend healthcheck will make the service emit health status but won't automatically gate other services.
   - What's unclear: Is the desired UX to make dev startup wait for Postgres+Redis to be up before nginx starts? This adds ~10-30s to `docker compose up` in dev.
   - Recommendation: Leave dev `depends_on` unconditioned for now; CI already has the condition; document the asymmetry.

3. **Runbook doc placement (D-20)**
   - What we know: CONTEXT.md suggests `docs/16-security.md` or a new ops doc; `docs/15-monitoring-logging.md` already exists and covers structlog.
   - What's unclear: Whether failure-mode runbook belongs in 15 (monitoring/logging) or 16 (security/compliance) or a new `docs/17a-operations.md`.
   - Recommendation: Append to `docs/15-monitoring-logging.md` under a new "## Failure Modes & Operator Response" section — it's a better semantic fit than security.md.

---

## Sources

### Primary (HIGH confidence)
- `/hynek/structlog` (Context7) — ProcessorFormatter, foreign_pre_chain, wrap_for_formatter, contextvars, make_filtering_bound_logger, capture_logs, redaction
- `/fastapi/fastapi` (Context7) — JSONResponse, HTTPException, status_code 503, is_body_allowed_for_status_code
- `nginx.org/en/docs/http/ngx_http_upstream_module.html` (official nginx docs) — max_fails, fail_timeout, single-server upstream behavior, health_check nginx-Plus-only status
- `backend/app/main.py`, `backend/app/redis_client.py`, `backend/app/db/session.py`, `backend/app/config.py` (live codebase) — existing patterns, middleware structure, lifespan setup
- `nginx/nginx.conf` (live codebase) — current proxy_pass patterns, no upstream block today
- `docker-compose.yml`, `docker-compose.ci.yml` (live codebase) — healthcheck locations, depends_on conditions
- `backend/pyproject.toml` (live codebase) — structlog>=24.0, orjson>=3.10, fastapi>=0.115, asyncio_mode=auto confirmed
- `backend/tests/conftest.py`, `test_rate_limit.py` (live codebase) — mock patterns for app.state.redis, single_app fixture, structlog.testing.capture_logs usage

### Secondary (MEDIUM confidence)
- `docs/15-monitoring-logging.md` (live codebase) — confirms no structlog.configure() exists today; structlog event name conventions

### Tertiary (LOW confidence — none)
No LOW confidence claims in this research.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already declared; versions confirmed from pyproject.toml
- Architecture patterns: HIGH — all code examples derived from official docs + live codebase patterns
- Pitfalls: HIGH — nginx single-server limitation verified from nginx.org; other pitfalls derived from structlog docs + Python 3.12 runtime tests
- nginx passive ejection limitation: HIGH — verified from nginx.org official module docs

**Research date:** 2026-07-10
**Valid until:** 2026-08-10 (structlog 24.x stable; nginx upstream module behavior very stable)
