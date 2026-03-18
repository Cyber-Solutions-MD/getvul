"""Compute risk scores for assets based on open vulnerabilities."""

from __future__ import annotations

import uuid

from sqlalchemy import func, case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability


async def compute_risk_score(db: AsyncSession, asset_id: uuid.UUID) -> int:
    """Compute risk score (0-100) for a single asset.

    Formula:
      raw = sum of weights per open vuln:
        CRITICAL=40, HIGH=20, MEDIUM=5, LOW=1
        × 2 if exploit_available
        × 3 if cisa_kev
      score = min(100, raw)
    """
    q = select(
        func.sum(
            case(
                (Vulnerability.severity == "CRITICAL", 40),
                (Vulnerability.severity == "HIGH", 20),
                (Vulnerability.severity == "MEDIUM", 5),
                (Vulnerability.severity == "LOW", 1),
                else_=0,
            )
            * case((Vulnerability.exploit_available.is_(True), 2), else_=1)
            * case((Vulnerability.cisa_kev.is_(True), 3), else_=1)
        )
    ).where(
        Vulnerability.asset_id == asset_id,
        Vulnerability.status == "OPEN",
    )
    raw = (await db.execute(q)).scalar_one() or 0
    return min(100, raw)


async def recompute_all_risk_scores(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Recompute risk scores for all assets in a tenant. Returns count updated."""
    result = await db.execute(
        select(Asset.id).where(Asset.tenant_id == tenant_id)
    )
    asset_ids = [r[0] for r in result.all()]

    count = 0
    for aid in asset_ids:
        score = await compute_risk_score(db, aid)
        await db.execute(
            update(Asset).where(Asset.id == aid).values(risk_score=score)
        )
        count += 1

    return count
