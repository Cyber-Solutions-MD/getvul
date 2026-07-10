"""Phase 7 — Health and Observability: RED test scaffold.

This file covers the full D-21 test matrix plus security tests (D-13/D-14
request-id, D-17 redaction). All tests are intentionally RED until the
downstream plans implement the features they assert:

  - 07-01: /ready route + RequestIdMiddleware + configure_logging() call-site
  - 07-02: full structlog configure_logging() implementation

Tests reference exact function names from VALIDATION.md §"Per-Task Verification
Map" so downstream <verify> commands match by name.

Fixtures (from conftest.py):
  - single_app: yields (client, app) with lifespan running and app.state.redis set
  - asyncio_mode = "auto" (pyproject.toml) — write async def without
    @pytest.mark.asyncio
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import pytest
import structlog

from app.logging import configure_logging, redact_sensitive_keys, SENSITIVE_KEYS


# ---------------------------------------------------------------------------
# D-02 / PROD-07-01: liveness probe
# ---------------------------------------------------------------------------


async def test_health_always_200(single_app):
    """GET /health returns 200 with the verbatim D-02 body regardless of state.

    The body must be EXACTLY {"status": "ok", "service": "getvul-api"} — no
    extra keys, no nesting. (PROD-07-01)
    """
    client, app = single_app
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "service": "getvul-api"}, (
        f"Expected verbatim D-02 body; got {body!r}"
    )


# ---------------------------------------------------------------------------
# D-05 / PROD-07-02: readiness probe — happy path
# ---------------------------------------------------------------------------


async def test_ready_200_both_up(single_app):
    """GET /ready returns 200 with per-dep body when DB and Redis are healthy.

    Asserts:
    - status == "ready"
    - checks.postgres.ok is True and latency_ms is present
    - checks.redis.ok is True and latency_ms is present
    - body is TOP-LEVEL shape (no "detail" wrapper — D-05, not HTTPException)

    Requires a reachable Postgres; skips if DB is not available.
    """
    # Guard: skip if Postgres is not reachable (sandbox environments)
    try:
        from sqlalchemy import text
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2.0)
    except Exception:
        pytest.skip("Postgres not reachable — skipping integration test")

    client, app = single_app
    resp = await client.get("/ready")
    assert resp.status_code == 200, (
        f"/ready should return 200 when both deps are healthy; got {resp.status_code}"
    )
    body = resp.json()

    # Top-level shape — must NOT be wrapped under "detail"
    assert "detail" not in body, (
        f"Body must be top-level per D-05; got 'detail' wrapper: {body!r}"
    )
    assert body["status"] == "ready", f"Expected status='ready'; got {body.get('status')!r}"

    postgres_check = body.get("checks", {}).get("postgres", {})
    assert postgres_check.get("ok") is True, (
        f"postgres check must be ok=True; got {postgres_check!r}"
    )
    assert "latency_ms" in postgres_check, (
        f"postgres check must include latency_ms; got {postgres_check!r}"
    )

    redis_check = body.get("checks", {}).get("redis", {})
    assert redis_check.get("ok") is True, (
        f"redis check must be ok=True; got {redis_check!r}"
    )
    assert "latency_ms" in redis_check, (
        f"redis check must include latency_ms; got {redis_check!r}"
    )


# ---------------------------------------------------------------------------
# PROD-07-02: readiness probe — failure paths
# ---------------------------------------------------------------------------


async def test_ready_503_postgres_down(single_app, monkeypatch):
    """GET /ready returns 503 when Postgres is down (mocked).

    Monkeypatches the async_session_factory to raise ConnectionRefusedError so
    the DB probe fails. Asserts body has top-level shape (no "detail" wrapper).
    """
    from app.db import session as session_module
    from unittest.mock import AsyncMock, MagicMock
    import contextlib

    # Build a fake session whose execute() raises immediately
    mock_session = AsyncMock()
    mock_session.execute.side_effect = ConnectionRefusedError("simulated postgres outage")

    # async_session_factory is used as `async with async_session_factory() as session:`
    # We need to replace it with an async context manager that yields the mock session.
    @contextlib.asynccontextmanager
    async def _broken_factory():
        yield mock_session

    monkeypatch.setattr(session_module, "async_session_factory", _broken_factory)

    client, app = single_app
    resp = await client.get("/ready")
    assert resp.status_code == 503, (
        f"/ready must return 503 when Postgres is down; got {resp.status_code}"
    )
    body = resp.json()
    assert "detail" not in body, (
        f"Body must be top-level per D-05; got 'detail' wrapper: {body!r}"
    )
    assert body.get("status") == "not_ready", (
        f"Expected status='not_ready'; got {body.get('status')!r}"
    )
    postgres_check = body.get("checks", {}).get("postgres", {})
    assert postgres_check.get("ok") is False, (
        f"postgres check must be ok=False; got {postgres_check!r}"
    )


async def test_ready_503_redis_down(single_app, monkeypatch):
    """GET /ready returns 503 when Redis is down (mocked).

    Uses the established mock-after-lifespan pattern from test_rate_limit.py:
    monkeypatch app.state.redis.ping after the lifespan has already set it up.
    """
    client, app = single_app

    async def boom_ping(*args, **kwargs):
        raise Exception("simulated redis outage")

    monkeypatch.setattr(app.state.redis, "ping", boom_ping)

    resp = await client.get("/ready")
    assert resp.status_code == 503, (
        f"/ready must return 503 when Redis is down; got {resp.status_code}"
    )
    body = resp.json()
    redis_check = body.get("checks", {}).get("redis", {})
    assert redis_check.get("ok") is False, (
        f"redis check must be ok=False; got {redis_check!r}"
    )


async def test_ready_503_timeout_path(single_app, monkeypatch):
    """GET /ready returns 503 with error='timeout' on the slow-dep path (D-06).

    Replaces app.state.redis.ping with a coroutine that sleeps for 10s.
    asyncio.wait_for(coro, timeout=0.5) fires TimeoutError; the probe sets
    error='timeout' and the overall response is 503.

    The test itself must complete in ~<1s, proving the 0.5s timeout fired
    rather than the 10s sleep.
    """
    client, app = single_app

    async def slow_ping(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(app.state.redis, "ping", slow_ping)

    resp = await client.get("/ready")
    assert resp.status_code == 503, (
        f"/ready must return 503 on timeout; got {resp.status_code}"
    )
    body = resp.json()
    redis_check = body.get("checks", {}).get("redis", {})
    assert redis_check.get("ok") is False, (
        f"redis check must be ok=False on timeout; got {redis_check!r}"
    )
    assert redis_check.get("error") == "timeout", (
        f"redis check error must be 'timeout'; got {redis_check!r}"
    )


# ---------------------------------------------------------------------------
# D-11 / PROD-07-04: structured logging renderer selection
# ---------------------------------------------------------------------------


async def test_logging_json_in_production(monkeypatch):
    """configure_logging() selects JSONRenderer when ENVIRONMENT=production.

    Monkeypatches settings.environment to 'production' and settings.debug to
    False, then calls configure_logging(). Asserts that:
    - The root logger has a handler
    - Its formatter is a structlog.stdlib.ProcessorFormatter
    - Emitting a log line produces parseable JSON containing 'event'

    This test is RED until 07-02 implements the real configure_logging().
    The stub is a no-op (returns immediately), so the formatter assertion fails.
    """
    from app import config as config_module

    # Monkeypatch settings to production mode
    monkeypatch.setattr(config_module.settings, "environment", "production")
    monkeypatch.setattr(config_module.settings, "debug", False)

    # Reset structlog so any prior test config does not bleed in
    structlog.reset_defaults()

    # Reset root logger handlers so we start clean
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    root_logger.handlers = []

    try:
        configure_logging()

        # Assert a handler was configured on the root logger
        assert root_logger.handlers, (
            "configure_logging() must add at least one handler to the root logger"
        )

        formatter = root_logger.handlers[0].formatter
        assert isinstance(formatter, structlog.stdlib.ProcessorFormatter), (
            f"Root handler formatter must be ProcessorFormatter in production; "
            f"got {type(formatter).__name__!r}"
        )

        # Assert JSON output: emit a log line and verify it parses as JSON with 'event'
        import io
        buf = io.StringIO()
        test_handler = logging.StreamHandler(buf)
        test_handler.setFormatter(formatter)

        test_logger = logging.getLogger("test.json_renderer")
        test_logger.addHandler(test_handler)
        test_logger.setLevel(logging.DEBUG)
        try:
            test_logger.info("test_event")
            line = buf.getvalue().strip()
            assert line, "Expected a log line; got nothing"
            parsed = json.loads(line)
            assert "event" in parsed, (
                f"JSON log line must contain 'event' key; got keys: {list(parsed.keys())}"
            )
        finally:
            test_logger.removeHandler(test_handler)
    finally:
        # Restore original handlers to avoid polluting other tests
        root_logger.handlers = original_handlers
        structlog.reset_defaults()


async def test_logging_console_in_dev(monkeypatch):
    """configure_logging() selects ConsoleRenderer when ENVIRONMENT=development.

    Monkeypatches settings.environment to 'development' and settings.debug to
    True, then calls configure_logging(). Asserts that a log line is NOT valid
    JSON (ConsoleRenderer produces human-readable output, not JSON).

    This test is RED until 07-02 implements the real configure_logging().
    """
    from app import config as config_module

    # Monkeypatch settings to dev mode
    monkeypatch.setattr(config_module.settings, "environment", "development")
    monkeypatch.setattr(config_module.settings, "debug", True)

    # Reset structlog so tests 6/7 do not leak config into each other
    structlog.reset_defaults()

    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    root_logger.handlers = []

    try:
        configure_logging()

        # Assert a handler was configured
        assert root_logger.handlers, (
            "configure_logging() must add at least one handler to the root logger"
        )

        formatter = root_logger.handlers[0].formatter
        assert isinstance(formatter, structlog.stdlib.ProcessorFormatter), (
            f"Root handler formatter must be ProcessorFormatter in dev; "
            f"got {type(formatter).__name__!r}"
        )

        # Assert dev path: output must NOT be valid JSON (ConsoleRenderer)
        import io
        buf = io.StringIO()
        test_handler = logging.StreamHandler(buf)
        test_handler.setFormatter(formatter)

        test_logger = logging.getLogger("test.console_renderer")
        test_logger.addHandler(test_handler)
        test_logger.setLevel(logging.DEBUG)
        try:
            test_logger.info("test_event")
            line = buf.getvalue().strip()
            # ConsoleRenderer output is NOT valid JSON
            try:
                json.loads(line)
                raise AssertionError(
                    f"Dev log line must NOT be valid JSON (ConsoleRenderer); got: {line!r}"
                )
            except json.JSONDecodeError:
                pass  # Expected: ConsoleRenderer output is not JSON
        finally:
            test_logger.removeHandler(test_handler)
    finally:
        root_logger.handlers = original_handlers
        structlog.reset_defaults()


# ---------------------------------------------------------------------------
# D-13 / D-14 / PROD-07-04: request-id middleware
# ---------------------------------------------------------------------------


async def test_request_id_middleware(single_app):
    """X-Request-ID is generated, echoed, and invalid inbound is sanitized.

    Three assertions (D-13/D-14):
    (a) No inbound X-Request-ID → response has an auto-generated UUID4-format
        X-Request-ID matching ^[A-Za-z0-9._-]{1,128}$.
    (b) Valid inbound X-Request-ID → response echoes the SAME value.
    (c) Invalid inbound (>128 chars or invalid charset) → response X-Request-ID
        differs from inbound and matches the valid charset regex (proves the
        invalid value was rejected and a UUID4 was minted).

    This test is RED until 07-01 adds the RequestIdMiddleware.
    """
    client, app = single_app
    valid_pattern = re.compile(r'^[A-Za-z0-9._-]{1,128}$')

    # (a) No inbound header → auto-generated
    resp_a = await client.get("/health")
    request_id_a = resp_a.headers.get("X-Request-ID")
    assert request_id_a is not None, (
        "Response must have X-Request-ID header when none was sent"
    )
    assert valid_pattern.match(request_id_a), (
        f"Auto-generated X-Request-ID must match valid charset regex; got {request_id_a!r}"
    )

    # (b) Valid inbound → echoed verbatim
    valid_inbound = "abc-123.ok"
    resp_b = await client.get("/health", headers={"X-Request-ID": valid_inbound})
    request_id_b = resp_b.headers.get("X-Request-ID")
    assert request_id_b == valid_inbound, (
        f"Valid inbound X-Request-ID must be echoed; sent {valid_inbound!r}, got {request_id_b!r}"
    )

    # (c) Invalid inbound (oversized, >128 chars) → rejected, new UUID4 minted
    invalid_inbound = "x" * 200  # 200 chars exceeds the 128-char limit
    resp_c = await client.get("/health", headers={"X-Request-ID": invalid_inbound})
    request_id_c = resp_c.headers.get("X-Request-ID")
    assert request_id_c is not None, (
        "Response must have X-Request-ID header even when inbound was invalid"
    )
    assert request_id_c != invalid_inbound, (
        f"Invalid inbound X-Request-ID must be rejected; got the same value back: {request_id_c!r}"
    )
    assert valid_pattern.match(request_id_c), (
        f"Replacement X-Request-ID must match valid charset regex; got {request_id_c!r}"
    )


# ---------------------------------------------------------------------------
# D-17 / PROD-07-04: redaction processor
# ---------------------------------------------------------------------------


def test_redact_sensitive_keys():
    """redact_sensitive_keys() scrubs D-17 sensitive keys to '[REDACTED]'.

    Direct call to the processor function (not via structlog pipeline).
    Tests:
    - Known sensitive keys ('authorization', 'password', 'api_key') → '[REDACTED]'
    - Non-sensitive key ('user') → untouched
    - Empty dict does not raise

    This test is RED until 07-02 implements the real redact_sensitive_keys().
    The stub raises NotImplementedError, which is the correct RED signal.
    """
    event_dict = {
        "authorization": "Bearer xyz",
        "password": "hunter2",
        "user": "alice",
        "api_key": "sk-123",
    }
    result = redact_sensitive_keys(None, "info", event_dict)

    assert result["authorization"] == "[REDACTED]", (
        f"'authorization' must be redacted; got {result['authorization']!r}"
    )
    assert result["password"] == "[REDACTED]", (
        f"'password' must be redacted; got {result['password']!r}"
    )
    assert result["api_key"] == "[REDACTED]", (
        f"'api_key' must be redacted; got {result['api_key']!r}"
    )
    assert result["user"] == "alice", (
        f"Non-sensitive 'user' must be untouched; got {result['user']!r}"
    )

    # Empty dict must not raise
    empty_result = redact_sensitive_keys(None, "info", {})
    assert empty_result == {}, f"Empty dict must return empty dict; got {empty_result!r}"


def test_redact_sensitive_keys_case_insensitive_and_nested():
    """redact_sensitive_keys() catches title-cased and nested credentials (CR-01).

    The processor also runs over foreign uvicorn records via foreign_pre_chain,
    where HTTP header keys arrive title-cased ('Authorization', 'Cookie') and
    credentials appear nested inside dicts/lists. An exact-case, top-level-only
    scrub would leak these in cleartext.
    """
    event_dict = {
        # Title-cased header keys — must match case-insensitively.
        "Authorization": "Bearer xyz",
        "Cookie": "session=abc",
        # Nested credential inside a sub-dict (e.g. structured request context).
        "request": {"headers": {"Authorization": "Bearer nested"}, "path": "/x"},
        # Credential nested inside a list of dicts.
        "items": [{"token": "sk-deep"}, {"user": "bob"}],
        "user": "alice",
    }
    result = redact_sensitive_keys(None, "info", event_dict)

    assert result["Authorization"] == "[REDACTED]", "title-cased Authorization must redact"
    assert result["Cookie"] == "[REDACTED]", "title-cased Cookie must redact"
    assert result["request"]["headers"]["Authorization"] == "[REDACTED]", (
        f"nested Authorization must redact; got {result['request']['headers']!r}"
    )
    assert result["request"]["path"] == "/x", "non-sensitive nested value must be untouched"
    assert result["items"][0]["token"] == "[REDACTED]", "token nested in list must redact"
    assert result["items"][1]["user"] == "bob", "non-sensitive nested value must be untouched"
    assert result["user"] == "alice", "top-level non-sensitive value must be untouched"


def test_probe_filter_exact_path_match():
    """_ProbePathFilter suppresses exact probe paths only, not substrings (WR-01).

    Substring matching would wrongly drop legitimate traffic like /health-history
    or a request carrying '/ready' in its query string.
    """
    from app.logging import _ProbePathFilter

    probe = _ProbePathFilter()

    def _rec(msg: str) -> logging.LogRecord:
        return logging.LogRecord("uvicorn.access", logging.INFO, __file__, 0, msg, None, None)

    # Exact probe paths → suppressed (filter returns False)
    assert probe.filter(_rec('127.0.0.1:5 - "GET /ready HTTP/1.1" 200')) is False
    assert probe.filter(_rec('127.0.0.1:5 - "GET /health HTTP/1.1" 200')) is False
    # Look-alike / query-carrying paths → kept (filter returns True)
    assert probe.filter(_rec('127.0.0.1:5 - "GET /health-history HTTP/1.1" 200')) is True
    assert probe.filter(_rec('127.0.0.1:5 - "GET /assets?redirect=/ready HTTP/1.1" 200')) is True
    assert probe.filter(_rec('127.0.0.1:5 - "GET /readyz HTTP/1.1" 200')) is True
