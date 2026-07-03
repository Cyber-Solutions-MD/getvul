"""PROD-04-01: CSP + COOP security header presence tests.

Verifies that every backend response carries:
  - Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'
  - Cross-Origin-Opener-Policy: same-origin

Both headers are emitted by SecurityHeadersMiddleware.dispatch (backend/app/main.py).
The /health endpoint is unauthenticated and DB-free — no Postgres dependency; only
Redis via the single_app lifespan is required (same pattern as test_rate_limit.py).

Fixtures (from backend/tests/conftest.py):
  - single_app: yields (client, app) with lifespan running; LifespanManager + ASGITransport.
"""

import pytest


@pytest.mark.asyncio
async def test_csp_and_coop_headers_emitted(single_app):
    client, _app = single_app
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("Content-Security-Policy") == (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
