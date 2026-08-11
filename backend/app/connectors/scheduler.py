"""Background sync scheduler — runs connector syncs on their configured intervals."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from app.connectors.sync import run_sync
from app.db.session import async_session_factory
from app.ticketing.models import ConnectorConfig

logger = structlog.get_logger()

# Track running tasks
_running_syncs: dict[str, asyncio.Task] = {}
_scheduler_task: asyncio.Task | None = None
_last_ticket_sync: datetime | None = None
_last_ai_batch_prewarm: datetime | None = None
_last_enrichment_refresh: datetime | None = None


async def _run_single_sync(connector_id: str, tenant_id: str) -> None:
    """Run a single connector sync in the background."""
    logger.info("background_sync_start", connector_id=connector_id)

    try:
        async with async_session_factory() as db:
            result = await db.execute(select(ConnectorConfig).where(ConnectorConfig.id == connector_id))
            connector = result.scalar_one_or_none()
            if connector is None:
                logger.error("background_sync_connector_not_found", connector_id=connector_id)
                return

            log = await run_sync(db, connector)
            await db.commit()

            logger.info(
                "background_sync_complete",
                connector_id=connector_id,
                connector_type=connector.connector_type,
                status=log.status,
                records_fetched=log.records_fetched,
                records_created=log.records_created,
                error=log.error_message,
            )
    except Exception as e:
        logger.error("background_sync_error", connector_id=connector_id, error=str(e))
    finally:
        _running_syncs.pop(connector_id, None)


def trigger_background_sync(connector_id: str, tenant_id: str) -> bool:
    """Trigger a sync in the background. Returns False if already running."""
    if connector_id in _running_syncs:
        task = _running_syncs[connector_id]
        if not task.done():
            return False  # Already running

    task = asyncio.create_task(_run_single_sync(connector_id, tenant_id))
    _running_syncs[connector_id] = task
    return True


def is_sync_running(connector_id: str) -> bool:
    """Check if a sync is currently running for a connector."""
    task = _running_syncs.get(connector_id)
    return task is not None and not task.done()


async def _dispatch_ai_batch_prewarm() -> None:
    """AIP-02/D-05 (RESEARCH Pattern 2): nightly, 24h-gated dispatch of the
    Message Batches nightly submitter. Mirrors THIS file's own
    `_last_ticket_sync` 24h-gate TIMING idiom (below, in `_scheduler_loop()`)
    combined with `trigger_background_sync()`'s non-blocking `asyncio.
    create_task` DISPATCH idiom (above) -- explicitly NOT the ticket-sync/
    snapshot blocks' own inline `await`, which is the WRONG idiom to copy
    for dispatch even though it is the more superficially similar "runs
    once per 24h" pattern already in this file.

    `run_batch_prewarm()` opens its OWN db session + Redis client and
    resolves every active tenant's OWN Anthropic key internally (T-24-19) --
    this dispatcher passes NO client and holds no per-tenant state; it is a
    thin gate-check-then-`create_task` call, safe to `await` inline here
    since it never waits for the dispatched batch work itself to finish.

    Extracted to its own top-level function (rather than inlined directly
    in `_scheduler_loop()`'s body) so it is directly unit-testable via the
    established `from app.connectors import scheduler as scheduler_module;
    await scheduler_module.<fn>(...)` convention
    (test_connector_health.py::test_scheduler_path_failure_parity) --
    `_scheduler_loop()`'s own infinite `while True:` loop cannot be awaited
    to completion in a test.
    """
    global _last_ai_batch_prewarm
    try:
        now = datetime.now(UTC)
        if _last_ai_batch_prewarm is None or (now - _last_ai_batch_prewarm).total_seconds() >= 86400:
            from app.ai.batch import run_batch_prewarm

            asyncio.create_task(run_batch_prewarm())
            _last_ai_batch_prewarm = now
    except Exception as e:
        logger.error("ai_batch_prewarm_dispatch_error", error=str(e))


async def _dispatch_ai_batch_poll() -> None:
    """AIP-02/D-05/RESEARCH Pitfall 3: every-tick (no 24h gate -- a
    submitted batch can end at any point within its up-to-24h window, so
    every tick must check) dispatch of the Message Batches poller. ALSO
    `asyncio.create_task`-dispatched: Pitfall 3 warns explicitly that
    leaving JUST the poll side as an inline `await` reintroduces the exact
    tick-stall D-05 exists to forbid, even though D-05's own wording names
    submission specifically.

    `poll_pending_batches()` opens its OWN db session + Redis client and
    resolves each in-flight job's OWNING tenant's key internally
    (T-24-19) -- this dispatcher passes NO client.
    """
    try:
        from app.ai.batch import poll_pending_batches

        asyncio.create_task(poll_pending_batches())
    except Exception as e:
        logger.error("ai_batch_poll_dispatch_error", error=str(e))


async def _dispatch_risk_exposure_backfill() -> None:
    """RISK-07 (34-RESEARCH.md "Design implication for Phase 34"): the
    per-tenant chunked historical-recompute backfill is dispatched via
    `asyncio.create_task` -- mirrors `_dispatch_ai_batch_prewarm`'s shape
    above (long-running, partial progress across many ticks is the whole
    point, must NEVER stall this tick), explicitly NOT
    `_dispatch_enrichment_refresh`'s inline-await/`asyncio.Lock()` shape
    below (that one exists because its atomic delete+insert swap must
    complete as ONE unit before its gate advances -- a backfill chunk is
    the opposite: resumable, incremental progress is the design goal).

    Deliberately NO in-memory `_last_*` gate here (unlike every other
    dispatcher in this file): the gate is the DURABLE per-tenant claim-row
    UPDATE inside `process_backfill_chunk` itself
    (`risk_backfill_service.py`) -- an in-memory gate would reset on the
    exact process restart RISK-07 must survive.

    `dispatch_backfill_chunks` already isolates each tenant's failure in
    its own try/except (mirrors `poll_pending_batches`); the extra
    try/except around the detached task is defense-in-depth so a totally
    unexpected error (e.g. a DB-connect failure before any tenant loop
    starts) still never escapes this create_task'd coroutine.

    Extracted as a top-level function (not inlined in `_scheduler_loop()`)
    so it is directly unit-testable via the established
    `from app.connectors import scheduler as scheduler_module; await
    scheduler_module._dispatch_risk_exposure_backfill()` convention.
    """
    try:
        from app.vulnerabilities.risk_backfill_service import dispatch_backfill_chunks

        async def _run() -> None:
            try:
                async with async_session_factory() as db:
                    await dispatch_backfill_chunks(db)
            except Exception as e:
                logger.error("risk_backfill_dispatch_error", error=str(e))

        asyncio.create_task(_run())
    except Exception as e:
        logger.error("risk_backfill_dispatch_error", error=str(e))


_enrichment_refresh_lock = asyncio.Lock()


async def _dispatch_enrichment_refresh() -> None:
    """ENRICH-05/D-09/D-10 (31-RESEARCH Pattern 2, deliberate deviation from
    `_dispatch_ai_batch_prewarm`'s create_task idiom above): nightly,
    24h-gated refresh of the global `epss_scores`/`cisa_kev` reference
    tables, followed by the D-01/D-02 re-propagation UPDATE onto every
    existing finding.

    Mirrors the INLINE-AWAIT shape of the "Daily ticket status sync" block
    below (NOT `_dispatch_ai_batch_prewarm`'s `asyncio.create_task`
    dispatch) -- D-09's atomic-swap transaction must run to completion as
    ONE unit, and the gate must only advance once it has actually
    committed. Detaching it via `create_task` would let the gate advance
    before the swap itself finishes, defeating the "keeps last good on
    failure" guarantee (a crashed detached task could leave the gate
    advanced with the ref tables still on last night's data, silently
    skipping a whole day). The gate is advanced ONLY after the `async with`
    block below completes, AND only when the swap reports `status == "ok"`
    -- a failed fetch/parse must not consume the day's retry window (D-09).

    Extracted as a top-level function (not inlined in `_scheduler_loop()`)
    so it is directly unit-testable via the established
    `from app.connectors import scheduler as scheduler_module; await
    scheduler_module._dispatch_enrichment_refresh()` convention
    (test_connector_health.py::test_scheduler_path_failure_parity).

    D-10 (eager first-run): `start_scheduler()` ALSO calls this once at
    process startup (in addition to `_scheduler_loop()`'s own per-tick
    call) -- a fresh process always starts with `_last_enrichment_refresh
    is None`, so this dispatcher's own gate already treats "just booted"
    the same as "cold/stale ref table", with no separate DB-staleness
    check needed.

    Concurrency (`_enrichment_refresh_lock`, found via live reproduction
    against the docker dev stack's --reload backend -- Rule 1 bug, not
    speculative): `start_scheduler()`'s eager call and `_scheduler_loop()`'s
    own first-tick inline call both fire nearly simultaneously on process
    startup. The in-memory `_last_enrichment_refresh is None` check ALONE
    is a check-then-act race -- both call sites can observe `None` before
    either finishes setting the gate, so both proceed to fetch+swap
    concurrently. Confirmed empirically: two overlapping delete-then-insert
    swaps interleaved and raised `UniqueViolationError` on `epss_scores_
    pkey`. The lock closes the window -- a concurrent call while a refresh
    is already in-flight is a clean no-op, never a second overlapping swap.
    """
    if _enrichment_refresh_lock.locked():
        return
    global _last_enrichment_refresh
    async with _enrichment_refresh_lock:
        try:
            now = datetime.now(UTC)
            if _last_enrichment_refresh is None or (now - _last_enrichment_refresh).total_seconds() >= 86400:
                from app.connectors.enrichment_feeds import (
                    refresh_enrichment_reference_data,
                    repropagate_enrichment,
                )

                status_ok = False
                async with async_session_factory() as db:
                    result = await refresh_enrichment_reference_data(db)
                    status_ok = result.get("status") == "ok"
                    if status_ok:
                        repropagate_result = await repropagate_enrichment(db)
                        await db.commit()
                        logger.info("enrichment_refresh_completed", **result, **repropagate_result)
                    else:
                        logger.warning("enrichment_refresh_skipped", **result)

                if status_ok:
                    _last_enrichment_refresh = now
        except Exception as e:
            logger.error("enrichment_refresh_dispatch_error", error=str(e))


async def _scheduler_loop() -> None:
    """Periodic loop that checks all connectors and triggers syncs when due."""
    logger.info("sync_scheduler_started")
    _loop_count = 0

    while True:
        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(ConnectorConfig).where(
                        ConnectorConfig.is_enabled.is_(True),
                        ConnectorConfig.credentials_secret_arn.isnot(None),
                    )
                )
                connectors = result.scalars().all()

                now = datetime.now(UTC)

                for connector in connectors:
                    # Skip if already running
                    if is_sync_running(str(connector.id)):
                        continue

                    # Check if sync is due
                    if connector.last_sync_at is None:
                        # Never synced — trigger immediately
                        should_sync = True
                    else:
                        elapsed_minutes = (now - connector.last_sync_at).total_seconds() / 60
                        should_sync = elapsed_minutes >= connector.sync_interval_minutes

                    if should_sync:
                        logger.info(
                            "scheduler_triggering_sync",
                            connector_type=connector.connector_type,
                            connector_id=str(connector.id),
                            interval=connector.sync_interval_minutes,
                        )
                        trigger_background_sync(str(connector.id), str(connector.tenant_id))

        except Exception as e:
            logger.error("scheduler_loop_error", error=str(e))

        # Run ticket rules
        try:
            async with async_session_factory() as db:
                from app.ticketing.rule_engine import run_all_due_rules

                result = await run_all_due_rules(db)
                if result.get("tickets_created", 0) > 0:
                    logger.info("ticket_rules_completed", **result)
        except Exception as e:
            logger.error("ticket_rules_error", error=str(e))

        # Run scheduled reports
        try:
            async with async_session_factory() as db:
                from app.reports import run_due_reports

                result = await run_due_reports(db)
                if result.get("sent", 0) > 0:
                    logger.info("scheduled_reports_sent", **result)
        except Exception as e:
            logger.error("scheduled_reports_error", error=str(e))

        # SLA breach check (runs every loop — lightweight query)
        try:
            async with async_session_factory() as db:
                from sqlalchemy import select as _sel  # noqa: N814

                from app.tenants.models import Tenant as TenantModel
                from app.vulnerabilities.sla_service import backfill_sla_due_dates, check_sla_breaches

                tenants = (await db.execute(_sel(TenantModel).where(TenantModel.is_active.is_(True)))).scalars().all()
                for t in tenants:
                    await backfill_sla_due_dates(db, t.id)
                    await check_sla_breaches(db, t.id)
                await db.commit()
        except Exception as e:
            logger.error("sla_check_error", error=str(e))

        # Daily ticket status sync (every 24 hours)
        global _last_ticket_sync
        try:
            now = datetime.now(UTC)
            if _last_ticket_sync is None or (now - _last_ticket_sync).total_seconds() >= 86400:
                async with async_session_factory() as db:
                    from app.ticketing.daily_sync import run_daily_ticket_sync

                    result = await run_daily_ticket_sync(db)
                    if result.get("comments_added", 0) > 0 or result.get("resolved", 0) > 0:
                        logger.info("daily_ticket_sync_completed", **result)
                _last_ticket_sync = now
        except Exception as e:
            logger.error("daily_ticket_sync_error", error=str(e))

        # Daily snapshot capture (runs with ticket sync — once per 24h)
        try:
            if _last_ticket_sync == now:  # just ran ticket sync = daily trigger
                async with async_session_factory() as db:
                    from app.vulnerabilities.trends import capture_all_snapshots

                    snap_result = await capture_all_snapshots(db)
                    if snap_result.get("captured", 0) > 0:
                        logger.info("daily_snapshots_captured", **snap_result)
        except Exception as e:
            logger.error("daily_snapshot_error", error=str(e))

        # ── Notification alert checks (every 5 minutes) ──
        try:
            if _loop_count % 5 == 0:
                async with async_session_factory() as db:
                    from app.notifications.alerts import run_alert_checks

                    alert_result = await run_alert_checks(db)
                    if alert_result.get("alerts_created", 0) > 0:
                        logger.info("alerts_created", **alert_result)
        except Exception as e:
            logger.error("alert_check_error", error=str(e))

        # AI batch prewarm (nightly, 24h-gated) + poll (every tick) --
        # AIP-02/D-05: both non-blocking asyncio.create_task dispatches;
        # neither dispatcher itself performs any I/O beyond a datetime
        # comparison + `create_task`, so awaiting them inline here never
        # stalls this tick (the batch work they dispatch runs detached).
        await _dispatch_ai_batch_prewarm()
        await _dispatch_ai_batch_poll()

        # Historical risk-exposure backfill (RISK-07, every tick -- no 24h
        # gate, the gate is the durable per-tenant claim-row inside
        # process_backfill_chunk): also a non-blocking asyncio.create_task
        # dispatch (mirrors the two AI batch dispatchers above, not the
        # enrichment-refresh lock/inline-await shape below).
        await _dispatch_risk_exposure_backfill()

        # Enrichment reference-data refresh (nightly, 24h-gated) + D-01/D-02
        # re-propagation -- ENRICH-05: inline-awaited (NOT create_task,
        # unlike the two AI batch dispatchers above) so D-09's atomic-swap
        # transaction runs to completion as one unit before the gate
        # advances (31-RESEARCH.md Pattern 2 deviation).
        await _dispatch_enrichment_refresh()

        _loop_count += 1

        # Check every 60 seconds
        await asyncio.sleep(60)


def start_scheduler() -> None:
    """Start the background scheduler. Call once at app startup."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("sync_scheduler_registered")
        # D-10: eager first-run -- a cold/just-booted process always starts
        # with `_last_enrichment_refresh is None`, so calling the SAME
        # gate-checked dispatcher once here (in addition to
        # `_scheduler_loop()`'s own per-tick call) refreshes an empty/stale
        # ref table immediately rather than waiting for the first natural
        # 60s-interval tick. The dispatcher's own 24h-gate + status check
        # make this idempotent/safe to invoke from both call sites.
        asyncio.create_task(_dispatch_enrichment_refresh())


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
