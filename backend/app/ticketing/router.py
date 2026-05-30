"""Ticketing API routes — create tickets, list, sync status."""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_analyst
from app.auth.schemas import CurrentUser
from app.db.session import get_db
from app.ticketing.asana_client import AsanaClient
from app.ticketing.schemas import (
    AsanaConfigResponse,
    AsanaConfigUpdate,
    HostTicketCreateRequest,
    TicketCreateRequest,
    TicketRuleCreate,
    TicketRuleResponse,
    TicketRuleUpdate,
)
from app.ticketing.service import (
    close_ticket,
    create_host_ticket,
    create_tickets,
    get_ticket_stats,
    list_tickets,
    sync_ticket_status,
)

router = APIRouter()


def _get_asana_config(db_config: dict) -> tuple[str | None, str | None, str | None]:
    """Extract Asana settings from tenant connector config."""
    asana = db_config.get("asana", {})
    return (
        asana.get("access_token"),
        asana.get("workspace_gid"),
        asana.get("project_gid"),
    )


async def _get_asana_client(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> tuple[AsanaClient, str, str]:
    """Get an AsanaClient from the ASANA connector config. Does NOT require workspace to be set."""
    from sqlalchemy import select

    from app.connectors.service import get_decrypted_credentials
    from app.ticketing.models import ConnectorConfig

    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.tenant_id == tenant_id,
            ConnectorConfig.connector_type == "ASANA",
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(400, "No Asana connector configured. Add one in Connectors page.")

    creds = get_decrypted_credentials(connector)
    token = creds.get("access_token", "")
    if not token:
        raise HTTPException(400, "Asana connector has no access token configured.")

    config = connector.config or {}
    workspace_gid = config.get("workspace_gid", "")
    project_gid = config.get("project_gid", "")

    return AsanaClient(token), workspace_gid, project_gid


async def _get_asana_client_from_connector(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> tuple[AsanaClient, str, str]:
    """Get an AsanaClient and REQUIRE workspace to be configured."""
    client, workspace_gid, project_gid = await _get_asana_client(db, tenant_id)
    if not workspace_gid:
        await client.close()
        raise HTTPException(400, "Asana workspace not configured. Go to Tickets → Asana Settings.")
    return client, workspace_gid, project_gid


# ── Tickets CRUD ──


@router.get("")
async def list_all_tickets(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
    provider: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    asset_id: uuid.UUID | None = Query(
        None,
        description="Filter tickets to those whose vulnerabilities belong to this asset (uuid)",
    ),
):
    """List all tickets with filtering and pagination.

    Phase 12 / UX-04-02: when ``asset_id`` is provided, the response is
    narrowed to tickets whose linked vulnerability is on the given asset —
    the asset detail page's remediation-timeline rail uses this to fetch
    in a single round-trip. Typed as ``uuid.UUID`` so FastAPI returns 422
    on malformed input instead of letting it surface as a 500 from the DB
    layer (BL-02).
    """
    return await list_tickets(db, user.tenant_id, provider, status, page, page_size, asset_id)


@router.get("/assignees")
async def list_assignees(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List available assignees — users with Humaans emails from enriched assets."""
    from sqlalchemy import select

    from app.assets.models import Asset

    email_col = Asset.mdm_details["humaans_email"].astext
    result = await db.execute(
        select(
            Asset.assigned_user,
            email_col.label("email"),
        )
        .where(
            Asset.tenant_id == user.tenant_id,
            Asset.assigned_user.isnot(None),
            email_col != "",
            email_col.isnot(None),
        )
        .group_by(Asset.assigned_user, email_col)
        .order_by(Asset.assigned_user)
    )
    return [{"name": r.assigned_user, "email": r.email} for r in result.all() if r.email]


@router.get("/stats")
async def ticket_stats(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get ticket statistics."""
    return await get_ticket_stats(db, user.tenant_id)


@router.post("")
async def create_new_tickets(
    body: TicketCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Create tickets for one or more vulnerabilities."""
    asana_client, workspace_gid, default_project = await _get_asana_client_from_connector(db, user.tenant_id)

    try:
        # Use the project from request, or fall back to default configured project
        if not body.project_key and default_project:
            body.project_key = default_project

        if not body.project_key:
            raise HTTPException(400, "No project specified and no default project configured.")

        tickets = await create_tickets(
            db=db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            request=body,
            asana_client=asana_client,
            workspace_gid=workspace_gid,
        )
        await db.commit()
        from app.audit import audit as _audit

        await _audit(db, user, "ticket.create", "ticket", None, {"count": len(tickets), "provider": body.provider})
        return {"created": len(tickets), "tickets": tickets}
    finally:
        await asana_client.close()


@router.post("/host")
async def create_host_remediation_ticket(
    body: HostTicketCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Create a single ticket for a host with all its remediations grouped."""
    asana_client, workspace_gid, default_project = await _get_asana_client_from_connector(db, user.tenant_id)

    try:
        if not body.project_key and default_project:
            body.project_key = default_project
        if not body.project_key:
            raise HTTPException(400, "No project specified and no default project configured.")

        result = await create_host_ticket(
            db=db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            request=body,
            asana_client=asana_client,
            workspace_gid=workspace_gid,
        )
        if "error" in result:
            raise HTTPException(400, result["error"])

        await db.commit()
        return result
    finally:
        await asana_client.close()


@router.post("/sync-status")
async def sync_all_ticket_statuses(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Sync ticket statuses from Asana back to GetVul."""
    asana_client, _, _ = await _get_asana_client_from_connector(db, user.tenant_id)
    try:
        result = await sync_ticket_status(db, user.tenant_id, asana_client)
        await db.commit()
        return result
    finally:
        await asana_client.close()


@router.post("/bulk-action")
async def bulk_ticket_action(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Bulk action on tickets: close, comment, sync-update, or delete."""
    urls = body.get("ticket_urls", [])
    action = body.get("action", "")
    comment_text = body.get("comment", "")

    if not urls:
        raise HTTPException(400, "No tickets selected")

    from sqlalchemy import select

    from app.ticketing.models import Ticket
    from app.ticketing.service import close_ticket
    from app.vulnerabilities.models import Vulnerability

    results = {"processed": 0, "errors": 0}

    if action == "close":
        asana_client, _, _ = await _get_asana_client_from_connector(db, user.tenant_id)
        try:
            for url in urls:
                result = await close_ticket(db, user.tenant_id, url, asana_client)
                if "error" in result:
                    results["errors"] += 1
                else:
                    results["processed"] += 1
            await db.commit()
        finally:
            await asana_client.close()

    elif action == "comment":
        if not comment_text:
            raise HTTPException(400, "Comment text is required")
        asana_client, _, _ = await _get_asana_client_from_connector(db, user.tenant_id)
        try:
            seen_tasks: set[str] = set()
            for url in urls:
                tickets = (
                    (
                        await db.execute(
                            select(Ticket).where(Ticket.external_ticket_url == url, Ticket.tenant_id == user.tenant_id)
                        )
                    )
                    .scalars()
                    .all()
                )
                for t in tickets:
                    task_gid = t.external_ticket_id.split(":")[0]
                    if task_gid not in seen_tasks:
                        ok = await asana_client.add_comment(task_gid, comment_text)
                        seen_tasks.add(task_gid)
                        if ok:
                            results["processed"] += 1
                        else:
                            results["errors"] += 1
                    break
        finally:
            await asana_client.close()

    elif action == "sync-update":
        asana_client, _, _ = await _get_asana_client_from_connector(db, user.tenant_id)
        try:
            from app.ticketing.service import sync_ticket_status

            result = await sync_ticket_status(db, user.tenant_id, asana_client)
            await db.commit()
            results = result
        finally:
            await asana_client.close()

    elif action == "delete":
        asana_client, _, _ = await _get_asana_client_from_connector(db, user.tenant_id)
        try:
            deleted_tasks: set[str] = set()
            for url in urls:
                tickets = (
                    (
                        await db.execute(
                            select(Ticket).where(Ticket.external_ticket_url == url, Ticket.tenant_id == user.tenant_id)
                        )
                    )
                    .scalars()
                    .all()
                )
                for t in tickets:
                    # Delete Asana task (once per unique task)
                    task_gid = t.external_ticket_id.split(":")[0]
                    if task_gid not in deleted_tasks:
                        with contextlib.suppress(Exception):
                            await asana_client.client.delete(f"/tasks/{task_gid}")
                        deleted_tasks.add(task_gid)
                    # Reopen vulns that were changed by this ticket
                    vuln = (
                        await db.execute(select(Vulnerability).where(Vulnerability.id == t.vulnerability_id))
                    ).scalar_one_or_none()
                    if vuln and vuln.status in ("IN_PROGRESS", "REMEDIATED"):
                        vuln.status = "OPEN"
                        vuln.remediated_at = None
                    await db.delete(t)
                results["processed"] += 1

            # Recompute risk scores
            from app.assets.risk_score import compute_risk_scores

            await compute_risk_scores(db, user.tenant_id)
            await db.commit()
        finally:
            await asana_client.close()

    else:
        raise HTTPException(400, f"Unknown action: {action}")

    return results


@router.post("/close")
async def close_ticket_endpoint(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Manually close a ticket — completes the Asana task and resolves vulns."""
    url = body.get("external_ticket_url", "")
    if not url:
        raise HTTPException(400, "external_ticket_url is required")

    asana_client, _, _ = await _get_asana_client_from_connector(db, user.tenant_id)
    try:
        result = await close_ticket(db, user.tenant_id, url, asana_client)
        if "error" in result:
            raise HTTPException(404, result["error"])
        await db.commit()
        return result
    finally:
        await asana_client.close()


# ── Asana configuration ──


@router.get("/asana/config")
async def get_asana_config(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Fast check: returns current Asana config from DB only (no API calls)."""
    from sqlalchemy import select as sel

    from app.ticketing.models import ConnectorConfig as ConnConfig

    result = await db.execute(
        sel(ConnConfig).where(ConnConfig.tenant_id == user.tenant_id, ConnConfig.connector_type == "ASANA")
    )
    connector = result.scalar_one_or_none()
    if not connector:
        return {"configured": False, "workspace_gid": None, "project_gid": None}

    config = connector.config or {}
    return {
        "configured": True,
        "workspace_gid": config.get("workspace_gid", ""),
        "project_gid": config.get("project_gid", ""),
    }


@router.get("/asana/setup")
async def get_asana_setup(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Full setup: fetches workspaces and projects from Asana API (slow)."""
    try:
        asana_client, workspace_gid, project_gid = await _get_asana_client(db, user.tenant_id)
    except HTTPException:
        return AsanaConfigResponse(
            workspace_gid=None,
            workspace_name=None,
            project_gid=None,
            project_name=None,
        )

    try:
        test = await asana_client.test_connection()
        workspaces = test.get("workspaces", [])

        projects = []
        workspace_name = None
        project_name = None

        if workspace_gid:
            projects = await asana_client.list_projects(workspace_gid)
            for w in workspaces:
                if w["gid"] == workspace_gid:
                    workspace_name = w["name"]
                    break
            for p in projects:
                if p["gid"] == project_gid:
                    project_name = p["name"]
                    break

        return AsanaConfigResponse(
            workspace_gid=workspace_gid,
            workspace_name=workspace_name,
            project_gid=project_gid,
            project_name=project_name,
            workspaces=workspaces,
            projects=projects,
        )
    finally:
        await asana_client.close()


@router.patch("/asana/config")
async def update_asana_config(
    body: AsanaConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Update the Asana workspace/project selection on the connector."""
    from sqlalchemy import select

    from app.ticketing.models import ConnectorConfig

    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.tenant_id == user.tenant_id,
            ConnectorConfig.connector_type == "ASANA",
        )
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(400, "No Asana connector configured.")

    config = dict(connector.config or {})
    if body.workspace_gid is not None:
        config["workspace_gid"] = body.workspace_gid
    if body.project_gid is not None:
        config["project_gid"] = body.project_gid
    connector.config = config

    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(connector, "config")
    await db.commit()

    return {"message": "Asana config updated", "config": config}


# ── Ticket Rules ──


@router.get("/rules")
async def list_rules(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all ticket rules."""
    from sqlalchemy import select

    from app.ticketing.models import TicketRule

    result = await db.execute(
        select(TicketRule).where(TicketRule.tenant_id == user.tenant_id).order_by(TicketRule.created_at.desc())
    )
    rules = result.scalars().all()
    return [TicketRuleResponse.model_validate(r) for r in rules]


@router.post("/rules")
async def create_rule(
    body: TicketRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Create a new ticket rule."""
    import uuid as _uuid

    from app.ticketing.models import TicketRule

    rule = TicketRule(
        tenant_id=user.tenant_id,
        name=body.name,
        is_enabled=body.is_enabled,
        conditions=body.conditions.model_dump(exclude_none=True),
        action=body.action.model_dump(exclude_none=True),
        saved_filter_id=_uuid.UUID(body.saved_filter_id) if body.saved_filter_id else None,
        schedule_minutes=body.schedule_minutes,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    await db.commit()
    return TicketRuleResponse.model_validate(rule)


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID,
    body: TicketRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Update a ticket rule."""
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from app.ticketing.models import TicketRule

    result = await db.execute(
        select(TicketRule).where(TicketRule.id == rule_id, TicketRule.tenant_id == user.tenant_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")

    if body.name is not None:
        rule.name = body.name
    if body.is_enabled is not None:
        rule.is_enabled = body.is_enabled
    if body.conditions is not None:
        rule.conditions = body.conditions.model_dump(exclude_none=True)
        flag_modified(rule, "conditions")
    if body.action is not None:
        rule.action = body.action.model_dump(exclude_none=True)
        flag_modified(rule, "action")
    if body.schedule_minutes is not None:
        rule.schedule_minutes = body.schedule_minutes

    await db.commit()
    return TicketRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Delete a ticket rule."""
    from sqlalchemy import select

    from app.ticketing.models import TicketRule

    result = await db.execute(
        select(TicketRule).where(TicketRule.id == rule_id, TicketRule.tenant_id == user.tenant_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"message": "Rule deleted"}


@router.post("/rules/{rule_id}/run")
async def run_rule_now(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Run a rule immediately (manual trigger)."""
    from sqlalchemy import select

    from app.ticketing.models import TicketRule
    from app.ticketing.rule_engine import run_rule

    result = await db.execute(
        select(TicketRule).where(TicketRule.id == rule_id, TicketRule.tenant_id == user.tenant_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")

    asana_client, workspace_gid, project_gid = await _get_asana_client_from_connector(db, user.tenant_id)
    try:
        run_result = await run_rule(db, rule, asana_client, workspace_gid, project_gid)
        from datetime import datetime

        rule.last_run_at = datetime.now(UTC)
        rule.last_run_status = "SUCCESS"
        rule.last_run_tickets_created = run_result["created"]
        await db.commit()
        return run_result
    finally:
        await asana_client.close()


@router.post("/sync-status")
async def trigger_ticket_sync(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Manually trigger ticket status sync — checks all open tickets and posts progress comments."""
    from app.ticketing.daily_sync import run_daily_ticket_sync

    result = await run_daily_ticket_sync(db)
    from app.audit import audit

    await audit(db, user, "ticket.sync_status", "ticket", None, result)
    await db.commit()
    return result
