"""Phase 32 Plan 04 — per-connector real internet_facing detection (EXPO-02).

Proves, per connector, whether a real vendor-supplied internet-facing /
public-exposure signal is mapped into `NormalizedVulnerability.internet_facing`
or whether the connector legitimately has no such signal (documented
FALLBACK — `internet_facing` stays the dataclass default of `None`, so
`infer_exposure_context`'s external_ip/tag proxy applies downstream).

See `app/assets/exposure.py`'s module docstring for the full honest
per-connector coverage table (this session's inspection of all 6 connectors'
actual raw payload/GraphQL response shape, re-verified against 32-PATTERNS.md
and 32-RESEARCH.md's prior findings — no field name here is guessed).
"""

from __future__ import annotations

import pytest

from app.connectors.crowdstrike import CrowdStrikeConnector


def test_placeholder_crowdstrike_normalize_has_internet_facing_attribute():
    """RED-phase placeholder (Task 1) — filled in with the full per-connector
    coverage sweep in Task 3. Must fail until `NormalizedVulnerability`
    carries the `internet_facing` field at all."""
    conn = CrowdStrikeConnector()
    item = {"vulnerability_id": "CVE-2024-9999", "aid": "a1", "apps": []}
    v = conn._normalize_vuln(item, "CRITICAL")
    assert v is not None
    assert hasattr(v, "internet_facing")
    assert v.internet_facing is None
