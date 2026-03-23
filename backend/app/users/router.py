"""Users API — merges Humaans people data with CrowdStrike asset data.

Provides a unified view of users and their devices, combining:
  - Humaans: name, work email, job title, GitHub/Element handles
  - CrowdStrike: devices, OS, risk score, vuln counts, last seen, host status
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.auth.dependencies import get_current_user
from app.db.session import get_db
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
    humaans_filter = [
        Asset.tenant_id == user.tenant_id,
        Asset.assigned_user.isnot(None),
        Asset.mdm_details["humaans_person_id"].astext.isnot(None),
    ]

    # Count unique Humaans users
    users_q = select(func.count(func.distinct(Asset.assigned_user))).where(*humaans_filter)
    total_users = (await db.execute(users_q)).scalar_one() or 0

    # Users with email
    humaans_q = select(func.count(func.distinct(Asset.assigned_user))).where(
        *humaans_filter,
        Asset.mdm_details["humaans_email"].astext != "",
    )
    humaans_enriched = (await db.execute(humaans_q)).scalar_one() or 0

    # Assets linked to Humaans users
    assigned_assets_q = select(func.count()).where(*humaans_filter)
    assigned_assets = (await db.execute(assigned_assets_q)).scalar_one() or 0

    # Unassigned assets (no user info at all)
    total_assets_q = select(func.count()).where(Asset.tenant_id == user.tenant_id)
    total_assets = (await db.execute(total_assets_q)).scalar_one() or 0
    unassigned = total_assets - assigned_assets

    return {
        "total_users": total_users,
        "humaans_enriched": humaans_enriched,
        "assigned_assets": assigned_assets,
        "unassigned_assets": unassigned,
    }
