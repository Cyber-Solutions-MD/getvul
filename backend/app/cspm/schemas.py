"""Pydantic schemas for CSPM endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MisconfigSummary(BaseModel):
    id: uuid.UUID
    rule_id: str
    rule_name: str
    category: str
    severity: str
    source: str
    status: str
    resource_id: str
    resource_name: str | None
    resource_type: str | None
    cloud_provider: str | None
    first_detected_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class MisconfigResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    rule_id: str
    rule_name: str
    rule_description: str | None
    category: str
    severity: str
    frameworks: list | None
    resource_id: str
    resource_name: str | None
    resource_type: str | None
    resource_region: str | None
    cloud_provider: str | None
    cloud_account_id: str | None
    cloud_account_name: str | None
    source: str
    source_finding_id: str | None
    remediation_info: str | None
    remediation_url: str | None
    status: str
    first_detected_at: datetime
    last_seen_at: datetime
    remediated_at: datetime | None
    details: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MisconfigFilter(BaseModel):
    severity: list[str] | None = None
    source: list[str] | None = None
    status: list[str] | None = None
    category: list[str] | None = None
    cloud_provider: str | None = None
    resource_type: str | None = None
    search: str | None = None


class MisconfigStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|REMEDIATED|SUPPRESSED|FALSE_POSITIVE)$")


class BulkMisconfigStatusUpdate(BaseModel):
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|REMEDIATED|SUPPRESSED|FALSE_POSITIVE)$")


class CategoryCount(BaseModel):
    category: str
    count: int


class SeverityCount(BaseModel):
    severity: str
    count: int


class SourceCount(BaseModel):
    source: str
    count: int


class CSPMDashboardStats(BaseModel):
    total_findings: int
    open_findings: int
    by_severity: list[SeverityCount]
    by_category: list[CategoryCount]
    by_source: list[SourceCount]
    by_cloud_provider: list[dict]
    compliance_pass_rate: float | None = None
