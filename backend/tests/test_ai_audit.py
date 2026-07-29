"""Tests for app.ai.audit — the AI-call audit writer (AI-06).

Modeled on test_encryption_rotation.py::test_audit_event (lines 258-295):
`audit_log_ai_call()` constructs `AuditLog` DIRECTLY (mirrors
`encryption.py::rotate_credentials`, lines 256-276) — it NEVER calls the
shared `app.audit.audit()` helper, whose nil-tenant fallback
(`uuid.UUID(int=0)` when `user` is None) would silently bucket a userless
scheduler-originated AI call under a fake tenant. Interactive and
scheduler-originated calls share one function shape (symmetric, no
nil-tenant branch); every attempt — including a validation_failed one —
writes exactly one row (no silent unlogged call).
"""

from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.ai.audit import audit_log_ai_call
from app.audit import AuditLog
from app.db.session import async_session_factory


@dataclass
class _FakeUsage:
    """Minimal stand-in for an Anthropic Message.usage object — decouples
    this test from importing the anthropic SDK."""

    input_tokens: int
    output_tokens: int


async def _fetch_rows(action: str, resource_id: str) -> list[AuditLog]:
    """Query via a FRESH session (not the test's own db_session) — proves
    the row was actually committed to Postgres, mirroring
    test_encryption_rotation.py::test_audit_event's own verification style."""
    async with async_session_factory() as fresh:
        result = await fresh.execute(
            select(AuditLog).where(AuditLog.action == action, AuditLog.resource_id == resource_id)
        )
        return list(result.scalars().all())


async def test_interactive_call_writes_one_row_with_analyst_email(db_session, tenant_a):
    """audit_log_ai_call(tenant_id=tenant_a, user_email=analyst.email, ...)
    writes one row with the analyst's email, the explicit tenant_id, and
    details carrying model/input_tokens/output_tokens/cost_estimate_usd/status."""
    resource_id = f"vuln-{uuid.uuid4().hex[:8]}"
    await audit_log_ai_call(
        db_session,
        tenant_id=tenant_a,
        user_email="analyst@tenant-a.test",
        model="claude-sonnet-5",
        usage=_FakeUsage(input_tokens=1200, output_tokens=300),
        resource_type="vuln",
        resource_id=resource_id,
        status="ok",
        cost_estimate_usd=0.015,
    )
    await db_session.commit()

    rows = await _fetch_rows("ai.explain.vuln", resource_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "ai.explain.vuln"
    assert row.user_email == "analyst@tenant-a.test"
    assert row.tenant_id == tenant_a
    assert row.user_id is None
    assert row.details is not None
    assert row.details["model"] == "claude-sonnet-5"
    assert row.details["input_tokens"] == 1200
    assert row.details["output_tokens"] == 300
    assert row.details["cost_estimate_usd"] == 0.015
    assert row.details["status"] == "ok"


async def test_scheduler_audit(db_session, tenant_a):
    """Scheduler-originated call: user_email == 'system:scheduler' AND
    tenant_id == tenant_a.id — proving the scheduler path avoids the
    audit() nil-tenant trap (NOT uuid.UUID(int=0))."""
    resource_id = f"vuln-{uuid.uuid4().hex[:8]}"
    await audit_log_ai_call(
        db_session,
        tenant_id=tenant_a,
        user_email="system:scheduler",
        model="claude-sonnet-5",
        usage=_FakeUsage(input_tokens=800, output_tokens=200),
        resource_type="vuln",
        resource_id=resource_id,
        status="ok",
    )
    await db_session.commit()

    rows = await _fetch_rows("ai.explain.vuln", resource_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_email == "system:scheduler"
    assert row.tenant_id == tenant_a
    assert row.tenant_id != uuid.UUID(int=0)


async def test_validation_failed_still_writes_exactly_one_row(db_session, tenant_a):
    """AI-06: a validation_failed attempt is still audit-logged — no
    silent, unlogged failure."""
    resource_id = f"vuln-{uuid.uuid4().hex[:8]}"
    await audit_log_ai_call(
        db_session,
        tenant_id=tenant_a,
        user_email="analyst@tenant-a.test",
        model="claude-sonnet-5",
        usage=_FakeUsage(input_tokens=1100, output_tokens=50),
        resource_type="vuln",
        resource_id=resource_id,
        status="validation_failed",
    )
    await db_session.commit()

    rows = await _fetch_rows("ai.explain.vuln", resource_id)
    assert len(rows) == 1
    assert rows[0].details["status"] == "validation_failed"
    assert rows[0].details["cost_estimate_usd"] is None  # not supplied — defaults to None


async def test_action_is_dot_namespaced_by_resource_type(db_session, tenant_a):
    """action convention: 'ai.explain.{resource_type}' — proven with a
    resource_type other than 'vuln' so this isn't a hardcoded string."""
    resource_id = f"host-{uuid.uuid4().hex[:8]}"
    await audit_log_ai_call(
        db_session,
        tenant_id=tenant_a,
        user_email="analyst@tenant-a.test",
        model="claude-sonnet-5",
        usage=_FakeUsage(input_tokens=500, output_tokens=100),
        resource_type="host",
        resource_id=resource_id,
        status="ok",
    )
    await db_session.commit()

    rows = await _fetch_rows("ai.explain.host", resource_id)
    assert len(rows) == 1


def test_tenant_id_is_required_keyword_only_with_no_default():
    """tenant_id must be a required, keyword-only parameter — it can never
    be silently defaulted, mirroring rotate_credentials()'s discipline."""
    sig = inspect.signature(audit_log_ai_call)
    tenant_id_param = sig.parameters["tenant_id"]
    assert tenant_id_param.kind == inspect.Parameter.KEYWORD_ONLY
    assert tenant_id_param.default is inspect.Parameter.empty
