"""Campaign API routes (Phase 38 -- CAMP-01/CAMP-02/CAMP-04)."""

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
    CampaignBulkAssignRequest,
    CampaignCreateRequest,
    CampaignCreateResponse,
    CampaignDetail,
    CampaignSummary,
)
from app.campaigns.service import (
    bulk_create_campaign_tickets,
    get_campaign_mttr,
    get_campaign_progress,
    get_or_create_campaign,
    list_campaigns,
)
from app.dependencies import DBSession
from app.ticketing.dispatch import TicketingClient, build_ticketing_client
from app.ticketing.providers import TicketProvider

router = APIRouter()

# Mirrors ticketing/router.py's `_PROVIDER_PROJECT_FIELD` -- which config key
# a request-supplied project routes to per provider. GitHub has no
# per-request project concept (owner/repo is fixed on the connector's own
# config), so it is deliberately absent here.
_PROVIDER_PROJECT_FIELD = {
    TicketProvider.ASANA: "project_gid",
    TicketProvider.JIRA: "project_key",
}


async def _get_campaign_ticketing_client(
    db: DBSession, tenant_id: uuid.UUID, provider: str, project_key: str
) -> TicketingClient:
    """Resolve a tenant-scoped dispatched client for `provider` (D-08's
    "existing dispatch pattern" reuse), mirroring
    `ticketing/router.py::_get_ticketing_client`'s tenant-scoped
    `ConnectorConfig` lookup + Fernet-decrypt + `build_ticketing_client`
    shape. Kept local to this router (not imported cross-router) since
    `project_key` here is always caller-supplied, never a fallback to the
    connector's own configured project.
    """
    from app.connectors.service import get_decrypted_credentials
    from app.ticketing.models import ConnectorConfig

    provider_enum = TicketProvider(provider)

    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.tenant_id == tenant_id,
            ConnectorConfig.connector_type == provider_enum.value,
            ConnectorConfig.is_enabled.is_(True),
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(400, f"No {provider_enum.value.title()} connector configured. Add one in Connectors page.")

    creds = get_decrypted_credentials(connector)
    config = dict(connector.config or {})
    project_field = _PROVIDER_PROJECT_FIELD.get(provider_enum)
    if project_field:
        config[project_field] = project_key

    return build_ticketing_client(provider_enum, creds, config)


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
    mttr_seconds = await get_campaign_mttr(db, user.tenant_id, campaign.remediation_id)
    return CampaignDetail(
        id=campaign.id,
        remediation_id=campaign.remediation_id,
        status=_derive_status(campaign, progress),
        mttr_seconds=mttr_seconds,
        **progress,
    )


@router.post("/{campaign_id}/bulk-assign")
async def bulk_assign_campaign(
    campaign_id: uuid.UUID,
    body: CampaignBulkAssignRequest,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
) -> dict[str, int | list[str | None]]:
    """CAMP-02: one ticket per owner covering that owner's live campaign
    members, reusing the existing owner-routing + dedup-by-URL logic
    verbatim (D-05/D-06/D-08). D-10: a `campaign.bulk_assign` audit row is
    written on EVERY run -- including a no-op re-run that tickets nobody --
    never gated on `result["created_tickets"] > 0`."""
    campaign = await _get_campaign_or_404(db, user.tenant_id, campaign_id)
    client = await _get_campaign_ticketing_client(db, user.tenant_id, body.provider, body.project_key)
    result = await bulk_create_campaign_tickets(
        db, user.tenant_id, user.id, campaign, body.provider, body.project_key, client, body.due_days
    )
    await audit(db, user, "campaign.bulk_assign", "campaign", str(campaign.id), result)
    await db.commit()
    return result
