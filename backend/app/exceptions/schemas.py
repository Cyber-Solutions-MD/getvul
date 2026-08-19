"""Pydantic schemas for exception endpoints (Phase 39 Plan 01 --
EXC-01/EXC-02/EXC-03/EXC-04 tracer slice).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExceptionCreate(BaseModel):
    """Grant-exception request body (EXC-01 / D-06 / D-07 / D-08).

    `extra="forbid"` is a deliberate mass-assignment defense (T-39-06),
    mirroring `CampaignCreateRequest` / `ticketing/schemas.py`'s
    `TicketCreateRequest` convention. Justification, approver, scope, and
    expiry are ALL mandatory (D-06) -- no optional-approver, no
    optional-expiry, for either exception type.

    `approver_user_id` is REQUIRED at this API boundary even though the DB
    column is nullable (D-08 x Pitfall 3 -- an app-level rule, not a DB
    constraint, so a later approver-user deletion can still SET NULL
    without an IntegrityError). `granted_by_user_id` is deliberately absent
    here -- it is always server-derived from `CurrentUser.id`, never
    client-supplied (T-39-06 mass-assignment defense).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["FALSE_POSITIVE", "ACCEPTED_RISK"]
    scope_type: Literal["FINDING", "ASSET", "ASSET_GROUP"]
    vulnerability_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    asset_group_id: uuid.UUID | None = None
    justification: str = Field(..., min_length=1, max_length=1000)
    approver_user_id: uuid.UUID
    expires_at: datetime


class ExceptionResponse(BaseModel):
    """A single exception row -- every persisted column plus the
    `approver_display_name` derived field (D-08; resolved via a batched
    lookup in `router.py`'s list handler, mirroring the `corr_by_key`
    batched-lookup precedent in `vulnerabilities/service.py:217-240`).

    Deliberately does NOT include a pre-formatted `target` label: Plan 01
    only implements FINDING-scope resolution end-to-end (ASSET/ASSET_GROUP
    grants 400 here and land in Plan 02) -- the raw `scope_type` /
    `cve_id` / `vulnerability_id` / `asset_id` / `asset_group_id` fields
    below are what the frontend list plan (deferred to `/gsd-ui-phase` per
    39-CONTEXT.md) needs to format a target string once all three scopes
    are resolvable; inventing that formatting now, ahead of ASSET/
    ASSET_GROUP resolution, would be untestable dead branches in a tracer
    plan whose stated goal is minimum blast radius.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: Literal["FALSE_POSITIVE", "ACCEPTED_RISK"]
    scope_type: Literal["FINDING", "ASSET", "ASSET_GROUP"]
    cve_id: str
    vulnerability_id: uuid.UUID | None
    asset_id: uuid.UUID | None
    asset_group_id: uuid.UUID | None
    justification: str
    approver_user_id: uuid.UUID | None
    approver_display_name: str | None = None
    granted_by_user_id: uuid.UUID | None
    expires_at: datetime
    revoked_at: datetime | None
    revoked_by_user_id: uuid.UUID | None
    resurfaced_audited_at: datetime | None
    created_at: datetime
