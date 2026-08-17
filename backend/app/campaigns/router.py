"""Campaign API routes (Phase 38 -- CAMP-01/CAMP-04)."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.audit import audit
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.campaigns.models import Campaign
from app.campaigns.schemas import (
    CampaignCreateRequest,
    CampaignCreateResponse,
    CampaignDetail,
    CampaignSummary,
)
from app.campaigns.service import get_campaign_progress, get_or_create_campaign, list_campaigns
from app.dependencies import DBSession

router = APIRouter()


def _derive_status(campaign: Campaign, progress: dict[str, int]) -> Literal["ACTIVE", "COMPLETE"]:
    """ACTIVE/COMPLETE display status, derived fresh on every read (D-07) --
    never stored. A persisted `closed_at` (set only by a manual close, Plan
    03) always wins; otherwise 100%-remediated with at least one member
    reads as COMPLETE.

    Pitfall 5: `progress["total"] > 0` is load-bearing -- without it a
    zero-member campaign's `done == total` (`0 == 0`) would misread as
    COMPLETE ("0/0 is not 100%").
    """
    if campaign.closed_at is not None:
        return "COMPLETE"
    if progress["total"] > 0 and progress["done"] == progress["total"]:
        return "COMPLETE"
    return "ACTIVE"


async def _get_campaign_or_404(db: DBSession, tenant_id: uuid.UUID, campaign_id: uuid.UUID) -> Campaign:
    """T-38-01 (IDOR): tenant scoping belongs IN the WHERE clause, not a
    post-fetch filter -- a cross-tenant campaign_id must 404, never a
    fetch-then-403 (existence stays private, matching the codebase's
    existing cross-tenant convention, e.g. `asset-groups`)."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("", response_model=CampaignCreateResponse)
async def create_campaign(
    body: CampaignCreateRequest,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
) -> CampaignCreateResponse:
    """D-11 get-or-create: launching a campaign on a remediation_id with an
    existing ACTIVE campaign opens it (`already_existed=true`, no duplicate
    row, no second audit row) instead of creating a duplicate. D-15: a
    `campaign.create` audit row is written ONLY when a genuinely new row is
    created."""
    campaign, is_new = await get_or_create_campaign(db, user.tenant_id, body.remediation_id, user.id)
    if is_new:
        await audit(db, user, "campaign.create", "campaign", str(campaign.id), {"remediation_id": body.remediation_id})
    await db.commit()
    return CampaignCreateResponse(id=campaign.id, remediation_id=campaign.remediation_id, already_existed=not is_new)


@router.get("", response_model=list[CampaignSummary])
async def campaigns_list(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> list[CampaignSummary]:
    """List every campaign for the caller's tenant with a live progress
    snapshot per row (D-07). Deterministic ordering (`created_at DESC, id`)
    is `list_campaigns`'s job."""
    campaigns = await list_campaigns(db, user.tenant_id)
    summaries: list[CampaignSummary] = []
    for campaign in campaigns:
        progress = await get_campaign_progress(db, user.tenant_id, campaign.remediation_id)
        summaries.append(
            CampaignSummary(
                id=campaign.id,
                remediation_id=campaign.remediation_id,
                status=_derive_status(campaign, progress),
                **progress,
            )
        )
    return summaries


@router.get("/{campaign_id}", response_model=CampaignDetail)
async def campaign_detail(
    campaign_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> CampaignDetail:
    """Single-campaign read with a live progress snapshot. Tenant-scoped
    404 (T-38-01) -- never leaks whether a campaign_id exists in another
    tenant."""
    campaign = await _get_campaign_or_404(db, user.tenant_id, campaign_id)
    progress = await get_campaign_progress(db, user.tenant_id, campaign.remediation_id)
    return CampaignDetail(
        id=campaign.id,
        remediation_id=campaign.remediation_id,
        status=_derive_status(campaign, progress),
        **progress,
    )
