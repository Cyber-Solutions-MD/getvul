"""Tests for the scheduler's enrichment-refresh dispatch (ENRICH-05, Phase 31
Plan 02) -- the daily 24h-gated, eager-first-run, atomic-swap-aware refresh
of the global `epss_scores`/`cisa_kev` reference tables.

Mirrors `test_scheduler_ai_batch.py`'s structure and its `from app.connectors
import scheduler as scheduler_module; await scheduler_module.<fn>(...)`
direct-await convention. UNLIKE the AI batch dispatchers (which
`asyncio.create_task` a detached background job), `_dispatch_enrichment_
refresh` is awaited INLINE by `_scheduler_loop()` (31-RESEARCH.md Pattern 2
deviation, A5) -- D-09's atomic-swap transaction must run to completion as
one unit and the 24h gate must only advance once it has actually committed.
Every test here therefore calls the dispatcher directly with NO
`asyncio.sleep(0)` "let the task run" step -- by the time `await
scheduler_module._dispatch_enrichment_refresh()` returns, the whole
gate-check + refresh + repropagate + commit sequence has already resolved.

Every test monkeypatches `app.connectors.enrichment_feeds.
refresh_enrichment_reference_data`/`repropagate_enrichment` with a fake --
the dispatcher's own `from app.connectors.enrichment_feeds import ...` is a
LOCAL import inside the function body, so it re-resolves the module
attribute fresh on every call, picking up whatever `monkeypatch.setattr`
most recently set (same idiom `test_scheduler_ai_batch.py` documents for
`app.ai.batch.run_batch_prewarm`).

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`) + JWT_SECRET_KEY set,
per-file.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.connectors import scheduler as scheduler_module


async def test_dispatch_enrichment_refresh_24h_gated(monkeypatch):
    """Mirrors test_scheduler_ai_batch.py::test_nightly_submit_24h_gated:
    dispatch once from a cold (None) gate -> the refresh runs, gate
    advances; an immediate second call must NOT re-dispatch."""
    monkeypatch.setattr(scheduler_module, "_last_enrichment_refresh", None)

    calls: list[None] = []

    async def fake_refresh(db):
        calls.append(None)
        return {"status": "ok", "epss_rows": 2, "kev_rows": 1}

    async def fake_repropagate(db):
        return {"repropagated": 0}

    monkeypatch.setattr("app.connectors.enrichment_feeds.refresh_enrichment_reference_data", fake_refresh)
    monkeypatch.setattr("app.connectors.enrichment_feeds.repropagate_enrichment", fake_repropagate)

    await scheduler_module._dispatch_enrichment_refresh()
    assert len(calls) == 1
    assert scheduler_module._last_enrichment_refresh is not None

    await scheduler_module._dispatch_enrichment_refresh()
    assert len(calls) == 1  # NOT re-dispatched


async def test_dispatch_enrichment_refresh_dispatches_again_after_24h(monkeypatch):
    """A stale (>= 86400s ago) `_last_enrichment_refresh` re-dispatches on
    the next call, and the gate timestamp advances past the stale value."""
    stale = datetime.now(UTC) - timedelta(seconds=86401)
    monkeypatch.setattr(scheduler_module, "_last_enrichment_refresh", stale)

    calls: list[None] = []

    async def fake_refresh(db):
        calls.append(None)
        return {"status": "ok", "epss_rows": 0, "kev_rows": 0}

    async def fake_repropagate(db):
        return {"repropagated": 0}

    monkeypatch.setattr("app.connectors.enrichment_feeds.refresh_enrichment_reference_data", fake_refresh)
    monkeypatch.setattr("app.connectors.enrichment_feeds.repropagate_enrichment", fake_repropagate)

    await scheduler_module._dispatch_enrichment_refresh()

    assert len(calls) == 1
    assert scheduler_module._last_enrichment_refresh is not None
    assert scheduler_module._last_enrichment_refresh > stale


async def test_dispatch_enrichment_refresh_atomic_swap_failure_does_not_advance_gate(monkeypatch):
    """D-09: a failed atomic-swap refresh must NOT advance the 24h gate --
    the very next tick (or the next eager start_scheduler() call) retries,
    rather than silently sitting on stale/empty ref data for a whole day.
    Re-propagation must also be skipped entirely on a failed swap (nothing
    new to propagate, and propagating against last night's -- now
    unverified -- data would be pointless work)."""
    monkeypatch.setattr(scheduler_module, "_last_enrichment_refresh", None)

    async def fake_failed_refresh(db):
        return {"status": "failed", "error": "feed unreachable"}

    repropagate_calls: list[None] = []

    async def fake_repropagate(db):
        repropagate_calls.append(None)
        return {"repropagated": 0}

    monkeypatch.setattr("app.connectors.enrichment_feeds.refresh_enrichment_reference_data", fake_failed_refresh)
    monkeypatch.setattr("app.connectors.enrichment_feeds.repropagate_enrichment", fake_repropagate)

    await scheduler_module._dispatch_enrichment_refresh()

    assert scheduler_module._last_enrichment_refresh is None  # gate did not advance
    assert repropagate_calls == []  # never re-propagate off the back of a failed swap


async def test_dispatch_enrichment_refresh_dispatch_exception_is_caught(monkeypatch):
    """A dispatch-time failure (here: the fake raising synchronously, a
    stand-in for e.g. a DB-connection error opening `async_session_factory`)
    must be caught by the dispatcher's own try/except and never propagate
    out -- and must NOT advance the gate either."""
    monkeypatch.setattr(scheduler_module, "_last_enrichment_refresh", None)

    async def bad_refresh(db):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.connectors.enrichment_feeds.refresh_enrichment_reference_data", bad_refresh)

    # Must not raise.
    await scheduler_module._dispatch_enrichment_refresh()

    assert scheduler_module._last_enrichment_refresh is None


async def test_start_scheduler_eagerly_dispatches_enrichment_refresh(monkeypatch):
    """D-10: on startup, a cold (None) `_last_enrichment_refresh` gate means
    `start_scheduler()` immediately dispatches the enrichment refresh rather
    than waiting for `_scheduler_loop()`'s first natural 60s tick -- calling
    the SAME gate-checked dispatcher once at startup is sufficient because
    its own internal 24h-gate (None-or-stale) already encodes "empty/cold
    ref table" semantics for a freshly-booted process, with no separate
    DB-staleness probe needed."""
    monkeypatch.setattr(scheduler_module, "_last_enrichment_refresh", None)
    monkeypatch.setattr(scheduler_module, "_scheduler_task", None)

    # Replace the real (infinite while-True) loop with a no-op coroutine so
    # start_scheduler()'s own asyncio.create_task(_scheduler_loop()) call
    # doesn't leak a live 60s-sleep background task across the test suite.
    async def _noop_loop() -> None:
        return None

    monkeypatch.setattr(scheduler_module, "_scheduler_loop", _noop_loop)

    calls: list[None] = []

    async def fake_refresh(db):
        calls.append(None)
        return {"status": "ok", "epss_rows": 0, "kev_rows": 0}

    async def fake_repropagate(db):
        return {"repropagated": 0}

    monkeypatch.setattr("app.connectors.enrichment_feeds.refresh_enrichment_reference_data", fake_refresh)
    monkeypatch.setattr("app.connectors.enrichment_feeds.repropagate_enrichment", fake_repropagate)

    scheduler_module.start_scheduler()
    await asyncio.sleep(0.05)  # let the eagerly-created task actually run to completion

    assert len(calls) == 1
    assert scheduler_module._last_enrichment_refresh is not None

    scheduler_module.stop_scheduler()


async def test_start_scheduler_eager_dispatch_does_not_fire_when_gate_is_warm(monkeypatch):
    """If the gate is already warm (a refresh ran recently, e.g. a scheduler
    restart shortly after a successful refresh), the eager startup call must
    NOT re-dispatch -- it reuses the exact same 24h-gate check, it isn't a
    second, separate "always run on boot" path."""
    warm = datetime.now(UTC)
    monkeypatch.setattr(scheduler_module, "_last_enrichment_refresh", warm)
    monkeypatch.setattr(scheduler_module, "_scheduler_task", None)

    async def _noop_loop() -> None:
        return None

    monkeypatch.setattr(scheduler_module, "_scheduler_loop", _noop_loop)

    calls: list[None] = []

    async def fake_refresh(db):
        calls.append(None)
        return {"status": "ok", "epss_rows": 0, "kev_rows": 0}

    monkeypatch.setattr("app.connectors.enrichment_feeds.refresh_enrichment_reference_data", fake_refresh)

    scheduler_module.start_scheduler()
    await asyncio.sleep(0.05)

    assert calls == []
    assert scheduler_module._last_enrichment_refresh == warm  # unchanged

    scheduler_module.stop_scheduler()


async def test_dispatch_enrichment_refresh_concurrent_calls_do_not_race(monkeypatch):
    """Regression (Rule 1 bug, found via live reproduction against the
    docker dev stack's --reload backend, not speculative): `start_scheduler()`'s
    eager call and `_scheduler_loop()`'s own first-tick inline call both fire
    nearly simultaneously on process startup. The in-memory
    `_last_enrichment_refresh is None` check ALONE is a check-then-act race
    -- both call sites can observe `None` before either finishes setting the
    gate, so both would proceed to fetch+swap concurrently without a lock.
    Confirmed empirically this races into a real `UniqueViolationError` on
    `epss_scores_pkey` from two overlapping delete-then-insert swaps.

    This test proves `_enrichment_refresh_lock` closes the window: a second
    concurrent call while a refresh is already in-flight must be a clean
    no-op (zero additional fetch calls), never a second overlapping swap."""
    monkeypatch.setattr(scheduler_module, "_last_enrichment_refresh", None)

    calls: list[None] = []
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_refresh(db):
        calls.append(None)
        entered.set()
        await release.wait()
        return {"status": "ok", "epss_rows": 0, "kev_rows": 0}

    async def fake_repropagate(db):
        return {"repropagated": 0}

    monkeypatch.setattr("app.connectors.enrichment_feeds.refresh_enrichment_reference_data", slow_refresh)
    monkeypatch.setattr("app.connectors.enrichment_feeds.repropagate_enrichment", fake_repropagate)

    task_a = asyncio.create_task(scheduler_module._dispatch_enrichment_refresh())
    await entered.wait()  # deterministically wait until task_a is inside the locked section

    task_b = asyncio.create_task(scheduler_module._dispatch_enrichment_refresh())
    await asyncio.sleep(0)  # let task_b run its (fully synchronous) lock-check-and-return path

    assert len(calls) == 1  # task_b observed the lock held and returned WITHOUT a second fetch

    release.set()
    await task_a
    await task_b

    assert scheduler_module._last_enrichment_refresh is not None


async def test_scheduler_module_enrichment_refresh_builds_no_client(monkeypatch):
    """The dispatcher passes NO extra positional/keyword argument beyond its
    own `db` session -- it resolves nothing per-tenant (these are global,
    no-tenant_id reference tables, D-11) and holds no client state itself."""
    monkeypatch.setattr(scheduler_module, "_last_enrichment_refresh", None)

    received_args: list[tuple] = []
    received_kwargs: list[dict] = []

    async def fake_refresh(*args, **kwargs):
        received_args.append(args[1:])  # drop the leading `db` positional
        received_kwargs.append(kwargs)
        return {"status": "ok", "epss_rows": 0, "kev_rows": 0}

    async def fake_repropagate(*args, **kwargs):
        return {"repropagated": 0}

    monkeypatch.setattr("app.connectors.enrichment_feeds.refresh_enrichment_reference_data", fake_refresh)
    monkeypatch.setattr("app.connectors.enrichment_feeds.repropagate_enrichment", fake_repropagate)

    await scheduler_module._dispatch_enrichment_refresh()

    assert received_args == [()]
    assert received_kwargs == [{}]
