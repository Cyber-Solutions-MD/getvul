"""Coverage business logic (Phase 41 Plan 01 -- COV-01 tracer slice): the
blind-spot reconciliation query -- authoritative (MDM/HR) inventory minus
anything a scanner has ever touched (D-01/D-02). Compute-on-read (D-10):
no new table, column, or migration -- every call recomputes from
`Asset.seen_by_sources` directly.

Reuses `app/assets/router.py`'s existing `.contains()` facet-filter idiom
(imports `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` from `app.assets.constants`,
never re-derives the 9 literal strings) composed into the two boolean
predicates this reconciliation needs:

  authoritative  = OR across ENRICHMENT_SOURCES   (D-01)
  never_scanned  = NOT (OR across SCANNER_SOURCES) (D-02)

`total_authoritative_assets`/`has_authoritative_inventory` answer a
DIFFERENT question than the list itself -- how many authoritative assets
exist at all, independent of scanner coverage -- so the frontend can tell
"no inventory source connected" (D-11) apart from "fully covered, zero
blind spots" (and render the real device count in that quiet-win copy).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.constants import ENRICHMENT_SOURCES, SCANNER_SOURCES
from app.assets.models import Asset
from app.coverage.schemas import BlindSpotAssetListResponse, BlindSpotAssetResponse

DEFAULT_PAGE_SIZE = 50


def _authoritative_clause() -> ColumnElement[bool]:
    """D-01: authoritative inventory = seen by >=1 ENRICHMENT source."""
    return or_(*[Asset.seen_by_sources.contains([e]) for e in ENRICHMENT_SOURCES])


def _never_scanned_clause() -> ColumnElement[bool]:
    """D-02: never scanned = seen by 0 SCANNER_SOURCES."""
    return not_(or_(*[Asset.seen_by_sources.contains([s]) for s in SCANNER_SOURCES]))


async def _count_authoritative_assets(
    db: AsyncSession, tenant_id: uuid.UUID, authoritative: ColumnElement[bool]
) -> int:
    """D-11: how many authoritative (MDM/HR) assets exist at all --
    independent of scanner coverage -- so the frontend can distinguish "no
    inventory source connected" from "fully covered" AND render the real
    device count in the quiet-win empty copy. A plain COUNT over the exact
    same `authoritative` clause already used above -- not a second
    join/query shape, just `.limit(1)` widened to a full count. Mirrors the
    blind-spot list's own is_ignored exclusion so "inventory exists" never
    points at an asset that is invisible everywhere else in the app."""
    count_q = select(func.count()).select_from(
        select(Asset.id).where(Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False), authoritative).subquery()
    )
    return (await db.execute(count_q)).scalar() or 0


async def list_blind_spot_assets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> BlindSpotAssetListResponse:
    """T-41-01: every WHERE clause below carries `Asset.tenant_id ==
    tenant_id` -- the list query, the count query, AND the
    has_authoritative_inventory existence check all independently
    tenant-scope; never fetch-then-filter.

    Ignored assets (`is_ignored=True`) are excluded from the list, mirroring
    `list_assets`'s default (assets/router.py). Ordering is
    `hostname ASC, id ASC` -- deterministic and stable across pagination
    requests (no ORDER BY on an unindexed/nullable-heavy column alone).
    """
    authoritative = _authoritative_clause()
    never_scanned = _never_scanned_clause()

    base = select(Asset).where(
        Asset.tenant_id == tenant_id,
        Asset.is_ignored.is_(False),
        authoritative,
        never_scanned,
    )

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Defense-in-depth clamp mirrors assets/router.py::list_assets's own
    # safe_page/safe_size belt-and-suspenders (the router's Query(...)
    # bounds are the primary defense).
    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 100))

    paged = (
        base.order_by(Asset.hostname.asc(), Asset.id.asc())
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
    )
    assets = (await db.execute(paged)).scalars().all()

    items = [
        BlindSpotAssetResponse(
            id=a.id,
            hostname=a.hostname or "",
            category=a.device_category,
            os=a.os_name,
            last_seen_at=a.last_seen_at,
            seen_by_sources=list(a.seen_by_sources or []),
        )
        for a in assets
    ]

    total_authoritative_assets = await _count_authoritative_assets(db, tenant_id, authoritative)

    return BlindSpotAssetListResponse(
        items=items,
        total=total,
        page=safe_page,
        page_size=safe_page_size,
        pages=(total + safe_page_size - 1) // safe_page_size,
        has_authoritative_inventory=total_authoritative_assets > 0,
        total_authoritative_assets=total_authoritative_assets,
    )
