"""Phase 8 — directory connector coverage (Azure Entra, Google Workspace).

Drives each connector's fetch_users() against an httpx.MockTransport, asserting
the raw provider payload normalizes correctly (email casing, org → dept/title,
active flag, guest filtering). No live Graph/Directory API, no credentials.
"""

from __future__ import annotations

import httpx
import pytest

from app.connectors.azure_entra import AzureEntraConnector
from app.connectors.google_workspace import GoogleWorkspaceConnector


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock")


@pytest.mark.asyncio
async def test_azure_fetch_users_normalizes_and_filters_guests():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "1",
                        "displayName": "Ann A",
                        "mail": "Ann@Acme.com",
                        "department": "Eng",
                        "jobTitle": "SWE",
                        "accountEnabled": True,
                    },
                    {"id": "2", "displayName": "Guest", "userPrincipalName": "guest#EXT#@acme.com"},  # external → skip
                    {"id": "3", "displayName": "No Email"},  # no email → skip
                ]
            },
        )

    conn = AzureEntraConnector()
    conn.client = _mock_client(handler)
    try:
        users = await conn.fetch_users()
    finally:
        await conn.client.aclose()

    assert len(users) == 1  # guest + no-email filtered out
    u = users[0]
    assert u.email == "ann@acme.com"  # lowercased
    assert u.name == "Ann A"
    assert u.department == "Eng"
    assert u.job_title == "SWE"
    assert u.is_active is True
    assert u.azure_id == "1"


@pytest.mark.asyncio
async def test_azure_fetch_users_empty_when_no_client():
    conn = AzureEntraConnector()
    conn.client = None
    assert await conn.fetch_users() == []


@pytest.mark.asyncio
async def test_google_fetch_users_maps_orgs_and_suspended():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "users": [
                    {
                        "primaryEmail": "bob@acme.com",
                        "name": {"givenName": "Bob", "familyName": "B"},
                        "organizations": [{"department": "IT", "title": "Admin"}],
                        "suspended": False,
                    },
                    {
                        "primaryEmail": "sus@acme.com",
                        "name": {"givenName": "Sus", "familyName": "P"},
                        "suspended": True,
                    },
                ]
            },
        )

    conn = GoogleWorkspaceConnector()
    conn.domain = "acme.com"
    conn.client = _mock_client(handler)
    try:
        users = await conn.fetch_users()
    finally:
        await conn.client.aclose()

    by_email = {u.email: u for u in users}
    assert set(by_email) == {"bob@acme.com", "sus@acme.com"}
    assert by_email["bob@acme.com"].name == "Bob B"
    assert by_email["bob@acme.com"].department == "IT"
    assert by_email["bob@acme.com"].job_title == "Admin"
    assert by_email["bob@acme.com"].is_active is True
    assert by_email["sus@acme.com"].is_active is False  # suspended → inactive


@pytest.mark.asyncio
async def test_google_fetch_users_error_status_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    conn = GoogleWorkspaceConnector()
    conn.domain = "acme.com"
    conn.client = _mock_client(handler)
    try:
        assert await conn.fetch_users() == []  # non-200 → logged + empty, no crash
    finally:
        await conn.client.aclose()
