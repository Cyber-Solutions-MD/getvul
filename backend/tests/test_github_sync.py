"""Phase 23 Plan 05 — GitHub ticketing connector registration + daily_sync (D-11/D-12/D-13).

Task 1: proves GITHUB is registered as a creatable connector type in all four
backend registration points (schemas.py CONNECTOR_TYPES, connectors/router.py
CONNECTOR_CATEGORIES, tester.py's dispatch table, sync.py SPECIAL_CONNECTORS +
no-data-sync short-circuit).

Task 2: proves daily_sync's new GitHub branch mirrors the Asana/Jira
inbound-state-map + outbound-auto-close pattern, using an httpx.MockTransport
swapped into a real GitHubClient instance (mirrors test_ticketing_clients.py's
established convention) rather than a live GitHub API call.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest

from app.connectors.schemas import CONNECTOR_TYPES
from app.connectors.sync import SPECIAL_CONNECTORS, run_sync
from app.encryption import encrypt_value
from app.ticketing.github_client import GitHubClient
from app.ticketing.models import ConnectorConfig, Ticket
from app.vulnerabilities.models import Vulnerability


def _seed_github_connector(tenant_id: uuid.UUID, *, enabled: bool = True) -> ConnectorConfig:
    """Seed a GITHUB ConnectorConfig with the established token(credentials)/
    owner+repo(config) split (matches test_ticketing_dispatch.py's
    _seed_connector fixture pattern)."""
    creds = {"token": "fake-gh-token"}
    return ConnectorConfig(
        tenant_id=tenant_id,
        connector_type="GITHUB",
        is_enabled=enabled,
        credentials_secret_arn=json.dumps({k: encrypt_value(v) for k, v in creds.items()}),
        config={"owner": "acme", "repo": "widgets"},
    )


def _seed_vuln(tenant_id, *, status="OPEN") -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-GH-{uuid.uuid4().hex[:6]}",
        severity="CRITICAL",
        status=status,
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=now,
        last_seen_at=now,
        remediation_action="Upgrade to fixed version",
        affected_product="widget",
    )


def _seed_ticket(tenant_id, vuln_id, issue_number: str) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vuln_id,
        provider="GITHUB",
        external_ticket_id=issue_number,
        external_ticket_url=f"https://github.com/acme/widgets/issues/{issue_number}",
        external_status="open",
        ticket_created_at=datetime.now(UTC),
    )


def _mock_github_client(handler) -> GitHubClient:
    """Build a real GitHubClient with its internal httpx transport swapped
    for a MockTransport (mirrors test_ticketing_clients.py's convention)."""
    client = GitHubClient(token="fake-gh-token", owner="acme", repo="widgets")
    client._client._transport = httpx.MockTransport(handler)
    return client


# ── Task 1: registration across the four backend points ──────────────────────


def test_special_connectors_includes_github():
    assert "GITHUB" in SPECIAL_CONNECTORS


def test_connector_types_includes_github_with_token_as_credential_owner_repo_as_config():
    assert "GITHUB" in CONNECTOR_TYPES
    info = CONNECTOR_TYPES["GITHUB"]
    fields_by_name = {f["name"]: f for f in info.fields}
    assert fields_by_name["token"]["type"] == "password"
    assert fields_by_name["owner"]["type"] == "text"
    assert fields_by_name["repo"]["type"] == "text"


def test_connector_categories_includes_github_as_ticketing():
    from app.connectors.router import CONNECTOR_CATEGORIES

    assert CONNECTOR_CATEGORIES["GITHUB"] == "ticketing"


@pytest.mark.asyncio
async def test_tester_dispatch_resolves_github(monkeypatch):
    from app.connectors.tester import test_connector

    async def fake_test_connection(self):
        return {"success": True, "message": "Successfully connected to acme/widgets"}

    async def fake_close(self):
        return None

    monkeypatch.setattr(GitHubClient, "test_connection", fake_test_connection)
    monkeypatch.setattr(GitHubClient, "close", fake_close)

    result = await test_connector("GITHUB", {"token": "t"}, {"owner": "acme", "repo": "widgets"})
    assert result.success is True
    assert "acme/widgets" in result.message


@pytest.mark.asyncio
async def test_run_sync_github_short_circuits_to_success_with_no_vuln_fetch(db_session, tenant_a):
    """A GITHUB connector logs SUCCESS immediately — no data-sync attempted
    (mirrors the ASANA/JIRA no-data-sync short-circuit)."""
    connector = _seed_github_connector(tenant_a)
    db_session.add(connector)
    await db_session.commit()

    log = await run_sync(db_session, connector)

    assert log.status == "SUCCESS"
    assert "GitHub" in log.details["message"]


# ── Task 2: daily_sync GitHub branch — inbound state map + outbound auto-close ──


@pytest.mark.asyncio
async def test_github_daily_sync_inbound_closed_issue_marks_ticket_and_vuln(db_session, tenant_a):
    """Phase 37 Plan 03 (D-03 fix): a closed GitHub issue -> GetVul ticket
    'closed' + linked vuln driven to IN_PROGRESS (awaiting rescan
    verification) -- NEVER REMEDIATED. A done ticket can no longer
    force-close a finding the scanner still detects; closure is rescan-only
    (Plan 01). `ticket.resolved_at` stays unset so the ticket keeps being
    polled next cycle (SYNC-03 recurrence-reopen needs it poll-able)."""
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    await db_session.flush()

    ticket = _seed_ticket(tenant_a, vuln.id, "7")
    db_session.add(ticket)
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/repos/acme/widgets/issues/7"
            return httpx.Response(200, json={"number": 7, "state": "closed"})
        # The awaiting-rescan comment posted alongside the IN_PROGRESS write.
        assert request.url.path == "/repos/acme/widgets/issues/7/comments"
        return httpx.Response(201, json={"id": 1})

    client = _mock_github_client(handler)
    try:
        from app.ticketing.daily_sync import _sync_github_tickets

        stats = await _sync_github_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    assert stats["synced"] == 1

    await db_session.refresh(ticket)
    await db_session.refresh(vuln)
    assert ticket.external_status == "closed"
    assert ticket.resolved_at is None
    assert vuln.status == "IN_PROGRESS"
    assert vuln.status != "REMEDIATED"


@pytest.mark.asyncio
async def test_github_daily_sync_outbound_all_vulns_resolved_closes_issue_and_comments(db_session, tenant_a):
    """All linked vulns resolved -> PATCH issue closed (close_issue) + add_comment."""
    vuln = _seed_vuln(tenant_a, status="REMEDIATED")
    db_session.add(vuln)
    await db_session.flush()

    ticket = _seed_ticket(tenant_a, vuln.id, "9")
    db_session.add(ticket)
    await db_session.commit()

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            # Issue still open remotely — outbound auto-close is what drives the close.
            return httpx.Response(200, json={"number": 9, "state": "open"})
        if request.method == "PATCH":
            assert request.url.path == "/repos/acme/widgets/issues/9"
            return httpx.Response(200, json={"number": 9, "state": "closed"})
        if request.method == "POST":
            assert request.url.path == "/repos/acme/widgets/issues/9/comments"
            return httpx.Response(201, json={"id": 1})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    client = _mock_github_client(handler)
    try:
        from app.ticketing.daily_sync import _sync_github_tickets

        stats = await _sync_github_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    assert stats["comments_added"] == 1
    assert ("PATCH", "/repos/acme/widgets/issues/9") in calls
    assert ("POST", "/repos/acme/widgets/issues/9/comments") in calls

    await db_session.refresh(ticket)
    assert ticket.external_status == "closed"
    assert ticket.resolved_at is not None


@pytest.mark.asyncio
async def test_github_daily_sync_never_calls_get_watchers(db_session, tenant_a):
    """get_watchers is not part of the daily_sync surface for GitHub — local
    ticket_watchers stay authoritative. Asserts no crash on the GitHub path
    even with a get_watchers spy attached that must never fire."""
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    await db_session.flush()

    ticket = _seed_ticket(tenant_a, vuln.id, "11")
    db_session.add(ticket)
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"number": 11, "state": "open"})

    client = _mock_github_client(handler)
    watchers_called = False

    async def spy_get_watchers(self):
        nonlocal watchers_called
        watchers_called = True
        return []

    client.get_watchers = spy_get_watchers.__get__(client, GitHubClient)

    try:
        from app.ticketing.daily_sync import _sync_github_tickets

        stats = await _sync_github_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    assert stats["synced"] == 1
    assert watchers_called is False
