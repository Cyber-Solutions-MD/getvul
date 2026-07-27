"""Ticketing service — creates vulnerability tickets via any dispatched
TicketingClient (Asana/Jira/GitHub), tracks status.

D-07 (Phase 23 Plan 04): the three create paths, sync_ticket_status, and
close_ticket used to hardcode the Asana client's create call regardless of
the caller's requested provider — the live data-integrity bug where
`provider:"JIRA"` silently created an Asana task while persisting
`Ticket.provider="JIRA"`. They now accept an already-resolved
`TicketingClient` (or, for sync/close where a ticket's provider is only
known after the DB lookup, a `client_resolver` callback) and dispatch
through the create/get/comment/close verb surface from dispatch.py.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import String, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.ticketing.dispatch import TicketingClient
from app.ticketing.models import Ticket
from app.ticketing.providers import TicketProvider
from app.ticketing.schemas import HostTicketCreateRequest, TicketCreateRequest, TicketStats, TicketSummary
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

# A resolver the caller (router.py) supplies to sync_ticket_status/close_ticket
# so those functions can dispatch to the RIGHT client per ticket's own stored
# provider, without service.py owning tenant-scoped credential decryption
# (that stays in router.py, mirroring the pre-existing _get_asana_client
# pattern). Returns None if no enabled connector exists for that provider —
# callers of sync_ticket_status treat that as "skip this provider's tickets",
# not a hard failure (T-23-11).
ClientResolver = Callable[[str], Awaitable[TicketingClient | None]]


def _extract_ref(url: str) -> str:
    """Extract the provider's raw ticket ref (Asana task gid / Jira issue key /
    GitHub issue number) from the URL returned by TicketingClient.create().

    All three adapters' create() return the human-facing URL (dispatch.py),
    and in every case the raw ref is the URL's last path segment:
      - Asana:  https://app.asana.com/0/{project_gid}/{gid}      -> gid
      - Jira:   {base_url}/browse/{issue_key}                    -> issue_key
      - GitHub: https://github.com/{owner}/{repo}/issues/{number} -> number
    """
    return url.rstrip("/").rsplit("/", 1)[-1]


def _provider_create_kwargs(provider: str, assignee: str | None, due_on: str | None) -> dict[str, Any]:
    """Only Asana's create_task natively accepts assignee/due_on kwargs.

    JiraClient.create_ticket / GitHubClient.create_ticket do NOT accept these
    parameter names — JiraAdapter.create forwards **kwargs straight through to
    create_ticket, so passing assignee/due_on there would raise TypeError.
    GitHubAdapter.create ignores **kwargs entirely. Asana behavior stays
    byte-for-byte; Jira/GitHub still get the same info baked into the
    description text via _build_task_description/_build_host_task_description.
    """
    if provider == TicketProvider.ASANA:
        return {"assignee": assignee, "due_on": due_on}
    return {}


async def recompute_ticket_sla(
    db: AsyncSession,
    external_ticket_url: str,
    tenant_id: uuid.UUID,
) -> None:
    """Set sla_due_at on every ticket row in the group to MIN(linked vuln.sla_due_at).

    Canonical-group identity rule (O1): a logical ticket is the group of tickets
    rows sharing one external_ticket_url. This function applies the group MIN of
    linked vulnerability.sla_due_at to ALL rows in the group. NULL when no linked
    vulnerability in the group has a non-null sla_due_at.

    Caller pattern: call AFTER db.flush() so new rows are visible, BEFORE
    db.commit() so the caller can commit the whole unit of work atomically.
    This function does NOT commit.

    Admin hook (WR-02, WIRED): the admin sla_recalculate endpoint
    (app/vulnerabilities/router.py) changes vulnerability.sla_due_at for many
    vulns at once, then calls recompute_ticket_sla for every affected
    external_ticket_url so the materialized ticket SLA stays in sync (no longer
    stale until the next ticket create/sync).
    """
    # SELECT MIN(v.sla_due_at) over all rows in this group
    min_q = (
        select(func.min(Vulnerability.sla_due_at).label("min_sla"))
        .select_from(Ticket)
        .join(Vulnerability, Ticket.vulnerability_id == Vulnerability.id)
        .where(
            Ticket.external_ticket_url == external_ticket_url,
            Ticket.tenant_id == tenant_id,
        )
    )
    result = await db.execute(min_q)
    min_sla = result.scalar_one_or_none()

    # UPDATE all rows in the group to the computed MIN (may be NULL)
    await db.execute(
        update(Ticket)
        .where(
            Ticket.external_ticket_url == external_ticket_url,
            Ticket.tenant_id == tenant_id,
        )
        .values(sla_due_at=min_sla)
    )


# Severity → SLA days mapping for default due dates
SEVERITY_SLA_DAYS = {
    "CRITICAL": 3,
    "HIGH": 14,
    "MEDIUM": 30,
    "LOW": 90,
    "INFO": 180,
}


def _build_task_description(vuln: Vulnerability, hostname: str | None) -> str:
    """Build plain text description for an Asana task."""
    sev = vuln.severity or "UNKNOWN"
    cve = vuln.cve_id or "N/A"
    product = vuln.affected_product or "Unknown"
    version = vuln.affected_version or ""
    fixed = vuln.fixed_version or "N/A"
    remediation = vuln.remediation_action or vuln.remediation_info or "No remediation info available"

    lines = [
        f"Vulnerability: {cve}",
        f"  Severity: {sev}",
        f"  Host: {hostname or 'Unknown'}",
        f"  Product: {product} {version}",
        f"  Fixed Version: {fixed}",
    ]

    if vuln.exploit_available:
        lines.append("  Exploit Available: Yes")
    if vuln.cisa_kev:
        lines.append("  CISA KEV: Yes")
    if vuln.cvss_v3_score:
        lines.append(f"  CVSS: {vuln.cvss_v3_score}")

    lines.append("")
    lines.append(f"Remediation: {remediation}")

    if vuln.cve_id:
        lines.append("")
        lines.append(f"NVD: https://nvd.nist.gov/vuln/detail/{vuln.cve_id}")

    return "\n".join(lines)


async def create_tickets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    request: TicketCreateRequest,
    client: TicketingClient,
) -> list[TicketSummary]:
    """Create tickets for vulnerabilities via the dispatched provider client (D-07)."""
    created_tickets: list[TicketSummary] = []

    for vuln_id in request.vulnerability_ids:
        # Fetch vulnerability with asset info
        result = await db.execute(
            select(Vulnerability)
            .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
            .add_columns(Asset.hostname.label("hostname"))
            .where(Vulnerability.id == vuln_id, Vulnerability.tenant_id == tenant_id)
        )
        row = result.first()
        if row is None:
            continue

        vuln = row[0]
        hostname = row.hostname

        # Check if a ticket already exists for this vuln
        existing = await db.execute(
            select(Ticket).where(
                Ticket.tenant_id == tenant_id,
                Ticket.vulnerability_id == vuln_id,
                Ticket.provider == request.provider,
            )
        )
        if existing.scalar_one_or_none():
            logger.info("ticket_already_exists", vuln_id=str(vuln_id))
            continue

        # Build task
        sev = vuln.severity or "MEDIUM"
        cve = vuln.cve_id or vuln.vulnerability_name or "Unknown vulnerability"
        task_name = f"[{sev}] {cve} on {hostname or 'unknown host'}"

        # Determine due date
        if request.due_days:
            due_on = (datetime.now(UTC) + timedelta(days=request.due_days)).strftime("%Y-%m-%d")
        else:
            sla_days = SEVERITY_SLA_DAYS.get(sev, 30)
            due_on = (datetime.now(UTC) + timedelta(days=sla_days)).strftime("%Y-%m-%d")

        # Resolve assignee
        assignee = request.assignee
        if not assignee and hostname:
            # Try to find the user assigned to this asset via Humaans data
            asset_result = await db.execute(select(Asset).where(Asset.id == vuln.asset_id))
            asset = asset_result.scalar_one_or_none()
            if asset and asset.mdm_details:
                humaans_email = asset.mdm_details.get("humaans_email")
                if humaans_email:
                    assignee = humaans_email

        notes = _build_task_description(vuln, hostname)

        # Create via the dispatched provider client (D-07: destination now
        # matches request.provider, not always Asana).
        url = await client.create(task_name, notes, **_provider_create_kwargs(request.provider, assignee, due_on))

        if url is None:
            logger.error("ticket_creation_failed", vuln_id=str(vuln_id), provider=request.provider)
            continue

        ref = _extract_ref(url)

        # Save ticket record
        now = datetime.now(UTC)
        ticket = Ticket(
            tenant_id=tenant_id,
            vulnerability_id=vuln_id,
            provider=request.provider,
            external_ticket_id=ref,
            external_ticket_url=url,
            external_status="open",
            project_key=request.project_key,
            assignee=assignee,
            created_by_user_id=user_id,
            detected_at=vuln.first_detected_at,
            ticket_created_at=now,
        )
        db.add(ticket)
        await db.flush()

        # Recompute group SLA so the new row gets the group MIN(linked vuln.sla_due_at)
        await recompute_ticket_sla(db, url, tenant_id)

        # Update vulnerability status to IN_PROGRESS
        vuln.status = "IN_PROGRESS"

        created_tickets.append(
            TicketSummary(
                id=ticket.id,
                provider=ticket.provider,
                external_ticket_id=ref,
                external_ticket_url=url,
                external_status="open",
                assignee=assignee,
                cve_id=vuln.cve_id,
                severity=vuln.severity,
                hostname=hostname,
                ticket_created_at=now,
            )
        )

        logger.info("ticket_created", vuln_id=str(vuln_id), ref=ref, provider=request.provider, assignee=assignee)

    return created_tickets


def _build_host_task_description(
    asset: Asset,
    remediations: list[dict],
    vuln_counts: dict,
    vulns: list | None = None,
) -> str:
    """Build plain text description for a host-level remediation ticket."""
    hostname = asset.hostname or "Unknown"
    assigned_user = asset.assigned_user or "Unassigned"

    lines = [
        f"Vulnerability Remediation: {hostname}",
        "",
        "Host Details:",
        f"  Hostname: {hostname}",
        f"  OS: {asset.os_name or ''} {asset.os_version or ''}",
        f"  Model: {asset.model or 'N/A'}",
        f"  Serial: {asset.serial_number or 'N/A'}",
        f"  Assigned User: {assigned_user}",
        f"  Risk Score: {asset.risk_score or 0}/100",
        "",
        "Vulnerability Summary:",
        f"  Total open: {vuln_counts.get('total', 0)}",
        f"  Critical: {vuln_counts.get('critical', 0)}",
        f"  High: {vuln_counts.get('high', 0)}",
        f"  Exploitable: {vuln_counts.get('exploitable', 0)}",
        f"  CISA KEV: {vuln_counts.get('kev', 0)}",
        "",
        "Remediation Actions Required:",
    ]

    for i, rem in enumerate(remediations, 1):
        action = rem.get("remediation_action") or "No remediation info"
        product = rem.get("product") or rem.get("affected_product") or "Unknown"
        sev = rem.get("max_severity") or "MEDIUM"
        rem.get("vuln_count", 1)
        lines.append("")
        lines.append(f"━━━ {i}. [{sev}] {product} ━━━")
        lines.append(f"  Action: {action}")

        # List individual CVEs with file paths for this remediation
        if vulns:
            rem_vulns = [
                v
                for v in vulns
                if (v.remediation_action or v.remediation_info) == (rem.get("remediation_action") or "")
                or v.affected_product == rem.get("affected_product")
            ]
            if not rem_vulns:
                rem_vulns = [v for v in vulns if v.remediation_id == rem.get("remediation_id")]
            for v in rem_vulns[:20]:
                cve = v.cve_id or "N/A"
                exploit = " ⚡EXPLOIT" if v.exploit_available else ""
                kev = " 🛡KEV" if v.cisa_kev else ""
                paths = ""
                if v.file_paths and isinstance(v.file_paths, list):
                    paths = f" | Path: {', '.join(v.file_paths[:2])}"
                lines.append(f"  [{v.severity}] {cve}{exploit}{kev}{paths}")

    return "\n".join(lines)


async def create_host_ticket(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    request: HostTicketCreateRequest,
    client: TicketingClient,
) -> dict:
    """Create a single ticket for a host with all its remediations (D-07)."""

    # Fetch asset
    result = await db.execute(select(Asset).where(Asset.id == request.asset_id, Asset.tenant_id == tenant_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        return {"error": "Asset not found"}

    # Check if this asset already has an open ticket
    existing_ticket = (
        await db.execute(
            select(Ticket)
            .join(Vulnerability, Ticket.vulnerability_id == Vulnerability.id)
            .where(
                Ticket.tenant_id == tenant_id,
                Ticket.provider == request.provider,
                Ticket.resolved_at.is_(None),
                Vulnerability.asset_id == asset.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing_ticket:
        return {
            "error": f"This host already has an open ticket ({existing_ticket.external_ticket_url})",
            "existing_url": existing_ticket.external_ticket_url,
        }

    # Fetch open vulns for this asset
    vulns = (
        (
            await db.execute(
                select(Vulnerability)
                .where(
                    Vulnerability.asset_id == asset.id,
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
            )
        )
        .scalars()
        .all()
    )

    if not vulns:
        return {"error": "No open vulnerabilities on this asset"}

    # Vuln counts
    vuln_counts = {"total": len(vulns), "critical": 0, "high": 0, "exploitable": 0, "kev": 0}
    max_severity = "LOW"
    sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
    for v in vulns:
        if v.severity == "CRITICAL":
            vuln_counts["critical"] += 1
        if v.severity == "HIGH":
            vuln_counts["high"] += 1
        if v.exploit_available:
            vuln_counts["exploitable"] += 1
        if v.cisa_kev:
            vuln_counts["kev"] += 1
        if sev_rank.get(v.severity, 0) > sev_rank.get(max_severity, 0):
            max_severity = v.severity

    # Group vulns by remediation action
    rem_groups: dict[str, dict] = {}
    for v in vulns:
        key = v.remediation_action or v.remediation_info or v.cve_id or str(v.id)
        if key not in rem_groups:
            rem_groups[key] = {
                "remediation_id": v.remediation_id,
                "remediation_action": v.remediation_action or v.remediation_info or "No remediation info",
                "affected_product": v.affected_product,
                "max_severity": v.severity,
                "vuln_count": 0,
                "cves": [],
            }
        rem_groups[key]["vuln_count"] += 1
        if v.cve_id and v.cve_id not in rem_groups[key]["cves"]:
            rem_groups[key]["cves"].append(v.cve_id)
        if sev_rank.get(v.severity, 0) > sev_rank.get(rem_groups[key]["max_severity"], 0):
            rem_groups[key]["max_severity"] = v.severity

    remediations = sorted(rem_groups.values(), key=lambda r: -sev_rank.get(r["max_severity"], 0))

    # Determine assignee — use Humaans email from asset
    assignee = request.assignee
    if not assignee:
        h = asset.mdm_details or {}
        assignee = h.get("humaans_email") or None

    # Due date based on highest severity
    if request.due_days:
        due_on = (datetime.now(UTC) + timedelta(days=request.due_days)).strftime("%Y-%m-%d")
    else:
        sla_days = SEVERITY_SLA_DAYS.get(max_severity, 30)
        due_on = (datetime.now(UTC) + timedelta(days=sla_days)).strftime("%Y-%m-%d")

    # Build task
    hostname = asset.hostname or "unknown"
    task_name = (
        f"[{max_severity}] Remediate {hostname} — {vuln_counts['total']} vulns ({vuln_counts['critical']} critical)"
    )

    notes = _build_host_task_description(asset, remediations, vuln_counts, vulns=vulns)

    # Create via the dispatched provider client (D-07).
    url = await client.create(task_name, notes, **_provider_create_kwargs(request.provider, assignee, due_on))

    if url is None:
        return {"error": "Failed to create ticket"}

    ref = _extract_ref(url)

    # Save ticket records — one per vuln so we can track resolution
    now = datetime.now(UTC)
    ticket_ids = []
    for v in vulns:
        # Skip if ticket already exists
        existing = await db.execute(
            select(Ticket).where(
                Ticket.tenant_id == tenant_id,
                Ticket.vulnerability_id == v.id,
                Ticket.provider == request.provider,
            )
        )
        if existing.scalar_one_or_none():
            continue

        ticket = Ticket(
            tenant_id=tenant_id,
            vulnerability_id=v.id,
            provider=request.provider,
            external_ticket_id=f"{ref}:{v.id}",
            external_ticket_url=url,
            external_status="open",
            project_key=request.project_key,
            assignee=assignee,
            created_by_user_id=user_id,
            detected_at=v.first_detected_at,
            ticket_created_at=now,
        )
        db.add(ticket)
        ticket_ids.append(v.id)

        # Mark vuln as in progress
        v.status = "IN_PROGRESS"

    await db.flush()

    # Recompute group SLA so all rows get MIN(linked vuln.sla_due_at) for this task URL
    if ticket_ids:
        await recompute_ticket_sla(db, url, tenant_id)

    logger.info(
        "host_ticket_created",
        hostname=hostname,
        ref=ref,
        provider=request.provider,
        assignee=assignee,
        vulns=len(ticket_ids),
        remediations=len(remediations),
    )

    return {
        "task_gid": ref,
        "task_url": url,
        "hostname": hostname,
        "assignee": assignee,
        "due_on": due_on,
        "vulns_linked": len(ticket_ids),
        "remediations": len(remediations),
        "max_severity": max_severity,
    }


async def create_remediation_ticket(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    remediation_id: str,
    provider: str,
    project_key: str,
    client: TicketingClient,
    due_days: int | None = None,
    assignee_email: str | None = None,
    severity_filter: list[str] | None = None,
    source_filter: list[str] | None = None,
    exploit_filter: bool = False,
    kev_filter: bool = False,
) -> dict:
    """Create a single ticket for a remediation action, listing all affected hosts (D-07)."""

    # Get open vulns for this remediation, applying filters
    vulns_q = (
        select(Vulnerability, Asset.hostname, Asset.assigned_user, Asset.mdm_details)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.remediation_id == remediation_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
    )
    if severity_filter:
        vulns_q = vulns_q.where(Vulnerability.severity.in_(severity_filter))
    if source_filter:
        vulns_q = vulns_q.where(Vulnerability.source.in_(source_filter))
    if exploit_filter:
        vulns_q = vulns_q.where(Vulnerability.exploit_available.is_(True))
    if kev_filter:
        vulns_q = vulns_q.where(Vulnerability.cisa_kev.is_(True))

    vulns_q = vulns_q.order_by(Asset.hostname)
    rows = (await db.execute(vulns_q)).all()
    if not rows:
        return {"error": "No open vulnerabilities for this remediation"}

    # Check if ticket already exists for this remediation
    first_vuln = rows[0][0]
    existing = await db.execute(
        select(Ticket)
        .where(
            Ticket.tenant_id == tenant_id,
            Ticket.provider == provider,
            Ticket.resolved_at.is_(None),
            Ticket.created_by_rule == remediation_id,
        )
        .limit(1)
    )
    if existing.scalar_one_or_none():
        return {"error": "Ticket already exists for this remediation"}

    # Group affected hosts
    hosts: dict[str, dict] = {}
    max_sev = "LOW"
    sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
    for vuln, hostname, assigned_user, mdm in rows:
        h = hostname or "unknown"
        if h not in hosts:
            hosts[h] = {
                "hostname": h,
                "assigned_user": assigned_user,
                "email": (mdm or {}).get("humaans_email"),
                "vulns": [],
            }
        hosts[h]["vulns"].append(vuln)
        if sev_rank.get(vuln.severity, 0) > sev_rank.get(max_sev, 0):
            max_sev = vuln.severity

    remediation_action = first_vuln.remediation_action or first_vuln.remediation_info or "Unknown"
    product = first_vuln.affected_product or "Unknown"

    # Build task description
    lines = [
        f"Remediation: {product}",
        f"Action: {remediation_action}",
        f"Severity: {max_sev}",
        f"Affected hosts: {len(hosts)} | Total vulns: {len(rows)}",
        "",
    ]

    # Per-host details with CVEs and file paths
    for h_info in hosts.values():
        user_str = f" ({h_info['assigned_user']})" if h_info.get("assigned_user") else ""
        lines.append(f"━━━ {h_info['hostname']}{user_str} ━━━")
        for v in h_info["vulns"]:
            cve = v.cve_id or "N/A"
            sev = v.severity
            paths = ""
            if v.file_paths and isinstance(v.file_paths, list):
                paths = f" | Path: {', '.join(v.file_paths[:3])}"
            exploit = " ⚡EXPLOIT" if v.exploit_available else ""
            kev = " 🛡KEV" if v.cisa_kev else ""
            lines.append(f"  [{sev}] {cve}{exploit}{kev}{paths}")
        lines.append("")

    notes = "\n".join(lines)

    # Due date
    if due_days:
        due_on = (datetime.now(UTC) + timedelta(days=due_days)).strftime("%Y-%m-%d")
    else:
        due_on = (datetime.now(UTC) + timedelta(days=SEVERITY_SLA_DAYS.get(max_sev, 30))).strftime("%Y-%m-%d")

    task_name = f"[{max_sev}] {product}: {remediation_action[:80]} — {len(hosts)} hosts"

    url = await client.create(task_name, notes, **_provider_create_kwargs(provider, assignee_email, due_on))
    if url is None:
        return {"error": "Failed to create ticket"}

    ref = _extract_ref(url)

    # Save ticket records
    now = datetime.now(UTC)
    linked = 0
    seen_vuln_ids: set = set()
    for vuln, _hostname, _, _ in rows:
        # Skip duplicate vuln IDs within the same remediation
        if vuln.id in seen_vuln_ids:
            continue
        seen_vuln_ids.add(vuln.id)

        ticket = Ticket(
            tenant_id=tenant_id,
            vulnerability_id=vuln.id,
            provider=provider,
            external_ticket_id=f"{ref}:{vuln.id}",
            external_ticket_url=url,
            external_status="open",
            project_key=project_key,
            assignee=assignee_email,
            created_by_user_id=user_id,
            created_by_rule=remediation_id,
            detected_at=vuln.first_detected_at,
            ticket_created_at=now,
        )
        db.add(ticket)
        vuln.status = "IN_PROGRESS"
        linked += 1

    await db.flush()

    # Recompute group SLA for all rows under this task URL
    if linked > 0:
        await recompute_ticket_sla(db, url, tenant_id)

    return {
        "task_gid": ref,
        "task_url": url,
        "remediation": remediation_action[:100],
        "product": product,
        "hosts_affected": len(hosts),
        "vulns_linked": linked,
        "max_severity": max_sev,
    }


async def list_tickets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    provider: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
    asset_id: str | None = None,
    severity: str | None = None,
    sla: str | None = None,
    search: str | None = None,
) -> dict:
    """List tickets grouped by Asana task (one row per task, not per CVE).

    Phase 12 / UX-04-02: when ``asset_id`` is provided, restrict the result
    set to tickets whose vulnerability sits on that asset. Implemented as a
    subquery so the existing grouped_q and detail_q stay untouched.

    WR-01: ``provider``/``status`` accept comma-separated multi-values; the
    four status chips (open/in_progress/completed/blocked) now map to backend
    semantics instead of silently no-op'ing. ``search`` matches the human
    ticket id / assignee (ILIKE) at the SQL level. ``severity`` and ``sla`` are
    applied as a post-aggregate filter on the built items (the per-group
    max_severity and SLA tier are only knowable after the detail aggregate).
    """
    from datetime import UTC, datetime, timedelta

    # Build base filter
    base_filter = [Ticket.tenant_id == tenant_id]

    # WR-01: provider is multi-value (comma-separated). Stored uppercase, so
    # match case-insensitively against the lowercased chip values.
    provider_vals = [p.strip() for p in (provider or "").split(",") if p.strip()]
    if provider_vals:
        base_filter.append(func.lower(Ticket.provider).in_([p.lower() for p in provider_vals]))

    # WR-01: map the four status chips to backend semantics. Multiple chips OR
    # together. "completed" → resolved; "blocked" → blocked flag; "open" /
    # "in_progress" → not resolved (in_progress further requires an external
    # status that is not the initial "open" — best-effort given the stub data).
    status_vals = [s.strip() for s in (status or "").split(",") if s.strip()]
    # Back-compat: the legacy single values open/resolved still work.
    status_clauses = []
    for s in status_vals:
        if s in ("open", "in_progress"):
            status_clauses.append(Ticket.resolved_at.is_(None))
        elif s in ("completed", "resolved"):
            status_clauses.append(Ticket.resolved_at.isnot(None))
        elif s == "blocked":
            status_clauses.append(Ticket.blocked.is_(True))
    if status_clauses:
        from sqlalchemy import or_

        base_filter.append(or_(*status_clauses))

    # WR-01: severity is multi-value. Semantics: include a ticket row if its
    # linked vulnerability matches one of the selected severities (stored
    # uppercase). Applied at the row level via the vuln join subquery so the
    # grouped count stays consistent (a group survives if ANY of its rows
    # match). This is an EXISTS-style row filter, not a group-MAX filter.
    severity_vals = [s.strip().upper() for s in (severity or "").split(",") if s.strip()]
    if severity_vals:
        sev_ticket_ids = select(Vulnerability.id).where(Vulnerability.severity.in_(severity_vals)).scalar_subquery()
        base_filter.append(Ticket.vulnerability_id.in_(sev_ticket_ids))

    # WR-01: free-text search across the human ticket id and assignee.
    if search:
        like = f"%{search}%"
        from sqlalchemy import or_ as _or

        base_filter.append(_or(Ticket.external_ticket_id.ilike(like), Ticket.assignee.ilike(like)))

    if asset_id:
        # T-12-21 mitigation — the Vulnerability subquery is unscoped, but
        # the outer `Ticket.tenant_id == tenant_id` constraint still applies,
        # so a cross-tenant probe can at most filter the caller's own tickets
        # by another tenant's vuln id. Since vulnerability_id is a 1:1 FK,
        # the intersection is empty by construction.
        ticket_ids_for_asset = select(Vulnerability.id).where(Vulnerability.asset_id == asset_id).scalar_subquery()
        base_filter.append(Ticket.vulnerability_id.in_(ticket_ids_for_asset))

    # WR-01: SLA tier filter operates on the group MIN(sla_due_at). Applied as a
    # HAVING so pagination + total stay consistent. "soon" uses the same 7-day
    # window the frontend SlaPill renders (WR-03 flags this flat window as a
    # known divergence from per-severity SLA days — tracked, not changed here).
    sla_having = None
    sla_val = (sla or "").strip()
    if sla_val:
        now = datetime.now(UTC)
        soon_cutoff = now + timedelta(days=7)
        group_sla = func.min(Ticket.sla_due_at)
        if sla_val == "overdue":
            sla_having = group_sla < now
        elif sla_val == "soon":
            sla_having = (group_sla >= now) & (group_sla <= soon_cutoff)
        elif sla_val == "ok":
            sla_having = group_sla > soon_cutoff

    # Group by task URL (unique per Asana task) to get aggregated info
    grouped_q = (
        select(
            Ticket.external_ticket_url,
            func.cast(func.min(func.cast(Ticket.id, String)), String).label("first_ticket_id"),
            func.min(Ticket.external_ticket_id).label("external_ticket_id"),
            func.min(Ticket.provider).label("provider"),
            func.min(Ticket.external_status).label("external_status"),
            func.min(Ticket.assignee).label("assignee"),
            func.min(Ticket.project_key).label("project_key"),
            func.min(Ticket.ticket_created_at).label("ticket_created_at"),
            func.max(Ticket.resolved_at).label("resolved_at"),
            func.count(Ticket.id).label("vuln_count"),
            # Phase 13 / UX-05-01: blocked/sla aggregates per logical-ticket group (O1)
            func.bool_or(Ticket.blocked).label("blocked"),
            func.min(Ticket.blocked_reason).label("blocked_reason"),
            func.min(Ticket.sla_due_at).label("sla_due_at"),
        )
        .where(*base_filter)
        .group_by(Ticket.external_ticket_url)
        .order_by(func.min(Ticket.ticket_created_at).desc())
    )
    if sla_having is not None:
        grouped_q = grouped_q.having(sla_having)

    # Count unique tasks. When an SLA HAVING is active, count the surviving
    # groups via a subquery so the total matches the filtered page set.
    if sla_having is not None:
        count_groups_q = (
            select(Ticket.external_ticket_url)
            .where(*base_filter)
            .group_by(Ticket.external_ticket_url)
            .having(sla_having)
        )
        total = (await db.execute(select(func.count()).select_from(count_groups_q.subquery()))).scalar_one()
    else:
        count_sub = select(func.count(func.distinct(Ticket.external_ticket_url))).where(*base_filter)
        total = (await db.execute(count_sub)).scalar_one()

    # Paginate
    grouped_q = grouped_q.offset((page - 1) * page_size).limit(page_size)
    grouped_rows = (await db.execute(grouped_q)).all()

    # WR-05: batch ALL per-URL detail aggregates into ONE query keyed by
    # external_ticket_url (previously this ran one detail_q per grouped row — up
    # to page_size=100 extra round-trips per list call). Scoping the IN-list to
    # exactly the page's URLs also keeps the detail aggregate consistent with the
    # filtered/paginated group set (the old per-row query ignored that scope).
    page_urls = [row.external_ticket_url for row in grouped_rows]
    details_by_url: dict = {}
    if page_urls:
        details_q = (
            select(
                Ticket.external_ticket_url.label("url"),
                func.min(Asset.hostname).label("hostname"),
                func.count(func.distinct(Asset.id)).label("host_count"),
                func.max(
                    case(
                        (Vulnerability.severity == "CRITICAL", 4),
                        (Vulnerability.severity == "HIGH", 3),
                        (Vulnerability.severity == "MEDIUM", 2),
                        (Vulnerability.severity == "LOW", 1),
                        else_=0,
                    )
                ).label("max_sev_rank"),
                func.count().filter(Vulnerability.severity == "CRITICAL").label("critical_count"),
                func.count().filter(Vulnerability.severity == "HIGH").label("high_count"),
                func.min(Ticket.created_by_rule).label("created_by_rule"),
                # WR-04: ticket "mode" is a group-level invariant. Derive it from
                # bool_and(created_by_rule IS NOT NULL) so a group counts as
                # per-remediation only when EVERY row carries the rule id — a
                # mixed group (some rows null) no longer silently flips type via
                # MIN returning the lone non-null value.
                func.bool_and(Ticket.created_by_rule.isnot(None)).label("all_by_rule"),
                func.min(Vulnerability.remediation_action).label("remediation_action"),
                func.min(Vulnerability.affected_product).label("affected_product"),
            )
            .select_from(Ticket)
            .join(Vulnerability, Ticket.vulnerability_id == Vulnerability.id)
            .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
            .where(
                Ticket.external_ticket_url.in_(page_urls),
                Ticket.tenant_id == tenant_id,
            )
            .group_by(Ticket.external_ticket_url)
        )
        details_by_url = {d.url: d for d in (await db.execute(details_q)).all()}

    sev_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "INFO"}

    items = []
    for row in grouped_rows:
        detail = details_by_url.get(row.external_ticket_url)

        max_severity = sev_map.get(detail.max_sev_rank, "UNKNOWN") if detail else None
        critical = detail.critical_count if detail else 0
        high = detail.high_count if detail else 0
        host_count = detail.host_count if detail else 0

        # WR-04: per-remediation iff ALL rows in the group carry created_by_rule.
        is_per_remediation = bool(detail.all_by_rule) if detail else False
        if is_per_remediation:
            title = f"{detail.affected_product or 'Unknown'}: {(detail.remediation_action or '')[:80]}"
            subtitle = f"{host_count} host{'s' if host_count != 1 else ''}"
        else:
            title = detail.hostname if detail else "Unknown"
            subtitle = None

        items.append(
            {
                "id": str(row.first_ticket_id),
                # CR-06: emit provider lowercased so the frontend literal
                # lookups (ProviderMark, isTicketProvider) match. Stored uppercase.
                "provider": row.provider.lower() if row.provider else row.provider,
                "external_ticket_id": row.external_ticket_id,
                "external_ticket_url": row.external_ticket_url,
                "external_status": row.external_status,
                "assignee": row.assignee,
                "title": title,
                "subtitle": subtitle,
                "ticket_type": "remediation" if is_per_remediation else "host",
                "hostname": detail.hostname if detail else None,
                "host_count": host_count,
                "max_severity": max_severity,
                "vuln_count": row.vuln_count,
                "critical_count": critical,
                "high_count": high,
                "ticket_created_at": row.ticket_created_at.isoformat() if row.ticket_created_at else None,
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
                # Phase 13 / O1: blocked/sla aggregates for the logical-ticket group
                "blocked": bool(row.blocked),
                "blocked_reason": row.blocked_reason,
                "sla_due_at": row.sla_due_at.isoformat() if row.sla_due_at else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


async def get_ticket_stats(db: AsyncSession, tenant_id: uuid.UUID) -> TicketStats:
    """Get ticket statistics — counts unique tasks (not individual vuln rows)."""
    base = Ticket.tenant_id == tenant_id

    total_q = select(func.count(func.distinct(Ticket.external_ticket_url))).where(base)
    total = (await db.execute(total_q)).scalar_one()

    open_q = select(func.count(func.distinct(Ticket.external_ticket_url))).where(
        base,
        Ticket.resolved_at.is_(None),
    )
    open_count = (await db.execute(open_q)).scalar_one()

    # By provider (unique tasks)
    prov_q = (
        select(Ticket.provider, func.count(func.distinct(Ticket.external_ticket_url)))
        .where(base)
        .group_by(Ticket.provider)
    )
    by_provider = {r[0]: r[1] for r in (await db.execute(prov_q)).all()}

    # Vulns covered by tickets (raw count for context)
    vuln_count = (await db.execute(select(func.count(Ticket.id)).where(base))).scalar_one()
    by_severity = {"vulns_covered": vuln_count}

    return TicketStats(
        total=total,
        open=open_count,
        resolved=total - open_count,
        by_provider=by_provider,
        by_severity=by_severity,
    )


def _is_ticket_completed(provider: str, payload: dict[str, Any]) -> bool:
    """Interpret a provider's raw `client.get(ref)` payload as done/not-done.

    Each provider's raw shape differs (dispatch.py's `get()` deliberately
    returns the raw provider payload, not a normalized one) — this is the one
    place that knows how to read all three: Asana's `completed` bool, Jira's
    status-category/name, GitHub's `state` string.
    """
    if provider == TicketProvider.ASANA:
        return bool(payload.get("completed"))
    if provider == TicketProvider.JIRA:
        status = payload.get("fields", {}).get("status", {})
        category = status.get("statusCategory", {}).get("key", "")
        name = status.get("name", "")
        return category == "done" or name.lower() in ("done", "closed", "resolved", "completed")
    if provider == TicketProvider.GITHUB:
        return payload.get("state") == "closed"
    return False


async def sync_ticket_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    client_resolver: ClientResolver,
) -> dict:
    """Sync ticket status from each ticket's OWN provider back to GetVul (D-07).

    Previously hardcoded `Ticket.provider == "ASANA"` — every open ticket
    regardless of provider is now considered, grouped by provider, and
    dispatched to that provider's client via `client_resolver`. A provider
    with no configured connector is skipped (logged), not treated as a hard
    failure, so one missing connector doesn't abort sync for the others.

    Also checks for partially remediated hosts and adds progress comments.
    """
    result = await db.execute(
        select(Ticket).where(
            Ticket.tenant_id == tenant_id,
            Ticket.resolved_at.is_(None),
        )
    )
    tickets = result.scalars().all()

    synced = 0
    resolved = 0
    comments_added = 0

    tickets_by_provider: dict[str, list[Ticket]] = {}
    for t in tickets:
        tickets_by_provider.setdefault(t.provider, []).append(t)

    resolved_clients: dict[str, TicketingClient | None] = {}

    for provider, provider_tickets in tickets_by_provider.items():
        if provider not in resolved_clients:
            resolved_clients[provider] = await client_resolver(provider)
        client = resolved_clients[provider]
        if client is None:
            logger.warning("ticket_sync_skip_unconfigured_provider", provider=provider)
            continue

        # Cache raw get() payloads to avoid redundant API calls for host tickets
        task_cache: dict[str, dict[str, Any] | None] = {}
        # Track which tasks we've already commented on
        commented_tasks: set[str] = set()

        for ticket in provider_tickets:
            ref = ticket.external_ticket_id.split(":")[0]

            if ref not in task_cache:
                task_cache[ref] = await client.get(ref)

            payload = task_cache[ref]
            if payload is None:
                continue

            synced += 1

            if _is_ticket_completed(provider, payload):
                ticket.external_status = "completed"
                ticket.resolved_at = datetime.now(UTC)
                resolved += 1
                # Mark vulnerability as remediated
                vuln_result = await db.execute(select(Vulnerability).where(Vulnerability.id == ticket.vulnerability_id))
                vuln = vuln_result.scalar_one_or_none()
                if vuln and vuln.status != "REMEDIATED":
                    vuln.status = "REMEDIATED"
                    vuln.remediated_at = datetime.now(UTC)
            else:
                ticket.external_status = "open"

        # For open host tickets, check if any vulns were remediated and post a progress comment
        # Group open tickets by ref
        task_tickets: dict[str, list[Ticket]] = {}
        for ticket in provider_tickets:
            ref = ticket.external_ticket_id.split(":")[0]
            if ticket.resolved_at is None:  # Still open
                task_tickets.setdefault(ref, []).append(ticket)

        for ref, task_ticket_list in task_tickets.items():
            # Count how many vulns linked to this task are now remediated vs still open
            vuln_ids = [t.vulnerability_id for t in task_ticket_list]
            if not vuln_ids:
                continue

            vuln_status_q = (
                select(
                    Vulnerability.status,
                    func.count(Vulnerability.id).label("cnt"),
                )
                .where(Vulnerability.id.in_(vuln_ids))
                .group_by(Vulnerability.status)
            )
            status_rows = (await db.execute(vuln_status_q)).all()
            status_counts = {r.status: r.cnt for r in status_rows}

            total = sum(status_counts.values())
            remediated = status_counts.get("REMEDIATED", 0)
            suppressed = status_counts.get("SUPPRESSED", 0)
            still_open = status_counts.get("OPEN", 0) + status_counts.get("IN_PROGRESS", 0)

            # Auto-close: if no open vulns remain, complete the ticket via the
            # dispatched client (D-07: no longer Asana-only).
            if still_open == 0 and total > 0 and ref not in commented_tasks:
                now = datetime.now(UTC)
                await client.close(ref)
                await client.comment(
                    ref,
                    f"✅ All {total} vulnerabilities resolved ({remediated} remediated, {suppressed} suppressed). Closing automatically.",
                )
                # Mark all ticket rows as resolved
                for t in task_ticket_list:
                    t.external_status = "completed"
                    t.resolved_at = now
                resolved += len(task_ticket_list)
                comments_added += 1
                commented_tasks.add(ref)
                continue

            # Only comment if some progress was made (at least 1 remediated or suppressed)
            if (remediated > 0 or suppressed > 0) and still_open > 0 and ref not in commented_tasks:
                # Build remaining remediations summary
                remaining_q = (
                    select(
                        Vulnerability.remediation_action,
                        Vulnerability.affected_product,
                        Vulnerability.severity,
                        Vulnerability.cve_id,
                    )
                    .where(
                        Vulnerability.id.in_(vuln_ids),
                        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                    )
                    .order_by(
                        case(
                            (Vulnerability.severity == "CRITICAL", 0),
                            (Vulnerability.severity == "HIGH", 1),
                            else_=2,
                        )
                    )
                    .limit(20)
                )
                remaining = (await db.execute(remaining_q)).all()

                comment_lines = [
                    "📊 Progress update from GetVul:",
                    "",
                    f"✅ Remediated: {remediated}/{total}",
                ]
                if suppressed > 0:
                    comment_lines.append(f"⏭️ Suppressed: {suppressed}")
                comment_lines.append(f"🔴 Remaining: {still_open}")
                comment_lines.append("")
                comment_lines.append("Remaining actions:")

                seen = set()
                for r in remaining:
                    action = r.remediation_action or r.cve_id or "Unknown"
                    if action not in seen:
                        seen.add(action)
                        comment_lines.append(f"• [{r.severity}] {r.affected_product or '?'}: {action[:100]}")

                comment = "\n".join(comment_lines)
                # dispatch.py's comment() returns None (not a success bool) —
                # adapters log-and-swallow provider failures internally, so we
                # optimistically count it (matches the auto-close branch above).
                await client.comment(ref, comment)
                comments_added += 1
                commented_tasks.add(ref)

    return {"synced": synced, "resolved": resolved, "comments_added": comments_added}


async def close_ticket(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    external_ticket_url: str,
    client_resolver: ClientResolver,
) -> dict:
    """Manually close a ticket — dispatches by the ticket's OWN stored
    provider (D-07), completing it on that provider and resolving all linked
    vulns. Previously always completed an Asana task regardless of the
    ticket's persisted provider.
    """
    # Find all ticket rows for this task URL
    result = await db.execute(
        select(Ticket).where(
            Ticket.tenant_id == tenant_id,
            Ticket.external_ticket_url == external_ticket_url,
        )
    )
    tickets = result.scalars().all()
    if not tickets:
        return {"error": "Ticket not found"}

    provider = tickets[0].provider
    client = await client_resolver(provider)
    if client is None:
        return {"error": f"No {provider} connector configured"}

    now = datetime.now(UTC)

    # Complete the ticket on its own provider
    ref = tickets[0].external_ticket_id.split(":")[0]
    await client.close(ref)

    # Resolve all ticket rows and their vulns
    resolved_vulns = 0
    for ticket in tickets:
        ticket.external_status = "completed"
        ticket.resolved_at = now

        vuln_result = await db.execute(select(Vulnerability).where(Vulnerability.id == ticket.vulnerability_id))
        vuln = vuln_result.scalar_one_or_none()
        if vuln and vuln.status not in ("REMEDIATED", "SUPPRESSED"):
            vuln.status = "REMEDIATED"
            vuln.remediated_at = now
            resolved_vulns += 1

    return {"closed": True, "tickets_resolved": len(tickets), "vulns_remediated": resolved_vulns}
