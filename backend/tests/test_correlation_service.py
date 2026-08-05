"""Phase 30 Plan 01 — SC#4 regression coverage for correlation_service.py
(CORR-01/CORR-03).

Behaviour under test (D-10): a finding seen only by QUALYS + RAPID7 must now
correlate. Pre-fix, `correlation_service.py`'s SOURCE_COLUMN_MAP only tracked
CROWDSTRIKE/NESSUS/DEFENDER/WIZ, so a Qualys+Rapid7-only pair silently built
an upsert with all 4 legacy FK columns NULL — structurally indistinguishable
from a genuinely-uncorrelated row, even though sources_count/confidence were
already correct.

This test is RED until Task 3 lands the `sources` ARRAY(String) + GIN column,
the `source_vuln_ids` JSONB column, and the correlation_service.py rewrite
over the full VulnSource enum. No prior test file for correlation_service.py
existed (confirmed via grep across backend/tests/).
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text

from app.assets.models import Asset
from app.vulnerabilities.correlation_service import get_correlation_for_vuln, run_correlations
from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation, VulnSource

# scripts/ is not a package under app/ -- add the repo's backend/ root (this
# file's grandparent) to sys.path so `from scripts.recorrelate_all_tenants
# import _recorrelate_tenant` resolves, mirroring how `backend/scripts/` sits
# as a sibling of `backend/app/` and `backend/tests/`.
_BACKEND_ROOT = str(Path(__file__).resolve().parent.parent)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from scripts.recorrelate_all_tenants import _recorrelate_tenant  # noqa: E402


async def _seed_asset(db_session, tenant_id: uuid.UUID) -> uuid.UUID:
    # Mirrors the _seed_asset helper shape in test_ai_grounding_prioritization.py
    asset = Asset(tenant_id=tenant_id, hostname=f"host-{uuid.uuid4().hex[:8]}")
    db_session.add(asset)
    await db_session.commit()  # visible to run_correlations' own session read
    return asset.id


def _seed_vuln(tenant_id: uuid.UUID, asset_id: uuid.UUID, source: str, cve_id: str) -> Vulnerability:
    # Mirrors test_vuln_source_filter.py's _seed, with asset_id added --
    # required because _find_correlated_groups filters Vulnerability.asset_id.isnot(None).
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        asset_id=asset_id,
        severity="HIGH",
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_qualys_rapid7_only_correlation_no_longer_silently_dropped(db_session, tenant_a):
    """D-10: this exact case (2 sources, neither CROWDSTRIKE/NESSUS/DEFENDER/WIZ)
    was silently dropped pre-fix -- the old SOURCE_COLUMN_MAP had no column for
    either source, so run_correlations() built an upsert with all 4 FK columns
    NULL, structurally indistinguishable from a genuinely-uncorrelated row.
    """
    asset_id = await _seed_asset(db_session, tenant_a)
    cve_id = "CVE-2024-QR001"
    qualys_vuln = _seed_vuln(tenant_a, asset_id, "QUALYS", cve_id)
    rapid7_vuln = _seed_vuln(tenant_a, asset_id, "RAPID7", cve_id)
    db_session.add_all([qualys_vuln, rapid7_vuln])
    await db_session.commit()

    await run_correlations(db_session, tenant_a)
    await db_session.commit()

    corr = await get_correlation_for_vuln(db_session, tenant_a, cve_id, asset_id)
    assert corr is not None, "Qualys+Rapid7 pair must now correlate"
    assert corr["sources"] == ["QUALYS", "RAPID7"], "canonical enum-declaration order"
    assert corr["sources_count"] == 2
    assert corr["confidence"] == "MEDIUM"  # D-08: 2-3 sources -> MEDIUM
    assert corr["source_vuln_ids"]["QUALYS"] == str(qualys_vuln.id)
    assert corr["source_vuln_ids"]["RAPID7"] == str(rapid7_vuln.id)


async def _consistency_count(db_session, tenant_id: uuid.UUID) -> int:
    """Per-tenant COALESCE zero-loss check (RESEARCH Pitfall 3: array_length()
    of an empty array is NULL, not 0, so this must be COALESCE-wrapped or a
    sources='{}' row is silently skipped)."""
    return (
        await db_session.execute(
            text(
                "SELECT count(*) FROM vulnerability_correlations "
                "WHERE tenant_id = :tid AND "
                "COALESCE(array_length(sources,1), 0) != sources_count"
            ),
            {"tid": str(tenant_id)},
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_recorrelate_tenant_corrects_backfill_bug_signature(db_session, tenant_a):
    """Task 2 (CORR-02 runtime zero-loss proof): reproduces the exact
    post-backfill bug signature -- a correlation row that survived the
    034_add_correlation_sources migration's baseline backfill with
    `sources=[]` while `sources_count` still holds its pre-migration value
    (RESEARCH Pitfall 5) -- and proves `_recorrelate_tenant` corrects it
    (not deletes it) and that the COALESCE consistency query returns 0
    afterwards, per-tenant.
    """
    asset_id = await _seed_asset(db_session, tenant_a)
    cve_id = "CVE-2024-BACKFILL001"
    qualys_vuln = _seed_vuln(tenant_a, asset_id, "QUALYS", cve_id)
    rapid7_vuln = _seed_vuln(tenant_a, asset_id, "RAPID7", cve_id)
    db_session.add_all([qualys_vuln, rapid7_vuln])

    # Directly insert the exact post-backfill bug signature: the row exists
    # (sources_count already correct from the old pre-migration value) but
    # `sources` is empty -- the migration's baseline backfill had no legacy
    # FK column to read a Qualys/Rapid7 linkage FROM.
    db_session.add(
        VulnerabilityCorrelation(
            tenant_id=tenant_a,
            cve_id=cve_id,
            asset_id=asset_id,
            sources=[],
            sources_count=2,
            confidence="MEDIUM",
        )
    )
    await db_session.commit()

    # Pre-state: the bug is genuinely present before recovery.
    assert await _consistency_count(db_session, tenant_a) >= 1, "corrupted row must be detected pre-recovery"

    stats = await _recorrelate_tenant(db_session, tenant_a)
    await db_session.commit()

    corr = await get_correlation_for_vuln(db_session, tenant_a, cve_id, asset_id)
    assert corr is not None, "row must be corrected, not pruned away"
    assert corr["sources"] == ["QUALYS", "RAPID7"]
    assert corr["sources_count"] == 2

    assert stats["inconsistent_rows_after"] == 0
    assert await _consistency_count(db_session, tenant_a) == 0


@pytest.mark.asyncio
async def test_single_source_does_not_correlate(db_session, tenant_a):
    """CORR-03 edge: a lone-source finding never produces a correlation row
    -- correlation only exists at 2+ sources."""
    asset_id = await _seed_asset(db_session, tenant_a)
    cve_id = "CVE-2024-SINGLE001"
    db_session.add(_seed_vuln(tenant_a, asset_id, "QUALYS", cve_id))
    await db_session.commit()

    await run_correlations(db_session, tenant_a)
    await db_session.commit()

    corr = await get_correlation_for_vuln(db_session, tenant_a, cve_id, asset_id)
    assert corr is None


_SOURCE_ORDER: list[str] = [s.value for s in VulnSource]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_count", "expected_confidence"),
    [
        (2, "MEDIUM"),
        (3, "MEDIUM"),
        (4, "HIGH"),
        (5, "HIGH"),
        (6, "HIGH"),
    ],
)
async def test_confidence_bands(db_session, tenant_a, source_count, expected_confidence):
    """D-08 recalibrated bands: HIGH >=4, MEDIUM 2-3, proven across every
    seeded source-count combination 2..6. Also locks CORR-03 (sources_count
    always equals len(sources)) and D-02 canonical enum-declaration order."""
    asset_id = await _seed_asset(db_session, tenant_a)
    cve_id = f"CVE-2024-BAND{source_count}"
    sources_to_seed = _SOURCE_ORDER[:source_count]
    for source in sources_to_seed:
        db_session.add(_seed_vuln(tenant_a, asset_id, source, cve_id))
    await db_session.commit()

    await run_correlations(db_session, tenant_a)
    await db_session.commit()

    corr = await get_correlation_for_vuln(db_session, tenant_a, cve_id, asset_id)
    assert corr is not None
    assert len(corr["sources"]) == corr["sources_count"] == source_count
    assert corr["sources"] == sources_to_seed, "canonical enum-declaration order"
    assert corr["confidence"] == expected_confidence


@pytest.mark.asyncio
async def test_correlation_tenant_scoped(db_session, tenant_a, tenant_b):
    """Cross-tenant isolation: a correlation created for tenant_a is never
    returned for tenant_b, mirroring test_vuln_source_filter.py's
    test_source_filter_tenant_scoped shape."""
    asset_id = await _seed_asset(db_session, tenant_a)
    cve_id = "CVE-2024-TSCOPE001"
    db_session.add_all(
        [
            _seed_vuln(tenant_a, asset_id, "QUALYS", cve_id),
            _seed_vuln(tenant_a, asset_id, "RAPID7", cve_id),
        ]
    )
    await db_session.commit()

    await run_correlations(db_session, tenant_a)
    await db_session.commit()

    corr_a = await get_correlation_for_vuln(db_session, tenant_a, cve_id, asset_id)
    assert corr_a is not None

    corr_b = await get_correlation_for_vuln(db_session, tenant_b, cve_id, asset_id)
    assert corr_b is None, "a tenant_a correlation must never be visible under tenant_b"


@pytest.mark.asyncio
async def test_correlation_route_returns_d09_shape(client, db_session, tenant_a, analyst_user):
    """D-09: GET /{vuln_id}/correlation returns the promoted sources/
    sources_count/source_vuln_ids shape and NONE of the 4 legacy *_vuln_id
    keys, under require_viewer auth (the `client` fixture is authed as the
    analyst -- ANALYST satisfies require_viewer's floor)."""
    asset_id = await _seed_asset(db_session, tenant_a)
    cve_id = "CVE-2024-D09SHAPE001"
    qualys_vuln = _seed_vuln(tenant_a, asset_id, "QUALYS", cve_id)
    rapid7_vuln = _seed_vuln(tenant_a, asset_id, "RAPID7", cve_id)
    db_session.add_all([qualys_vuln, rapid7_vuln])
    await db_session.commit()

    await run_correlations(db_session, tenant_a)
    await db_session.commit()

    resp = await client.get(f"/api/v1/vulnerabilities/{qualys_vuln.id}/correlation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["correlated"] is True
    assert {"sources", "sources_count", "source_vuln_ids"}.issubset(body)
    legacy_keys = {"crowdstrike_vuln_id", "nessus_vuln_id", "defender_vuln_id", "wiz_vuln_id"}
    assert not (legacy_keys & body.keys()), f"legacy keys leaked into response: {legacy_keys & body.keys()}"
