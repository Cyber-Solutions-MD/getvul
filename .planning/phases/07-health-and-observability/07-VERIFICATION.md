---
phase: 07-health-and-observability
verified: 2026-07-10T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 7: Health and Observability Verification Report

**Phase Goal:** Operators and load balancers can distinguish a starting backend from a healthy one, and production logs are machine-parseable.
**Verified:** 2026-07-10
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /health is a no-dependency liveness probe (always 200 if the process is alive) | VERIFIED | `backend/app/main.py:303-305` — route returns `{"status": "ok", "service": "getvul-api"}` with no DB/Redis calls; `test_health_always_200` GREEN |
| 2 | GET /ready checks Postgres SELECT 1 and Redis PING, each with ≤500ms timeout, returns 503 on failure | VERIFIED | `main.py:307-351` — `asyncio.wait_for(..., timeout=0.5)` on both probes; `JSONResponse(status_code=503)` on failure; body top-level shape confirmed; `test_ready_200_both_up`, `test_ready_503_postgres_down`, `test_ready_503_redis_down`, `test_ready_503_timeout_path` all GREEN |
| 3 | Nginx proxy_pass for backend uses /ready for upstream health | VERIFIED | `nginx/nginx.conf:38-40` — `upstream backend { server backend:8000 max_fails=3 fail_timeout=30s; }`; `location /ready` present in both server blocks (HTTP:80 and HTTPS:443) at lines 94-96 and 164-166; all backend proxy_pass use upstream name `http://backend/...` not `http://backend:8000/...` |
| 4 | structlog output is JSON when ENVIRONMENT=production, human-readable in dev | VERIFIED | `backend/app/logging.py:183-186` — `if settings.environment == "production": renderer = JSONRenderer(serializer=_json_serializer)` else `ConsoleRenderer()`; `test_logging_json_in_production` and `test_logging_console_in_dev` GREEN |
| 5 | Failure modes have a documented operator response (DB down → 503 + alert; Redis down → 503 + alert) | VERIFIED | `docs/15-monitoring-logging.md:88-118` — `## Failure Modes & Operator Response` section with Postgres/Redis/timeout symptom table; `readiness_check_failed` log event documented; nginx single-VM limitation explained; CI/dev `depends_on` asymmetry documented |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/main.py` | `/ready` route + `RequestIdMiddleware` + `configure_logging()` call-site | VERIFIED | `/ready` at line 307; `RequestIdMiddleware` class at line 245, registered at line 288; `configure_logging()` called at line 97 (first statement of `lifespan`) |
| `backend/app/logging.py` | `configure_logging()`, `redact_sensitive_keys()`, `_ProbePathFilter` | VERIFIED | 231 lines; all three present; `ProcessorFormatter`, `wrap_for_formatter`, `remove_processors_meta`, `foreign_pre_chain` all present; no `NotImplementedError` remnants |
| `nginx/nginx.conf` | `upstream backend` block + `/ready` location in both server blocks | VERIFIED | `upstream backend` at line 38; `location /ready` in both HTTP and HTTPS blocks (2 occurrences confirmed); no direct `backend:8000` proxy_pass for backend locations |
| `docker-compose.yml` | backend healthcheck on `/ready` | VERIFIED | Line 69: `urlopen('http://localhost:8000/ready', timeout=4)` with `interval: 5s`, `timeout: 5s`, `retries: 20`, `start_period: 60s` |
| `docker-compose.ci.yml` | backend healthcheck flipped from `/health` to `/ready` | VERIFIED | Line 45: `urlopen('http://localhost:8000/ready', timeout=4)` with matching parameters |
| `backend/tests/test_health_observability.py` | 11 test functions; all GREEN | VERIFIED | 488 lines; 11 tests collected and all PASSED in 1.53s |
| `docs/15-monitoring-logging.md` | Failure Modes & Operator Response runbook section | VERIFIED | Lines 88-118: `## Failure Modes & Operator Response` with 3-row symptom table (Postgres down, Redis down, slow dependency); nginx single-server limitation documented; CI/dev asymmetry documented |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main.py /ready handler` | `async_session_factory SELECT 1` | `asyncio.wait_for(session.execute(text("SELECT 1")), timeout=0.5)` | WIRED | `main.py:320-322`; local import of `async_session_factory` inside handler |
| `main.py /ready handler` | `app.state.redis PING` | `asyncio.wait_for(request.app.state.redis.ping(), timeout=0.5)` | WIRED | `main.py:332` |
| `nginx locations` | `upstream backend` | `proxy_pass http://backend/...` | WIRED | All 6 backend locations in both server blocks use `http://backend/` upstream name |
| `main.py lifespan` | `app.logging.configure_logging` | First statement in lifespan | WIRED | `main.py:25` import + `main.py:97` call; `configure_logging()` runs before `_check_secrets_at_startup()` |
| `logging.py configure_logging` | structlog + stdlib root logger | `ProcessorFormatter.wrap_for_formatter` + `foreign_pre_chain` | WIRED | `logging.py:207-212`; formatter attached to root logger at line 223; `uvicorn.access` filter at line 230 |
| `logging.py redact_sensitive_keys` | processor chain (before renderer) | position in `shared_processors` list | WIRED | `logging.py:171` — `redact_sensitive_keys` is last entry in `shared_processors` before the renderer |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `main.py /ready handler` | `checks` dict | `asyncio.wait_for(session.execute(...))` + `redis.ping()` | Yes — live DB/Redis queries at call time | FLOWING |
| `logging.py configure_logging` | log stream | `settings.environment` from `app.config` | Yes — env-gated renderer selection; `orjson.dumps` for JSON | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 11 health/observability tests pass | `.venv/bin/pytest tests/test_health_observability.py -v` | 11 passed, 4 warnings in 1.53s | PASS |
| /health returns 200 with verbatim body | `test_health_always_200` | GREEN | PASS |
| /ready returns 200 when both up | `test_ready_200_both_up` | GREEN (with live Postgres + Redis) | PASS |
| /ready returns 503 on Postgres down | `test_ready_503_postgres_down` | GREEN (monkeypatched) | PASS |
| /ready returns 503 on Redis down | `test_ready_503_redis_down` | GREEN (monkeypatched) | PASS |
| /ready returns 503 on timeout, completes < 1s | `test_ready_503_timeout_path` | GREEN (10s sleep bounded to 0.5s) | PASS |
| JSON log in production | `test_logging_json_in_production` | GREEN | PASS |
| ConsoleRenderer in dev | `test_logging_console_in_dev` | GREEN | PASS |
| X-Request-ID behavior (missing/valid/invalid) | `test_request_id_middleware` | GREEN | PASS |
| Redaction of sensitive keys | `test_redact_sensitive_keys` | GREEN | PASS |
| Redaction — case-insensitive + nested | `test_redact_sensitive_keys_case_insensitive_and_nested` | GREEN (CR-01 fix verified) | PASS |
| ProbePathFilter exact-path match | `test_probe_filter_exact_path_match` | GREEN (WR-01 fix verified) | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROD-07-01 | 07-00, 07-01 | `GET /health` is a liveness probe (no dependencies) | SATISFIED | `main.py:303-305` — returns static JSON body, no DB/Redis calls; `test_health_always_200` GREEN |
| PROD-07-02 | 07-00, 07-01 | `GET /ready` readiness probe with Postgres + Redis checks, ≤500ms timeout, 503 on failure | SATISFIED | `main.py:307-351` — `asyncio.wait_for(..., 0.5)` on both; `JSONResponse(503)`; all 4 ready-related tests GREEN |
| PROD-07-03 | 07-01 | Nginx upstream health check uses `/ready` | SATISFIED | `nginx.conf:38-40, 94-96, 164-166` — `upstream backend` block + `/ready` location in both server blocks |
| PROD-07-04 | 07-00, 07-02 | structlog output is JSON in production (`ENVIRONMENT=production`), env-gated | SATISFIED | `logging.py:183-186`; `test_logging_json_in_production` + `test_logging_console_in_dev` GREEN |

All 4 requirement IDs (PROD-07-01 through PROD-07-04) satisfied with codebase evidence.

**Note on REQUIREMENTS.md traceability table:** The table at line 127-130 of `REQUIREMENTS.md` still shows all four Phase 7 requirements as "Pending" — these should be updated to "Complete" to reflect phase completion. This is a documentation bookkeeping item, not a code defect.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `docs/15-monitoring-logging.md` | 171-172 | "Recommended additions" section lists `PROD-07-01` and `PROD-07-02` as future work to implement | Info | These were the Phase 7 requirements and are now implemented. The "Recommended additions" section is stale and misleads an operator into thinking these probes are still missing. Not a code defect; does not affect runtime behavior. |
| `backend/app/main.py` | 7 | Duplicate uuid import: `import uuid` and `import uuid as _uuid` | Info | Noted in code review as IN-01; non-blocking cleanup |
| `backend/app/main.py` | 134-135 | `except Exception: pass` swallows syslog-config startup failures silently | Info | Noted in code review as IN-03; pre-existing; non-blocking |

No BLOCKER or WARNING-level anti-patterns found that affect Phase 7's goal.

---

## Human Verification Required

None. All success criteria are verifiable programmatically and the Nyquist test suite (11 tests, all GREEN with live Postgres + Redis) provides behavioral coverage for every success criterion.

---

## Gaps Summary

No gaps. All 5 observable truths are VERIFIED, all 7 artifacts are substantive and wired, all 6 key links are connected, and all 4 requirement IDs are satisfied. The 11-test Nyquist suite ran GREEN on live infrastructure.

The only items worth noting (neither blockers nor warnings):

1. **Stale "Recommended additions" in docs** — `docs/15-monitoring-logging.md` lines 171-172 still list PROD-07-01 and PROD-07-02 as post-v1.0 future work. The section predates Phase 7 and was not removed when the runbook was added above it. An operator reading this section bottom-up would see apparent contradictions. Suggest removing those two bullet points in a follow-up commit.

2. **REQUIREMENTS.md traceability table** — still marks PROD-07-01 through PROD-07-04 as "Pending". Should be updated to "Complete" as part of milestone close-out.

3. **SAWarning on timeout test** — `test_ready_503_timeout_path` produces SQLAlchemy pool connection warnings (non-checked-in connection cleaned by GC after timeout cancellation). This is a known and accepted consequence of the timeout-cancellation path; it does not affect correctness.

---

_Verified: 2026-07-10_
_Verifier: Claude (gsd-verifier)_
