"""Phase 11 / Plan 01 — Wave 0 RED tests for expanded sort axes.

Behaviour under test (UX-03-01 / D-T-01): GET /api/v1/vulnerabilities must
accept ?sort=severity|cve_id|cvss_v3_score|sla_due_at paired with
?order=asc|desc and surface unknown values as Pydantic 422 (T-11-01).

These tests will FAIL initially:
- The current `VulnerabilityFilter.sort` Literal only allows {"triage", "severity"};
  the four new axes land in Task 11-01-03 (GREEN).
- The `order` query param does not yet exist on `list_vulns`.

The existing `?sort=triage` test (test 7) protects the Phase 10 regression.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.vulnerabilities.models import Vulnerability


def _seed_vuln(
    tenant_id,
    *,
    cve_id: str,
    severity: str = "HIGH",
    cisa_kev: bool = False,
    cvss: float | None = 7.0,
    sla_due_at: datetime | None = None,
) -> Vulnerability:
    """Phase 10 fixture pattern — accept the kwargs the sort tests vary."""
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity=severity,
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
async def test_sort_severity_desc_orders_critical_first(client, db_session, tenant_a):
    """D-T-01: ?sort=severity&order=desc returns CRITICAL → HIGH → MEDIUM → LOW.

    Severity-case rank — CRITICAL is highest (numerically first) and LOW is lowest.
    The default severity sort already exists today; this test pins the explicit
    Literal entry + the desc/asc toggle wired through `order`.
    """
    crit = _seed_vuln(tenant_a, cve_id="CVE-S-CRIT", severity="CRITICAL")
    high = _seed_vuln(tenant_a, cve_id="CVE-S-HIGH", severity="HIGH")
    med = _seed_vuln(tenant_a, cve_id="CVE-S-MED", severity="MEDIUM")
    low = _seed_vuln(tenant_a, cve_id="CVE-S-LOW", severity="LOW")
    for v in (crit, high, med, low):
        db_session.add(v)
    await db_session.commit()
    expected_ids = [str(crit.id), str(high.id), str(med.id), str(low.id)]

    resp = await client.get("/api/v1/vulnerabilities?sort=severity&order=desc&limit=4")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body.get("items", body if isinstance(body, list) else [])
    got_ids = [item["id"] for item in items[:4]]
    assert got_ids == expected_ids, f"severity desc: got {got_ids}, expected {expected_ids}"


@pytest.mark.asyncio
async def test_sort_cve_id_asc_orders_lexicographically(client, db_session, tenant_a):
    """D-T-01: ?sort=cve_id&order=asc returns lexicographically ascending CVE IDs.

    Seed three CVEs across two years. ASCII sort: '2023' < '2024', then within
    2024 numeric strings sort lexicographically ('0001' < '9999').
    """
    later = _seed_vuln(tenant_a, cve_id="CVE-2024-9999")
    early_2024 = _seed_vuln(tenant_a, cve_id="CVE-2024-0001")
    oldest = _seed_vuln(tenant_a, cve_id="CVE-2023-5555")
    for v in (later, early_2024, oldest):
        db_session.add(v)
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?sort=cve_id&order=asc&limit=3")
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items", [])
    got_cves = [item["cve_id"] for item in items[:3]]
    assert got_cves == [
        "CVE-2023-5555",
        "CVE-2024-0001",
        "CVE-2024-9999",
    ], f"cve_id asc: got {got_cves}"


@pytest.mark.asyncio
async def test_sort_cvss_v3_score_desc_orders_highest_first(client, db_session, tenant_a):
    """D-T-01: ?sort=cvss_v3_score&order=desc returns 9.8 → 7.5 → 4.2.

    Also pins nulls-last semantics: a vuln with NULL cvss_v3_score must not
    surface above any scored vuln regardless of order direction.
    """
    high = _seed_vuln(tenant_a, cve_id="CVE-CVSS-9", cvss=9.8)
    mid = _seed_vuln(tenant_a, cve_id="CVE-CVSS-7", cvss=7.5)
    low = _seed_vuln(tenant_a, cve_id="CVE-CVSS-4", cvss=4.2)
    nullscore = _seed_vuln(tenant_a, cve_id="CVE-CVSS-NULL", cvss=None)
    for v in (high, mid, low, nullscore):
        db_session.add(v)
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?sort=cvss_v3_score&order=desc&limit=4")
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items", [])
    got_cves = [item["cve_id"] for item in items[:4]]
    # First three must be the scored rows in descending order; NULL row last.
    assert got_cves[:3] == [
        "CVE-CVSS-9",
        "CVE-CVSS-7",
        "CVE-CVSS-4",
    ], f"cvss desc: got {got_cves}"
    assert got_cves[3] == "CVE-CVSS-NULL", "NULL cvss must sort last (nulls_last)"


@pytest.mark.asyncio
async def test_sort_sla_due_at_asc_orders_soonest_first(client, db_session, tenant_a):
    """D-T-01: ?sort=sla_due_at&order=asc returns soonest-due first.

    nulls-last: a vuln with no sla_due_at must not surface above a vuln with
    a date set.
    """
    now = datetime.now(UTC)
    soon = _seed_vuln(tenant_a, cve_id="CVE-SLA-SOON", sla_due_at=now + timedelta(days=1))
    week = _seed_vuln(tenant_a, cve_id="CVE-SLA-WEEK", sla_due_at=now + timedelta(days=7))
    month = _seed_vuln(tenant_a, cve_id="CVE-SLA-MONTH", sla_due_at=now + timedelta(days=30))
    nodate = _seed_vuln(tenant_a, cve_id="CVE-SLA-NULL", sla_due_at=None)
    for v in (soon, week, month, nodate):
        db_session.add(v)
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?sort=sla_due_at&order=asc&limit=4")
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items", [])
    got_cves = [item["cve_id"] for item in items[:4]]
    assert got_cves[:3] == [
        "CVE-SLA-SOON",
        "CVE-SLA-WEEK",
        "CVE-SLA-MONTH",
    ], f"sla_due_at asc: got {got_cves}"
    assert got_cves[3] == "CVE-SLA-NULL", "NULL sla_due_at must sort last (nulls_last)"


@pytest.mark.asyncio
async def test_list_response_includes_sla_state_key(client, db_session, tenant_a):
    """Phase 36 / SLA-01/SLA-02, Pitfall 3: GET /vulnerabilities list items
    carry `sla_state` + `sla_due_at` (previously undeclared on
    VulnerabilitySummary -- FastAPI silently drops undeclared response-model
    attributes). Covers the D-03 NULL-score severity fallback (mapped to the
    "critical" tier via severity, not the "moderate" default) and the D-12
    not_tracked floor (risk_exposure_score < 20).
    """
    now = datetime.now(UTC)
    fallback = _seed_vuln(tenant_a, cve_id="CVE-SLA36-FALLBACK", severity="CRITICAL")
    fallback.first_detected_at = now - timedelta(days=10)  # > critical's 7d fallback window
    floor = _seed_vuln(tenant_a, cve_id="CVE-SLA36-FLOOR", severity="LOW")
    floor.risk_exposure_score = 10  # < RISK_SCORE_TIER_MEDIUM (20) -> D-12 not_tracked
    for v in (fallback, floor):
        db_session.add(v)
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?cve_id=CVE-SLA36&limit=10")
    assert resp.status_code == 200, resp.text
    by_cve = {item["cve_id"]: item for item in resp.json().get("items", [])}

    assert "sla_state" in by_cve["CVE-SLA36-FALLBACK"]
    assert "sla_due_at" in by_cve["CVE-SLA36-FALLBACK"]
    assert by_cve["CVE-SLA36-FALLBACK"]["sla_state"] == "breached"
    assert by_cve["CVE-SLA36-FALLBACK"]["sla_due_at"] is not None

    assert by_cve["CVE-SLA36-FLOOR"]["sla_state"] == "not_tracked"
    assert by_cve["CVE-SLA36-FLOOR"]["sla_due_at"] is None


@pytest.mark.asyncio
async def test_detail_response_includes_sla_state_key(client, db_session, tenant_a):
    """Phase 36 / SLA-01/SLA-02: GET /vulnerabilities/{id} ALSO carries
    sla_state + sla_due_at — this phase's must_haves require BOTH the list
    AND the detail response to carry these fields."""
    now = datetime.now(UTC)
    v = _seed_vuln(tenant_a, cve_id="CVE-SLA36-DETAIL", severity="CRITICAL")
    v.first_detected_at = now - timedelta(days=1)  # within critical's 7d window -> on_track
    db_session.add(v)
    await db_session.commit()

    resp = await client.get(f"/api/v1/vulnerabilities/{v.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sla_state"] == "on_track"
    assert body["sla_due_at"] is not None


@pytest.mark.asyncio
async def test_sort_rejects_invalid_field_with_422(client):
    """T-11-01: ?sort=password is not in the Literal allow-list → 422 not 500.

    Pydantic's Literal validator surfaces the rejection before the route
    handler ever runs; the response body must include a `detail` field naming
    the bad field so the frontend can surface a useful error.
    """
    resp = await client.get("/api/v1/vulnerabilities?sort=password")
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "detail" in body, f"expected 'detail' in 422 body: {body}"


@pytest.mark.asyncio
async def test_sort_rejects_invalid_order_with_422(client):
    """T-11-01: ?order=upward is not in {asc, desc} → 422 not 500."""
    resp = await client.get("/api/v1/vulnerabilities?sort=cve_id&order=upward")
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_sort_triage_still_works_phase10_carryover(client, db_session, tenant_a):
    """Phase 10 regression guard: ?sort=triage continues to order
    KEV-true first then by CVSS desc, with SLA-due asc as final tiebreaker.

    Seed mirrors test_triage_sort.py::test_triage_sort_order so a single
    regression in Task 11-01-03's GREEN edit shows up here too.
    """
    now = datetime.now(UTC)
    a = _seed_vuln(tenant_a, cve_id="CVE-T11-A", cisa_kev=True, cvss=7.0)
    b = _seed_vuln(tenant_a, cve_id="CVE-T11-B", cisa_kev=True, cvss=9.5)
    c = _seed_vuln(tenant_a, cve_id="CVE-T11-C", cisa_kev=False, cvss=9.8)
    d = _seed_vuln(
        tenant_a,
        cve_id="CVE-T11-D",
        cisa_kev=False,
        cvss=8.0,
        sla_due_at=now - timedelta(days=1),
    )
    for v in (a, b, c, d):
        db_session.add(v)
    await db_session.commit()
    expected_ids = [str(b.id), str(a.id), str(c.id), str(d.id)]

    resp = await client.get("/api/v1/vulnerabilities?sort=triage&limit=4")
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items", [])
    got_ids = [item["id"] for item in items[:4]]
    assert got_ids == expected_ids, f"triage carryover: got {got_ids}, expected {expected_ids}"
