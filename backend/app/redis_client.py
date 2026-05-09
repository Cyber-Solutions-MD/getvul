"""Redis client accessor for route handlers.

The client itself is built once in `app.main.lifespan` and stored on
`app.state.redis`. This module exposes a thin FastAPI dependency that
hands the client to route handlers without importing `app.main` at
module scope (which would risk a circular import).
"""

import redis.asyncio as redis
from fastapi import Request


def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis
