"""Pydantic schemas for campaign endpoints (Phase 38 -- CAMP-01/CAMP-04)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CampaignCreateRequest(BaseModel):
    """Create/open-campaign request body.

    `extra="forbid"` is a deliberate mass-assignment defense (T-38-02, ASVS
    V5), matching `ticketing/schemas.py:69`'s `TicketCreateRequest`
    convention. `max_length=200` mirrors `Campaign.remediation_id`'s
    `String(200)` column width.
    """

    model_config = ConfigDict(extra="forbid")

    remediation_id: str = Field(..., min_length=1, max_length=200)


class CampaignCreateResponse(BaseModel):
    """D-11 get-or-create result -- `already_existed=true` means this POST
    opened a pre-existing ACTIVE campaign instead of creating a new row (no
    duplicate, no second audit row)."""

    id: uuid.UUID
    remediation_id: str
    already_existed: bool


class CampaignSummary(BaseModel):
    """A campaign list row -- identity + derived status + live compute-on-read
    progress (D-07). No count/percentage/status field here is ever persisted
    verbatim; all are recomputed from a live `vulnerabilities` join on every
    read (`app/campaigns/service.py::get_campaign_progress`)."""

    id: uuid.UUID
    remediation_id: str
    status: Literal["ACTIVE", "COMPLETE"]
    total: int
    open: int
    in_progress: int
    done: int
    pct_remediated: int


class CampaignDetail(CampaignSummary):
    """`CampaignSummary` + Plan 03's live-computed MTTR (D-12). `mttr_seconds`
    is `float | None` -- `None` (never `0`) when no member has ever been
    remediated (Pitfall 5's zero-guard sibling)."""

    mttr_seconds: float | None


class CampaignBulkAssignRequest(BaseModel):
    """Bulk-assign request body (CAMP-02) -- `extra="forbid"` is the same
    mass-assignment defense (T-38-02) as `CampaignCreateRequest`. `provider`
    mirrors `ticketing/schemas.py`'s existing 3-provider pattern verbatim.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(..., pattern="^(ASANA|JIRA|GITHUB)$")
    project_key: str = Field(..., min_length=1, max_length=100)
    due_days: int | None = Field(None, ge=1, le=365)
