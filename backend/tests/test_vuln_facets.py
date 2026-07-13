"""Phase 11 / Plan 01 — Wave 0 RED tests for ?facets= contextual counts.

Behaviour under test (UX-03-01 / D-F-02): GET /api/v1/vulnerabilities accepts
?facets=severity,source,status and returns a `facets` object whose counts are
computed under all OTHER applied filters (Pitfall 1 — facet for severity
ignores the severity filter so the chip-bar can keep showing alternatives).

These tests will FAIL initially:
- No `facets` query param is wired on `list_vulns` yet.
- No `get_facets()` service function exists yet.
- Both land in Task 11-01-03 (GREEN — service layer) + Task 11-01-04
  (router wiring + response wrapper).

Tenant scope (T-11-04) and 400 on unknown facet group (T-11-03) round out
the threat coverage.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.vulnerabilities.models import Vulnerability


def _seed_vuln(
    tenant_id,
    *,
    cve_id: str,
    severity: str = "HIGH",
    source: str = "CROWDSTRIKE",
    status: str = "OPEN",
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity=severity,
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        status=status,
        cvss_v3_score=7.0,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_facets_returned_when_requested(client, db_session, tenant_a):
    """D-F-02: ?facets=severity returns severity counts in `facets.severity`."""
    for i in range(3):
        db_session.add(_seed_vuln(tenant_a, cve_id=f"CVE-F-C{i}", severity="CRITICAL"))
    for i in range(5):
        db_session.add(_seed_vuln(tenant_a, cve_id=f"CVE-F-H{i}", severity="HIGH"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?facets=severity")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "facets" in body, f"expected 'facets' key in response: {body}"
    assert "severity" in body["facets"], f"expected 'severity' subkey in facets: {body['facets']}"
    sev = body["facets"]["severity"]
    assert sev.get("CRITICAL") == 3, f"expected 3 CRITICAL, got {sev}"
    assert sev.get("HIGH") == 5, f"expected 5 HIGH, got {sev}"


@pytest.mark.asyncio
async def test_facets_omitted_when_not_requested(client, db_session, tenant_a):
    """D-F-02: without ?facets=, response carries no facets payload."""
    db_session.add(_seed_vuln(tenant_a, cve_id="CVE-F-NO", severity="LOW"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Either the key is absent or its value is None — both are acceptable
    # contracts. The shape MUST NOT carry zero-counted maps as if they were
    # requested.
    facets = body.get("facets")
    assert facets is None, f"expected no facets payload when not requested, got {facets}"


@pytest.mark.asyncio
async def test_facets_contextual_to_other_filters(client, db_session, tenant_a):
    """Pitfall 1: severity facet must be computed WITHOUT the severity filter
    so the chip bar can still show alternative severities to switch to.

    Seed: 5 CRITICAL + 10 HIGH, half QUALYS / half TENABLE for each. Filter by
    `?source=QUALYS&facets=severity` — the severity facet must ignore the
    source filter? NO — re-read Pitfall 1: severity facet ignores the SEVERITY
    filter, but RESPECTS the source filter. So under ?source=QUALYS, severity
    facet shows: CRITICAL=3 (QUALYS only), HIGH=5 (QUALYS only).

    Wait — re-reading RESEARCH "Pitfall 1: facet counts that contradict the
    visible table" + "all OTHER filters except the one we're showing": the
    severity facet is computed under all filters EXCEPT severity. The source
    filter IS one of the "other" filters and stays applied. So the expected
    result is QUALYS-only counts of each severity.
    """
    # 6 CRITICAL: 3 QUALYS + 3 TENABLE
    for i in range(3):
        db_session.add(_seed_vuln(tenant_a, cve_id=f"CVE-PF1-CQ{i}", severity="CRITICAL", source="QUALYS"))
    for i in range(3):
        db_session.add(_seed_vuln(tenant_a, cve_id=f"CVE-PF1-CT{i}", severity="CRITICAL", source="TENABLE"))
    # 10 HIGH: 5 QUALYS + 5 TENABLE
    for i in range(5):
        db_session.add(_seed_vuln(tenant_a, cve_id=f"CVE-PF1-HQ{i}", severity="HIGH", source="QUALYS"))
    for i in range(5):
        db_session.add(_seed_vuln(tenant_a, cve_id=f"CVE-PF1-HT{i}", severity="HIGH", source="TENABLE"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?source=QUALYS&facets=severity")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sev = body.get("facets", {}).get("severity", {})
    # Source filter still applies; severity filter does not.
    assert sev.get("CRITICAL") == 3, f"expected 3 CRITICAL QUALYS, got {sev}"
    assert sev.get("HIGH") == 5, f"expected 5 HIGH QUALYS, got {sev}"


@pytest.mark.asyncio
async def test_facets_respect_tenant_scope(
    client_factory, db_session, analyst_user, analyst_user_b, tenant_a, tenant_b
):
    """T-11-04 / ASVS V4 IDOR: tenant_a analyst gets ONLY tenant_a's counts.

    Seed CRITICAL in both tenants; assert tenant_a only sees its own.
    """
    db_session.add(_seed_vuln(tenant_a, cve_id="CVE-TA-1", severity="CRITICAL"))
    db_session.add(_seed_vuln(tenant_a, cve_id="CVE-TA-2", severity="CRITICAL"))
    db_session.add(_seed_vuln(tenant_b, cve_id="CVE-TB-1", severity="CRITICAL"))
    db_session.add(_seed_vuln(tenant_b, cve_id="CVE-TB-2", severity="CRITICAL"))
    db_session.add(_seed_vuln(tenant_b, cve_id="CVE-TB-3", severity="CRITICAL"))
    await db_session.commit()

    a_client = client_factory(analyst_user)
    resp_a = await a_client.get("/api/v1/vulnerabilities?facets=severity")
    assert resp_a.status_code == 200, resp_a.text
    sev_a = resp_a.json().get("facets", {}).get("severity", {})
    assert sev_a.get("CRITICAL") == 2, f"tenant_a should see only its 2 CRITICAL, got {sev_a}"

    b_client = client_factory(analyst_user_b)
    resp_b = await b_client.get("/api/v1/vulnerabilities?facets=severity")
    assert resp_b.status_code == 200, resp_b.text
    sev_b = resp_b.json().get("facets", {}).get("severity", {})
    assert sev_b.get("CRITICAL") == 3, f"tenant_b should see its 3 CRITICAL, got {sev_b}"


@pytest.mark.asyncio
async def test_facets_rejects_unknown_group_400(client):
    """T-11-03: ?facets=password is not in {severity, source, status} → 400.

    A 500 here would be a leaky internal error; 400 surfaces the bad input
    cleanly to the frontend.
    """
    resp = await client.get("/api/v1/vulnerabilities?facets=password")
    assert resp.status_code == 400, resp.text
    body = resp.json()
    detail = body.get("detail", "")
    assert isinstance(detail, str)
    # Surfaced detail must name the bad field so the frontend can show a
    # useful error (not just "Bad Request").
    assert "password" in detail.lower() or "unknown" in detail.lower(), (
        f"expected detail to name bad facet group, got: {detail}"
    )


@pytest.mark.asyncio
async def test_facets_severity_source_status_all_three_groups(client, db_session, tenant_a):
    """D-F-02: ?facets=severity,source,status returns all three count maps."""
    # Seed at least one row per (severity, source, status) so all groups
    # contain non-empty data.
    db_session.add(_seed_vuln(tenant_a, cve_id="CVE-3F-1", severity="CRITICAL", source="QUALYS", status="OPEN"))
    db_session.add(_seed_vuln(tenant_a, cve_id="CVE-3F-2", severity="HIGH", source="CROWDSTRIKE", status="IN_PROGRESS"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?facets=severity,source,status")
    assert resp.status_code == 200, resp.text
    facets = resp.json().get("facets", {})
    assert isinstance(facets.get("severity"), dict) and facets["severity"], "severity facet missing/empty"
    assert isinstance(facets.get("source"), dict) and facets["source"], "source facet missing/empty"
    assert isinstance(facets.get("status"), dict) and facets["status"], "status facet missing/empty"
