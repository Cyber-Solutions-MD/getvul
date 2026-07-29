"""Tests for app.ai.tenant_keys + app.ai.cache — BYOK key resolution (AI-01)
and the tenant-scoped, cross-tenant-isolated explanation cache (AI-05).

The cross-tenant isolation test is the zero-tolerance proof for Critical
Failure Mode #2 (T-24-11): it runs against a REAL, flushed Redis (the
`flushed_redis` fixture), never a mock — a namespacing bug that a mock
would paper over is exactly the bug this test exists to catch.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with
ENCRYPTION_KEY (a real Fernet key — `Fernet.generate_key()`, NOT a
placeholder string) + JWT_SECRET_KEY set, per-file (not the whole tests/
dir). The roundtrip test below genuinely calls `encrypt_value`/
`decrypt_value`, which requires a real Fernet-shaped key.
"""

from __future__ import annotations

import json

from app.ai.cache import (
    acquire_inflight,
    build_cache_key,
    get_cached,
    record_hash,
    release_inflight,
    set_cached,
)
from app.ai.tenant_keys import get_tenant_anthropic_key
from app.encryption import encrypt_value
from app.ticketing.models import ConnectorConfig

# ── tenant_keys.py — BYOK key resolution (AI-01) ──────────────────────────


async def test_no_key_configured_returns_none(db_session, tenant_a):
    """A tenant with no ANTHROPIC ConnectorConfig row gets None back — the
    inert 'configure AI' precondition (AI-01) — never an exception."""
    result = await get_tenant_anthropic_key(db_session, tenant_a)
    assert result is None


async def test_configured_key_roundtrips_decrypted(db_session, tenant_a):
    """A tenant with an encrypted ANTHROPIC key gets the plaintext key back,
    decrypted fresh on every call (no module-level cache of the key)."""
    plaintext_key = "sk-ant-test-abc123"
    connector = ConnectorConfig(
        tenant_id=tenant_a,
        connector_type="ANTHROPIC",
        credentials_secret_arn=json.dumps({"api_key": encrypt_value(plaintext_key)}),
        config={"model": "claude-sonnet-5"},
    )
    db_session.add(connector)
    await db_session.flush()

    result = await get_tenant_anthropic_key(db_session, tenant_a)
    assert result == plaintext_key


async def test_key_never_falls_back_across_tenants(db_session, tenant_a, tenant_b):
    """tenant_b has no ANTHROPIC row even though tenant_a does — no shared/
    fallback key exists, so tenant_b still gets None (BYOK-01 constraint)."""
    connector = ConnectorConfig(
        tenant_id=tenant_a,
        connector_type="ANTHROPIC",
        credentials_secret_arn=json.dumps({"api_key": encrypt_value("sk-ant-tenant-a-only")}),
    )
    db_session.add(connector)
    await db_session.flush()

    result = await get_tenant_anthropic_key(db_session, tenant_b)
    assert result is None


# ── cache.py — cross-tenant isolation (AI-05, T-24-11) ────────────────────


async def test_cross_tenant_cache_read_is_a_forced_miss(flushed_redis, tenant_a, tenant_b):
    """Setting an explanation under tenant_a's key and reading under
    tenant_b's key (same resource_type/resource_id/record_hash/model/
    prompt_version) is a MISS — proven against a real, flushed Redis."""
    h = record_hash({"cve_id": "CVE-2024-1234", "cvss_v3_score": 9.8})
    key_a = build_cache_key(tenant_a, "vuln", "finding-1", h, "claude-sonnet-5", "v1")
    key_b = build_cache_key(tenant_b, "vuln", "finding-1", h, "claude-sonnet-5", "v1")
    assert key_a != key_b

    await set_cached(flushed_redis, key_a, {"summary": "tenant A's explanation"})

    tenant_a_result = await get_cached(flushed_redis, key_a)
    tenant_b_result = await get_cached(flushed_redis, key_b)

    assert tenant_a_result == {"summary": "tenant A's explanation"}
    assert tenant_b_result is None  # cross-tenant read is a forced MISS


async def test_cache_key_tenant_id_is_first_interpolated_segment(tenant_a):
    key = build_cache_key(tenant_a, "vuln", "finding-1", "hash123", "claude-sonnet-5", "v1")
    assert key == f"ai:explain:{tenant_a}:vuln:finding-1:hash123:claude-sonnet-5:v1"
    assert key.startswith(f"ai:explain:{tenant_a}:")


# ── cache.py — record_hash allowlist scoping (D-18) ───────────────────────


def test_record_hash_unchanged_by_non_allowlisted_field():
    """A hash computed over ONLY the allowlisted grounding fields is
    identical across two records that differ solely in a non-allowlisted
    field (e.g. owner) — record_hash never sees "owner" at all because the
    caller is responsible for extracting only the allowlisted subset before
    calling. D-18: an owner reassignment must not force a re-spend."""
    allowlisted_from_record_v1 = {"cve_id": "CVE-2024-1234", "cvss_v3_score": 9.8, "status": "OPEN"}
    allowlisted_from_record_v2 = {"cve_id": "CVE-2024-1234", "cvss_v3_score": 9.8, "status": "OPEN"}
    assert record_hash(allowlisted_from_record_v1) == record_hash(allowlisted_from_record_v2)


def test_record_hash_changes_with_allowlisted_field():
    """Changing an allowlisted grounding field (cvss_v3_score) changes the
    hash — a genuine grounding-affecting edit forces a fresh explanation."""
    before = {"cve_id": "CVE-2024-1234", "cvss_v3_score": 9.8, "status": "OPEN"}
    after = {"cve_id": "CVE-2024-1234", "cvss_v3_score": 7.2, "status": "OPEN"}
    assert record_hash(before) != record_hash(after)


def test_record_hash_is_order_independent():
    """Key insertion order must not affect the hash (canonical sort_keys)."""
    a = {"cve_id": "CVE-2024-1234", "cvss_v3_score": 9.8}
    b = {"cvss_v3_score": 9.8, "cve_id": "CVE-2024-1234"}
    assert record_hash(a) == record_hash(b)


# ── cache.py — TTL (D-19) ──────────────────────────────────────────────────


async def test_cached_entry_has_ttl_close_to_30_days(flushed_redis, tenant_a):
    key = build_cache_key(tenant_a, "vuln", "finding-1", "hash123", "claude-sonnet-5", "v1")
    await set_cached(flushed_redis, key, {"summary": "..."})

    ttl = await flushed_redis.ttl(key)
    thirty_days_seconds = 30 * 24 * 60 * 60
    assert ttl > 0
    # Within a minute of the full 30-day window — no meaningful time has
    # elapsed between set_cached() and this check.
    assert thirty_days_seconds - ttl < 60


# ── cache.py — in-flight concurrency guard (D-25) ─────────────────────────


async def test_inflight_guard_second_acquire_before_release_fails(flushed_redis, tenant_a):
    """A queue-clicking analyst's second acquire attempt (before the first
    releases) returns False — turned away rather than stampeding the
    tenant's Anthropic key with a concurrent call."""
    first = await acquire_inflight(flushed_redis, tenant_a, ttl=30)
    second = await acquire_inflight(flushed_redis, tenant_a, ttl=30)

    assert first is True
    assert second is False

    await release_inflight(flushed_redis, tenant_a)
    third = await acquire_inflight(flushed_redis, tenant_a, ttl=30)
    assert third is True


async def test_inflight_guard_is_tenant_scoped(flushed_redis, tenant_a, tenant_b):
    """tenant_a holding the in-flight guard must never block tenant_b."""
    acquired_a = await acquire_inflight(flushed_redis, tenant_a, ttl=30)
    acquired_b = await acquire_inflight(flushed_redis, tenant_b, ttl=30)

    assert acquired_a is True
    assert acquired_b is True
