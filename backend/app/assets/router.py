"""Assets API router — CRUD, filtering, classification."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, case, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.assets.models import Asset
from app.assets.classification import classify_asset
from app.vulnerabilities.models import Vulnerability

router = APIRouter(prefix="", tags=["Assets"])


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
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List assets with filtering, pagination, sorting."""
    query = select(Asset).where(Asset.tenant_id == user.tenant_id)

    # Filters
    if search:
        query = query.where(
            (Asset.hostname.ilike(f"%{search}%")) | (Asset.os_name.ilike(f"%{search}%"))
        )
    if device_category:
        categories = [c.strip().upper() for c in device_category.split(",") if c.strip()]
        if categories:
            query = query.where(Asset.device_category.in_(categories))
    if scanner:
        # Filter by seen_by_sources containing the scanner
        scanners = [s.strip().upper() for s in scanner.split(",") if s.strip()]
        for s in scanners:
            query = query.where(Asset.seen_by_sources.has_key(s.upper()))
    if min_risk > 0:
        query = query.where(Asset.risk_score >= min_risk)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    sort_col = getattr(Asset, sort_by, Asset.risk_score)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    assets = result.scalars().all()

    # Enrich with vuln counts
    items = []
    for a in assets:
        vuln_q = select(
            func.count().label("total"),
            func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
            func.count().filter(Vulnerability.severity == "HIGH").label("high"),
            func.count().filter(Vulnerability.exploit_available == True).label("exploitable"),
            func.count().filter(Vulnerability.cisa_kev == True).label("kev"),
        ).where(Vulnerability.asset_id == a.id)
        vcounts = (await db.execute(vuln_q)).one()

        items.append({
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
        })

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
    base = select(Asset).where(Asset.tenant_id == user.tenant_id)

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
        await db.execute(
            select(func.avg(Asset.risk_score)).where(Asset.tenant_id == user.tenant_id)
        )
    ).scalar() or 0

    # Risk distribution
    risk_q = (
        select(
            func.count().filter(Asset.risk_score >= 80).label("critical"),
            func.count().filter((Asset.risk_score >= 50) & (Asset.risk_score < 80)).label("high"),
            func.count().filter((Asset.risk_score >= 20) & (Asset.risk_score < 50)).label("medium"),
            func.count().filter(Asset.risk_score < 20).label("low"),
        ).where(Asset.tenant_id == user.tenant_id)
    )
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
        await db.execute(
            select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id)
        )
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
        func.count().filter(Vulnerability.exploit_available == True).label("exploitable"),
        func.count().filter(Vulnerability.cisa_kev == True).label("kev"),
    ).where(Vulnerability.asset_id == asset.id)
    vc = (await db.execute(vuln_q)).one()

    # Vulns list
    vulns = (
        await db.execute(
            select(Vulnerability)
            .where(Vulnerability.asset_id == asset.id)
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
    ).scalars().all()

    return {
        "id": str(asset.id),
        "hostname": asset.hostname,
        "os_name": asset.os_name,
        "os_version": asset.os_version,
        "device_category": asset.device_category or "OTHER",
        "risk_score": asset.risk_score or 0,
        "ip_addresses": asset.ip_addresses or [],
        "mac_addresses": asset.mac_addresses or [],
        "seen_by_sources": asset.seen_by_sources or {},
        "assigned_user": asset.assigned_user,
        "department": asset.department,
        "building": asset.building,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "managed_by": asset.managed_by,
        "last_checkin_at": str(asset.last_checkin_at) if asset.last_checkin_at else None,
        "mdm_details": asset.mdm_details,
        "vuln_counts": {
            "total": vc.total, "critical": vc.critical, "high": vc.high,
            "medium": vc.medium, "low": vc.low, "exploitable": vc.exploitable, "kev": vc.kev,
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


@router.post("/classify")
async def classify_all_assets(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Re-classify all assets by device type."""
    result = await db.execute(
        select(Asset).where(Asset.tenant_id == user.tenant_id)
    )
    assets = result.scalars().all()

    counts: dict[str, int] = {}
    for asset in assets:
        category = classify_asset(asset)
        asset.device_category = category
        counts[category] = counts.get(category, 0) + 1

    await db.commit()
    return {"classified": len(assets), "by_category": counts}
