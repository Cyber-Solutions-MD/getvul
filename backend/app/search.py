"""Global search API — searches across vulnerabilities, assets, users, tickets, and CSPM findings."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.assets.models import Asset
from app.auth.rbac import require_viewer
from app.auth.schemas import CurrentUser
from app.cspm.models import Misconfiguration
from app.dependencies import DBSession
from app.tenants.models import User
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger(__name__)

search_router = APIRouter()

SEVERITY_RANK = case(
    (func.upper(Vulnerability.severity) == "CRITICAL", 1),
    (func.upper(Vulnerability.severity) == "HIGH", 2),
    (func.upper(Vulnerability.severity) == "MEDIUM", 3),
    (func.upper(Vulnerability.severity) == "LOW", 4),
    else_=5,
)

CSPM_SEVERITY_RANK = case(
    (func.upper(Misconfiguration.severity) == "CRITICAL", 1),
    (func.upper(Misconfiguration.severity) == "HIGH", 2),
    (func.upper(Misconfiguration.severity) == "MEDIUM", 3),
    (func.upper(Misconfiguration.severity) == "LOW", 4),
    else_=5,
)


async def _search_vulnerabilities(db: AsyncSession, tenant_id: uuid.UUID, query: str, limit: int) -> list[dict]:
    pattern = f"%{query}%"
    asset = aliased(Asset)
    stmt = (
        select(
            Vulnerability.id, Vulnerability.cve_id, Vulnerability.severity,
            Vulnerability.status, Vulnerability.affected_product,
            asset.hostname.label("hostname"), Vulnerability.source,
        )
        .outerjoin(asset, Vulnerability.asset_id == asset.id)
        .where(
            Vulnerability.tenant_id == tenant_id,
            or_(
                Vulnerability.cve_id.ilike(pattern),
                Vulnerability.vulnerability_name.ilike(pattern),
                Vulnerability.affected_product.ilike(pattern),
                Vulnerability.remediation_action.ilike(pattern),
            ),
        )
        .order_by(SEVERITY_RANK)
        .limit(limit)
    )
    return [
        {"id": str(r.id), "cve_id": r.cve_id, "severity": r.severity, "status": r.status,
         "affected_product": r.affected_product, "hostname": r.hostname, "source": r.source}
        for r in (await db.execute(stmt)).all()
    ]


async def _search_assets(db: AsyncSession, tenant_id: uuid.UUID, query: str, limit: int) -> list[dict]:
    pattern = f"%{query}%"
    stmt = (
        select(Asset.id, Asset.hostname, Asset.device_category, Asset.os_name, Asset.risk_score, Asset.host_status)
        .where(
            Asset.tenant_id == tenant_id,
            or_(
                Asset.hostname.ilike(pattern),
                Asset.serial_number.ilike(pattern),
                func.cast(Asset.ip_addresses, String).ilike(pattern),
                Asset.os_name.ilike(pattern),
            ),
        )
        .order_by(Asset.risk_score.desc().nulls_last())
        .limit(limit)
    )
    return [
        {"id": str(r.id), "hostname": r.hostname, "device_category": r.device_category,
         "os_name": r.os_name, "risk_score": r.risk_score, "host_status": r.host_status}
        for r in (await db.execute(stmt)).all()
    ]


async def _search_users(db: AsyncSession, tenant_id: uuid.UUID, query: str, limit: int) -> list[dict]:
    pattern = f"%{query}%"
    stmt = (
        select(User.id, User.email, User.display_name, User.department, User.role, User.is_active)
        .where(
            User.tenant_id == tenant_id,
            or_(User.email.ilike(pattern), User.display_name.ilike(pattern), User.department.ilike(pattern)),
        )
        .order_by(User.display_name)
        .limit(limit)
    )
    return [
        {"id": str(r.id), "email": r.email, "name": r.display_name, "department": r.department,
         "role": r.role, "is_active": r.is_active}
        for r in (await db.execute(stmt)).all()
    ]


async def _search_tickets(db: AsyncSession, tenant_id: uuid.UUID, query: str, limit: int) -> list[dict]:
    pattern = f"%{query}%"
    vuln = aliased(Vulnerability)
    stmt = (
        select(Ticket.id, Ticket.external_ticket_url, Ticket.provider, Ticket.external_status, vuln.cve_id.label("cve_id"))
        .join(vuln, Ticket.vulnerability_id == vuln.id)
        .where(Ticket.tenant_id == tenant_id, or_(vuln.cve_id.ilike(pattern), Ticket.external_ticket_url.ilike(pattern)))
        .order_by(Ticket.created_at.desc())
        .limit(limit)
    )
    return [
        {"id": str(r.id), "external_ticket_url": r.external_ticket_url, "provider": r.provider,
         "external_status": r.external_status, "cve_id": r.cve_id}
        for r in (await db.execute(stmt)).all()
    ]


async def _search_cspm(db: AsyncSession, tenant_id: uuid.UUID, query: str, limit: int) -> list[dict]:
    pattern = f"%{query}%"
    stmt = (
        select(Misconfiguration.id, Misconfiguration.rule_id, Misconfiguration.rule_name,
               Misconfiguration.severity, Misconfiguration.status, Misconfiguration.resource_name,
               Misconfiguration.cloud_provider)
        .where(
            Misconfiguration.tenant_id == tenant_id,
            or_(
                Misconfiguration.rule_id.ilike(pattern), Misconfiguration.rule_name.ilike(pattern),
                Misconfiguration.resource_name.ilike(pattern), Misconfiguration.resource_id.ilike(pattern),
            ),
        )
        .order_by(CSPM_SEVERITY_RANK)
        .limit(limit)
    )
    return [
        {"id": str(r.id), "rule_id": r.rule_id, "rule_name": r.rule_name, "severity": r.severity,
         "status": r.status, "resource_name": r.resource_name, "cloud_provider": r.cloud_provider}
        for r in (await db.execute(stmt)).all()
    ]


@search_router.get("/search")
async def global_search(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(5, ge=1, le=10),
) -> dict[str, Any]:
    """Search across vulnerabilities, assets, users, tickets, and CSPM findings."""
    results: dict[str, list] = {}
    for name, fn in [
        ("vulnerabilities", _search_vulnerabilities),
        ("assets", _search_assets),
        ("users", _search_users),
        ("tickets", _search_tickets),
        ("cspm", _search_cspm),
    ]:
        try:
            results[name] = await fn(db, user.tenant_id, q, limit)
        except Exception as e:
            logger.error("search_category_error", category=name, error=str(e))
            results[name] = []

    total = sum(len(v) for v in results.values())
    return {"query": q, "results": results, "total": total}
