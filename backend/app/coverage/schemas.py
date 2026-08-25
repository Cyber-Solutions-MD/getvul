"""Pydantic schemas for coverage endpoints (Phase 41 Plan 01 -- COV-01
tracer slice: the blind-spot asset list response). Mirrors
`app/exceptions/schemas.py`'s response-model conventions -- deliberately
narrow, no pre-formatted display field invented ahead of need (Plan 02/03
extend additively for COV-02/COV-03).

`BlindSpotAssetResponse` renames a couple of ORM columns for a cleaner
frontend-facing contract (`category` <- `Asset.device_category`, `os` <-
`Asset.os_name`) -- callers build this explicitly in `service.py` rather
than via `model_validate(asset, from_attributes=True)`, since the attribute
names don't match 1:1.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BlindSpotAssetResponse(BaseModel):
    """A single never-scanned authoritative-inventory asset row (D-01/D-02)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hostname: str
    category: str | None
    os: str | None
    last_seen_at: datetime | None
    seen_by_sources: list[str]


class CoverageConnectorCardResponse(BaseModel):
    """One enabled scanner connector's coverage card (Phase 41 Plan 03,
    COV-02): what fraction of the authoritative (MDM/HR) inventory it
    actually touches (D-05), plus staleness (D-06) and wire-normalized
    sync status (Pitfall 3 -- never a raw uppercase DB value)."""

    model_config = ConfigDict(from_attributes=True)

    connector_type: str
    # D-11 misleading-number guard: null (never 0 or 100) when the
    # authoritative-asset denominator is zero.
    coverage_pct: int | None
    # D-06: strict `now - last_sync_at > 7 days`, never >=.
    is_stale: bool
    stale_days: int | None
    # Wire-normalized via app.connectors.service._normalize_sync_status
    # ("ok"|"failed"|"syncing"|None) -- never the raw uppercase DB value.
    last_sync_status: str | None
    last_sync_at: datetime | None


class CoverageSummaryResponse(BaseModel):
    """GET /coverage/summary (COV-02): the per-connector coverage strip
    the frontend renders above the blind-spot list."""

    model_config = ConfigDict(from_attributes=True)

    cards: list[CoverageConnectorCardResponse]
    total_authoritative_assets: int
    has_authoritative_inventory: bool
    # True when >=1 enabled scanner connector exists at all -- distinct from
    # has_authoritative_inventory, so the frontend can render a
    # scanner-specific empty variant ("No scanner connected") when inventory
    # exists but no scanner connector does.
    has_scanner_connector: bool


class RouteToOwnerResponse(BaseModel):
    """POST /assets/{asset_id}/route-to-owner (Phase 41 Plan 04, COV-03):
    the notify-only result of resolving a never-scanned asset's owner and
    telling them to onboard it (D-07) -- `routed_to` is either the resolved
    owner's display name/email, or the literal "your admins" fallback
    string (D-09) when no owner resolves."""

    model_config = ConfigDict(from_attributes=True)

    hostname: str
    routed_to: str


class BlindSpotAssetListResponse(BaseModel):
    """Mirrors the existing `/assets` pagination envelope
    (`{items,total,page,page_size,pages}`, `assets/router.py::list_assets`)
    verbatim, plus two authoritative-inventory signals (D-11) so the
    frontend can distinguish "no MDM/HR connector configured" from "fully
    covered, zero blind spots" -- never a misleading 0%/100% or a
    total-assets fallback:

      has_authoritative_inventory -- any authoritative asset exists at all.
      total_authoritative_assets  -- the real count, needed by the
        frontend's "All {N} devices in your inventory..." quiet-win empty
        copy (41-UI-SPEC.md) -- `total` above is the BLIND-SPOT count
        (deliberately 0 in that same quiet-win state), so it cannot supply
        this number. Named to match the field 41-PATTERNS.md already
        anticipates on the future `/coverage/summary` (COV-02) response.
    """

    model_config = ConfigDict(from_attributes=True)

    items: list[BlindSpotAssetResponse]
    total: int
    page: int
    page_size: int
    pages: int
    has_authoritative_inventory: bool
    total_authoritative_assets: int
