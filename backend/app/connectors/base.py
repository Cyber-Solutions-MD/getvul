"""Abstract base class for all vulnerability/CSPM connectors."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedVulnerability:
    """Normalized vulnerability finding from any source."""

    cve_id: str | None
    vulnerability_name: str | None
    cvss_v3_score: float | None
    severity: str
    exploit_available: bool = False
    cisa_kev: bool = False
    source_vuln_id: str | None = None
    affected_product: str | None = None
    affected_version: str | None = None
    fixed_version: str | None = None
    remediation_info: str | None = None
    hostname: str | None = None
    ip_addresses: list[str] = field(default_factory=list)
    os_name: str | None = None
    os_version: str | None = None
    asset_type: str = "ENDPOINT"
    # Classification hints from the source (e.g., CrowdStrike product_type_desc)
    platform_name: str | None = None
    product_type_desc: str | None = None
    # Device enrichment from the source
    serial_number: str | None = None
    mac_address: str | None = None
    external_ip: str | None = None
    # Phase 32 Plan 04 (EXPO-02): REAL per-connector internet-facing/
    # public-exposure signal, set by a connector's normalize step ONLY when
    # its raw vendor payload genuinely supports it. None (the default) means
    # "no vendor signal" -- app/assets/exposure.py's infer_exposure_context
    # then falls back to the external_ip/tag proxy. See exposure.py's module
    # docstring for the honest per-connector coverage table.
    internet_facing: bool | None = None
    last_login_user: str | None = None
    last_login_at: str | None = None
    last_seen_at: str | None = None
    host_status: str | None = None
    containment_status: str | None = None
    system_manufacturer: str | None = None
    system_product_name: str | None = None
    crowdstrike_aid: str | None = None
    file_paths: list[str] | None = None  # Paths where the vulnerable software was detected
    # ENRICH-03/D-05 (Phase 31 Plan 01): generic vendor-native composite pair --
    # raw value/label verbatim (no cross-scale normalization; that's Phase 33).
    # None for connectors with no vendor-authored composite (Defender, Wiz).
    native_priority_score: float | None = None
    native_priority_rating: str | None = None
    # ENRICH-04/D-07/D-08: curated per-connector allowlist keyed by raw vendor
    # field name. Omission = missing; a present key with a falsy value = negative.
    source_signals: dict[str, Any] | None = None


@dataclass
class NormalizedMisconfiguration:
    """Normalized CSPM misconfiguration from any source."""

    rule_id: str
    rule_name: str
    rule_description: str | None = None
    category: str = "OTHER"
    severity: str = "MEDIUM"
    frameworks: list[str] = field(default_factory=list)
    resource_id: str = ""
    resource_name: str | None = None
    resource_type: str | None = None
    resource_region: str | None = None
    cloud_provider: str | None = None
    cloud_account_id: str | None = None
    cloud_account_name: str | None = None
    source_finding_id: str | None = None
    remediation_info: str | None = None
    remediation_url: str | None = None
    details: dict | None = None


class BaseConnector(abc.ABC):
    """Abstract connector that all integrations must implement."""

    source_name: str

    @abc.abstractmethod
    async def authenticate(self, credentials: dict, config: dict) -> bool:
        """Authenticate with the vendor API. Returns True on success."""
        ...

    @abc.abstractmethod
    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        """Fetch and normalize vulnerability findings."""
        ...

    async def fetch_misconfigurations(self) -> list[NormalizedMisconfiguration]:
        """Fetch and normalize CSPM findings. Override if supported."""
        return []
