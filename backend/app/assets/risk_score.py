"""Risk score computation for assets based on open vulnerabilities.

Uses a piecewise curve so the score reflects real risk tiers:
  - 0       = no open vulns
  - 1-19    = low risk (only LOW/INFO vulns, or a single MEDIUM/HIGH)
  - 20-49   = medium risk (a few HIGH vulns, or many MEDIUMs)
  - 50-79   = high risk (multiple CRITICALs, or many HIGHs, exploitable findings)
  - 80-100  = critical risk (exploitable CRITICALs, CISA KEV entries, severe mix)

Per-vuln contribution:
  base weight: CRITICAL=40, HIGH=20, MEDIUM=5, LOW=1, INFO=0
  × exploit_available bonus: ×2
  × cisa_kev bonus: ×3
  (bonuses stack multiplicatively)

Raw sum is mapped to 0-100 via piecewise curve:
  Below the knee (raw ≤ 120):  sub-linear power curve, max score ~45
  Above the knee (raw > 120):  log curve from 45 → 100

Example scores:
  1 LOW=2, 5 LOW=5, 10 LOW=8
  1 MEDIUM=5, 10 MEDIUM=24, 20 MEDIUM=40
  1 HIGH=13, 5 HIGH=40, 10 HIGH=78
  1 CRITICAL=21, 3 CRITICAL=45, 5 CRITICAL=78
  1 CRITICAL exploitable=34, 2 CRITICAL exploitable=73
  1 CRITICAL KEV exploit=81, 3 CRITICAL KEV exploit=94
"""

from __future__ import annotations

import math
import uuid

import structlog
from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

# Severity weights
SEVERITY_WEIGHTS = {
    "CRITICAL": 40,
    "HIGH": 20,
    "MEDIUM": 5,
    "LOW": 1,
    "INFO": 0,
}

# Multiplier for exploit availability and CISA KEV
EXPLOIT_MULTIPLIER = 2.0
KEV_MULTIPLIER = 3.0

# Piecewise normalization parameters.
# KNEE_RAW: raw score at the transition point (~3 CRITICALs or 6 HIGHs).
# Below the knee, score grows slowly via a power curve (exponent < 1).
# Above the knee, score grows via a log curve toward 100.
# This ensures low-severity volume can't inflate scores past ~45,
# while exploitable/KEV findings push into the 80-100 range.
KNEE_RAW = 120.0
KNEE_SCORE = 45.0
MAX_RAW = 1500.0  # raw score that maps to 100


def _normalize_raw_score(raw: float) -> int:
    """Map raw weighted sum to 0-100 via piecewise curve."""
    if raw <= 0:
        return 0

    if raw <= KNEE_RAW:
        # Sub-linear power curve: grows quickly at first, flattens toward KNEE_SCORE.
        # Exponent 0.7 means diminishing returns as vulns accumulate.
        score = KNEE_SCORE * (raw / KNEE_RAW) ** 0.7
    else:
        # Log curve from KNEE_SCORE toward 100.
        # Reaches 100 around MAX_RAW.
        score = KNEE_SCORE + (100.0 - KNEE_SCORE) * (
            math.log1p(raw - KNEE_RAW) / math.log1p(MAX_RAW - KNEE_RAW)
        )

    return min(int(round(score)), 100)


async def compute_risk_scores(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """
    Recompute risk scores for all assets belonging to the tenant.

    Returns stats dict.
    """
    # Build a subquery that computes the raw weighted score per asset.
    # For each open vuln: weight * exploit_multiplier * kev_multiplier
    severity_weight = case(
        (Vulnerability.severity == "CRITICAL", SEVERITY_WEIGHTS["CRITICAL"]),
        (Vulnerability.severity == "HIGH", SEVERITY_WEIGHTS["HIGH"]),
        (Vulnerability.severity == "MEDIUM", SEVERITY_WEIGHTS["MEDIUM"]),
        (Vulnerability.severity == "LOW", SEVERITY_WEIGHTS["LOW"]),
        else_=SEVERITY_WEIGHTS["INFO"],
    )

    exploit_mult = case(
        (Vulnerability.exploit_available.is_(True), EXPLOIT_MULTIPLIER),
        else_=1.0,
    )

    kev_mult = case(
        (Vulnerability.cisa_kev.is_(True), KEV_MULTIPLIER),
        else_=1.0,
    )

    weighted_score = severity_weight * exploit_mult * kev_mult

    raw_score_sub = (
        select(
            Vulnerability.asset_id,
            func.coalesce(func.sum(weighted_score), 0).label("raw_score"),
        )
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.asset_id.isnot(None),
        )
        .group_by(Vulnerability.asset_id)
        .subquery()
    )

    # Get all assets for this tenant with their raw scores
    query = (
        select(Asset.id, func.coalesce(raw_score_sub.c.raw_score, 0).label("raw_score"))
        .outerjoin(raw_score_sub, Asset.id == raw_score_sub.c.asset_id)
        .where(Asset.tenant_id == tenant_id)
    )
    rows = (await db.execute(query)).all()

    updated = 0
    for asset_id, raw_score in rows:
        normalized = _normalize_raw_score(float(raw_score))

        await db.execute(
            update(Asset)
            .where(Asset.id == asset_id)
            .values(risk_score=normalized)
        )
        updated += 1

    logger.info(
        "risk_scores_computed",
        tenant_id=str(tenant_id),
        assets_updated=updated,
    )

    return {"assets_updated": updated}
