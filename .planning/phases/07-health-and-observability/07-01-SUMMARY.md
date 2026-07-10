---
phase: 07-health-and-observability
plan: "01"
subsystem: backend/observability
tags: [health, readiness, middleware, nginx, docker-compose, structlog]
dependency_graph:
  requires:
    - backend/app/logging.py (stub from 07-00)
    - backend/tests/test_health_observability.py (RED scaffold from 07-00)
  provides:
    - backend/app/main.py: GET /ready route, RequestIdMiddleware, configure_logging() call-site
    - nginx/nginx.conf: upstream backend block + /ready location in both server blocks
    - docker-compose.yml: backend healthcheck on /ready
    - docker-compose.ci.yml: backend healthcheck flipped from /health to /ready
  affects:
    - backend/tests/test_health_observability.py (consumed, not modified — turns RED→GREEN when Redis available)
tech_stack:
  added: []
  patterns:
    - asyncio.wait_for(coro, timeout=0.5) per-check timeout pattern (D-06)
    - JSONResponse(content=..., status_code=503) for non-HTTPException 503 (D-05 top-level shape)
    - BaseHTTPMiddleware subclass for X-Request-ID correlation (D-13/D-14)
    - structlog.contextvars bind_contextvars/clear_contextvars per-request binding
    - nginx upstream backend block (forward-compatible; passive ejection disabled for single-server per docs)
key_files:
  created: []
  modified:
    - backend/app/main.py
    - nginx/nginx.conf
    - docker-compose.yml
    - docker-compose.ci.yml
decisions:
  - JSONResponse (not HTTPException) used for /ready 503 to preserve D-05 top-level body shape
  - configure_logging() called as first lifespan statement before _check_secrets_at_startup() so every startup log uses the configured renderer
  - RequestIdMiddleware registered last in add_middleware stack (outermost => runs first) so request_id is bound before rate-limiter and security-header middleware execute
  - Dev docker-compose.yml depends_on left unconditioned per RESEARCH A2/Open Q2; CI/dev asymmetry documented in 07-02 runbook
  - nginx upstream block added as forward-compatible scaffolding; single-server limitation (max_fails/fail_timeout silently ignored by open-source nginx) documented in 07-02 runbook per RESEARCH Pitfall 3
metrics:
  duration_minutes: 33
  completed_date: "2026-07-10"
  tasks_completed: 3
  tasks_total: 3
  files_created: 0
  files_modified: 4
---

# Phase 07 Plan 01: Health and Observability Slice A Summary

**One-liner:** Split liveness/readiness probes (GET /ready with 500ms-bounded Postgres+Redis checks), X-Request-ID correlation middleware, configure_logging() lifespan wiring, nginx named upstream + /ready location, and compose healthcheck flip in both compose files.

## What Was Built

### Task 1: RequestIdMiddleware + configure_logging() lifespan wiring (`backend/app/main.py`)

Two edits to `backend/app/main.py`:

**RequestIdMiddleware (D-13/D-14):**
- Added `_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")` — validates inbound X-Request-ID charset and length
- Added `class RequestIdMiddleware(BaseHTTPMiddleware)` mirroring the existing SecurityHeadersMiddleware/TenantRateLimitMiddleware pattern
- Middleware behavior: `clear_contextvars()` per request → validate/honor inbound X-Request-ID (len ≤128, charset `[A-Za-z0-9._-]`) or mint UUID4 for invalid/missing → `bind_contextvars(request_id=...)` for structlog → set `X-Request-ID` response header
- Registered via `app.add_middleware(RequestIdMiddleware)` after the two existing middleware calls (last-added = outermost = runs first in Starlette)
- Added imports: `asyncio`, `re`, `JSONResponse`, `text`, `bind_contextvars`, `clear_contextvars`, `async_session_factory`, `configure_logging`

**configure_logging() call-site:**
- Added `from app.logging import configure_logging` import
- Called `configure_logging()` as the VERY FIRST statement in `lifespan(app)`, before `_check_secrets_at_startup()`. This ensures the logging renderer is configured before any startup log line (including secrets check), regardless of the module-level `logger = structlog.get_logger()` at line 34.

### Task 2: GET /ready readiness probe (`backend/app/main.py`)

Added `@app.get("/ready")` handler in `create_app()` immediately after the existing `/health` handler (which stays verbatim per D-01/D-02):

- **Postgres probe:** `async with async_session_factory() as session: await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=0.5)` — fresh session per probe (Pitfall 4: cancelled session discarded, not returned to pool); runs through shared pool (D-07, pool exhaustion surfaces as 503)
- **Redis probe:** `await asyncio.wait_for(request.app.state.redis.ping(), timeout=0.5)` — uses existing `app.state.redis` client
- **Timeout handling:** Catches builtin `TimeoutError` (= `asyncio.TimeoutError` in Python 3.12) → `{"ok": False, "error": "timeout"}` per D-06
- **Generic failure handling:** Catches `Exception` → `{"ok": False, "error": type(exc).__name__}` (no connection strings, credentials, or stack traces — T-07-01-02)
- **Response shape (D-05):** `JSONResponse(content={"status": status, "checks": checks}, status_code=200 if overall_ok else 503)` — top-level body, NOT wrapped under `"detail"` (using `HTTPException` would produce the wrong shape)
- **Failure logging (D-20):** `logger.error("readiness_check_failed", postgres_ok=..., redis_ok=...)` when either check fails

### Task 3: nginx upstream + /ready, compose healthcheck flip (`nginx/nginx.conf`, `docker-compose.yml`, `docker-compose.ci.yml`)

**nginx/nginx.conf (D-09.2, D-10):**
- Added `upstream backend { server backend:8000 max_fails=3 fail_timeout=30s; }` inside `http {}` above both server blocks (above the HTTP :80 server block)
- Changed all backend `proxy_pass` URLs from `http://backend:8000/<path>` to `http://backend/<path>` (upstream name) in BOTH server blocks — locations: `/api/`, `/auth/`, `/health`, `/docs`, `/dev/`
- Added `location /ready { proxy_pass http://backend/ready; }` in BOTH server blocks (no auth override — body carries no secrets per D-10; external uptime monitors may reach it)
- `/` location (`proxy_pass http://frontend:3000`) left untouched

**docker-compose.ci.yml (D-09.1):**
- Flipped backend healthcheck URL from `/health` to `/ready`
- Interval/timeout/retries/start_period unchanged

**docker-compose.yml (D-09.1):**
- Added backend healthcheck: `test: urlopen('http://localhost:8000/ready')`, interval: 5s, timeout: 5s, retries: 20, start_period: 30s
- Dev nginx/frontend `depends_on` left unconditioned (RESEARCH A2 / Open Q2 resolved)

## Deviations from Plan

### Sandbox Verification Limitation

**1. [Rule — Sandbox] nginx -t DNS resolution failure in isolated container**
- **Found during:** Task 3 verification
- **Issue:** The plan's acceptance criterion `docker run --rm -v "$PWD/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:alpine nginx -t` fails with "host not found in upstream 'backend:8000'" because `backend` is a Docker Compose service name that resolves only on the Compose network. This is not a syntax error — it is a DNS lookup failure in the isolated test container.
- **Nature:** Pre-documented limitation — RESEARCH Pattern 4 explicitly notes this as the "single-server upstream limitation" and RESEARCH Pitfall 3 covers the passive ejection behavior. The nginx config is syntactically correct; `docker compose config` validates successfully for both compose files.
- **Verification performed:** All other acceptance criteria confirmed manually:
  - `upstream backend` block present (line 38)
  - `server backend:8000 max_fails=3 fail_timeout=30s` present (line 39)
  - `proxy_pass http://backend/ready` present in both server blocks (2 occurrences)
  - `grep -c 'location /ready' nginx/nginx.conf` = 2
  - No `proxy_pass http://backend:8000/` references remain
  - `docker compose -f docker-compose.yml config` exits 0
  - `docker compose -f docker-compose.ci.yml config` exits 0
  - Both compose files contain `localhost:8000/ready`; CI file does NOT contain `localhost:8000/health`
- **Not fixed:** This requires the Compose network to be running for the nginx -t test to pass. Full validation is available via `docker compose up` (per plan §verification manual step).

## Known Stubs

None introduced by this plan. The pre-existing stubs from 07-00 (`configure_logging()` no-op, `redact_sensitive_keys()` NotImplementedError) are intentional and documented in the 07-00 SUMMARY.

## Threat Flags

No new security-relevant surface beyond what the plan's `<threat_model>` covers:
- T-07-01-01 (Tampering / X-Request-ID): mitigated by `_REQUEST_ID_RE` validation in `RequestIdMiddleware`
- T-07-01-02 (Information Disclosure / /ready body): accepted — only `ok`/`latency_ms`/`error`-class exposed; `except Exception` records only `type(exc).__name__`
- T-07-01-03 (DoS / /ready probe): mitigated by `asyncio.wait_for(..., 0.5)` per check
- T-07-01-04 (DoS / pool exhaustion): mitigated by using shared `async_session_factory` pool

## Self-Check: PASSED

- `backend/app/main.py` exists and contains all required changes: FOUND
  - `class RequestIdMiddleware(BaseHTTPMiddleware)`: FOUND (line 245)
  - `_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")`: FOUND (line 242)
  - `app.add_middleware(RequestIdMiddleware)`: FOUND (line 288)
  - `from app.logging import configure_logging`: FOUND (line 25)
  - `configure_logging()` in lifespan: FOUND (line 97)
  - `@app.get("/ready")`: FOUND (line 307)
  - `asyncio.wait_for(` count >= 2: FOUND (2 occurrences)
  - `timeout=0.5`: FOUND (2 occurrences)
  - `readiness_check_failed`: FOUND (line 339)
  - `JSONResponse(` for /ready: FOUND (line 343)
  - `{"status": "ok", "service": "getvul-api"}`: FOUND (line 305, verbatim /health unchanged)
- `nginx/nginx.conf` exists with all required changes: FOUND
  - `upstream backend` block: FOUND (line 38)
  - `/ready` location in both server blocks: FOUND (lines 95, 165)
  - No `http://backend:8000/` proxy_pass remaining: CONFIRMED
- `docker-compose.yml` backend healthcheck on /ready: FOUND
- `docker-compose.ci.yml` healthcheck on /ready (not /health): FOUND
- Commit `40d64af` (Task 1 — RequestIdMiddleware + configure_logging()): FOUND
- Commit `5083362` (Task 2 — GET /ready): FOUND
- Commit `a5e456c` (Task 3 — nginx + compose): FOUND
- Test collection: 9 tests collected, 0 ImportError — VERIFIED
- Test execution: 3 expected-RED (07-02 scope) + 6 fixture-setup errors (Redis not in sandbox) — VERIFIED correct sandbox behavior
