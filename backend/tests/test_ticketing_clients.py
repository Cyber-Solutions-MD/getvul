"""Phase 8 — ticketing provider client coverage (Jira, Asana), extended in
Phase 23 Plan 03 with the Jira comment/transition/close methods ported from
the deleted legacy connectors Jira client (D-08), and the new GitHub
add_comment/close_issue methods (D-12).

Drives each client against an httpx.MockTransport: connection test, issue
creation, comment posting, and status transitions. No live Jira/Asana/GitHub,
no credentials.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.ticketing.asana_client import AsanaClient
from app.ticketing.github_client import GitHubClient
from app.ticketing.jira_client import JiraClient


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock")


# ── Jira (canonical v3/ADF client) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_jira_test_connection_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"displayName": "Ann", "emailAddress": "ann@x.com", "accountId": "acc1"})

    c = JiraClient(email="e@x.com", api_token="tok", base_url="https://acme.atlassian.net")
    c._client = _mock_client(handler)
    try:
        r = await c.test_connection()
    finally:
        await c._client.aclose()

    assert r["success"] is True
    assert r["account_id"] == "acc1"


@pytest.mark.asyncio
async def test_jira_get_issue_404_returns_none():
    """Canonical convention: 404 -> None, never raises."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"errorMessages": ["Issue not found"]})

    c = JiraClient(email="e@x.com", api_token="tok", base_url="https://acme.atlassian.net")
    c._client = _mock_client(handler)
    try:
        result = await c.get_issue("GV-999")
    finally:
        await c._client.aclose()

    assert result is None


@pytest.mark.asyncio
async def test_jira_comment_posts_adf_body_to_v3_endpoint():
    """Ported from the deleted connectors client's update_issue(comment=...)."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "1"})

    c = JiraClient(email="e@x.com", api_token="tok", base_url="https://acme.atlassian.net")
    c._client = _mock_client(handler)
    try:
        await c.comment("GV-12", "Status update from GetVul")
    finally:
        await c._client.aclose()

    assert captured["method"] == "POST"
    assert captured["path"] == "/rest/api/3/issue/GV-12/comment"
    # v3 requires ADF, not a bare string body
    assert captured["body"]["body"]["type"] == "doc"
    assert "Status update from GetVul" in json.dumps(captured["body"])


@pytest.mark.asyncio
async def test_jira_transition_finds_matching_transition_and_posts_it():
    """Ported from update_issue(status=...): GET transitions, POST matching id."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "transitions": [
                        {"id": "21", "name": "In Progress", "to": {"name": "In Progress"}},
                        {"id": "31", "name": "Done", "to": {"name": "Done"}},
                    ]
                },
            )
        return httpx.Response(204)

    c = JiraClient(email="e@x.com", api_token="tok", base_url="https://acme.atlassian.net")
    c._client = _mock_client(handler)
    try:
        await c.transition("GV-12", "Done")
    finally:
        await c._client.aclose()

    assert len(calls) == 2
    assert calls[0].method == "GET"
    assert calls[0].url.path == "/rest/api/3/issue/GV-12/transitions"
    assert calls[1].method == "POST"
    assert calls[1].url.path == "/rest/api/3/issue/GV-12/transitions"
    body = json.loads(calls[1].content)
    assert body["transition"]["id"] == "31"


@pytest.mark.asyncio
async def test_jira_transition_no_match_does_not_post():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={"transitions": [{"id": "1", "name": "In Progress", "to": {"name": "In Progress"}}]},
        )

    c = JiraClient(email="e@x.com", api_token="tok", base_url="https://acme.atlassian.net")
    c._client = _mock_client(handler)
    try:
        await c.transition("GV-12", "Done")  # no match; must not raise or POST
    finally:
        await c._client.aclose()

    assert len(calls) == 1
    assert calls[0].method == "GET"


@pytest.mark.asyncio
async def test_jira_close_issue_transitions_to_done():
    """close_issue() is a thin wrapper over transition(..., 'Done') — named
    close_issue (not close) because close() is this client's unrelated
    HTTP-cleanup method."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"transitions": [{"id": "31", "name": "Done", "to": {"name": "Done"}}]})
        return httpx.Response(204)

    c = JiraClient(email="e@x.com", api_token="tok", base_url="https://acme.atlassian.net")
    c._client = _mock_client(handler)
    try:
        await c.close_issue("GV-12")
    finally:
        await c._client.aclose()

    assert calls[1].method == "POST"
    assert json.loads(calls[1].content)["transition"]["id"] == "31"


def test_jira_client_import_smoke_daily_sync_can_resolve_ported_methods():
    """Import smoke: daily_sync's repointed import resolves comment/transition."""
    from app.ticketing.jira_client import JiraClient as CanonicalJiraClient

    assert hasattr(CanonicalJiraClient, "comment")
    assert hasattr(CanonicalJiraClient, "transition")
    assert hasattr(CanonicalJiraClient, "close_issue")


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


# ── GitHub (D-12: add_comment + close_issue) ───────────────────────────────────


@pytest.mark.asyncio
async def test_github_add_comment_posts_to_comments_endpoint():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": 1})

    c = GitHubClient(token="fake-token", owner="o", repo="r")
    c._client._transport = httpx.MockTransport(handler)
    try:
        await c.add_comment(7, "Status update")
    finally:
        await c.close()

    assert captured["method"] == "POST"
    assert captured["path"] == "/repos/o/r/issues/7/comments"
    assert captured["body"] == {"body": "Status update"}


@pytest.mark.asyncio
async def test_github_close_issue_patches_state_closed():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"number": 7, "state": "closed"})

    c = GitHubClient(token="fake-token", owner="o", repo="r")
    c._client._transport = httpx.MockTransport(handler)
    try:
        await c.close_issue(7)
    finally:
        await c.close()

    assert captured["method"] == "PATCH"
    assert captured["path"] == "/repos/o/r/issues/7"
    assert captured["body"] == {"state": "closed"}


@pytest.mark.asyncio
async def test_github_get_watchers_still_returns_empty_stub():
    """D-12: GitHub has no per-issue watcher primitive — unchanged stub."""
    c = GitHubClient(token="fake-token", owner="o", repo="r")
    result = await c.get_watchers()
    await c.close()

    assert result == []
