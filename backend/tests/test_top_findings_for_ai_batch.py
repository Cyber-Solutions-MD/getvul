"""Tests for get_top_findings_for_ai_batch() -- Phase 26 Plan 07 (AIP-02),
the D-01 top-N batch-scope query. Mirrors test_triage_sort.py's
_seed_vuln()-style seed-and-assert convention (per 26-PATTERNS.md's own
correction: this is the correct test home, NOT the nonexistent
test_vulnerabilities_service.py), extended to also seed Asset.risk_score
(Assumption A1: the ASSET-02 per-asset score is the PRIMARY sort key).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.service import get_top_findings_for_ai_batch


def _seed_asset(tenant_id, *, risk_score: int | None, hostname: str) -> Asset:
    return Asset(tenant_id=tenant_id, hostname=hostname, risk_score=risk_score)


def _seed_vuln(
    tenant_id,
    *,
    asset_id=None,
    status: str = "OPEN",
    cisa_kev: bool = False,
    cvss: float | None = None,
    sla_due_at: datetime | None = None,
    cve_id: str,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=cve_id,
        severity="HIGH",
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status=status,
        cisa_kev=cisa_kev,
        cvss_v3_score=cvss,
        sla_due_at=sla_due_at,
        first_detected_at=now,
        last_seen_at=now,
    )


async def test_orders_by_asset_risk_score_primary_then_kev_cvss_sla_tiebreak(db_session, tenant_a):
    """Assumption A1: Asset.risk_score is the PRIMARY sort key -- a finding
    on a LOWER-risk_score asset must sort AFTER every finding on a
    HIGHER-risk_score asset, even when its own KEV/CVSS factors are
    individually higher. Within one asset, KEV desc -> CVSS desc breaks
    the tie (mirrors sort="triage")."""
    asset_hi = _seed_asset(tenant_a, risk_score=90, hostname=f"hi-risk-{uuid.uuid4().hex[:8]}")
    asset_lo = _seed_asset(tenant_a, risk_score=10, hostname=f"lo-risk-{uuid.uuid4().hex[:8]}")
    db_session.add_all([asset_hi, asset_lo])
    await db_session.flush()

    v_hi_kev = _seed_vuln(tenant_a, asset_id=asset_hi.id, cisa_kev=True, cvss=7.0, cve_id="CVE-TN-HI-KEV")
    v_hi_plain = _seed_vuln(tenant_a, asset_id=asset_hi.id, cisa_kev=False, cvss=9.5, cve_id="CVE-TN-HI-PLAIN")
    # Higher CVSS + KEV than anything on asset_hi, but on the LOWER-risk_score
    # asset -- must still sort LAST if Asset.risk_score is truly primary.
    v_lo_kev = _seed_vuln(tenant_a, asset_id=asset_lo.id, cisa_kev=True, cvss=9.9, cve_id="CVE-TN-LO-KEV")
    db_session.add_all([v_hi_kev, v_hi_plain, v_lo_kev])
    await db_session.commit()

    result = await get_top_findings_for_ai_batch(db_session, tenant_a, limit=10)

    assert result == [v_hi_kev.id, v_hi_plain.id, v_lo_kev.id]


async def test_asset_less_finding_sorts_last_via_nulls_last(db_session, tenant_a):
    """A finding with no asset (Asset.risk_score effectively NULL via the
    outer join) never crowds out a scored finding, regardless of its own
    KEV/CVSS factors."""
    asset = _seed_asset(tenant_a, risk_score=50, hostname=f"scored-{uuid.uuid4().hex[:8]}")
    db_session.add(asset)
    await db_session.flush()

    v_scored = _seed_vuln(tenant_a, asset_id=asset.id, cvss=1.0, cve_id="CVE-TN-SCORED")
    v_no_asset = _seed_vuln(tenant_a, asset_id=None, cisa_kev=True, cvss=9.9, cve_id="CVE-TN-NOASSET")
    db_session.add_all([v_scored, v_no_asset])
    await db_session.commit()

    result = await get_top_findings_for_ai_batch(db_session, tenant_a, limit=10)

    assert result == [v_scored.id, v_no_asset.id]


async def test_limit_is_respected(db_session, tenant_a):
    asset = _seed_asset(tenant_a, risk_score=50, hostname=f"limit-{uuid.uuid4().hex[:8]}")
    db_session.add(asset)
    await db_session.flush()

    for i in range(5):
        db_session.add(_seed_vuln(tenant_a, asset_id=asset.id, cvss=float(i), cve_id=f"CVE-TN-LIM-{i}"))
    await db_session.commit()

    result = await get_top_findings_for_ai_batch(db_session, tenant_a, limit=2)

    assert len(result) == 2


async def test_excludes_remediated_suppressed_false_positive_includes_open_and_in_progress(db_session, tenant_a):
    asset = _seed_asset(tenant_a, risk_score=50, hostname=f"status-{uuid.uuid4().hex[:8]}")
    db_session.add(asset)
    await db_session.flush()

    v_open = _seed_vuln(tenant_a, asset_id=asset.id, status="OPEN", cve_id="CVE-TN-OPEN")
    v_in_progress = _seed_vuln(tenant_a, asset_id=asset.id, status="IN_PROGRESS", cve_id="CVE-TN-INPROG")
    v_remediated = _seed_vuln(tenant_a, asset_id=asset.id, status="REMEDIATED", cve_id="CVE-TN-REM")
    v_suppressed = _seed_vuln(tenant_a, asset_id=asset.id, status="SUPPRESSED", cve_id="CVE-TN-SUP")
    v_false_positive = _seed_vuln(tenant_a, asset_id=asset.id, status="FALSE_POSITIVE", cve_id="CVE-TN-FP")
    db_session.add_all([v_open, v_in_progress, v_remediated, v_suppressed, v_false_positive])
    await db_session.commit()

    result = await get_top_findings_for_ai_batch(db_session, tenant_a, limit=10)

    assert set(result) == {v_open.id, v_in_progress.id}


async def test_tenant_scoped(db_session, tenant_a, tenant_b):
    asset_a = _seed_asset(tenant_a, risk_score=50, hostname=f"asset-a-{uuid.uuid4().hex[:8]}")
    asset_b = _seed_asset(tenant_b, risk_score=99, hostname=f"asset-b-{uuid.uuid4().hex[:8]}")
    db_session.add_all([asset_a, asset_b])
    await db_session.flush()

    v_a = _seed_vuln(tenant_a, asset_id=asset_a.id, cve_id="CVE-TN-A")
    v_b = _seed_vuln(tenant_b, asset_id=asset_b.id, cve_id="CVE-TN-B")
    db_session.add_all([v_a, v_b])
    await db_session.commit()

    result = await get_top_findings_for_ai_batch(db_session, tenant_a, limit=10)

    assert result == [v_a.id]


async def test_sla_due_at_is_the_final_tiebreak(db_session, tenant_a):
    """Within the same asset, and with equal KEV/CVSS, the earlier
    sla_due_at (already-closer-to-breach) sorts first (asc, nulls_last)."""
    asset = _seed_asset(tenant_a, risk_score=50, hostname=f"sla-{uuid.uuid4().hex[:8]}")
    db_session.add(asset)
    await db_session.flush()

    now = datetime.now(UTC)
    v_later = _seed_vuln(
        tenant_a,
        asset_id=asset.id,
        cisa_kev=False,
        cvss=8.0,
        sla_due_at=now + timedelta(days=10),
        cve_id="CVE-TN-LATER",
    )
    v_earlier = _seed_vuln(
        tenant_a,
        asset_id=asset.id,
        cisa_kev=False,
        cvss=8.0,
        sla_due_at=now - timedelta(days=1),
        cve_id="CVE-TN-EARLIER",
    )
    v_no_sla = _seed_vuln(tenant_a, asset_id=asset.id, cisa_kev=False, cvss=8.0, sla_due_at=None, cve_id="CVE-TN-NOSLA")
    db_session.add_all([v_later, v_earlier, v_no_sla])
    await db_session.commit()

    result = await get_top_findings_for_ai_batch(db_session, tenant_a, limit=10)

    assert result == [v_earlier.id, v_later.id, v_no_sla.id]
