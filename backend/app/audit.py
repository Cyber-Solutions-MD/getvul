"""Audit logging — records user actions for compliance and accountability.

Supports optional syslog forwarding to SIEM solutions (Splunk, QRadar, Sentinel, etc.)

Usage:
    await audit(db, user, "vuln.suppress", "vulnerability", vuln_id, {"count": 5})
    await audit(db, user, "ticket.create", "ticket", task_gid, {"host": "par03642"})
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import socket
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.schemas import CurrentUser
from app.db.base import Base

# AUDIT-01: audit failures are observable. The router pattern is
# `audit(...); db.commit()` so any exception raised here propagates and the
# caller's commit short-circuits — the snooze/unsnooze fails closed when its
# audit row cannot be written. Compliance-sensitive: "mutation succeeded
# without audit row" is a regulatory hazard.
_logger = logging.getLogger(__name__)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    user_email: Mapped[str | None] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ── Actions ──
# auth.login, auth.register, auth.logout, auth.password_change
# vuln.status_update, vuln.bulk_status, vuln.suppress, vuln.unsuppress
# ticket.create, ticket.close, ticket.delete, ticket.comment
# rule.create, rule.update, rule.delete, rule.run
# connector.create, connector.update, connector.delete, connector.sync
# user.create, user.update, user.delete, user.role_change, user.deactivate
# settings.update, settings.sso_toggle
# filter.create, filter.update, filter.delete
# asset.exposure_override (admin manual override, actor=admin email),
# asset.exposure_recompute (auto-inference write, actor=system:exposure-inference,
#   logged only when a value actually changes — Phase 32/EXPO-05)
# asset_group.create, asset_group.update, asset_group.delete,
#   asset_group.member_add, asset_group.member_remove,
#   asset_group.exposure_override (Phase 32 Plan 03 — EXPO-04/EXPO-05; one row
#   per group mutation, regardless of how many member assets it fans out to)
# risk_cutover.threshold_ack (Phase 34 Plan 03 — RISK-09, admin-only, records
#   the per-tenant re-tuning acknowledgment that gates the flag flip below),
#   risk_cutover.flag_enable (admin-only, actor=admin email; the flip is
#   consequential+rare, never actually invoked live in this environment)
# risk_cutover.backfill_enqueue (Phase 34 Plan 05 — RISK-07 gap closure,
#   admin-only, the production trigger for a tenant's historical backfill;
#   only logged on a genuinely NEW enqueue, not a repeated idempotent no-op)
# exception.grant, exception.revoke (Phase 39 Plan 01 — EXC-01/EXC-03,
#   analyst-actor, audit-then-commit), exception.expire (Phase 39 Plan 01 —
#   EXC-03/EXC-04, system actor "system:exception-expiry", lazy-on-read
#   Pattern 4 sweep guarded by resurfaced_audited_at IS NULL so it fires
#   exactly once per naturally-lapsed exception)
# coverage.route_to_owner (Phase 41 -- COV-03, analyst-actor, audit-then-commit;
#   details={hostname, routed_to})


# ── Syslog forwarder ──

_syslog_handler: logging.handlers.SysLogHandler | None = None
_syslog_enabled: bool = False


def configure_syslog(host: str, port: int = 514, protocol: str = "udp", facility: str = "local0") -> None:
    """Configure syslog forwarding for audit events."""
    global _syslog_handler, _syslog_enabled

    facility_map = {
        "local0": logging.handlers.SysLogHandler.LOG_LOCAL0,
        "local1": logging.handlers.SysLogHandler.LOG_LOCAL1,
        "local2": logging.handlers.SysLogHandler.LOG_LOCAL2,
        "local3": logging.handlers.SysLogHandler.LOG_LOCAL3,
        "local4": logging.handlers.SysLogHandler.LOG_LOCAL4,
        "local5": logging.handlers.SysLogHandler.LOG_LOCAL5,
        "local6": logging.handlers.SysLogHandler.LOG_LOCAL6,
        "local7": logging.handlers.SysLogHandler.LOG_LOCAL7,
        "auth": logging.handlers.SysLogHandler.LOG_AUTH,
        "authpriv": logging.handlers.SysLogHandler.LOG_AUTHPRIV,
    }

    sock_type = socket.SOCK_DGRAM if protocol == "udp" else socket.SOCK_STREAM

    try:
        _syslog_handler = logging.handlers.SysLogHandler(
            address=(host, port),
            facility=facility_map.get(facility, logging.handlers.SysLogHandler.LOG_LOCAL0),
            socktype=sock_type,
        )
        _syslog_handler.setFormatter(logging.Formatter("%(message)s"))
        _syslog_enabled = True
    except Exception:
        _syslog_enabled = False


def disable_syslog() -> None:
    """Disable syslog forwarding."""
    global _syslog_handler, _syslog_enabled
    _syslog_handler = None
    _syslog_enabled = False


def _send_to_syslog(event: dict) -> None:
    """Send an audit event to syslog in CEF format."""
    if not _syslog_enabled or not _syslog_handler:
        return
    try:
        # Common Event Format (CEF) for SIEM compatibility
        cef = (
            f"CEF:0|GetVul|VulnMgmt|1.0|{event['action']}|{event['action']}|5|"
            f"suser={event.get('user_email', 'system')} "
            f"act={event['action']} "
            f"cs1={event['resource_type']} cs1Label=ResourceType "
            f"cs2={event.get('resource_id', '')} cs2Label=ResourceID "
            f"msg={json.dumps(event.get('details', {}), default=str)} "
            f"rt={event.get('timestamp', '')}"
        )
        record = logging.LogRecord("getvul.audit", logging.INFO, "", 0, cef, (), None)
        _syslog_handler.emit(record)
    except Exception:
        pass


async def audit(
    db: AsyncSession,
    user: CurrentUser | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Record an audit log entry.

    BL-04 / WR-01 / WR-12: fail-closed. AUDIT-01 (the threat-model item for
    audit-trail tampering / loss) requires that a mutation does not succeed
    without its audit row landing in the database. Caller pattern is
    `audit(...); await db.commit()`, so any exception raised here propagates
    and the commit is skipped — SQLAlchemy will roll back the entire
    transaction including the snooze/unsnooze UPDATE on the next
    connection-level rollback.

    Programmer bugs (e.g. malformed AuditLog kwargs, AttributeError on a
    None user) now surface as 500s rather than being silently swallowed
    (WR-12). DB-level errors (FK violation, JSONB serialisation failure)
    are logged with structured context (WR-01) before being re-raised so
    monitoring can alert.

    Also forwards to syslog if configured (best-effort; syslog failure is
    not allowed to block the DB audit row).
    """
    now = datetime.now(UTC)
    try:
        log = AuditLog(
            tenant_id=user.tenant_id if user else uuid.UUID(int=0),
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=ip_address,
            created_at=now,
        )
        db.add(log)
    except SQLAlchemyError:
        _logger.warning(
            "audit_add_failed",
            extra={
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "user_id": str(user.id) if user else None,
            },
            exc_info=True,
        )
        raise

    # Forward to syslog/SIEM (best-effort — syslog outages must not block
    # the DB audit row, which is the system-of-record).
    if _syslog_enabled:
        _send_to_syslog(
            {
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "user_email": user.email if user else None,
                "user_id": str(user.id) if user else None,
                "tenant_id": str(user.tenant_id) if user else None,
                "details": details,
                "ip_address": ip_address,
                "timestamp": now.isoformat(),
                "timezone": _tenant_timezone,
            }
        )


# Tenant timezone for syslog events
_tenant_timezone: str = "UTC"


def set_tenant_timezone(tz: str) -> None:
    global _tenant_timezone
    _tenant_timezone = tz


async def get_audit_logs(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    action: str | None = None,
    resource_type: str | None = None,
    user_email: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Query audit logs with filters."""
    from sqlalchemy import func

    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_email:
        query = query.where(AuditLog.user_email.ilike(f"%{user_email}%"))

    # Count
    count_q = select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id)
    if action:
        count_q = count_q.where(AuditLog.action.ilike(f"%{action}%"))
    if resource_type:
        count_q = count_q.where(AuditLog.resource_type == resource_type)
    if user_email:
        count_q = count_q.where(AuditLog.user_email.ilike(f"%{user_email}%"))
    total = (await db.execute(count_q)).scalar_one()

    # Data
    query = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    return {
        "items": [
            {
                "id": str(r.id),
                "user_email": r.user_email,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "details": r.details,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }
