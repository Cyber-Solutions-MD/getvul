# Phase 1: Multi-Replica State - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 01-multi-replica-state
**Areas discussed:** Rate-limiter algorithm, Redis-down behavior, OIDC state TTL, Redis client lifecycle, Multi-replica test approach, Metric emission

---

## Rate-limiter algorithm

| Option | Description | Selected |
|--------|-------------|----------|
| Sliding window via sorted set | Closest to current behavior. ZREMRANGEBYSCORE + ZADD + ZCARD + EXPIRE per request. Precise to ms. ~4 RTTs unless pipelined. | ✓ |
| Fixed-window counter via INCR+EXPIRE | Cheapest: 1 INCR + conditional EXPIRE per request. Allows up to 2× burst at boundaries. | |
| Sliding-window log with Lua script | Same precision as sorted set, atomic in 1 RTT via EVAL. Adds a Lua script. | |
| Token bucket via Lua | Smoothest UX, allows bursts, refills continuously. Different mental model than current 200/60s. | |

**User's choice:** Sliding window via sorted set
**Notes:** Recommended option taken. Closest to current behavior preserves observable semantics.

| Option | Description | Selected |
|--------|-------------|----------|
| Pipeline via MULTI/EXEC | 1 RTT per request. Atomic. Slight code complexity. | ✓ |
| Sequential commands | Simpler code. 4 RTTs per request — could matter under load. | |
| Lua script (atomic + 1 RTT) | Best correctness-per-RTT tradeoff. Adds a small Lua file. | |

**User's choice:** Pipeline via MULTI/EXEC

| Option | Description | Selected |
|--------|-------------|----------|
| Stay global — same constants | No new config surface. Out of scope per no-scope-creep rule. | ✓ |
| Read from tenant.rate_limit_config (JSONB) | Tenants can set their own limits. New schema, validation, admin UI. | |

**User's choice:** Stay global — same constants

---

## Redis-down behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Fail open + log + emit metric | Allow the request, log a warning. Standard for limiters. | ✓ |
| Fail closed (return 503) | Reject all /api/ traffic when Redis is down. Higher correctness, Redis becomes SPOF. | |
| Fall back to in-process counter | Best-effort local counter. More code, fuzzy semantics. | |

**User's choice:** Fail open + log + emit metric

| Option | Description | Selected |
|--------|-------------|----------|
| Fail closed — reject login with 503 | OIDC state is a CSRF defense. Bypass = security bug. | ✓ |
| Fail open — skip state check, log warning | Lets users log in; trades correctness for availability. | |

**User's choice:** Fail closed — reject login with 503

| Option | Description | Selected |
|--------|-------------|----------|
| structlog only | Phase 7 (PROD-07) adds /ready that checks Redis. Keeps Phase 1 scope tight. | ✓ |
| Add a Redis ping to /health | Out of Phase 1 scope per PROD-07; would conflict with Phase 7 design. | |

**User's choice:** structlog only

---

## OIDC state TTL

| Option | Description | Selected |
|--------|-------------|----------|
| 10 minutes | Matches PROD-01-01 ceiling. Comfortable margin for slow IdP, MFA, proxy retries. | ✓ |
| 5 minutes | Tighter. Could fail flows where IdP screen sat idle. | |
| 15 minutes (exceeds PROD-01-01) | Would need REQUIREMENTS.md amended. | |

**User's choice:** 10 minutes

| Option | Description | Selected |
|--------|-------------|----------|
| One-shot — atomic GETDEL on consume | Matches current `.pop()` semantics. Defense in depth. | ✓ |
| Just TTL — GET, no DEL | Simpler; relies on TTL alone. State could be reused within window. | |

**User's choice:** One-shot — atomic GETDEL on consume

---

## Redis client lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Created in lifespan, stored on app.state | FastAPI documented pattern. Test-friendly via dep override. | ✓ |
| Module-level singleton in app/redis_client.py | Lazy init. Simpler call sites, harder to mock. | |
| Per-request connection from a pool | Each request acquires/releases. Overkill for this workload. | |

**User's choice:** Created in lifespan, stored on app.state

| Option | Description | Selected |
|--------|-------------|----------|
| Read from request.app.state.redis | Middleware has direct request access — no DI ceremony. | ✓ |
| Inject via custom factory in app builder | Pass client into middleware constructor at add_middleware time. | |

**User's choice:** Read from request.app.state.redis

| Option | Description | Selected |
|--------|-------------|----------|
| Delete entirely | No backwards-compat shim. Redis is required; matches "no backwards-compatibility hacks". | ✓ |
| Keep as fallback when REDIS_URL is unset | Two code paths. Tests cover both. Rejected by fail-open + log decision. | |

**User's choice:** Delete entirely

---

## Multi-replica test approach

| Option | Description | Selected |
|--------|-------------|----------|
| Two FastAPI app instances + one real Redis | Pytest fixture spawns two `app`s, both pointing at one Redis container. Closest to production. | ✓ |
| Two uvicorn subprocesses + one real Redis | Most realistic but brittle: port allocation, startup waits, slower tests. | |
| Two TestClient instances + fakeredis | No Redis dependency. Risk: fakeredis behavior diverges from real Redis. | |
| Single TestClient + state-isolation assertions only | Doesn't actually prove the multi-replica case — fails spirit of PROD-01-03. | |

**User's choice:** Two FastAPI app instances + one real Redis

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing services.redis in ci.yml | ci.yml already starts redis:7-alpine. Free — point tests at REDIS_URL=redis://localhost:6379/1. | ✓ |
| testcontainers-python | New dev dep. Works locally and CI without changing ci.yml. | |

**User's choice:** Reuse existing services.redis in ci.yml

---

## Metric emission shape

| Option | Description | Selected |
|--------|-------------|----------|
| Structured log event only | `logger.warning('redis_unavailable', subsystem=...)`. No new deps. | ✓ |
| Add prometheus_client + /metrics endpoint | New dep. Real metrics surface but introduces auth/network-policy thinking — Phase 7 concern. | |
| Defer entirely — just structlog warning, no 'metric' verbiage | Cleanest scope cut. | |

**User's choice:** Structured log event only

---

## Claude's Discretion

- Exact module layout for the Redis client (`backend/app/redis_client.py` vs inline in `lifespan`)
- Names for any small response/exception classes
- Whether to introduce a `RateLimiterError` exception or catch `redis.RedisError` directly
- Test fixture location (`conftest.py` vs `test_multi_replica.py`)
- Connection pool size

## Deferred Ideas

- Prometheus `/metrics` endpoint — Phase 7 or its own phase
- Per-user / per-IP rate limits — new capability, backlog
- Tenant-configurable limits — backlog
- Token-bucket / Lua-script algorithms — revisit only if measured perf demands it
- Rate-limit fallback to in-process counter — rejected in favor of fail-open + warn
- Redis Sentinel / Cluster — v1.1+ SCALE bucket
