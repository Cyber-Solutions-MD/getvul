"""Pydantic schemas for vulnerability endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ── Responses ──


class VulnerabilityResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    cve_id: str | None
    vulnerability_name: str | None
    cvss_v3_score: Decimal | None
    cvss_v3_vector: str | None
    severity: str
    epss_score: Decimal | None
    exploit_available: bool
    cisa_kev: bool
    asset_id: uuid.UUID | None
    source: str
    source_vuln_id: str | None
    affected_product: str | None
    affected_version: str | None
    fixed_version: str | None
    remediation_id: str | None = None
    remediation_action: str | None = None
    exploit_status_id: int | None = None
    exploit_status_name: str | None = None
    remediation_info: str | None
    status: str
    first_detected_at: datetime
    last_seen_at: datetime
    remediated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Joined fields (optional, populated on detail view)
    asset_hostname: str | None = None
    correlation_sources_count: int | None = None

    model_config = {"from_attributes": True}


class VulnerabilitySummary(BaseModel):
    """Lightweight vuln for list views."""

    id: uuid.UUID
    cve_id: str | None
    severity: str
    source: str
    status: str
    exploit_available: bool
    cisa_kev: bool
    affected_product: str | None
    asset_id: uuid.UUID | None
    asset_hostname: str | None = None
    first_detected_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


# ── Filters ──


class VulnerabilityFilter(BaseModel):
    """Filter parameters for vulnerability queries."""

    severity: list[str] | None = None
    source: list[str] | None = None
    status: list[str] | None = None
    cve_id: str | None = None
    exploit_available: bool | None = None
    cisa_kev: bool | None = None
    asset_id: uuid.UUID | None = None
    search: str | None = Field(None, description="Search CVE ID or product name")
    age_days_min: int | None = Field(None, ge=0)
    age_days_max: int | None = Field(None, ge=0)
    # Phase 10 / D-T-01: 'triage' opts in to KEV → CVSS desc → SLA-due asc.
    # Default (None) preserves existing severity-case-then-last_seen ordering.
    sort: Literal["triage", "severity"] | None = None


# ── Requests ──


class VulnerabilityStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|REMEDIATED|SUPPRESSED|FALSE_POSITIVE)$")


class BulkStatusUpdate(BaseModel):
    vulnerability_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|REMEDIATED|SUPPRESSED|FALSE_POSITIVE)$")


# ── Dashboard Stats ──


class SeverityCount(BaseModel):
    severity: str
    count: int


class SourceCount(BaseModel):
    source: str
    count: int


class TileValue(BaseModel):
    """One tile in the Phase 10 dashboard StatStrip.

    Warning-6 fix: `value` is `int | str` because the `mttr_30d` tile is
    formatted server-side as e.g. "4.2d" while critical_open / sla_at_risk
    / kev are integers. Frontend TS type is `number | string`.
    """

    value: int | str
    delta: int | None = None
    delta_direction: Literal["up", "down", "flat"] | None = None


class DashboardTiles(BaseModel):
    """The 4 tiles rendered in the StatStrip per D-S-01..04."""

    critical_open: TileValue
    sla_at_risk: TileValue
    kev: TileValue
    mttr_30d: TileValue


class TopVuln(BaseModel):
    """Highest-CVSS OPEN CRITICAL row for the Hero per D-B-02 / D-H-03.

    Blocker-2 fix: `id` (UUID) is required so the frontend Hero CTA can
    fire POST /vulnerabilities/{id}/snooze and /unsnooze. `cve_id` is the
    human-facing label; `id` is the IDOR-safe primary key.
    """

    id: uuid.UUID
    cve_id: str | None = None
    host: str | None = None
    path: str | None = None
    cvss: Decimal | None = None
    on_kev: bool = False
    exploited: bool = False


class DashboardStats(BaseModel):
    total_vulnerabilities: int
    open_vulnerabilities: int
    by_severity: list[SeverityCount]
    by_source: list[SourceCount]
    exploitable_count: int
    cisa_kev_count: int
    correlated_cves: int
    mttr_days: float | None = None
    # ── Phase 10 additive extensions (D-B-02 / D-O-01) ──
    dashboard_tiles: DashboardTiles | None = None
    top_vuln: TopVuln | None = None
    vuln_open_count: int = 0
    asset_total_count: int = 0
    ticket_open_count: int = 0
    onboarding_state: Literal["no_scanners", "no_data_yet", "ready"] = "no_scanners"
