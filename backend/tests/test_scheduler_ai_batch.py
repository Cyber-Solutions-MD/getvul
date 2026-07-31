"""Tests for the scheduler's AI batch dispatch (AIP-02, Phase 26 Plan 08) --
the FIRST direct tests of `backend/app/connectors/scheduler.py`'s own
dispatch functions.

Mirrors `test_connector_health.py::test_scheduler_path_failure_parity`'s
`from app.connectors import scheduler as scheduler_module; await
scheduler_module.<fn>(...)` direct-await calling convention -- extended
here to the two NEW `_dispatch_ai_batch_prewarm()`/`_dispatch_ai_batch_poll()`
helpers `_scheduler_loop()` calls each tick (extracted specifically so they
are directly awaitable in isolation; `_scheduler_loop()`'s own infinite
`while True:` loop cannot be awaited to completion in a test).

Every test monkeypatches `app.ai.batch.run_batch_prewarm`/
`app.ai.batch.poll_pending_batches` with a fake -- the dispatcher's own
`from app.ai.batch import run_batch_prewarm` is a LOCAL import inside the
function body, so it re-resolves the module attribute fresh on every call,
picking up whatever `monkeypatch.setattr` most recently set.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`) + JWT_SECRET_KEY set,
per-file.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.connectors import scheduler as scheduler_module


async def test_batch_blocks_are_non_blocking(monkeypatch):
    """Pitfall 3 regression guard: BOTH the nightly-submit and every-tick
    poll dispatchers use `asyncio.create_task`, never an inline `await` --
    a call to either dispatcher must return control BEFORE a slow fake's
    body finishes (proves create_task, not inline await)."""
    monkeypatch.setattr(scheduler_module, "_last_ai_batch_prewarm", None)

    prewarm_event = asyncio.Event()
    poll_event = asyncio.Event()

    async def slow_prewarm(*args, **kwargs):
        await asyncio.sleep(0.05)
        prewarm_event.set()

    async def slow_poll(*args, **kwargs):
        await asyncio.sleep(0.05)
        poll_event.set()

    monkeypatch.setattr("app.ai.batch.run_batch_prewarm", slow_prewarm)
    monkeypatch.setattr("app.ai.batch.poll_pending_batches", slow_poll)

    await scheduler_module._dispatch_ai_batch_prewarm()
    await scheduler_module._dispatch_ai_batch_poll()

    # Both dispatchers must have returned control WITHOUT waiting for
    # either slow fake's 0.05s sleep to complete.
    assert not prewarm_event.is_set()
    assert not poll_event.is_set()

    # Let the dispatched tasks actually run to completion so they don't
    # leak across tests as unawaited/pending-task warnings.
    await asyncio.sleep(0.15)
    assert prewarm_event.is_set()
    assert poll_event.is_set()


async def test_nightly_submit_24h_gated(monkeypatch):
    """A second call immediately after the first must NOT re-dispatch --
    the 24h gate mirrors this file's own `_last_ticket_sync` idiom."""
    monkeypatch.setattr(scheduler_module, "_last_ai_batch_prewarm", None)

    calls: list[None] = []

    async def fake_prewarm(*args, **kwargs):
        calls.append(None)

    monkeypatch.setattr("app.ai.batch.run_batch_prewarm", fake_prewarm)

    await scheduler_module._dispatch_ai_batch_prewarm()
    await asyncio.sleep(0)  # let the created task actually run
    assert len(calls) == 1
    assert scheduler_module._last_ai_batch_prewarm is not None

    await scheduler_module._dispatch_ai_batch_prewarm()
    await asyncio.sleep(0)
    assert len(calls) == 1  # NOT re-dispatched


async def test_nightly_submit_dispatches_again_after_24h(monkeypatch):
    """A stale (>= 86400s ago) `_last_ai_batch_prewarm` re-dispatches on the
    next call, and the gate timestamp advances."""
    stale = datetime.now(UTC) - timedelta(seconds=86401)
    monkeypatch.setattr(scheduler_module, "_last_ai_batch_prewarm", stale)

    calls: list[None] = []

    async def fake_prewarm(*args, **kwargs):
        calls.append(None)

    monkeypatch.setattr("app.ai.batch.run_batch_prewarm", fake_prewarm)

    await scheduler_module._dispatch_ai_batch_prewarm()
    await asyncio.sleep(0)

    assert len(calls) == 1
    assert scheduler_module._last_ai_batch_prewarm is not None
    assert scheduler_module._last_ai_batch_prewarm > stale


async def test_poll_dispatches_every_call_no_gate(monkeypatch):
    """Unlike the nightly submit block, the poll block has NO 24h gate --
    every call dispatches (a submitted batch can end at any point within
    its up-to-24h window)."""
    calls: list[None] = []

    async def fake_poll(*args, **kwargs):
        calls.append(None)

    monkeypatch.setattr("app.ai.batch.poll_pending_batches", fake_poll)

    await scheduler_module._dispatch_ai_batch_poll()
    await asyncio.sleep(0)
    await scheduler_module._dispatch_ai_batch_poll()
    await asyncio.sleep(0)

    assert len(calls) == 2


async def test_dispatch_exception_is_caught(monkeypatch):
    """A dispatch-time failure (here: calling the fake with the wrong
    signature, raising TypeError synchronously -- a stand-in for any
    failure at the `asyncio.create_task(...)` call site itself) must be
    caught by the dispatcher's own try/except and never propagate out of
    the block, for BOTH the nightly-submit and the poll dispatcher."""
    monkeypatch.setattr(scheduler_module, "_last_ai_batch_prewarm", None)

    async def bad_prewarm(required_arg):  # raises TypeError when called with zero args
        pass

    async def bad_poll(required_arg):
        pass

    monkeypatch.setattr("app.ai.batch.run_batch_prewarm", bad_prewarm)
    monkeypatch.setattr("app.ai.batch.poll_pending_batches", bad_poll)

    # Must not raise -- each dispatcher's own try/except contains it.
    await scheduler_module._dispatch_ai_batch_prewarm()
    await scheduler_module._dispatch_ai_batch_poll()


async def test_scheduler_builds_no_client(monkeypatch):
    """The scheduler passes NO client/positional argument to either batch
    function -- each resolves its own per-tenant key(s) internally
    (T-24-19); the scheduler itself stays a thin dispatch with zero
    per-tenant logic."""
    monkeypatch.setattr(scheduler_module, "_last_ai_batch_prewarm", None)

    received_args: list[tuple] = []
    received_kwargs: list[dict] = []

    async def fake_prewarm(*args, **kwargs):
        received_args.append(args)
        received_kwargs.append(kwargs)

    async def fake_poll(*args, **kwargs):
        received_args.append(args)
        received_kwargs.append(kwargs)

    monkeypatch.setattr("app.ai.batch.run_batch_prewarm", fake_prewarm)
    monkeypatch.setattr("app.ai.batch.poll_pending_batches", fake_poll)

    await scheduler_module._dispatch_ai_batch_prewarm()
    await scheduler_module._dispatch_ai_batch_poll()
    await asyncio.sleep(0)  # let the created tasks actually run

    assert received_args == [(), ()]
    assert received_kwargs == [{}, {}]


async def test_scheduler_module_never_imports_asyncanthropic():
    """Static regression guard mirroring the plan's own grep acceptance
    criterion: the scheduler module builds no Anthropic client at all --
    each batch function resolves its own per-tenant key(s) internally."""
    import inspect

    source = inspect.getsource(scheduler_module)
    assert "AsyncAnthropic" not in source
    assert "await run_batch_prewarm" not in source
    assert "await poll_pending_batches" not in source
