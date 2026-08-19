"""Users API — merges Humaans people data with CrowdStrike asset data.

Provides a unified view of users and their devices, combining:
  - Humaans: name, work email, job title, GitHub/Element handles
  - CrowdStrike: devices, OS, risk score, vuln counts, last seen, host status
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.exceptions.service import active_exception_subquery
from app.vulnerabilities.models import Vulnerability

router = APIRouter(prefix="", tags=["Users"])


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = Query("", description="Search by name, email, or hostname"),
    risk: str = Query("", description="Risk filter: critical,high,medium,low"),
    sort_by: str = Query("risk_score", description="risk_score,name,devices,vulns"),
    sort_dir: str = Query("desc", description="asc or desc"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List users with their devices and aggregated risk info.

    A 'user' is identified by assigned_user (from Humaans) or last_login_user (from CrowdStrike).
    Assets are grouped by user to show each person's devices.
    """
    # Build base query: only assets enriched by Humaans (have humaans_person_id)
    query = select(Asset).where(
        Asset.tenant_id == user.tenant_id,
        Asset.assigned_user.isnot(None),
        Asset.mdm_details["humaans_person_id"].astext.isnot(None),
    )

    # Search filter
    if search:
        s = f"%{search}%"
        query = query.where(
            or_(
                Asset.assigned_user.ilike(s),
                Asset.last_login_user.ilike(s),
                Asset.hostname.ilike(s),
                Asset.mdm_details["humaans_email"].astext.ilike(s),
            )
        )

    # Fetch all matching assets
    assets = (await db.execute(query)).scalars().all()

    # Group assets by user identity
    user_map: dict[str, dict] = {}
    for a in assets:
        # Determine the user key — prefer assigned_user (Humaans), fall back to last_login_user
        user_key = (a.assigned_user or "").strip().lower()
        if not user_key:
            user_key = (a.last_login_user or "").strip().lower()
        if not user_key:
            continue

        if user_key not in user_map:
            humaans_data = a.mdm_details or {}
            user_map[user_key] = {
                "user_key": user_key,
                "name": a.assigned_user or a.last_login_user or "",
                "email": humaans_data.get("humaans_email", ""),
                "job_title": humaans_data.get("humaans_job_title", ""),
                "department": a.department or "",
                "github_handle": humaans_data.get("github_handle", ""),
                "linkedin_handle": humaans_data.get("linkedin_handle", ""),
                "element_handle": humaans_data.get("element_handle", ""),
                "humaans_teams": humaans_data.get("humaans_teams", []),
                "humaans_location": humaans_data.get("humaans_location", ""),
                "humaans_timezone": humaans_data.get("humaans_timezone", ""),
                "humaans_person_id": humaans_data.get("humaans_person_id", ""),
                "devices": [],
                "total_vulns": 0,
                "critical_vulns": 0,
                "high_vulns": 0,
                "exploitable_vulns": 0,
                "kev_vulns": 0,
                "max_risk_score": 0,
                "device_count": 0,
            }

        entry = user_map[user_key]
        # Update Humaans data if this asset has richer info
        h = a.mdm_details or {}
        if h.get("humaans_email") and not entry["email"]:
            entry["email"] = h["humaans_email"]
            entry["job_title"] = h.get("humaans_job_title", "")
            entry["github_handle"] = h.get("github_handle", "")
            entry["linkedin_handle"] = h.get("linkedin_handle", "")
            entry["element_handle"] = h.get("element_handle", "")
            entry["humaans_teams"] = h.get("humaans_teams", [])
            entry["humaans_location"] = h.get("humaans_location", "")
            entry["humaans_timezone"] = h.get("humaans_timezone", "")
            entry["humaans_person_id"] = h.get("humaans_person_id", "")
        if a.assigned_user and (not entry["name"] or entry["name"] == a.last_login_user):
            entry["name"] = a.assigned_user

        entry["devices"].append(
            {
                "id": str(a.id),
                "hostname": a.hostname,
                "os_name": a.os_name,
                "os_version": a.os_version,
                "model": a.model,
                "serial_number": a.serial_number,
                "device_category": a.device_category or "OTHER",
                "risk_score": a.risk_score or 0,
                "host_status": a.host_status,
                "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
                "last_login_user": a.last_login_user,
            }
        )
        entry["max_risk_score"] = max(entry["max_risk_score"], a.risk_score or 0)
        entry["device_count"] += 1

    # Fetch vuln counts per user (aggregate across all their assets)
    for entry in user_map.values():
        asset_ids = [d["id"] for d in entry["devices"]]
        if not asset_ids:
            continue
        vuln_q = select(
            func.count().label("total"),
            func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
            func.count().filter(Vulnerability.severity == "HIGH").label("high"),
            func.count().filter(Vulnerability.exploit_available.is_(True)).label("exploitable"),
            func.count().filter(Vulnerability.cisa_kev.is_(True)).label("kev"),
        ).where(
            Vulnerability.asset_id.in_(asset_ids),
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            # EXC-02/D-15 (Phase 39 Tier 2 #12): an actively-excepted
            # finding never inflates a person's owner-risk aggregate badges.
            ~active_exception_subquery(user.tenant_id, datetime.now(UTC)),
        )
        vc = (await db.execute(vuln_q)).one()
        entry["total_vulns"] = vc.total
        entry["critical_vulns"] = vc.critical
        entry["high_vulns"] = vc.high
        entry["exploitable_vulns"] = vc.exploitable
        entry["kev_vulns"] = vc.kev

    # Convert to list and apply risk filter
    users = list(user_map.values())
    if risk:
        risk_ranges = {
            "critical": (80, 101),
            "high": (50, 80),
            "medium": (20, 50),
            "low": (0, 20),
        }
        r = risk_ranges.get(risk.lower())
        if r:
            users = [u for u in users if r[0] <= u["max_risk_score"] < r[1]]

    # Sort
    sort_keys = {
        "risk_score": lambda u: u["max_risk_score"],
        "name": lambda u: u["name"].lower(),
        "devices": lambda u: u["device_count"],
        "vulns": lambda u: u["total_vulns"],
    }
    key_fn = sort_keys.get(sort_by, sort_keys["risk_score"])
    users.sort(key=key_fn, reverse=(sort_dir == "desc"))

    # Paginate
    total = len(users)
    start = (page - 1) * page_size
    paginated = users[start : start + page_size]

    return {
        "items": paginated,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.get("/stats")
async def user_stats(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Summary stats for the users dashboard."""
    from app.tenants.models import User

    base = User.tenant_id == user.tenant_id

    total = (await db.execute(select(func.count(User.id)).where(base))).scalar_one()
    active = (await db.execute(select(func.count(User.id)).where(base, User.is_active.is_(True)))).scalar_one()
    suspended = total - active

    # By source
    source_q = select(User.idp_source, func.count(User.id)).where(base).group_by(User.idp_source)
    by_source = {r[0] or "local": r[1] for r in (await db.execute(source_q)).all()}

    # With department
    has_dept = (
        await db.execute(select(func.count(User.id)).where(base, User.department.isnot(None), User.department != ""))
    ).scalar_one()

    # With groups
    has_groups = (
        await db.execute(
            select(func.count(User.id)).where(base, User.groups.isnot(None), func.jsonb_array_length(User.groups) > 0)
        )
    ).scalar_one()

    # Departments breakdown
    dept_q = (
        select(User.department, func.count(User.id))
        .where(base, User.is_active.is_(True), User.department.isnot(None), User.department != "")
        .group_by(User.department)
        .order_by(func.count(User.id).desc())
        .limit(10)
    )
    departments = [{"name": r[0], "count": r[1]} for r in (await db.execute(dept_q)).all()]

    # Assets linked
    assigned_assets = (
        await db.execute(
            select(func.count(Asset.id)).where(Asset.tenant_id == user.tenant_id, Asset.assigned_user.isnot(None))
        )
    ).scalar_one()
    total_assets = (
        await db.execute(select(func.count(Asset.id)).where(Asset.tenant_id == user.tenant_id))
    ).scalar_one()

    return {
        "total_users": total,
        "active": active,
        "suspended": suspended,
        "by_source": by_source,
        "has_department": has_dept,
        "has_groups": has_groups,
        "departments": departments,
        "assigned_assets": assigned_assets,
        "unassigned_assets": total_assets - assigned_assets,
    }


@router.get("/directory")
async def list_directory_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = Query(""),
    status: str = Query("active", description="active, suspended, or all"),
    department: str = Query(""),
    source: str = Query(""),
    sort_by: str = Query("display_name"),
    sort_dir: str = Query("asc"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all directory users (from Google Workspace, Azure, Okta, Humaans, local)."""
    from app.tenants.models import User

    query = select(User).where(User.tenant_id == user.tenant_id)

    # Status filter
    if status == "active":
        query = query.where(User.is_active.is_(True))
    elif status == "suspended":
        query = query.where(User.is_active.is_(False))

    # Search
    if search:
        s = f"%{search}%"
        query = query.where(
            or_(
                User.email.ilike(s),
                User.display_name.ilike(s),
                User.department.ilike(s),
                User.job_title.ilike(s),
            )
        )

    # Department filter
    if department:
        query = query.where(User.department == department)

    # Source filter
    if source:
        query = query.where(User.idp_source == source)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    allowed_sort = {"display_name", "email", "department", "role", "last_login_at"}
    safe_sort = sort_by if sort_by in allowed_sort else "display_name"
    sort_col = getattr(User, safe_sort)
    if sort_dir == "desc":
        query = query.order_by(sort_col.desc().nullslast())
    else:
        query = query.order_by(sort_col.asc().nullslast())

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    # Enrich with device/vuln data by matching email → assigned_user or humaans_email
    emails = [u.email for u in rows if u.email]
    device_map: dict[str, list] = {e: [] for e in emails}
    vuln_map: dict[str, dict] = {}

    if emails:
        # Find assets linked to these users (by assigned_user, last_login_user, or humaans_email)
        asset_q = select(Asset).where(
            Asset.tenant_id == user.tenant_id,
            or_(
                func.lower(Asset.assigned_user).in_([e.lower() for e in emails]),
                func.lower(Asset.last_login_user).in_([e.lower() for e in emails]),
                func.lower(Asset.mdm_details["humaans_email"].astext).in_([e.lower() for e in emails]),
            ),
        )
        assets = (await db.execute(asset_q)).scalars().all()

        for a in assets:
            # Match to user email
            match_email = None
            for e in emails:
                el = e.lower()
                if (
                    (a.assigned_user or "").lower() == el
                    or (a.last_login_user or "").lower() == el
                    or ((a.mdm_details or {}).get("humaans_email") or "").lower() == el
                ):
                    match_email = e
                    break
            if not match_email:
                continue

            device_map.setdefault(match_email, []).append(
                {
                    "id": str(a.id),
                    "hostname": a.hostname,
                    "os_name": a.os_name,
                    "device_category": a.device_category or "OTHER",
                    "risk_score": a.risk_score or 0,
                    "model": a.model,
                    "serial_number": a.serial_number,
                    "host_status": a.host_status,
                    "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
                }
            )

        # Vuln counts per user's assets
        for email_key, devices in device_map.items():
            if not devices:
                continue
            asset_ids = [d["id"] for d in devices]
            vc = (
                await db.execute(
                    select(
                        func.count().label("total"),
                        func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
                        func.count().filter(Vulnerability.severity == "HIGH").label("high"),
                        func.count().filter(Vulnerability.exploit_available.is_(True)).label("exploitable"),
                    ).where(
                        Vulnerability.asset_id.in_(asset_ids),
                        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                        # EXC-02/D-15 (Phase 39 Tier 2 #12): same owner-risk
                        # aggregate exclusion as list_users above.
                        ~active_exception_subquery(user.tenant_id, datetime.now(UTC)),
                    )
                )
            ).one()
            vuln_map[email_key] = {
                "total_vulns": vc.total,
                "critical_vulns": vc.critical,
                "high_vulns": vc.high,
                "exploitable_vulns": vc.exploitable,
            }

    items = []
    for u in rows:
        devices = device_map.get(u.email, [])
        vulns = vuln_map.get(u.email, {})
        max_risk = max((d["risk_score"] for d in devices), default=0)
        items.append(
            {
                "id": str(u.id),
                "email": u.email,
                "display_name": u.display_name,
                "role": u.role,
                "department": u.department,
                "job_title": u.job_title,
                "idp_source": u.idp_source or "local",
                "is_active": u.is_active,
                "groups": u.groups or [],
                "avatar_url": u.avatar_url,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "device_count": len(devices),
                "devices": devices,
                "max_risk_score": max_risk,
                "total_vulns": vulns.get("total_vulns", 0),
                "critical_vulns": vulns.get("critical_vulns", 0),
                "high_vulns": vulns.get("high_vulns", 0),
                "exploitable_vulns": vulns.get("exploitable_vulns", 0),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }
