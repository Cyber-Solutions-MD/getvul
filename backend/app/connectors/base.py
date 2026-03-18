"""Abstract base class for all vulnerability/CSPM connectors."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime


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
