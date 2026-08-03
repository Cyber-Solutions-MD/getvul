"""Tests for GET /api/v1/ai/usage (AIE-04) -- RBAC, tenant isolation, the
user_email batch/on-demand split, and the derived breaker_tripped boolean.

Seeds ai.*-namespaced AuditLog rows directly (adapted from
test_ai_budget.py::_seed_ai_spend to additionally vary resource_type/
user_email/status/tokens, which this endpoint's 6-row breakdown + degraded-
count formula both need) rather than driving a real Anthropic call
end-to-end -- this endpoint is a pure aggregation over rows
audit_log_ai_call() already writes (D-08: no new telemetry). Reuses
test_ai_budget_coverage.py's `_seed_anthropic_connector` verbatim (same
exact signature this file needs) rather than re-deriving it.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.audit import AuditLog
from tests.test_ai_budget_coverage import _seed_anthropic_connector  # reuse, don't re-derive

# The literal user_email a batch-originated audit_log_ai_call() write always
# carries (batch.py:267,318,511) -- the discriminator usage.py's rows 5/6
# split on, NEVER `status` (a successful batch call also audits status="ok").
_SCHEDULER_USER_EMAIL = "system:scheduler"


async def _seed_ai_usage_row(
    db_session: Any,
    tenant_id: uuid.UUID,
    *,
    resource_type: str = "vuln",
    user_email: str = "analyst@tenant-a.test",
    status: str = "ok",
    cost_estimate_usd: float = 1.0,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> None:
    """Insert one ai.*-namespaced AuditLog row dated 'now' -- mirrors the
    EXACT shape `audit_log_ai_call()` writes (app/ai/audit.py:57-74):
    `action=f"ai.explain.{resource_type}"`, `details` carrying model/
    tokens/cost/status. Adapted from test_ai_budget.py::_seed_ai_spend to
    also vary resource_type/user_email/status/tokens."""
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=None,
        user_email=user_email,
        action=f"ai.explain.{resource_type}",
        resource_type=resource_type,
        resource_id=f"finding-{uuid.uuid4().hex[:8]}",
        details={
            "model": "claude-sonnet-5",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_estimate_usd": cost_estimate_usd,
            "status": status,
        },
        ip_address=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(log)
    await db_session.flush()


def _row(body: dict[str, Any], resource_type: str, is_batch: bool | None) -> dict[str, Any]:
    """Find one of the 6 fixed capability_breakdown rows by (resource_type, is_batch)."""
    return next(
        r for r in body["capability_breakdown"] if r["resource_type"] == resource_type and r["is_batch"] == is_batch
    )


# ── RBAC: viewer/analyst -> 403, admin -> 200 ───────────────────────────────


async def test_viewer_forbidden(client_factory: Any, viewer_user: Any) -> None:
    client = client_factory(viewer_user)
    resp = await client.get("/api/v1/ai/usage")
    assert resp.status_code == 403


async def test_analyst_forbidden(client_factory: Any, analyst_user: Any) -> None:
    client = client_factory(analyst_user)
    resp = await client.get("/api/v1/ai/usage")
    assert resp.status_code == 403


async def test_admin_allowed_and_returns_6_fixed_rows(
    client_factory: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=50.0)
    await db_session.commit()

    client = client_factory(admin_user)
    resp = await client.get("/api/v1/ai/usage")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["capability_breakdown"]) == 6
    assert body["spent_this_month_usd"] == 0.0
    assert body["breaker_tripped"] is False
    assert body["degraded_calls_count"] == 0


# ── Tenant isolation ─────────────────────────────────────────────────────


async def test_tenant_isolation_excludes_other_tenant_spend(
    client_factory: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID, tenant_b: uuid.UUID
) -> None:
    await _seed_ai_usage_row(db_session, tenant_a, resource_type="vuln", cost_estimate_usd=2.0)
    await _seed_ai_usage_row(db_session, tenant_b, resource_type="vuln", cost_estimate_usd=999.0)
    await db_session.commit()

    client = client_factory(admin_user)  # admin_user is scoped to tenant_a
    resp = await client.get("/api/v1/ai/usage")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["spent_this_month_usd"] == 2.0

    vuln_row = _row(body, "vuln", None)
    assert vuln_row["calls"] == 1
    assert vuln_row["cost_usd"] == 2.0


# ── Batch vs on-demand split keys on user_email, never status ──────────────


async def test_batch_prioritization_counted_in_batch_row_not_on_demand(
    client_factory: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    # Batch success -- status="ok", user_email="system:scheduler" (batch.py:511).
    await _seed_ai_usage_row(
        db_session,
        tenant_a,
        resource_type="prioritization",
        user_email=_SCHEDULER_USER_EMAIL,
        status="ok",
        cost_estimate_usd=3.0,
    )
    # On-demand -- the real analyst's email, ALSO status="ok" (proves the
    # split is on user_email, not status -- a status-based split could not
    # distinguish these two rows).
    await _seed_ai_usage_row(
        db_session,
        tenant_a,
        resource_type="prioritization",
        user_email="analyst@tenant-a.test",
        status="ok",
        cost_estimate_usd=1.0,
    )
    await db_session.commit()

    client = client_factory(admin_user)
    resp = await client.get("/api/v1/ai/usage")

    assert resp.status_code == 200, resp.text
    body = resp.json()

    batch_row = _row(body, "prioritization", True)
    on_demand_row = _row(body, "prioritization", False)
    assert batch_row["calls"] == 1
    assert batch_row["cost_usd"] == 3.0
    assert on_demand_row["calls"] == 1
    assert on_demand_row["cost_usd"] == 1.0


# ── breaker_tripped derivation (matches check_tenant_budget() exactly) ─────


async def test_breaker_tripped_true_when_spend_at_or_over_cap(
    client_factory: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=10.0)
    await _seed_ai_usage_row(db_session, tenant_a, cost_estimate_usd=10.0)
    await db_session.commit()

    client = client_factory(admin_user)
    resp = await client.get("/api/v1/ai/usage")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["monthly_budget_usd"] == 10.0
    assert body["breaker_tripped"] is True


async def test_breaker_tripped_false_when_under_cap(
    client_factory: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=100.0)
    await _seed_ai_usage_row(db_session, tenant_a, cost_estimate_usd=10.0)
    await db_session.commit()

    client = client_factory(admin_user)
    resp = await client.get("/api/v1/ai/usage")

    assert resp.status_code == 200, resp.text
    assert resp.json()["breaker_tripped"] is False


async def test_breaker_tripped_false_when_no_cap_configured(
    client_factory: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=None)
    await _seed_ai_usage_row(db_session, tenant_a, cost_estimate_usd=999.0)
    await db_session.commit()

    client = client_factory(admin_user)
    resp = await client.get("/api/v1/ai/usage")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["monthly_budget_usd"] is None
    assert body["breaker_tripped"] is False


# ── degraded_calls_count: NOT IN ('ok') AND NOT LIKE 'batch_%' ──────────────


async def test_degraded_calls_count_excludes_batch_prefixed_status(
    client_factory: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    # Genuinely degraded -- counted.
    await _seed_ai_usage_row(db_session, tenant_a, resource_type="vuln", status="validation_failed")
    # A batch_-prefixed skip/error status -- EXCLUDED (28-UI-SPEC.md line
    # ~153's exact formula; a bare `status != "ok"` would over-count this).
    await _seed_ai_usage_row(
        db_session,
        tenant_a,
        resource_type="prioritization",
        user_email=_SCHEDULER_USER_EMAIL,
        status="batch_skipped_budget_exceeded",
        cost_estimate_usd=0.0,
    )
    # A plain successful call -- excluded (status == "ok").
    await _seed_ai_usage_row(db_session, tenant_a, resource_type="host", status="ok")
    await db_session.commit()

    client = client_factory(admin_user)
    resp = await client.get("/api/v1/ai/usage")

    assert resp.status_code == 200, resp.text
    assert resp.json()["degraded_calls_count"] == 1
