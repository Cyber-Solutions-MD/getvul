"""Tests for app.ai.budget — the fail-closed monthly AI spend guard (D-06)
and admin breach notification (D-08).

Spend is derived directly from AuditLog rows this phase's own audit writer
(`app.ai.audit.audit_log_ai_call`) already produces — no separate counter
table, no second source of truth (T-24-14) — so these tests seed AuditLog
rows directly rather than driving a real Anthropic call end-to-end.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.ai.budget import check_tenant_budget, notify_admins_budget_exceeded
from app.audit import AuditLog

# ── helpers ────────────────────────────────────────────────────────────────


async def _seed_ai_spend(db_session, tenant_id, cost_estimate_usd: float, action: str = "ai.explain.vuln") -> None:
    """Insert one ai.%-namespaced AuditLog row with a given cost, dated
    'now' (within the current month) — mirrors the shape
    `audit_log_ai_call()` actually writes."""
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=None,
        user_email="analyst@tenant-a.test",
        action=action,
        resource_type="vuln",
        resource_id=f"finding-{uuid.uuid4().hex[:8]}",
        details={"cost_estimate_usd": cost_estimate_usd, "status": "ok"},
        ip_address=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(log)
    await db_session.flush()


# ── check_tenant_budget — fail-closed (D-06) ──────────────────────────────


async def test_under_budget_returns_true(db_session, tenant_a):
    await _seed_ai_spend(db_session, tenant_a, 5.0)
    result = await check_tenant_budget(db_session, tenant_a, monthly_cap_usd=50.0)
    assert result is True


async def test_at_or_over_budget_fails_closed(db_session, tenant_a):
    await _seed_ai_spend(db_session, tenant_a, 30.0)
    await _seed_ai_spend(db_session, tenant_a, 20.0)
    # Total spend = 50.0, cap = 50.0 -> spend >= cap -> fail closed
    result = await check_tenant_budget(db_session, tenant_a, monthly_cap_usd=50.0)
    assert result is False


async def test_over_budget_fails_closed(db_session, tenant_a):
    await _seed_ai_spend(db_session, tenant_a, 75.0)
    result = await check_tenant_budget(db_session, tenant_a, monthly_cap_usd=50.0)
    assert result is False


async def test_no_cap_configured_is_unlimited(db_session, tenant_a):
    """A missing/None monthly_budget_usd is the tenant's own explicit choice
    to run unlimited (D-06) -- the independent per-call max_tokens=1024
    ceiling (D-07) still applies regardless, enforced elsewhere."""
    await _seed_ai_spend(db_session, tenant_a, 100_000.0)
    result = await check_tenant_budget(db_session, tenant_a, monthly_cap_usd=None)
    assert result is True


async def test_non_ai_spend_is_not_counted(db_session, tenant_a):
    """Only ai.%-namespaced audit rows count toward the AI budget -- an
    unrelated high-cost-looking detail on a non-'ai.' action must not
    trip the cap."""
    log = AuditLog(
        tenant_id=tenant_a,
        user_id=None,
        user_email="analyst@tenant-a.test",
        action="ticket.create",
        resource_type="ticket",
        resource_id=f"ticket-{uuid.uuid4().hex[:8]}",
        details={"cost_estimate_usd": 999.0},
        ip_address=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(log)
    await db_session.flush()

    result = await check_tenant_budget(db_session, tenant_a, monthly_cap_usd=50.0)
    assert result is True


# ── notify_admins_budget_exceeded — NOTIF-01 path (D-08) ──────────────────


async def test_admin_notified_on_breach(db_session, tenant_a, admin_user):
    with patch("app.ai.budget.create_notification", new_callable=AsyncMock) as mock_notify:
        await notify_admins_budget_exceeded(db_session, tenant_a)

    assert mock_notify.await_count >= 1
    call_kwargs = mock_notify.await_args_list[0].kwargs
    assert call_kwargs["send_email_flag"] is True
    assert call_kwargs["category"] == "ai_budget_exceeded"
    assert call_kwargs["severity"] == "high"
    assert call_kwargs["tenant_id"] == tenant_a
    assert call_kwargs["user_email"] == admin_user.email
    # T-24-15: metadata-only -- no key material, no prompt/output content.
    assert "sk-ant" not in call_kwargs.get("message", "")
    assert "sk-ant" not in call_kwargs.get("title", "")


async def test_non_admin_not_notified(db_session, tenant_a, analyst_user):
    """Only OWNER/ADMIN roles are notified -- a tenant with just an ANALYST
    user gets zero create_notification calls."""
    with patch("app.ai.budget.create_notification", new_callable=AsyncMock) as mock_notify:
        await notify_admins_budget_exceeded(db_session, tenant_a)

    mock_notify.assert_not_awaited()
