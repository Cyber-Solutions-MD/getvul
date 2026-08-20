"""Phase 8 — Intune (MDM) connector coverage.

Covers the pure ISO parser, the paginated device fetch (httpx.MockTransport),
and the asset-enrichment mapping. run_intune_sync itself is DB/graph
integration; these are its correctness-critical units.

Phase 41 (COV-01 / Pitfall 1 fix): added a DB-integration test proving
run_intune_sync now constructs a valid, tenant-scoped SyncLog and persists a
tenant-scoped, INTUNE-tagged Asset (previously a TypeError on the bad
connector_config_id kwarg meant this path never ran end-to-end).
"""

from __future__ import annotations

from datetime import UTC

import httpx
import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.connectors import intune_sync as intune_sync_module
from app.connectors.intune_sync import _enrich_asset, _fetch_managed_devices, _parse_iso, run_intune_sync
from app.ticketing.models import ConnectorConfig, SyncLog


def test_parse_iso_handles_z_suffix_and_invalid():
    dt = _parse_iso("2024-01-15T08:30:00Z")
    assert dt is not None
    assert dt.tzinfo == UTC
    assert (dt.year, dt.month, dt.day) == (2024, 1, 15)
    assert _parse_iso(None) is None
    assert _parse_iso("not-a-date") is None


@pytest.mark.asyncio
async def test_fetch_managed_devices_paginates_odata_next_link():
    pages = [
        httpx.Response(200, json={"value": [{"id": "d1"}], "@odata.nextLink": "https://graph/next"}),
        httpx.Response(200, json={"value": [{"id": "d2"}, {"id": "d3"}]}),  # no nextLink → done
    ]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        resp = pages[calls["n"]]
        calls["n"] += 1
        return resp

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://graph")
    try:
        devices = await _fetch_managed_devices(client, "token")
    finally:
        await client.aclose()

    assert [d["id"] for d in devices] == ["d1", "d2", "d3"]
    assert calls["n"] == 2


def test_enrich_asset_maps_intune_device_fields():
    asset = Asset(tenant_id="00000000-0000-0000-0000-000000000001", hostname="LAPTOP-1")
    device = {
        "id": "intune-abc",
        "operatingSystem": "Windows",
        "osVersion": "10.0.19045",
        "serialNumber": "SN-123",
        "manufacturer": "Dell",
        "model": "Latitude 7420",
        "userPrincipalName": "ann@acme.com",
        "complianceState": "compliant",
        "lastSyncDateTime": "2024-02-01T12:00:00Z",
    }
    _enrich_asset(asset, device)

    assert asset.os_name == "Windows"
    assert asset.os_version == "10.0.19045"
    assert asset.serial_number == "SN-123"
    assert asset.model == "Dell Latitude 7420"
    assert asset.system_manufacturer == "Dell"
    assert asset.assigned_user == "ann@acme.com"
    assert asset.managed_by == "INTUNE"
    assert "INTUNE" in (asset.seen_by_sources or [])
    assert asset.mdm_details["intune_device_id"] == "intune-abc"
    assert asset.mdm_details["complianceState"] == "compliant"
    assert asset.last_checkin_at is not None
    # Enrichment must classify + assign a device_category (the prior code called
    # the wrong classify function with an Asset arg, crashed, and never set it).
    assert asset.device_category  # non-empty category string


@pytest.mark.asyncio
async def test_run_intune_sync_persists_synclog_and_tenant_scoped_asset(db_session, tenant_a, monkeypatch):
    """run_intune_sync (Pitfall 1 fix): a valid SyncLog row is created for the
    connector's tenant, and the discovered device lands as a tenant-scoped
    Asset carrying INTUNE in seen_by_sources."""
    connector_config = ConnectorConfig(
        tenant_id=tenant_a,
        connector_type="INTUNE",
        is_enabled=True,
        credentials_secret_arn=None,
        config={},
    )
    db_session.add(connector_config)
    await db_session.flush()

    # Stub credential decryption — this test never touches Fernet or a real
    # secret; only the fields run_intune_sync reads off the returned dict.
    monkeypatch.setattr(
        intune_sync_module,
        "get_decrypted_credentials",
        lambda _connector: {"tenant_id": "aad-tenant-id", "client_id": "cid", "client_secret": "secret"},
    )

    async def _fake_get_access_token(client, tenant_id, client_id, client_secret):
        return "fake-token"

    async def _fake_fetch_managed_devices(client, token):
        return [
            {
                "id": "intune-device-1",
                "deviceName": "LAPTOP-42",
                "operatingSystem": "Windows",
                "osVersion": "10.0.19045",
                "serialNumber": "SN-999",
                "userPrincipalName": "bob@acme.com",
                "complianceState": "compliant",
                "lastSyncDateTime": "2024-03-01T00:00:00Z",
            }
        ]

    monkeypatch.setattr(intune_sync_module, "_get_access_token", _fake_get_access_token)
    monkeypatch.setattr(intune_sync_module, "_fetch_managed_devices", _fake_fetch_managed_devices)

    sync_log = await run_intune_sync(db_session, connector_config)
    await db_session.flush()

    assert sync_log.status == "SUCCESS"
    assert sync_log.tenant_id == tenant_a
    assert sync_log.connector_id == connector_config.id

    log_rows = (
        (await db_session.execute(select(SyncLog).where(SyncLog.connector_id == connector_config.id)))
        .scalars()
        .all()
    )
    assert len(log_rows) == 1
    assert log_rows[0].status == "SUCCESS"
    assert log_rows[0].tenant_id == tenant_a

    asset = (
        (await db_session.execute(select(Asset).where(Asset.tenant_id == tenant_a, Asset.hostname == "laptop-42")))
        .scalars()
        .first()
    )
    assert asset is not None
    assert asset.tenant_id == tenant_a
    assert "INTUNE" in (asset.seen_by_sources or [])
