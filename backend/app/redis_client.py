"""Redis client accessor for route handlers, and a non-request factory for
callers outside FastAPI's request/response cycle.

`get_redis(request)` is the existing FastAPI dependency route handlers use
to reach the client built once in `app.main.lifespan` and stored on
`app.state.redis`. `get_redis_client()` (Phase 26 Plan 07, AIP-02) is the
SAME construction, exposed as a plain, non-request callable -- for the
connector scheduler's batch pre-warm/poll tasks (`app.ai.batch`, Plan 08),
which run detached from any FastAPI request (dispatched via
`asyncio.create_task`) and have no `Request` object to hand to
`get_redis()`. `app.main`'s lifespan now calls THIS function too (single
construction site) rather than duplicating the `redis.Redis(...)` call --
so `app.state.redis` and every non-request caller build an identical
client.
"""

import redis.asyncio as redis
from fastapi import Request

from app.config import settings


def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis


def get_redis_client() -> redis.Redis:
    """Build a fresh `redis.Redis` client from `settings.redis_url`.

    BlockingConnectionPool (not the default pool): under a concurrent burst
    the default pool raises `MaxConnectionsError` once exhausted -- a
    `RedisError` that would make a caller relying on this client (the rate
    limiter, the AI cache, the batch pre-warm job) fail OPEN, silently
    disabling whatever guard it backs under exactly the load it exists for
    (PROD-01-02, inherited from `app.main`'s original inline lifespan
    construction this function replaces). A blocking pool queues briefly
    for a free connection instead. Genuine Redis outages still fail fast
    (`socket_connect_timeout`) -> fail open.
    """
    return redis.Redis(
        connection_pool=redis.BlockingConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            max_connections=50,
            timeout=5,
        )
    )
