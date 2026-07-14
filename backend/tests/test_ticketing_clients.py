"""Phase 8 — ticketing provider client coverage (Jira, Asana).

Drives each client against an httpx.MockTransport: connection test, issue
creation, project listing. No live Jira/Asana, no credentials.
"""

from __future__ import annotations

import httpx
import pytest

from app.connectors.jira_client import JiraClient
from app.ticketing.asana_client import AsanaClient


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock")


# ── Jira ──────────────────────────────────────────────────────────────────────


def test_jira_api_url_construction():
    c = JiraClient("https://acme.atlassian.net/", "e@x.com", "tok")
    assert c.base_url == "https://acme.atlassian.net"  # trailing slash stripped
    assert c._api_url == "https://acme.atlassian.net/rest/api/2"


@pytest.mark.asyncio
async def test_jira_test_connection_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"displayName": "Ann", "emailAddress": "ann@x.com", "accountId": "acc1"})

    c = JiraClient("https://acme.atlassian.net", "e@x.com", "tok")
    c._client = _mock_client(handler)
    try:
        r = await c.test_connection()
    finally:
        await c._client.aclose()

    assert r == {"success": True, "display_name": "Ann", "email": "ann@x.com", "account_id": "acc1"}


@pytest.mark.asyncio
async def test_jira_test_connection_reports_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    c = JiraClient("https://acme.atlassian.net", "e@x.com", "tok")
    c._client = _mock_client(handler)
    try:
        r = await c.test_connection()
    finally:
        await c._client.aclose()

    assert r["success"] is False
    assert "401" in r["error"]


@pytest.mark.asyncio
async def test_jira_create_issue_returns_key_id_and_browse_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(201, json={"key": "SEC-42", "id": "1001"})

    c = JiraClient("https://acme.atlassian.net", "e@x.com", "tok")
    c._client = _mock_client(handler)
    try:
        r = await c.create_issue(project_key="SEC", summary="Patch me", description="details")
    finally:
        await c._client.aclose()

    assert r["key"] == "SEC-42"
    assert r["id"] == "1001"
    assert r["url"] == "https://acme.atlassian.net/browse/SEC-42"  # browse URL built from base + key


# ── Asana ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_asana_test_connection_returns_user_and_workspaces():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/me":
            return httpx.Response(200, json={"data": {"name": "Ann", "email": "ann@x.com"}})
        if request.url.path == "/workspaces":
            return httpx.Response(200, json={"data": [{"gid": "w1", "name": "Acme"}]})
        return httpx.Response(404)

    c = AsanaClient("tok")
    c.client = _mock_client(handler)
    try:
        r = await c.test_connection()
    finally:
        await c.client.aclose()

    assert r["success"] is True
    assert r["user"] == "Ann"
    assert r["email"] == "ann@x.com"
    assert r["workspaces"] == [{"gid": "w1", "name": "Acme"}]


@pytest.mark.asyncio
async def test_asana_test_connection_auth_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={})

    c = AsanaClient("tok")
    c.client = _mock_client(handler)
    try:
        r = await c.test_connection()
    finally:
        await c.client.aclose()

    assert r["success"] is False
    assert "401" in r["message"]


@pytest.mark.asyncio
async def test_asana_list_projects_excludes_archived():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"gid": "p1", "name": "Active", "archived": False},
                    {"gid": "p2", "name": "Old", "archived": True},  # archived → excluded
                ]
            },
        )

    c = AsanaClient("tok")
    c.client = _mock_client(handler)
    try:
        projects = await c.list_projects("w1")
    finally:
        await c.client.aclose()

    assert projects == [{"gid": "p1", "name": "Active"}]
