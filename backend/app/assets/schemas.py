"""Pydantic schemas for asset endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AssetResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    hostname: str | None
    ip_addresses: list | None
    mac_addresses: list | None
    os_name: str | None
    os_version: str | None
    asset_type: str | None
    cloud_provider: str | None
    cloud_resource_id: str | None
    seen_by_sources: list | None
    risk_score: int | None
    device_category: str | None
    serial_number: str | None
    model: str | None
    department: str | None
    building: str | None
    assigned_user: str | None
    managed_by: str | None
    last_checkin_at: datetime | None
    mdm_details: dict | None
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime
    # NOTE (Phase 12): the `vuln_counts` dict shape MUST include an `sla_breach: int` key
    # populated by the list / detail handlers — frontend RiskCard (UX-04-03 row 2) depends on it.
    # Type stays `dict | None` to avoid Pydantic churn at the response edge.
    vuln_counts: dict | None = None

    model_config = {"from_attributes": True}


class AssetSummary(BaseModel):
    id: uuid.UUID
    hostname: str | None
    os_name: str | None
    os_version: str | None
    asset_type: str | None
    cloud_provider: str | None
    seen_by_sources: list | None
    risk_score: int | None
    device_category: str | None
    model: str | None
    assigned_user: str | None
    managed_by: str | None
    open_vuln_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    exploitable_count: int = 0
    kev_count: int = 0
    tags: list[str] | None = None
    sla_breach_count: int = 0

    model_config = {"from_attributes": True}


class AssetFilter(BaseModel):
    hostname: str | None = None
    os_name: str | None = None
    asset_type: str | None = None
    cloud_provider: str | None = None
    source: str | None = None
    risk_score_min: int | None = Field(None, ge=0, le=100)
    device_category: str | None = None
    search: str | None = None
