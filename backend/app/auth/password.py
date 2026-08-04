"""Password authentication — registration, login, password management, reset."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

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

# Phase 29 (WR-02): the strong floor enforced on the forced-rotation
# (must_change_password) path only. A tenant's own password_policy may be
# stricter, never weaker — see merge_policy_floor.
FORCED_ROTATION_POLICY = {
    "min_length": 12,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digit": True,
    "require_symbol": True,
    "history_count": 5,
}


def merge_policy_floor(base: dict[str, Any] | None, floor: dict[str, Any]) -> dict[str, Any]:
    """Merge a tenant policy with a strong floor — the STRICTEST value wins.

    Bools are OR'd (True wins); min_length and history_count take the max
    of base vs. floor. `base=None` is treated as DEFAULT_POLICY. This lets a
    tenant configure a *stricter* policy than the floor without ever being
    weakened below it.
    """
    effective_base: dict[str, Any] = {**DEFAULT_POLICY, **(base or {})}
    merged: dict[str, Any] = dict(effective_base)
    for key, floor_value in floor.items():
        base_value = effective_base.get(key)
        if isinstance(floor_value, bool):
            merged[key] = bool(base_value) or floor_value
        elif isinstance(floor_value, int):
            merged[key] = max(int(base_value or 0), floor_value)
        else:
            merged[key] = floor_value
    return merged


def password_similarity_ratio(a: str, b: str) -> float:
    """Return a symmetric similarity ratio in [0.0, 1.0] between two strings.

    Normalizes (casefold + strip) both inputs, THEN truncates each to 128
    chars before running difflib's O(n·m) SequenceMatcher — bounding CPU
    cost regardless of submitted input length (DoS mitigation). Returns 0.0
    if either side is empty after normalization.
    """
    norm_a = a.casefold().strip()[:128]
    norm_b = b.casefold().strip()[:128]
    if not norm_a or not norm_b:
        return 0.0
    return SequenceMatcher(None, norm_a, norm_b).ratio()


def is_too_similar(candidate: str, forbidden: Iterable[str], threshold: float = 0.7) -> str | None:
    """Return the first forbidden string too similar to `candidate`, else None.

    "Too similar" means password_similarity_ratio >= threshold. 0.7 mirrors
    Django's UserAttributeSimilarityValidator default. Empty forbidden
    entries are skipped.
    """
    for entry in forbidden:
        if not entry:
            continue
        if password_similarity_ratio(candidate, entry) >= threshold:
            return entry
    return None


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
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == tenant_slug, Tenant.is_active.is_(True)))
        ).scalar_one_or_none()
    else:
        # Try to find tenant by email domain
        tenant = (
            await db.execute(select(Tenant).where(Tenant.domain == domain, Tenant.is_active.is_(True)))
        ).scalar_one_or_none()

    if not tenant:
        return {"error": f"No organization found for domain '{domain}'. Contact your admin."}

    # Validate password against tenant policy
    policy = tenant.password_policy or DEFAULT_POLICY
    err = validate_password(password, policy)
    if err:
        return {"error": err}

    # Check if user already exists in this tenant
    existing = (
        await db.execute(select(User).where(User.tenant_id == tenant.id, User.email == email))
    ).scalar_one_or_none()
    if existing:
        return {"error": "User with this email already exists"}

    # Determine role — first user in tenant becomes OWNER
    user_count = (await db.execute(select(User).where(User.tenant_id == tenant.id).limit(1))).scalar_one_or_none()

    role = "OWNER" if user_count is None else "VIEWER"

    user = User(
        tenant_id=tenant.id,
        email=email,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
        allow_password_login=True,
        last_login_at=datetime.now(UTC),
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
        select(User)
        .where(User.email == email, User.is_active.is_(True))
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
    user.last_login_at = datetime.now(UTC)

    logger.info("password_login", email=email)

    return {"user": user, "tenant": tenant}


async def change_password(
    db: AsyncSession,
    user_id: uuid.UUID,
    current_password: str | None,
    new_password: str,
    policy_override: dict[str, Any] | None = None,
) -> dict:
    """Change user password with policy validation and history check.

    `policy_override` (Phase 29, WR-02): when provided, the effective policy
    is `merge_policy_floor(tenant.password_policy, policy_override)` — a
    strong floor that a tenant policy may exceed but never weaken. When
    omitted, behavior is unchanged (tenant.password_policy or DEFAULT_POLICY).
    """
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return {"error": "User not found"}

    # Get tenant policy
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    policy = (
        merge_policy_floor(tenant.password_policy, policy_override)
        if policy_override
        else (tenant.password_policy or DEFAULT_POLICY)
    )

    # Validate against policy
    err = validate_password(new_password, policy)
    if err:
        return {"error": err}

    # If user has a current password, verify it
    if user.password_hash and current_password and not verify_password(current_password, user.password_hash):
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
            history = history[-max(history_count, 10) :]
    user.password_history = history

    user.password_hash = hash_password(new_password)
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(user, "password_history")
    return {"message": "Password updated"}


# ── Password Reset ──

# In-memory token store (use Redis in production for multi-instance)
_reset_tokens: dict[str, dict] = {}
RESET_TOKEN_EXPIRY_MINUTES = 30


async def request_password_reset(db: AsyncSession, email: str) -> dict:
    """Generate a password reset token and send it via email.

    Always returns success to prevent email enumeration.
    """
    email = email.lower().strip()

    user = (await db.execute(select(User).where(User.email == email, User.is_active.is_(True)))).scalars().first()

    if not user:
        # Don't reveal whether email exists
        logger.info("password_reset_requested_unknown_email", email=email)
        return {"message": "If an account exists with that email, a reset link has been sent."}

    if not user.password_hash and not user.allow_password_login:
        # SSO-only user, no password to reset
        logger.info("password_reset_sso_only", email=email)
        return {"message": "If an account exists with that email, a reset link has been sent."}

    # Generate secure token
    token = secrets.token_urlsafe(32)
    _reset_tokens[token] = {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "email": email,
        "expires_at": datetime.now(UTC) + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES),
    }

    # Send email
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    smtp_cfg = getattr(tenant, "smtp_config", None)

    if smtp_cfg and smtp_cfg.get("enabled") and smtp_cfg.get("host"):
        from app.email import send_email

        send_email(
            smtp_config=smtp_cfg,
            to=[email],
            subject="GetVul — Password Reset",
            body=(
                f"A password reset was requested for your GetVul account.\n\n"
                f"Use this token to reset your password: {token}\n\n"
                f"Or open the app and enter the token on the password reset page.\n\n"
                f"This token expires in {RESET_TOKEN_EXPIRY_MINUTES} minutes.\n\n"
                f"If you did not request this, you can ignore this email."
            ),
        )
        logger.info("password_reset_email_sent", email=email)
    else:
        logger.warning("password_reset_no_smtp", email=email, token=token[:8])

    return {"message": "If an account exists with that email, a reset link has been sent."}


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> dict:
    """Validate reset token and set new password."""
    token_data = _reset_tokens.get(token)
    if not token_data:
        return {"error": "Invalid or expired reset token"}

    if datetime.now(UTC) > token_data["expires_at"]:
        _reset_tokens.pop(token, None)
        return {"error": "Reset token has expired"}

    user_id = uuid.UUID(token_data["user_id"])
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        _reset_tokens.pop(token, None)
        return {"error": "User not found"}

    # Validate against tenant policy
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    policy = tenant.password_policy or DEFAULT_POLICY
    err = validate_password(new_password, policy)
    if err:
        return {"error": err}

    # Check password history
    history_count = policy.get("history_count", 0)
    if history_count > 0 and check_password_history(new_password, user.password_history, history_count):
        return {"error": f"Cannot reuse one of your last {history_count} passwords"}

    # Save old hash to history
    history = list(user.password_history or [])
    if user.password_hash:
        history.append(user.password_hash)
        if len(history) > max(history_count, 10):
            history = history[-max(history_count, 10) :]
    user.password_history = history
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(user, "password_history")

    # Set new password
    user.password_hash = hash_password(new_password)

    # Invalidate token
    _reset_tokens.pop(token, None)

    # Clean up expired tokens
    now = datetime.now(UTC)
    expired = [k for k, v in _reset_tokens.items() if now > v["expires_at"]]
    for k in expired:
        _reset_tokens.pop(k, None)

    logger.info("password_reset_completed", email=user.email)
    return {"message": "Password has been reset successfully. You can now sign in."}
