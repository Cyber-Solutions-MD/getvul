"""Tenant and user management routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_, select, update

from app.audit import audit
from app.auth.rbac import require_admin, require_owner
from app.auth.schemas import CurrentUser
from app.dependencies import AuthenticatedUser, DBSession
from app.tenants.models import Tenant, User
from app.tenants.schemas import TenantResponse, UserResponse, UserRoleUpdate

router = APIRouter()


@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(db: DBSession, user: AuthenticatedUser):
    """Get the current user's tenant info."""
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """List app users (with login access) in the tenant. Requires Admin role.

    Excludes directory-only users (synced from IdP with no password and VIEWER role).
    To see all directory users, use GET /api/v1/users/directory.
    """
    result = await db.execute(
        select(User).where(
            User.tenant_id == user.tenant_id,
            or_(
                User.password_hash.isnot(None),
                User.allow_password_login.is_(True),
                User.role.in_(["OWNER", "ADMIN", "ANALYST"]),
            ),
        ).order_by(User.email)
    )
    return result.scalars().all()


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Update a user's role. Requires Owner role."""
    if body.role not in ("OWNER", "ADMIN", "ANALYST", "VIEWER"):
        raise HTTPException(status_code=400, detail="Invalid role")

    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = target_user.role
    target_user.role = body.role
    await audit(
        db,
        user,
        "user.role_change",
        "user",
        str(user_id),
        {"email": target_user.email, "old_role": old_role, "new_role": body.role},
    )
    await db.flush()
    return target_user


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Deactivate a user. Requires Owner role."""
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    result = await db.execute(
        update(User).where(User.id == user_id, User.tenant_id == user.tenant_id).values(is_active=False)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await audit(db, user, "user.deactivate", "user", str(user_id))
    return {"message": "User deactivated"}


@router.get("/settings")
async def get_tenant_settings(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Get tenant settings including SSO enforcement."""
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    return {
        "sso_enforced": tenant.sso_enforced,
        "idp_provider": tenant.idp_provider,
        "domain": tenant.domain,
        "timezone": tenant.timezone,
        "password_policy": tenant.password_policy
        or {
            "min_length": 8,
            "require_uppercase": False,
            "require_lowercase": False,
            "require_digit": False,
            "require_symbol": False,
            "history_count": 0,
        },
        "syslog_config": tenant.syslog_config,
        "smtp_config": _safe_smtp(getattr(tenant, "smtp_config", None)),
        "sla_config": getattr(tenant, "sla_config", None),
        "branding": getattr(tenant, "branding", None),
    }


def _safe_smtp(cfg: dict | None) -> dict | None:
    """Return smtp_config with password masked for the frontend."""
    if not cfg:
        return None
    safe = dict(cfg)
    if safe.get("password"):
        safe["password"] = "••••••••"
    return safe


@router.patch("/settings")
async def update_tenant_settings(
    body: dict,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Update tenant settings. Requires Owner role."""
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()

    if "sso_enforced" in body:
        if body["sso_enforced"] and (not tenant.idp_provider or tenant.idp_provider == "LOCAL"):
            raise HTTPException(
                400, "Cannot enforce SSO without an identity provider configured. Select Google or Azure first."
            )
        tenant.sso_enforced = bool(body["sso_enforced"])
    if "name" in body:
        tenant.name = body["name"]
    if "domain" in body:
        tenant.domain = body["domain"]
    if "idp_provider" in body:
        tenant.idp_provider = body["idp_provider"]
        if body["idp_provider"] == "LOCAL" and tenant.sso_enforced:
            tenant.sso_enforced = False  # Auto-disable SSO when switching to LOCAL
    if "slug" in body:
        tenant.slug = body["slug"]
    if "timezone" in body:
        tenant.timezone = body["timezone"]
    if "password_policy" in body:
        from sqlalchemy.orm.attributes import flag_modified as _fm

        tenant.password_policy = body["password_policy"]
        _fm(tenant, "password_policy")
    if "syslog_config" in body:
        from sqlalchemy.orm.attributes import flag_modified

        tenant.syslog_config = body["syslog_config"]
        flag_modified(tenant, "syslog_config")

        # Apply syslog config
        from app.audit import configure_syslog, disable_syslog

        cfg = body["syslog_config"]
        if cfg and cfg.get("enabled") and cfg.get("host"):
            configure_syslog(
                host=cfg["host"],
                port=int(cfg.get("port", 514)),
                protocol=cfg.get("protocol", "udp"),
                facility=cfg.get("facility", "local0"),
            )
        else:
            disable_syslog()

    if "sla_config" in body:
        from sqlalchemy.orm.attributes import flag_modified as _fm_sla

        tenant.sla_config = body["sla_config"]
        _fm_sla(tenant, "sla_config")

    if "branding" in body:
        from sqlalchemy.orm.attributes import flag_modified as _fm_brand

        tenant.branding = body["branding"]
        _fm_brand(tenant, "branding")

    if "smtp_config" in body:
        from sqlalchemy.orm.attributes import flag_modified as _fm_smtp

        new_smtp = body["smtp_config"]
        # If password is masked, keep the existing one
        if new_smtp and new_smtp.get("password") == "••••••••" and tenant.smtp_config:
            new_smtp["password"] = tenant.smtp_config.get("password", "")
        tenant.smtp_config = new_smtp
        _fm_smtp(tenant, "smtp_config")

    # Audit log all changed fields (mask smtp password)
    changed = {k: v for k, v in body.items() if k not in ("syslog_config", "smtp_config") or (v and v.get("enabled"))}
    await audit(db, user, "settings.update", "tenant", str(tenant.id), changed)

    await db.commit()
    return {"message": "Settings updated"}


@router.post("/branding/logo")
async def upload_logo(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
    file: UploadFile = File(...),
):
    """Upload a logo image for PDF reports (PNG/JPG, max 500KB)."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image (PNG or JPG)")

    content = await file.read()
    if len(content) > 512_000:
        raise HTTPException(400, "Logo must be under 500KB")

    from pathlib import Path

    logo_dir = Path("/app/data/branding")
    logo_dir.mkdir(parents=True, exist_ok=True)

    ext = "png" if "png" in (file.content_type or "") else "jpg"
    logo_path = logo_dir / f"{user.tenant_id}.{ext}"
    logo_path.write_bytes(content)

    # Update tenant branding
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    branding = dict(tenant.branding or {})
    branding["logo_path"] = str(logo_path)
    tenant.branding = branding
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(tenant, "branding")
    await db.commit()

    return {"message": "Logo uploaded", "path": str(logo_path)}


@router.patch("/users/{user_id}/allow-password")
async def toggle_user_password_login(
    user_id: uuid.UUID,
    body: dict,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Toggle whether a user can use password login when SSO is enforced. Requires Owner."""
    target = (
        await db.execute(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")

    target.allow_password_login = bool(body.get("allow", True))
    await audit(
        db,
        user,
        "user.password_toggle",
        "user",
        str(user_id),
        {"email": target.email, "allow": target.allow_password_login},
    )
    await db.commit()
    return {"message": "Updated", "allow_password_login": target.allow_password_login}


@router.post("/users")
async def create_user(
    body: dict,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Create a new user in the tenant. Requires Owner role.

    If user with this email already exists in the tenant, updates their role and password instead.
    """
    from app.auth.password import hash_password

    email = (body.get("email") or "").lower().strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email is required")

    display_name = body.get("display_name", email.split("@")[0])
    role = body.get("role", "VIEWER")
    password = body.get("password", "")

    # Check if user already exists in this tenant
    existing = (
        await db.execute(select(User).where(User.tenant_id == user.tenant_id, User.email == email))
    ).scalar_one_or_none()

    if existing:
        # Update existing user
        if display_name:
            existing.display_name = display_name
        if role:
            existing.role = role
        if password and len(password) >= 8:
            existing.password_hash = hash_password(password)
        existing.is_active = True
        existing.allow_password_login = True
        await db.commit()
        await audit(db, user, "user.update", "user", str(existing.id), {"email": email, "role": role})
        return {"message": f"User {email} updated", "id": str(existing.id), "created": False}

    # Create new user
    new_user = User(
        tenant_id=user.tenant_id,
        email=email,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password) if password and len(password) >= 8 else None,
        allow_password_login=True,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()
    await db.commit()
    await audit(db, user, "user.create", "user", str(new_user.id), {"email": email, "role": role})
    return {"message": f"User {email} created", "id": str(new_user.id), "created": True}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: dict,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Update user display name or email. Requires Owner role."""
    target = (
        await db.execute(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")

    changes = {}
    if "display_name" in body:
        target.display_name = body["display_name"]
        changes["display_name"] = body["display_name"]
    if "email" in body and body["email"]:
        target.email = body["email"].lower().strip()
        changes["email"] = target.email

    await audit(db, user, "user.update", "user", str(user_id), changes)
    await db.commit()
    return {"message": "Updated"}


@router.get("/audit-log")
async def get_audit_log(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
    action: str | None = None,
    resource_type: str | None = None,
    user_email: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """Get audit log entries. Requires Admin role."""
    from app.audit import get_audit_logs

    return await get_audit_logs(db, user.tenant_id, action, resource_type, user_email, page, page_size)


@router.get("/groups")
async def list_groups(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """List all groups and their member counts."""

    # Get all unique groups across users
    result = await db.execute(
        select(User).where(
            User.tenant_id == user.tenant_id,
            User.groups.isnot(None),
        )
    )
    users_with_groups = result.scalars().all()

    groups_map: dict[str, list[dict]] = {}
    for u in users_with_groups:
        for g in u.groups or []:
            if g not in groups_map:
                groups_map[g] = []
            groups_map[g].append(
                {
                    "id": str(u.id),
                    "email": u.email,
                    "display_name": u.display_name,
                    "role": u.role,
                    "department": u.department,
                }
            )

    return [
        {"name": name, "member_count": len(members), "members": members}
        for name, members in sorted(groups_map.items(), key=lambda x: -len(x[1]))
    ]


@router.get("/groups/export")
async def export_groups_csv(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Export all groups and their members as CSV."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    result = await db.execute(
        select(User).where(
            User.tenant_id == user.tenant_id,
            User.groups.isnot(None),
        )
    )
    users_with_groups = result.scalars().all()

    groups_map: dict[str, list[dict]] = {}
    for u in users_with_groups:
        for g in u.groups or []:
            if g not in groups_map:
                groups_map[g] = []
            groups_map[g].append(
                {
                    "email": u.email,
                    "display_name": u.display_name or "",
                    "department": u.department or "",
                    "job_title": u.job_title or "",
                    "role": u.role,
                    "is_active": u.is_active,
                }
            )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Group", "Member Email", "Display Name", "Department", "Job Title", "Role", "Active"])

    for group_name in sorted(groups_map.keys()):
        for m in sorted(groups_map[group_name], key=lambda x: x["email"]):
            writer.writerow(
                [
                    group_name,
                    m["email"],
                    m["display_name"],
                    m["department"],
                    m["job_title"],
                    m["role"],
                    "Yes" if m["is_active"] else "No",
                ]
            )

    content = output.getvalue()

    from datetime import UTC, datetime

    filename = f"groups_export_{datetime.now(UTC).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Permanently delete a user. Requires Owner role."""
    if user_id == user.id:
        raise HTTPException(400, "Cannot delete yourself")

    target = (
        await db.execute(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")

    email = target.email
    await audit(db, user, "user.delete", "user", str(user_id), {"email": email})
    await db.delete(target)
    await db.commit()
    return {"message": f"User {email} deleted"}
