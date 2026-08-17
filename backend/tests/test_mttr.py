"""Phase 36 Plan 04 -- MTTR-by-tier capture (SLA-04, D-09, Pitfall 6/13).

Covers the durable `remediation_events` table + the single
`mark_vulnerability_remediated()` helper (app/vulnerabilities/service.py)
that ALL REMEDIATED write sites must route through, plus the tier-grouped
`get_mttr_by_tier` aggregate + its `GET /vulnerabilities/mttr/by-tier`
endpoint.

Exercises every REMEDIATED write site directly against the real production
function (no test doubles for GetVul's own code -- only the outbound
provider I/O is faked, mirroring test_github_sync.py's existing daily_sync
convention of driving `_sync_*_tickets` with a client double):
  - vulnerabilities/service.py: update_vulnerability_status, bulk_update_status
  - ticketing/service.py: sync_ticket_status, close_ticket (fake client_resolver)
  - ticketing/daily_sync.py: _sync_asana_tickets, _sync_jira_tickets,
    _sync_github_tickets (duck-typed fake provider clients -- these
    functions only call a handful of named async methods on `client`, no
    isinstance/Protocol check, so a plain fake object exercises the exact
    same GetVul-side branch a real client would). Phase 37 Plan 03 (D-03):
    a done ticket in these three functions no longer routes through
    mark_vulnerability_remediated -- it drives IN_PROGRESS only, so the
    three tests below assert NO RemediationEvent is written from this
    path (closure is rescan-only, Plan 01's SUCCESS-branch sweep).

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY + JWT_SECRET_KEY set, per-file (not the whole tests/
dir).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.audit import AuditLog
from app.ticketing.models import Ticket
from app.vulnerabilities.models import RemediationEvent, Vulnerability
from app.vulnerabilities.schemas import BulkStatusUpdate
from app.vulnerabilities.service import (
    bulk_update_status,
    get_mttr_by_tier,
    mark_vulnerability_remediated,
    update_vulnerability_status,
)

# ── Seed helpers ─────────────────────────────────────────────────────────


def _vuln(
    *,
    tenant_id: uuid.UUID,
    severity: str = "CRITICAL",
    status: str = "OPEN",
    risk_exposure_score: int | None = None,
    first_detected_at: datetime | None = None,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity=severity,
        source="CROWDSTRIKE",
        status=status,
        risk_exposure_score=risk_exposure_score,
        first_detected_at=first_detected_at or (now - timedelta(days=3)),
        last_seen_at=now,
    )


def _ticket(
    *,
    tenant_id: uuid.UUID,
    vulnerability_id: uuid.UUID,
    provider: str,
    external_ticket_id: str,
    resolved_at: datetime | None = None,
) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vulnerability_id,
        provider=provider,
        external_ticket_id=external_ticket_id,
        external_ticket_url=f"https://example.test/{provider.lower()}/{external_ticket_id}",
        external_status="open",
        ticket_created_at=datetime.now(UTC),
        resolved_at=resolved_at,
    )


async def _events_for(db_session, vuln_id: uuid.UUID) -> list[RemediationEvent]:
    result = await db_session.execute(select(RemediationEvent).where(RemediationEvent.vulnerability_id == vuln_id))
    return list(result.scalars().all())


# ── 1. mark_vulnerability_remediated -- the core helper (direct call) ──────


async def test_mark_vulnerability_remediated_writes_status_and_event(db_session, tenant_a):
    detected = datetime.now(UTC) - timedelta(days=5)
    vuln = _vuln(tenant_id=tenant_a, risk_exposure_score=85, first_detected_at=detected)
    db_session.add(vuln)
    await db_session.flush()

    await mark_vulnerability_remediated(db_session, vuln)
    await db_session.commit()

    assert vuln.status == "REMEDIATED"
    assert vuln.remediated_at is not None

    events = await _events_for(db_session, vuln.id)
    assert len(events) == 1
    event = events[0]
    assert event.tenant_id == tenant_a
    assert event.tier_at_remediation == "critical"
    assert event.first_detected_at == detected
    assert event.remediated_at == vuln.remediated_at
    # ~5 days elapsed -- allow slack for test wall-clock drift.
    assert 4 * 86400 < event.duration_seconds < 6 * 86400


async def test_mark_vulnerability_remediated_null_score_uses_severity_fallback(db_session, tenant_a):
    """D-03/D-12: a NULL risk_exposure_score freezes tier via severity_to_tier."""
    vuln = _vuln(tenant_id=tenant_a, severity="HIGH", risk_exposure_score=None)
    db_session.add(vuln)
    await db_session.flush()

    await mark_vulnerability_remediated(db_session, vuln)
    await db_session.commit()

    events = await _events_for(db_session, vuln.id)
    assert events[0].tier_at_remediation == "high"


async def test_mark_vulnerability_remediated_below_floor_records_not_tracked(db_session, tenant_a):
    """D-12/Pitfall 13: a SCORED finding below RISK_SCORE_TIER_MEDIUM (20) is
    never dropped -- the row is still written, tier_at_remediation freezes
    to the literal 'not_tracked' string rather than silently vanishing."""
    vuln = _vuln(tenant_id=tenant_a, severity="LOW", risk_exposure_score=5)
    db_session.add(vuln)
    await db_session.flush()

    await mark_vulnerability_remediated(db_session, vuln)
    await db_session.commit()

    events = await _events_for(db_session, vuln.id)
    assert len(events) == 1
    assert events[0].tier_at_remediation == "not_tracked"


# ── 2. vulnerabilities/service.py direct call sites ─────────────────────────


async def test_update_vulnerability_status_remediated_routes_through_helper(db_session, tenant_a):
    vuln = _vuln(tenant_id=tenant_a, risk_exposure_score=60)
    db_session.add(vuln)
    await db_session.flush()

    updated = await update_vulnerability_status(db_session, tenant_a, vuln.id, "REMEDIATED")
    await db_session.commit()

    assert updated is True
    await db_session.refresh(vuln)
    assert vuln.status == "REMEDIATED"
    events = await _events_for(db_session, vuln.id)
    assert len(events) == 1
    assert events[0].tier_at_remediation == "high"


async def test_update_vulnerability_status_non_remediated_writes_no_event(db_session, tenant_a):
    """Non-REMEDIATED transitions keep the original bulk-update behavior --
    zero remediation_events rows (the helper only fires for REMEDIATED)."""
    vuln = _vuln(tenant_id=tenant_a)
    db_session.add(vuln)
    await db_session.flush()

    updated = await update_vulnerability_status(db_session, tenant_a, vuln.id, "IN_PROGRESS")
    await db_session.commit()

    assert updated is True
    await db_session.refresh(vuln)
    assert vuln.status == "IN_PROGRESS"
    assert await _events_for(db_session, vuln.id) == []


async def test_bulk_update_status_remediated_writes_one_event_per_vuln(db_session, tenant_a):
    v1 = _vuln(tenant_id=tenant_a, risk_exposure_score=90)
    v2 = _vuln(tenant_id=tenant_a, risk_exposure_score=55)
    db_session.add_all([v1, v2])
    await db_session.flush()

    body = BulkStatusUpdate(vulnerability_ids=[v1.id, v2.id], status="REMEDIATED")
    count = await bulk_update_status(db_session, tenant_a, body)
    await db_session.commit()

    assert count == 2
    for v in (v1, v2):
        await db_session.refresh(v)
        assert v.status == "REMEDIATED"
        assert len(await _events_for(db_session, v.id)) == 1


# ── 3. ticketing/service.py -- sync_ticket_status + close_ticket ───────────


class _FakeTicketingClient:
    """Duck-typed fake matching dispatch.py's TicketingClient verb surface --
    only `get`/`comment`/`close` are exercised by these tests."""

    def __init__(self, get_payload: dict | None = None):
        self._get_payload = get_payload or {}
        self.closed_refs: list[str] = []
        # Phase 37 Plan 04: record comment calls so the idempotency tests can
        # assert a steady-state re-poll / repeat-close does NOT re-spam the
        # ticket (the fresh-transition guards hold).
        self.comment_calls: list[tuple[str, str]] = []

    async def create(self, title, body, **kwargs):  # pragma: no cover -- unused by these tests
        raise NotImplementedError

    async def get(self, ref):
        return self._get_payload

    async def comment(self, ref, body):
        self.comment_calls.append((ref, body))
        return None

    async def close(self, ref):
        self.closed_refs.append(ref)


async def _audit_rows_for(db_session, vuln_id: uuid.UUID) -> list[AuditLog]:
    """All ticket-status-sync audit rows for a vuln (Phase 37 Plan 04)."""
    rows = await db_session.execute(
        select(AuditLog).where(
            AuditLog.resource_id == str(vuln_id),
            AuditLog.action == "vuln.ticket_status_sync",
        )
    )
    return list(rows.scalars().all())


async def test_sync_ticket_status_done_drives_in_progress_never_remediated(db_session, tenant_a):
    """D-03 addendum (Phase 37 Plan 04): a done ticket read via the manual
    `sync_ticket_status` router path drives the linked finding to IN_PROGRESS
    (+ awaiting-rescan comment + audit), NEVER REMEDIATED -- closure is
    rescan-verified only. Re-polling a steady-state (ticket already done,
    finding still awaiting rescan) is a no-op: no repeat comment, no
    duplicate audit row (the `not was_done_before` guard holds)."""
    from app.ticketing.service import sync_ticket_status

    vuln = _vuln(tenant_id=tenant_a, risk_exposure_score=85)
    db_session.add(vuln)
    await db_session.flush()

    # Fresh transition: ticket starts non-done (_ticket defaults external_status="open").
    ticket = _ticket(tenant_id=tenant_a, vulnerability_id=vuln.id, provider="ASANA", external_ticket_id="123")
    db_session.add(ticket)
    await db_session.commit()

    fake_client = _FakeTicketingClient(get_payload={"completed": True})

    async def resolver(provider):
        return fake_client

    # First sync: fresh done-transition -> IN_PROGRESS + one comment + one audit, zero RemediationEvent.
    await sync_ticket_status(db_session, tenant_a, resolver)
    await db_session.commit()

    await db_session.refresh(vuln)
    assert vuln.status == "IN_PROGRESS"
    assert await _events_for(db_session, vuln.id) == []
    assert len(fake_client.comment_calls) == 1
    assert len(await _audit_rows_for(db_session, vuln.id)) == 1

    # Second sync on the now-steady state (ticket "completed", finding still
    # IN_PROGRESS): idempotent -- the comment count and audit-row count must
    # NOT grow, and the finding is never force-closed.
    await sync_ticket_status(db_session, tenant_a, resolver)
    await db_session.commit()

    await db_session.refresh(vuln)
    assert vuln.status == "IN_PROGRESS"
    assert await _events_for(db_session, vuln.id) == []
    assert len(fake_client.comment_calls) == 1
    assert len(await _audit_rows_for(db_session, vuln.id)) == 1


async def test_close_ticket_done_drives_in_progress_never_remediated(db_session, tenant_a):
    """D-03 addendum (Phase 37 Plan 04): an analyst's explicit manual close
    still closes the TICKET on its provider, but drives the linked finding to
    IN_PROGRESS (+ awaiting-rescan comment + audit), NEVER REMEDIATED. A
    repeat close on the already-resolved URL is a no-op on the finding (the
    `not row_was_resolved` guard holds)."""
    from app.ticketing.service import close_ticket

    vuln = _vuln(tenant_id=tenant_a, risk_exposure_score=55)
    db_session.add(vuln)
    await db_session.flush()

    ticket = _ticket(tenant_id=tenant_a, vulnerability_id=vuln.id, provider="JIRA", external_ticket_id="GV-1")
    db_session.add(ticket)
    await db_session.commit()

    fake_client = _FakeTicketingClient()

    async def resolver(provider):
        return fake_client

    # First close: ticket closes on provider; finding driven IN_PROGRESS, zero RemediationEvent.
    result = await close_ticket(db_session, tenant_a, ticket.external_ticket_url, resolver)
    await db_session.commit()

    assert result["findings_awaiting_rescan"] == 1
    assert fake_client.closed_refs == ["GV-1"]

    await db_session.refresh(vuln)
    assert vuln.status == "IN_PROGRESS"
    assert await _events_for(db_session, vuln.id) == []
    assert len(fake_client.comment_calls) == 1
    assert len(await _audit_rows_for(db_session, vuln.id)) == 1

    # Second close on the same (now-resolved) URL: idempotent on the finding
    # -- no new audit row, no repeat comment; still IN_PROGRESS, never REMEDIATED.
    result2 = await close_ticket(db_session, tenant_a, ticket.external_ticket_url, resolver)
    await db_session.commit()

    assert result2["findings_awaiting_rescan"] == 0
    await db_session.refresh(vuln)
    assert vuln.status == "IN_PROGRESS"
    assert await _events_for(db_session, vuln.id) == []
    assert len(fake_client.comment_calls) == 1
    assert len(await _audit_rows_for(db_session, vuln.id)) == 1


# ── 4. ticketing/daily_sync.py -- three provider-sync functions ────────────


class _FakeAsanaLikeClient:
    """Duck-typed fake -- only the methods `_sync_asana_tickets` calls."""

    def __init__(self, task_payload: dict):
        self._task_payload = task_payload

    async def get_task(self, gid):
        return self._task_payload

    async def update_task(self, gid, **kwargs):
        return None

    async def add_comment(self, gid, body):
        return True


async def test_sync_asana_tickets_done_drives_in_progress_no_remediation_event(db_session, tenant_a):
    """Phase 37 Plan 03 (D-03 fix): a done Asana task no longer routes
    through mark_vulnerability_remediated -- it drives IN_PROGRESS only, so
    NO RemediationEvent is written from this path (closure is rescan-only,
    Plan 01)."""
    from app.ticketing.daily_sync import _sync_asana_tickets

    vuln = _vuln(tenant_id=tenant_a, risk_exposure_score=90)
    db_session.add(vuln)
    await db_session.flush()

    ticket = _ticket(tenant_id=tenant_a, vulnerability_id=vuln.id, provider="ASANA", external_ticket_id="a1")
    db_session.add(ticket)
    await db_session.commit()

    client = _FakeAsanaLikeClient({"completed": True})
    stats = await _sync_asana_tickets(db_session, tenant_a, client)
    await db_session.commit()

    assert stats["synced"] == 1
    await db_session.refresh(vuln)
    assert vuln.status == "IN_PROGRESS"
    events = await _events_for(db_session, vuln.id)
    assert events == []


class _FakeJiraLikeClient:
    """Duck-typed fake -- only the methods `_sync_jira_tickets` calls."""

    def __init__(self, issue_payload: dict):
        self._issue_payload = issue_payload

    async def get_issue(self, key):
        return self._issue_payload

    async def comment(self, key, body):
        return None

    async def transition(self, key, name):
        return None


async def test_sync_jira_tickets_done_drives_in_progress_no_remediation_event(db_session, tenant_a):
    """Phase 37 Plan 03 (D-03 fix): see the Asana test above -- a done Jira
    issue drives IN_PROGRESS only, never a RemediationEvent."""
    from app.ticketing.daily_sync import _sync_jira_tickets

    vuln = _vuln(tenant_id=tenant_a, risk_exposure_score=None, severity="MEDIUM")
    db_session.add(vuln)
    await db_session.flush()

    ticket = _ticket(tenant_id=tenant_a, vulnerability_id=vuln.id, provider="JIRA", external_ticket_id="GV-2")
    db_session.add(ticket)
    await db_session.commit()

    payload = {"fields": {"status": {"statusCategory": {"key": "done"}, "name": "Done"}}}
    client = _FakeJiraLikeClient(payload)
    stats = await _sync_jira_tickets(db_session, tenant_a, client)
    await db_session.commit()

    assert stats["synced"] == 1
    await db_session.refresh(vuln)
    assert vuln.status == "IN_PROGRESS"
    events = await _events_for(db_session, vuln.id)
    assert events == []


class _FakeGitHubLikeClient:
    """Duck-typed fake -- only the methods `_sync_github_tickets` calls."""

    def __init__(self, issue_payload: dict):
        self._issue_payload = issue_payload

    async def get_issue(self, number):
        return self._issue_payload

    async def close_issue(self, number):
        return None

    async def add_comment(self, number, body):
        return None


async def test_sync_github_tickets_done_drives_in_progress_no_remediation_event(db_session, tenant_a):
    """Phase 37 Plan 03 (D-03 fix): see the Asana test above -- a closed
    GitHub issue drives IN_PROGRESS only, never a RemediationEvent."""
    from app.ticketing.daily_sync import _sync_github_tickets

    vuln = _vuln(tenant_id=tenant_a, risk_exposure_score=30)
    db_session.add(vuln)
    await db_session.flush()

    ticket = _ticket(tenant_id=tenant_a, vulnerability_id=vuln.id, provider="GITHUB", external_ticket_id="7")
    db_session.add(ticket)
    await db_session.commit()

    client = _FakeGitHubLikeClient({"number": 7, "state": "closed"})
    stats = await _sync_github_tickets(db_session, tenant_a, client)
    await db_session.commit()

    assert stats["synced"] == 1
    await db_session.refresh(vuln)
    assert vuln.status == "IN_PROGRESS"
    events = await _events_for(db_session, vuln.id)
    assert events == []


# ── 5. get_mttr_by_tier aggregate ────────────────────────────────────────────


async def test_get_mttr_by_tier_groups_by_tier_and_tenant(db_session, tenant_a, tenant_b):
    now = datetime.now(UTC)

    v1 = _vuln(tenant_id=tenant_a, risk_exposure_score=85, first_detected_at=now - timedelta(days=2))
    v2 = _vuln(tenant_id=tenant_a, risk_exposure_score=90, first_detected_at=now - timedelta(days=4))
    v3 = _vuln(tenant_id=tenant_a, risk_exposure_score=55, first_detected_at=now - timedelta(days=1))
    v_other_tenant = _vuln(tenant_id=tenant_b, risk_exposure_score=85, first_detected_at=now - timedelta(days=10))
    db_session.add_all([v1, v2, v3, v_other_tenant])
    await db_session.flush()

    for v in (v1, v2, v3, v_other_tenant):
        await mark_vulnerability_remediated(db_session, v)
    await db_session.commit()

    rows = await get_mttr_by_tier(db_session, tenant_a)
    by_tier = {r["tier_at_remediation"]: r for r in rows}

    assert by_tier["critical"]["count"] == 2
    assert by_tier["high"]["count"] == 1
    assert "not_tracked" not in by_tier
    # tenant_b's row must never leak into tenant_a's aggregate.
    assert sum(r["count"] for r in rows) == 3


# ── 6. GET /vulnerabilities/mttr/by-tier -- admin-gated, tenant-scoped ─────


async def test_mttr_by_tier_endpoint_requires_admin_and_is_tenant_scoped(
    client, client_factory, db_session, tenant_a, admin_user
):
    vuln = _vuln(tenant_id=tenant_a, risk_exposure_score=85)
    db_session.add(vuln)
    await db_session.flush()
    await mark_vulnerability_remediated(db_session, vuln)
    await db_session.commit()

    # Analyst (the default `client` fixture role) is below the admin floor.
    analyst_resp = await client.get("/api/v1/vulnerabilities/mttr/by-tier")
    assert analyst_resp.status_code == 403

    admin_client = client_factory(admin_user)
    admin_resp = await admin_client.get("/api/v1/vulnerabilities/mttr/by-tier")
    assert admin_resp.status_code == 200
    body = admin_resp.json()
    assert any(r["tier_at_remediation"] == "critical" and r["count"] == 1 for r in body)
