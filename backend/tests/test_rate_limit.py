"""PROD-01-02: Redis-backed per-tenant rate limiter unit tests.

Targets each row in .planning/phases/01-multi-replica-state/01-VALIDATION.md
under "Per-Task Verification Map" tasks 01-02-01 through 01-02-06:

  - 01-02-01 → test_limit_enforced
  - 01-02-02 → test_window_slides
  - 01-02-03 → test_per_tenant_isolation
  - 01-02-04 → test_fail_open_on_redis_down
  - 01-02-05 → test_concurrent_burst_respects_limit
  - 01-02-06 → test_doc_parity

Fixtures (from backend/tests/conftest.py):
  - single_app:    yields (client, app) with lifespan running and an httpx
                   AsyncClient routed through ASGITransport. `app.state.redis`
                   is populated by lifespan.
  - flushed_redis: real redis.asyncio client on db=1 with FLUSHDB before/after.
                   Pin assertion guards against accidentally hitting db=0.

Why TEST_ENDPOINT is a non-existent /api/* path:
  The rate-limit middleware (TenantRateLimitMiddleware) runs BEFORE FastAPI
  routing, so any path starting with /api/ exercises the limiter. By choosing
  a path that does not match any route the request short-circuits with a clean
  404 — no get_db, no get_current_user, no Postgres dependency in the unit
  test. _is_allowed() accepts ANY non-429 status (including 404 and 401);
  the contract under test is "did the limiter fire", not "did the handler
  succeed".
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import structlog
from redis.exceptions import ConnectionError as RedisConnectionError

# A non-existent /api/* path: the rate-limit middleware (which runs BEFORE
# routing) still increments the bucket because the path starts with /api/,
# but the eventual response is a clean FastAPI 404 with no Depends evaluation —
# so the route handler's get_db / get_current_user never run, and the test
# does not need a live Postgres. _is_allowed accepts any non-429 response.
TEST_ENDPOINT = "/api/v1/__rate_limit_test__"


def _is_allowed(status_code: int) -> bool:
    """The limiter allows the request if it is NOT 429."""
    return status_code != 429


@pytest.mark.asyncio
async def test_limit_enforced(single_app, flushed_redis):
    """VALIDATION 01-02-01: cap is exactly 200 per 60-second window.

    Setup: clean Redis db=1 (flushed_redis fixture), single app with limiter
    middleware bound to db=1.

    Behavior asserted:
      - 200 sequential GETs against TEST_ENDPOINT all return non-429 (allowed).
      - The 201st request returns HTTP 429 with `Retry-After: 60`.

    This corresponds to "limiter allows N≤200 in window, 429 at 201" in the
    research/test map (PROD-01-02 acceptance #1).
    """
    client, app = single_app
    allowed = 0
    for _ in range(200):
        resp = await client.get(TEST_ENDPOINT)
        if _is_allowed(resp.status_code):
            allowed += 1
    assert allowed == 200, f"expected all 200 to be allowed, got {allowed}"

    blocked = await client.get(TEST_ENDPOINT)
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_window_slides(single_app, flushed_redis):
    """VALIDATION 01-02-02: pruning old entries restores the budget.

    Setup: clean Redis db=1, then issue 5 requests so the sorted-set has 5
    members, then DELETE the ratelimit:anonymous key (a faster equivalent of
    waiting RATE_LIMIT_WINDOW seconds for ZREMRANGEBYSCORE to finish pruning).

    Behavior asserted:
      - After the key is gone, 200 requests succeed again (budget reset).
      - The 201st request returns 429 — the cap still applies in the new
        window, so we have not accidentally disabled the limiter.

    This corresponds to "limiter prunes entries older than window" in the
    research/test map (PROD-01-02 acceptance #2). The ZREMRANGEBYSCORE pipeline
    step is what makes this work in production; deleting the key is the
    test-time stand-in.
    """
    client, app = single_app
    for _ in range(5):
        await client.get(TEST_ENDPOINT)

    # Simulate window slide by deleting the sorted-set entries.
    await flushed_redis.delete("ratelimit:anonymous")

    # Budget is restored.
    for _ in range(200):
        resp = await client.get(TEST_ENDPOINT)
        assert _is_allowed(resp.status_code)
    blocked = await client.get(TEST_ENDPOINT)
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_per_tenant_isolation(single_app, flushed_redis):
    """VALIDATION 01-02-03: tenant A's exhaustion does not affect tenant B.

    Setup: clean Redis db=1, mint two access tokens with distinct tenant_id
    UUIDs (tenant-aaa and tenant-bbb).

    Behavior asserted:
      - 200 requests from tenant A succeed; the 201st returns 429.
      - The very next request from tenant B succeeds (non-429).

    This corresponds to "limiter is per-tenant (tenant A and B independent)"
    in the research/test map (PROD-01-02 acceptance #3). The tenant key in the
    limiter is `payload.tenant_id` extracted by the lightweight JWT decode in
    middleware — DB-free.
    """
    from app.auth.jwt import create_access_token

    client, app = single_app

    # Tenant key for the limiter comes from the JWT payload (lightweight
    # decode in middleware) — the bucket is independent per tenant_id.
    token_a = create_access_token(
        user_id="11111111-1111-1111-1111-111111111111",
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        email="a@example.com",
        role="ADMIN",
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}
    for _ in range(200):
        await client.get(TEST_ENDPOINT, headers=headers_a)
    blocked_a = await client.get(TEST_ENDPOINT, headers=headers_a)
    assert blocked_a.status_code == 429

    # Tenant B's budget is independent.
    token_b = create_access_token(
        user_id="22222222-2222-2222-2222-222222222222",
        tenant_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        email="b@example.com",
        role="ADMIN",
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}
    resp_b = await client.get(TEST_ENDPOINT, headers=headers_b)
    assert _is_allowed(resp_b.status_code), (
        f"tenant B should be unaffected by tenant A's exhaustion; got {resp_b.status_code}"
    )


@pytest.mark.asyncio
async def test_fail_open_on_redis_down(single_app, monkeypatch):
    """VALIDATION 01-02-04: fail OPEN with structured warning on Redis outage.

    Setup: monkeypatch `app.state.redis.pipeline` to raise
    redis.exceptions.ConnectionError so the limiter's `try ... except
    RedisError` branch fires.

    Behavior asserted:
      - The request status is NOT 429 (limiter let traffic through — D-05).
      - structlog captured a warning with event=`redis_unavailable`,
        subsystem=`rate_limiter`, and error containing the simulated message.

    This corresponds to "limiter fails OPEN on Redis ConnectionError + emits
    warning log" in the research/test map (PROD-01-02 acceptance #4). The
    contract is operational: rate limiting is a safety valve (D-05), not a
    security boundary, so an outage favors availability over precision while
    surfacing the gap to operators via structured logs (D-19).
    """
    client, app = single_app

    def boom_pipeline(*args, **kwargs):
        raise RedisConnectionError("simulated outage")

    monkeypatch.setattr(app.state.redis, "pipeline", boom_pipeline)

    # Reset the module-level logger to a fresh proxy so capture_logs() can
    # intercept it. configure_logging() sets cache_logger_on_first_use=True, so
    # once app.main.logger is bound (by an earlier test in a full run) it ignores
    # capture_logs' processor swap and nothing is captured. A fresh get_logger()
    # proxy binds lazily to the LogCapture processor on first use in the context.
    from app import main as _app_main

    monkeypatch.setattr(_app_main, "logger", structlog.get_logger())

    with structlog.testing.capture_logs() as captured:
        resp = await client.get(TEST_ENDPOINT)

    assert resp.status_code != 429, "limiter must fail open on Redis outage"
    events = [e for e in captured if e.get("event") == "redis_unavailable"]
    assert events, f"expected a redis_unavailable warning; captured: {captured}"
    assert events[0].get("subsystem") == "rate_limiter"
    assert "simulated outage" in events[0].get("error", "")


@pytest.mark.asyncio
async def test_concurrent_burst_respects_limit(single_app, flushed_redis):
    """VALIDATION 01-02-05: 250 concurrent requests resolve to exactly 200/50.

    Setup: clean Redis db=1, fire 250 GETs through asyncio.gather so the
    requests interleave at sub-millisecond scale.

    Behavior asserted:
      - Exactly 200 responses are non-429 (allowed).
      - Exactly 50 responses are 429 (blocked at cap).

    This corresponds to "200 concurrent requests observe correct cap (sub-ms)"
    in the research/test map (PROD-01-02 acceptance #5). Critically, this test
    is the explicit guard against RESEARCH Pitfall 1: if the ZADD member were
    `now_ms` alone (instead of `f"{now_ms}:{uuid.uuid4().hex[:8]}"`), two
    requests in the same millisecond would produce identical (member, score)
    and the second ZADD would be a no-op — the count would silently undershoot
    the actual request volume and `allowed > 200` would slip through. The
    uuid-suffix mitigation makes every member unique even under perfect
    sub-ms collisions.
    """
    client, app = single_app

    async def one():
        return await client.get(TEST_ENDPOINT)

    responses = await asyncio.gather(*(one() for _ in range(250)))
    blocked = sum(1 for r in responses if r.status_code == 429)
    allowed = sum(1 for r in responses if _is_allowed(r.status_code))
    assert allowed == 200, (
        f"expected exactly 200 allowed (defeating ZADD duplicate-member bug); got allowed={allowed}, blocked={blocked}"
    )
    assert blocked == 50


def test_doc_parity():
    """VALIDATION 01-02-06: doc/security.md:20 matches the new code semantics.

    The doc has long claimed "Redis-backed" but the implementation was
    in-process until this plan landed. D-20 mandates the doc reads
    "Redis-backed sliding window" verbatim — both because that wording is now
    accurate and because future doc-parity drift checks (Phase 4 / PROD-04)
    will diff this exact substring.

    Behavior asserted:
      - doc/security.md line 20 contains the substring
        `"Redis-backed sliding window"`.

    This is exercised by Task 3 of the plan (the actual doc edit). Task 2's
    automated verify deselects this test so the suite passes when only the
    code lands; Task 3's verify covers it explicitly. After Task 3 the full
    PROD-01-02 suite (all 6 tests) is green.
    """
    # Docs were reorganised from doc/security.md → docs/16-security.md; assert the
    # substring anywhere in the file rather than a brittle hardcoded line number.
    repo_root = Path(__file__).resolve().parents[2]
    sec_doc = (repo_root / "docs" / "16-security.md").read_text()
    assert "Redis-backed sliding window" in sec_doc, (
        "docs/16-security.md must describe rate limiting as a 'Redis-backed sliding window'"
    )
