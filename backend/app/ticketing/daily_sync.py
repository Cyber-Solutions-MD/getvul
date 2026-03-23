"""Daily ticket status sync — checks all open tickets, updates with remediation progress."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.connectors.service import get_decrypted_credentials
from app.ticketing.models import ConnectorConfig, Ticket
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()


async def run_daily_ticket_sync(db: AsyncSession) -> dict:
    """Run daily ticket status sync for all tenants with ticketing connectors.

    For each tenant:
    1. Find all open tickets
    2. For each ticket, check the current state of linked vulnerabilities
    3. If progress was made (some vulns remediated), post a status comment
    4. If all vulns resolved, auto-close the ticket
    """
    # Find all tenants with ticketing connectors
    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.is_enabled.is_(True),
            ConnectorConfig.connector_type.in_(["ASANA", "JIRA"]),
            ConnectorConfig.credentials_secret_arn.isnot(None),
        )
    )
    ticketing_connectors = result.scalars().all()

    total_synced = 0
    total_resolved = 0
    total_comments = 0
    tenants_processed = 0

    for connector in ticketing_connectors:
        try:
            creds = get_decrypted_credentials(connector)
            tenant_id = connector.tenant_id
            provider = connector.connector_type

            if provider == "ASANA":
                from app.ticketing.asana_client import AsanaClient

                client = AsanaClient(creds.get("access_token", ""))
                stats = await _sync_asana_tickets(db, tenant_id, client)
                await client.close()
            elif provider == "JIRA":
                from app.connectors.jira_client import JiraClient

                client = JiraClient(
                    url=creds.get("url", ""),
                    email=creds.get("email", ""),
                    api_token=creds.get("api_token", ""),
                )
                stats = await _sync_jira_tickets(db, tenant_id, client)
                await client.close()
            else:
                continue

            total_synced += stats.get("synced", 0)
            total_resolved += stats.get("resolved", 0)
            total_comments += stats.get("comments_added", 0)
            tenants_processed += 1

            if stats.get("comments_added", 0) > 0 or stats.get("resolved", 0) > 0:
                logger.info(
                    "daily_ticket_sync_tenant",
                    tenant_id=str(tenant_id),
                    provider=provider,
                    **stats,
                )

        except Exception as e:
            logger.error(
                "daily_ticket_sync_error",
                tenant_id=str(connector.tenant_id),
                provider=connector.connector_type,
                error=str(e),
            )

    if total_synced > 0:
        await db.commit()

    return {
        "tenants_processed": tenants_processed,
        "synced": total_synced,
        "resolved": total_resolved,
        "comments_added": total_comments,
    }


async def _build_status_comment(db: AsyncSession, vuln_ids: list[uuid.UUID]) -> dict:
    """Analyze vulnerability status for a group of ticket-linked vulns.

    Returns {total, remediated, suppressed, still_open, comment_text, should_close}.
    """
    if not vuln_ids:
        return {"total": 0, "should_close": False, "comment_text": ""}

    status_q = (
        select(Vulnerability.status, func.count(Vulnerability.id).label("cnt"))
        .where(Vulnerability.id.in_(vuln_ids))
        .group_by(Vulnerability.status)
    )
    rows = (await db.execute(status_q)).all()
    counts = {r.status: r.cnt for r in rows}

    total = sum(counts.values())
    remediated = counts.get("REMEDIATED", 0)
    suppressed = counts.get("SUPPRESSED", 0)
    still_open = counts.get("OPEN", 0) + counts.get("IN_PROGRESS", 0)

    if still_open == 0 and total > 0:
        return {
            "total": total,
            "remediated": remediated,
            "suppressed": suppressed,
            "still_open": 0,
            "should_close": True,
            "comment_text": f"All {total} vulnerabilities resolved ({remediated} remediated, {suppressed} suppressed). Closing automatically.",
        }

    if (remediated > 0 or suppressed > 0) and still_open > 0:
        # Build remaining remediations list
        remaining_q = (
            select(
                Vulnerability.remediation_action,
                Vulnerability.affected_product,
                Vulnerability.severity,
                Vulnerability.cve_id,
                Asset.hostname,
            )
            .join(Asset, Vulnerability.asset_id == Asset.id)
            .where(
                Vulnerability.id.in_(vuln_ids),
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            )
            .order_by(
                case(
                    (Vulnerability.severity == "CRITICAL", 0),
                    (Vulnerability.severity == "HIGH", 1),
                    (Vulnerability.severity == "MEDIUM", 2),
                    else_=3,
                )
            )
            .limit(20)
        )
        remaining = (await db.execute(remaining_q)).all()

        lines = [
            "Progress update from GetVul:",
            "",
            f"Remediated: {remediated}/{total}",
        ]
        if suppressed > 0:
            lines.append(f"Suppressed: {suppressed}")
        lines.append(f"Remaining: {still_open}")
        lines.append("")
        lines.append("Remaining actions:")

        seen = set()
        for r in remaining:
            action = r.remediation_action or r.cve_id or "Unknown"
            key = f"{r.hostname}:{action}"
            if key not in seen:
                seen.add(key)
                host = r.hostname or "?"
                product = r.affected_product or ""
                lines.append(f"- [{r.severity}] {host} — {product}: {action[:120]}")

        return {
            "total": total,
            "remediated": remediated,
            "suppressed": suppressed,
            "still_open": still_open,
            "should_close": False,
            "comment_text": "\n".join(lines),
        }

    # No progress to report
    return {"total": total, "still_open": still_open, "should_close": False, "comment_text": ""}


async def _sync_asana_tickets(db: AsyncSession, tenant_id: uuid.UUID, client) -> dict:
    """Sync all open Asana tickets for a tenant."""

    result = await db.execute(
        select(Ticket).where(
            Ticket.tenant_id == tenant_id,
            Ticket.provider == "ASANA",
            Ticket.resolved_at.is_(None),
        )
    )
    tickets = result.scalars().all()
    if not tickets:
        return {"synced": 0, "resolved": 0, "comments_added": 0}

    synced = 0
    resolved = 0
    comments_added = 0
    task_cache: dict[str, dict | None] = {}
    commented_tasks: set[str] = set()

    # First pass: sync completion status from Asana
    for ticket in tickets:
        task_gid = ticket.external_ticket_id.split(":")[0]
        if task_gid not in task_cache:
            task_cache[task_gid] = await client.get_task(task_gid)

        task = task_cache[task_gid]
        if task is None:
            continue

        synced += 1

        if task.get("completed"):
            ticket.external_status = "completed"
            ticket.resolved_at = datetime.now(UTC)
            resolved += 1
            vuln = (
                await db.execute(select(Vulnerability).where(Vulnerability.id == ticket.vulnerability_id))
            ).scalar_one_or_none()
            if vuln and vuln.status not in ("REMEDIATED", "SUPPRESSED"):
                vuln.status = "REMEDIATED"
                vuln.remediated_at = datetime.now(UTC)
        else:
            ticket.external_status = "open"

    # Second pass: group open tickets by task and post progress comments
    task_tickets: dict[str, list[Ticket]] = {}
    for ticket in tickets:
        if ticket.resolved_at is None:
            task_gid = ticket.external_ticket_id.split(":")[0]
            task_tickets.setdefault(task_gid, []).append(ticket)

    for task_gid, tlist in task_tickets.items():
        if task_gid in commented_tasks:
            continue

        vuln_ids = [t.vulnerability_id for t in tlist if t.vulnerability_id]
        status = await _build_status_comment(db, vuln_ids)

        if status["should_close"]:
            await client.update_task(task_gid, completed=True)
            await client.add_comment(task_gid, status["comment_text"])
            now = datetime.now(UTC)
            for t in tlist:
                t.external_status = "completed"
                t.resolved_at = now
            resolved += len(tlist)
            comments_added += 1
            commented_tasks.add(task_gid)
        elif status["comment_text"]:
            ok = await client.add_comment(task_gid, status["comment_text"])
            if ok:
                comments_added += 1
                commented_tasks.add(task_gid)

    return {"synced": synced, "resolved": resolved, "comments_added": comments_added}


async def _sync_jira_tickets(db: AsyncSession, tenant_id: uuid.UUID, client) -> dict:
    """Sync all open Jira tickets for a tenant."""
    result = await db.execute(
        select(Ticket).where(
            Ticket.tenant_id == tenant_id,
            Ticket.provider == "JIRA",
            Ticket.resolved_at.is_(None),
        )
    )
    tickets = result.scalars().all()
    if not tickets:
        return {"synced": 0, "resolved": 0, "comments_added": 0}

    synced = 0
    resolved = 0
    comments_added = 0
    issue_cache: dict[str, dict | None] = {}
    commented_issues: set[str] = set()

    # First pass: sync status from Jira
    for ticket in tickets:
        issue_key = ticket.external_ticket_id.split(":")[0]
        if issue_key not in issue_cache:
            try:
                issue_cache[issue_key] = await client.get_issue(issue_key)
            except Exception:
                issue_cache[issue_key] = None

        issue = issue_cache[issue_key]
        if issue is None:
            continue

        synced += 1

        # Check if Jira issue is in a "done" category
        status_category = issue.get("fields", {}).get("status", {}).get("statusCategory", {}).get("key", "")
        jira_status = issue.get("fields", {}).get("status", {}).get("name", "")

        if status_category == "done" or jira_status.lower() in ("done", "closed", "resolved", "completed"):
            ticket.external_status = jira_status.lower()
            ticket.resolved_at = datetime.now(UTC)
            resolved += 1
            vuln = (
                await db.execute(select(Vulnerability).where(Vulnerability.id == ticket.vulnerability_id))
            ).scalar_one_or_none()
            if vuln and vuln.status not in ("REMEDIATED", "SUPPRESSED"):
                vuln.status = "REMEDIATED"
                vuln.remediated_at = datetime.now(UTC)
        else:
            ticket.external_status = jira_status.lower()

    # Second pass: group open tickets by issue key and post progress comments
    issue_tickets: dict[str, list[Ticket]] = {}
    for ticket in tickets:
        if ticket.resolved_at is None:
            issue_key = ticket.external_ticket_id.split(":")[0]
            issue_tickets.setdefault(issue_key, []).append(ticket)

    for issue_key, tlist in issue_tickets.items():
        if issue_key in commented_issues:
            continue

        vuln_ids = [t.vulnerability_id for t in tlist if t.vulnerability_id]
        status = await _build_status_comment(db, vuln_ids)

        if status["should_close"]:
            # Add comment and try to transition to Done
            await client.update_issue(issue_key, comment=status["comment_text"], status="Done")
            now = datetime.now(UTC)
            for t in tlist:
                t.external_status = "done"
                t.resolved_at = now
            resolved += len(tlist)
            comments_added += 1
            commented_issues.add(issue_key)
        elif status["comment_text"]:
            try:
                await client.update_issue(issue_key, comment=status["comment_text"])
                comments_added += 1
                commented_issues.add(issue_key)
            except Exception as e:
                logger.error("jira_comment_error", issue_key=issue_key, error=str(e))

    return {"synced": synced, "resolved": resolved, "comments_added": comments_added}
