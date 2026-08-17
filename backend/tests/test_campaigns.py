"""Phase 38 Plan 01 (CAMP-01/CAMP-04) -- campaign persistence tracer slice.

Task 2: DB-level partial-unique-index proof for D-11 (exactly one ACTIVE
campaign per (tenant_id, remediation_id); a CLOSED campaign's remediation_id
accepts a fresh active campaign). Task 3 extends this same file with the
get-or-create service + router (POST/GET/GET-detail) + audit + RBAC +
compute-on-read progress tests.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from app.campaigns.models import Campaign


def _make_campaign(tenant_id: uuid.UUID, remediation_id: str, **overrides: Any) -> Campaign:
    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "remediation_id": remediation_id,
    }
    defaults.update(overrides)
    return Campaign(**defaults)


# ── Task 2: D-11 partial unique index (DB-constraint proof) ─────────────────


@pytest.mark.asyncio
async def test_campaign_unique_active_index(db_session, tenant_a):
    """A second ACTIVE (closed_at IS NULL) campaign on the same
    (tenant_id, remediation_id) raises IntegrityError -- the D-11 partial
    unique index (`uq_campaign_active_remediation`, migration 049) is
    enforced at the DB level, not just in application code."""
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"

    c1 = _make_campaign(tenant_a, remediation_id)
    db_session.add(c1)
    await db_session.flush()  # first insert must succeed

    c2 = _make_campaign(tenant_a, remediation_id)
    db_session.add(c2)
    with pytest.raises(IntegrityError):
        await db_session.flush()  # duplicate ACTIVE row must raise


@pytest.mark.asyncio
async def test_new_campaign_after_close(db_session, tenant_a):
    """A CLOSED campaign's remediation_id can get a fresh active campaign --
    the partial index only guards rows WHERE closed_at IS NULL (D-13
    auto-complete / D-17 manual-close-is-sticky both require this
    remediation_id to stay re-launchable after a prior campaign closes)."""
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"

    closed = _make_campaign(
        tenant_a,
        remediation_id,
        closed_at=datetime.now(UTC) - timedelta(days=1),
        close_trigger="manual",
    )
    db_session.add(closed)
    await db_session.flush()

    reopened = _make_campaign(tenant_a, remediation_id)
    db_session.add(reopened)
    await db_session.flush()  # must NOT raise -- the closed row doesn't block a new active one

    assert reopened.closed_at is None
    assert reopened.id != closed.id
