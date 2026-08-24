"""Export service — CSV and PDF report generation."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import detect_version_boundaries, get_scoped_trend_series
from app.assets.models import Asset
from app.assets.risk_score import RISK_SCORE_TIER_CRITICAL, RISK_SCORE_TIER_HIGH, RISK_SCORE_TIER_MEDIUM
from app.exceptions.service import active_exception_subquery
from app.tenants.models import Tenant, User
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.service import get_mttr_by_tier
from app.vulnerabilities.sla_service import get_sla_metrics


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
            # EXC-02/D-15 (Phase 39 Tier 2 #14): an actively-excepted
            # finding never inflates the remediations export.
            ~active_exception_subquery(tenant_id, datetime.now(UTC)),
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


def last_completed_quarter(today: date) -> tuple[date, date]:
    """RPT-01 D-03 default board-report period: the most-recently
    *completed* calendar quarter (never the in-progress one) --
    43-RESEARCH.md's verified sketch, Open Question 1 RESOLVED. No prior
    "quarter" date-math exists anywhere in this codebase (verified via
    grep) -- this is genuinely new logic, not a re-derivation. Reused by
    `main.py::export_resource`'s `period=quarter` preset (Task 3) so the
    route's explicit choice and this module's own fallback-when-no-period
    default share one definition."""
    q = (today.month - 1) // 3 + 1  # current quarter, 1-4
    first_of_this_q = date(today.year, 3 * (q - 1) + 1, 1)
    end = first_of_this_q - timedelta(days=1)  # last day of the previous quarter
    start_month = 3 * ((end.month - 1) // 3) + 1
    start = date(end.year, start_month, 1)
    return start, end


# RPT-01 MTTR-by-tier display order + print-safe light-mode hexes
# (43-UI-SPEC.md) -- "not_tracked" (a below-floor scored finding, see
# RemediationEvent's own docstring) deliberately has no bar; it isn't a
# named risk tier in the UI sense.
_MTTR_TIER_DISPLAY: tuple[tuple[str, str, str], ...] = (
    ("critical", "Critical", "#DC2626"),
    ("high", "High", "#EA580C"),
    ("moderate", "Moderate", "#B45309"),
)


def _sla_compliance_color(compliance_pct: float) -> str:
    """43-UI-SPEC.md light-mode success/warning/danger thresholds for the
    SLA-compliance gauge (pass >=95 / approaching >=80 / breached <80)."""
    if compliance_pct >= 95:
        return "#15803D"
    if compliance_pct >= 80:
        return "#B45309"
    return "#DC2626"


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
    sections = f.get("sections") or [
        "vulns",
        "assets",
        "risk",
        "top_hosts",
        "top_remediations",
        "tickets",
        "risk_trend",
        "mttr_by_tier",
        "sla_compliance",
    ]

    # EXC-02/D-15 (Phase 39 Tier 2 #14): an actively-excepted finding is
    # excluded from every count/query below that spreads `*open_filter`
    # (vuln totals, top_remediations) -- ONE addition here propagates to
    # all of them, mirroring `_apply_filters`' shared-predicate-list shape.
    open_filter = [
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        ~active_exception_subquery(tenant_id, now),
    ]
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
        func.count().filter(Asset.risk_score >= RISK_SCORE_TIER_CRITICAL),
        func.count().filter((Asset.risk_score >= RISK_SCORE_TIER_HIGH) & (Asset.risk_score < RISK_SCORE_TIER_CRITICAL)),
        func.count().filter((Asset.risk_score >= RISK_SCORE_TIER_MEDIUM) & (Asset.risk_score < RISK_SCORE_TIER_HIGH)),
        func.count().filter((Asset.risk_score < RISK_SCORE_TIER_MEDIUM) | (Asset.risk_score.is_(None))),
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

    # RPT-01 (Phase 43 Plan 02): period-scoped risk-trend + MTTR-by-tier,
    # plus a fixed trailing-90-day SLA-compliance metric (D-01a -- direct
    # service calls, never re-derived). Only computed when actually
    # requested (`want_new_sections`) so CSV/txt exports and any caller
    # that omits the 3 new keys never pay for these extra queries --
    # backward-compatible with the pre-existing 6-section shape (43-02
    # Task 2 acceptance criteria).
    #
    # `period_start`/`period_end` are caller-supplied `date`s (Task 3's
    # `export_resource` period/from/to params thread through here as
    # `filters["period_start"]`/`filters["period_end"]`); default to the
    # most-recently-completed calendar quarter (D-03) for callers that
    # don't supply either -- scheduled reports (no period UI) and any
    # direct/programmatic caller.
    #
    # Pitfall 3: `get_sla_metrics()` has NO period parameter -- its
    # trailing-90-day window is fixed regardless of `period_start`/
    # `period_end`; the PDF renderer captions this explicitly rather than
    # silently implying it's period-scoped like the other two.
    want_new_sections = any(key in sections for key in ("risk_trend", "mttr_by_tier", "sla_compliance"))
    risk_trend_data: dict[str, Any] = {}
    mttr_by_tier_data: dict[str, Any] = {}
    sla_compliance_data: dict[str, Any] = {}
    if want_new_sections:
        period_start_in = f.get("period_start")
        period_end_in = f.get("period_end")
        if isinstance(period_start_in, date) and isinstance(period_end_in, date):
            period_start, period_end = period_start_in, period_end_in
        else:
            period_start, period_end = last_completed_quarter(now.date())

        trend = await get_scoped_trend_series(db, tenant_id, start=period_start, end=period_end)
        boundaries = detect_version_boundaries(trend)
        risk_trend_data = {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "series": trend,
            "boundaries": boundaries,
        }

        mttr_start = datetime.combine(period_start, time.min, tzinfo=UTC)
        mttr_end = datetime.combine(period_end, time.max, tzinfo=UTC)
        mttr_rows = await get_mttr_by_tier(db, tenant_id, start=mttr_start, end=mttr_end)
        mttr_by_tier_data = {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "rows": mttr_rows,
        }

        sla_compliance_data = await get_sla_metrics(db, tenant_id, exclude_exceptions=True)

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
        "risk_trend": risk_trend_data,
        "mttr_by_tier": mttr_by_tier_data,
        "sla_compliance": sla_compliance_data,
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


# ── RPT-01 chart-render helpers (Phase 43 Plan 02, D-01a/D-02) ─────────────
#
# Server-side chart rasterization for the 3 new board-PDF sections (risk
# trend / MTTR by tier / SLA compliance). Every helper below constructs a
# `matplotlib.figure.Figure` directly and drives it with
# `matplotlib.backends.backend_agg.FigureCanvasAgg` -- the `pyplot` module
# must NEVER be imported anywhere in this codebase; it keeps a global
# mutable figure registry documented as unsafe under concurrent access
# (43-RESEARCH.md Pitfall 5). matplotlib is imported lazily inside each
# helper, mirroring this module's own `from fpdf import FPDF` lazy-import
# convention below, not at module top-level.


def _render_risk_trend_chart(
    trend: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    primary_color: tuple[int, int, int],
) -> io.BytesIO:
    """RPT-01 risk-trend line chart. `trend` is `get_scoped_trend_series()`'s
    list (`date`/`avg_risk_exposure_score`/`risk_model_version`);
    `boundaries` is `detect_version_boundaries()`'s output. With fewer than
    2 real (non-null-score) data points, renders a neutral "not enough
    history" note instead of a plotted line (E9) -- never a fabricated or
    misleading line. `primary_color` is the tenant's own brand RGB (never
    the sunset palette, per 43-UI-SPEC.md's PDF Rendering Contract).
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7.2, 4.0), dpi=200)
    ax = fig.add_subplot(111)

    points = [
        (row["date"], row["avg_risk_exposure_score"]) for row in trend if row.get("avg_risk_exposure_score") is not None
    ]

    if len(points) < 2:
        ax.text(
            0.5,
            0.5,
            "Not enough history to plot a trend yet",
            ha="center",
            va="center",
            fontsize=12,
            color="#6B7280",  # neutral gray -- never a fabricated line (E9)
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
    else:
        dates = [p[0] for p in points]
        scores = [p[1] for p in points]
        color_hex = "#{:02x}{:02x}{:02x}".format(*primary_color)
        ax.plot(dates, scores, color=color_hex, linewidth=2)
        ax.set_ylabel("Avg Risk Exposure Score")
        ax.set_title("Risk Trend")
        step = max(1, len(dates) // 8)
        ax.set_xticks(dates[::step])
        ax.tick_params(axis="x", rotation=45, labelsize=7)
        boundary_dates = {b["date"] for b in boundaries}
        for d in dates:
            if d in boundary_dates:
                # Neutral gray dashed -- NEVER colored (43-UI-SPEC.md).
                ax.axvline(x=d, color="#9CA3AF", linestyle="--", linewidth=1)

    fig.tight_layout()
    canvas = FigureCanvasAgg(fig)
    canvas.draw()  # type: ignore[no-untyped-call]
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    buf.seek(0)
    return buf


def _render_mttr_by_tier_chart(tiers: list[str], days: list[float], colors: list[str]) -> io.BytesIO:
    """RPT-01 MTTR-by-tier grouped bar chart. `colors` are the print-safe
    light-mode severity hexes (43-UI-SPEC.md), never dark-theme tokens."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7.2, 4.0), dpi=200)
    ax = fig.add_subplot(111)
    ax.bar(tiers, days, color=colors)
    ax.set_ylabel("MTTR (days)")
    ax.set_title("MTTR by Risk Tier")
    fig.tight_layout()

    canvas = FigureCanvasAgg(fig)
    canvas.draw()  # type: ignore[no-untyped-call]
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    buf.seek(0)
    return buf


def _render_sla_compliance_chart(compliance_pct: float, color: str) -> io.BytesIO:
    """RPT-01 SLA-compliance bar/gauge. `color` is a pre-resolved
    light-mode success/warning/danger hex (43-UI-SPEC.md) chosen by the
    caller from the pass/approaching/breached thresholds."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7.2, 2.2), dpi=200)
    ax = fig.add_subplot(111)
    ax.barh(["SLA Compliance"], [compliance_pct], color=color)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% remediated within SLA (trailing 90 days)")
    ax.text(min(compliance_pct + 2, 96), 0, f"{compliance_pct:.1f}%", va="center", fontsize=10)
    fig.tight_layout()

    canvas = FigureCanvasAgg(fig)
    canvas.draw()  # type: ignore[no-untyped-call]
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    buf.seek(0)
    return buf


async def generate_executive_summary_pdf(db: AsyncSession, tenant_id: uuid.UUID, filters: dict | None = None) -> bytes:
    """Generate executive summary as PDF."""
    import structlog
    from fpdf import FPDF

    logger = structlog.get_logger()

    f = filters or {}
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
    # [Rule 1 - Bug, discovered Phase 43 Plan 02]: fpdf2's core-font default
    # `core_fonts_encoding` is "latin-1", which does NOT cover the em-dash
    # (U+2014) this function's title (line ~920) and footer (below) have
    # ALWAYS hardcoded -- every call to this function has always raised
    # `FPDFUnicodeEncodingException` for any tenant name, a pre-existing,
    # previously-undiscovered crash (Wave 0 gap: no test ever called this
    # function before 43-RESEARCH.md's Validation Architecture / this
    # plan's test_export.py). cp1252 is a superset-compatible encoding for
    # this font (identical for ASCII, adds the em-dash at 0x97) -- fixes
    # the crash without changing any visible rendered text.
    pdf.core_fonts_encoding = "cp1252"
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

    def section(title: str) -> None:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_fill_color(accent_r, accent_g, accent_b)
        pdf.set_text_color(primary_r, primary_g, primary_b)
        pdf.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    def row(label: str, value: str) -> None:
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

    # RPT-01 (Phase 43 Plan 02): risk trend -> MTTR by tier -> SLA
    # compliance, in that exact order (43-UI-SPEC.md PDF Rendering
    # Contract "board narrative first"). Each section is independently
    # toggle-gated via `sec` and embeds a Task-1 chart helper's PNG via
    # `pdf.image(buf, w=180)`. A chart-render failure (or an explicit
    # `filters["charts_enabled"] = False` request) degrades that ONE
    # section to a tables-only render rather than silently dropping it
    # (E9 -- "never a silently-dropped section").
    charts_enabled = bool(f.get("charts_enabled", True))

    if "risk_trend" in sec:
        section("Risk Trend")
        rt = d["risk_trend"]
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 5, f"  {rt['period_start']} to {rt['period_end']}", new_x="LMARGIN", new_y="NEXT")

        chart_rendered = False
        chart_failed = False
        if charts_enabled:
            try:
                buf = _render_risk_trend_chart(rt["series"], rt["boundaries"], (primary_r, primary_g, primary_b))
                pdf.image(buf, w=180)
                chart_rendered = True
            except Exception as e:
                logger.warning("board_pdf_chart_render_failed", section="risk_trend", error=str(e))
                chart_failed = True

        if chart_failed or not charts_enabled:
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 5, "  (chart unavailable -- showing table)", new_x="LMARGIN", new_y="NEXT")

        if not chart_rendered:
            scored = [
                p["avg_risk_exposure_score"] for p in rt["series"] if p.get("avg_risk_exposure_score") is not None
            ]
            if len(scored) >= 2:
                row("Start of period", f"{scored[0]:.1f}")
                row("End of period", f"{scored[-1]:.1f}")
                row("Change", f"{scored[-1] - scored[0]:+.1f}")
            elif len(scored) == 1:
                row("Risk score (period)", f"{scored[0]:.1f}")
            else:
                row("Risk Trend", "Not enough history to plot a trend yet")
        pdf.ln(5)

    if "mttr_by_tier" in sec:
        section("MTTR by Risk Tier")
        mt = d["mttr_by_tier"]
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 5, f"  {mt['period_start']} to {mt['period_end']}", new_x="LMARGIN", new_y="NEXT")

        by_tier = {r["tier_at_remediation"]: r for r in mt["rows"]}
        measured = [
            (label, by_tier[key]["avg_seconds"] / 86400.0, color)
            for key, label, color in _MTTR_TIER_DISPLAY
            if by_tier.get(key) and by_tier[key]["count"] > 0 and by_tier[key]["avg_seconds"] is not None
        ]

        chart_rendered = False
        chart_failed = False
        if measured and charts_enabled:
            try:
                buf = _render_mttr_by_tier_chart(
                    [m[0] for m in measured], [m[1] for m in measured], [m[2] for m in measured]
                )
                pdf.image(buf, w=180)
                chart_rendered = True
            except Exception as e:
                logger.warning("board_pdf_chart_render_failed", section="mttr_by_tier", error=str(e))
                chart_failed = True

        if chart_failed or (measured and not charts_enabled):
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 5, "  (chart unavailable -- showing table)", new_x="LMARGIN", new_y="NEXT")

        if not chart_rendered:
            for key, label, _color in _MTTR_TIER_DISPLAY:
                r = by_tier.get(key)
                if r and r["count"] > 0 and r["avg_seconds"] is not None:
                    row(f"{label} MTTR", f"{r['avg_seconds'] / 86400.0:.1f} days ({r['count']:,} remediated)")
                else:
                    row(f"{label} MTTR", "Not yet measured")
        pdf.ln(5)

    if "sla_compliance" in sec:
        section("SLA Compliance")
        sla = d["sla_compliance"]
        not_measured = sla.get("remediated_total", 0) == 0

        chart_rendered = False
        chart_failed = False
        if not not_measured and charts_enabled:
            try:
                color = _sla_compliance_color(sla["compliance_pct"])
                buf = _render_sla_compliance_chart(sla["compliance_pct"], color)
                pdf.image(buf, w=180)
                chart_rendered = True
            except Exception as e:
                logger.warning("board_pdf_chart_render_failed", section="sla_compliance", error=str(e))
                chart_failed = True

        if chart_failed or (not not_measured and not charts_enabled):
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 5, "  (chart unavailable -- showing table)", new_x="LMARGIN", new_y="NEXT")

        if not chart_rendered:
            if not_measured:
                row("SLA Compliance", "Not yet measured")
            else:
                row("SLA Compliance", f"{sla['compliance_pct']:.1f}%")
                row("Remediated within SLA", f"{sla['remediated_within_sla']:,} / {sla['remediated_total']:,}")
                row("Currently Breached", f"{sla['breached']:,}")
                row("At Risk (72h)", f"{sla['at_risk']:,}")

        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 5, "  Trailing 90-day metric, independent of the selected period", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
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
    #
    # [Rule 1 - Bug, found during Phase 43 Plan 03's checkpoint pre-
    # verification against a real multi-page report]: `set_auto_page_break`
    # was still enabled (set near the top of this function) during this
    # retroactive per-page footer stamp. `set_y(-15)` positions exactly at
    # the auto-break trigger threshold (page_height - margin), so fpdf2's
    # OWN auto-page-break logic fired on the very `cell()` call meant to
    # draw the footer -- silently advancing to the next page before
    # drawing anything. On a real 2-page report this meant: page 1's
    # footer text landed at the TOP of page 2 (visually colliding with
    # page 2's real content), and the final loop iteration's misfire
    # minted a genuinely spurious, otherwise-blank trailing page (a report
    # that should have 2 pages came out as 3). Disabling auto-page-break
    # for this manual, already-fully-paginated stamp pass is the standard
    # fix for a post-hoc footer/page-numbering loop in fpdf2.
    pdf.set_auto_page_break(auto=False)
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
