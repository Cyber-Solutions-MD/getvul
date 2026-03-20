"""Password authentication — registration, login, password management."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import bcrypt
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenants.models import Tenant, User

logger = structlog.get_logger()


DEFAULT_POLICY = {
    "min_length": 8,
    "require_uppercase": False,
    "require_lowercase": False,
    "require_digit": False,
    "require_symbol": False,
    "history_count": 0,
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def validate_password(password: str, policy: dict | None = None) -> str | None:
    """Validate password against policy. Returns error message or None."""
    p = {**DEFAULT_POLICY, **(policy or {})}

    if len(password) < p["min_length"]:
        return f"Password must be at least {p['min_length']} characters"
    if p["require_uppercase"] and not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if p["require_lowercase"] and not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter"
    if p["require_digit"] and not any(c.isdigit() for c in password):
        return "Password must contain at least one digit"
    if p["require_symbol"] and not any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/~`" for c in password):
        return "Password must contain at least one symbol (!@#$%...)"
    return None


def check_password_history(password: str, history: list | None, count: int) -> bool:
    """Check if password was used recently. Returns True if reused."""
    if not history or count <= 0:
        return False
    for old_hash in history[-count:]:
        try:
            if bcrypt.checkpw(password.encode(), old_hash.encode()):
                return True
        except Exception:
            continue
    return False


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    display_name: str,
    tenant_slug: str | None = None,
    tenant_name: str | None = None,
) -> dict:
    """Register a new user with email/password.

    If tenant_slug is provided, joins that tenant.
    If tenant_name is provided and no tenant exists for the email domain, creates a new one.
    """
    email = email.lower().strip()
    if not email or "@" not in email:
        return {"error": "Valid email is required"}

    domain = email.split("@")[1]

    # Find tenant — must already exist (no auto-creation)
    tenant = None
    if tenant_slug:
        tenant = (await db.execute(
            select(Tenant).where(Tenant.slug == tenant_slug, Tenant.is_active.is_(True))
        )).scalar_one_or_none()
    else:
        # Try to find tenant by email domain
        tenant = (await db.execute(
            select(Tenant).where(Tenant.domain == domain, Tenant.is_active.is_(True))
        )).scalar_one_or_none()

    if not tenant:
        return {"error": f"No organization found for domain '{domain}'. Contact your admin."}

    # Validate password against tenant policy
    policy = tenant.password_policy or DEFAULT_POLICY
    err = validate_password(password, policy)
    if err:
        return {"error": err}

    # Check if user already exists in this tenant
    existing = (await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.email == email)
    )).scalar_one_or_none()
    if existing:
        return {"error": "User with this email already exists"}

    # Determine role — first user in tenant becomes OWNER
    user_count = (await db.execute(
        select(User).where(User.tenant_id == tenant.id).limit(1)
    )).scalar_one_or_none()

    role = "OWNER" if user_count is None else "VIEWER"

    user = User(
        tenant_id=tenant.id,
        email=email,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
        allow_password_login=True,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info("user_registered", email=email, tenant=tenant.slug, role=role)

    return {
        "user": user,
        "tenant": tenant,
    }


async def login_with_password(
    db: AsyncSession,
    email: str,
    password: str,
) -> dict:
    """Authenticate with email/password."""
    email = email.lower().strip()

    # Find user — if multiple (different tenants), prefer the one with a password
    result = await db.execute(
        select(User).where(User.email == email, User.is_active.is_(True))
        .order_by(User.password_hash.isnot(None).desc(), User.last_login_at.desc().nullslast())
    )
    user = result.scalars().first()
    if user is None:
        return {"error": "Invalid email or password"}

    if not user.is_active:
        return {"error": "Account is deactivated"}

    # Check if password login is allowed
    if not user.password_hash:
        return {"error": "Password login not set up. Use SSO to login."}

    # Check tenant SSO enforcement
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()

    if tenant.sso_enforced and not user.allow_password_login:
        return {"error": "SSO is enforced for this organization. Use SSO to login."}

    # Verify password
    if not verify_password(password, user.password_hash):
        return {"error": "Invalid email or password"}

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)

    logger.info("password_login", email=email)

    return {"user": user, "tenant": tenant}


async def change_password(
    db: AsyncSession,
    user_id: uuid.UUID,
    current_password: str | None,
    new_password: str,
) -> dict:
    """Change user password with policy validation and history check."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return {"error": "User not found"}

    # Get tenant policy
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    policy = tenant.password_policy or DEFAULT_POLICY

    # Validate against policy
    err = validate_password(new_password, policy)
    if err:
        return {"error": err}

    # If user has a current password, verify it
    if user.password_hash and current_password:
        if not verify_password(current_password, user.password_hash):
            return {"error": "Current password is incorrect"}

    # Check password history
    history_count = policy.get("history_count", 0)
    if history_count > 0 and check_password_history(new_password, user.password_history, history_count):
        return {"error": f"Cannot reuse one of your last {history_count} passwords"}

    # Save old hash to history
    history = list(user.password_history or [])
    if user.password_hash:
        history.append(user.password_hash)
        # Keep only the last N
        if len(history) > max(history_count, 10):
            history = history[-max(history_count, 10):]
    user.password_history = history

    user.password_hash = hash_password(new_password)
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(user, "password_history")
    return {"message": "Password updated"}
