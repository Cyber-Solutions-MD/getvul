"""Phase 8 — Okta directory-sync connector coverage.

Exercises the pure header/link helpers and the paginated fetch loop via an
httpx.MockTransport (no live Okta). run_okta_sync itself needs a DB + encrypted
creds and is integration-shaped; the pagination + parsing logic here is the
correctness-critical unit.
"""

from __future__ import annotations

import httpx
import pytest

from app.connectors.okta_sync import _auth_headers, _paginated_get, _parse_next_link


def test_parse_next_link_extracts_next_url():
    header = (
        '<https://acme.okta.com/api/v1/users?after=abc>; rel="next", <https://acme.okta.com/api/v1/users>; rel="self"'
    )
    assert _parse_next_link(header) == "https://acme.okta.com/api/v1/users?after=abc"


def test_parse_next_link_none_and_no_next():
    assert _parse_next_link(None) is None
    assert _parse_next_link('<https://acme.okta.com/api/v1/users>; rel="self"') is None


def test_auth_headers_uses_ssws_scheme():
    h = _auth_headers("tok-123")
    assert h["Authorization"] == "SSWS tok-123"
    assert h["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_paginated_get_follows_next_link_across_pages():
    pages = [
        httpx.Response(200, json=[{"id": "1"}, {"id": "2"}], headers={"link": '<https://okta/p2>; rel="next"'}),
        httpx.Response(200, json=[{"id": "3"}]),  # no Link header → last page
    ]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        resp = pages[calls["n"]]
        calls["n"] += 1
        return resp

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        results = await _paginated_get(client, "https://okta/p1", _auth_headers("t"))
    finally:
        await client.aclose()

    assert [r["id"] for r in results] == ["1", "2", "3"]  # accumulated across 2 pages
    assert calls["n"] == 2  # stopped when no next link


@pytest.mark.asyncio
async def test_paginated_get_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await _paginated_get(client, "https://okta/x", {})
    finally:
        await client.aclose()
