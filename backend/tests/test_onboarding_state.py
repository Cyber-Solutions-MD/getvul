"""Phase 10 / Plan 01 — Wave 0 RED.

Behaviour under test: GET /api/v1/vulnerabilities/stats must expose a
top-level `onboarding_state` field whose value is one of:
  - 'no_scanners'  → tenant has zero enabled ConnectorConfig rows
  - 'no_data_yet'  → enabled connectors exist but none synced SUCCESS
  - 'ready'        → at least one enabled connector synced SUCCESS

per D-O-01 (REQ UX-02-06). Tests will fail until Task 2 lands the
detection helper in backend/app/vulnerabilities/dashboard.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.ticketing.models import ConnectorConfig


@pytest.mark.asyncio
async def test_onboarding_state_no_scanners(client, db_session, tenant_a):
    """UX-02-06 / D-O-01: zero enabled connectors → 'no_scanners'."""
    # No ConnectorConfig rows for tenant_a
    body = (await client.get("/api/v1/vulnerabilities/stats")).json()
    assert body.get("onboarding_state") == "no_scanners"


@pytest.mark.asyncio
async def test_onboarding_state_no_data_yet(client, db_session, tenant_a):
    """UX-02-06 / D-O-01: enabled connector exists but never synced SUCCESS
    → 'no_data_yet'."""
    db_session.add(
        ConnectorConfig(
            tenant_id=tenant_a,
            connector_type="CROWDSTRIKE",
            is_enabled=True,
            last_sync_status=None,  # never run, or failed/pending — anything not 'SUCCESS'
        )
    )
    await db_session.commit()

    body = (await client.get("/api/v1/vulnerabilities/stats")).json()
    assert body.get("onboarding_state") == "no_data_yet"


@pytest.mark.asyncio
async def test_onboarding_state_ready(client, db_session, tenant_a):
    """UX-02-06 / D-O-01: at least one enabled connector synced SUCCESS → 'ready'."""
    db_session.add(
        ConnectorConfig(
            tenant_id=tenant_a,
            connector_type="CROWDSTRIKE",
            is_enabled=True,
            last_sync_status="SUCCESS",
            last_sync_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    body = (await client.get("/api/v1/vulnerabilities/stats")).json()
    assert body.get("onboarding_state") == "ready"
