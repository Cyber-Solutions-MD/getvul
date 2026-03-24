"""Export service — CSV and PDF report generation."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.tenants.models import Tenant, User
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability


async def export_vulnerabilities_csv(db: AsyncSession, tenant_id: uuid.UUID, filters: dict) -> str:
    """Export vulnerabilities to CSV."""
    query = (
        select(Vulnerability, Asset.hostname)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(Vulnerability.tenant_id == tenant_id)
        .order_by(
            case(
                (Vulnerability.severity == "CRITICAL", 0),
                (Vulnerability.severity == "HIGH", 1),
                (Vulnerability.severity == "MEDIUM", 2),
                else_=3,
            ),
            Vulnerability.last_seen_at.desc(),
        )
        .limit(10000)
    )

    if filters.get("severity"):
        query = query.where(Vulnerability.severity.in_(filters["severity"]))
    if filters.get("status"):
        query = query.where(Vulnerability.status.in_(filters["status"]))
    if filters.get("source"):
        query = query.where(Vulnerability.source.in_(filters["source"]))
    if filters.get("exploit_available"):
        query = query.where(Vulnerability.exploit_available.is_(True))
    if filters.get("cisa_kev"):
        query = query.where(Vulnerability.cisa_kev.is_(True))

    rows = (await db.execute(query)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "CVE ID",
            "Severity",
            "Status",
            "Source",
            "Hostname",
            "Product",
            "Version",
            "Fixed Version",
            "Exploit Available",
            "CISA KEV",
            "CVSS",
            "Remediation",
            "File Paths",
            "First Detected",
            "Last Seen",
        ]
    )

    for vuln, hostname in rows:
        paths = ", ".join(vuln.file_paths) if vuln.file_paths and isinstance(vuln.file_paths, list) else ""
        writer.writerow(
            [
                vuln.cve_id,
                vuln.severity,
                vuln.status,
                vuln.source,
                hostname,
                vuln.affected_product,
                vuln.affected_version,
                vuln.fixed_version,
                vuln.exploit_available,
                vuln.cisa_kev,
                vuln.cvss_v3_score,
                vuln.remediation_action or vuln.remediation_info,
                paths,
                vuln.first_detected_at.isoformat() if vuln.first_detected_at else "",
                vuln.last_seen_at.isoformat() if vuln.last_seen_at else "",
            ]
        )

    return output.getvalue()


async def export_assets_csv(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Export assets to CSV."""
    query = select(Asset).where(Asset.tenant_id == tenant_id).order_by(Asset.risk_score.desc().nullslast()).limit(10000)
    assets = (await db.execute(query)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Hostname",
            "Device Category",
            "OS",
            "OS Version",
            "Risk Score",
            "Serial Number",
            "Model",
            "Assigned User",
            "Department",
            "Host Status",
            "Last Seen",
            "Scanners",
        ]
    )

    for a in assets:
        scanners = ", ".join(a.seen_by_sources) if isinstance(a.seen_by_sources, list) else ""
        writer.writerow(
            [
                a.hostname,
                a.device_category,
                a.os_name,
                a.os_version,
                a.risk_score,
                a.serial_number,
                a.model,
                a.assigned_user,
                a.department,
                a.host_status,
                a.last_seen_at.isoformat() if a.last_seen_at else "",
                scanners,
            ]
        )

    return output.getvalue()


async def export_users_csv(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Export users to CSV."""
    users = (await db.execute(select(User).where(User.tenant_id == tenant_id).order_by(User.email))).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Email",
            "Display Name",
            "Role",
            "Department",
            "Job Title",
            "Active",
            "Password Login",
            "IdP Source",
            "Groups",
            "Last Login",
        ]
    )

    for u in users:
        groups = ", ".join(u.groups) if u.groups and isinstance(u.groups, list) else ""
        writer.writerow(
            [
                u.email,
                u.display_name,
                u.role,
                u.department,
                u.job_title,
                u.is_active,
                u.allow_password_login,
                u.idp_source,
                groups,
                u.last_login_at.isoformat() if u.last_login_at else "",
            ]
        )

    return output.getvalue()


async def export_tickets_csv(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Export tickets to CSV."""
    query = (
        select(Ticket, Vulnerability.cve_id, Vulnerability.severity, Asset.hostname)
        .join(Vulnerability, Ticket.vulnerability_id == Vulnerability.id)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(Ticket.tenant_id == tenant_id)
        .order_by(Ticket.ticket_created_at.desc())
        .limit(10000)
    )
    rows = (await db.execute(query)).all()

    # Group by task URL
    tasks: dict[str, dict] = {}
    for ticket, cve_id, severity, hostname in rows:
        url = ticket.external_ticket_url
        if url not in tasks:
            tasks[url] = {
                "url": url,
                "provider": ticket.provider,
                "status": ticket.external_status,
                "assignee": ticket.assignee,
                "hostname": hostname,
                "created": ticket.ticket_created_at,
                "resolved": ticket.resolved_at,
                "vulns": 0,
                "cves": [],
                "max_severity": "LOW",
            }
        tasks[url]["vulns"] += 1
        if cve_id and cve_id not in tasks[url]["cves"]:
            tasks[url]["cves"].append(cve_id)
        sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        if sev_rank.get(severity, 0) > sev_rank.get(tasks[url]["max_severity"], 0):
            tasks[url]["max_severity"] = severity

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Ticket URL", "Provider", "Host", "Severity", "Vulns", "CVEs", "Assignee", "Status", "Created", "Resolved"]
    )

    for t in tasks.values():
        writer.writerow(
            [
                t["url"],
                t["provider"],
                t["hostname"],
                t["max_severity"],
                t["vulns"],
                "; ".join(t["cves"][:10]),
                t["assignee"],
                t["status"],
                t["created"].isoformat() if t["created"] else "",
                t["resolved"].isoformat() if t["resolved"] else "",
            ]
        )

    return output.getvalue()


async def export_remediations_csv(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Export remediations to CSV."""
    query = (
        select(
            Vulnerability.remediation_id,
            Vulnerability.remediation_action,
            Vulnerability.affected_product,
            func.count(func.distinct(Vulnerability.asset_id)).label("hosts"),
            func.count(Vulnerability.id).label("vulns"),
            func.max(
                case(
                    (Vulnerability.severity == "CRITICAL", 4),
                    (Vulnerability.severity == "HIGH", 3),
                    (Vulnerability.severity == "MEDIUM", 2),
                    else_=1,
                )
            ).label("max_sev"),
        )
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.remediation_id.isnot(None),
        )
        .group_by(Vulnerability.remediation_id, Vulnerability.remediation_action, Vulnerability.affected_product)
        .order_by(
            func.max(
                case(
                    (Vulnerability.severity == "CRITICAL", 4),
                    (Vulnerability.severity == "HIGH", 3),
                    (Vulnerability.severity == "MEDIUM", 2),
                    else_=1,
                )
            ).desc()
        )
        .limit(5000)
    )
    rows = (await db.execute(query)).all()
    sev_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW"}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Remediation ID", "Action", "Product", "Max Severity", "Affected Hosts", "Vuln Count"])

    for r in rows:
        writer.writerow(
            [
                r.remediation_id,
                r.remediation_action,
                r.affected_product,
                sev_map.get(r.max_sev, "LOW"),
                r.hosts,
                r.vulns,
            ]
        )

    return output.getvalue()


async def _collect_summary_data(db: AsyncSession, tenant_id: uuid.UUID, filters: dict | None = None) -> dict:
    """Collect all data needed for the executive summary."""
    f = filters or {}
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    now = datetime.now(UTC)

    sev_filter = f.get("severity")
    dev_filter = f.get("device_type")
    exploit_filter = f.get("exploit_available")
    kev_filter = f.get("cisa_kev")
    top_count = f.get("top_count", 5) or 5
    min_risk = f.get("min_risk", 0) or 0
    sections = f.get("sections") or ["vulns", "assets", "risk", "top_hosts", "top_remediations", "tickets"]

    open_filter = [Vulnerability.tenant_id == tenant_id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])]
    if sev_filter:
        open_filter.append(Vulnerability.severity.in_(sev_filter))
    if exploit_filter:
        open_filter.append(Vulnerability.exploit_available.is_(True))
    if kev_filter:
        open_filter.append(Vulnerability.cisa_kev.is_(True))

    total = (await db.execute(select(func.count(Vulnerability.id)).where(*open_filter))).scalar_one()
    critical = (
        (
            await db.execute(
                select(func.count(Vulnerability.id)).where(*open_filter, Vulnerability.severity == "CRITICAL")
            )
        ).scalar_one()
        if not sev_filter or "CRITICAL" in sev_filter
        else 0
    )
    high = (
        (
            await db.execute(select(func.count(Vulnerability.id)).where(*open_filter, Vulnerability.severity == "HIGH"))
        ).scalar_one()
        if not sev_filter or "HIGH" in sev_filter
        else 0
    )
    exploitable = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(*open_filter, Vulnerability.exploit_available.is_(True))
        )
    ).scalar_one()
    kev_count = (
        await db.execute(select(func.count(Vulnerability.id)).where(*open_filter, Vulnerability.cisa_kev.is_(True)))
    ).scalar_one()

    # Assets by device category (filtered)
    asset_where = [Asset.tenant_id == tenant_id]
    if dev_filter:
        asset_where.append(Asset.device_category.in_(dev_filter))
    if min_risk > 0:
        asset_where.append(Asset.risk_score >= min_risk)

    cat_q = (
        select(Asset.device_category, func.count(), func.avg(Asset.risk_score))
        .where(*asset_where)
        .group_by(Asset.device_category)
    )
    by_category = [(r[0] or "OTHER", r[1], round(float(r[2] or 0), 1)) for r in (await db.execute(cat_q)).all()]
    total_assets = sum(c[1] for c in by_category)

    # Risk distribution (filtered)
    risk_q = select(
        func.count().filter(Asset.risk_score >= 80),
        func.count().filter((Asset.risk_score >= 50) & (Asset.risk_score < 80)),
        func.count().filter((Asset.risk_score >= 20) & (Asset.risk_score < 50)),
        func.count().filter((Asset.risk_score < 20) | (Asset.risk_score.is_(None))),
    ).where(*asset_where)
    rd = (await db.execute(risk_q)).one()

    # Top N riskiest hosts (filtered)
    top_hosts_q = (
        select(Asset.hostname, Asset.risk_score, Asset.device_category, Asset.assigned_user)
        .where(*asset_where, Asset.risk_score.isnot(None))
        .order_by(Asset.risk_score.desc())
        .limit(top_count)
    )
    top_hosts = (await db.execute(top_hosts_q)).all()

    # Top N remediations by impact (filtered by device type)
    rem_q = (
        select(
            Vulnerability.remediation_action,
            Vulnerability.affected_product,
            func.count(func.distinct(Vulnerability.asset_id)).label("hosts"),
            func.count(Vulnerability.id).label("vulns"),
            func.max(
                case(
                    (Vulnerability.severity == "CRITICAL", 4),
                    (Vulnerability.severity == "HIGH", 3),
                    (Vulnerability.severity == "MEDIUM", 2),
                    else_=1,
                )
            ).label("max_sev"),
        )
        .join(Asset, Vulnerability.asset_id == Asset.id)
        .where(*open_filter, Vulnerability.remediation_id.isnot(None))
    )
    if dev_filter:
        rem_q = rem_q.where(Asset.device_category.in_(dev_filter))
    if min_risk > 0:
        rem_q = rem_q.where(Asset.risk_score >= min_risk)
    rem_q = (
        rem_q.group_by(Vulnerability.remediation_action, Vulnerability.affected_product)
        .order_by(func.count(func.distinct(Vulnerability.asset_id)).desc())
        .limit(top_count)
    )
    top_rems = (await db.execute(rem_q)).all()
    sev_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW"}

    # Tickets
    ticket_total = (
        await db.execute(
            select(func.count(func.distinct(Ticket.external_ticket_url))).where(Ticket.tenant_id == tenant_id)
        )
    ).scalar_one()
    ticket_open = (
        await db.execute(
            select(func.count(func.distinct(Ticket.external_ticket_url))).where(
                Ticket.tenant_id == tenant_id, Ticket.resolved_at.is_(None)
            )
        )
    ).scalar_one()

    return {
        "org": tenant.name,
        "generated": now,
        "sections": sections,
        "vulns": {
            "total": total,
            "open": total,
            "critical": critical,
            "high": high,
            "exploitable": exploitable,
            "kev": kev_count,
        },
        "assets": {
            "total": total_assets,
            "by_category": by_category,
            "risk": {"critical": rd[0], "high": rd[1], "medium": rd[2], "low": rd[3]},
        },
        "top_hosts": [
            {"hostname": h.hostname, "risk": h.risk_score, "type": h.device_category, "user": h.assigned_user}
            for h in top_hosts
        ],
        "top_remediations": [
            {
                "action": r.remediation_action,
                "product": r.affected_product,
                "hosts": r.hosts,
                "vulns": r.vulns,
                "severity": sev_map.get(r.max_sev, "LOW"),
            }
            for r in top_rems
        ],
        "tickets": {"total": ticket_total, "open": ticket_open, "resolved": ticket_total - ticket_open},
    }


async def generate_executive_summary(db: AsyncSession, tenant_id: uuid.UUID, filters: dict | None = None) -> str:
    """Generate a text-based executive summary."""
    d = await _collect_summary_data(db, tenant_id, filters)
    v, a, t = d["vulns"], d["assets"], d["tickets"]
    sec = d.get("sections", [])
    n = len(d["top_hosts"])

    lines = [
        f"{'=' * 70}",
        "  GETVUL EXECUTIVE SUMMARY REPORT",
        f"  Organization: {d['org']}",
        f"  Generated: {d['generated'].strftime('%Y-%m-%d %H:%M UTC')}",
        f"{'=' * 70}",
    ]

    if "vulns" in sec:
        lines.extend(
            [
                "",
                "VULNERABILITY OVERVIEW",
                f"  Total (filtered):           {v['total']:>8,}",
                f"  Critical:                   {v['critical']:>8,}",
                f"  High:                       {v['high']:>8,}",
                f"  Exploitable:                {v['exploitable']:>8,}",
                f"  CISA KEV:                   {v['kev']:>8,}",
            ]
        )
    if "assets" in sec:
        lines.extend(["", "ASSETS BY TYPE", f"  {'Category':<20s} {'Count':>8s}  {'Avg Risk':>10s}", f"  {'-' * 42}"])
        for cat, count, avg in sorted(a["by_category"], key=lambda x: -x[1]):
            lines.append(f"  {cat:<20s} {count:>8,}  {avg:>10.1f}")
        lines.append(f"  {'TOTAL':<20s} {a['total']:>8,}")
    if "risk" in sec:
        lines.extend(
            [
                "",
                "RISK DISTRIBUTION",
                f"  Critical (80+):             {a['risk']['critical']:>8,}",
                f"  High (50-79):               {a['risk']['high']:>8,}",
                f"  Medium (20-49):             {a['risk']['medium']:>8,}",
                f"  Low (<20):                  {a['risk']['low']:>8,}",
            ]
        )
    if "top_hosts" in sec:
        lines.extend(
            [
                "",
                f"TOP {n} RISKIEST HOSTS",
                f"  {'Hostname':<30s} {'Risk':>5s}  {'Type':<15s} {'User':<20s}",
                f"  {'-' * 75}",
            ]
        )
        for h in d["top_hosts"]:
            lines.append(f"  {h['hostname']:<30s} {h['risk']:>5d}  {(h['type'] or '-'):<15s} {(h['user'] or '-'):<20s}")
    if "top_remediations" in sec:
        lines.extend(
            [
                "",
                f"TOP {n} REMEDIATIONS",
                f"  {'Product':<25s} {'Sev':<10s} {'Hosts':>6s} {'Vulns':>6s}  Action",
                f"  {'-' * 80}",
            ]
        )
        for r in d["top_remediations"]:
            lines.append(
                f"  {(r['product'] or '?'):<25s} {r['severity']:<10s} {r['hosts']:>6,} {r['vulns']:>6,}  {(r['action'] or '')[:50]}"
            )
    if "tickets" in sec:
        lines.extend(
            [
                "",
                "TICKET STATUS",
                f"  Total:                      {t['total']:>8,}",
                f"  Open:                       {t['open']:>8,}",
                f"  Resolved:                   {t['resolved']:>8,}",
            ]
        )

    lines.extend(["", f"{'=' * 70}", "  END OF REPORT"])
    return "\n".join(lines)


async def generate_executive_summary_csv(db: AsyncSession, tenant_id: uuid.UUID, filters: dict | None = None) -> str:
    """Generate executive summary as CSV."""
    d = await _collect_summary_data(db, tenant_id, filters)
    v, a, t = d["vulns"], d["assets"], d["tickets"]

    output = io.StringIO()
    w = csv.writer(output)

    w.writerow(["GetVul Executive Summary"])
    w.writerow(["Organization", d["org"]])
    w.writerow(["Generated", d["generated"].strftime("%Y-%m-%d %H:%M UTC")])
    w.writerow([])

    w.writerow(["VULNERABILITY OVERVIEW"])
    w.writerow(["Metric", "Count"])
    for label, val in [
        ("Total", v["total"]),
        ("Open", v["open"]),
        ("Critical", v["critical"]),
        ("High", v["high"]),
        ("Exploitable", v["exploitable"]),
        ("CISA KEV", v["kev"]),
    ]:
        w.writerow([label, val])
    w.writerow([])

    w.writerow(["ASSETS BY TYPE"])
    w.writerow(["Category", "Count", "Avg Risk Score"])
    for cat, count, avg in sorted(a["by_category"], key=lambda x: -x[1]):
        w.writerow([cat, count, avg])
    w.writerow(["TOTAL", a["total"]])
    w.writerow([])

    w.writerow(["RISK DISTRIBUTION"])
    w.writerow(["Level", "Count"])
    for label, val in [
        ("Critical (80+)", a["risk"]["critical"]),
        ("High (50-79)", a["risk"]["high"]),
        ("Medium (20-49)", a["risk"]["medium"]),
        ("Low (<20)", a["risk"]["low"]),
    ]:
        w.writerow([label, val])
    w.writerow([])

    w.writerow(["TOP 5 RISKIEST HOSTS"])
    w.writerow(["Hostname", "Risk Score", "Type", "User"])
    for h in d["top_hosts"]:
        w.writerow([h["hostname"], h["risk"], h["type"], h["user"]])
    w.writerow([])

    w.writerow(["TOP 5 REMEDIATIONS"])
    w.writerow(["Product", "Severity", "Affected Hosts", "Vuln Count", "Action"])
    for r in d["top_remediations"]:
        w.writerow([r["product"], r["severity"], r["hosts"], r["vulns"], r["action"]])
    w.writerow([])

    w.writerow(["TICKETS"])
    w.writerow(["Total", t["total"]])
    w.writerow(["Open", t["open"]])
    w.writerow(["Resolved", t["resolved"]])

    return output.getvalue()


async def generate_executive_summary_pdf(db: AsyncSession, tenant_id: uuid.UUID, filters: dict | None = None) -> bytes:
    """Generate executive summary as PDF."""
    from fpdf import FPDF

    d = await _collect_summary_data(db, tenant_id, filters)
    v, a, t = d["vulns"], d["assets"], d["tickets"]

    # Load branding config
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    brand = tenant.branding or {}
    company_name = brand.get("company_name") or d["org"] or "Organization"
    tagline = brand.get("tagline", "")
    logo_path = brand.get("logo_path", "")
    primary_r = brand.get("primary_color_r", 79)
    primary_g = brand.get("primary_color_g", 70)
    primary_b = brand.get("primary_color_b", 229)  # indigo-500 default
    accent_r = brand.get("accent_color_r", 240)
    accent_g = brand.get("accent_color_g", 240)
    accent_b = brand.get("accent_color_b", 250)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header bar with branding color
    pdf.set_fill_color(primary_r, primary_g, primary_b)
    pdf.rect(0, 0, 210, 3, "F")

    # Logo
    y_start = 10
    if logo_path:
        from pathlib import Path

        if Path(logo_path).exists():
            try:
                pdf.image(logo_path, x=10, y=y_start, h=15)
                y_start += 2  # slight offset for text alignment
            except Exception:
                pass  # skip if image fails

    # Title
    pdf.set_y(y_start)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(primary_r, primary_g, primary_b)
    pdf.cell(0, 12, f"{company_name} — Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    sub_line = f"Generated: {d['generated'].strftime('%Y-%m-%d %H:%M UTC')}"
    if tagline:
        sub_line = f"{tagline}  |  {sub_line}"
    pdf.cell(0, 6, sub_line, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    def section(title):
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_fill_color(accent_r, accent_g, accent_b)
        pdf.set_text_color(primary_r, primary_g, primary_b)
        pdf.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    def row(label, value):
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(90, 6, f"  {label}")
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, str(value), new_x="LMARGIN", new_y="NEXT")

    sec = d.get("sections", [])
    n = len(d["top_hosts"])

    # Vulnerabilities
    if "vulns" not in sec:
        pass
    else:
        section("Vulnerability Overview")
    for label, val in [
        ("Total Vulnerabilities", f"{v['total']:,}"),
        ("Open / In Progress", f"{v['open']:,}"),
        ("Critical (open)", f"{v['critical']:,}"),
        ("High (open)", f"{v['high']:,}"),
        ("Exploitable (open)", f"{v['exploitable']:,}"),
        ("CISA KEV (open)", f"{v['kev']:,}"),
    ]:
        row(label, val)
    pdf.ln(5)

    # Assets by type
    section("Assets by Type")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(60, 6, "  Category")
    pdf.cell(30, 6, "Count", align="R")
    pdf.cell(40, 6, "Avg Risk", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for cat, count, avg in sorted(a["by_category"], key=lambda x: -x[1]):
        pdf.cell(60, 5, f"  {cat}")
        pdf.cell(30, 5, f"{count:,}", align="R")
        pdf.cell(40, 5, f"{avg:.1f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(60, 5, "  TOTAL")
    pdf.cell(30, 5, f"{a['total']:,}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Risk distribution
    section("Risk Distribution")
    for label, val in [
        ("Critical (80+)", a["risk"]["critical"]),
        ("High (50-79)", a["risk"]["high"]),
        ("Medium (20-49)", a["risk"]["medium"]),
        ("Low (<20)", a["risk"]["low"]),
    ]:
        row(label, f"{val:,}")
    pdf.ln(5)

    n = len(d["top_hosts"])
    # Top N hosts
    section(f"Top {n} Riskiest Hosts")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(55, 6, "  Hostname")
    pdf.cell(20, 6, "Risk", align="R")
    pdf.cell(35, 6, "Type")
    pdf.cell(0, 6, "User", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for h in d["top_hosts"]:
        pdf.cell(55, 5, f"  {h['hostname'][:25]}")
        pdf.cell(20, 5, str(h["risk"]), align="R")
        pdf.cell(35, 5, f"  {h['type'] or '-'}")
        pdf.cell(0, 5, h["user"] or "-", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    nr = len(d["top_remediations"])
    # Top N remediations
    section(f"Top {nr} Remediations (by impact)")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(45, 6, "  Product")
    pdf.cell(20, 6, "Sev")
    pdf.cell(15, 6, "Hosts", align="R")
    pdf.cell(15, 6, "Vulns", align="R")
    pdf.cell(0, 6, "  Action", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    for r in d["top_remediations"]:
        pdf.cell(45, 5, f"  {(r['product'] or '?')[:20]}")
        pdf.cell(20, 5, r["severity"])
        pdf.cell(15, 5, str(r["hosts"]), align="R")
        pdf.cell(15, 5, str(r["vulns"]), align="R")
        pdf.cell(0, 5, f"  {(r['action'] or '')[:45]}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Tickets
    section("Ticket Status")
    for label, val in [("Total Tickets", t["total"]), ("Open", t["open"]), ("Resolved", t["resolved"])]:
        row(label, f"{val:,}")

    # Footer on each page
    for page_num in range(1, pdf.pages_count + 1):
        pdf.page = page_num
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(150, 150, 150)
        footer_text = f"{company_name} — Confidential  |  Page {page_num}/{pdf.pages_count}"
        pdf.cell(0, 5, footer_text, align="C")

    # Bottom color bar on last page
    pdf.set_fill_color(primary_r, primary_g, primary_b)
    pdf.rect(0, 292, 210, 3, "F")

    return pdf.output()
