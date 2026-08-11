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
from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation


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


# --- Plan 33-02: full-formula expansion tests -------------------------------
# (native per-source normalization, exposure sub-split, corroboration,
# KEV floor under the full formula, correlation bulk-join). These MUST fail
# for real against the Plan 33-01 tracer: _normalize_native_signal does not
# exist yet, and the native/exposure/corroboration components are still
# zeroed placeholders, and compute_finding_risk_scores hardcodes
# sources_count=1 (RED).


def test_normalize_native_signal_per_source():
    """CONTEXT native-normalization lock: each source's native_priority_score
    maps to 0-1 on its OWN scale; CrowdStrike uses the categorical rating,
    never its unverified numeric; DEFENDER/WIZ/missing/garbage soft-null to
    0.0 and this function NEVER raises."""
    from app.vulnerabilities.risk_exposure_service import _normalize_native_signal

    assert _normalize_native_signal("NESSUS", Decimal("5"), None) == pytest.approx(0.5)
    assert _normalize_native_signal("QUALYS", Decimal("50"), None) == pytest.approx(0.5)
    assert _normalize_native_signal("RAPID7", Decimal("500"), None) == pytest.approx(0.5)
    assert _normalize_native_signal("CROWDSTRIKE", None, "HIGH") == pytest.approx(0.75)
    assert _normalize_native_signal("CROWDSTRIKE", None, "UNKNOWN") == 0.0
    assert _normalize_native_signal("DEFENDER", None, None) == 0.0
    assert _normalize_native_signal("WIZ", None, None) == 0.0
    assert _normalize_native_signal("NESSUS", None, None) == 0.0
    # garbage/over-scale clamps to 1.0, never raises
    assert _normalize_native_signal("NESSUS", Decimal("999"), None) == 1.0
    assert _normalize_native_signal("QUALYS", Decimal("-50"), None) == 0.0


def test_score_finding_all_components():
    """RISK-01: a finding exercising all 6 categories scores near the top of
    the range, is deterministic across two calls, and every returned
    component's points never exceed its own max_points."""
    from app.vulnerabilities.risk_exposure_service import FindingScoreInputs, score_finding

    inputs = FindingScoreInputs(
        severity="CRITICAL",
        cvss_v3_score=Decimal("9.8"),
        epss_score=Decimal("0.9"),
        cisa_kev=False,
        source="NESSUS",
        native_priority_score=Decimal("8"),
        native_priority_rating=None,
        sources_count=4,
        business_criticality="CRITICAL",
        data_sensitivity="RESTRICTED",
        internet_facing=True,
    )

    first = score_finding(inputs)
    second = score_finding(inputs)

    assert first.final_score == second.final_score
    assert first.components == second.components
    assert first.final_score > 85
    assert len(first.components) >= 6
    for component in first.components:
        assert component.points <= component.max_points


def test_corroboration_fixture():
    """RISK-04, RESEARCH verbatim base fixture: an identical HIGH finding at
    sources_count=3 scores measurably higher than at sources_count=1, driven
    by the corroboration component's exact ~6.7pt contribution.

    NOTE: final_score is a rounded int (RiskBreakdown.final_score: int); with
    this exact base fixture the two independently-rounded subtotals (41.87 ->
    42 vs 48.54 -> 49) land 7 apart, not 6.7 -- an expected int-rounding
    boundary artifact, not a formula bug. Asserting on the underlying
    "corroboration" breakdown component (computed pre-rounding) is the
    precise, deterministic RISK-04 proof; the final_score assertion below
    proves the direction/magnitude at the reported-score level."""
    from app.vulnerabilities.risk_exposure_service import FindingScoreInputs, score_finding

    base = FindingScoreInputs(
        severity="HIGH",
        cvss_v3_score=Decimal("7.5"),
        epss_score=Decimal("0.1"),
        cisa_kev=False,
        source="QUALYS",
        native_priority_score=Decimal("60"),
        native_priority_rating=None,
        sources_count=1,
        business_criticality="MEDIUM",
        data_sensitivity="INTERNAL",
        internet_facing=False,
    )
    three_sources = replace(base, sources_count=3)

    one_result = score_finding(base)
    three_result = score_finding(three_sources)

    assert three_result.final_score > one_result.final_score
    assert three_result.final_score - one_result.final_score >= 6

    one_corrob = next(c for c in one_result.components if c.key == "corroboration")
    three_corrob = next(c for c in three_result.components if c.key == "corroboration")
    assert three_corrob.points - one_corrob.points == pytest.approx(6.7, abs=0.1)


def test_kev_floor_survives_full_formula():
    """RISK-03, RESEARCH verbatim (primary proof): a genuinely
    zero-contribution LOW/PUBLIC baseline scores materially higher (>90
    points higher, landing at the exact floor 90) once cisa_kev=True — the
    KEV floor still escalates under the FULL formula, not just the tracer's
    two real components. The KEV variant's breakdown includes an explicit
    kev_floor component row."""
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
    assert with_kev_result.final_score > no_kev_result.final_score + 60
    assert any(c.key == "kev_floor" for c in with_kev_result.components)


@pytest.mark.asyncio
async def test_compute_uses_correlation_sources_count(db_session, tenant_a):
    """RISK-04: compute_finding_risk_scores bulk-fetches
    VulnerabilityCorrelation.sources_count (no N+1) and feeds it into
    score_finding; a finding with no correlation row scores as
    sources_count=1 -- the 3-source finding scores higher than the
    single-source finding, all else equal."""
    from app.vulnerabilities.risk_exposure_service import compute_finding_risk_scores

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    cve_id = "CVE-2024-CORR001"
    corroborated_vuln = _seed_vuln(
        tenant_a, asset.id, cve_id=cve_id, severity="HIGH", cvss_v3_score=Decimal("7.5"), source="QUALYS"
    )
    db_session.add(corroborated_vuln)
    db_session.add(
        VulnerabilityCorrelation(
            tenant_id=tenant_a,
            cve_id=cve_id,
            asset_id=asset.id,
            sources=["QUALYS", "RAPID7", "NESSUS"],
            sources_count=3,
            confidence="HIGH",
        )
    )

    single_vuln = _seed_vuln(
        tenant_a,
        asset.id,
        cve_id="CVE-2024-SINGLE001",
        severity="HIGH",
        cvss_v3_score=Decimal("7.5"),
        source="QUALYS",
    )
    db_session.add(single_vuln)
    await db_session.commit()

    await compute_finding_risk_scores(db_session, tenant_a)
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Vulnerability).where(
                    Vulnerability.tenant_id == tenant_a,
                    Vulnerability.id.in_([corroborated_vuln.id, single_vuln.id]),
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {row.id: row for row in rows}

    assert by_id[corroborated_vuln.id].risk_exposure_score > by_id[single_vuln.id].risk_exposure_score
