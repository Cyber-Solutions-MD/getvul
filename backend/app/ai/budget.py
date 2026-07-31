"""Fail-closed monthly AI budget guard (D-06) + admin breach notification (D-08).

`check_tenant_budget()` derives month-to-date spend directly from the
existing AUDIT-01 `audit_logs` table (no separate counter table, no second
source of truth) — every `ai.`-namespaced audit row this phase's callers
write (see `app.ai.audit.audit_log_ai_call`) already carries
`details["cost_estimate_usd"]`, so budget accounting is a SUM over rows the
system itself already writes (T-24-14: a call that never wrote an audit row
also never ran, so there is nothing to bypass by forging a cost figure).

FAIL-CLOSED: once a cap IS configured, month-to-date spend >= cap returns
False and the caller must treat that as the typed "AI budget exceeded"
panel state (D-08) — never silently degrade to some other behavior. A
missing/None `monthly_cap_usd` is the tenant's own explicit choice (the
`ConnectorConfig.config["monthly_budget_usd"]` field is optional per Plan
01's wizard) to run unlimited; the independent per-call `max_tokens=1024`
ceiling (D-07, enforced in Plan 04) still bounds every individual call
regardless of whether a monthly cap is configured.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import AuditLog
from app.notifications.service import create_notification
from app.tenants.models import User

AI_BUDGET_EXCEEDED_TITLE = "AI budget exceeded"
AI_BUDGET_EXCEEDED_MESSAGE = (
    "This tenant's monthly AI spend cap has been reached. AI-assisted "
    "explanations are paused until next month, or raise the cap in the AI "
    "connector's settings."
)


async def get_month_to_date_spend(db: AsyncSession, tenant_id: uuid.UUID) -> float:
    """Sum this month's `ai.%`-namespaced `AuditLog.details['cost_estimate_usd']`
    for `tenant_id` (Phase 26 Plan 07) -- extracted from `check_tenant_budget()`
    so a batch pre-submission estimate (`would_exceed_budget_for_batch`) can
    add its own projected cost to the SAME already-spent figure without a
    second, duplicated SUM query."""
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = (
        await db.execute(
            select(func.sum(AuditLog.details["cost_estimate_usd"].as_float())).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.action.like("ai.%"),
                AuditLog.created_at >= month_start,
            )
        )
    ).scalar_one_or_none() or 0.0
    return spent


async def check_tenant_budget(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    monthly_cap_usd: float | None,
) -> bool:
    """Return True if the tenant is under its monthly AI spend cap.

    Fail-closed (D-06): once `monthly_cap_usd` is configured, month-to-date
    spend >= cap returns False. `monthly_cap_usd=None` (no cap configured)
    is the tenant's own explicit choice and returns True unconditionally.

    Delegates to `get_month_to_date_spend()` (Phase 26 Plan 07 extraction) --
    the public signature and fail-closed comparison are UNCHANGED, so every
    existing caller (`explain.py::_run_explain_stream()` and every
    `explain_*.py` route that transitively calls it) needs zero edits.
    """
    if monthly_cap_usd is None:
        return True

    spent = await get_month_to_date_spend(db, tenant_id)
    return spent < monthly_cap_usd


async def would_exceed_budget_for_batch(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    monthly_cap_usd: float | None,
    estimated_batch_cost_usd: float,
) -> bool:
    """D-07: fail-closed pre-submission check for a Message Batch's
    ESTIMATED cost (Phase 26 Plan 07) -- called BEFORE
    `client.messages.batches.create()`, never after. Returns True (the
    caller must SKIP the batch -- notify admins, audit
    `batch_skipped_budget_exceeded`, insert NO `AiBatchJob` row, never a
    silent partial) iff a cap IS configured and month-to-date spend PLUS
    the projected batch cost would meet or exceed it.

    `monthly_cap_usd=None` (no cap configured) never skips -- mirrors
    `check_tenant_budget()`'s own unconditional-True precedent for the
    identical input, so a tenant who has explicitly chosen "unlimited"
    is treated identically on both the interactive and batch paths.
    """
    if monthly_cap_usd is None:
        return False

    spent = await get_month_to_date_spend(db, tenant_id)
    return (spent + estimated_batch_cost_usd) >= monthly_cap_usd


async def notify_admins_budget_exceeded(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Alert every active OWNER/ADMIN user in the tenant that the monthly AI
    budget has been exceeded (D-08) — in-app + SMTP via the existing
    NOTIF-01 `create_notification(..., send_email_flag=True)` path,
    mirroring `notifications/alerts.py`'s query -> threshold -> notify
    shape (e.g. `_check_sla_breaches`).

    Notifies each admin individually (`user_id`/`user_email` set to that
    admin) rather than one broadcast row, so `send_email_flag=True`
    actually reaches every admin's inbox, not just a single arbitrary one.
    The notification carries no key material and no prompt/output content
    — metadata only (T-24-15).
    """
    admins = (
        (
            await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.is_active.is_(True),
                    User.role.in_(["OWNER", "ADMIN"]),
                )
            )
        )
        .scalars()
        .all()
    )

    for admin in admins:
        await create_notification(
            db,
            tenant_id=tenant_id,
            title=AI_BUDGET_EXCEEDED_TITLE,
            message=AI_BUDGET_EXCEEDED_MESSAGE,
            severity="high",
            category="ai_budget_exceeded",
            resource_type="tenant",
            resource_id=str(tenant_id),
            user_id=admin.id,
            user_email=admin.email,
            send_email_flag=True,
        )
