"""PROD-04-01: CSP + COOP security header tests.

Verifies that backend responses carry:
  - Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'
  - Cross-Origin-Opener-Policy: same-origin

Both headers are emitted by SecurityHeadersMiddleware.dispatch (backend/app/main.py).

The strict CSP covers every route EXCEPT the debug-only interactive docs
(`/docs`, `/redoc`, `/openapi.json`), which are HTML/JS and would render blank
under `default-src 'none'`. Those routes exist only when settings.debug=True;
in production (debug=False) the strict policy covers the entire surface.

Fixtures (from backend/tests/conftest.py):
  - single_app: yields (client, app) with lifespan running (Redis required).

The dispatch-level unit tests below need neither Redis nor Postgres — they
exercise the middleware branch directly, so they catch the docs-exemption logic
that the /health integration test structurally cannot (code-review WR-02).
"""

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app import main as main_mod
from app.main import DOCS_PATHS, SecurityHeadersMiddleware

STRICT_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


def _request(path: str) -> Request:
    """Minimal ASGI GET request for the given path."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
    }
    return Request(scope)


async def _dispatch(path: str) -> Response:
    mw = SecurityHeadersMiddleware(app=lambda scope, receive, send: None)

    async def call_next(_request):
        return Response(status_code=200)

    return await mw.dispatch(_request(path), call_next)


@pytest.mark.asyncio
async def test_csp_and_coop_headers_emitted(single_app):
    """Integration: the documented headers are present on a real JSON route."""
    client, _app = single_app
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("Content-Security-Policy") == STRICT_CSP
    assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"


@pytest.mark.asyncio
async def test_strict_csp_on_api_path():
    """API/JSON paths always carry the strict CSP + COOP."""
    resp = await _dispatch("/api/vulnerabilities")
    assert resp.headers.get("Content-Security-Policy") == STRICT_CSP
    assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"


@pytest.mark.asyncio
async def test_docs_routes_exempt_from_strict_csp_when_debug(monkeypatch):
    """WR-01: in debug mode the docs routes must NOT get default-src 'none',
    or Swagger UI / ReDoc render blank. COOP still applies."""
    monkeypatch.setattr(main_mod.settings, "debug", True)
    for path in DOCS_PATHS:
        resp = await _dispatch(path)
        assert resp.headers.get("Content-Security-Policy") is None, (
            f"{path} must not carry the strict CSP when debug=True"
        )
        assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"


@pytest.mark.asyncio
async def test_docs_paths_get_strict_csp_when_not_debug(monkeypatch):
    """In production (debug=False) the docs routes are unmounted, so even a
    request to /docs falls under the strict policy — no exemption leaks to prod."""
    monkeypatch.setattr(main_mod.settings, "debug", False)
    resp = await _dispatch("/docs")
    assert resp.headers.get("Content-Security-Policy") == STRICT_CSP
