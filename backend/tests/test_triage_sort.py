"""Phase 10 / Plan 01 — Wave 0 RED.

Behaviour under test: GET /api/v1/vulnerabilities?sort=triage must order
rows KEV desc → CVSS desc → SLA-due asc per D-B-03 / D-T-01 (REQ UX-02-04).
?sort=garbage must 422. Limit must be honoured.

Tests will fail until Task 2 lands the triage ordering branch in
backend/app/vulnerabilities/service.py::list_vulnerabilities.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.vulnerabilities.models import Vulnerability


def _seed_vuln(
    tenant_id,
    *,
    cisa_kev: bool,
    cvss: float,
    sla_due_at: datetime | None,
    cve_id: str,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity="HIGH",
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        cisa_kev=cisa_kev,
        cvss_v3_score=cvss,
        sla_due_at=sla_due_at,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_triage_sort_order(client, db_session, tenant_a):
    """UX-02-04 / D-T-01: KEV-true first (highest-CVSS within), then KEV-false
    by CVSS desc, with SLA-asc as final tiebreaker.

    Seed:
      A: KEV=true,  CVSS=7.0
      B: KEV=true,  CVSS=9.5    → first
      C: KEV=false, CVSS=9.8    → third (highest CVSS but KEV-false)
      D: KEV=false, CVSS=8.0, sla_due_at=earliest → fourth
    Expected order: [B, A, C, D]
    """
    now = datetime.now(UTC)
    a = _seed_vuln(tenant_a, cisa_kev=True, cvss=7.0, sla_due_at=None, cve_id="CVE-T-A")
    b = _seed_vuln(tenant_a, cisa_kev=True, cvss=9.5, sla_due_at=None, cve_id="CVE-T-B")
    c = _seed_vuln(tenant_a, cisa_kev=False, cvss=9.8, sla_due_at=None, cve_id="CVE-T-C")
    d = _seed_vuln(tenant_a, cisa_kev=False, cvss=8.0, sla_due_at=now - timedelta(days=1), cve_id="CVE-T-D")
    for v in (a, b, c, d):
        db_session.add(v)
    await db_session.commit()
    expected_ids = [str(b.id), str(a.id), str(c.id), str(d.id)]

    resp = await client.get("/api/v1/vulnerabilities?sort=triage&limit=4")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # PaginatedResponse shape — items key carries the rows
    items = body.get("items", body if isinstance(body, list) else [])
    got_ids = [item["id"] for item in items[:4]]
    assert got_ids == expected_ids, f"triage order: got {got_ids} expected {expected_ids}"


@pytest.mark.asyncio
async def test_triage_sort_limit_honored(client, db_session, tenant_a):
    """UX-02-04: ?sort=triage&limit=2 returns at most 2 rows even with 4 seeded."""
    for cve in ("CVE-LIM-1", "CVE-LIM-2", "CVE-LIM-3", "CVE-LIM-4"):
        db_session.add(_seed_vuln(tenant_a, cisa_kev=False, cvss=8.0, sla_due_at=None, cve_id=cve))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?sort=triage&limit=2")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body.get("items", body if isinstance(body, list) else [])
    assert len(items) <= 2


@pytest.mark.asyncio
async def test_triage_sort_rejects_invalid_value(client):
    """UX-02-04 / T-10-07: pydantic enum validation rejects ?sort=garbage as 422."""
    resp = await client.get("/api/v1/vulnerabilities?sort=garbage")
    assert resp.status_code == 422, resp.text
