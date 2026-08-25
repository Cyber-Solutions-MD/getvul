"""Phase 37 Plan 02 -- SYNC-03: reopen-on-recurrence (D-04).

Task 1: `reopen_vulnerability` soft-close resurrection helper
(`app.vulnerabilities.service.reopen_vulnerability`).
Task 2: `_upsert_vulnerability`'s existing-row branch wires the reopen in
when a re-detected finding's row is REMEDIATED.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY + JWT_SECRET_KEY set, per-file (not the whole tests/
dir).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import AuditLog
from app.connectors.base import NormalizedVulnerability
from app.connectors.sync import _upsert_vulnerability
from app.ticketing.models import Ticket
from app.vulnerabilities.models import RemediationEvent, Vulnerability
from app.vulnerabilities.service import mark_vulnerability_remediated, reopen_vulnerability

# ── Seed helpers (mirrors tests/test_rescan_autoclose.py conventions) ───────


def _seed_vuln(
    tenant_id: uuid.UUID,
    *,
    asset_id: uuid.UUID | None = None,
    status: str = "OPEN",
    source: str = "MOCK",
    cve_id: str | None = None,
    last_seen_at: datetime | None = None,
    clean_scan_streak: int = 0,
    first_detected_at: datetime | None = None,
    remediated_at: datetime | None = None,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id or f"CVE-REOPEN-{uuid.uuid4().hex[:6]}",
        severity="CRITICAL",
        status=status,
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        asset_id=asset_id,
        first_detected_at=first_detected_at or (now - timedelta(days=5)),
        last_seen_at=last_seen_at or now,
        clean_scan_streak=clean_scan_streak,
        remediated_at=remediated_at,
        remediation_action="Upgrade to fixed version",
        affected_product="widget",
    )


def _seed_asset(tenant_id: uuid.UUID) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04 LTS",
    )


def _normalized(cve_id: str, source_vuln_id: str) -> NormalizedVulnerability:
    return NormalizedVulnerability(
        cve_id=cve_id,
        vulnerability_name="widget vuln",
        cvss_v3_score=9.8,
        severity="CRITICAL",
        source_vuln_id=source_vuln_id,
        affected_product="widget",
        remediation_info="Upgrade to fixed version",
    )


# ── Task 1: reopen_vulnerability helper ──────────────────────────────────────


@pytest.mark.asyncio
async def test_reopen_helper_resurrects_remediated_row(db_session, tenant_a):
    """reopen_vulnerability on a REMEDIATED row sets status=OPEN,
    remediated_at=None, clean_scan_streak=0, preserves first_detected_at,
    and writes a system:rescan-reopen AuditLog row."""
    first_detected = datetime.now(UTC) - timedelta(days=10)
    remediated_at = datetime.now(UTC) - timedelta(days=1)
    vuln = _seed_vuln(
        tenant_a,
        status="REMEDIATED",
        clean_scan_streak=0,
        first_detected_at=first_detected,
        remediated_at=remediated_at,
    )
    db_session.add(vuln)
    await db_session.flush()

    result = await reopen_vulnerability(db_session, vuln)
    await db_session.flush()

    assert result is True
    assert vuln.status == "OPEN"
    assert vuln.remediated_at is None
    assert vuln.clean_scan_streak == 0
    assert vuln.first_detected_at == first_detected, "first_detected_at must be preserved (MTTR lineage)"

    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(vuln.id),
                AuditLog.action == "vuln.reopen_recurrence",
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1, f"expected exactly 1 reopen AuditLog row, got {len(audit_rows)}"
    assert audit_rows[0].user_email == "system:rescan-reopen"
    assert audit_rows[0].tenant_id == tenant_a


@pytest.mark.asyncio
async def test_reopen_helper_preserves_prior_remediation_event(db_session, tenant_a):
    """The prior RemediationEvent row survives reopen -- MTTR history is
    never deleted."""
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()

    event = await mark_vulnerability_remediated(db_session, vuln)
    await db_session.flush()
    assert vuln.status == "REMEDIATED"

    await reopen_vulnerability(db_session, vuln)
    await db_session.flush()

    rows = (
        await db_session.execute(select(RemediationEvent).where(RemediationEvent.vulnerability_id == vuln.id))
    ).scalars().all()
    assert len(rows) == 1, "the prior RemediationEvent row must survive reopen"
    assert rows[0].id == event.id


@pytest.mark.asyncio
async def test_reopen_helper_noop_on_non_remediated_row(db_session, tenant_a):
    """Called on a non-REMEDIATED row, reopen_vulnerability is a no-op
    returning False (idempotent guard)."""
    vuln = _seed_vuln(tenant_a, status="OPEN", clean_scan_streak=1)
    db_session.add(vuln)
    await db_session.flush()

    result = await reopen_vulnerability(db_session, vuln)
    await db_session.flush()

    assert result is False
    assert vuln.status == "OPEN"
    assert vuln.clean_scan_streak == 1, "no-op must not touch the streak either"

    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(vuln.id),
                AuditLog.action == "vuln.reopen_recurrence",
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 0, "no-op must not write an audit row"


# ── Task 2: _upsert_vulnerability existing-row reopen branch ────────────────


@pytest.mark.asyncio
async def test_redetection_reopens_same_row_no_duplicate(db_session, tenant_a):
    """A scan re-detecting a REMEDIATED finding reopens the SAME row: no
    duplicate Vulnerability row is created, first_detected_at is preserved,
    and the linked Ticket still points at the reopened finding."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    cve_id = "CVE-2026-REDETECT"
    source_vuln_id = str(uuid.uuid4())
    first_detected = datetime.now(UTC) - timedelta(days=10)
    remediated_at = datetime.now(UTC) - timedelta(days=1)
    vuln = _seed_vuln(
        tenant_a,
        asset_id=asset.id,
        status="REMEDIATED",
        source="CROWDSTRIKE",
        cve_id=cve_id,
        first_detected_at=first_detected,
        remediated_at=remediated_at,
        clean_scan_streak=0,
    )
    db_session.add(vuln)
    await db_session.flush()

    ticket = Ticket(
        tenant_id=tenant_a,
        vulnerability_id=vuln.id,
        provider="JIRA",
        external_ticket_id="PROJ-123",
        external_ticket_url="https://example.atlassian.net/browse/PROJ-123",
        external_status="done",
    )
    db_session.add(ticket)
    await db_session.flush()
    vuln_id = vuln.id

    # Re-detection: same (tenant, cve, asset, source) identity key.
    normalized = _normalized(cve_id, source_vuln_id)
    created = await _upsert_vulnerability(db_session, tenant_a, normalized, asset.id, "CROWDSTRIKE")
    await db_session.flush()

    assert created is False, "re-detection must route to the existing-row branch, not create a new row"

    count_rows = (
        await db_session.execute(
            select(Vulnerability).where(
                Vulnerability.tenant_id == tenant_a,
                Vulnerability.cve_id == cve_id,
                Vulnerability.asset_id == asset.id,
                Vulnerability.source == "CROWDSTRIKE",
            )
        )
    ).scalars().all()
    assert len(count_rows) == 1, f"expected exactly 1 finding row for this identity key, got {len(count_rows)}"

    reopened = count_rows[0]
    assert reopened.id == vuln_id, "the SAME row must be reopened, not a new one"
    assert reopened.status == "OPEN"
    assert reopened.remediated_at is None
    assert reopened.clean_scan_streak == 0
    assert reopened.first_detected_at == first_detected, "MTTR lineage must be preserved"

    ticket_rows = (
        await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln_id))
    ).scalars().all()
    assert len(ticket_rows) == 1, "reopen must not create a duplicate Ticket row"
    assert ticket_rows[0].id == ticket.id

    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(vuln_id),
                AuditLog.action == "vuln.reopen_recurrence",
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1, "re-detection through the upsert path must audit the reopen"


@pytest.mark.asyncio
async def test_redetection_of_open_row_does_not_reopen_again(db_session, tenant_a):
    """Re-detecting an already-OPEN row (never closed) must NOT trigger the
    reopen branch or write a reopen audit row -- regression guard on the
    existing-row field-refresh path."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    cve_id = "CVE-2026-STILLOPEN"
    source_vuln_id = str(uuid.uuid4())
    vuln = _seed_vuln(
        tenant_a,
        asset_id=asset.id,
        status="OPEN",
        source="CROWDSTRIKE",
        cve_id=cve_id,
        clean_scan_streak=1,
    )
    db_session.add(vuln)
    await db_session.flush()
    vuln_id = vuln.id

    normalized = _normalized(cve_id, source_vuln_id)
    created = await _upsert_vulnerability(db_session, tenant_a, normalized, asset.id, "CROWDSTRIKE")
    await db_session.flush()

    assert created is False
    await db_session.refresh(vuln)
    assert vuln.status == "OPEN"
    # The reopen branch guard must not fire on a non-REMEDIATED row -- streak
    # bookkeeping here belongs to the SYNC-02 sweep, not this upsert branch.
    assert vuln.clean_scan_streak == 1

    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(vuln_id),
                AuditLog.action == "vuln.reopen_recurrence",
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 0
