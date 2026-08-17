"""Campaign business logic: race-safe get-or-create (D-11) + compute-on-read
progress aggregation (D-07/D-18) for Phase 38 (CAMP-01/CAMP-04).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.campaigns.models import Campaign
from app.vulnerabilities.models import Vulnerability

# D-18 / 38-RESEARCH.md Pitfall 2: campaign membership/progress counts ONLY
# these three actionable statuses. NEVER reuse remediation_service.py's
# _base_open_vulns() here -- it excludes REMEDIATED entirely, which would
# make "% remediated" permanently read 0. SUPPRESSED/FALSE_POSITIVE are
# deliberately excluded from the denominator (D-18), matching the
# remediation-grouped entry-point view's own default semantics.
_CAMPAIGN_MEMBER_STATUSES = ("OPEN", "IN_PROGRESS", "REMEDIATED")


async def get_or_create_campaign(
    db: AsyncSession, tenant_id: uuid.UUID, remediation_id: str, user_id: uuid.UUID
) -> tuple[Campaign, bool]:
    """D-11 race-safe get-or-create.

    SELECTs the existing ACTIVE campaign first (the common-case fast path --
    D-11's "opens the existing campaign" UX), then INSERTs inside a nested
    transaction, catching the partial-unique-index `IntegrityError` as the
    concurrent-request backstop -- mirrors `sla_tier_service.py:406-428`'s
    proven `begin_nested()` + `IntegrityError` shape for the identical
    "insert unless a matching unique-constrained row already exists"
    problem.

    Returns `(campaign, is_new)` -- `is_new=False` means D-11 opened an
    existing active campaign: no row was created, and per CAMP-04's "only
    when a NEW campaign is created" contract the caller must NOT write a
    second `campaign.create` audit row in that case.
    """
    existing = (
        await db.execute(
            select(Campaign).where(
                Campaign.tenant_id == tenant_id,
                Campaign.remediation_id == remediation_id,
                Campaign.closed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    campaign = Campaign(tenant_id=tenant_id, remediation_id=remediation_id, created_by_user_id=user_id)
    db.add(campaign)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # Another request won the race between our SELECT and INSERT -- the
        # partial unique index rejected our insert. Re-SELECT the row that
        # won; it is guaranteed to exist now.
        existing = (
            await db.execute(
                select(Campaign).where(
                    Campaign.tenant_id == tenant_id,
                    Campaign.remediation_id == remediation_id,
                    Campaign.closed_at.is_(None),
                )
            )
        ).scalar_one()
        return existing, False
    return campaign, True


async def get_campaign_progress(db: AsyncSession, tenant_id: uuid.UUID, remediation_id: str) -> dict[str, int]:
    """Compute-on-read progress (D-07): total/open/in_progress/done/
    pct_remediated, aggregated fresh from a live `vulnerabilities` join --
    no persisted snapshot, ever, so this always reflects true current
    exposure (D-03 live membership).

    Pitfall 5: explicit zero-guard so a zero-member remediation_id (every
    member suppressed, or a race against ingestion right after launch)
    returns `pct_remediated=0` instead of raising `ZeroDivisionError`.
    """
    row = (
        await db.execute(
            select(
                func.count().label("total"),
                func.count().filter(Vulnerability.status == "REMEDIATED").label("done"),
                func.count().filter(Vulnerability.status == "IN_PROGRESS").label("in_progress"),
            ).where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.remediation_id == remediation_id,
                Vulnerability.status.in_(_CAMPAIGN_MEMBER_STATUSES),
            )
        )
    ).one()
    total, done, in_progress = row.total, row.done, row.in_progress
    return {
        "total": total,
        "open": total - done - in_progress,
        "in_progress": in_progress,
        "done": done,
        "pct_remediated": round(done / total * 100) if total else 0,
    }


async def list_campaigns(db: AsyncSession, tenant_id: uuid.UUID) -> list[Campaign]:
    """All campaigns for a tenant, deterministically ordered (backstop:
    `created_at DESC, id` tiebreak so equal-timestamp campaigns never
    reorder between reads)."""
    result = await db.execute(
        select(Campaign).where(Campaign.tenant_id == tenant_id).order_by(Campaign.created_at.desc(), Campaign.id)
    )
    return list(result.scalars().all())
