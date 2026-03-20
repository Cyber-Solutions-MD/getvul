"""Pydantic schemas for ticketing endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Ticket responses ──

class TicketResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    vulnerability_id: uuid.UUID
    provider: str
    external_ticket_id: str
    external_ticket_url: str
    external_status: str | None
    project_key: str | None
    assignee: str | None
    created_by_user_id: uuid.UUID | None
    detected_at: datetime | None
    ticket_created_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Joined fields
    cve_id: str | None = None
    severity: str | None = None
    hostname: str | None = None

    model_config = {"from_attributes": True}


class TicketSummary(BaseModel):
    id: uuid.UUID
    provider: str
    external_ticket_id: str
    external_ticket_url: str
    external_status: str | None
    assignee: str | None
    cve_id: str | None
    severity: str | None
    hostname: str | None
    ticket_created_at: datetime | None


# ── Ticket requests ──

class TicketCreateRequest(BaseModel):
    vulnerability_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)
    provider: str = Field(..., pattern="^(ASANA|JIRA|GITHUB)$")
    project_key: str = Field("", description="Asana project GID or Jira project key")
    assignee: str | None = Field(None, description="Email or user ID to assign the ticket to")
    due_days: int | None = Field(None, ge=1, le=365, description="Days from now for due date")


class HostTicketCreateRequest(BaseModel):
    asset_id: uuid.UUID = Field(..., description="Asset ID to create the ticket for")
    provider: str = Field(..., pattern="^(ASANA|JIRA|GITHUB)$")
    project_key: str = Field("", description="Asana project GID")
    assignee: str | None = Field(None, description="Email to assign the ticket to (auto-detected if empty)")
    due_days: int | None = Field(None, ge=1, le=365)


# ── Asana config ──

class AsanaConfigResponse(BaseModel):
    workspace_gid: str | None
    workspace_name: str | None
    project_gid: str | None
    project_name: str | None
    workspaces: list[dict] = []
    projects: list[dict] = []


class AsanaConfigUpdate(BaseModel):
    workspace_gid: str | None = None
    project_gid: str | None = None


# ── Ticket Rules ──

class TicketRuleConditions(BaseModel):
    device_category: list[str] | None = None
    min_risk_score: int | None = None
    severity: list[str] | None = None
    exploit_available: bool | None = None
    cisa_kev: bool | None = None
    min_critical_vulns: int | None = None
    min_high_vulns: int | None = None
    scanner: list[str] | None = None


class TicketRuleAction(BaseModel):
    provider: str = "ASANA"
    project_key: str = ""
    auto_assign: bool = True
    due_days: int | None = None
    ticket_mode: str = Field("per_host", pattern="^(per_host|per_remediation)$")
    assignee_email: str | None = None  # Fixed assignee for per_remediation mode
    max_tickets: int = Field(10, ge=1, le=500)  # Max tickets per rule run


class TicketRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    conditions: TicketRuleConditions
    action: TicketRuleAction
    schedule_minutes: int = Field(1440, ge=1, le=43200)  # 1 min to 30 days
    is_enabled: bool = True
    saved_filter_id: str | None = None


class TicketRuleUpdate(BaseModel):
    name: str | None = None
    conditions: TicketRuleConditions | None = None
    action: TicketRuleAction | None = None
    schedule_minutes: int | None = Field(None, ge=1, le=43200)
    is_enabled: bool | None = None


class TicketRuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_enabled: bool
    conditions: dict
    action: dict
    saved_filter_id: uuid.UUID | None = None
    schedule_minutes: int
    last_run_at: datetime | None
    last_run_status: str | None
    last_run_tickets_created: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Stats ──

class TicketStats(BaseModel):
    total: int
    open: int
    resolved: int
    by_provider: dict[str, int]
    by_severity: dict[str, int]
