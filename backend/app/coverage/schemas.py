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


class BlindSpotAssetListResponse(BaseModel):
    """Mirrors the existing `/assets` pagination envelope
    (`{items,total,page,page_size,pages}`, `assets/router.py::list_assets`)
    verbatim, plus `has_authoritative_inventory` (D-11) so the frontend can
    distinguish "no MDM/HR connector configured" from "fully covered, zero
    blind spots" -- never a misleading 0%/100% or a total-assets fallback.
    """

    model_config = ConfigDict(from_attributes=True)

    items: list[BlindSpotAssetResponse]
    total: int
    page: int
    page_size: int
    pages: int
    has_authoritative_inventory: bool
