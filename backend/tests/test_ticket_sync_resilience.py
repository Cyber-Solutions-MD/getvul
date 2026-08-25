"""Phase 37 Plan 03 — SYNC-04 ticketing connector sync resilience.

Bounded retry (3 attempts, exponential backoff) + real per-connector
`last_sync_at`/`last_sync_status`/`last_sync_record_count`/
`consecutive_failure_count`/`last_error` bookkeeping for the ticketing
daily-sync pass, mirroring the scanner-connector resilience precedent
(`connectors/sync.py::run_sync` / `directory_sync.py`). A connector that
exhausts every retry surfaces FAILED with a sanitized `last_error` and never
aborts the pass for other connectors (T-37-12).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.encryption import encrypt_value
from app.ticketing import daily_sync as m
from app.ticketing.models import ConnectorConfig, SyncLog


async def _no_sleep(_seconds: float) -> None:
    """Speeds up retry-backoff tests (real backoff is ~1s/2s/4s = 7s)."""
    return None


def _seed_asana_connector(tenant_id: uuid.UUID) -> ConnectorConfig:
    creds = {"access_token": "fake-asana-token"}
    return ConnectorConfig(
        tenant_id=tenant_id,
        connector_type="ASANA",
        is_enabled=True,
        credentials_secret_arn=json.dumps({k: encrypt_value(v) for k, v in creds.items()}),
        config={},
    )


def _seed_github_connector(tenant_id: uuid.UUID) -> ConnectorConfig:
    creds = {"token": "fake-gh-token"}
    return ConnectorConfig(
        tenant_id=tenant_id,
        connector_type="GITHUB",
        is_enabled=True,
        credentials_secret_arn=json.dumps({k: encrypt_value(v) for k, v in creds.items()}),
        config={"owner": "acme", "repo": "widgets"},
    )


async def _sync_logs_for(db_session, connector_id) -> list[SyncLog]:
    result = await db_session.execute(select(SyncLog).where(SyncLog.connector_id == connector_id))
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_transient_failure_retries_then_succeeds_records_success_columns(db_session, tenant_a, monkeypatch):
    connector = _seed_asana_connector(tenant_a)
    db_session.add(connector)
    await db_session.commit()

    monkeypatch.setattr(m.asyncio, "sleep", _no_sleep)

    call_count = {"n": 0}

    async def flaky_sync(db, tenant_id, client):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ConnectionError("simulated transient network failure")
        return {"synced": 2, "resolved": 0, "comments_added": 0}

    monkeypatch.setattr(m, "_sync_asana_tickets", flaky_sync)

    result = await m.run_daily_ticket_sync(db_session)

    assert call_count["n"] == 3  # 2 failures + 1 success, within the 3-attempt bound
    assert result["synced"] == 2

    await db_session.refresh(connector)
    assert connector.last_sync_status == "SUCCESS"
    assert connector.last_sync_record_count == 2
    assert connector.consecutive_failure_count == 0
    assert connector.last_error is None
    assert connector.last_sync_at is not None

    logs = await _sync_logs_for(db_session, connector.id)
    assert len(logs) == 1
    assert logs[0].status == "SUCCESS"
    assert logs[0].records_fetched == 2


@pytest.mark.asyncio
async def test_all_retries_exhausted_marks_failed_with_sanitized_error(db_session, tenant_a, monkeypatch):
    connector = _seed_asana_connector(tenant_a)
    db_session.add(connector)
    await db_session.commit()

    monkeypatch.setattr(m.asyncio, "sleep", _no_sleep)

    call_count = {"n": 0}
    _secret_token = "abc123def456ghi789jklmno"  # noqa: S105 - fake test secret shape, not a real credential

    async def always_fails(db, tenant_id, client):
        call_count["n"] += 1
        raise RuntimeError(f"upstream 500: Bearer {_secret_token} rejected")

    monkeypatch.setattr(m, "_sync_asana_tickets", always_fails)

    await m.run_daily_ticket_sync(db_session)

    assert call_count["n"] == 3  # bounded retry -- never more than 3 attempts

    await db_session.refresh(connector)
    assert connector.last_sync_status == "FAILED"
    assert connector.consecutive_failure_count == 1
    assert connector.last_error is not None
    assert "Bearer" not in connector.last_error
    assert _secret_token not in connector.last_error

    logs = await _sync_logs_for(db_session, connector.id)
    assert len(logs) == 1
    assert logs[0].status == "FAILED"
    assert logs[0].error_message is not None
    assert _secret_token not in logs[0].error_message


@pytest.mark.asyncio
async def test_failed_connector_does_not_abort_pass_second_connector_still_succeeds(db_session, tenant_a, monkeypatch):
    """T-37-12 isolation: one connector exhausting retries must not prevent
    another (healthy) connector in the same pass from recording SUCCESS."""
    bad_connector = _seed_asana_connector(tenant_a)
    good_connector = _seed_github_connector(tenant_a)
    db_session.add(bad_connector)
    db_session.add(good_connector)
    await db_session.commit()

    monkeypatch.setattr(m.asyncio, "sleep", _no_sleep)

    async def always_fails(db, tenant_id, client):
        raise RuntimeError("persistent upstream outage")

    monkeypatch.setattr(m, "_sync_asana_tickets", always_fails)
    # _sync_github_tickets is NOT patched -- the real function runs against
    # zero seeded Ticket rows for this tenant/provider, so it returns
    # {"synced": 0, ...} immediately without any HTTP call (no mock needed).

    await m.run_daily_ticket_sync(db_session)

    await db_session.refresh(bad_connector)
    await db_session.refresh(good_connector)

    assert bad_connector.last_sync_status == "FAILED"
    assert bad_connector.consecutive_failure_count == 1

    assert good_connector.last_sync_status == "SUCCESS"
    assert good_connector.last_sync_record_count == 0
    assert good_connector.consecutive_failure_count == 0
    assert good_connector.last_error is None


@pytest.mark.asyncio
async def test_repeated_failures_increment_consecutive_failure_count(db_session, tenant_a, monkeypatch):
    connector = _seed_asana_connector(tenant_a)
    connector.consecutive_failure_count = 2
    db_session.add(connector)
    await db_session.commit()

    monkeypatch.setattr(m.asyncio, "sleep", _no_sleep)

    async def always_fails(db, tenant_id, client):
        raise RuntimeError("still down")

    monkeypatch.setattr(m, "_sync_asana_tickets", always_fails)

    await m.run_daily_ticket_sync(db_session)

    await db_session.refresh(connector)
    assert connector.consecutive_failure_count == 3


@pytest.mark.asyncio
async def test_success_resets_consecutive_failure_count_to_zero(db_session, tenant_a, monkeypatch):
    connector = _seed_asana_connector(tenant_a)
    connector.consecutive_failure_count = 4
    connector.last_error = "some prior failure"
    db_session.add(connector)
    await db_session.commit()

    monkeypatch.setattr(m.asyncio, "sleep", _no_sleep)

    async def ok_sync(db, tenant_id, client):
        return {"synced": 1, "resolved": 0, "comments_added": 0}

    monkeypatch.setattr(m, "_sync_asana_tickets", ok_sync)

    await m.run_daily_ticket_sync(db_session)

    await db_session.refresh(connector)
    assert connector.consecutive_failure_count == 0
    assert connector.last_error is None
    assert connector.last_sync_status == "SUCCESS"
