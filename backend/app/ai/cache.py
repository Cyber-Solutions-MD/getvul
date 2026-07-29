"""Tenant-scoped Redis cache for AI explanations (AI-05) + a per-tenant
in-flight concurrency guard (D-25).

Cross-tenant isolation (Critical Failure Mode #2, T-24-11) is enforced
structurally: `tenant_id` is always the FIRST interpolated segment of the
cache key `ai:explain:{tenant_id}:{resource_type}:{resource_id}:
{record_hash}:{model}:{prompt_version}` — so a tenant_b read can never
collide with a tenant_a write. Proven in `tests/test_ai_cache_isolation.py`
against a real (flushed) Redis, not a mock.

Every function here takes an already-built Redis connection as a parameter
— this module never independently constructs its own client and never
reaches into the FastAPI app state directly. Callers (Plan 04's router)
get that connection via the existing `get_redis(request)` dependency
(`app/redis_client.py`), mirroring the one existing Redis convention in
this codebase (`auth/router.py`'s `oidc:state:{state}` key).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, cast

import redis.asyncio as redis

# ~30 days (D-19) — bounds Redis growth as a safety net on top of the
# content-hash keying; a stale hash surviving 30 days without a fresh
# grounding change is still evicted.
CACHE_TTL_SECONDS = 30 * 24 * 60 * 60

# D-25: bounds how long a single in-flight "explain" call may hold the
# per-tenant concurrency guard before it's assumed abandoned/crashed.
INFLIGHT_TTL_SECONDS = 120


def build_cache_key(
    tenant_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    record_hash_value: str,
    model: str,
    prompt_version: str,
) -> str:
    """Build the tenant-namespaced explanation cache key.

    `tenant_id` is ALWAYS the first interpolated segment — this is the
    entire cross-tenant isolation mechanism (AI-05): two tenants sharing an
    identical (resource_type, resource_id, record_hash, model,
    prompt_version) tuple still land in disjoint keys. `resource_type` is
    included (extending AI-SPEC's original 4-part key) so a vuln ID and a
    remediation-group ID can never collide in the same namespace once D-15
    adds the host/remediation views.
    """
    return f"ai:explain:{tenant_id}:{resource_type}:{resource_id}:{record_hash_value}:{model}:{prompt_version}"


def record_hash(allowlisted_fields: dict[str, Any]) -> str:
    """Sha256 hex digest over ONLY the caller-supplied allowlisted grounding
    fields (D-18) — mirrors `prompt_builder.py::prompt_version`'s hashing
    style (a canonical `json.dumps(..., sort_keys=True)` payload).

    Callers must pass ONLY the grounding fields that should force a fresh
    explanation on change (e.g. `VULN_ALLOWLIST`'s members) — a
    non-grounding field (owner reassignment, internal status flags) must
    never be included here, or an unrelated edit would force a re-spend
    (D-10: no manual regenerate — the hash IS the invalidation signal).
    """
    payload = json.dumps(allowlisted_fields, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def get_cached(redis_client: redis.Redis, key: str) -> dict[str, Any] | None:
    """Return the cached explanation payload, or None on a cache miss
    (including a cross-tenant "miss" — the read never even considers
    another tenant's key since the caller built the fully-namespaced key)."""
    raw = await redis_client.get(key)
    if raw is None:
        return None
    # json.loads() is typed to return Any — cast() documents the contract
    # (set_cached() only ever writes a json.dumps()'d dict) without
    # silencing a genuinely wrong shape at the call site.
    return cast("dict[str, Any]", json.loads(raw))


async def set_cached(
    redis_client: redis.Redis,
    key: str,
    payload: dict[str, Any],
    ttl: int = CACHE_TTL_SECONDS,
) -> None:
    """Cache a validated explanation payload with a TTL (D-19)."""
    await redis_client.set(key, json.dumps(payload), ex=ttl)


async def acquire_inflight(
    redis_client: redis.Redis,
    tenant_id: uuid.UUID,
    ttl: int = INFLIGHT_TTL_SECONDS,
) -> bool:
    """Acquire the per-tenant in-flight concurrency guard (D-25).

    Returns True if this call acquired the lock (no other explain call is
    in flight for this tenant); False if another call already holds it — a
    queue-clicking analyst's second click is turned away rather than
    stampeding the tenant's own Anthropic key with concurrent calls.
    Mirrors the `SETNX`-with-TTL convention already established by
    `auth/router.py`'s `oidc:state:{state}` key (`set(..., ex=..., nx=True)`).
    """
    return bool(await redis_client.set(f"ai:inflight:{tenant_id}", "1", ex=ttl, nx=True))


async def release_inflight(redis_client: redis.Redis, tenant_id: uuid.UUID) -> None:
    """Release the per-tenant in-flight guard — call in a `finally` block
    once the explain call completes (success or failure) so the next
    request isn't blocked for the full TTL."""
    await redis_client.delete(f"ai:inflight:{tenant_id}")
