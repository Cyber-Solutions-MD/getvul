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

import uuid
from datetime import UTC, datetime

import pytest

from app.assets.models import Asset
from app.vulnerabilities.correlation_service import get_correlation_for_vuln, run_correlations
from app.vulnerabilities.models import Vulnerability


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
