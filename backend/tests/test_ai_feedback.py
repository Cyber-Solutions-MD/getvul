"""Tests for POST /api/v1/ai/feedback/{resource_type}/{resource_id} -- the
D-21/D-22 idempotent per-user feedback upsert (T-24-28..31).

Capture-only this phase (D-21): there is no GET/surfacing route to test.
resource_id is a plain opaque string identifier (String(200), no FK) --
these tests don't need to seed a real vulnerability row.

Fixtures from conftest.py: db_session, tenant_a, tenant_b, analyst_user,
analyst_user_b, viewer_user, client, client_factory.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with
ENCRYPTION_KEY/JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.ai.models import AiFeedback
from app.audit import AuditLog

RESOURCE_TYPE = "vuln"


def _resource_id() -> str:
    return f"finding-{uuid.uuid4().hex[:8]}"


# ── Test: create ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_feedback_creates_row(db_session, tenant_a, analyst_user, client):
    """POST feedback (verdict=up, note set) writes one ai_feedback row
    scoped to the analyst's own tenant+user."""
    resource_id = _resource_id()
    # tenant_a/analyst_user fixtures only flush() -- commit so the FK rows
    # are visible to the app's own DB session (WR-13, mirrors test_ticket_watch.py).
    await db_session.commit()
    response = await client.post(
        f"/api/v1/ai/feedback/{RESOURCE_TYPE}/{resource_id}",
        json={"verdict": "up", "note": "off on CVSS"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert response.json().get("verdict") == "up"

    row = (
        await db_session.execute(
            select(AiFeedback).where(
                AiFeedback.resource_type == RESOURCE_TYPE,
                AiFeedback.resource_id == resource_id,
                AiFeedback.user_id == analyst_user.id,
            )
        )
    ).scalar_one()
    assert row.tenant_id == tenant_a
    assert row.verdict == "up"
    assert row.note == "off on CVSS"


# ── Test: edit / idempotent upsert (D-22) ────────────────────────────────────


@pytest.mark.asyncio
async def test_post_feedback_edit_upserts_single_row(db_session, analyst_user, client):
    """A second POST for the same (resource_type, resource_id, user) UPDATES
    verdict/note to a single row -- never a duplicate insert."""
    resource_id = _resource_id()
    await db_session.commit()
    await client.post(
        f"/api/v1/ai/feedback/{RESOURCE_TYPE}/{resource_id}",
        json={"verdict": "up", "note": "first pass"},
    )
    response = await client.post(
        f"/api/v1/ai/feedback/{RESOURCE_TYPE}/{resource_id}",
        json={"verdict": "down", "note": "changed my mind"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert response.json().get("verdict") == "down"

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(AiFeedback)
            .where(
                AiFeedback.resource_type == RESOURCE_TYPE,
                AiFeedback.resource_id == resource_id,
                AiFeedback.user_id == analyst_user.id,
            )
        )
    ).scalar_one()
    assert count == 1, f"Expected exactly 1 row after edit (upsert), got {count}"

    row = (
        await db_session.execute(
            select(AiFeedback).where(
                AiFeedback.resource_type == RESOURCE_TYPE,
                AiFeedback.resource_id == resource_id,
                AiFeedback.user_id == analyst_user.id,
            )
        )
    ).scalar_one()
    assert row.verdict == "down"
    assert row.note == "changed my mind"


# ── Test: thumb-only (note omitted) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_feedback_thumb_only_succeeds(db_session, analyst_user, client):
    """A thumb alone (no note) is a valid submission -- partial submit is fine."""
    resource_id = _resource_id()
    await db_session.commit()
    response = await client.post(
        f"/api/v1/ai/feedback/{RESOURCE_TYPE}/{resource_id}",
        json={"verdict": "down"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    row = (
        await db_session.execute(
            select(AiFeedback).where(
                AiFeedback.resource_type == RESOURCE_TYPE,
                AiFeedback.resource_id == resource_id,
                AiFeedback.user_id == analyst_user.id,
            )
        )
    ).scalar_one()
    assert row.note is None


# ── Test: note cap (>500 chars -> 422) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_feedback_note_too_long_rejected(client):
    """A note > 500 chars is rejected 422 (request-validation convention)."""
    resource_id = _resource_id()
    response = await client.post(
        f"/api/v1/ai/feedback/{RESOURCE_TYPE}/{resource_id}",
        json={"verdict": "up", "note": "x" * 501},
    )
    assert response.status_code == 422, f"Expected 422 for an over-long note, got {response.status_code}"


# ── Test: tenant isolation ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_tenant_feedback_isolated(
    db_session, tenant_a, tenant_b, analyst_user, analyst_user_b, client_factory
):
    """analyst_user_b (tenant_b) posting feedback for the SAME resource_id as
    tenant_a's analyst_user cannot read/overwrite tenant_a's row -- each lands
    in its own row, scoped by (resource_type, resource_id, user_id) + tenant_id."""
    resource_id = _resource_id()
    await db_session.commit()

    client_a = client_factory(analyst_user)
    client_b = client_factory(analyst_user_b)

    async with client_a:
        resp_a = await client_a.post(
            f"/api/v1/ai/feedback/{RESOURCE_TYPE}/{resource_id}",
            json={"verdict": "up", "note": "tenant a verdict"},
        )
    assert resp_a.status_code == 200, f"Expected 200, got {resp_a.status_code}: {resp_a.text}"

    async with client_b:
        resp_b = await client_b.post(
            f"/api/v1/ai/feedback/{RESOURCE_TYPE}/{resource_id}",
            json={"verdict": "down", "note": "tenant b verdict"},
        )
    assert resp_b.status_code == 200, f"Expected 200, got {resp_b.status_code}: {resp_b.text}"

    row_a = (
        await db_session.execute(
            select(AiFeedback).where(
                AiFeedback.resource_type == RESOURCE_TYPE,
                AiFeedback.resource_id == resource_id,
                AiFeedback.user_id == analyst_user.id,
            )
        )
    ).scalar_one()
    row_b = (
        await db_session.execute(
            select(AiFeedback).where(
                AiFeedback.resource_type == RESOURCE_TYPE,
                AiFeedback.resource_id == resource_id,
                AiFeedback.user_id == analyst_user_b.id,
            )
        )
    ).scalar_one()

    assert row_a.tenant_id == tenant_a
    assert row_a.verdict == "up"
    assert row_a.note == "tenant a verdict"

    assert row_b.tenant_id == tenant_b
    assert row_b.verdict == "down"
    assert row_b.note == "tenant b verdict"

    # tenant_b's write did NOT overwrite tenant_a's row (IDOR guard, T-24-28).
    assert row_a.id != row_b.id


# ── Test: RBAC -- Viewer is forbidden (require_analyst gate) ─────────────────


@pytest.mark.asyncio
async def test_viewer_forbidden(viewer_user, client_factory):
    """Feedback gates at require_analyst (mirrors the watch/unwatch analog and
    D-17's actor model) -- a Viewer gets 403, never a silently-accepted write."""
    resource_id = _resource_id()
    client_viewer = client_factory(viewer_user)
    async with client_viewer:
        response = await client_viewer.post(
            f"/api/v1/ai/feedback/{RESOURCE_TYPE}/{resource_id}",
            json={"verdict": "up"},
        )
    assert response.status_code == 403, f"Expected 403 for Viewer, got {response.status_code}: {response.text}"


# ── Test: audit row ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_feedback_writes_audit_row(db_session, tenant_a, analyst_user, client):
    """Feedback writes an audit row via the standard audit() helper (a real
    interactive user action with a real tenant -- distinct from the AI-call
    audit path, T-24-30)."""
    resource_id = _resource_id()
    await db_session.commit()
    await client.post(
        f"/api/v1/ai/feedback/{RESOURCE_TYPE}/{resource_id}",
        json={"verdict": "up", "note": "good catch"},
    )

    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "ai.feedback",
                    AuditLog.tenant_id == tenant_a,
                    AuditLog.resource_id == resource_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) >= 1, "Expected at least one ai.feedback audit row"
    assert audit_rows[0].user_email == analyst_user.email
    assert audit_rows[0].details == {"verdict": "up"}
