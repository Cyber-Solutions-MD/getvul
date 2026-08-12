"""Phase 34 Plan 02 (RISK-08) — flag-gated consumer cutover fixture suite.

Proves two things per consumer (`list_vulnerabilities(sort="triage")` and
`get_top_findings_for_ai_batch`): (1) with `Tenant.cutover_risk_exposure_scoring`
OFF (the default, and the only state this environment ever runs — 34-CONTEXT
locked), ordering is BYTE-IDENTICAL to pre-Phase-34 behavior; (2) with the flag
ON, ordering leads by the new per-finding `Vulnerability.risk_exposure_score`.
Every fixture seeds `risk_exposure_score` DELIBERATELY INVERTED relative to the
OFF-path ordering keys (KEV/CVSS/SLA for triage sort; `Asset.risk_score` for the
AI batch selector) so an OFF-vs-ON behavioral difference is unambiguous — if the
cutover branch were missing or wired backwards, the ON-path assertions fail for
real.

Also asserts the RESOLVED-A1 boundary: SLA breach detection
(`app/vulnerabilities/sla_service.py`) stays severity-keyed and must contain NO
reference to `risk_exposure_score` / `risk_score` — it is deliberately NOT a
cutover target this phase.
"""

from __future__ import annotations

import pathlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.assets.models import Asset
from app.pagination import PaginationParams
from app.tenants.models import Tenant
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.schemas import VulnerabilityFilter
from app.vulnerabilities.service import get_top_findings_for_ai_batch, list_vulnerabilities


def _seed_asset(tenant_id: uuid.UUID, *, risk_score: int | None = None) -> Asset:
    return Asset(tenant_id=tenant_id, hostname=f"host-{uuid.uuid4().hex[:8]}", risk_score=risk_score)


def _seed_vuln(
    tenant_id: uuid.UUID,
    asset_id: uuid.UUID | None,
    *,
    cve_id: str,
    severity: str = "HIGH",
    cvss_v3_score: Decimal | None = Decimal("7.5"),
    cisa_kev: bool = False,
    sla_due_at: datetime | None = None,
    risk_exposure_score: int | None = None,
    status: str = "OPEN",
    source: str = "QUALYS",
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        asset_id=asset_id,
        severity=severity,
        cvss_v3_score=cvss_v3_score,
        cisa_kev=cisa_kev,
        sla_due_at=sla_due_at,
        risk_exposure_score=risk_exposure_score,
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        status=status,
        first_detected_at=now,
        last_seen_at=now,
    )


async def _set_cutover_flag(db_session, tenant_id: uuid.UUID, *, enabled: bool) -> None:
    await db_session.execute(
        update(Tenant).where(Tenant.id == tenant_id).values(cutover_risk_exposure_scoring=enabled)
    )
    await db_session.commit()


# ── list_vulnerabilities(sort="triage") ──────────────────────────────────


@pytest.mark.asyncio
async def test_triage_sort_flag_off_is_identical(db_session, tenant_a):
    """Flag OFF (default): ordering is KEV desc -> CVSS desc -> SLA-due asc,
    exactly as today — byte-identical even though risk_exposure_score is
    seeded in the OPPOSITE order (proves the OFF path ignores the new score
    entirely)."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    now = datetime.now(UTC)
    vuln_a = _seed_vuln(
        tenant_a,
        asset.id,
        cve_id="CVE-2024-TRI-A",
        cisa_kev=True,
        cvss_v3_score=Decimal("9.0"),
        sla_due_at=now + timedelta(days=1),
        risk_exposure_score=10,  # lowest -- inverted vs. KEV/CVSS ranking
    )
    vuln_b = _seed_vuln(
        tenant_a,
        asset.id,
        cve_id="CVE-2024-TRI-B",
        cisa_kev=False,
        cvss_v3_score=Decimal("7.0"),
        sla_due_at=now + timedelta(days=2),
        risk_exposure_score=50,  # middle
    )
    vuln_c = _seed_vuln(
        tenant_a,
        asset.id,
        cve_id="CVE-2024-TRI-C",
        cisa_kev=False,
        cvss_v3_score=Decimal("5.0"),
        sla_due_at=now + timedelta(days=3),
        risk_exposure_score=90,  # highest -- would sort first if ON
    )
    db_session.add_all([vuln_a, vuln_b, vuln_c])
    await db_session.commit()

    result = await list_vulnerabilities(
        db_session, tenant_a, VulnerabilityFilter(sort="triage"), PaginationParams(page=1, page_size=50)
    )
    ids = [item.id for item in result.items if item.id in (vuln_a.id, vuln_b.id, vuln_c.id)]

    assert ids == [vuln_a.id, vuln_b.id, vuln_c.id]


@pytest.mark.asyncio
async def test_triage_sort_cutover_flag(db_session, tenant_a):
    """Flag ON: ordering leads by risk_exposure_score desc (primary key),
    reversing the OFF-path order for the same inverted fixture."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    now = datetime.now(UTC)
    vuln_a = _seed_vuln(
        tenant_a,
        asset.id,
        cve_id="CVE-2024-TRI2-A",
        cisa_kev=True,
        cvss_v3_score=Decimal("9.0"),
        sla_due_at=now + timedelta(days=1),
        risk_exposure_score=10,
    )
    vuln_b = _seed_vuln(
        tenant_a,
        asset.id,
        cve_id="CVE-2024-TRI2-B",
        cisa_kev=False,
        cvss_v3_score=Decimal("7.0"),
        sla_due_at=now + timedelta(days=2),
        risk_exposure_score=50,
    )
    vuln_c = _seed_vuln(
        tenant_a,
        asset.id,
        cve_id="CVE-2024-TRI2-C",
        cisa_kev=False,
        cvss_v3_score=Decimal("5.0"),
        sla_due_at=now + timedelta(days=3),
        risk_exposure_score=90,
    )
    db_session.add_all([vuln_a, vuln_b, vuln_c])
    await db_session.commit()

    await _set_cutover_flag(db_session, tenant_a, enabled=True)

    result = await list_vulnerabilities(
        db_session, tenant_a, VulnerabilityFilter(sort="triage"), PaginationParams(page=1, page_size=50)
    )
    ids = [item.id for item in result.items if item.id in (vuln_a.id, vuln_b.id, vuln_c.id)]

    # Leads by risk_exposure_score desc: C (90) -> B (50) -> A (10) --
    # the exact reverse of the OFF-path KEV/CVSS/SLA order above.
    assert ids == [vuln_c.id, vuln_b.id, vuln_a.id]


# ── get_top_findings_for_ai_batch ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_batch_selector_flag_off_is_identical(db_session, tenant_a):
    """Flag OFF (default): ranked by Asset.risk_score desc, nulls_last for
    an asset-less finding — exactly as today, even though each finding's own
    risk_exposure_score is seeded in the opposite order."""
    asset_lo = _seed_asset(tenant_a, risk_score=10)
    asset_hi = _seed_asset(tenant_a, risk_score=90)
    db_session.add_all([asset_lo, asset_hi])
    await db_session.flush()

    vuln_lo_asset = _seed_vuln(
        tenant_a, asset_lo.id, cve_id="CVE-2024-AI-LO", risk_exposure_score=90  # inverted vs. its own asset
    )
    vuln_hi_asset = _seed_vuln(
        tenant_a, asset_hi.id, cve_id="CVE-2024-AI-HI", risk_exposure_score=10  # inverted vs. its own asset
    )
    vuln_no_asset = _seed_vuln(tenant_a, None, cve_id="CVE-2024-AI-NULL", risk_exposure_score=None)
    db_session.add_all([vuln_lo_asset, vuln_hi_asset, vuln_no_asset])
    await db_session.commit()

    ids = await get_top_findings_for_ai_batch(db_session, tenant_a, limit=50)
    ids = [i for i in ids if i in (vuln_lo_asset.id, vuln_hi_asset.id, vuln_no_asset.id)]

    assert ids == [vuln_hi_asset.id, vuln_lo_asset.id, vuln_no_asset.id]


@pytest.mark.asyncio
async def test_ai_batch_selector_cutover_flag(db_session, tenant_a):
    """Flag ON: ranked by the per-finding Vulnerability.risk_exposure_score
    desc — reverses the OFF-path order; the asset-less finding (own score
    NULL) still sorts last via nulls_last."""
    asset_lo = _seed_asset(tenant_a, risk_score=10)
    asset_hi = _seed_asset(tenant_a, risk_score=90)
    db_session.add_all([asset_lo, asset_hi])
    await db_session.flush()

    vuln_lo_asset = _seed_vuln(tenant_a, asset_lo.id, cve_id="CVE-2024-AI2-LO", risk_exposure_score=90)
    vuln_hi_asset = _seed_vuln(tenant_a, asset_hi.id, cve_id="CVE-2024-AI2-HI", risk_exposure_score=10)
    vuln_no_asset = _seed_vuln(tenant_a, None, cve_id="CVE-2024-AI2-NULL", risk_exposure_score=None)
    db_session.add_all([vuln_lo_asset, vuln_hi_asset, vuln_no_asset])
    await db_session.commit()

    await _set_cutover_flag(db_session, tenant_a, enabled=True)

    ids = await get_top_findings_for_ai_batch(db_session, tenant_a, limit=50)
    ids = [i for i in ids if i in (vuln_lo_asset.id, vuln_hi_asset.id, vuln_no_asset.id)]

    assert ids == [vuln_lo_asset.id, vuln_hi_asset.id, vuln_no_asset.id]


# ── SLA boundary guard (RESOLVED A1) ─────────────────────────────────────


def test_sla_breach_stays_severity_keyed():
    """RESOLVED A1: SLA breach detection is NOT a cutover target this phase
    -- sla_service.py's due-date math must contain no reference to the new
    per-finding risk_exposure_score or the old Asset.risk_score."""
    sla_service_path = pathlib.Path(__file__).resolve().parent.parent / "app" / "vulnerabilities" / "sla_service.py"
    source = sla_service_path.read_text()

    assert "risk_exposure_score" not in source
    assert "risk_score" not in source
