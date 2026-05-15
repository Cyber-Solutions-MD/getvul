"""Phase 10 / Plan 01 — Wave 0 RED.

Behaviour under test: GET /api/v1/vulnerabilities/trends must expose a
top-level `severity_trends` field shaped {YYYY-MM-DD: {critical, high,
medium, low}} per D-B-01 / D-C-09 (REQ UX-02-03).

Tests will fail until Task 2 lands the reshape in
backend/app/vulnerabilities/trends.py::get_all_trends.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.vulnerabilities.models import Vulnerability

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _seed_vuln(
    tenant_id: uuid.UUID,
    *,
    severity: str = "CRITICAL",
    cve_id: str | None = None,
    detected_at: datetime | None = None,
    cvss: float | None = 9.8,
    cisa_kev: bool = False,
) -> Vulnerability:
    """Build a minimal Vulnerability row for trend seeding."""
    now = detected_at or datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id or f"CVE-2099-{uuid.uuid4().hex[:4]}",
        severity=severity,
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        cisa_kev=cisa_kev,
        cvss_v3_score=cvss,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_severity_trends_shape_30_day(client, db_session, tenant_a):
    """UX-02-03 / D-B-01: response includes severity_trends dict keyed by
    ISO date, each value carries critical/high/medium/low ints."""
    # Seed one vuln so the timeline has at least one non-zero bucket
    db_session.add(_seed_vuln(tenant_a, severity="CRITICAL"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities/trends?days=30")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "severity_trends" in body, "Missing top-level severity_trends key"

    st = body["severity_trends"]
    assert isinstance(st, dict)
    for day_key, counts in st.items():
        assert DATE_RE.match(day_key), f"Unexpected date key shape: {day_key!r}"
        assert set(counts.keys()) == {"critical", "high", "medium", "low"}, counts
        for v in counts.values():
            assert isinstance(v, int)


@pytest.mark.asyncio
async def test_severity_trends_length_matches_days(client):
    """UX-02-03: dict has one bucket per requested day for 7 / 30 / 90."""
    for days in (7, 30, 90):
        resp = await client.get(f"/api/v1/vulnerabilities/trends?days={days}")
        assert resp.status_code == 200, resp.text
        st = resp.json()["severity_trends"]
        assert len(st) == days, f"days={days} returned len(severity_trends)={len(st)}"


@pytest.mark.asyncio
async def test_severity_trends_tenant_isolated(
    client_factory, db_session, analyst_user, analyst_user_b, tenant_a, tenant_b
):
    """D-B-01 + TENANT-01: analyst in tenant A must not see tenant B's
    severity counts in their severity_trends payload."""
    # Tenant A gets a CRITICAL vuln; tenant B gets a HIGH vuln on the same
    # day. The two analysts should each see only their own tenant's counts.
    now = datetime.now(UTC) - timedelta(days=1)
    db_session.add(_seed_vuln(tenant_a, severity="CRITICAL", detected_at=now))
    db_session.add(_seed_vuln(tenant_b, severity="HIGH", detected_at=now))
    await db_session.commit()

    client_a = client_factory(analyst_user)
    client_b = client_factory(analyst_user_b)

    a_st = (await client_a.get("/api/v1/vulnerabilities/trends?days=7")).json()["severity_trends"]
    b_st = (await client_b.get("/api/v1/vulnerabilities/trends?days=7")).json()["severity_trends"]

    a_total_critical = sum(d["critical"] for d in a_st.values())
    a_total_high = sum(d["high"] for d in a_st.values())
    b_total_critical = sum(d["critical"] for d in b_st.values())
    b_total_high = sum(d["high"] for d in b_st.values())

    assert a_total_critical >= 1
    assert a_total_high == 0, "tenant A leaked tenant B's HIGH vuln"
    assert b_total_high >= 1
    assert b_total_critical == 0, "tenant B leaked tenant A's CRITICAL vuln"
