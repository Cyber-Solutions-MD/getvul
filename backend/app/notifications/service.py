"""Notification service — create, list, read, delete notifications."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.email import send_email
from app.notifications.models import Notification
from app.tenants.models import Tenant

logger = structlog.get_logger()


async def create_notification(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    title: str,
    message: str,
    severity: str,
    category: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    user_id: uuid.UUID | None = None,
    details: dict | None = None,
    send_email_flag: bool = False,
    user_email: str | None = None,
) -> Notification:
    """Create a notification and optionally send an email."""
    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        message=message,
        severity=severity,
        category=category,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    db.add(notification)
    await db.flush()

    if send_email_flag and user_email:
        await _send_notification_email(db, tenant_id, user_email, title, message, category)
        notification.email_sent = True
        notification.email_sent_at = datetime.now(UTC)

    logger.info(
        "notification_created",
        notification_id=str(notification.id),
        tenant_id=str(tenant_id),
        category=category,
        severity=severity,
    )
    return notification


async def get_notifications(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    is_read: bool | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Return paginated notifications for a user (includes broadcasts)."""
    conditions = [
        Notification.tenant_id == tenant_id,
        # User-specific or broadcast (user_id IS NULL)
        (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
    ]
    if is_read is not None:
        conditions.append(Notification.is_read == is_read)
    if category:
        conditions.append(Notification.category == category)

    # Total count
    count_q = select(func.count(Notification.id)).where(and_(*conditions))
    total = (await db.execute(count_q)).scalar_one()

    # Items
    items_q = (
        select(Notification)
        .where(and_(*conditions))
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(items_q)).scalars().all()

    return {
        "items": [_serialize(n) for n in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


async def get_unread_count(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
    """Return count of unread notifications for a user."""
    q = select(func.count(Notification.id)).where(
        Notification.tenant_id == tenant_id,
        (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
        Notification.is_read == False,  # noqa: E712
    )
    return (await db.execute(q)).scalar_one()


async def mark_read(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    """Mark a single notification as read. Returns True if updated."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.tenant_id == tenant_id,
            (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
        )
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    return result.rowcount > 0


async def mark_all_read(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
    """Mark all unread notifications as read for a user. Returns count updated."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.tenant_id == tenant_id,
            (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    return result.rowcount


async def delete_notification(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
) -> bool:
    """Delete a notification. Returns True if deleted."""
    q = select(Notification).where(
        Notification.id == notification_id,
        Notification.tenant_id == tenant_id,
        (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
    )
    notification = (await db.execute(q)).scalar_one_or_none()
    if not notification:
        return False
    await db.delete(notification)
    return True


async def _send_notification_email(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_email: str,
    title: str,
    message: str,
    category: str,
) -> None:
    """Check SMTP config and send notification email if enabled."""
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    smtp_cfg = tenant.smtp_config
    if smtp_cfg and smtp_cfg.get("enabled") and smtp_cfg.get("host"):
        result = send_email(
            smtp_config=smtp_cfg,
            to=[user_email],
            subject=f"GetVul Alert: {title}",
            body=message,
        )
        if not result.get("ok"):
            logger.warning(
                "notification_email_failed",
                tenant_id=str(tenant_id),
                to=user_email,
                category=category,
                error=result.get("error"),
            )
    else:
        logger.debug("notification_email_skipped", tenant_id=str(tenant_id), reason="smtp_not_configured")


def _serialize(n: Notification) -> dict:
    """Serialize a Notification to a dict for API responses."""
    return {
        "id": str(n.id),
        "tenant_id": str(n.tenant_id),
        "user_id": str(n.user_id) if n.user_id else None,
        "title": n.title,
        "message": n.message,
        "severity": n.severity,
        "category": n.category,
        "resource_type": n.resource_type,
        "resource_id": n.resource_id,
        "is_read": n.is_read,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "email_sent": n.email_sent,
        "details": n.details,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
    }
