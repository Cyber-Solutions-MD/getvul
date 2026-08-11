"""Phase 33 Plan 03 -- characterization regression for the severity-tier
boundary triplication (RISK-06).

Guards the tier-centralization refactor: must pass BEFORE (baseline, against
the current triplicated-literal code) AND AFTER (against the RISK_SCORE_TIER_*
constants substituted in Task 3) -- byte-identical bucket counts prove zero
behavior change.

The 3 sites under test (confirmed byte-for-byte identical boolean structure
via direct read, 33-PATTERNS.md):
  - backend/app/vulnerabilities/dashboard.py:125-128 (get_overview_stats)
  - backend/app/export.py:368-371 (_collect_summary_data)
  - backend/app/assets/router.py:297-300 (asset_stats, GET /api/v1/assets/stats)

Note: dashboard.py and export.py's low-bucket includes `| Asset.risk_score
.is_(None)`; assets/router.py's low-bucket does NOT (`< 20` only, no
is_(None) clause) -- this is a genuine, pre-existing discrepancy between the
3 sites, not something this plan's pure refactor may fix (task scope is
literal->constant substitution ONLY, zero behavior change). The seed below
therefore asserts DIFFERENT expected low-bucket counts for assets/router.py
vs. the other two, verbatim as today's behavior.
"""

from __future__ import annotations

import uuid

import pytest

from app.assets.models import Asset


def _seed_asset_with_score(tenant_id: uuid.UUID, score: int | None) -> Asset:
    return Asset(tenant_id=tenant_id, hostname=f"host-{uuid.uuid4().hex[:8]}", risk_score=score)


@pytest.mark.asyncio
async def test_risk_distribution_buckets_unchanged(client, db_session, tenant_a):
    """Boundary-value seed {85, 80, 79, 50, 49, 20, 19, None} across all 3
    identical bucket sites -- golden bucket counts captured here must remain
    byte-identical after Task 3's tier-centralization refactor."""
    from app.export import _collect_summary_data
    from app.vulnerabilities.dashboard import get_overview_stats

    scores = [85, 80, 79, 50, 49, 20, 19, None]
    for score in scores:
        db_session.add(_seed_asset_with_score(tenant_a, score))
    await db_session.commit()

    # -- dashboard.py:125-128 (get_overview_stats) --
    dashboard_stats = await get_overview_stats(db_session, tenant_a)
    dashboard_dist = dashboard_stats["risk_distribution"]
    assert dashboard_dist == {"critical": 2, "high": 2, "medium": 2, "low": 2}

    # -- export.py:368-371 (_collect_summary_data) --
    export_data = await _collect_summary_data(db_session, tenant_a)
    export_dist = export_data["assets"]["risk"]
    assert export_dist == {"critical": 2, "high": 2, "medium": 2, "low": 2}

    # -- assets/router.py:297-300 (GET /api/v1/assets/stats) --
    resp = await client.get("/api/v1/assets/stats")
    assert resp.status_code == 200, resp.text
    router_dist = resp.json()["risk_distribution"]
    # No is_(None) clause in this site's low bucket -- the None-scored asset
    # is counted in NEITHER bucket, unlike dashboard/export above. Verbatim
    # pre-existing behavior, not touched by the centralization refactor.
    assert router_dist == {"critical": 2, "high": 2, "medium": 2, "low": 1}
