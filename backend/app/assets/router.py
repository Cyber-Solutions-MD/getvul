"""Assets API router — CRUD, filtering, classification."""

from __future__ import annotations

from datetime import UTC

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.classification import classify_asset
from app.assets.models import Asset
from app.auth.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.vulnerabilities.models import Vulnerability

router = APIRouter(prefix="", tags=["Assets"])


async def _get_directory_user(db: AsyncSession, tenant_id, asset) -> dict | None:
    """Find matching directory user for an asset by email."""
    from app.tenants.models import User

    # Try to match by humaans_email, assigned_user email, or last_login_user
    emails_to_try = []
    mdm = asset.mdm_details or {}
    if mdm.get("humaans_email"):
        emails_to_try.append(mdm["humaans_email"].lower())
    if asset.assigned_user and "@" in asset.assigned_user:
        emails_to_try.append(asset.assigned_user.lower())
    if asset.last_login_user and "@" in asset.last_login_user:
        emails_to_try.append(asset.last_login_user.lower())

    if not emails_to_try:
        return None

    from sqlalchemy import or_

    result = await db.execute(
        select(User)
        .where(
            User.tenant_id == tenant_id,
            or_(*[User.email == e for e in emails_to_try]),
        )
        .limit(1)
    )
    u = result.scalar_one_or_none()
    if not u:
        return None

    return {
        "email": u.email,
        "display_name": u.display_name,
        "department": u.department,
        "job_title": u.job_title,
        "avatar_url": u.avatar_url,
        "groups": u.groups or [],
        "idp_source": u.idp_source,
        "is_active": u.is_active,
        "role": u.role,
    }


@router.get("")
async def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = Query("", description="Search hostname or OS"),
    device_category: str = Query("", description="WORKSTATION,SERVER,NETWORK,MOBILE,OTHER"),
    scanner: str = Query("", description="CROWDSTRIKE,NESSUS,DEFENDER,WIZ,JAMF"),
    min_risk: int = Query(0, ge=0, le=100),
    sort_by: str = Query("risk_score", description="risk_score,hostname,os_name,device_category"),
    sort_dir: str = Query("desc", description="asc or desc"),
    show_ignored: str = Query("active", description="active, ignored, or all"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List assets with filtering, pagination, sorting."""
    query = select(Asset).where(Asset.tenant_id == user.tenant_id)

    # Ignored filter
    if show_ignored == "ignored":
        query = query.where(Asset.is_ignored.is_(True))
    elif show_ignored != "all":
        query = query.where(Asset.is_ignored.is_(False))

    # Filters
    if search:
        query = query.where((Asset.hostname.ilike(f"%{search}%")) | (Asset.os_name.ilike(f"%{search}%")))
    if device_category:
        categories = [c.strip().upper() for c in device_category.split(",") if c.strip()]
        if categories:
            query = query.where(Asset.device_category.in_(categories))
    if scanner:
        # Filter by seen_by_sources containing the scanner
        # seen_by_sources is a JSONB array like ["CROWDSTRIKE", "NESSUS"]
        scanners = [s.strip().upper() for s in scanner.split(",") if s.strip()]
        for s in scanners:
            query = query.where(Asset.seen_by_sources.contains([s]))
    if min_risk > 0:
        query = query.where(Asset.risk_score >= min_risk)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort (allowlist to prevent SQL injection via column name)
    allowed_sort = {"risk_score", "hostname", "os_name", "device_category"}
    safe_sort_by = sort_by if sort_by in allowed_sort else "risk_score"
    sort_col = getattr(Asset, safe_sort_by)
    query = query.order_by(sort_col.asc()) if sort_dir == "asc" else query.order_by(sort_col.desc())

    # Paginate — clamp to safe integer range to satisfy SAST taint analysis
    safe_page = max(1, min(int(page), 10000))
    safe_size = max(1, min(int(page_size), 100))
    query = query.offset((safe_page - 1) * safe_size).limit(safe_size)
    result = await db.execute(query)  # nosemgrep: python.fastapi.db.generic-sql-fastapi.generic-sql-fastapi
    assets = result.scalars().all()

    # Enrich with vuln counts
    items = []
    for a in assets:
        vuln_q = select(
            func.count().label("total"),
            func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
            func.count().filter(Vulnerability.severity == "HIGH").label("high"),
            func.count().filter(Vulnerability.exploit_available).label("exploitable"),
            func.count().filter(Vulnerability.cisa_kev).label("kev"),
        ).where(Vulnerability.asset_id == a.id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]))
        vcounts = (await db.execute(vuln_q)).one()

        items.append(
            {
                "id": str(a.id),
                "hostname": a.hostname,
                "os_name": a.os_name,
                "os_version": a.os_version,
                "device_category": a.device_category or "OTHER",
                "risk_score": a.risk_score or 0,
                "seen_by_sources": a.seen_by_sources or {},
                "assigned_user": a.assigned_user,
                "department": a.department,
                "model": a.model,
                "serial_number": a.serial_number,
                "managed_by": a.managed_by,
                "ip_addresses": a.ip_addresses or [],
                "total_vulns": vcounts.total,
                "critical": vcounts.critical,
                "high": vcounts.high,
                "exploitable": vcounts.exploitable,
                "kev": vcounts.kev,
                "is_ignored": a.is_ignored,
                "ignored_at": a.ignored_at.isoformat() if a.ignored_at else None,
                "ignored_reason": a.ignored_reason,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/stats")
async def asset_stats(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard stats for assets."""
    base = select(Asset).where(Asset.tenant_id == user.tenant_id, Asset.is_ignored.is_(False))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    # By device category
    cat_q = (
        select(Asset.device_category, func.count())
        .where(Asset.tenant_id == user.tenant_id)
        .group_by(Asset.device_category)
    )
    cats = {row[0] or "OTHER": row[1] for row in (await db.execute(cat_q)).fetchall()}

    # Avg risk score
    avg_risk = (
        await db.execute(select(func.avg(Asset.risk_score)).where(Asset.tenant_id == user.tenant_id))
    ).scalar() or 0

    # Risk distribution
    risk_q = select(
        func.count().filter(Asset.risk_score >= 80).label("critical"),
        func.count().filter((Asset.risk_score >= 50) & (Asset.risk_score < 80)).label("high"),
        func.count().filter((Asset.risk_score >= 20) & (Asset.risk_score < 50)).label("medium"),
        func.count().filter(Asset.risk_score < 20).label("low"),
    ).where(Asset.tenant_id == user.tenant_id)
    risk_dist = (await db.execute(risk_q)).one()

    return {
        "total": total,
        "avg_risk_score": round(float(avg_risk), 1),
        "by_device_category": cats,
        "risk_distribution": {
            "critical": risk_dist.critical,
            "high": risk_dist.high,
            "medium": risk_dist.medium,
            "low": risk_dist.low,
        },
    }


@router.get("/{asset_id}")
async def get_asset(
    asset_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get single asset with full details."""
    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException

        raise HTTPException(404, "Asset not found")

    # Vuln breakdown
    vuln_q = select(
        func.count().label("total"),
        func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
        func.count().filter(Vulnerability.severity == "HIGH").label("high"),
        func.count().filter(Vulnerability.severity == "MEDIUM").label("medium"),
        func.count().filter(Vulnerability.severity == "LOW").label("low"),
        func.count().filter(Vulnerability.exploit_available).label("exploitable"),
        func.count().filter(Vulnerability.cisa_kev).label("kev"),
    ).where(Vulnerability.asset_id == asset.id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]))
    vc = (await db.execute(vuln_q)).one()

    # Vulns list
    vulns = (
        (
            await db.execute(
                select(Vulnerability)
                .where(Vulnerability.asset_id == asset.id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]))
                .order_by(
                    case(
                        (Vulnerability.severity == "CRITICAL", 0),
                        (Vulnerability.severity == "HIGH", 1),
                        (Vulnerability.severity == "MEDIUM", 2),
                        else_=3,
                    )
                )
                .limit(100)
            )
        )
        .scalars()
        .all()
    )

    return {
        "id": str(asset.id),
        "hostname": asset.hostname,
        "os_name": asset.os_name,
        "os_version": asset.os_version,
        "device_category": asset.device_category or "OTHER",
        "asset_type": asset.asset_type,
        "risk_score": asset.risk_score or 0,
        "ip_addresses": asset.ip_addresses or [],
        "mac_addresses": asset.mac_addresses or [],
        "external_ip": asset.external_ip,
        "seen_by_sources": asset.seen_by_sources or {},
        # Device identity
        "serial_number": asset.serial_number,
        "model": asset.model,
        "system_manufacturer": asset.system_manufacturer,
        # User & activity
        "last_login_user": asset.last_login_user,
        "last_login_at": asset.last_login_at.isoformat() if asset.last_login_at else None,
        "last_seen_at": asset.last_seen_at.isoformat() if asset.last_seen_at else None,
        "host_status": asset.host_status,
        # HR / MDM enrichment
        "assigned_user": asset.assigned_user,
        "department": asset.department,
        "building": asset.building,
        "managed_by": asset.managed_by,
        "last_checkin_at": str(asset.last_checkin_at) if asset.last_checkin_at else None,
        "mdm_details": asset.mdm_details,
        # Humaans-specific (extracted from mdm_details for convenience)
        "humaans_email": (asset.mdm_details or {}).get("humaans_email"),
        "github_handle": (asset.mdm_details or {}).get("github_handle"),
        "linkedin_handle": (asset.mdm_details or {}).get("linkedin_handle"),
        "element_handle": (asset.mdm_details or {}).get("element_handle"),
        "humaans_teams": (asset.mdm_details or {}).get("humaans_teams"),
        "humaans_location": (asset.mdm_details or {}).get("humaans_location"),
        "humaans_timezone": (asset.mdm_details or {}).get("humaans_timezone"),
        # CrowdStrike
        "crowdstrike_aid": asset.crowdstrike_aid,
        # Directory user info (from Google Workspace / Azure / Okta sync)
        "directory_user": await _get_directory_user(db, user.tenant_id, asset),
        "is_ignored": asset.is_ignored,
        "ignored_at": asset.ignored_at.isoformat() if asset.ignored_at else None,
        "ignored_reason": asset.ignored_reason,
        "vuln_counts": {
            "total": vc.total,
            "critical": vc.critical,
            "high": vc.high,
            "medium": vc.medium,
            "low": vc.low,
            "exploitable": vc.exploitable,
            "kev": vc.kev,
        },
        "vulnerabilities": [
            {
                "id": str(v.id),
                "cve_id": v.cve_id,
                "severity": v.severity,
                "status": v.status,
                "product": v.affected_product,
                "remediation": v.remediation_action,
                "exploit_status": v.exploit_status_name,
                "is_exploitable": bool(v.exploit_status_id) if hasattr(v, "exploit_status") else False,
                "is_cisa_kev": v.cisa_kev or False,
                "source": v.source,
            }
            for v in vulns
        ],
    }


@router.post("/{asset_id}/ignore")
async def ignore_asset(
    asset_id: str,
    body: dict = None,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark an asset as ignored — excludes from remediations and ticket creation."""
    from datetime import datetime

    from app.audit import audit

    if body is None:
        body = {}
    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException

        raise HTTPException(404, "Asset not found")

    asset.is_ignored = True
    asset.ignored_at = datetime.now(UTC)
    asset.ignored_reason = body.get("reason", "")
    await audit(
        db, user, "asset.ignore", "asset", str(asset.id), {"hostname": asset.hostname, "reason": asset.ignored_reason}
    )
    await db.commit()
    return {"message": f"Asset '{asset.hostname}' ignored", "is_ignored": True}


@router.post("/{asset_id}/unignore")
async def unignore_asset(
    asset_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unignore an asset — restores it to active remediation and ticket creation."""
    from app.audit import audit

    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException

        raise HTTPException(404, "Asset not found")

    asset.is_ignored = False
    asset.ignored_at = None
    asset.ignored_reason = None
    await audit(db, user, "asset.unignore", "asset", str(asset.id), {"hostname": asset.hostname})
    await db.commit()
    return {"message": f"Asset '{asset.hostname}' restored", "is_ignored": False}


@router.post("/bulk-ignore")
async def bulk_ignore_assets(
    body: dict,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk ignore/unignore assets."""
    from datetime import datetime

    from app.audit import audit

    asset_ids = body.get("asset_ids", [])
    action = body.get("action", "ignore")  # "ignore" or "unignore"
    reason = body.get("reason", "")

    if not asset_ids:
        from fastapi import HTTPException

        raise HTTPException(400, "No asset IDs provided")

    result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids), Asset.tenant_id == user.tenant_id))
    assets = result.scalars().all()

    for a in assets:
        if action == "ignore":
            a.is_ignored = True
            a.ignored_at = datetime.now(UTC)
            a.ignored_reason = reason
        else:
            a.is_ignored = False
            a.ignored_at = None
            a.ignored_reason = None

    await audit(db, user, f"asset.bulk_{action}", "asset", None, {"count": len(assets), "reason": reason})
    await db.commit()
    return {"message": f"{len(assets)} assets {action}d"}


@router.post("/recompute-risk-scores")
async def recompute_risk_scores(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Recompute risk scores for all assets based on current vulnerabilities."""
    from app.assets.risk_score import compute_risk_scores

    stats = await compute_risk_scores(db, user.tenant_id)
    await db.commit()
    return {"message": "Risk scores recomputed", **stats}


@router.post("/classify")
async def classify_all_assets(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Re-classify all assets by device type."""
    result = await db.execute(select(Asset).where(Asset.tenant_id == user.tenant_id))
    assets = result.scalars().all()

    counts: dict[str, int] = {}
    for asset in assets:
        category = classify_asset(asset)
        asset.device_category = category
        counts[category] = counts.get(category, 0) + 1

    await db.commit()
    return {"classified": len(assets), "by_category": counts}
