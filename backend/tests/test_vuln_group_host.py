"""Phase 11 / Plan 01 — Wave 0 RED tests for ?group=host grouping.

Behaviour under test (UX-03-05 / D-V-01): GET /api/v1/vulnerabilities?group=host
returns one row per asset with denormalized severity counts and paginates on
HOST rows (not vuln rows).

These tests will FAIL initially:
- No `group` query param is wired on `list_vulns` yet.
- No `list_vulnerabilities_by_host()` service function exists yet.
- Both land in Task 11-01-03 (GREEN — service layer) + Task 11-01-04
  (router wiring).

T-11-02 (Pydantic Literal 422 for invalid group) and T-11-04 (tenant scope
via _apply_filters) are pinned by tests 5 + 6.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability


def _seed_asset(tenant_id, hostname: str) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=hostname,
        ip_addresses=[],
        mac_addresses=[],
        seen_by_sources=[],
    )


def _seed_vuln_on_asset(
    tenant_id,
    asset_id,
    *,
    cve_id: str,
    severity: str = "HIGH",
    cvss: float = 7.0,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity=severity,
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        cvss_v3_score=cvss,
        asset_id=asset_id,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_group_host_returns_one_row_per_asset(client, db_session, tenant_a):
    """D-V-01: ?group=host returns one row per host. 3+2 vulns across 2 hosts → 2 rows."""
    host_a = _seed_asset(tenant_a, "host-A")
    host_b = _seed_asset(tenant_a, "host-B")
    db_session.add(host_a)
    db_session.add(host_b)
    await db_session.flush()

    for i in range(3):
        db_session.add(_seed_vuln_on_asset(tenant_a, host_a.id, cve_id=f"CVE-GH-A{i}"))
    for i in range(2):
        db_session.add(_seed_vuln_on_asset(tenant_a, host_b.id, cve_id=f"CVE-GH-B{i}"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?group=host")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body.get("items", [])
    assert len(items) == 2, f"expected 2 host rows, got {len(items)}: {items}"
    # Each row carries a vuln_count + a host identifier.
    for row in items:
        assert "vuln_count" in row, f"row missing vuln_count: {row}"
        assert "host" in row or "asset_id" in row, f"row missing host identifier: {row}"


@pytest.mark.asyncio
async def test_group_host_severity_counts_match_seeded(client, db_session, tenant_a):
    """D-V-01: each host row carries critical_count/high_count/medium_count/low_count.

    Host A: 1 CRITICAL + 2 HIGH → critical_count=1, high_count=2, medium=0, low=0
    """
    host_a = _seed_asset(tenant_a, "host-counts-A")
    db_session.add(host_a)
    await db_session.flush()

    db_session.add(_seed_vuln_on_asset(tenant_a, host_a.id, cve_id="CVE-CNT-1", severity="CRITICAL"))
    db_session.add(_seed_vuln_on_asset(tenant_a, host_a.id, cve_id="CVE-CNT-2", severity="HIGH"))
    db_session.add(_seed_vuln_on_asset(tenant_a, host_a.id, cve_id="CVE-CNT-3", severity="HIGH"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?group=host")
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items", [])
    assert len(items) == 1, f"expected 1 host row, got {items}"
    row = items[0]
    assert row.get("critical_count") == 1, f"expected critical_count=1, got {row.get('critical_count')}"
    assert row.get("high_count") == 2, f"expected high_count=2, got {row.get('high_count')}"
    assert row.get("medium_count") == 0, f"expected medium_count=0, got {row.get('medium_count')}"
    assert row.get("low_count") == 0, f"expected low_count=0, got {row.get('low_count')}"


@pytest.mark.asyncio
async def test_group_host_pagination_on_host_rows_not_vuln_rows(client, db_session, tenant_a):
    """D-V-01: pagination is on HOST rows. 12 hosts × 5 vulns each =
    60 vuln rows but only 12 distinct host rows; ?page=1&page_size=10 returns
    10 host items and `total=12` (not 60).
    """
    hosts = []
    for h in range(12):
        a = _seed_asset(tenant_a, f"host-pag-{h:02d}")
        db_session.add(a)
        hosts.append(a)
    await db_session.flush()

    for host in hosts:
        for v in range(5):
            db_session.add(
                _seed_vuln_on_asset(
                    tenant_a, host.id, cve_id=f"CVE-PAG-{host.hostname}-{v}"
                )
            )
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?group=host&page=1&page_size=10")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body.get("items", [])
    assert len(items) == 10, f"expected 10 host rows on page 1, got {len(items)}"
    assert body.get("total") == 12, f"expected total=12 (hosts, not vulns), got {body.get('total')}"


@pytest.mark.asyncio
async def test_group_host_respects_severity_filter(client, db_session, tenant_a):
    """D-V-01: ?severity=CRITICAL&group=host returns only hosts with ≥1 CRITICAL.

    Host A has 1 CRITICAL → appears. Host B has only HIGH → does NOT appear.
    """
    host_a = _seed_asset(tenant_a, "host-flt-A")
    host_b = _seed_asset(tenant_a, "host-flt-B")
    db_session.add(host_a)
    db_session.add(host_b)
    await db_session.flush()

    db_session.add(_seed_vuln_on_asset(tenant_a, host_a.id, cve_id="CVE-FLT-A1", severity="CRITICAL"))
    db_session.add(_seed_vuln_on_asset(tenant_a, host_b.id, cve_id="CVE-FLT-B1", severity="HIGH"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?severity=CRITICAL&group=host")
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items", [])
    assert len(items) == 1, f"expected 1 host row (CRITICAL only), got {items}"
    only = items[0]
    # The single host must be host-A
    assert only.get("host") == "host-flt-A" or str(only.get("asset_id")) == str(host_a.id), (
        f"expected host-flt-A, got {only}"
    )


@pytest.mark.asyncio
async def test_group_host_respects_tenant_scope(
    client_factory, db_session, analyst_user, analyst_user_b, tenant_a, tenant_b
):
    """T-11-04: tenant_a analyst MUST NOT see tenant_b hosts in ?group=host.

    Critical IDOR guard — the host grouping must apply tenant scope BEFORE
    aggregation, otherwise tenant_a sees tenant_b's hosts in their facet bar.
    """
    host_a = _seed_asset(tenant_a, "host-iso-A")
    host_b = _seed_asset(tenant_b, "host-iso-B")
    db_session.add(host_a)
    db_session.add(host_b)
    await db_session.flush()

    db_session.add(_seed_vuln_on_asset(tenant_a, host_a.id, cve_id="CVE-ISO-A1"))
    db_session.add(_seed_vuln_on_asset(tenant_b, host_b.id, cve_id="CVE-ISO-B1"))
    await db_session.commit()

    a_client = client_factory(analyst_user)
    resp_a = await a_client.get("/api/v1/vulnerabilities?group=host")
    assert resp_a.status_code == 200, resp_a.text
    items_a = resp_a.json().get("items", [])
    hostnames_a = [item.get("host") for item in items_a]
    assert "host-iso-A" in hostnames_a, f"tenant_a should see host-iso-A: {hostnames_a}"
    assert "host-iso-B" not in hostnames_a, (
        f"IDOR: tenant_a should NOT see tenant_b host-iso-B: {hostnames_a}"
    )


@pytest.mark.asyncio
async def test_group_host_rejects_invalid_value_422(client):
    """T-11-02: ?group=floor is not in {cve, host} → Pydantic 422."""
    resp = await client.get("/api/v1/vulnerabilities?group=floor")
    assert resp.status_code == 422, resp.text
