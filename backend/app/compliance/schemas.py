"""Pydantic schemas for the compliance endpoint (Phase 43 Plan 01, RPT-03
tracer slice). Mirrors `app/coverage/schemas.py`'s response conventions
(`ConfigDict(from_attributes=True)`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ControlStatusResponse(BaseModel):
    """One framework-control row (D-08/D-13): program-level status,
    evidenced by a posture metric -- never per-CVE tagged. `value` is
    `None` exactly when `status == "not_measured"` (the metric's
    denominator was zero) -- a control is never rendered as a fabricated
    pass or fail on absent data."""

    model_config = ConfigDict(from_attributes=True)

    framework: str  # "soc2" | "iso27001" | "pci_dss" | "nist_csf"
    control_id: str
    title: str
    metric_key: str
    value: float | None
    status: Literal["pass", "partial", "fail", "not_measured"]


class ComplianceOverviewResponse(BaseModel):
    """GET /api/v1/compliance/overview (RPT-03): every catalog control
    across all four frameworks (D-12), tenant-scoped."""

    model_config = ConfigDict(from_attributes=True)

    controls: list[ControlStatusResponse]
