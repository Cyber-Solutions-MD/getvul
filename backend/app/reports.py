"""Scheduled reports — model, CRUD, and scheduler integration."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule: Mapped[str] = mapped_column(String(20), nullable=False)  # daily, weekly, monthly
    format: Mapped[str] = mapped_column(String(10), default="pdf")
    recipients: Mapped[dict] = mapped_column(JSONB, nullable=False)  # ["email@example.com"]
    sections: Mapped[dict] = mapped_column(JSONB)
    filters: Mapped[dict] = mapped_column(JSONB)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_send_status: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ── CRUD ──


async def list_reports(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(ScheduledReport)
                .where(ScheduledReport.tenant_id == tenant_id)
                .order_by(ScheduledReport.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_to_dict(r) for r in rows]


async def create_report(db: AsyncSession, tenant_id: uuid.UUID, data: dict) -> dict:
    r = ScheduledReport(
        tenant_id=tenant_id,
        name=data.get("name", "Weekly Report"),
        schedule=data.get("schedule", "weekly"),
        format=data.get("format", "pdf"),
        recipients=data.get("recipients", []),
        sections=data.get(
            "sections",
            # Phase 43 Plan 02 (RPT-01 D-04): the 3 new board-report
            # sections are appended at the end of the pre-existing default
            # list -- never inserted mid-list -- so a newly-created report
            # that doesn't specify `sections` explicitly stores the same
            # effective default `export.py::_collect_summary_data` already
            # falls back to. Kept in lockstep with that default and with
            # `_send_report`'s own fallback below (43-PATTERNS.md: 3 call
            # sites, one literal list each).
            [
                "vulns",
                "assets",
                "risk",
                "top_hosts",
                "top_remediations",
                "tickets",
                "risk_trend",
                "mttr_by_tier",
                "sla_compliance",
            ],
        ),
        filters=data.get("filters", {}),
        is_enabled=data.get("is_enabled", True),
        created_at=datetime.now(UTC),
    )
    db.add(r)
    await db.flush()
    await db.refresh(r)
    return _to_dict(r)


async def update_report(db: AsyncSession, tenant_id: uuid.UUID, report_id: uuid.UUID, data: dict) -> dict | None:
    r = (
        await db.execute(
            select(ScheduledReport).where(ScheduledReport.id == report_id, ScheduledReport.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not r:
        return None
    for key in ["name", "schedule", "format", "recipients", "sections", "filters", "is_enabled"]:
        if key in data:
            setattr(r, key, data[key])
    if "recipients" in data or "sections" in data or "filters" in data:
        from sqlalchemy.orm.attributes import flag_modified

        for k in ["recipients", "sections", "filters"]:
            if k in data:
                flag_modified(r, k)
    r.updated_at = datetime.now(UTC)
    return _to_dict(r)


async def delete_report(db: AsyncSession, tenant_id: uuid.UUID, report_id: uuid.UUID) -> bool:
    r = (
        await db.execute(
            select(ScheduledReport).where(ScheduledReport.id == report_id, ScheduledReport.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not r:
        return False
    await db.delete(r)
    return True


def _to_dict(r: ScheduledReport) -> dict:
    return {
        "id": str(r.id),
        "name": r.name,
        "is_enabled": r.is_enabled,
        "schedule": r.schedule,
        "format": r.format,
        "recipients": r.recipients,
        "sections": r.sections,
        "filters": r.filters,
        "last_sent_at": r.last_sent_at.isoformat() if r.last_sent_at else None,
        "last_send_status": r.last_send_status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ── Scheduler ──


async def run_due_reports(db: AsyncSession) -> dict:
    """Check all enabled reports and send those that are due."""
    import structlog

    logger = structlog.get_logger()

    now = datetime.now(UTC)
    reports = (await db.execute(select(ScheduledReport).where(ScheduledReport.is_enabled.is_(True)))).scalars().all()

    sent = 0
    for report in reports:
        if not _is_due(report, now):
            continue

        try:
            await _send_report(db, report)
            report.last_sent_at = now
            report.last_send_status = "SUCCESS"
            sent += 1
            logger.info("scheduled_report_sent", name=report.name, recipients=len(report.recipients))
        except Exception as e:
            report.last_sent_at = now
            report.last_send_status = "FAILED"
            logger.error("scheduled_report_failed", name=report.name, error=str(e))

    if sent > 0:
        await db.commit()

    return {"checked": len(reports), "sent": sent}


def _is_due(report: ScheduledReport, now: datetime) -> bool:
    """Check if a scheduled report is due to be sent."""
    if not report.last_sent_at:
        return True  # Never sent — send now

    elapsed_hours = (now - report.last_sent_at).total_seconds() / 3600

    return (
        (report.schedule == "daily" and elapsed_hours >= 23)
        or (report.schedule == "weekly" and elapsed_hours >= 167)
        or (report.schedule == "monthly" and elapsed_hours >= 719)
    )


async def _send_report(db: AsyncSession, report: ScheduledReport) -> None:
    """Generate and send a report to recipients.

    Currently writes to the audit log. Email delivery requires SMTP configuration.
    In production, integrate with SendGrid, SES, or an SMTP server.
    """
    from app.export import generate_executive_summary, generate_executive_summary_csv, generate_executive_summary_pdf

    filters = {
        "severity": report.filters.get("severity") if report.filters else None,
        "device_type": report.filters.get("device_type") if report.filters else None,
        "exploit_available": report.filters.get("exploit_available") if report.filters else None,
        "cisa_kev": report.filters.get("cisa_kev") if report.filters else None,
        # Phase 43 Plan 02 (RPT-01 D-04): fallback for a pre-existing
        # `ScheduledReport` row whose `sections` is empty/None -- kept in
        # lockstep with `create_report`'s own default above and with
        # `export.py::_collect_summary_data`'s default. No `period_start`/
        # `period_end` key here: `ScheduledReport` has no period field
        # (out of scope this phase), so `_collect_summary_data` falls back
        # to its own last-completed-quarter default every scheduled run.
        "sections": report.sections
        or [
            "vulns",
            "assets",
            "risk",
            "top_hosts",
            "top_remediations",
            "tickets",
            "risk_trend",
            "mttr_by_tier",
            "sla_compliance",
        ],
        "top_count": report.filters.get("top_count", 10) if report.filters else 10,
        "min_risk": report.filters.get("min_risk", 0) if report.filters else 0,
    }

    if report.format == "pdf":
        content = await generate_executive_summary_pdf(db, report.tenant_id, filters)
    elif report.format == "csv":
        content = await generate_executive_summary_csv(db, report.tenant_id, filters)
    else:
        content = await generate_executive_summary(db, report.tenant_id, filters)

    # Store the generated report path for download
    from pathlib import Path

    report_dir = Path("/app/reports")
    report_dir.mkdir(exist_ok=True)

    ext = report.format or "txt"
    filename = f"{report.name.replace(' ', '_')}_{datetime.now(UTC).strftime('%Y%m%d')}.{ext}"
    filepath = report_dir / filename

    if isinstance(content, (bytes, bytearray)):
        filepath.write_bytes(bytes(content))
    else:
        filepath.write_text(content)

    # Send via email if SMTP is configured
    email_result = None
    if report.recipients:
        from sqlalchemy import select as _sel

        from app.tenants.models import Tenant

        tenant = (await db.execute(_sel(Tenant).where(Tenant.id == report.tenant_id))).scalar_one_or_none()
        smtp_cfg = tenant.smtp_config if tenant else None

        if smtp_cfg and smtp_cfg.get("enabled") and smtp_cfg.get("host"):
            from app.email import send_email

            mime = {
                "pdf": "application/pdf",
                "csv": "text/csv",
            }.get(report.format or "txt", "text/plain")

            email_result = send_email(
                smtp_config=smtp_cfg,
                to=report.recipients,
                subject=f"GetVul Report: {report.name}",
                body=f'Attached is your scheduled report "{report.name}" ({report.schedule}).\n\nGenerated: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}',
                attachment=content if isinstance(content, (bytes, bytearray)) else content.encode("utf-8"),
                attachment_filename=filename,
                attachment_mime=mime,
            )

    # Log for audit
    from app.audit import AuditLog

    log = AuditLog(
        tenant_id=report.tenant_id,
        action="report.scheduled_send",
        resource_type="report",
        resource_id=str(report.id),
        details={
            "name": report.name,
            "recipients": report.recipients,
            "file": filename,
            "email_sent": email_result.get("ok") if email_result else False,
            "email_error": email_result.get("error") if email_result and not email_result.get("ok") else None,
        },
        created_at=datetime.now(UTC),
    )
    db.add(log)
