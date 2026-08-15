"""Phase 37 Plan 03 — SYNC-01/SYNC-03 two-way ticket sync remediation (D-03).

Task 1: `map_ticket_status` (the D-03-safe provider-status -> workflow-intent
mapper) + `GitHubClient.reopen_issue` (the SYNC-03 ticket-side reopen call).

Task 2 (appended below Task 1's tests): the rewritten `daily_sync.py`
first-pass branches — ticket-done drives IN_PROGRESS (never REMEDIATED,
D-03), an unknown provider status is a no-op, and a finding that is OPEN
again while its ticket still shows done/closed (recurrence, from Plan 02's
DB-side reopen) reopens the EXTERNAL ticket (SYNC-03/D-04) rather than
creating a duplicate.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from app.audit import AuditLog
from app.ticketing import daily_sync as m
from app.ticketing.asana_client import AsanaClient
from app.ticketing.github_client import GitHubClient
from app.ticketing.jira_client import JiraClient
from app.ticketing.models import Ticket
from app.ticketing.providers import TicketProvider
from app.ticketing.service import map_ticket_status
from app.vulnerabilities.models import Vulnerability

# ── Task 1: map_ticket_status ────────────────────────────────────────────────


class TestMapTicketStatusJira:
    def test_indeterminate_category_maps_in_progress(self):
        payload = {"fields": {"status": {"statusCategory": {"key": "indeterminate"}, "name": "In Progress"}}}
        assert map_ticket_status(TicketProvider.JIRA, payload) == "in_progress"

    def test_done_category_maps_done_awaiting_rescan(self):
        payload = {"fields": {"status": {"statusCategory": {"key": "done"}, "name": "Done"}}}
        assert map_ticket_status(TicketProvider.JIRA, payload) == "done_awaiting_rescan"

    def test_done_by_name_without_done_category_maps_done_awaiting_rescan(self):
        """A workflow whose 'Resolved' status is (mis)categorized outside
        'done' should still be recognized via the name whitelist."""
        payload = {"fields": {"status": {"statusCategory": {"key": "new"}, "name": "Resolved"}}}
        assert map_ticket_status(TicketProvider.JIRA, payload) == "done_awaiting_rescan"

    def test_new_category_maps_open(self):
        payload = {"fields": {"status": {"statusCategory": {"key": "new"}, "name": "To Do"}}}
        assert map_ticket_status(TicketProvider.JIRA, payload) == "open"

    def test_unrecognized_category_maps_unknown(self):
        payload = {"fields": {"status": {"statusCategory": {"key": "bogus"}, "name": "???"}}}
        assert map_ticket_status(TicketProvider.JIRA, payload) == "unknown"

    def test_empty_payload_maps_unknown(self):
        assert map_ticket_status(TicketProvider.JIRA, {}) == "unknown"


class TestMapTicketStatusAsana:
    def test_completed_true_maps_done_awaiting_rescan(self):
        assert map_ticket_status(TicketProvider.ASANA, {"completed": True}) == "done_awaiting_rescan"

    def test_completed_false_maps_open(self):
        assert map_ticket_status(TicketProvider.ASANA, {"completed": False}) == "open"

    def test_missing_completed_key_maps_unknown(self):
        assert map_ticket_status(TicketProvider.ASANA, {"gid": "1"}) == "unknown"

    def test_empty_payload_maps_unknown(self):
        assert map_ticket_status(TicketProvider.ASANA, {}) == "unknown"


class TestMapTicketStatusGitHub:
    def test_closed_maps_done_awaiting_rescan(self):
        assert map_ticket_status(TicketProvider.GITHUB, {"state": "closed"}) == "done_awaiting_rescan"

    def test_open_maps_open(self):
        assert map_ticket_status(TicketProvider.GITHUB, {"state": "open"}) == "open"

    def test_garbage_state_maps_unknown(self):
        assert map_ticket_status(TicketProvider.GITHUB, {"state": "archived"}) == "unknown"

    def test_empty_payload_maps_unknown(self):
        assert map_ticket_status(TicketProvider.GITHUB, {}) == "unknown"


def test_map_ticket_status_never_returns_remediated():
    """T-37-08/D-03 whitelist assertion: no combination of known-good or
    garbage payloads across any provider ever produces a close intent."""
    payloads = [
        (TicketProvider.JIRA, {"fields": {"status": {"statusCategory": {"key": "done"}, "name": "Done"}}}),
        (TicketProvider.JIRA, {"fields": {"status": {"statusCategory": {"key": "indeterminate"}, "name": "Doing"}}}),
        (TicketProvider.JIRA, {"fields": {"status": {"statusCategory": {"key": "new"}, "name": "To Do"}}}),
        (TicketProvider.JIRA, {}),
        (TicketProvider.ASANA, {"completed": True}),
        (TicketProvider.ASANA, {"completed": False}),
        (TicketProvider.ASANA, {}),
        (TicketProvider.GITHUB, {"state": "closed"}),
        (TicketProvider.GITHUB, {"state": "open"}),
        (TicketProvider.GITHUB, {"state": "weird"}),
        (TicketProvider.GITHUB, {}),
    ]
    for provider, payload in payloads:
        intent = map_ticket_status(provider, payload)
        assert intent != "remediated"
        assert intent in ("in_progress", "done_awaiting_rescan", "open", "unknown")


# ── Task 1: GitHubClient.reopen_issue ────────────────────────────────────────


@pytest.mark.asyncio
async def test_github_reopen_issue_patches_state_open():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"number": 7, "state": "open"})

    c = GitHubClient(token="fake-token", owner="o", repo="r")
    c._client._transport = httpx.MockTransport(handler)
    try:
        await c.reopen_issue(7)
    finally:
        await c.close()

    assert captured["method"] == "PATCH"
    assert captured["path"] == "/repos/o/r/issues/7"
    assert captured["body"] == {"state": "open"}


@pytest.mark.asyncio
async def test_github_reopen_issue_retries_once_on_429():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"number": 7, "state": "open"})

    c = GitHubClient(token="fake-token", owner="o", repo="r")
    c._client._transport = httpx.MockTransport(handler)
    try:
        await c.reopen_issue(7)
    finally:
        await c.close()

    assert len(calls) == 2
    assert all(req.method == "PATCH" for req in calls)


@pytest.mark.asyncio
async def test_github_reopen_issue_logs_never_raises_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    c = GitHubClient(token="fake-token", owner="o", repo="r")
    c._client._transport = httpx.MockTransport(handler)
    try:
        await c.reopen_issue(7)  # must not raise
    finally:
        await c.close()


# ── Task 2 fixtures/helpers ───────────────────────────────────────────────────


def _seed_vuln(tenant_id: uuid.UUID, *, status: str = "OPEN") -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-SYNC-{uuid.uuid4().hex[:6]}",
        severity="HIGH",
        status=status,
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=now,
        last_seen_at=now,
        remediation_action="Upgrade package",
        affected_product="widget",
    )


def _seed_github_ticket(tenant_id: uuid.UUID, vuln_id: uuid.UUID, issue_number: str, *, external_status: str) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vuln_id,
        provider="GITHUB",
        external_ticket_id=issue_number,
        external_ticket_url=f"https://github.com/acme/widgets/issues/{issue_number}",
        external_status=external_status,
        ticket_created_at=datetime.now(UTC),
    )


def _seed_jira_ticket(tenant_id: uuid.UUID, vuln_id: uuid.UUID, issue_key: str, *, external_status: str) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vuln_id,
        provider="JIRA",
        external_ticket_id=issue_key,
        external_ticket_url=f"https://acme.atlassian.net/browse/{issue_key}",
        external_status=external_status,
        ticket_created_at=datetime.now(UTC),
    )


def _seed_asana_ticket(tenant_id: uuid.UUID, vuln_id: uuid.UUID, task_gid: str, *, external_status: str) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vuln_id,
        provider="ASANA",
        external_ticket_id=task_gid,
        external_ticket_url=f"https://app.asana.com/0/proj/{task_gid}",
        external_status=external_status,
        ticket_created_at=datetime.now(UTC),
    )


def _mock_github_client(handler) -> GitHubClient:
    client = GitHubClient(token="fake-gh-token", owner="acme", repo="widgets")
    client._client._transport = httpx.MockTransport(handler)
    return client


def _mock_jira_client(handler) -> JiraClient:
    client = JiraClient(email="e@x.com", api_token="tok", base_url="https://acme.atlassian.net")
    client._client._transport = httpx.MockTransport(handler)
    return client


def _mock_asana_client(handler) -> AsanaClient:
    client = AsanaClient("fake-asana-token")
    client.client._transport = httpx.MockTransport(handler)
    return client


async def _audit_rows_for(db_session, vuln_id: uuid.UUID):
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.resource_id == str(vuln_id),
            AuditLog.action == "vuln.ticket_status_sync",
        )
    )
    return result.scalars().all()


# ── Task 2: ticket-done -> IN_PROGRESS, never REMEDIATED (D-03) ─────────────


@pytest.mark.asyncio
async def test_github_ticket_done_drives_in_progress_never_remediated(db_session, tenant_a):
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()
    ticket = _seed_github_ticket(tenant_a, vuln.id, "42", external_status="open")
    db_session.add(ticket)
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"number": 42, "state": "closed"})

    client = _mock_github_client(handler)
    try:
        stats = await m._sync_github_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    assert stats["synced"] == 1

    await db_session.refresh(vuln)
    await db_session.refresh(ticket)
    assert vuln.status == "IN_PROGRESS"
    assert vuln.status != "REMEDIATED"
    assert ticket.external_status == "closed"
    # D-03: never resolved by a ticket-done event alone -- only a rescan
    # (2 clean scans, Plan 01) or an already-remediated-by-other-means
    # auto-close (second pass below) may set resolved_at.
    assert ticket.resolved_at is None

    audit_rows = await _audit_rows_for(db_session, vuln.id)
    assert len(audit_rows) == 1
    assert audit_rows[0].user_email == "system:ticket-sync"
    assert audit_rows[0].tenant_id == tenant_a


@pytest.mark.asyncio
async def test_jira_ticket_done_drives_in_progress_never_remediated(db_session, tenant_a):
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()
    ticket = _seed_jira_ticket(tenant_a, vuln.id, "GV-1", external_status="to do")
    db_session.add(ticket)
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"fields": {"status": {"statusCategory": {"key": "done"}, "name": "Done"}}},
            )
        return httpx.Response(201, json={"id": "1"})

    client = _mock_jira_client(handler)
    try:
        stats = await m._sync_jira_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    assert stats["synced"] == 1

    await db_session.refresh(vuln)
    await db_session.refresh(ticket)
    assert vuln.status == "IN_PROGRESS"
    assert vuln.status != "REMEDIATED"
    assert ticket.external_status == "done"
    assert ticket.resolved_at is None

    audit_rows = await _audit_rows_for(db_session, vuln.id)
    assert len(audit_rows) == 1


@pytest.mark.asyncio
async def test_asana_ticket_done_drives_in_progress_never_remediated(db_session, tenant_a):
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()
    ticket = _seed_asana_ticket(tenant_a, vuln.id, "9001", external_status="open")
    db_session.add(ticket)
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": {"gid": "9001", "completed": True}})
        return httpx.Response(201, json={"data": {}})

    client = _mock_asana_client(handler)
    try:
        stats = await m._sync_asana_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    assert stats["synced"] == 1

    await db_session.refresh(vuln)
    await db_session.refresh(ticket)
    assert vuln.status == "IN_PROGRESS"
    assert vuln.status != "REMEDIATED"
    assert ticket.external_status == "completed"
    assert ticket.resolved_at is None

    audit_rows = await _audit_rows_for(db_session, vuln.id)
    assert len(audit_rows) == 1


@pytest.mark.asyncio
async def test_jira_in_progress_status_drives_finding_in_progress(db_session, tenant_a):
    """A ticket in an in-progress state drives the finding to IN_PROGRESS
    (no comment/audit -- distinct from the done-awaiting-rescan transition)."""
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()
    ticket = _seed_jira_ticket(tenant_a, vuln.id, "GV-2", external_status="to do")
    db_session.add(ticket)
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"fields": {"status": {"statusCategory": {"key": "indeterminate"}, "name": "In Progress"}}},
        )

    client = _mock_jira_client(handler)
    try:
        await m._sync_jira_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    await db_session.refresh(vuln)
    await db_session.refresh(ticket)
    assert vuln.status == "IN_PROGRESS"
    assert ticket.external_status == "in progress"


# ── Task 2: unknown status is a no-op ───────────────────────────────────────


@pytest.mark.asyncio
async def test_github_unknown_status_is_noop(db_session, tenant_a):
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()
    ticket = _seed_github_ticket(tenant_a, vuln.id, "43", external_status="open")
    db_session.add(ticket)
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"number": 43, "state": "archived"})  # garbage state

    client = _mock_github_client(handler)
    try:
        await m._sync_github_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    await db_session.refresh(vuln)
    await db_session.refresh(ticket)
    assert vuln.status == "OPEN"
    assert ticket.external_status == "open"

    audit_rows = await _audit_rows_for(db_session, vuln.id)
    assert audit_rows == []


@pytest.mark.asyncio
async def test_asana_unknown_status_is_noop(db_session, tenant_a):
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()
    ticket = _seed_asana_ticket(tenant_a, vuln.id, "9002", external_status="open")
    db_session.add(ticket)
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        # no "completed" key -> unknown
        return httpx.Response(200, json={"data": {"gid": "9002"}})

    client = _mock_asana_client(handler)
    try:
        stats = await m._sync_asana_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    assert stats["synced"] == 1

    await db_session.refresh(vuln)
    assert vuln.status == "OPEN"


# ── Task 2: recurrence reopens the EXTERNAL ticket (SYNC-03/D-04) ──────────


@pytest.mark.asyncio
async def test_github_recurrence_reopens_external_ticket_no_duplicate(db_session, tenant_a):
    """A finding reopened by Plan 02's rescan-recurrence path (status back to
    OPEN) while its ticket still shows done/closed on the provider ->
    reopen the external ticket + a recurrence comment, never a new row."""
    vuln = _seed_vuln(tenant_a, status="OPEN")  # already reopened via SYNC-03 DB-side
    db_session.add(vuln)
    await db_session.flush()
    ticket = _seed_github_ticket(tenant_a, vuln.id, "44", external_status="closed")  # done from a prior cycle
    db_session.add(ticket)
    await db_session.commit()

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"number": 44, "state": "closed"})
        if request.method == "PATCH":
            return httpx.Response(200, json={"number": 44, "state": "open"})
        if request.method == "POST":
            return httpx.Response(201, json={"id": 1})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    client = _mock_github_client(handler)
    try:
        await m._sync_github_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    assert ("PATCH", "/repos/acme/widgets/issues/44") in calls
    assert ("POST", "/repos/acme/widgets/issues/44/comments") in calls

    await db_session.refresh(ticket)
    assert ticket.external_status == "open"
    assert ticket.resolved_at is None

    all_tickets = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalars().all()
    assert len(all_tickets) == 1


@pytest.mark.asyncio
async def test_jira_recurrence_reopens_external_ticket_no_duplicate(db_session, tenant_a):
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()
    ticket = _seed_jira_ticket(tenant_a, vuln.id, "GV-3", external_status="done")
    db_session.add(ticket)
    await db_session.commit()

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/rest/api/3/issue/GV-3":
            return httpx.Response(
                200,
                json={"fields": {"status": {"statusCategory": {"key": "done"}, "name": "Done"}}},
            )
        if request.url.path == "/rest/api/3/issue/GV-3/transitions" and request.method == "GET":
            return httpx.Response(200, json={"transitions": [{"id": "11", "name": "To Do", "to": {"name": "To Do"}}]})
        if request.url.path == "/rest/api/3/issue/GV-3/transitions" and request.method == "POST":
            return httpx.Response(204)
        if request.url.path == "/rest/api/3/issue/GV-3/comment":
            return httpx.Response(201, json={"id": "1"})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    client = _mock_jira_client(handler)
    try:
        await m._sync_jira_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    transition_posts = [r for r in calls if r.method == "POST" and r.url.path.endswith("/transitions")]
    comment_posts = [r for r in calls if r.url.path.endswith("/comment")]
    assert len(transition_posts) == 1
    assert len(comment_posts) == 1

    await db_session.refresh(ticket)
    assert ticket.external_status == "to do"
    assert ticket.resolved_at is None


@pytest.mark.asyncio
async def test_asana_recurrence_reopens_external_ticket_no_duplicate(db_session, tenant_a):
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()
    ticket = _seed_asana_ticket(tenant_a, vuln.id, "9003", external_status="completed")
    db_session.add(ticket)
    await db_session.commit()

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"data": {"gid": "9003", "completed": True}})
        if request.method == "PUT":
            return httpx.Response(200, json={"data": {"gid": "9003", "completed": False}})
        if request.method == "POST":
            return httpx.Response(201, json={"data": {}})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    client = _mock_asana_client(handler)
    try:
        await m._sync_asana_tickets(db_session, tenant_a, client)
        await db_session.commit()
    finally:
        await client.close()

    put_calls = [r for r in calls if r.method == "PUT"]
    post_calls = [r for r in calls if r.method == "POST"]
    assert len(put_calls) == 1
    assert json.loads(put_calls[0].content)["data"]["completed"] is False
    assert len(post_calls) == 1  # the recurrence comment

    await db_session.refresh(ticket)
    assert ticket.external_status == "open"
    assert ticket.resolved_at is None
