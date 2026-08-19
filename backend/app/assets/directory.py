"""Directory (IdP/MDM/HR) user resolution for an asset.

Extracted from `app.assets.router._get_directory_user` (Phase 40 Plan 02,
research A5) so the notifications/alerting layer (`app.notifications.alerts`)
can resolve an asset's owner without importing the assets router module
(which would pull in FastAPI route registration + Pydantic request models
that have nothing to do with alerting). Behavior is unchanged from the
original — moved verbatim, `assets/router.py` re-imports this symbol so its
existing callers (GET /assets/{id}, PATCH /assets/{id}/owner) keep working.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.assets.models import Asset


async def get_directory_user(db: AsyncSession, tenant_id: uuid.UUID, asset: Asset) -> dict[str, Any] | None:
    """Find matching directory user for an asset by email.

    Precedence: MDM `humaans_email` -> `assigned_user` -> `last_login_user`
    (first email that resolves to a real, tenant-scoped `User` row wins).
    """
    from app.tenants.models import User

    # Try to match by humaans_email, assigned_user email, or last_login_user
    emails_to_try = []
    mdm = asset.mdm_details or {}
    if mdm.get("humaans_email"):
        emails_to_try.append(mdm["humaans_email"].lower())
    if asset.assigned_user and "@" in asset.assigned_user:
        emails_to_try.append(asset.assigned_user.lower())
    if asset.last_login_user and "@" in asset.last_login_user:
        emails_to_try.append(asset.last_login_user.lower())

    if not emails_to_try:
        return None

    result = await db.execute(
        select(User)
        .where(
            User.tenant_id == tenant_id,
            or_(*[User.email == e for e in emails_to_try]),
        )
        .limit(1)
    )
    u = result.scalar_one_or_none()
    if not u:
        return None

    return {
        "email": u.email,
        "display_name": u.display_name,
        "department": u.department,
        "job_title": u.job_title,
        "avatar_url": u.avatar_url,
        "groups": u.groups or [],
        "idp_source": u.idp_source,
        "is_active": u.is_active,
        "role": u.role,
    }
