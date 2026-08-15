"""Phase 37 Plan 01 -- SYNC-02: rescan-verified auto-close tracer slice.

Task 1: migration 048 (clean_scan_streak) + the `verified_by`-extended
`mark_vulnerability_remediated` helper. Task 2 (added below Task 1's tests)
covers the SUCCESS-branch absent-sweep in `connectors/sync.py::run_sync`
that actually drives the streak + auto-close end to end.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY + JWT_SECRET_KEY set, per-file (not the whole tests/
dir).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import AuditLog
from app.connectors.sync import run_sync
from app.encryption import encrypt_value
from app.ticketing.models import ConnectorConfig
from app.vulnerabilities.models import RemediationEvent, Vulnerability
from app.vulnerabilities.service import mark_vulnerability_remediated

# ── Seed helpers (mirrors tests/test_github_sync.py conventions) ────────────


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
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id or f"CVE-RESCAN-{uuid.uuid4().hex[:6]}",
        severity="CRITICAL",
        status=status,
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        asset_id=asset_id,
        first_detected_at=first_detected_at or (now - timedelta(days=5)),
        last_seen_at=last_seen_at or now,
        clean_scan_streak=clean_scan_streak,
        remediation_action="Upgrade to fixed version",
        affected_product="widget",
    )


def _seed_asset(tenant_id: uuid.UUID) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04 LTS",
    )


def _seed_crowdstrike_connector(tenant_id: uuid.UUID) -> ConnectorConfig:
    creds = {"client_id": "fake-id", "client_secret": "fake-secret"}
    return ConnectorConfig(
        tenant_id=tenant_id,
        connector_type="CROWDSTRIKE",
        is_enabled=True,
        credentials_secret_arn=json.dumps({k: encrypt_value(v) for k, v in creds.items()}),
        config={},
    )


# ── Task 1: migration + column default + helper kwarg ───────────────────────


@pytest.mark.asyncio
async def test_migration_048_clean_scan_streak_defaults_zero(db_session, tenant_a):
    """A freshly-inserted Vulnerability reads clean_scan_streak == 0 via the
    column's server_default, without the ORM caller setting it explicitly."""
    now = datetime.now(UTC)
    vuln = Vulnerability(
        tenant_id=tenant_a,
        cve_id=f"CVE-DEFAULT-{uuid.uuid4().hex[:6]}",
        severity="HIGH",
        status="OPEN",
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=now,
        last_seen_at=now,
    )
    db_session.add(vuln)
    await db_session.flush()

    result = await db_session.execute(select(Vulnerability).where(Vulnerability.id == vuln.id))
    fetched = result.scalar_one()
    assert fetched.clean_scan_streak == 0, f"expected clean_scan_streak default 0, got {fetched.clean_scan_streak}"


@pytest.mark.asyncio
async def test_helper_regression_no_verified_by_unchanged(db_session, tenant_a):
    """mark_vulnerability_remediated(db, vuln) with NO verified_by kwarg
    behaves EXACTLY as before: REMEDIATED + remediated_at=now + one
    RemediationEvent — proves existing callers are unaffected."""
    vuln = _seed_vuln(tenant_a, status="OPEN")
    db_session.add(vuln)
    await db_session.flush()

    event = await mark_vulnerability_remediated(db_session, vuln)
    await db_session.flush()

    assert vuln.status == "REMEDIATED"
    assert vuln.remediated_at is not None
    assert vuln.clean_scan_streak == 0

    result = await db_session.execute(
        select(RemediationEvent).where(RemediationEvent.vulnerability_id == vuln.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1, f"expected exactly 1 RemediationEvent, got {len(rows)}"
    assert rows[0].id == event.id


@pytest.mark.asyncio
async def test_helper_verified_by_rescan_still_produces_event_and_mttr(db_session, tenant_a):
    """mark_vulnerability_remediated(db, vuln, verified_by="rescan") produces
    the same status/RemediationEvent write AND the returned event still
    captures MTTR; verified_by does NOT change remediated_at (Q1)."""
    first_detected = datetime.now(UTC) - timedelta(days=10)
    vuln = _seed_vuln(tenant_a, status="OPEN", clean_scan_streak=2, first_detected_at=first_detected)
    db_session.add(vuln)
    await db_session.flush()

    event = await mark_vulnerability_remediated(db_session, vuln, verified_by="rescan")
    await db_session.flush()

    assert vuln.status == "REMEDIATED"
    assert vuln.clean_scan_streak == 0, "REMEDIATED row must never carry a stale streak forward"
    assert event.duration_seconds > 0
    assert event.first_detected_at == first_detected

    result = await db_session.execute(
        select(RemediationEvent).where(RemediationEvent.vulnerability_id == vuln.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1


# ── Task 2: SUCCESS-branch absent-sweep + streak + auto-close (SYNC-02) ────


def _mock_crowdstrike_handler(request: httpx.Request) -> httpx.Response:
    """Minimal CrowdStrike auth + empty-fetch mock: SUCCESS sync with zero
    findings from the connector itself — the absent-sweep operates purely
    on pre-seeded rows, not on anything this mock returns."""
    if "oauth2/token" in request.url.path:
        return httpx.Response(200, json={"access_token": "fake-token", "expires_in": 1800})
    if "/devices/queries/devices" in request.url.path or "/devices/entities/devices" in request.url.path:
        return httpx.Response(200, json={"resources": []})
    if "/detects/queries/detects" in request.url.path or "/detects/entities/summaries" in request.url.path:
        return httpx.Response(200, json={"resources": []})
    if "spotlight" in request.url.path or "combined/vulnerabilities" in request.url.path:
        return httpx.Response(200, json={"resources": []})
    return httpx.Response(200, json={"resources": []})


async def _run_sync_with_mock(db_session, connector_config: ConnectorConfig):
    """Run the real run_sync against a CrowdStrikeConnector whose internal
    httpx client is swapped for a MockTransport (mirrors
    test_github_sync.py's established convention) — no live API call."""
    import app.connectors.crowdstrike as crowdstrike_module

    original_client_cls = httpx.AsyncClient

    class _MockAsyncClient(original_client_cls):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(_mock_crowdstrike_handler)
            super().__init__(*args, **kwargs)

    patched = crowdstrike_module.httpx.AsyncClient
    crowdstrike_module.httpx.AsyncClient = _MockAsyncClient
    try:
        return await run_sync(db_session, connector_config)
    finally:
        crowdstrike_module.httpx.AsyncClient = patched


@pytest.mark.asyncio
async def test_two_clean_success_syncs_auto_close_via_helper_with_audit(db_session, tenant_a):
    """A finding absent from 2 consecutive SUCCESSful scanner syncs of its
    source auto-closes as rescan-verified, with a RemediationEvent and a
    system:rescan-verify AuditLog row (SYNC-02)."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    stale = datetime.now(UTC) - timedelta(days=1)
    vuln = _seed_vuln(
        tenant_a,
        asset_id=asset.id,
        status="OPEN",
        source="CROWDSTRIKE",
        last_seen_at=stale,
        clean_scan_streak=0,
    )
    db_session.add(vuln)
    connector = _seed_crowdstrike_connector(tenant_a)
    db_session.add(connector)
    await db_session.flush()

    # First clean SUCCESS sync: streak 0 -> 1, still OPEN.
    log1 = await _run_sync_with_mock(db_session, connector)
    await db_session.flush()
    assert log1.status == "SUCCESS"

    await db_session.refresh(vuln)
    assert vuln.clean_scan_streak == 1, f"expected streak 1 after first clean sync, got {vuln.clean_scan_streak}"
    assert vuln.status == "OPEN", "1 clean sync must not close the finding"

    no_close_events = (
        await db_session.execute(select(RemediationEvent).where(RemediationEvent.vulnerability_id == vuln.id))
    ).scalars().all()
    assert len(no_close_events) == 0, "1 clean sync must not write a RemediationEvent"

    # Second clean SUCCESS sync: streak 1 -> 2, auto-close.
    # last_seen_at is still stale (the sweep only touches OPEN/IN_PROGRESS
    # rows whose last_seen_at predates sync_start; it wasn't refreshed by
    # the first sync since nothing re-detected it).
    log2 = await _run_sync_with_mock(db_session, connector)
    await db_session.flush()
    assert log2.status == "SUCCESS"

    await db_session.refresh(vuln)
    assert vuln.status == "REMEDIATED", f"expected auto-close at streak>=2, status is {vuln.status}"

    events = (
        await db_session.execute(select(RemediationEvent).where(RemediationEvent.vulnerability_id == vuln.id))
    ).scalars().all()
    assert len(events) == 1, f"expected exactly 1 RemediationEvent on auto-close, got {len(events)}"

    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(vuln.id),
                AuditLog.action == "vuln.rescan_verified_close",
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1, f"expected exactly 1 rescan-verified AuditLog row, got {len(audit_rows)}"
    assert audit_rows[0].user_email == "system:rescan-verify"
    assert audit_rows[0].tenant_id == tenant_a


@pytest.mark.asyncio
async def test_one_clean_sync_does_not_close(db_session, tenant_a):
    """1 clean sync does NOT close (streak==1)."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    stale = datetime.now(UTC) - timedelta(days=1)
    vuln = _seed_vuln(
        tenant_a, asset_id=asset.id, status="OPEN", source="CROWDSTRIKE", last_seen_at=stale, clean_scan_streak=0
    )
    db_session.add(vuln)
    connector = _seed_crowdstrike_connector(tenant_a)
    db_session.add(connector)
    await db_session.flush()

    await _run_sync_with_mock(db_session, connector)
    await db_session.flush()

    await db_session.refresh(vuln)
    assert vuln.clean_scan_streak == 1
    assert vuln.status == "OPEN"


@pytest.mark.asyncio
async def test_failed_sync_never_advances_streak_or_closes(db_session, tenant_a):
    """A FAILED/partial scanner sync never advances any streak and never
    closes anything (D-02)."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    stale = datetime.now(UTC) - timedelta(days=1)
    vuln = _seed_vuln(
        tenant_a, asset_id=asset.id, status="OPEN", source="CROWDSTRIKE", last_seen_at=stale, clean_scan_streak=1
    )
    db_session.add(vuln)
    connector = _seed_crowdstrike_connector(tenant_a)
    db_session.add(connector)
    await db_session.flush()

    def _auth_fail_handler(request: httpx.Request) -> httpx.Response:
        if "oauth2/token" in request.url.path:
            return httpx.Response(401, json={"errors": [{"message": "unauthorized"}]})
        return httpx.Response(401, json={"errors": [{"message": "unauthorized"}]})

    import app.connectors.crowdstrike as crowdstrike_module

    original_client_cls = httpx.AsyncClient

    class _MockAsyncClient(original_client_cls):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(_auth_fail_handler)
            super().__init__(*args, **kwargs)

    patched = crowdstrike_module.httpx.AsyncClient
    crowdstrike_module.httpx.AsyncClient = _MockAsyncClient
    try:
        log = await run_sync(db_session, connector)
    finally:
        crowdstrike_module.httpx.AsyncClient = patched
    await db_session.flush()

    assert log.status == "FAILED"

    await db_session.refresh(vuln)
    assert vuln.clean_scan_streak == 1, "a FAILED sync must not advance the streak"
    assert vuln.status == "OPEN", "a FAILED sync must never close a finding"


@pytest.mark.asyncio
async def test_redetected_finding_resets_streak(db_session, tenant_a):
    """A re-detected finding resets its clean_scan_streak to 0."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    # last_seen_at fresh (>= sync_start) simulates "re-detected this cycle" —
    # the reset-statement branch of the sweep, independent of the connector
    # mock's own (empty) fetch.
    fresh = datetime.now(UTC) + timedelta(seconds=5)
    vuln = _seed_vuln(
        tenant_a, asset_id=asset.id, status="OPEN", source="CROWDSTRIKE", last_seen_at=fresh, clean_scan_streak=1
    )
    db_session.add(vuln)
    connector = _seed_crowdstrike_connector(tenant_a)
    db_session.add(connector)
    await db_session.flush()

    log = await _run_sync_with_mock(db_session, connector)
    await db_session.flush()
    assert log.status == "SUCCESS"

    await db_session.refresh(vuln)
    assert vuln.clean_scan_streak == 0, f"re-detected row must reset streak to 0, got {vuln.clean_scan_streak}"
    assert vuln.status == "OPEN"
