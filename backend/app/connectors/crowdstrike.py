"""CrowdStrike Falcon Spotlight + CSPM connector."""

from __future__ import annotations

import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedMisconfiguration, NormalizedVulnerability

logger = structlog.get_logger()

# Severity mapping
CS_SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "informational": "INFO",
    "none": "INFO",
}

# CSPM category mapping from CrowdStrike policy types
CS_CSPM_CATEGORY_MAP = {
    "IAM": "IAM",
    "Network": "NETWORK",
    "Encryption": "ENCRYPTION",
    "Logging": "LOGGING",
    "Storage": "STORAGE",
    "Compute": "COMPUTE",
    "Database": "DATABASE",
    "Container": "CONTAINER",
    "Secrets": "SECRETS",
}


class CrowdStrikeConnector(BaseConnector):
    source_name = "CROWDSTRIKE"

    def __init__(self):
        self.base_url: str = "https://api.crowdstrike.com"
        self.access_token: str | None = None
        self.client: httpx.AsyncClient | None = None

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        """Get OAuth2 token from CrowdStrike."""
        self.base_url = config.get("base_url", credentials.get("base_url", self.base_url))
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30)

        try:
            resp = await self.client.post(
                "/oauth2/token",
                data={
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                },
            )
            if resp.status_code == 201:
                self.access_token = resp.json().get("access_token")
                logger.info("crowdstrike_auth_success")
                return True
            else:
                logger.error("crowdstrike_auth_failed", status=resp.status_code)
                return False
        except Exception as e:
            logger.error("crowdstrike_auth_error", error=str(e))
            return False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        """Fetch vulnerabilities from CrowdStrike Spotlight."""
        if not self.client or not self.access_token:
            return []

        all_vulns: list[NormalizedVulnerability] = []
        after = None
        page = 0

        while True:
            params = {
                "filter": "status:'open'",
                "limit": 400,
                "facets": "cve",
            }
            if after:
                params["after"] = after

            try:
                resp = await self.client.get(
                    "/spotlight/combined/vulnerabilities/v1",
                    headers=self._headers(),
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("crowdstrike_vuln_fetch_error", page=page, error=str(e))
                break

            resources = data.get("resources", [])
            if not resources:
                break

            for item in resources:
                cve = item.get("cve", {})
                host = item.get("host_info", {})
                app_info = item.get("app", {})
                remediation = item.get("remediation", {})

                severity_raw = cve.get("base_score_severity", "").lower()
                severity = CS_SEVERITY_MAP.get(severity_raw, "MEDIUM")

                vuln = NormalizedVulnerability(
                    cve_id=item.get("cve", {}).get("id"),
                    vulnerability_name=cve.get("description", "")[:500] if cve.get("description") else None,
                    cvss_v3_score=cve.get("base_score"),
                    severity=severity,
                    exploit_available=bool(cve.get("exploit_status")),
                    source_vuln_id=item.get("id"),
                    affected_product=app_info.get("product_name_version"),
                    hostname=host.get("hostname"),
                    ip_addresses=[host.get("local_ip")] if host.get("local_ip") else [],
                    os_name=host.get("os_version"),
                    remediation_info=remediation.get("action"),
                )
                all_vulns.append(vuln)

            # Pagination
            meta = data.get("meta", {}).get("pagination", {})
            after = meta.get("after")
            if not after or len(resources) < 400:
                break
            page += 1

        logger.info("crowdstrike_vulns_fetched", count=len(all_vulns))
        return all_vulns

    async def fetch_misconfigurations(self) -> list[NormalizedMisconfiguration]:
        """Fetch CSPM policy violations from CrowdStrike Horizon."""
        if not self.client or not self.access_token:
            return []

        all_findings: list[NormalizedMisconfiguration] = []
        next_token = None
        page = 0

        while True:
            params = {
                "filter": "status:'fail'",
                "limit": 500,
            }
            if next_token:
                params["next_token"] = next_token

            try:
                resp = await self.client.get(
                    "/detects/entities/iom/v2",
                    headers=self._headers(),
                    params=params,
                )

                # CSPM API may not be available — gracefully handle
                if resp.status_code == 403:
                    logger.info("crowdstrike_cspm_not_licensed")
                    break
                if resp.status_code == 404:
                    logger.info("crowdstrike_cspm_endpoint_not_found")
                    break

                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError:
                break
            except Exception as e:
                logger.error("crowdstrike_cspm_fetch_error", page=page, error=str(e))
                break

            resources = data.get("resources", [])
            if not resources:
                break

            for item in resources:
                policy = item.get("policy_statement", "")
                severity_raw = item.get("severity", "medium").lower()
                severity = CS_SEVERITY_MAP.get(severity_raw, "MEDIUM")

                category_raw = item.get("policy_type", "Other")
                category = CS_CSPM_CATEGORY_MAP.get(category_raw, "OTHER")

                cloud = item.get("cloud_provider", "").upper()
                if cloud not in ("AWS", "AZURE", "GCP"):
                    cloud = None

                finding = NormalizedMisconfiguration(
                    rule_id=item.get("policy_id", ""),
                    rule_name=item.get("policy_statement", "Unknown policy")[:500],
                    rule_description=item.get("policy_description"),
                    category=category,
                    severity=severity,
                    frameworks=item.get("benchmark", []),
                    resource_id=item.get("resource_id", ""),
                    resource_name=item.get("resource_name"),
                    resource_type=item.get("resource_type"),
                    resource_region=item.get("region"),
                    cloud_provider=cloud,
                    cloud_account_id=item.get("cloud_account_id"),
                    source_finding_id=item.get("id"),
                    remediation_info=item.get("remediation"),
                )
                all_findings.append(finding)

            meta = data.get("meta", {}).get("pagination", {})
            next_token = meta.get("next_token")
            if not next_token or len(resources) < 500:
                break
            page += 1

        logger.info("crowdstrike_cspm_fetched", count=len(all_findings))
        return all_findings

    async def close(self):
        if self.client:
            await self.client.aclose()
