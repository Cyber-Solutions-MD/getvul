"""Phase 33 Plan 01 (LEAD TRACER) — determinism + KEV-floor fixture +
persistence + response-shape tests for `app/vulnerabilities/risk_exposure_service.py`
(RISK-01/RISK-02/RISK-03/RISK-06).

No prior test file for risk_exposure_service existed (confirmed via grep across
backend/tests/). This tracer suite proves the pure `score_finding` determinism
+ KEV-floor mechanics as DB-free fixtures (RESEARCH.md "KEV Floor Mechanics",
verbatim shape), plus the DB-orchestration `compute_finding_risk_scores`
persistence and the persisted-column read on GET /vulnerabilities/{id} — the
full per-finding scoring pipeline this plan lands end-to-end at minimum blast
radius (severity/CVSS + EPSS + KEV floor are REAL; native_exploitability /
exposure_* / corroboration are zeroed placeholders — Plan 33-02's expansion
surface, never renormalized per RESEARCH Pitfall 5).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability


def _seed_asset(tenant_id: uuid.UUID) -> Asset:
    # Mirrors test_correlation_service.py's _seed_asset helper shape.
    return Asset(tenant_id=tenant_id, hostname=f"host-{uuid.uuid4().hex[:8]}")


def _seed_vuln(
    tenant_id: uuid.UUID,
    asset_id: uuid.UUID,
    *,
    cve_id: str,
    severity: str = "HIGH",
    cvss_v3_score: Decimal | None = Decimal("7.5"),
    epss_score: Decimal | None = None,
    cisa_kev: bool = False,
    source: str = "QUALYS",
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        asset_id=asset_id,
        severity=severity,
        cvss_v3_score=cvss_v3_score,
        epss_score=epss_score,
        cisa_kev=cisa_kev,
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )


def test_score_finding_deterministic():
    """RISK-01: calling score_finding twice on identical inputs returns an
    identical final_score AND an identical components list."""
    from app.vulnerabilities.risk_exposure_service import FindingScoreInputs, score_finding

    inputs = FindingScoreInputs(
        severity="HIGH",
        cvss_v3_score=Decimal("7.5"),
        epss_score=Decimal("0.3"),
        cisa_kev=False,
        source="QUALYS",
        native_priority_score=None,
        native_priority_rating=None,
        sources_count=1,
        business_criticality="MEDIUM",
        data_sensitivity="INTERNAL",
        internet_facing=False,
    )

    first = score_finding(inputs)
    second = score_finding(inputs)

    assert first.final_score == second.final_score
    assert first.components == second.components


def test_kev_floor_fixture():
    """RISK-03: a LOW-severity KEV finding scores EXACTLY the floor (90) and
    materially higher than the identical finding with cisa_kev=False.

    Verbatim per 33-RESEARCH.md "KEV Floor Mechanics" — baseline is
    genuinely zero-contribution on every non-severity input (LOW criticality,
    PUBLIC sensitivity, not internet-facing, no EPSS/native/corroboration) so
    only severity/CVSS contributes.
    """
    from app.vulnerabilities.risk_exposure_service import FindingScoreInputs, score_finding

    low_no_kev = FindingScoreInputs(
        severity="LOW",
        cvss_v3_score=Decimal("3.1"),
        epss_score=None,
        cisa_kev=False,
        source="DEFENDER",
        native_priority_score=None,
        native_priority_rating=None,
        sources_count=1,
        business_criticality="LOW",
        data_sensitivity="PUBLIC",
        internet_facing=False,
    )
    low_with_kev = replace(low_no_kev, cisa_kev=True)

    no_kev_result = score_finding(low_no_kev)
    with_kev_result = score_finding(low_with_kev)

    assert no_kev_result.final_score < 20
    assert with_kev_result.final_score == 90
    assert with_kev_result.kev_floor_applied is True
    assert with_kev_result.final_score > no_kev_result.final_score + 60


def test_score_finding_epss_and_severity():
    """EPSS component is REAL in the tracer: a HIGH finding with
    epss_score set scores strictly higher than the identical finding with
    epss_score=None."""
    from app.vulnerabilities.risk_exposure_service import FindingScoreInputs, score_finding

    base = FindingScoreInputs(
        severity="HIGH",
        cvss_v3_score=Decimal("8.0"),
        epss_score=None,
        cisa_kev=False,
        source="QUALYS",
        native_priority_score=None,
        native_priority_rating=None,
        sources_count=1,
        business_criticality="MEDIUM",
        data_sensitivity="INTERNAL",
        internet_facing=False,
    )
    with_epss = replace(base, epss_score=Decimal("0.5"))

    assert score_finding(with_epss).final_score > score_finding(base).final_score


@pytest.mark.asyncio
async def test_compute_finding_risk_scores_persists(db_session, tenant_a):
    """RISK-02/06: compute_finding_risk_scores persists risk_exposure_score +
    risk_exposure_breakdown (JSONB) + risk_model_version on every OPEN
    Vulnerability row for the tenant; the KEV row's score >= 90 (floor)."""
    from app.vulnerabilities.risk_exposure_service import RISK_MODEL_VERSION, compute_finding_risk_scores

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    kev_vuln = _seed_vuln(
        tenant_a,
        asset.id,
        cve_id="CVE-2024-KEV001",
        severity="LOW",
        cvss_v3_score=None,
        cisa_kev=True,
    )
    plain_vuln = _seed_vuln(
        tenant_a,
        asset.id,
        cve_id="CVE-2024-PLAIN001",
        severity="MEDIUM",
        cisa_kev=False,
    )
    db_session.add_all([kev_vuln, plain_vuln])
    await db_session.commit()

    stats = await compute_finding_risk_scores(db_session, tenant_a)
    await db_session.commit()

    assert stats["findings_updated"] >= 2

    rows = (
        (
            await db_session.execute(
                select(Vulnerability).where(
                    Vulnerability.tenant_id == tenant_a,
                    Vulnerability.id.in_([kev_vuln.id, plain_vuln.id]),
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {row.id: row for row in rows}
    assert len(rows) == 2

    for row in rows:
        assert row.risk_exposure_score is not None
        assert isinstance(row.risk_exposure_breakdown, list)
        assert len(row.risk_exposure_breakdown) > 0
        assert row.risk_model_version == RISK_MODEL_VERSION == "v1"

    assert by_id[kev_vuln.id].risk_exposure_score >= 90


@pytest.mark.asyncio
async def test_get_vulnerability_returns_risk_fields(client, db_session, tenant_a, analyst_user):
    """RISK-05 precursor: GET /vulnerabilities/{id} returns
    risk_exposure_score/risk_exposure_breakdown/risk_model_version read
    directly from the persisted row (no live recompute)."""
    from app.vulnerabilities.risk_exposure_service import compute_finding_risk_scores

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_a, asset.id, cve_id="CVE-2024-GETVUL001", severity="HIGH", cisa_kev=False)
    db_session.add(vuln)
    await db_session.commit()

    await compute_finding_risk_scores(db_session, tenant_a)
    await db_session.commit()

    resp = await client.get(f"/api/v1/vulnerabilities/{vuln.id}")
    assert resp.status_code == 200
    body = resp.json()

    assert body["risk_exposure_score"] is not None
    assert isinstance(body["risk_exposure_breakdown"], list)
    assert len(body["risk_exposure_breakdown"]) > 0
    for component in body["risk_exposure_breakdown"]:
        assert {"key", "label", "raw_value", "points", "max_points"}.issubset(component)
    assert body["risk_model_version"] == "v1"
