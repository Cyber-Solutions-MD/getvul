"""Phase 8 — Intune (MDM) connector coverage.

Covers the pure ISO parser, the paginated device fetch (httpx.MockTransport),
and the asset-enrichment mapping. run_intune_sync itself is DB/graph
integration; these are its correctness-critical units.
"""

from __future__ import annotations

from datetime import UTC

import httpx
import pytest

from app.assets.models import Asset
from app.connectors.intune_sync import _enrich_asset, _fetch_managed_devices, _parse_iso


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
