"""Phase 23 Plan 07 — connector health signals (REL-06, D-18/D-19).

Proves the runtime side of the connector health columns added in Plan 06
(`consecutive_failure_count`, `last_error`):
  - increments on any FAILED sync outcome (exception path, auth-failure
    early-return path) and resets to 0 + clears `last_error` on SUCCESS.
  - `last_error` is captured via the reused Phase-7 `app.logging` redaction
    machinery (key-based `_redact_value`) composed with a pattern-based
    scrub, per the 23-RESEARCH Pitfall 4 / Open Question 7 correction — a
    crafted `Bearer <token>`-shaped secret must not survive into
    `last_error` verbatim.
  - the truncation cap is applied after redaction.
  - the scheduler-driven path (`app.connectors.scheduler._run_single_sync`)
    produces identical counter/last_error semantics to the direct
    `run_sync` path, proving there is exactly one implementation (T-23-21).

A minimal in-memory `_FakeConnector` (registered into `sync.CONNECTOR_CLASSES`
under a throwaway "FAKE" type via monkeypatch) drives each outcome without
touching any real scanner HTTP layer — `connector_type` is a plain string
column with no DB-level enum constraint, so this is safe.
"""

from __future__ import annotations

import uuid

import pytest
import structlog.testing
from sqlalchemy import select

import app.connectors.sync as sync_module
from app.connectors.base import BaseConnector
from app.connectors.sync import SyncLog, _sanitize_error, run_sync
from app.ticketing.models import ConnectorConfig


class _FakeConnector(BaseConnector):
    """Minimal connector whose behavior is driven by class-level attributes.

    `sync.py`'s harness instantiates connectors with `connector_cls()` (no
    constructor args), so per-test behavior is configured via class
    attributes rather than `__init__` args — each test sets them via
    `monkeypatch.setattr` so they're auto-restored.
    """

    source_name = "FAKE"
    AUTH_OK: bool = True
    RAISE: Exception | None = None

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        return self.AUTH_OK

    async def fetch_vulnerabilities(self) -> list:
        if self.RAISE is not None:
            raise self.RAISE
        return []

    async def fetch_misconfigurations(self) -> list:
        return []


@pytest.fixture(autouse=True)
def _register_fake_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register FAKE into sync.CONNECTOR_CLASSES for the duration of each test.

    scheduler.py imports `run_sync` from this same module and reads the same
    module-level `CONNECTOR_CLASSES` dict object at call time, so this single
    monkeypatch covers both the direct and scheduler-driven test paths.
    """
    monkeypatch.setitem(sync_module.CONNECTOR_CLASSES, "FAKE", _FakeConnector)
    # Reset class-level state before/after each test so tests can't bleed
    # into each other via the shared class attributes.
    monkeypatch.setattr(_FakeConnector, "AUTH_OK", True)
    monkeypatch.setattr(_FakeConnector, "RAISE", None)


def _seed_fake_connector(tenant_id: uuid.UUID, *, consecutive_failure_count: int = 0) -> ConnectorConfig:
    return ConnectorConfig(
        tenant_id=tenant_id,
        connector_type="FAKE",
        is_enabled=True,
        credentials_secret_arn=None,
        config={},
        consecutive_failure_count=consecutive_failure_count,
    )


# ── Direct path (run_sync) ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_success_resets_counter_and_clears_last_error(db_session, tenant_a, monkeypatch):
    connector = _seed_fake_connector(tenant_a, consecutive_failure_count=3)
    connector.last_error = "stale error from a previous failure"
    db_session.add(connector)
    await db_session.flush()

    monkeypatch.setattr(_FakeConnector, "AUTH_OK", True)
    monkeypatch.setattr(_FakeConnector, "RAISE", None)

    log = await run_sync(db_session, connector)

    assert log.status == "SUCCESS"
    assert connector.consecutive_failure_count == 0
    assert connector.last_error is None


@pytest.mark.asyncio
async def test_failure_increments_counter_and_sets_sanitized_last_error(db_session, tenant_a, monkeypatch):
    connector = _seed_fake_connector(tenant_a, consecutive_failure_count=0)
    db_session.add(connector)
    await db_session.flush()

    secret_exc = Exception("upstream 401: Authorization: Bearer sk-secret123 was rejected")
    monkeypatch.setattr(_FakeConnector, "AUTH_OK", True)
    monkeypatch.setattr(_FakeConnector, "RAISE", secret_exc)

    log = await run_sync(db_session, connector)

    assert log.status == "FAILED"
    assert connector.last_sync_status == "FAILED"
    assert connector.consecutive_failure_count == 1
    assert connector.last_error is not None
    assert "sk-secret123" not in connector.last_error
    assert "Bearer" not in connector.last_error


@pytest.mark.asyncio
async def test_failure_increments_from_prior_nonzero_value(db_session, tenant_a, monkeypatch):
    connector = _seed_fake_connector(tenant_a, consecutive_failure_count=2)
    db_session.add(connector)
    await db_session.flush()

    monkeypatch.setattr(_FakeConnector, "AUTH_OK", True)
    monkeypatch.setattr(_FakeConnector, "RAISE", Exception("boom"))

    await run_sync(db_session, connector)

    assert connector.consecutive_failure_count == 3


@pytest.mark.asyncio
async def test_auth_failure_path_increments_and_sets_last_error(db_session, tenant_a, monkeypatch):
    connector = _seed_fake_connector(tenant_a, consecutive_failure_count=0)
    db_session.add(connector)
    await db_session.flush()

    monkeypatch.setattr(_FakeConnector, "AUTH_OK", False)

    log = await run_sync(db_session, connector)

    assert log.status == "FAILED"
    assert connector.last_sync_status == "FAILED"
    assert connector.consecutive_failure_count == 1
    assert connector.last_error == "Authentication failed"


def test_sanitize_error_truncates_after_redaction():
    # Space-separated words (not one long token-shaped run) so truncation,
    # not the token-pattern scrub, is what's under test.
    long_message = "connection failed while syncing host " * 60
    result = _sanitize_error(Exception(long_message), cap=500)
    assert len(result) == 500


def test_sanitize_error_scrubs_basic_auth_and_long_tokens():
    exc = Exception("failed with Basic dXNlcjpwYXNz and key abcdefghij0123456789ABCDEFGHIJ0123")
    result = _sanitize_error(exc)
    assert "dXNlcjpwYXNz" not in result
    assert "abcdefghij0123456789ABCDEFGHIJ0123" not in result


# ── Scheduler-path parity (Task 2, T-23-21) ─────────────────────────────────
#
# scheduler.py's `_run_single_sync` delegates straight to `sync.run_sync` —
# confirmed by inspection (no duplicate write-back logic exists there). These
# tests prove that delegation holds at runtime: a scheduler-driven failure/
# success produces identical consecutive_failure_count/last_error semantics
# to the direct path above, so the two paths cannot drift (T-23-21).


@pytest.mark.asyncio
async def test_scheduler_path_failure_parity(db_session, tenant_a, monkeypatch):
    """The scheduler's `_run_single_sync` delegates to the same `run_sync` —
    proving one implementation, not a divergent counter/last_error path."""
    from app.connectors import scheduler as scheduler_module

    connector = _seed_fake_connector(tenant_a, consecutive_failure_count=0)
    db_session.add(connector)
    await db_session.commit()  # scheduler opens its own session — must be visible

    monkeypatch.setattr(_FakeConnector, "AUTH_OK", True)
    monkeypatch.setattr(_FakeConnector, "RAISE", Exception("Authorization: Bearer sk-scheduler-secret"))

    await scheduler_module._run_single_sync(str(connector.id), str(tenant_a))

    # `async_session_factory` is `expire_on_commit=False` (app/db/session.py),
    # so the test's `db_session` identity map won't auto-refresh `connector`'s
    # attributes from the scheduler's separately-committed transaction — force
    # a reload of this specific instance.
    await db_session.refresh(connector)

    assert connector.last_sync_status == "FAILED"
    assert connector.consecutive_failure_count == 1
    assert connector.last_error is not None
    assert "sk-scheduler-secret" not in connector.last_error
    assert "Bearer" not in connector.last_error


@pytest.mark.asyncio
async def test_scheduler_path_error_message_and_log_are_sanitized(db_session, tenant_a, monkeypatch):
    """CR-03 regression: `SyncLog.error_message` must go through the same
    `_sanitize_error` redaction as its sibling `connector_config.last_error`,
    and the scheduler's `background_sync_complete` log event (which logs
    `error=log.error_message` verbatim) must therefore be clean by
    construction. Reverting the Task 1 fix (restoring
    `log.error_message = str(e)[:2000]`) must fail this test."""
    from app.connectors import scheduler as scheduler_module

    connector = _seed_fake_connector(tenant_a, consecutive_failure_count=0)
    db_session.add(connector)
    await db_session.commit()  # scheduler opens its own session — must be visible

    secret_exc = Exception("upstream 401: Authorization: Bearer sk-log-leak-42 rejected")
    monkeypatch.setattr(_FakeConnector, "AUTH_OK", True)
    monkeypatch.setattr(_FakeConnector, "RAISE", secret_exc)

    with structlog.testing.capture_logs() as captured_logs:
        await scheduler_module._run_single_sync(str(connector.id), str(tenant_a))

    result = await db_session.execute(
        select(SyncLog)
        .where(SyncLog.connector_id == connector.id, SyncLog.tenant_id == tenant_a)
        .order_by(SyncLog.started_at.desc())
    )
    log = result.scalars().first()

    assert log is not None
    assert log.error_message is not None
    assert "sk-log-leak-42" not in log.error_message
    assert "Bearer" not in log.error_message
    assert "[REDACTED]" in log.error_message

    logs_repr = repr(captured_logs)
    assert "sk-log-leak-42" not in logs_repr
    assert "Bearer" not in logs_repr

    complete_events = [entry for entry in captured_logs if entry.get("event") == "background_sync_complete"]
    assert len(complete_events) == 1
    assert "sk-log-leak-42" not in str(complete_events[0].get("error"))
    assert "Bearer" not in str(complete_events[0].get("error"))


@pytest.mark.asyncio
async def test_scheduler_path_success_parity(db_session, tenant_a, monkeypatch):
    from app.connectors import scheduler as scheduler_module

    connector = _seed_fake_connector(tenant_a, consecutive_failure_count=4)
    connector.last_error = "stale"
    db_session.add(connector)
    await db_session.commit()

    monkeypatch.setattr(_FakeConnector, "AUTH_OK", True)
    monkeypatch.setattr(_FakeConnector, "RAISE", None)

    await scheduler_module._run_single_sync(str(connector.id), str(tenant_a))

    await db_session.refresh(connector)

    assert connector.last_sync_status == "SUCCESS"
    assert connector.consecutive_failure_count == 0
    assert connector.last_error is None
