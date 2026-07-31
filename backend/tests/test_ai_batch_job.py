"""Tests for `AiBatchJob` (Phase 26 Plan 06, Task 1) -- the durable Postgres
registry for a submitted Anthropic Message Batch (D-05/D-06, RESEARCH
#2/Pattern 4, T-26-08).

Modeled on test_ai_audit.py's fresh-session verification style: an
in-memory dict (like scheduler.py's `_running_syncs`) is NOT sufficient for
tracking a Message Batch that can legitimately still be `in_progress` up to
24h later, spanning a backend restart -- these tests prove the row survives
in a genuinely FRESH `async_session_factory()` session, not just the same
test's own `db_session`.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.ai.models import AiBatchJob
from app.db.session import async_session_factory


def _make_batch_job(tenant_id: uuid.UUID, finding_id: uuid.UUID, **overrides: Any) -> AiBatchJob:
    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "anthropic_batch_id": f"msgbatch_{uuid.uuid4().hex[:16]}",
        "status": "in_progress",
        "model": "claude-sonnet-5",
        "prompt_version": "abc123",
        "custom_id_hash_map": {str(finding_id): "hash1"},
        "submitted_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return AiBatchJob(**defaults)


# ── Test: durable round-trip in a FRESH session ─────────────────────────────


@pytest.mark.asyncio
async def test_ai_batch_job_durable_round_trip(db_session, tenant_a):
    """An AiBatchJob row persists and is retrievable in a FRESH
    async_session_factory() session -- durability, not just in-memory
    (T-26-08). custom_id_hash_map round-trips as a real dict (JSONB)."""
    finding_id = uuid.uuid4()
    job = _make_batch_job(tenant_a, finding_id)
    db_session.add(job)
    await db_session.commit()  # visible to a genuinely independent session
    job_id = job.id

    async with async_session_factory() as fresh:
        result = await fresh.execute(select(AiBatchJob).where(AiBatchJob.id == job_id))
        row = result.scalar_one()

    assert row.tenant_id == tenant_a
    assert row.anthropic_batch_id == job.anthropic_batch_id
    assert row.status == "in_progress"
    assert row.model == "claude-sonnet-5"
    assert row.prompt_version == "abc123"
    assert row.custom_id_hash_map == {str(finding_id): "hash1"}
    assert isinstance(row.custom_id_hash_map, dict)
    assert row.submitted_at is not None
    assert row.ended_at is None


# ── Test: anthropic_batch_id uniqueness ──────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_batch_job_anthropic_id_unique(db_session, tenant_a):
    """A second row with a duplicate anthropic_batch_id raises an
    IntegrityError (unique index, migration 033)."""
    shared_batch_id = f"msgbatch_{uuid.uuid4().hex[:16]}"
    job1 = _make_batch_job(tenant_a, uuid.uuid4(), anthropic_batch_id=shared_batch_id)
    db_session.add(job1)
    await db_session.flush()  # first insert must succeed

    job2 = _make_batch_job(tenant_a, uuid.uuid4(), anthropic_batch_id=shared_batch_id)
    db_session.add(job2)
    with pytest.raises(IntegrityError):
        await db_session.flush()  # duplicate anthropic_batch_id must raise


# ── Test: JSONB containment predicate (the GET route's exact query) ─────────


@pytest.mark.asyncio
async def test_ai_batch_job_jsonb_containment(db_session, tenant_a, tenant_b):
    """`custom_id_hash_map.has_key(str(finding_id))` scoped by tenant_id +
    status='in_progress' returns the row -- the exact predicate Task 2's
    `_is_finding_queued()` uses. A completed row and a different-tenant row
    for the SAME finding_id must NOT match (T-26-03 cross-tenant isolation)."""
    finding_id = uuid.uuid4()
    other_finding_id = uuid.uuid4()

    in_progress_job = _make_batch_job(tenant_a, finding_id)
    db_session.add(in_progress_job)

    completed_job = _make_batch_job(
        tenant_a,
        other_finding_id,
        status="completed",
        anthropic_batch_id=f"msgbatch_{uuid.uuid4().hex[:16]}",
    )
    db_session.add(completed_job)

    # tenant_b has an in_progress batch containing the SAME finding_id --
    # must never satisfy tenant_a's own containment query.
    cross_tenant_job = _make_batch_job(tenant_b, finding_id, anthropic_batch_id=f"msgbatch_{uuid.uuid4().hex[:16]}")
    db_session.add(cross_tenant_job)
    await db_session.commit()

    result = await db_session.execute(
        select(AiBatchJob.id).where(
            AiBatchJob.tenant_id == tenant_a,
            AiBatchJob.status == "in_progress",
            AiBatchJob.custom_id_hash_map.has_key(str(finding_id)),
        )
    )
    row = result.first()
    assert row is not None
    assert row[0] == in_progress_job.id

    # The completed row's finding is never returned by the same predicate,
    # even though it's the same tenant.
    completed_result = await db_session.execute(
        select(AiBatchJob.id).where(
            AiBatchJob.tenant_id == tenant_a,
            AiBatchJob.status == "in_progress",
            AiBatchJob.custom_id_hash_map.has_key(str(other_finding_id)),
        )
    )
    assert completed_result.first() is None
