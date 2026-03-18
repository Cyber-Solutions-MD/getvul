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
    created_at: datetime
    updated_at: datetime
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
    open_vuln_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    exploitable_count: int = 0
    kev_count: int = 0

    model_config = {"from_attributes": True}


class AssetFilter(BaseModel):
    hostname: str | None = None
    os_name: str | None = None
    asset_type: str | None = None
    cloud_provider: str | None = None
    source: str | None = Field(None, description="Filter by scanner source")
    risk_score_min: int | None = Field(None, ge=0, le=100)
    search: str | None = None
