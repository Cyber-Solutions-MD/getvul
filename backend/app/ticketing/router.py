"""Ticketing API routes — create tickets, list, sync status."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.auth.dependencies import get_current_user
from app.auth.rbac import require_analyst
from app.auth.schemas import CurrentUser
from app.db.session import get_db
from app.ticketing.asana_client import AsanaClient
from app.ticketing.dispatch import TicketingClient, build_ticketing_client
from app.ticketing.models import Ticket, TicketComment, TicketWatcher
from app.ticketing.providers import TicketProvider
from app.ticketing.schemas import (
    AsanaConfigResponse,
    AsanaConfigUpdate,
    BlockedUpdate,
    CommentCreate,
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


# ── Generalized provider-dispatched client resolution (D-10) ─────────────────
#
# The old workspace-requiring Asana-only connector helper is gone — every
# create/close/sync/bulk/run-now call site below now resolves its client via
# `_get_ticketing_client`, generalized to any provider. `_get_asana_client`
# itself stays (it's used only by the Asana-specific /asana/setup +
# /asana/config settings routes, out of this plan's scope).
#
# Which config key a per-request project override lands on, keyed by
# provider. GitHub has no per-request project concept — its routing
# (owner/repo) is fixed on the connector's own config.
_PROVIDER_PROJECT_FIELD = {
    TicketProvider.ASANA: "project_gid",
    TicketProvider.JIRA: "project_key",
}


async def _get_ticketing_client(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    provider: str,
    project_override: str | None = None,
) -> tuple[TicketingClient, str]:
    """Resolve a tenant-scoped dispatched client for `provider` (D-10).

    Mirrors `_get_asana_client`'s tenant-scoped ConnectorConfig lookup
    (T-23-09: the `tenant_id == user.tenant_id` filter is preserved exactly —
    never a provider-only global lookup) and Fernet-decrypts credentials via
    the existing `get_decrypted_credentials` helper, then builds the
    provider's TicketingClient via `build_ticketing_client`.

    Returns `(client, effective_project_key)` — `effective_project_key` is
    `project_override` if given, else the connector's own configured project
    (empty string for GitHub, which has no per-request project concept).
    Raises the same "not configured" HTTPException shape `_get_asana_client`
    already used, generalized to name the requested provider.
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
    effective_project = project_override or (config.get(project_field, "") if project_field else "")
    if project_field and project_override:
        config[project_field] = project_override

    client = build_ticketing_client(provider_enum, creds, config)
    return client, effective_project


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
    # WR-01: these chip axes were previously accepted by the frontend and
    # silently ignored. They now reach list_tickets and are applied.
    severity: str | None = Query(None, description="Comma-separated severities (critical,high,...)"),
    sla: str | None = Query(None, description="SLA tier: overdue | soon | ok"),
    search: str | None = Query(None, description="Free-text match on ticket id / assignee"),
):
    """List all tickets with filtering and pagination.

    Phase 12 / UX-04-02: when ``asset_id`` is provided, the response is
    narrowed to tickets whose linked vulnerability is on the given asset —
    the asset detail page's remediation-timeline rail uses this to fetch
    in a single round-trip. Typed as ``uuid.UUID`` so FastAPI returns 422
    on malformed input instead of letting it surface as a 500 from the DB
    layer (BL-02).
    """
    return await list_tickets(
        db,
        user.tenant_id,
        provider,
        status,
        page,
        page_size,
        asset_id,
        severity=severity,
        sla=sla,
        search=search,
    )


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


@router.get("/providers")
async def list_configured_providers(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return which ticketing providers are configured+enabled for the
    caller's tenant (D-15). Reused by the Plan 08 provider picker and
    Phase 27's ticket auto-drafting.

    T-23-10 (Information Disclosure) mitigation: filters strictly by
    `user.tenant_id` — returns only provider name + enabled flag, never
    credentials or secret_arn. This static route is declared before the
    `/{ticket_id}` catch-all (FastAPI matches routes in declaration order;
    same reasoning as the existing `/rules` note below).
    """
    from app.ticketing.models import ConnectorConfig

    result = await db.execute(
        select(ConnectorConfig.connector_type, ConnectorConfig.is_enabled).where(
            ConnectorConfig.tenant_id == user.tenant_id,
            ConnectorConfig.connector_type.in_([p.value for p in TicketProvider]),
            ConnectorConfig.is_enabled.is_(True),
        )
    )
    return [{"provider": connector_type, "enabled": is_enabled} for connector_type, is_enabled in result.all()]


@router.post("")
async def create_new_tickets(
    body: TicketCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Create tickets for one or more vulnerabilities — dispatches by
    `body.provider` (D-10): provider:'JIRA' now actually reaches the Jira
    client, fixing the data-integrity bug where every provider silently
    created the ticket in Asana.
    """
    client, default_project = await _get_ticketing_client(db, user.tenant_id, body.provider, body.project_key or None)

    # Use the project from request, or fall back to the connector's default
    # configured project. GitHub has no per-request project concept.
    if not body.project_key and default_project:
        body.project_key = default_project

    if body.provider in (TicketProvider.ASANA, TicketProvider.JIRA) and not body.project_key:
        raise HTTPException(400, "No project specified and no default project configured.")

    tickets = await create_tickets(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        request=body,
        client=client,
    )
    await db.commit()
    from app.audit import audit as _audit

    await _audit(db, user, "ticket.create", "ticket", None, {"count": len(tickets), "provider": body.provider})
    return {"created": len(tickets), "tickets": tickets}


@router.post("/host")
async def create_host_remediation_ticket(
    body: HostTicketCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Create a single ticket for a host with all its remediations grouped —
    dispatches by `body.provider` (D-10)."""
    client, default_project = await _get_ticketing_client(db, user.tenant_id, body.provider, body.project_key or None)

    if not body.project_key and default_project:
        body.project_key = default_project
    if body.provider in (TicketProvider.ASANA, TicketProvider.JIRA) and not body.project_key:
        raise HTTPException(400, "No project specified and no default project configured.")

    result = await create_host_ticket(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        request=body,
        client=client,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])

    await db.commit()
    return result


async def _make_client_resolver(
    db: AsyncSession, tenant_id: uuid.UUID
) -> Callable[[str], Awaitable[TicketingClient | None]]:
    """Build a `client_resolver` for service.py's sync_ticket_status/close_ticket.

    Resolves + caches one dispatched client per provider actually requested,
    tenant-scoped (T-23-09). Returns None (not a raise) for a provider with no
    enabled connector — sync/close treat that as "skip", not a hard failure.
    """
    cache: dict[str, TicketingClient | None] = {}

    async def _resolve(provider: str) -> TicketingClient | None:
        if provider not in cache:
            try:
                client, _project = await _get_ticketing_client(db, tenant_id, provider)
                cache[provider] = client
            except HTTPException:
                cache[provider] = None
        return cache[provider]

    return _resolve


@router.post("/sync-status")
async def sync_all_ticket_statuses(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Sync ticket statuses from each ticket's own provider back to GetVul
    (D-10) — previously always synced against Asana regardless of the
    ticket's persisted provider."""
    resolver = await _make_client_resolver(db, user.tenant_id)
    result = await sync_ticket_status(db, user.tenant_id, resolver)
    await db.commit()
    return result


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
        resolver = await _make_client_resolver(db, user.tenant_id)
        for url in urls:
            result = await close_ticket(db, user.tenant_id, url, resolver)
            if "error" in result:
                results["errors"] += 1
            else:
                results["processed"] += 1
        await db.commit()

    elif action == "comment":
        if not comment_text:
            raise HTTPException(400, "Comment text is required")
        resolver = await _make_client_resolver(db, user.tenant_id)
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
                task_ref = t.external_ticket_id.split(":")[0]
                cache_key = f"{t.provider}:{task_ref}"
                if cache_key not in seen_tasks:
                    provider_client = await resolver(t.provider)
                    seen_tasks.add(cache_key)
                    if provider_client is None:
                        results["errors"] += 1
                    else:
                        await provider_client.comment(task_ref, comment_text)
                        results["processed"] += 1
                break

    elif action == "sync-update":
        resolver = await _make_client_resolver(db, user.tenant_id)
        from app.ticketing.service import sync_ticket_status

        result = await sync_ticket_status(db, user.tenant_id, resolver)
        await db.commit()
        results = result

    elif action == "delete":
        # D-10 deviation: dispatch.py's TicketingClient Protocol has no
        # `delete` verb (only create/get/comment/close) — the prior raw
        # `asana_client.client.delete(f"/tasks/{gid}")` HTTP call was already
        # best-effort (wrapped in contextlib.suppress). Rather than reach
        # around the Protocol for a provider-specific escape hatch, this
        # bulk action now only deletes the local GetVul ticket rows +
        # reopens their vulns; the external ticket is left as-is on its
        # provider. Logged as a deviation, not silently dropped.
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

    elif action in ("block", "unblock"):
        # Bulk block/unblock: group-scoped UPDATE for each provided external_ticket_url.
        # Canonical-group identity (O1): blocked/blocked_reason apply to the WHOLE group
        # (WHERE external_ticket_url = url AND tenant_id = ...), mirroring close_ticket.
        # Audit BEFORE the single commit — fail-closed (AUDIT-01, T-13-10).
        blocked_flag = action == "block"
        blocked_reason = body.get("blocked_reason") if blocked_flag else None

        for url in urls:
            await db.execute(
                update(Ticket)
                .where(
                    Ticket.external_ticket_url == url,
                    Ticket.tenant_id == user.tenant_id,
                )
                .values(blocked=blocked_flag, blocked_reason=blocked_reason)
            )
            audit_action = "ticket.blocked" if blocked_flag else "ticket.unblocked"
            await audit(db, user, audit_action, "ticket", url, {"reason": blocked_reason})
            results["processed"] += 1

        await db.commit()

    else:
        raise HTTPException(400, f"Unknown action: {action}")

    return results


@router.post("/close")
async def close_ticket_endpoint(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Manually close a ticket — dispatches by the ticket's own stored
    provider (D-10) and resolves vulns."""
    url = body.get("external_ticket_url", "")
    if not url:
        raise HTTPException(400, "external_ticket_url is required")

    resolver = await _make_client_resolver(db, user.tenant_id)
    result = await close_ticket(db, user.tenant_id, url, resolver)
    if "error" in result:
        raise HTTPException(404, result["error"])
    await db.commit()
    return result


# ── Canonical-group resolution helper ─────────────────────────────────────────
#
# Canonical identity (O1, RESOLVED): a logical ticket is the group of `tickets`
# rows sharing one `external_ticket_url`. Routes accept `ticket_id: uuid.UUID`
# (BL-02 → malformed UUID yields 422 not 500). The handler resolves {id} →
# its row → its `external_ticket_url`, scoped to `tenant_id`. Cross-tenant
# rows are indistinguishable from missing (IDOR pattern, mirrors snooze_vuln
# T-10-01) → 404.
#
# Returns: (row, external_ticket_url)
# - row: the resolved Ticket row (used for first_ticket_id in comments/watchers)
# - external_ticket_url: the group key (used for blocked/sla group updates)


async def _resolve_group(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> tuple[Ticket, str]:
    """Resolve a ticket_id to its group (external_ticket_url) within a tenant.

    Canonical-group identity rule (O1): returns the Ticket row (used as the
    canonical first_ticket_id for comments/watchers FK) and its external_ticket_url
    (used for group-scoped blocked/sla UPDATEs).

    Cross-tenant IDs are treated as missing (IDOR guard, T-13-08) → 404.
    """
    result = await db.execute(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.tenant_id == tenant_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return row, row.external_ticket_url


# ── Comment routes ─────────────────────────────────────────────────────────────


@router.get("/{ticket_id}/comments")
async def list_ticket_comments(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """List local audit comments for a logical ticket, chronological ascending (D-C-04).

    Canonical identity (O1): resolves {ticket_id} to first_ticket_id within tenant.
    Comments FK to tickets(id) using the canonical first_ticket_id (the MIN row id
    in the group returned by list_tickets). Tenant scope enforced by _resolve_group.
    """
    from app.tenants.models import User

    row, _url = await _resolve_group(db, ticket_id, user.tenant_id)

    # CR-05: LEFT JOIN users so each comment carries user_display_name. Without
    # it the frontend timeline rendered every author as "Unknown". snake_case
    # keys (user_display_name / created_at / edited_at) match the wire convention
    # api() consumes verbatim (no casing transform).
    comments_q = (
        select(TicketComment, User.display_name.label("user_display_name"))
        .outerjoin(User, TicketComment.user_id == User.id)
        .where(TicketComment.ticket_id == row.id)
        .order_by(TicketComment.created_at.asc())
    )
    results = (await db.execute(comments_q)).all()

    return [
        {
            "id": str(c.id),
            "ticket_id": str(c.ticket_id),
            "user_id": str(c.user_id),
            "user_display_name": user_display_name,
            "body": c.body,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "edited_at": c.edited_at.isoformat() if c.edited_at else None,
        }
        for c, user_display_name in results
    ]


@router.post("/{ticket_id}/comments", status_code=201)
async def add_ticket_comment(
    ticket_id: uuid.UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Add a local audit comment to a logical ticket (D-C-01/03).

    Canonical identity (O1): resolves {ticket_id} to first_ticket_id within tenant.
    Comments FK to tickets(id) using the canonical first_ticket_id. Audit-then-commit
    (AUDIT-01): audit() called BEFORE db.commit() — fail-closed.

    Mass-assignment guard (T-13-09): only CommentCreate.body is written to DB.
    """
    row, _url = await _resolve_group(db, ticket_id, user.tenant_id)

    comment = TicketComment(
        ticket_id=row.id,
        user_id=user.id,
        body=body.body,
    )
    db.add(comment)
    await db.flush()

    # Audit BEFORE commit — fail-closed (AUDIT-01, T-13-10)
    await audit(db, user, "ticket.comment_added", "ticket", str(ticket_id), {})
    await db.commit()
    await db.refresh(comment)

    return {
        "id": str(comment.id),
        "ticket_id": str(comment.ticket_id),
        "user_id": str(comment.user_id),
        "body": comment.body,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "edited_at": None,
    }


# ── Blocked route ──────────────────────────────────────────────────────────────


@router.post("/{ticket_id}/blocked")
async def set_ticket_blocked(
    ticket_id: uuid.UUID,
    body: BlockedUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Toggle the blocked state for a logical ticket group (D-P-02).

    Canonical identity (O1): blocked/blocked_reason apply to the WHOLE group
    (UPDATE WHERE external_ticket_url = url AND tenant_id = ...). This mirrors
    how close_ticket already operates on a group.

    Audit-then-commit (AUDIT-01, T-13-10): audit() called BEFORE db.commit().
    Mass-assignment guard (T-13-09): only blocked + blocked_reason written to DB.
    """
    _row, external_ticket_url = await _resolve_group(db, ticket_id, user.tenant_id)

    # Apply to the WHOLE group (canonical-identity rule O1)
    await db.execute(
        update(Ticket)
        .where(
            Ticket.external_ticket_url == external_ticket_url,
            Ticket.tenant_id == user.tenant_id,
        )
        .values(blocked=body.blocked, blocked_reason=body.blocked_reason)
    )

    action = "ticket.blocked" if body.blocked else "ticket.unblocked"
    # Audit BEFORE commit — fail-closed (AUDIT-01, T-13-10)
    await audit(db, user, action, "ticket", str(ticket_id), {"reason": body.blocked_reason})
    await db.commit()

    return {"blocked": body.blocked, "blocked_reason": body.blocked_reason}


# ── Watch routes ──────────────────────────────────────────────────────────────


@router.post("/{ticket_id}/watch")
async def watch_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Subscribe to a logical ticket (D-W-02).

    Idempotent: INSERT ... ON CONFLICT DO NOTHING — always 200 regardless of
    whether the row already existed (D-W-02 no-op semantics, T-13-13).
    Canonical identity (O1): resolves {ticket_id} → canonical first_ticket_id
    within tenant. Audit-then-commit (AUDIT-01).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    row, _url = await _resolve_group(db, ticket_id, user.tenant_id)

    # Idempotent insert — ON CONFLICT (ticket_id, user_id) DO NOTHING (T-13-13)
    stmt = (
        pg_insert(TicketWatcher)
        .values(ticket_id=row.id, user_id=user.id)
        .on_conflict_do_nothing(index_elements=["ticket_id", "user_id"])
    )
    await db.execute(stmt)

    # Audit BEFORE commit — fail-closed (AUDIT-01, T-13-10)
    await audit(db, user, "ticket.watch", "ticket", str(ticket_id), {})
    await db.commit()

    return {"watching": True}


@router.delete("/{ticket_id}/watch")
async def unwatch_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Unsubscribe from a logical ticket (D-W-02).

    Idempotent: delete the watcher row if present; no-op if absent — always 200.
    Canonical identity (O1): resolves to canonical first_ticket_id within tenant.
    Audit-then-commit (AUDIT-01).
    """
    from sqlalchemy import delete as sa_delete

    row, _url = await _resolve_group(db, ticket_id, user.tenant_id)

    # Idempotent delete — no error if row doesn't exist
    await db.execute(
        sa_delete(TicketWatcher).where(
            TicketWatcher.ticket_id == row.id,
            TicketWatcher.user_id == user.id,
        )
    )

    # Audit BEFORE commit — fail-closed (AUDIT-01, T-13-10)
    await audit(db, user, "ticket.unwatch", "ticket", str(ticket_id), {})
    await db.commit()

    return {"watching": False}


# ── Ticket Rules (list) ──
# NOTE: this static route MUST be declared before the /{ticket_id} catch-all
# below. FastAPI matches routes in declaration order — if /{ticket_id} comes
# first, GET /tickets/rules is captured by it and 422s trying to parse "rules"
# as a UUID (uuid_parsing on path param ticket_id).


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


# ── Ticket detail endpoint ────────────────────────────────────────────────────


@router.get("/{ticket_id}")
async def get_ticket_detail(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_analyst),
):
    """Return the resolved logical ticket detail (UX-05-04).

    Canonical identity (O1): resolves {ticket_id} → its external_ticket_url group
    within tenant. Returns:
    - assignee: aggregated from the group (already in list_tickets)
    - reporter (REQUIRED, UX-05-04): the ticket creator from created_by_user_id on the
      resolved Ticket row; falls back to null if not set. Source: Ticket.created_by_user_id.
    - linked_vulns: top vulnerabilities in the group (cve + severity + cvss)
    - watchers: local TicketWatcher rows only (D-PROV-02 — no provider followers in P13).
      Each watcher carries role: "watcher" (D-W-04 injection-point seam); the frontend
      People card (Plan 08) assembles the assignee + reporter + watchers display.
    - blocked, blocked_reason, sla_due_at: bool_or/min over the group.
    """
    from app.assets.models import Asset
    from app.tenants.models import User
    from app.vulnerabilities.models import Vulnerability as Vuln

    row, external_ticket_url = await _resolve_group(db, ticket_id, user.tenant_id)

    # ── Group aggregates ──────────────────────────────────────────────────────
    group_q = select(
        func.min(Ticket.provider).label("provider"),
        func.min(Ticket.external_status).label("external_status"),
        func.min(Ticket.assignee).label("assignee"),
        func.min(Ticket.ticket_created_at).label("ticket_created_at"),
        func.max(Ticket.resolved_at).label("resolved_at"),
        func.count(Ticket.id).label("vuln_count"),
        func.bool_or(Ticket.blocked).label("blocked"),
        func.min(Ticket.blocked_reason).label("blocked_reason"),
        func.min(Ticket.sla_due_at).label("sla_due_at"),
    ).where(
        Ticket.external_ticket_url == external_ticket_url,
        Ticket.tenant_id == user.tenant_id,
    )
    group = (await db.execute(group_q)).first()

    # ── Reporter (UX-05-04) — from created_by_user_id on the resolved row ─────
    # Source: Ticket.created_by_user_id (the user who created the ticket).
    # Falls back to null if not set (People card renders '—').
    reporter_data = None
    if row.created_by_user_id:
        reporter_row = (
            await db.execute(select(User.id, User.display_name, User.email).where(User.id == row.created_by_user_id))
        ).first()
        if reporter_row:
            reporter_data = {
                "userId": str(reporter_row.id),
                "displayName": reporter_row.display_name,
                "email": reporter_row.email,
            }

    # ── Linked vulns (top by severity) ────────────────────────────────────────
    vulns_q = (
        select(
            Vuln.cve_id,
            Vuln.severity,
            Vuln.cvss_v3_score.label("cvss"),
        )
        .select_from(Ticket)
        .join(Vuln, Ticket.vulnerability_id == Vuln.id)
        .where(
            Ticket.external_ticket_url == external_ticket_url,
            Ticket.tenant_id == user.tenant_id,
        )
        .order_by(
            case(
                (Vuln.severity == "CRITICAL", 0),
                (Vuln.severity == "HIGH", 1),
                (Vuln.severity == "MEDIUM", 2),
                (Vuln.severity == "LOW", 3),
                else_=4,
            )
        )
        .limit(20)
    )
    vuln_rows = (await db.execute(vulns_q)).all()
    linked_vulns = [
        {
            "cve": r.cve_id,
            "severity": r.severity,
            "cvss": float(r.cvss) if r.cvss is not None else None,
        }
        for r in vuln_rows
    ]

    # ── Watchers (local only — D-PROV-02) ─────────────────────────────────────
    # FK to tickets(id) using the canonical first_ticket_id (row.id).
    # Provider followers are out of P13 stub scope; local watchers only.
    watchers_q = (
        select(
            TicketWatcher.user_id,
            User.display_name,
        )
        .join(User, TicketWatcher.user_id == User.id)
        .where(TicketWatcher.ticket_id == row.id)
        .order_by(User.display_name)
    )
    watcher_rows = (await db.execute(watchers_q)).all()
    watchers = [
        {
            "userId": str(r.user_id),
            "displayName": r.display_name,
            "role": "watcher",  # D-W-04: role-tagged so frontend can compose the People card
        }
        for r in watcher_rows
    ]

    # ── Determine title ───────────────────────────────────────────────────────
    detail_q = (
        select(
            # Postgres has no min(uuid); cast to text. Only consumed when the
            # group is single-host (host_count == 1), so the MIN is unambiguous.
            func.min(func.cast(Asset.id, String)).label("asset_id"),
            func.min(Asset.hostname).label("hostname"),
            func.min(Asset.os_name).label("os_name"),
            func.max(Asset.risk_score).label("risk_score"),
            func.count(func.distinct(Asset.id)).label("host_count"),
            func.max(
                case(
                    (Vuln.severity == "CRITICAL", 4),
                    (Vuln.severity == "HIGH", 3),
                    (Vuln.severity == "MEDIUM", 2),
                    (Vuln.severity == "LOW", 1),
                    else_=0,
                )
            ).label("max_sev_rank"),
            func.count().filter(Vuln.severity == "CRITICAL").label("critical_count"),
            func.count().filter(Vuln.severity == "HIGH").label("high_count"),
            func.min(Ticket.created_by_rule).label("created_by_rule"),
            # WR-04: group-level invariant — per-remediation iff every row carries
            # created_by_rule (not just the MIN being non-null).
            func.bool_and(Ticket.created_by_rule.isnot(None)).label("all_by_rule"),
            func.min(Vuln.remediation_action).label("remediation_action"),
            func.min(Vuln.affected_product).label("affected_product"),
        )
        .select_from(Ticket)
        .join(Vuln, Ticket.vulnerability_id == Vuln.id)
        .outerjoin(Asset, Vuln.asset_id == Asset.id)
        .where(
            Ticket.external_ticket_url == external_ticket_url,
            Ticket.tenant_id == user.tenant_id,
        )
    )
    detail = (await db.execute(detail_q)).first()

    is_per_remediation = bool(detail.all_by_rule) if detail else False
    if is_per_remediation:
        title = f"{detail.affected_product or 'Unknown'}: {(detail.remediation_action or '')[:80]}"
        # CR-03: per-remediation description seam — the remediation action text.
        description = detail.remediation_action if detail else None
    else:
        title = detail.hostname if detail else "Unknown"
        description = None

    # CR-03: severity aggregates for the People/Asset rail + summary.
    sev_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "INFO"}
    max_severity = sev_map.get(detail.max_sev_rank, "UNKNOWN") if detail else None
    host_count = detail.host_count if detail else 0

    # CR-03: single-host tickets expose a typed asset object so TicketAssetCard
    # cross-links to /assets/{id}; multi-host groups send asset=null (the card
    # then renders the "Multiple hosts" fallback). camelCase nested keys match
    # the existing reporter/watcher nested-object convention on this endpoint.
    asset_obj = None
    if detail and host_count == 1 and detail.asset_id is not None:
        asset_obj = {
            "assetId": str(detail.asset_id),
            "hostname": detail.hostname,
            "osName": detail.os_name,
            "riskScore": detail.risk_score,
        }

    # CR-02: resolve the assignee string (email/user id) to a Person object so
    # the People card + buildWatcherList receive an object, never a bare string.
    raw_assignee = group.assignee if group else row.assignee
    assignee_obj = None
    if raw_assignee:
        assignee_row = (
            await db.execute(
                select(User.id, User.display_name, User.email).where(
                    User.email == raw_assignee, User.tenant_id == user.tenant_id
                )
            )
        ).first()
        if assignee_row:
            assignee_obj = {
                "userId": str(assignee_row.id),
                "displayName": assignee_row.display_name,
                "email": assignee_row.email,
            }
        else:
            # No matching user row — surface the raw value as the display name
            # so the card still shows something meaningful (no userId collision).
            assignee_obj = {
                "userId": f"assignee:{raw_assignee}",
                "displayName": raw_assignee,
                "email": raw_assignee if "@" in raw_assignee else None,
            }

    raw_provider = group.provider if group else row.provider
    return {
        "id": str(row.id),
        # CR-06: lowercased provider for the frontend literal lookups.
        "provider": raw_provider.lower() if raw_provider else raw_provider,
        "external_ticket_id": row.external_ticket_id,
        "external_ticket_url": external_ticket_url,
        "external_status": group.external_status if group else row.external_status,
        "blocked": bool(group.blocked) if group else False,
        "blocked_reason": group.blocked_reason if group else None,
        "sla_due_at": group.sla_due_at.isoformat() if group and group.sla_due_at else None,
        # CR-02: Person object (or null), never a bare string.
        "assignee": assignee_obj,
        "reporter": reporter_data,
        "title": title,
        # CR-03: fields the detail page consumes.
        "description": description,
        "max_severity": max_severity,
        "critical_count": detail.critical_count if detail else 0,
        "high_count": detail.high_count if detail else 0,
        "asset": asset_obj,
        "linked_vulns": linked_vulns,
        "watchers": watchers,
        "vuln_count": group.vuln_count if group else 0,
        "ticket_created_at": (group.ticket_created_at.isoformat() if group and group.ticket_created_at else None),
        "resolved_at": (group.resolved_at.isoformat() if group and group.resolved_at else None),
    }


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
    """Run a rule immediately (manual trigger) — dispatches by the rule's OWN
    `action.provider` (D-10), not always Asana."""
    from sqlalchemy import select

    from app.connectors.service import get_decrypted_credentials
    from app.ticketing.models import ConnectorConfig, TicketRule
    from app.ticketing.rule_engine import run_rule

    result = await db.execute(
        select(TicketRule).where(TicketRule.id == rule_id, TicketRule.tenant_id == user.tenant_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")

    provider = (rule.action or {}).get("provider", "ASANA")
    connector_result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.tenant_id == user.tenant_id,
            ConnectorConfig.connector_type == provider,
            ConnectorConfig.is_enabled.is_(True),
        )
    )
    connector = connector_result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(400, f"No {provider.title()} connector configured. Add one in Connectors page.")

    creds = get_decrypted_credentials(connector)
    config = connector.config or {}

    run_result = await run_rule(db, rule, creds, config)
    from datetime import datetime

    rule.last_run_at = datetime.now(UTC)
    rule.last_run_status = "SUCCESS"
    rule.last_run_tickets_created = run_result["created"]
    await db.commit()
    return run_result


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
