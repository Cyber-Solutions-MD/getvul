"""Read-only AI usage/cost aggregation endpoint (AIE-04).

`GET /api/v1/ai/usage` is `require_admin`-gated and aggregates the EXISTING
`ai.*`-namespaced `AuditLog` rows every explain route / batch prewarm already
writes via `audit_log_ai_call()` (D-08 -- no new telemetry pipeline, no new
table). It is the single source of the derived `breaker_tripped` boolean the
admin usage/cost pane (Plan 04) reads (D-09) -- computed with the EXACT same
comparison `check_tenant_budget()` uses, never a second, independently
re-derived one -- plus a fixed 6-row per-capability usage breakdown and a
degraded-calls footnote count.

Batch vs on-demand prioritization is split on `user_email ==
'system:scheduler'` (set at `batch.py:267,318,511`), NEVER on `status` -- a
successful batch call audits `status="ok"`, byte-identical to a successful
on-demand call. Splitting on status would misattribute nearly all real batch
spend into the on-demand row (28-RESEARCH.md Pitfall 5 / 28-UI-SPEC.md Meter
Contract).

T-28-03/T-28-04 (threat model): every query below is scoped by
`AuditLog.tenant_id == user.tenant_id` (no cross-tenant leakage) and the
route itself is gated by `Depends(require_admin)` (the authoritative,
backend-side RBAC gate -- never a UI-only check).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.ai.budget import get_month_to_date_spend
from app.ai.explain import get_model_and_budget
from app.ai.tenant_keys import get_tenant_anthropic_key
from app.audit import AuditLog
from app.auth.rbac import require_admin
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession

router = APIRouter()

# The literal user_email a batch-originated audit_log_ai_call() write always
# carries (batch.py:267,318,511) -- the ONLY reliable discriminator between
# rows 5/6 below, since a successful batch call's `status` is "ok", identical
# to a successful on-demand call's.
_SCHEDULER_USER_EMAIL = "system:scheduler"

# (resource_type, is_batch) -- is_batch: None = no user_email split (rows
# 1-4), True/False = the user_email discriminator for the two prioritization
# rows (28-UI-SPEC.md Meter/Table Contract, 6 fixed rows). NEVER
# `status LIKE 'batch_%'` here -- see module docstring.
_CAPABILITY_ROWS: list[tuple[str, bool | None]] = [
    ("vuln", None),
    ("host", None),
    ("remediation", None),
    ("remediation-guidance", None),
    ("prioritization", False),  # on-demand: user_email != "system:scheduler"
    ("prioritization", True),  # batch: user_email == "system:scheduler"
]


@router.get("/usage")
async def get_ai_usage(db: DBSession, user: Annotated[CurrentUser, Depends(require_admin)]) -> dict[str, Any]:
    """Month-to-date AI usage/cost aggregation for the caller's own tenant."""
    model, monthly_cap_usd = await get_model_and_budget(db, user.tenant_id)
    spent = await get_month_to_date_spend(db, user.tenant_id)
    # The EXACT comparison check_tenant_budget() uses (app/ai/budget.py) --
    # never a second, independently-authored comparison (D-09).
    breaker_tripped = monthly_cap_usd is not None and spent >= monthly_cap_usd
    configured = await get_tenant_anthropic_key(db, user.tenant_id) is not None

    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    capability_breakdown: list[dict[str, Any]] = []
    for resource_type, is_batch in _CAPABILITY_ROWS:
        conditions: list[Any] = [
            AuditLog.tenant_id == user.tenant_id,
            AuditLog.action.like("ai.%"),
            AuditLog.resource_type == resource_type,
            AuditLog.created_at >= month_start,
        ]
        if is_batch is True:
            conditions.append(AuditLog.user_email == _SCHEDULER_USER_EMAIL)
        elif is_batch is False:
            conditions.append(AuditLog.user_email != _SCHEDULER_USER_EMAIL)

        result = await db.execute(
            select(
                func.count().label("calls"),
                func.coalesce(func.sum(AuditLog.details["cost_estimate_usd"].as_float()), 0.0).label("cost"),
                func.coalesce(
                    func.sum(
                        AuditLog.details["input_tokens"].as_integer() + AuditLog.details["output_tokens"].as_integer()
                    ),
                    0,
                ).label("tokens"),
            ).where(*conditions)
        )
        row = result.one()
        capability_breakdown.append(
            {
                "resource_type": resource_type,
                "is_batch": is_batch,
                "calls": row.calls,
                "cost_usd": row.cost,
                "tokens": row.tokens,
            }
        )

    # 28-UI-SPEC.md Meter/Table Contract (~line 153) EXACT formula: counts
    # ai.* rows whose status is neither "ok" NOR a batch_-prefixed skip/error
    # status (those are already surfaced by the breaker banner elsewhere) --
    # a bare `status != "ok"` would double-count batch_skipped_budget_
    # exceeded/batch_errored/etc rows here.
    degraded_result = await db.execute(
        select(func.count()).where(
            AuditLog.tenant_id == user.tenant_id,
            AuditLog.action.like("ai.%"),
            AuditLog.created_at >= month_start,
            AuditLog.details["status"].as_string() != "ok",
            AuditLog.details["status"].as_string().notlike("batch_%"),
        )
    )
    degraded_calls_count = degraded_result.scalar_one()

    return {
        "configured": configured,
        "model": model,
        "monthly_budget_usd": monthly_cap_usd,
        "spent_this_month_usd": spent,
        "breaker_tripped": breaker_tripped,
        "capability_breakdown": capability_breakdown,
        "degraded_calls_count": degraded_calls_count,
    }
