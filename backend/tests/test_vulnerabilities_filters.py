"""Phase 44 Plan 02 / NLQ-01 / D-03 — the two additive vulnerability
predicates (asset_internet_facing, sla_breached) the north-star NLQ
question and starter questions need, plus their AssetFilter/TicketQueryFilter
siblings.

Behaviour under test:
- `VulnerabilityFilter.asset_internet_facing` filters via a subquery against
  `Asset.internet_facing` (Pitfall 1: deliberately NOT a `.join()` inside
  `_apply_filters`, to avoid double-joining Asset on `list_vulnerabilities`'s
  existing data-path `.outerjoin(Asset, ...)`) -- proven correct on BOTH the
  count query and the data query with no InvalidRequestError.
- `VulnerabilityFilter.sla_breached` filters on the STORED
  `Vulnerability.sla_breached` derived-mirror column (Pitfall 6), never a
  live `resolve_state_for_vuln` recompute.
- `AssetFilter.internet_facing` filters on the native `Asset.internet_facing`
  column directly (no join needed).
- `TicketQueryFilter` (ticketing/schemas.py) is a NEW, `extra="forbid"`
  NLQ-only translation wrapper -- an unknown field is rejected.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.assets.models import Asset
from app.assets.schemas import AssetFilter
from app.assets.service import list_assets
from app.pagination import PaginationParams
from app.ticketing.schemas import TicketQueryFilter
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.schemas import VulnerabilityFilter
from app.vulnerabilities.service import list_vulnerabilities


def _seed_asset(tenant_id: uuid.UUID, hostname: str, *, internet_facing: bool = False) -> Asset:
    return Asset(tenant_id=tenant_id, hostname=hostname, internet_facing=internet_facing)


def _seed_vuln(
    tenant_id: uuid.UUID,
    *,
    cve_id: str,
    asset_id: uuid.UUID | None = None,
    sla_breached: bool = False,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity="HIGH",
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        asset_id=asset_id,
        sla_breached=sla_breached,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_filter_asset_internet_facing(db_session, tenant_a) -> None:
    """Pitfall 1: asset_internet_facing must filter correctly on BOTH the
    count query (no existing Asset join) and the data query (which ALREADY
    outerjoins Asset for asset_hostname) with no double-join error."""
    facing_asset = _seed_asset(tenant_a, "web-prod-01", internet_facing=True)
    internal_asset = _seed_asset(tenant_a, "internal-db-01", internet_facing=False)
    db_session.add_all([facing_asset, internal_asset])
    await db_session.flush()

    facing_vuln = _seed_vuln(tenant_a, cve_id="CVE-IF-1", asset_id=facing_asset.id)
    internal_vuln = _seed_vuln(tenant_a, cve_id="CVE-IF-2", asset_id=internal_asset.id)
    db_session.add_all([facing_vuln, internal_vuln])
    await db_session.commit()

    result = await list_vulnerabilities(
        db_session,
        tenant_a,
        VulnerabilityFilter(asset_internet_facing=True),
        PaginationParams(page=1, page_size=10),
    )

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].cve_id == "CVE-IF-1"


@pytest.mark.asyncio
async def test_filter_sla_breached(db_session, tenant_a) -> None:
    """sla_breached filters on the STORED Vulnerability.sla_breached column
    (Pitfall 6) -- not a live resolve_state_for_vuln recompute."""
    breached = _seed_vuln(tenant_a, cve_id="CVE-SLA-1", sla_breached=True)
    not_breached = _seed_vuln(tenant_a, cve_id="CVE-SLA-2", sla_breached=False)
    db_session.add_all([breached, not_breached])
    await db_session.commit()

    result = await list_vulnerabilities(
        db_session,
        tenant_a,
        VulnerabilityFilter(sla_breached=True),
        PaginationParams(page=1, page_size=10),
    )

    assert result.total == 1
    assert result.items[0].cve_id == "CVE-SLA-1"


@pytest.mark.asyncio
async def test_asset_internet_facing_filter(db_session, tenant_a) -> None:
    """AssetFilter.internet_facing is a native-column filter, no join."""
    facing_asset = _seed_asset(tenant_a, "web-prod-02", internet_facing=True)
    internal_asset = _seed_asset(tenant_a, "internal-db-02", internet_facing=False)
    db_session.add_all([facing_asset, internal_asset])
    await db_session.commit()

    result = await list_assets(
        db_session,
        tenant_a,
        AssetFilter(internet_facing=True),
        PaginationParams(page=1, page_size=10),
    )

    assert result.total == 1
    assert result.items[0].hostname == "web-prod-02"


def test_ticket_query_filter_forbids_extra() -> None:
    """TicketQueryFilter is extra='forbid' -- an unknown field is rejected,
    same discipline as every other NLQ-facing schema."""
    TicketQueryFilter(status="open", asset_hostname="prod-db-01")  # valid shape sanity check

    with pytest.raises(ValidationError):
        TicketQueryFilter(status="open", asset_id="not-allowed-here")
