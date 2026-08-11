"""Phase 34 Plan 01 (LEAD TRACER) — RISK-07 fixture suite for the historical
risk-exposure recompute: idempotent + resumable + throttled + per-tenant
isolated bulk backfill of `Vulnerability.risk_exposure_score` onto
RISK_MODEL_VERSION.

No prior chunked/resumable-job test surface exists in this codebase
(confirmed via grep) — `test_scheduler_ai_batch.py`/`test_scheduler_enrichment_
refresh.py` cover GATED DISPATCH (24h timers, create_task-vs-inline-await),
not a durable, chunked, keyset-resumable job with its own claim-row
concurrency guard. This file synthesizes: `test_risk_exposure_service.py`'s
`_seed_asset`/`_seed_vuln` fixture-seed idiom + direct-service-call
convention, `test_scheduler_ai_batch.py`'s `from app.connectors import
scheduler as scheduler_module; await scheduler_module._dispatch_...()`
direct-await + monkeypatch-a-slow/failing-fake idiom, and
`test_ai_batch_job.py`'s genuinely-fresh-`async_session_factory()`-session
idiom for proving durability survives a simulated process restart.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`) + JWT_SECRET_KEY set,
per-file (not the whole tests/ dir).

RED (this task): `RiskExposureBackfillJob`, `risk_backfill_service.py`, and
`scheduler._dispatch_risk_exposure_backfill` do not exist yet — every test
below fails for real via a local (inside-test-body) import raising
ImportError/AttributeError, or a missing-table error once a migration/model
mismatch is exercised against the live DB. No respx/pytest-httpx (this
suite is DB-only, no external HTTP).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability


def _seed_asset(tenant_id: uuid.UUID) -> Asset:
    # Mirrors test_risk_exposure_service.py's _seed_asset helper shape.
    return Asset(tenant_id=tenant_id, hostname=f"host-{uuid.uuid4().hex[:8]}")


def _seed_vuln(
    tenant_id: uuid.UUID,
    asset_id: uuid.UUID,
    *,
    cve_id: str,
    severity: str = "HIGH",
    cvss_v3_score: Decimal | None = Decimal("7.5"),
    epss_score: Decimal | None = None,
    cisa_kev: bool = False,
    source: str = "QUALYS",
    status: str = "OPEN",
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        asset_id=asset_id,
        severity=severity,
        cvss_v3_score=cvss_v3_score,
        epss_score=epss_score,
        cisa_kev=cisa_kev,
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        status=status,
        first_detected_at=now,
        last_seen_at=now,
    )


# ── Chunk correctness ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chunk_processes_correct_rows(db_session, tenant_a):
    """RISK-07: a single chunk pass (chunk_size >= row count) scores every
    eligible row with the exact score_finding output for its inputs, persists
    the breakdown + version, and a FOLLOWING empty pass marks the job
    completed with the right rows_migrated count."""
    from app.vulnerabilities.models import RiskExposureBackfillJob
    from app.vulnerabilities.risk_backfill_service import enqueue_backfill_job, process_backfill_chunk
    from app.vulnerabilities.risk_exposure_service import RISK_MODEL_VERSION, FindingScoreInputs, score_finding

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    # Captured BEFORE the backfill runs: process_backfill_chunk's bulk
    # UPDATE...FROM is raw SQL that bypasses the ORM, so it calls
    # `db.expire_all()` afterwards to avoid stale identity-map reads (see
    # risk_backfill_service.py) -- that expires THIS test's own `asset`
    # reference too, so any attribute read after the backfill call must
    # come from a value captured beforehand (or a fresh query), not from
    # touching the now-expired `asset` object directly.
    asset_criticality = asset.business_criticality
    asset_sensitivity = asset.data_sensitivity
    asset_internet_facing = asset.internet_facing

    vulns = [_seed_vuln(tenant_a, asset.id, cve_id=f"CVE-2024-{i:04d}") for i in range(3)]
    db_session.add_all(vulns)
    await db_session.commit()

    job = await enqueue_backfill_job(db_session, tenant_a)
    await db_session.commit()
    assert job.rows_total_estimate == 3
    assert job.status == "pending"

    result = await process_backfill_chunk(db_session, tenant_a)
    assert result["processed"] == 3
    assert result["done"] is False  # completion is only confirmed by the NEXT (empty) pass

    result2 = await process_backfill_chunk(db_session, tenant_a)
    assert result2["processed"] == 0
    assert result2["done"] is True

    rows = (await db_session.execute(select(Vulnerability).where(Vulnerability.tenant_id == tenant_a))).scalars().all()
    assert len(rows) == 3
    for row in rows:
        expected = score_finding(
            FindingScoreInputs(
                severity=row.severity,
                cvss_v3_score=row.cvss_v3_score,
                epss_score=row.epss_score,
                cisa_kev=row.cisa_kev,
                source=row.source,
                native_priority_score=row.native_priority_score,
                native_priority_rating=row.native_priority_rating,
                sources_count=1,
                business_criticality=asset_criticality,
                data_sensitivity=asset_sensitivity,
                internet_facing=asset_internet_facing,
            )
        )
        assert row.risk_exposure_score == expected.final_score
        assert isinstance(row.risk_exposure_breakdown, list)
        assert len(row.risk_exposure_breakdown) > 0
        assert row.risk_model_version == RISK_MODEL_VERSION

    job_row = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    assert job_row.rows_migrated == 3
    assert job_row.status == "completed"
    assert job_row.completed_at is not None


@pytest.mark.asyncio
async def test_backfill_is_idempotent(db_session, tenant_a):
    """RISK-07: re-running process_backfill_chunk after completion is a
    no-op — the risk_model_version WHERE-guard excludes every already-scored
    row, rows_migrated is unchanged, status stays completed."""
    from app.vulnerabilities.models import RiskExposureBackfillJob
    from app.vulnerabilities.risk_backfill_service import enqueue_backfill_job, process_backfill_chunk

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vulns = [_seed_vuln(tenant_a, asset.id, cve_id=f"CVE-2024-I{i:04d}") for i in range(2)]
    db_session.add_all(vulns)
    await db_session.commit()

    await enqueue_backfill_job(db_session, tenant_a)
    await db_session.commit()

    await process_backfill_chunk(db_session, tenant_a)  # scores both rows
    completion = await process_backfill_chunk(db_session, tenant_a)  # marks completed
    assert completion["done"] is True

    job_before = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    assert job_before.status == "completed"
    rows_migrated_before = job_before.rows_migrated

    # Re-run from scratch (claim-row still eligible since 'completed' is not
    # in the claimable set -- the direct call proves the WHERE-guard even if
    # a caller mistakenly tries to force a chunk on a done job).
    rerun = await process_backfill_chunk(db_session, tenant_a)
    assert rerun["processed"] == 0
    assert rerun.get("claimed", True) is False or rerun["done"] is True

    job_after = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    assert job_after.rows_migrated == rows_migrated_before
    assert job_after.status == "completed"


@pytest.mark.asyncio
async def test_chunk_size_bounds_each_pass(db_session, tenant_a):
    """RISK-07 throttle proof: chunk_size=2 over 5 rows takes exactly 3
    data-bearing passes (2+2+1), never exceeding chunk_size in a single
    pass, with a monotonically-advancing cursor; status stays 'in_progress'
    across all 3 (a following empty pass is required to flip to
    'completed', proven separately in test_chunk_processes_correct_rows)."""
    from app.vulnerabilities.models import RiskExposureBackfillJob
    from app.vulnerabilities.risk_backfill_service import enqueue_backfill_job, process_backfill_chunk

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vulns = [_seed_vuln(tenant_a, asset.id, cve_id=f"CVE-2024-C{i:04d}") for i in range(5)]
    db_session.add_all(vulns)
    await db_session.commit()

    job = await enqueue_backfill_job(db_session, tenant_a)
    job.chunk_size = 2
    await db_session.commit()

    processed_counts: list[int] = []
    cursors: list[uuid.UUID] = []
    for _ in range(3):
        result = await process_backfill_chunk(db_session, tenant_a)
        processed_counts.append(result["processed"])
        assert result["processed"] <= 2

        job_row = (
            await db_session.execute(
                select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a)
            )
        ).scalar_one()
        assert job_row.status == "in_progress"
        cursors.append(job_row.cursor_vuln_id)

    assert processed_counts == [2, 2, 1]
    assert cursors == sorted(cursors)  # each pass's cursor > the previous (ORDER BY id ASC)

    # Draining pass confirms full completion + correct final rows_migrated.
    final = await process_backfill_chunk(db_session, tenant_a)
    assert final["done"] is True
    job_row = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    assert job_row.status == "completed"
    assert job_row.rows_migrated == 5


# ── Kill-mid-chunk + restart resume ───────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_mid_chunk_resumes_correctly(db_session, tenant_a, monkeypatch):
    """RISK-07 Pitfall 5/6: an exception raised AFTER selecting/scoring but
    BEFORE commit (simulated by making db_session.commit() raise on the
    FIRST pass only) rolls the whole chunk back -- zero rows on-version,
    rows_migrated == 0. Removing the fault and re-running completes cleanly
    with every row on-version EXACTLY once (no double-counted
    rows_migrated)."""
    from app.vulnerabilities.models import RiskExposureBackfillJob
    from app.vulnerabilities.risk_backfill_service import enqueue_backfill_job, process_backfill_chunk

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vulns = [_seed_vuln(tenant_a, asset.id, cve_id=f"CVE-2024-K{i:04d}") for i in range(3)]
    db_session.add_all(vulns)
    await db_session.commit()

    await enqueue_backfill_job(db_session, tenant_a)
    await db_session.commit()

    real_commit = db_session.commit
    call_count = {"n": 0}

    async def flaky_commit():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated crash mid-chunk")
        return await real_commit()

    monkeypatch.setattr(db_session, "commit", flaky_commit)

    with pytest.raises(RuntimeError, match="simulated crash mid-chunk"):
        await process_backfill_chunk(db_session, tenant_a)

    await db_session.rollback()

    rows = (await db_session.execute(select(Vulnerability).where(Vulnerability.tenant_id == tenant_a))).scalars().all()
    assert len(rows) == 3
    assert all(r.risk_exposure_score is None for r in rows)
    assert all(r.risk_model_version is None for r in rows)

    job_row = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    assert job_row.rows_migrated == 0
    assert job_row.status == "pending"

    monkeypatch.setattr(db_session, "commit", real_commit)

    result = await process_backfill_chunk(db_session, tenant_a)
    assert result["processed"] == 3
    completion = await process_backfill_chunk(db_session, tenant_a)
    assert completion["done"] is True

    rows = (await db_session.execute(select(Vulnerability).where(Vulnerability.tenant_id == tenant_a))).scalars().all()
    assert all(r.risk_exposure_score is not None for r in rows)

    job_row = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    assert job_row.status == "completed"
    assert job_row.rows_migrated == 3  # NOT double-counted despite the earlier failed attempt


@pytest.mark.asyncio
async def test_resume_survives_simulated_restart(db_session, tenant_a):
    """RISK-07 durable/resumable: process one chunk of a multi-chunk set
    and commit; then, WITHOUT reusing any in-memory handle, open a genuinely
    fresh `async_session_factory()` session (mirrors test_ai_batch_job.py's
    durability idiom) and drive the SAME job to completion. Final state is
    correct and the cursor resumed from the persisted value, not from
    scratch."""
    from app.db.session import async_session_factory
    from app.vulnerabilities.models import RiskExposureBackfillJob
    from app.vulnerabilities.risk_backfill_service import enqueue_backfill_job, process_backfill_chunk

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vulns = [_seed_vuln(tenant_a, asset.id, cve_id=f"CVE-2024-R{i:04d}") for i in range(6)]
    db_session.add_all(vulns)
    await db_session.commit()

    job = await enqueue_backfill_job(db_session, tenant_a)
    job.chunk_size = 2
    await db_session.commit()

    first_pass = await process_backfill_chunk(db_session, tenant_a)
    assert first_pass["processed"] == 2

    job_after_first = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    cursor_after_first = job_after_first.cursor_vuln_id
    assert cursor_after_first is not None

    # Simulate a process restart: a genuinely independent session, no
    # in-memory state carried over at all.
    async with async_session_factory() as fresh:
        pass_count = 0
        result = {"done": False}
        while not result["done"]:
            result = await process_backfill_chunk(fresh, tenant_a)
            pass_count += 1
            assert pass_count < 10  # sanity bound

        final_job = (
            await fresh.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
        ).scalar_one()
        assert final_job.status == "completed"
        assert final_job.rows_migrated == 6

        final_rows = (
            (await fresh.execute(select(Vulnerability).where(Vulnerability.tenant_id == tenant_a))).scalars().all()
        )
        assert len(final_rows) == 6
        assert all(r.risk_exposure_score is not None for r in final_rows)

    # The fresh session's own resumed work never re-processed the prefix
    # the first (pre-restart) pass already covered -- cursor only moves
    # forward, never resets to null/zero.
    async with async_session_factory() as verify:
        replayed_job = (
            await verify.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
        ).scalar_one()
        assert replayed_job.cursor_vuln_id is not None
        assert replayed_job.cursor_vuln_id >= cursor_after_first


# ── Per-tenant isolation ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tenant_failure_isolated(db_session, tenant_a, tenant_b, monkeypatch):
    """RISK-07 per-tenant isolation (T-34-01 threat register): tenant_b's
    scoring is forced to raise; dispatch_backfill_chunks sets ONLY tenant_b's
    job to 'failed' with error_message populated, while tenant_a's job
    progresses and its rows are correctly scored. tenant_b's rows are left
    untouched (still unscored)."""
    from app.vulnerabilities import risk_backfill_service
    from app.vulnerabilities.models import RiskExposureBackfillJob
    from app.vulnerabilities.risk_backfill_service import dispatch_backfill_chunks, enqueue_backfill_job

    asset_a = _seed_asset(tenant_a)
    asset_b = _seed_asset(tenant_b)
    db_session.add_all([asset_a, asset_b])
    await db_session.flush()

    vulns_a = [_seed_vuln(tenant_a, asset_a.id, cve_id=f"CVE-2024-TA{i:04d}", severity="HIGH") for i in range(2)]
    vulns_b = [_seed_vuln(tenant_b, asset_b.id, cve_id=f"CVE-2024-TB{i:04d}", severity="CRITICAL") for i in range(2)]
    db_session.add_all(vulns_a + vulns_b)
    await db_session.commit()

    await enqueue_backfill_job(db_session, tenant_a)
    await enqueue_backfill_job(db_session, tenant_b)
    await db_session.commit()

    real_score_finding = risk_backfill_service.score_finding

    def flaky_score_finding(inputs):
        if inputs.severity == "CRITICAL":  # tenant_b's marker severity only
            raise RuntimeError("simulated tenant_b scoring failure")
        return real_score_finding(inputs)

    monkeypatch.setattr(risk_backfill_service, "score_finding", flaky_score_finding)

    await dispatch_backfill_chunks(db_session)

    job_a = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    job_b = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_b))
    ).scalar_one()

    assert job_b.status == "failed"
    assert job_b.error_message is not None
    assert "simulated tenant_b scoring failure" in job_b.error_message

    assert job_a.status in ("in_progress", "completed")

    rows_a = (
        (await db_session.execute(select(Vulnerability).where(Vulnerability.tenant_id == tenant_a))).scalars().all()
    )
    assert all(r.risk_exposure_score is not None for r in rows_a)

    rows_b = (
        (await db_session.execute(select(Vulnerability).where(Vulnerability.tenant_id == tenant_b))).scalars().all()
    )
    assert all(r.risk_exposure_score is None for r in rows_b)
    assert all(r.risk_model_version is None for r in rows_b)


# ── Multi-chunk load fixture ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_large_tenant_backfill_throughput(db_session, tenant_a):
    """RISK-07 fixture load test (NOT live): 34-RESEARCH.md's own example is
    2500 rows @ chunk_size 500 (5 chunks); scaled down here to 105 rows @
    chunk_size 20 (6 passes: 5 full + 1 trailing partial) to keep this
    file's total runtime bounded (<30s target) while preserving the exact
    multi-chunk structural shape the throttle proof needs. Asserts every
    pass stays <= chunk_size (never the whole set in one statement) and the
    job completes with the exact seeded row count, none double-counted."""
    from app.vulnerabilities.models import RiskExposureBackfillJob
    from app.vulnerabilities.risk_backfill_service import enqueue_backfill_job, process_backfill_chunk

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    total = 105
    chunk_size = 20
    vulns = [_seed_vuln(tenant_a, asset.id, cve_id=f"CVE-2024-L{i:05d}") for i in range(total)]
    db_session.add_all(vulns)
    await db_session.commit()

    job = await enqueue_backfill_job(db_session, tenant_a)
    job.chunk_size = chunk_size
    await db_session.commit()
    assert job.rows_total_estimate == total

    passes = 0
    result = {"done": False}
    while not result["done"]:
        result = await process_backfill_chunk(db_session, tenant_a)
        passes += 1
        assert result["processed"] <= chunk_size
        assert passes < 20  # sanity bound against an infinite-loop regression

    assert passes >= 6  # >=5 full data-bearing chunks + >=1 completion-detecting pass

    job_row = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    assert job_row.status == "completed"
    assert job_row.rows_migrated == total

    rows = (await db_session.execute(select(Vulnerability).where(Vulnerability.tenant_id == tenant_a))).scalars().all()
    assert len(rows) == total
    assert all(r.risk_exposure_score is not None for r in rows)


# ── Scheduler dispatch: non-blocking ────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatcher_is_non_blocking(monkeypatch):
    """RISK-07: _dispatch_risk_exposure_backfill uses asyncio.create_task
    (never inline-awaited), mirroring test_scheduler_ai_batch.py's
    non-blocking assertion -- a call to the dispatcher must return control
    BEFORE a slow fake dispatch_backfill_chunks' body finishes."""
    from app.connectors import scheduler as scheduler_module

    event = asyncio.Event()
    calls: list[None] = []

    async def slow_dispatch(db):
        calls.append(None)
        await asyncio.sleep(0.05)
        event.set()

    monkeypatch.setattr("app.vulnerabilities.risk_backfill_service.dispatch_backfill_chunks", slow_dispatch)

    await scheduler_module._dispatch_risk_exposure_backfill()

    # Must have returned control WITHOUT waiting for the slow fake's sleep.
    assert not event.is_set()

    await asyncio.sleep(0.15)
    assert event.is_set()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_dispatcher_swallows_failure(monkeypatch):
    """A failing dispatch_backfill_chunks must never raise out of the
    dispatcher itself (mirrors test_scheduler_ai_batch.py's
    test_dispatch_exception_is_caught)."""
    from app.connectors import scheduler as scheduler_module

    async def failing_dispatch(db):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.vulnerabilities.risk_backfill_service.dispatch_backfill_chunks", failing_dispatch)

    # Must not raise, even though the underlying dispatch fails inside the
    # detached task.
    await scheduler_module._dispatch_risk_exposure_backfill()
    await asyncio.sleep(0.05)
