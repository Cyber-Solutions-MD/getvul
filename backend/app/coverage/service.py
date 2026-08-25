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
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import ColumnElement, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.constants import ENRICHMENT_SOURCES, SCANNER_SOURCES
from app.assets.models import Asset
from app.auth.schemas import CurrentUser
from app.connectors.service import _normalize_sync_status
from app.coverage.schemas import (
    BlindSpotAssetListResponse,
    BlindSpotAssetResponse,
    CoverageConnectorCardResponse,
    CoverageSummaryResponse,
)
from app.notifications.alerting_config import merged_alerting_config
from app.tenants.models import Tenant
from app.ticketing.models import ConnectorConfig

logger = structlog.get_logger()

DEFAULT_PAGE_SIZE = 50

# D-06: a connector is "stale" when it hasn't reported in MORE than 7 days --
# strict `>`, never `>=` (a connector synced exactly 7 days ago is NOT stale).
STALE_THRESHOLD = timedelta(days=7)


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


async def _count_covered_assets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    authoritative: ColumnElement[bool],
    connector_type: str,
) -> int:
    """How many authoritative assets a single connector's source has
    touched -- the numerator of that connector's coverage % (D-05)."""
    count_q = select(func.count()).select_from(
        select(Asset.id)
        .where(
            Asset.tenant_id == tenant_id,
            Asset.is_ignored.is_(False),
            authoritative,
            Asset.seen_by_sources.contains([connector_type]),
        )
        .subquery()
    )
    return (await db.execute(count_q)).scalar() or 0


async def get_coverage_summary(db: AsyncSession, tenant_id: uuid.UUID) -> CoverageSummaryResponse:
    """COV-02: for each enabled scanner connector (Pitfall 6 -- iterate
    `ConnectorConfig` where `connector_type in SCANNER_SOURCES`, never
    special-case vendor names), what fraction of the authoritative (MDM/HR)
    inventory it actually covers (D-05), plus a stale-source flag when it
    hasn't reported in >7 days (D-06) and the wire-normalized sync status
    (Pitfall 3). Reuses the identical `authoritative` clause the blind-spot
    reconciliation above already uses -- one source of truth, not a second
    query shape."""
    authoritative = _authoritative_clause()
    total = await _count_authoritative_assets(db, tenant_id, authoritative)

    conn_q = select(ConnectorConfig).where(
        ConnectorConfig.tenant_id == tenant_id,
        ConnectorConfig.is_enabled.is_(True),
        ConnectorConfig.connector_type.in_(SCANNER_SOURCES),
    )
    connectors = (await db.execute(conn_q)).scalars().all()

    now = datetime.now(timezone.utc)
    cards: list[CoverageConnectorCardResponse] = []
    for conn in connectors:
        covered = await _count_covered_assets(db, tenant_id, authoritative, conn.connector_type)
        # D-11: null (never 0/100) when the denominator is zero.
        coverage_pct = round(100 * covered / total) if total else None

        last_sync_at = conn.last_sync_at
        is_stale = bool(last_sync_at and (now - last_sync_at) > STALE_THRESHOLD)
        stale_days = (now - last_sync_at).days if is_stale and last_sync_at else None

        cards.append(
            CoverageConnectorCardResponse(
                connector_type=conn.connector_type,
                coverage_pct=coverage_pct,
                is_stale=is_stale,
                stale_days=stale_days,
                last_sync_status=_normalize_sync_status(conn.last_sync_status),
                last_sync_at=last_sync_at,
            )
        )

    return CoverageSummaryResponse(
        cards=cards,
        total_authoritative_assets=total,
        has_authoritative_inventory=total > 0,
        has_scanner_connector=len(cards) > 0,
    )


async def route_to_owner(
    db: AsyncSession,
    tenant: Tenant,
    user: CurrentUser,
    asset: Asset,
) -> dict[str, str]:
    """COV-03: resolve a never-scanned asset's owner via the directory and
    tell them the device is in inventory but no scanner covers it (D-07,
    notify-only -- no synthetic finding, no ticket, no new column). Falls
    back to the tenant's OWNER/ADMIN users plus the tenant alert channel
    when no owner resolves (D-09), so the riskiest shadow-IT asset is never
    silently dropped. Mirrors `alerts.py::_fire_kev_epss_alert`'s
    resolve-then-notify-with-fallback template, adapted to a real
    `CurrentUser` actor: the caller (router) audits and commits, this
    function never calls `db.commit()` and never constructs `AuditLog`
    directly.

    Local imports mirror `_fire_kev_epss_alert` / `detect_and_escalate`'s
    own idiom -- each re-resolves the module attribute fresh on every call,
    so `monkeypatch.setattr` on the origin module is honored by tests.
    """
    from app.assets.directory import get_directory_user
    from app.notifications.alerts import _email_owners_and_admins
    from app.notifications.escalation_channels import dispatch_channel
    from app.notifications.service import _send_notification_email
    from app.vulnerabilities.sla_tier_service import _build_channel_config

    hostname = asset.hostname or "Unknown host"
    title = f"Unmanaged device needs a scanner: {hostname}"
    message = (
        f"{hostname} is in your device inventory but no vulnerability scanner covers it. "
        "Please onboard it to a scanner so its vulnerabilities can be tracked."
    )
    category = "coverage_route_to_owner"

    # D-07: resolved owner gets emailed directly; an unresolved owner falls
    # back to the tenant's OWNER/ADMIN users (`_email_owners_and_admins`
    # already fans out to every matching user).
    directory_user = await get_directory_user(db, tenant.id, asset)
    if directory_user and directory_user.get("email"):
        await _send_notification_email(db, tenant.id, directory_user["email"], title, message, category)
        routed_to = directory_user.get("display_name") or directory_user["email"]
    else:
        await _email_owners_and_admins(db, tenant, title, message, category)
        routed_to = "your admins"

    # D-09: also push to the tenant's configured channel(s) for this routing
    # key -- fail-isolated per channel, never blocks the email/audit above.
    sla_config = tenant.sla_config or {}
    channels = merged_alerting_config(tenant)["routing"].get("coverage_unmanaged_asset") or []
    for channel in channels:
        try:
            channel_config = _build_channel_config(sla_config, channel, tenant)
            outcome = await dispatch_channel(
                channel,
                channel_config,
                {"hostname": hostname, "routed_to": routed_to, "category": category},
            )
        except Exception as e:  # decrypt/dispatch failure -- never blocks the email or the audit
            outcome = {"ok": False, "error": str(e)}
        if not outcome.get("ok"):
            logger.warning(
                "coverage_route_to_owner_channel_dispatch_failed",
                tenant_id=str(tenant.id),
                asset_id=str(asset.id),
                channel=channel,
                error=outcome.get("error"),
            )

    return {"hostname": hostname, "routed_to": routed_to}
