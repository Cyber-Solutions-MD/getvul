"""Tests for app.ai.grounding.has_actionable_remediation_text() and
get_remediation_guidance_context() (D-01/D-10, Plan 01 Task 2).

`has_actionable_remediation_text()` is the D-01 pre-generation refuse
predicate: treats empty string / generic placeholder / sub-minimum-length
text as ABSENT, never just `None` (25-RESEARCH.md Pattern 1 / Pitfall 1 --
Rapid7's own fetch-failure path persists a literal "").

`get_remediation_guidance_context()` is the new per-finding, tenant-scoped,
PII-excluding grounding query (25-RESEARCH.md Pattern 2) -- mirrors
`get_asset_posture()`'s narrow-SELECT + tenant-scoped-404 shape, but is
neither a reuse of `get_vulnerability()` (no OS columns) nor
`get_remediation_group()` (cross-asset CVE aggregate, wrong scope for one
finding).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.ai.grounding import (
    MIN_REMEDIATION_CHARS,
    get_remediation_guidance_context,
    has_actionable_remediation_text,
)

# ── Seed helpers ─────────────────────────────────────────────────────────


async def _seed_asset(db_session, tenant_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    from app.assets.models import Asset

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "hostname": f"host-{uuid.uuid4().hex[:8]}",
        "os_name": "Ubuntu",
        "os_version": "22.04",
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
        "exploit_available": False,
        "cisa_kev": False,
        "source": "NESSUS",
        "source_vuln_id": str(uuid.uuid4()),
        "affected_product": "OpenSSL",
        "affected_version": "1.1.1",
        "fixed_version": "1.1.1w",
        "remediation_action": None,
        "remediation_info": "Upgrade OpenSSL to 1.1.1w or later.",
        "status": "OPEN",
        "first_detected_at": datetime.now(UTC),
        "last_seen_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    vuln = Vulnerability(**defaults)
    db_session.add(vuln)
    await db_session.commit()
    return vuln.id


# ── has_actionable_remediation_text (D-01 refuse predicate) ──────────────


def test_both_none_is_not_actionable() -> None:
    assert has_actionable_remediation_text(None, None) is False


def test_both_empty_string_is_not_actionable() -> None:
    """Rapid7's own fetch-failure path persists a literal '' -- `is not
    None` would wrongly treat this as present (Pitfall 1)."""
    assert has_actionable_remediation_text("", "") is False


@pytest.mark.parametrize(
    "placeholder",
    ["Unknown", "N/A", "None", "No remediation info", "No remediation info available", "-"],
)
def test_generic_placeholders_are_not_actionable(placeholder: str) -> None:
    assert has_actionable_remediation_text(placeholder, None) is False
    assert has_actionable_remediation_text(None, placeholder) is False


def test_real_fix_text_is_actionable() -> None:
    assert has_actionable_remediation_text("Upgrade OpenSSL to 3.0.14 or later.", None) is True


def test_short_text_below_minimum_is_not_actionable() -> None:
    text = "x" * (MIN_REMEDIATION_CHARS - 1)
    assert len(text) < MIN_REMEDIATION_CHARS
    assert has_actionable_remediation_text(text, None) is False


def test_crowdstrike_synthesized_update_product_text_is_actionable() -> None:
    """25-RESEARCH.md Assumptions A1: CrowdStrike's connector-synthesized
    'Update {product} to the latest version' contains a real,
    asset-specific product name -- NOT added to the placeholder denylist."""
    text = "Update Google Chrome to the latest version"
    assert len(text) >= MIN_REMEDIATION_CHARS
    assert has_actionable_remediation_text(text, None) is True


def test_remediation_info_fallback_used_when_action_absent() -> None:
    assert has_actionable_remediation_text(None, "Upgrade to version 9.4.2 immediately.") is True


def test_empty_string_is_not_treated_as_present_via_is_not_none() -> None:
    """Structural proof: the empty-string case must not be treated as
    'present' the way a naive `is not None` check would."""
    assert has_actionable_remediation_text("", "Upgrade to version 9.4.2 immediately.") is True
    assert has_actionable_remediation_text("", "") is False


# ── get_remediation_guidance_context (tenant-scoped, PII-excluding) ──────

_OWNER_PII_KEYS = {"assigned_user", "directory_user", "managed_by", "building", "serial_number", "department"}


async def test_returns_none_for_foreign_tenant_finding(db_session, tenant_a, tenant_b):
    asset_id = await _seed_asset(db_session, tenant_a)
    finding_id = await _seed_finding(db_session, tenant_a, asset_id)

    record = await get_remediation_guidance_context(db_session, tenant_b, finding_id)
    assert record is None


async def test_returns_none_for_missing_finding_id(db_session, tenant_a):
    record = await get_remediation_guidance_context(db_session, tenant_a, uuid.uuid4())
    assert record is None


async def test_returns_12_key_allowlisted_dict_for_a_valid_finding(db_session, tenant_a):
    asset_id = await _seed_asset(db_session, tenant_a, hostname="web-prod-03", os_name="Ubuntu", os_version="22.04")
    finding_id = await _seed_finding(
        db_session,
        tenant_a,
        asset_id,
        cve_id="CVE-2024-1234",
        remediation_info="Upgrade OpenSSL to 3.0.14 or later.",
    )

    record = await get_remediation_guidance_context(db_session, tenant_a, finding_id)

    assert record is not None
    assert len(record) == 12
    assert record["cve_id"] == "CVE-2024-1234"
    assert record["remediation_info"] == "Upgrade OpenSSL to 3.0.14 or later."
    assert record["asset_hostname"] == "web-prod-03"
    assert record["os_name"] == "Ubuntu"
    assert record["os_version"] == "22.04"
    assert not (set(record.keys()) & _OWNER_PII_KEYS)


async def test_owner_pii_columns_never_selected(db_session, tenant_a):
    """Belt-and-suspenders with the source-level grep (T-25-01 defense-in-
    depth): even a finding with an asset present never surfaces a PII key."""
    asset_id = await _seed_asset(db_session, tenant_a)
    finding_id = await _seed_finding(db_session, tenant_a, asset_id)

    record = await get_remediation_guidance_context(db_session, tenant_a, finding_id)
    assert record is not None
    for pii_key in _OWNER_PII_KEYS:
        assert pii_key not in record


async def test_returns_none_asset_hostname_when_asset_is_null(db_session, tenant_a):
    """outerjoin -- a finding with no linked asset still resolves (never a
    404 just because the asset relationship is absent)."""
    finding_id = await _seed_finding(db_session, tenant_a, None)

    record = await get_remediation_guidance_context(db_session, tenant_a, finding_id)
    assert record is not None
    assert record["asset_hostname"] is None
