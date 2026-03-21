"""Background sync scheduler — runs connector syncs on their configured intervals."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.sync import run_sync
from app.db.session import async_session_factory
from app.ticketing.models import ConnectorConfig

logger = structlog.get_logger()

# Track running tasks
_running_syncs: dict[str, asyncio.Task] = {}
_scheduler_task: asyncio.Task | None = None


async def _run_single_sync(connector_id: str, tenant_id: str) -> None:
    """Run a single connector sync in the background."""
    logger.info("background_sync_start", connector_id=connector_id)

    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(ConnectorConfig).where(ConnectorConfig.id == connector_id)
            )
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


async def _scheduler_loop() -> None:
    """Periodic loop that checks all connectors and triggers syncs when due."""
    logger.info("sync_scheduler_started")

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

                now = datetime.now(timezone.utc)

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

        # Check every 60 seconds
        await asyncio.sleep(60)


def start_scheduler() -> None:
    """Start the background scheduler. Call once at app startup."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("sync_scheduler_registered")


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
