"""Ticketing service — creates vulnerability tickets in Asana, tracks status."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import String, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.ticketing.asana_client import AsanaClient
from app.ticketing.models import Ticket
from app.ticketing.schemas import HostTicketCreateRequest, TicketCreateRequest, TicketStats, TicketSummary
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

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
    asana_client: AsanaClient,
    workspace_gid: str,
) -> list[TicketSummary]:
    """Create tickets for vulnerabilities in Asana."""
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

        # Create in Asana
        task = await asana_client.create_task(
            workspace_gid=workspace_gid,
            project_gid=request.project_key,
            name=task_name,
            notes=notes,
            assignee=assignee,
            due_on=due_on,
        )

        if task is None:
            logger.error("ticket_creation_failed", vuln_id=str(vuln_id))
            continue

        # Save ticket record
        now = datetime.now(UTC)
        ticket = Ticket(
            tenant_id=tenant_id,
            vulnerability_id=vuln_id,
            provider=request.provider,
            external_ticket_id=task.gid,
            external_ticket_url=task.url,
            external_status="open",
            project_key=request.project_key,
            assignee=assignee,
            created_by_user_id=user_id,
            detected_at=vuln.first_detected_at,
            ticket_created_at=now,
        )
        db.add(ticket)
        await db.flush()

        # Update vulnerability status to IN_PROGRESS
        vuln.status = "IN_PROGRESS"

        created_tickets.append(
            TicketSummary(
                id=ticket.id,
                provider=ticket.provider,
                external_ticket_id=task.gid,
                external_ticket_url=task.url,
                external_status="open",
                assignee=assignee,
                cve_id=vuln.cve_id,
                severity=vuln.severity,
                hostname=hostname,
                ticket_created_at=now,
            )
        )

        logger.info("ticket_created", vuln_id=str(vuln_id), task_gid=task.gid, assignee=assignee)

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
    asana_client: AsanaClient,
    workspace_gid: str,
) -> dict:
    """Create a single Asana ticket for a host with all its remediations."""

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

    # Create in Asana
    task = await asana_client.create_task(
        workspace_gid=workspace_gid,
        project_gid=request.project_key,
        name=task_name,
        notes=notes,
        assignee=assignee,
        due_on=due_on,
    )

    if task is None:
        return {"error": "Failed to create Asana task"}

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
            external_ticket_id=f"{task.gid}:{v.id}",
            external_ticket_url=task.url,
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

    logger.info(
        "host_ticket_created",
        hostname=hostname,
        task_gid=task.gid,
        assignee=assignee,
        vulns=len(ticket_ids),
        remediations=len(remediations),
    )

    return {
        "task_gid": task.gid,
        "task_url": task.url,
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
    asana_client: AsanaClient,
    workspace_gid: str,
    due_days: int | None = None,
    assignee_email: str | None = None,
    severity_filter: list[str] | None = None,
    source_filter: list[str] | None = None,
    exploit_filter: bool = False,
    kev_filter: bool = False,
) -> dict:
    """Create a single ticket for a remediation action, listing all affected hosts."""

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

    task = await asana_client.create_task(
        workspace_gid=workspace_gid,
        project_gid=project_key,
        name=task_name,
        notes=notes,
        assignee=assignee_email,
        due_on=due_on,
    )
    if task is None:
        return {"error": "Failed to create Asana task"}

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
            external_ticket_id=f"{task.gid}:{vuln.id}",
            external_ticket_url=task.url,
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

    return {
        "task_gid": task.gid,
        "task_url": task.url,
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
) -> dict:
    """List tickets grouped by Asana task (one row per task, not per CVE).

    Phase 12 / UX-04-02: when ``asset_id`` is provided, restrict the result
    set to tickets whose vulnerability sits on that asset. Implemented as a
    subquery so the existing grouped_q and detail_q stay untouched.
    """
    # Build base filter
    base_filter = [Ticket.tenant_id == tenant_id]
    if provider:
        base_filter.append(Ticket.provider == provider)
    if status == "open":
        base_filter.append(Ticket.resolved_at.is_(None))
    elif status == "resolved":
        base_filter.append(Ticket.resolved_at.isnot(None))
    if asset_id:
        # T-12-21 mitigation — the Vulnerability subquery is unscoped, but
        # the outer `Ticket.tenant_id == tenant_id` constraint still applies,
        # so a cross-tenant probe can at most filter the caller's own tickets
        # by another tenant's vuln id. Since vulnerability_id is a 1:1 FK,
        # the intersection is empty by construction.
        ticket_ids_for_asset = (
            select(Vulnerability.id).where(Vulnerability.asset_id == asset_id).scalar_subquery()
        )
        base_filter.append(Ticket.vulnerability_id.in_(ticket_ids_for_asset))

    # Group by task URL (unique per Asana task) to get aggregated info
    grouped_q = (
        select(
            Ticket.external_ticket_url,
            func.cast(func.min(func.cast(Ticket.id, String)), String).label("first_ticket_id"),
            func.min(Ticket.provider).label("provider"),
            func.min(Ticket.external_status).label("external_status"),
            func.min(Ticket.assignee).label("assignee"),
            func.min(Ticket.project_key).label("project_key"),
            func.min(Ticket.ticket_created_at).label("ticket_created_at"),
            func.max(Ticket.resolved_at).label("resolved_at"),
            func.count(Ticket.id).label("vuln_count"),
        )
        .where(*base_filter)
        .group_by(Ticket.external_ticket_url)
        .order_by(func.min(Ticket.ticket_created_at).desc())
    )

    # Count unique tasks
    count_sub = select(func.count(func.distinct(Ticket.external_ticket_url))).where(*base_filter)
    total = (await db.execute(count_sub)).scalar_one()

    # Paginate
    grouped_q = grouped_q.offset((page - 1) * page_size).limit(page_size)
    grouped_rows = (await db.execute(grouped_q)).all()

    items = []
    for row in grouped_rows:
        # Get details for this task
        detail_q = (
            select(
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
                func.min(Vulnerability.remediation_action).label("remediation_action"),
                func.min(Vulnerability.affected_product).label("affected_product"),
            )
            .select_from(Ticket)
            .join(Vulnerability, Ticket.vulnerability_id == Vulnerability.id)
            .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
            .where(Ticket.external_ticket_url == row.external_ticket_url, Ticket.tenant_id == tenant_id)
        )
        detail = (await db.execute(detail_q)).first()

        sev_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "INFO"}
        max_severity = sev_map.get(detail.max_sev_rank, "UNKNOWN") if detail else None
        critical = detail.critical_count if detail else 0
        high = detail.high_count if detail else 0
        host_count = detail.host_count if detail else 0

        # Detect ticket type: per-remediation has created_by_rule set
        is_per_remediation = bool(detail.created_by_rule) if detail else False
        if is_per_remediation:
            title = f"{detail.affected_product or 'Unknown'}: {(detail.remediation_action or '')[:80]}"
            subtitle = f"{host_count} host{'s' if host_count != 1 else ''}"
        else:
            title = detail.hostname if detail else "Unknown"
            subtitle = None

        items.append(
            {
                "id": str(row.first_ticket_id),
                "provider": row.provider,
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


async def sync_ticket_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    asana_client: AsanaClient,
) -> dict:
    """Sync ticket status from Asana back to GetVul.

    Also checks for partially remediated hosts and adds progress comments.
    """
    result = await db.execute(
        select(Ticket).where(
            Ticket.tenant_id == tenant_id,
            Ticket.provider == "ASANA",
            Ticket.resolved_at.is_(None),
        )
    )
    tickets = result.scalars().all()

    synced = 0
    resolved = 0
    comments_added = 0

    # Cache task status to avoid redundant API calls for host tickets
    task_cache: dict[str, dict | None] = {}
    # Track which tasks we've already commented on
    commented_tasks: set[str] = set()

    for ticket in tickets:
        task_gid = ticket.external_ticket_id.split(":")[0]

        if task_gid not in task_cache:
            task_cache[task_gid] = await asana_client.get_task(task_gid)

        task = task_cache[task_gid]
        if task is None:
            continue

        synced += 1

        if task.get("completed"):
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
    # Group open tickets by task URL
    task_tickets: dict[str, list[Ticket]] = {}
    for ticket in tickets:
        task_gid = ticket.external_ticket_id.split(":")[0]
        if ticket.resolved_at is None:  # Still open
            task_tickets.setdefault(task_gid, []).append(ticket)

    for task_gid, task_ticket_list in task_tickets.items():
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

        # Auto-close: if no open vulns remain, complete the Asana task
        if still_open == 0 and total > 0 and task_gid not in commented_tasks:
            now = datetime.now(UTC)
            # Complete the Asana task
            await asana_client.update_task(task_gid, completed=True)
            await asana_client.add_comment(
                task_gid,
                f"✅ All {total} vulnerabilities resolved ({remediated} remediated, {suppressed} suppressed). Closing automatically.",
            )
            # Mark all ticket rows as resolved
            for t in task_ticket_list:
                t.external_status = "completed"
                t.resolved_at = now
            resolved += len(task_ticket_list)
            comments_added += 1
            commented_tasks.add(task_gid)
            continue

        # Only comment if some progress was made (at least 1 remediated or suppressed)
        if (remediated > 0 or suppressed > 0) and still_open > 0 and task_gid not in commented_tasks:
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
            ok = await asana_client.add_comment(task_gid, comment)
            if ok:
                comments_added += 1
                commented_tasks.add(task_gid)

    return {"synced": synced, "resolved": resolved, "comments_added": comments_added}


async def close_ticket(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    external_ticket_url: str,
    asana_client: AsanaClient,
) -> dict:
    """Manually close a ticket — completes the Asana task and resolves all linked vulns."""
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

    now = datetime.now(UTC)

    # Complete the Asana task
    task_gid = tickets[0].external_ticket_id.split(":")[0]
    await asana_client.update_task(task_gid, completed=True)

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
