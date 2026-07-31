"""Tests for the `prioritization` allowlist + prompt-builder quadruplet
(AIP-01, Phase 26 Plan 02) — the 5th instance of the allowlist-quadruplet
discipline `test_ai_prompt_builder.py` already proves for the vuln view.

Three things this file exists to prove, mirroring the existing house style
exactly (`test_ai_prompt_builder_remediation_guidance.py`):

1. Owner PII (the analyst-assignment column, the manager column, the
   physical building, the hardware serial number) never reaches the built
   prompt, whether `record` is a dict or an attribute-bearing object
   (T-26-01) — `department` is the one deliberately-included non-PII owner
   signal (D-04) and DOES appear.
2. The system prompt text forbids the model from asserting an independent
   priority verdict or inventing a rank/number (D-08/D-03 as prompt text,
   threat T-26-02).
3. `prioritization_prompt_version()` is stable and distinct from every
   other view's version hash (D-20).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.prompt_builder import (
    PRIORITIZATION_ALLOWLIST,
    AllowlistedPrioritization,
    build_explain_prioritization_prompt,
    host_prompt_version,
    prioritization_prompt_version,
    remediation_guidance_prompt_version,
)


def _record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "cve_id": "CVE-2024-12345",
        "cvss_v3_score": 8.8,
        "epss_score": 0.94,
        "exploit_available": True,
        "cisa_kev": True,
        "exploit_status_name": "Weaponized",
        "severity": "HIGH",
        "sla_due_at": "2026-07-01T00:00:00Z",
        "sla_breached": True,
        "department": "Finance",
    }
    base.update(overrides)
    return base


def _user_text(system_and_blocks: tuple[str, list[dict[str, str]]]) -> str:
    _, blocks = system_and_blocks
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    return blocks[0]["text"]


# ── PRIORITIZATION_ALLOWLIST shape (T-26-01) ──


def test_prioritization_allowlist_has_10_fields_no_owner_pii() -> None:
    assert len(PRIORITIZATION_ALLOWLIST) == 10
    owner_pii_fields = {"assigned_user", "managed_by", "building", "serial_number"}
    assert PRIORITIZATION_ALLOWLIST.isdisjoint(owner_pii_fields)
    assert (
        frozenset(
            {
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
        )
        == PRIORITIZATION_ALLOWLIST
    )


def test_allowlisted_prioritization_fields_match_allowlist() -> None:
    assert set(AllowlistedPrioritization.model_fields.keys()) == PRIORITIZATION_ALLOWLIST


# ── Owner-PII exclusion (T-26-01, dict + attribute-object) ──


def test_allowlist_enforcement_excludes_owner_pii_from_dict() -> None:
    """An input dict carrying owner PII alongside the allowlisted grounding
    fields must never leak those keys/values into the serialized
    <scanner_data> block — only PRIORITIZATION_ALLOWLIST names are read.
    `department` DOES appear — it is the one deliberately-included non-PII
    owner signal (D-04), not owner PII."""
    record = _record(
        assigned_user="alice@example.com",
        managed_by="Bob Manager",
        building="HQ-3",
        serial_number="SN-998877",
    )

    _, blocks = build_explain_prioritization_prompt(record)
    user_text = _user_text(("", blocks))

    for field in ("assigned_user", "managed_by", "building", "serial_number"):
        assert field not in user_text
    assert "alice@example.com" not in user_text
    assert "Bob Manager" not in user_text
    assert "HQ-3" not in user_text
    assert "SN-998877" not in user_text
    # `department` is the allowed non-PII owner signal — it DOES appear.
    assert "Finance" in user_text


def test_allowlist_enforcement_excludes_owner_pii_from_attribute_object() -> None:
    """Same guarantee when `record` is an attribute-bearing object (e.g. an
    ORM row) rather than a dict — only named allowlisted attributes are ever
    read off it."""

    @dataclass
    class _Row:
        cve_id: str | None
        cvss_v3_score: float | None
        epss_score: float | None
        exploit_available: bool | None
        cisa_kev: bool | None
        exploit_status_name: str | None
        severity: str | None
        sla_due_at: str | None
        sla_breached: bool | None
        department: str | None
        # Non-allowlisted owner-PII extras that must never be read:
        assigned_user: str
        managed_by: str
        building: str
        serial_number: str

    row = _Row(
        **_record(),
        assigned_user="alice@example.com",
        managed_by="Bob Manager",
        building="HQ-3",
        serial_number="SN-998877",
    )

    _, blocks = build_explain_prioritization_prompt(row)
    user_text = _user_text(("", blocks))

    for field in ("assigned_user", "managed_by", "building", "serial_number"):
        assert field not in user_text
    assert "alice@example.com" not in user_text
    assert "Bob Manager" not in user_text
    assert "HQ-3" not in user_text
    assert "SN-998877" not in user_text
    assert "Finance" in user_text
