"""Notification API routes — list, read, delete in-app notifications."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.rbac import require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.notifications.service import (
    delete_notification,
    get_notifications,
    get_unread_count,
    mark_all_read,
    mark_read,
)

router = APIRouter(prefix="", tags=["Notifications"])


@router.get("")
async def list_notifications(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    is_read: bool | None = Query(None),
):
    """List notifications for the current user (paginated, filterable)."""
    return await get_notifications(
        db,
        user.tenant_id,
        user.id,
        is_read=is_read,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count")
async def unread_count(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Return the count of unread notifications (for badge display)."""
    count = await get_unread_count(db, user.tenant_id, user.id)
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def read_notification(
    notification_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Mark a single notification as read."""
    updated = await mark_read(db, user.tenant_id, user.id, notification_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return {"ok": True}


@router.post("/read-all")
async def read_all_notifications(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Mark all notifications as read for the current user."""
    count = await mark_all_read(db, user.tenant_id, user.id)
    await db.commit()
    return {"ok": True, "updated": count}


@router.delete("/{notification_id}")
async def remove_notification(
    notification_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Delete a single notification."""
    deleted = await delete_notification(db, user.tenant_id, user.id, notification_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return {"ok": True}
