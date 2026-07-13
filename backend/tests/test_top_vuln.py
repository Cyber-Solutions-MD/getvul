"""Phase 10 / Plan 01 — Wave 0 RED.

Behaviour under test: GET /api/v1/vulnerabilities/stats must expose a
top-level `top_vuln` field selecting the highest-CVSS OPEN CRITICAL
vuln for the tenant, with id (UUID) and human-facing fields (cve_id,
host, path, cvss, on_kev, exploited) per D-B-02 / D-H-03 (REQ UX-02-01).

Tests will fail until Task 2 lands top_vuln computation in dashboard.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability


def _seed_vuln(
    tenant_id,
    *,
    severity: str = "CRITICAL",
    status: str = "OPEN",
    cvss: float,
    cve_id: str,
    asset_id: uuid.UUID | None = None,
    exploit_available: bool = False,
    cisa_kev: bool = False,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity=severity,
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status=status,
        cvss_v3_score=cvss,
        asset_id=asset_id,
        affected_product="my-product/2.1.0",
        cisa_kev=cisa_kev,
        exploit_available=exploit_available,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_top_vuln_picks_highest_cvss_open_critical(client, db_session, tenant_a):
    """UX-02-01 / D-B-02 / D-H-03: top_vuln is the OPEN CRITICAL row with the
    highest CVSS. Must carry `id` (UUID string) so the frontend Hero CTA
    can POST /vulnerabilities/{id}/snooze (Blocker 2)."""
    # Asset to satisfy host field
    asset = Asset(tenant_id=tenant_a, hostname="prod-host-01.test")
    db_session.add(asset)
    await db_session.flush()

    db_session.add(_seed_vuln(tenant_a, cvss=7.5, cve_id="CVE-LOW", asset_id=asset.id))
    db_session.add(
        _seed_vuln(tenant_a, cvss=9.8, cve_id="CVE-WIN", asset_id=asset.id, cisa_kev=True, exploit_available=True)
    )
    db_session.add(_seed_vuln(tenant_a, cvss=8.0, cve_id="CVE-MID", asset_id=asset.id))
    await db_session.commit()

    body = (await client.get("/api/v1/vulnerabilities/stats")).json()
    assert "top_vuln" in body, "Missing top-level top_vuln"
    tv = body["top_vuln"]
    assert tv is not None
    assert tv["cve_id"] == "CVE-WIN"

    # Blocker 2: id (UUID) must be present so frontend can POST snooze/unsnooze
    assert "id" in tv
    uuid.UUID(tv["id"])  # raises if not a UUID

    # Visual fields the Hero renders
    for key in ("host", "path", "cvss", "on_kev", "exploited"):
        assert key in tv, f"top_vuln missing field: {key}"
    assert tv["on_kev"] is True
    assert tv["exploited"] is True


@pytest.mark.asyncio
async def test_top_vuln_null_when_no_open_critical(client, db_session, tenant_a):
    """UX-02-01: if there are no OPEN CRITICAL rows top_vuln is null
    (used by the 'quiet-win' Hero swap per D-O-04)."""
    # Seed a SUPPRESSED critical and an OPEN high — neither qualifies
    db_session.add(_seed_vuln(tenant_a, status="SUPPRESSED", cvss=9.0, cve_id="CVE-SUP"))
    db_session.add(_seed_vuln(tenant_a, severity="HIGH", cvss=8.0, cve_id="CVE-HIGH"))
    await db_session.commit()

    body = (await client.get("/api/v1/vulnerabilities/stats")).json()
    assert body.get("top_vuln") is None
