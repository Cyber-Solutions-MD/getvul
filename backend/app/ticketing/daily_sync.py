"""Daily ticket status sync — checks all open tickets, updates with remediation progress."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.audit import AuditLog
from app.connectors.service import get_decrypted_credentials
from app.connectors.sync import _sanitize_error
from app.ticketing.models import ConnectorConfig, SyncLog, Ticket
from app.ticketing.service import (
    _AWAITING_RESCAN_COMMENT,
    _was_previously_done,
    map_ticket_status,
)
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

# SYNC-04: bounded retry for a transient per-connector ticket-sync failure
# (network blip / upstream 5xx). Reads are idempotent (no partial-write
# risk from a retried poll), so a retry simply redoes the same GET(s).
_MAX_SYNC_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = (1, 2, 4)

# Phase 37 Plan 04: `_DONE_EXTERNAL_STATUSES`, `_AWAITING_RESCAN_COMMENT`, and
# `_was_previously_done` moved to service.py (single owner, imported above) --
# service.py's `sync_ticket_status`/`close_ticket` router-invoked twins need
# the exact same fresh-transition guard this module pioneered, and
# service.py already owns `map_ticket_status`, so promoting them there
# avoids a circular import (this module already imports FROM service.py).
_RECURRENCE_COMMENT = "Recurrence detected — the scanner re-detected this vulnerability. Reopening this ticket."

# Jira's default simplified-workflow "not started" status name -- the
# `transition()` target for a recurrence reopen (matches `to.name`/`name`
# case-insensitively; a tenant with a differently-named open status simply
# logs a "no matching transition" warning via JiraClient.transition's own
# existing no-op-on-no-match behavior, never raises).
_JIRA_OPEN_TRANSITION_TARGET = "To Do"


async def _sync_with_retry(sync_coro_fn, *args):
    """SYNC-04: run a provider `_sync_*` call with bounded retry (3 attempts,
    ~1s/2s/4s exponential backoff) for a transient failure.

    The final attempt's exception propagates to the caller's own per-
    connector isolation `try/except` (T-37-12) -- a connector that exhausts
    every retry surfaces FAILED but never aborts the pass for the other
    connectors. Referenced by module-level name (not a bound closure) so
    tests can monkeypatch `daily_sync._sync_asana_tickets` etc. and still
    have this wrapper pick up the patched function.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_SYNC_ATTEMPTS):
        try:
            return await sync_coro_fn(*args)
        except Exception as e:
            last_exc = e
            if attempt < _MAX_SYNC_ATTEMPTS - 1:
                logger.warning(
                    "ticket_sync_retry",
                    attempt=attempt + 1,
                    max_attempts=_MAX_SYNC_ATTEMPTS,
                    error=_sanitize_error(e),
                )
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS[attempt])
    assert last_exc is not None  # noqa: S101 - unreachable without an exception
    raise last_exc


async def run_daily_ticket_sync(db: AsyncSession) -> dict:
    """Run daily ticket status sync for all tenants with ticketing connectors.

    For each tenant:
    1. Find all open tickets
    2. For each ticket, check the current state of linked vulnerabilities
    3. If progress was made (some vulns remediated), post a status comment
    4. If all vulns resolved, auto-close the ticket

    SYNC-04: each connector's poll is retried (bounded, `_sync_with_retry`)
    and always records a real `last_sync_at`/`last_sync_status`/
    `last_sync_record_count`/`consecutive_failure_count`/`last_error`
    outcome plus a `SyncLog` row -- mirrors the scanner-connector
    resilience precedent (`connectors/sync.py::run_sync`). One connector
    exhausting its retries and surfacing FAILED never aborts the pass for
    the others (per-connector `try/except` isolation, unchanged).
    """
    # Find all tenants with ticketing connectors
    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.is_enabled.is_(True),
            ConnectorConfig.connector_type.in_(["ASANA", "JIRA", "GITHUB"]),
            ConnectorConfig.credentials_secret_arn.isnot(None),
        )
    )
    ticketing_connectors = result.scalars().all()

    total_synced = 0
    total_resolved = 0
    total_comments = 0
    tenants_processed = 0

    for connector in ticketing_connectors:
        sync_start = datetime.now(UTC)
        log = SyncLog(
            connector_id=connector.id,
            tenant_id=connector.tenant_id,
            status="RUNNING",
            started_at=sync_start,
        )
        db.add(log)
        await db.flush()

        client = None
        try:
            creds = get_decrypted_credentials(connector)
            tenant_id = connector.tenant_id
            provider = connector.connector_type

            if provider == "ASANA":
                from app.ticketing.asana_client import AsanaClient

                client = AsanaClient(creds.get("access_token", ""))
                stats = await _sync_with_retry(_sync_asana_tickets, db, tenant_id, client)
            elif provider == "JIRA":
                from app.ticketing.jira_client import JiraClient

                client = JiraClient(
                    email=creds.get("email", ""),
                    api_token=creds.get("api_token", ""),
                    base_url=creds.get("url", ""),
                )
                stats = await _sync_with_retry(_sync_jira_tickets, db, tenant_id, client)
            elif provider == "GITHUB":
                from app.ticketing.github_client import GitHubClient

                connector_config = connector.config or {}
                client = GitHubClient(
                    token=creds.get("token", ""),
                    owner=connector_config.get("owner", ""),
                    repo=connector_config.get("repo", ""),
                )
                stats = await _sync_with_retry(_sync_github_tickets, db, tenant_id, client)
            else:
                log.status = "SUCCESS"
                log.finished_at = datetime.now(UTC)
                continue

            total_synced += stats.get("synced", 0)
            total_resolved += stats.get("resolved", 0)
            total_comments += stats.get("comments_added", 0)
            tenants_processed += 1

            record_count = stats.get("synced", 0)
            connector.last_sync_at = datetime.now(UTC)
            connector.last_sync_status = "SUCCESS"
            connector.last_sync_record_count = record_count
            connector.consecutive_failure_count = 0
            connector.last_error = None

            log.status = "SUCCESS"
            log.records_fetched = record_count
            log.details = stats
            log.finished_at = datetime.now(UTC)

            if stats.get("comments_added", 0) > 0 or stats.get("resolved", 0) > 0:
                logger.info(
                    "daily_ticket_sync_tenant",
                    tenant_id=str(tenant_id),
                    provider=provider,
                    **stats,
                )

        except Exception as e:
            sanitized = _sanitize_error(e)
            logger.error(
                "daily_ticket_sync_error",
                tenant_id=str(connector.tenant_id),
                provider=connector.connector_type,
                error=sanitized,
            )
            connector.last_sync_status = "FAILED"
            connector.consecutive_failure_count = (connector.consecutive_failure_count or 0) + 1
            connector.last_error = sanitized
            log.status = "FAILED"
            log.error_message = sanitized
            log.finished_at = datetime.now(UTC)
        finally:
            if client is not None:
                await client.close()

    # SYNC-04: always commit (not gated on total_synced>0 as before) -- a
    # zero-tickets-synced cycle still needs its SyncLog + connector
    # last_sync_* resilience columns persisted so the connector list
    # reflects a real outcome rather than going stale.
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

    # First pass: sync completion status from Asana (SYNC-01/SYNC-03, D-03:
    # a done ticket drives workflow state only -- it NEVER closes a finding
    # the scanner still detects; closure is rescan-only, Plan 01).
    for ticket in tickets:
        task_gid = ticket.external_ticket_id.split(":")[0]
        if task_gid not in task_cache:
            task_cache[task_gid] = await client.get_task(task_gid)

        task = task_cache[task_gid]
        if task is None:
            continue

        synced += 1

        intent = map_ticket_status("ASANA", task)
        was_done_before = _was_previously_done("ASANA", ticket.external_status)
        vuln = (
            await db.execute(select(Vulnerability).where(Vulnerability.id == ticket.vulnerability_id))
        ).scalar_one_or_none()

        if intent == "done_awaiting_rescan":
            if vuln and was_done_before and vuln.status == "OPEN":
                # SYNC-03/D-04: the finding was reopened (rescan re-detected
                # it) while the ticket still shows completed on Asana --
                # reopen the SAME task, never create a new Ticket row.
                await client.update_task(task_gid, completed=False)
                await client.add_comment(task_gid, _RECURRENCE_COMMENT)
                ticket.external_status = "open"
                ticket.resolved_at = None
            else:
                ticket.external_status = "completed"
                if vuln and not was_done_before and vuln.status in ("OPEN", "IN_PROGRESS"):
                    vuln.status = "IN_PROGRESS"
                    await client.add_comment(task_gid, _AWAITING_RESCAN_COMMENT)
                    db.add(
                        AuditLog(
                            tenant_id=vuln.tenant_id,
                            user_id=None,
                            user_email="system:ticket-sync",
                            action="vuln.ticket_status_sync",
                            resource_type="vulnerability",
                            resource_id=str(vuln.id),
                            details={"provider": "ASANA", "ticket_id": str(ticket.id), "new_status": "IN_PROGRESS"},
                            ip_address=None,
                            created_at=datetime.now(UTC),
                        )
                    )
        elif intent == "open":
            ticket.external_status = "open"
        else:
            logger.warning("ticket_status_unknown", provider="ASANA", ticket_id=str(ticket.id))

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

    # First pass: sync status from Jira (SYNC-01/SYNC-03, D-03: a done ticket
    # drives workflow state only -- closure is rescan-only, Plan 01).
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

        intent = map_ticket_status("JIRA", issue)
        jira_status_name = (issue.get("fields", {}).get("status", {}).get("name", "") or "").lower()
        was_done_before = _was_previously_done("JIRA", ticket.external_status)
        vuln = (
            await db.execute(select(Vulnerability).where(Vulnerability.id == ticket.vulnerability_id))
        ).scalar_one_or_none()

        if intent == "done_awaiting_rescan":
            if vuln and was_done_before and vuln.status == "OPEN":
                # SYNC-03/D-04: the finding was reopened (rescan re-detected
                # it) while the ticket still shows done on Jira -- transition
                # the SAME issue back to an open status, never create a new
                # Ticket row.
                await client.transition(issue_key, _JIRA_OPEN_TRANSITION_TARGET)
                await client.comment(issue_key, _RECURRENCE_COMMENT)
                ticket.external_status = _JIRA_OPEN_TRANSITION_TARGET.lower()
                ticket.resolved_at = None
            else:
                ticket.external_status = jira_status_name
                if vuln and not was_done_before and vuln.status in ("OPEN", "IN_PROGRESS"):
                    vuln.status = "IN_PROGRESS"
                    await client.comment(issue_key, _AWAITING_RESCAN_COMMENT)
                    db.add(
                        AuditLog(
                            tenant_id=vuln.tenant_id,
                            user_id=None,
                            user_email="system:ticket-sync",
                            action="vuln.ticket_status_sync",
                            resource_type="vulnerability",
                            resource_id=str(vuln.id),
                            details={"provider": "JIRA", "ticket_id": str(ticket.id), "new_status": "IN_PROGRESS"},
                            ip_address=None,
                            created_at=datetime.now(UTC),
                        )
                    )
        elif intent == "in_progress":
            ticket.external_status = jira_status_name
            if vuln and vuln.status in ("OPEN", "IN_PROGRESS"):
                vuln.status = "IN_PROGRESS"
        elif intent == "open":
            ticket.external_status = jira_status_name
        else:
            logger.warning("ticket_status_unknown", provider="JIRA", ticket_id=str(ticket.id))

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
            # Add comment and transition to Done
            await client.comment(issue_key, status["comment_text"])
            await client.transition(issue_key, "Done")
            now = datetime.now(UTC)
            for t in tlist:
                t.external_status = "done"
                t.resolved_at = now
            resolved += len(tlist)
            comments_added += 1
            commented_issues.add(issue_key)
        elif status["comment_text"]:
            try:
                await client.comment(issue_key, status["comment_text"])
                comments_added += 1
                commented_issues.add(issue_key)
            except Exception as e:
                logger.error("jira_comment_error", issue_key=issue_key, error=str(e))

    return {"synced": synced, "resolved": resolved, "comments_added": comments_added}


async def _sync_github_tickets(db: AsyncSession, tenant_id: uuid.UUID, client) -> dict:
    """Sync all open GitHub-provider tickets for a tenant.

    Mirrors the Jira branch's structure: `get_issue(number)` for inbound
    state, `close_issue`/`add_comment` for outbound auto-close parity with
    the Asana template (service.py's Asana auto-close block). `get_watchers`
    is intentionally never called here — local `ticket_watchers` stay the
    source of truth for GitHub-backed tickets (D-12).
    """
    result = await db.execute(
        select(Ticket).where(
            Ticket.tenant_id == tenant_id,
            Ticket.provider == "GITHUB",
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

    # First pass: sync state from GitHub (SYNC-01/SYNC-03, D-03: a done ticket
    # drives workflow state only -- closure is rescan-only, Plan 01).
    for ticket in tickets:
        issue_number = ticket.external_ticket_id.split(":")[0]
        if issue_number not in issue_cache:
            try:
                issue_cache[issue_number] = await client.get_issue(int(issue_number))
            except Exception:
                issue_cache[issue_number] = None

        issue = issue_cache[issue_number]
        if issue is None:
            continue

        synced += 1

        intent = map_ticket_status("GITHUB", issue)
        was_done_before = _was_previously_done("GITHUB", ticket.external_status)
        vuln = (
            await db.execute(select(Vulnerability).where(Vulnerability.id == ticket.vulnerability_id))
        ).scalar_one_or_none()

        if intent == "done_awaiting_rescan":
            if vuln and was_done_before and vuln.status == "OPEN":
                # SYNC-03/D-04: the finding was reopened (rescan re-detected
                # it) while the ticket still shows closed on GitHub --
                # reopen the SAME issue, never create a new Ticket row.
                await client.reopen_issue(int(issue_number))
                await client.add_comment(int(issue_number), _RECURRENCE_COMMENT)
                ticket.external_status = "open"
                ticket.resolved_at = None
            else:
                ticket.external_status = "closed"
                if vuln and not was_done_before and vuln.status in ("OPEN", "IN_PROGRESS"):
                    vuln.status = "IN_PROGRESS"
                    await client.add_comment(int(issue_number), _AWAITING_RESCAN_COMMENT)
                    db.add(
                        AuditLog(
                            tenant_id=vuln.tenant_id,
                            user_id=None,
                            user_email="system:ticket-sync",
                            action="vuln.ticket_status_sync",
                            resource_type="vulnerability",
                            resource_id=str(vuln.id),
                            details={"provider": "GITHUB", "ticket_id": str(ticket.id), "new_status": "IN_PROGRESS"},
                            ip_address=None,
                            created_at=datetime.now(UTC),
                        )
                    )
        elif intent == "open":
            ticket.external_status = "open"
        else:
            logger.warning("ticket_status_unknown", provider="GITHUB", ticket_id=str(ticket.id))

    # Second pass: group open tickets by issue number and post progress comments / auto-close
    issue_tickets: dict[str, list[Ticket]] = {}
    for ticket in tickets:
        if ticket.resolved_at is None:
            issue_number = ticket.external_ticket_id.split(":")[0]
            issue_tickets.setdefault(issue_number, []).append(ticket)

    for issue_number, tlist in issue_tickets.items():
        if issue_number in commented_issues:
            continue

        vuln_ids = [t.vulnerability_id for t in tlist if t.vulnerability_id]
        status = await _build_status_comment(db, vuln_ids)

        if status["should_close"]:
            # Auto-close parity with the Asana block: close + comment.
            await client.close_issue(int(issue_number))
            await client.add_comment(int(issue_number), status["comment_text"])
            now = datetime.now(UTC)
            for t in tlist:
                t.external_status = "closed"
                t.resolved_at = now
            resolved += len(tlist)
            comments_added += 1
            commented_issues.add(issue_number)
        elif status["comment_text"]:
            try:
                await client.add_comment(int(issue_number), status["comment_text"])
                comments_added += 1
                commented_issues.add(issue_number)
            except Exception as e:
                logger.error("github_comment_error", issue_number=issue_number, error=str(e))

    return {"synced": synced, "resolved": resolved, "comments_added": comments_added}
