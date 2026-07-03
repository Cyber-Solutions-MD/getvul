"""Phase 04 / Plan 02 — Wave 0 RED tests for VulnSource enum extension + source filter.

Behaviour under test (PROD-04-03 / PROD-04-04):
  - VulnSource enum has exactly 6 members including QUALYS and RAPID7 (D-10).
  - GET /api/v1/vulnerabilities?source=QUALYS returns only QUALYS rows.
  - GET /api/v1/vulnerabilities?source=RAPID7 returns only RAPID7 rows.
  - Tenant isolation: tenant_b's QUALYS rows never surface for tenant_a.

test_vuln_source_enum_members FAILS until Task 2 adds QUALYS/RAPID7 to VulnSource.
The three API tests require Postgres (skip gracefully when unreachable).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.vulnerabilities.models import Vulnerability, VulnSource


def _seed(tenant_id, source: str, cve_id: str) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity="HIGH",
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )


def test_vuln_source_enum_members():
    assert VulnSource.QUALYS.value == "QUALYS"
    assert VulnSource.RAPID7.value == "RAPID7"
    assert {m.value for m in VulnSource} == {
        "CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ", "QUALYS", "RAPID7"
    }


@pytest.mark.asyncio
async def test_source_filter_qualys(client, db_session, tenant_a):
    db_session.add(_seed(tenant_a, "QUALYS", "CVE-Q-001"))
    db_session.add(_seed(tenant_a, "RAPID7", "CVE-R-001"))
    await db_session.commit()
    resp = await client.get("/api/v1/vulnerabilities?source=QUALYS")
    assert resp.status_code == 200
    sources = {i["source"] for i in resp.json()["items"]}
    assert sources == {"QUALYS"}, f"expected only QUALYS, got {sources}"


@pytest.mark.asyncio
async def test_source_filter_rapid7(client, db_session, tenant_a):
    db_session.add(_seed(tenant_a, "QUALYS", "CVE-Q-002"))
    db_session.add(_seed(tenant_a, "RAPID7", "CVE-R-002"))
    await db_session.commit()
    resp = await client.get("/api/v1/vulnerabilities?source=RAPID7")
    assert resp.status_code == 200
    sources = {i["source"] for i in resp.json()["items"]}
    assert sources == {"RAPID7"}, f"expected only RAPID7, got {sources}"


@pytest.mark.asyncio
async def test_source_filter_tenant_scoped(
    client_factory, db_session, analyst_user, tenant_a, tenant_b
):
    """PROD-04-04 tenant isolation: tenant_b QUALYS rows must not surface for tenant_a."""
    db_session.add(_seed(tenant_a, "QUALYS", "CVE-TA-Q-001"))
    db_session.add(_seed(tenant_b, "QUALYS", "CVE-TB-Q-001"))
    db_session.add(_seed(tenant_b, "QUALYS", "CVE-TB-Q-002"))
    await db_session.commit()
    a_client = client_factory(analyst_user)
    resp = await a_client.get("/api/v1/vulnerabilities?source=QUALYS")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1, f"tenant_a should see exactly 1 QUALYS row, got {len(items)}"
    assert items[0]["source"] == "QUALYS"
