"""Phase 8 — MDM/HR connector coverage (Jamf, Humaans).

Jamf builds its httpx clients inline per call, so its testable pure surface is
the base-URL normalization in __init__. Humaans keeps a `self.client`, so its
people-fetch/normalization is driven via an httpx.MockTransport.
"""

from __future__ import annotations

import httpx
import pytest

from app.connectors.humaans import HumaansConnector
from app.connectors.jamf import JamfConnector


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock")


# ── Jamf — base-URL normalization ─────────────────────────────────────────────


def test_jamf_strips_trailing_api_segment():
    c = JamfConnector("https://acme.jamfcloud.com/api/", "cid", "secret")
    assert c.base_url == "https://acme.jamfcloud.com"  # trailing slash + /api stripped


def test_jamf_strips_trailing_slash_only():
    c = JamfConnector("https://acme.jamfcloud.com/", "cid", "secret")
    assert c.base_url == "https://acme.jamfcloud.com"


def test_jamf_leaves_clean_url_untouched():
    c = JamfConnector("https://acme.jamfcloud.com", "cid", "secret")
    assert c.base_url == "https://acme.jamfcloud.com"


# ── Humaans — people fetch + normalization ────────────────────────────────────


@pytest.mark.asyncio
async def test_humaans_fetch_all_people_normalizes_and_flattens_teams():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "p1",
                        "firstName": "Ann",
                        "lastName": "A",
                        "email": "ann@acme.com",
                        "jobTitle": "SWE",
                        "department": "Eng",
                        "teams": [{"name": "Platform"}, {"name": "Security"}],
                        "github": "annhub",
                    },
                    {"id": "", "firstName": "NoId"},  # missing id → skipped
                ],
                "total": 2,
            },
        )

    conn = HumaansConnector()
    conn.client = _mock_client(handler)
    try:
        people = await conn._fetch_all_people()
    finally:
        await conn.client.aclose()

    assert set(people) == {"p1"}  # empty-id row skipped
    p = people["p1"]
    assert p.email == "ann@acme.com"
    assert p.first_name == "Ann"
    assert p.job_title == "SWE"
    assert p.department == "Eng"
    assert p.teams == ["Platform", "Security"]  # dict teams flattened to names
    assert p.github_handle == "annhub"


@pytest.mark.asyncio
async def test_humaans_paginate_stops_at_total():
    """_paginate walks $skip until it reaches `total`, then stops."""
    pages = [
        httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}], "total": 3}),
        httpx.Response(200, json={"data": [{"id": "c"}], "total": 3}),
    ]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        resp = pages[calls["n"]]
        calls["n"] += 1
        return resp

    conn = HumaansConnector()
    conn.client = _mock_client(handler)
    try:
        items = await conn._paginate("/people")
    finally:
        await conn.client.aclose()

    assert [i["id"] for i in items] == ["a", "b", "c"]  # two pages accumulated
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_humaans_empty_when_no_client():
    conn = HumaansConnector()
    conn.client = None
    assert await conn._fetch_all_people() == {}
