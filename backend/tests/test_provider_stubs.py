"""Unit tests for Jira and GitHub connector stubs.

Uses httpx.MockTransport injected via monkeypatching the client's transport
so no real network calls are made.  Six tests cover:
  1. Jira create-ticket → JiraIssue with browse URL
  2. Jira get-issue → raw dict with fields.status.name
  3. Jira failure (400) → create_ticket returns None
  4. GitHub create-ticket → GitHubIssue with number + html_url
  5. GitHub get-issue → raw dict with state
  6. GitHub get_watchers → empty list (D-W-01 stub)
"""

from __future__ import annotations

import json

import httpx
import pytest
import pytest_asyncio

from app.ticketing.github_client import GitHubClient, GitHubIssue
from app.ticketing.jira_client import JiraClient, JiraIssue


# ── helpers ──────────────────────────────────────────────────────────────────


def _mock_transport(status: int, body: dict) -> httpx.MockTransport:
    """Return an httpx.MockTransport that always responds with a fixed response."""
    response = httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        return response

    return httpx.MockTransport(_handler)


def _patch_transport(client_instance, transport: httpx.MockTransport) -> None:
    """Inject a mock transport into an httpx.AsyncClient at test time."""
    client_instance._transport = transport


# ── Jira tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_jira_create_ticket_success():
    """Test 1: mock POST /rest/api/3/issue → 201; assert JiraIssue url ends with /browse/GV-12."""
    mock_body = {"id": "10042", "key": "GV-12", "self": "https://acme.atlassian.net/rest/api/3/issue/10042"}
    transport = _mock_transport(201, mock_body)

    client = JiraClient(
        email="user@example.com",
        api_token="fake-token",
        base_url="https://acme.atlassian.net",
    )
    _patch_transport(client._client, transport)

    issue = await client.create_ticket(
        project_key="GV",
        summary="Test issue",
        description="Some description",
    )
    await client.close()

    assert issue is not None
    assert isinstance(issue, JiraIssue)
    assert issue.key == "GV-12"
    assert issue.url.endswith("/browse/GV-12")


@pytest.mark.asyncio
async def test_jira_get_issue_success():
    """Test 2: mock GET issue → 200 {fields:{status:{name:'Done'}}}; assert dict returned."""
    mock_body = {
        "id": "10042",
        "key": "GV-12",
        "fields": {"status": {"name": "Done"}, "summary": "Test issue"},
    }
    transport = _mock_transport(200, mock_body)

    client = JiraClient(
        email="user@example.com",
        api_token="fake-token",
        base_url="https://acme.atlassian.net",
    )
    _patch_transport(client._client, transport)

    result = await client.get_issue("GV-12")
    await client.close()

    assert result is not None
    assert isinstance(result, dict)
    assert result["fields"]["status"]["name"] == "Done"


@pytest.mark.asyncio
async def test_jira_create_ticket_failure():
    """Test 3: mock POST → 400; assert create_ticket returns None (no exception raised)."""
    mock_body = {"errorMessages": ["Field 'summary' is required."]}
    transport = _mock_transport(400, mock_body)

    client = JiraClient(
        email="user@example.com",
        api_token="fake-token",
        base_url="https://acme.atlassian.net",
    )
    _patch_transport(client._client, transport)

    result = await client.create_ticket(
        project_key="GV",
        summary="Test issue",
        description="desc",
    )
    await client.close()

    assert result is None


# ── GitHub tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_github_create_ticket_success():
    """Test 4: mock POST /repos/o/r/issues → 201; assert GitHubIssue.number==7, url==html_url."""
    html_url = "https://github.com/o/r/issues/7"
    mock_body = {
        "id": 1001,
        "number": 7,
        "html_url": html_url,
        "state": "open",
        "title": "Test issue",
        "assignee": None,
    }
    transport = _mock_transport(201, mock_body)

    client = GitHubClient(token="fake-token", owner="o", repo="r")
    _patch_transport(client._client, transport)

    issue = await client.create_ticket(title="Test issue", body="Some body")
    await client.close()

    assert issue is not None
    assert isinstance(issue, GitHubIssue)
    assert issue.number == 7
    assert issue.url == html_url


@pytest.mark.asyncio
async def test_github_get_issue_success():
    """Test 5: mock GET issue → 200 {state:'closed'}; assert returned dict state=='closed'."""
    mock_body = {
        "id": 1001,
        "number": 7,
        "state": "closed",
        "title": "Test issue",
        "html_url": "https://github.com/o/r/issues/7",
    }
    transport = _mock_transport(200, mock_body)

    client = GitHubClient(token="fake-token", owner="o", repo="r")
    _patch_transport(client._client, transport)

    result = await client.get_issue(7)
    await client.close()

    assert result is not None
    assert isinstance(result, dict)
    assert result["state"] == "closed"


@pytest.mark.asyncio
async def test_github_get_watchers_stub():
    """Test 6: assert get_watchers() returns [] (D-W-01 — GitHub has no per-issue watcher API)."""
    client = GitHubClient(token="fake-token", owner="o", repo="r")
    result = await client.get_watchers()
    await client.close()

    assert result == []
