"""Tests for app.ai.grounding.get_prioritization_context() (D-04, Phase 26
Plan 01 Task 1).

`get_prioritization_context()` is the 5th grounding-query quadruplet member
(26-PATTERNS.md "backend/app/ai/grounding.py -- add
get_prioritization_context()") -- mirrors `get_remediation_guidance_context()`'s
narrow-SELECT + tenant-scoped-None shape exactly, but returns D-04's 8
scoring/exploit/SLA factor columns + `cve_id` + `Asset.department` (the ONE
allowed owner factor) instead of remediation-text columns. Owner PII
(`assigned_user`/`managed_by`/`building`/`serial_number`) must never be
fetched -- T-26-01's defense-in-depth, proven here as a positive
negative-assertion on the returned dict's keys.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.ai.grounding import get_prioritization_context

# ── Seed helpers ─────────────────────────────────────────────────────────


async def _seed_asset(db_session, tenant_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    from app.assets.models import Asset

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "hostname": f"host-{uuid.uuid4().hex[:8]}",
        "department": "Finance",
    }
    defaults.update(overrides)
    asset = Asset(**defaults)
    db_session.add(asset)
    await db_session.commit()  # visible to the app's OWN, independently-connected session
    return asset.id


async def _seed_finding(db_session, tenant_id: uuid.UUID, asset_id: uuid.UUID | None, **overrides: Any) -> uuid.UUID:
    from app.vulnerabilities.models import Vulnerability

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "asset_id": asset_id,
        "cve_id": "CVE-2024-9999",
        "vulnerability_name": "Sample Vuln",
        "severity": "HIGH",
        "cvss_v3_score": 7.5,
        "epss_score": 0.4500,
        "exploit_available": True,
        "cisa_kev": True,
        "exploit_status_name": "Weaponized",
        "source": "NESSUS",
        "source_vuln_id": str(uuid.uuid4()),
        "status": "OPEN",
        "first_detected_at": datetime.now(UTC),
        "last_seen_at": datetime.now(UTC),
        "sla_due_at": datetime.now(UTC),
        "sla_breached": True,
    }
    defaults.update(overrides)
    vuln = Vulnerability(**defaults)
    db_session.add(vuln)
    await db_session.commit()
    return vuln.id


# ── get_prioritization_context (tenant-scoped, PII-excluding) ───────────

_OWNER_PII_KEYS = {"assigned_user", "managed_by", "building", "serial_number"}
_EXPECTED_KEYS = {
    "cve_id",
    "cvss_v3_score",
    "epss_score",
    "exploit_available",
    "cisa_kev",
    "exploit_status_name",
    "severity",
    "sla_due_at",
    "sla_breached",
    "department",
}


async def test_returns_none_for_foreign_tenant_finding(db_session, tenant_a, tenant_b):
    asset_id = await _seed_asset(db_session, tenant_a)
    finding_id = await _seed_finding(db_session, tenant_a, asset_id)

    record = await get_prioritization_context(db_session, tenant_b, finding_id)
    assert record is None


async def test_returns_none_for_missing_finding_id(db_session, tenant_a):
    record = await get_prioritization_context(db_session, tenant_a, uuid.uuid4())
    assert record is None


async def test_returns_10_key_dict_with_department_for_a_valid_finding(db_session, tenant_a):
    asset_id = await _seed_asset(db_session, tenant_a, department="Finance")
    finding_id = await _seed_finding(
        db_session,
        tenant_a,
        asset_id,
        cve_id="CVE-2024-1234",
        severity="CRITICAL",
    )

    record = await get_prioritization_context(db_session, tenant_a, finding_id)

    assert record is not None
    assert set(record.keys()) == _EXPECTED_KEYS
    assert record["cve_id"] == "CVE-2024-1234"
    assert record["severity"] == "CRITICAL"
    assert record["department"] == "Finance"
    assert not (set(record.keys()) & _OWNER_PII_KEYS)


async def test_owner_pii_columns_never_selected(db_session, tenant_a):
    """Belt-and-suspenders with the source-level grep (T-26-01 defense-in-
    depth): even a finding with an asset present never surfaces a PII key."""
    asset_id = await _seed_asset(db_session, tenant_a)
    finding_id = await _seed_finding(db_session, tenant_a, asset_id)

    record = await get_prioritization_context(db_session, tenant_a, finding_id)
    assert record is not None
    for pii_key in _OWNER_PII_KEYS:
        assert pii_key not in record


async def test_returns_department_none_when_asset_is_null(db_session, tenant_a):
    """outerjoin -- a finding with no linked asset still resolves (never a
    404 just because the asset relationship is absent)."""
    finding_id = await _seed_finding(db_session, tenant_a, None)

    record = await get_prioritization_context(db_session, tenant_a, finding_id)
    assert record is not None
    assert record["department"] is None
